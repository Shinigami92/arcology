"""Skirting boards (D-036): one glb swept along the runs the apartment generator computes.
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

Input: tools/blockout/apartment_skirting.json, written by `python tools/blockout/apartment.py`
(format: tools/blockout/skirting.py). Runs are polylines in Godot world coordinates (x, z) at
floor level, one unit normal per segment pointing into the room; the polyline is the wall face.
A layout change only means re-running these stages. `-- --runs <file>` (relative to the repo
root) reads another run file; outputs are named after its stem.

Stages (Blender 5.2, background, from the repo root):

  blender -b --factory-startup --python blender/architecture/skirting/build.py [-- --runs F]
  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/bake.py
  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/export.py [-- --runs F]
  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/architecture/skirting/verify.py [-- --runs F]

Output: assets/architecture/skirting/<stem>.glb, authored at world positions (glb origin =
world origin, Godot places it at (0, 0, 0)), one material `skirting_paint`, no collision.

Coordinates: Blender (x, y, z) = Godot (x, -z, y). The profile's back sits on the polyline,
its bottom on the floor (z = 0), its face looks along the run normal.

Finish: one small trim sheet (skirting_trim.py, numpy, deterministic) with real-world UVs:
U along the run (1024 px = one 2.4 m board, the sheet tiles along U), V up the profile.
Board joints are the sheet's seam at U = 0; build.py offsets each wall's U so the joints
fall where a carpenter would put them (see `joint_offsets`).
"""

import ast
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, repo_path, scratch_dir, script_args  # noqa: E402

DEFAULT_RUNS = ("tools", "blockout", "apartment_skirting.json")
APARTMENT_PY = ("tools", "blockout", "apartment.py")  # parsed (ast), never run: door/window placements
SCRATCH = scratch_dir("skirting")

# --- Profile (height and the thickness limit come from the run file) ----------------------
THICKNESS = 0.009      # <= profile.thickness (10 mm) and below the thinnest casing edge (9.5 mm)
CASING_MIN = 0.0095    # interior door casing at its wall edge (door_interior: 9.5 mm; entrance 12 mm)
TOP_R = 0.0035         # round-over on the top front edge
TOP_STEPS = 6
ARRIS_R = 0.002        # eased arris on outside corners (radius at the face)
ARRIS_STEPS = 4
RUB_MARGIN = 0.03      # rubbed paint fades off an outside corner over this distance

# --- Finish -------------------------------------------------------------------------------
MAT = "skirting_paint"
BOARD = 2.4            # board length = the sheet's U period
TRIM_W, TRIM_H = 1024, 256
TRIM_PX_PER_M = TRIM_W / BOARD   # 426.7 px/m
JOINT_CLEAR = 0.3      # no joint closer than this to a corner or an end
BAND_ROWS = 40         # visible profile arc (face + round-over + top) is 87.5 mm = 37.3 rows
PLAIN_ROWS = 8         # back and bottom (hidden)
TRIM_PAD = 8
BANDS = ("paint", "paint_rub", "paint_arris")   # face; near outside corners; on the arris
PLAIN = "paint_plain"

# Colors (linear). Same paint as the interior door frames (door_interior FRAME_PAINT).
FRAME_PAINT = (0.275, 0.254, 0.216)   # sRGB ~#8F8A80
PRIMER = (0.62, 0.60, 0.56)           # paint rubbed through to the undercoat
RUBBER = (0.07, 0.065, 0.06)          # shoe scuffs
DUST = (0.40, 0.385, 0.36)
PAINT_ROUGH = 0.34                    # semi-gloss/satin, as the frames

# Render-only context
WALL_HEIGHT = 2.6
WALL_PLASTER_TILE = 4.0
VINYL_TILE = 7.32
CARPET_TILE = 4.0


def runs_path(args=None):
    args = script_args() if args is None else args
    if "--runs" in args:
        p = args[args.index("--runs") + 1]
        return p if os.path.isabs(p) else repo_path(p)
    return repo_path(*DEFAULT_RUNS)


def load_runs(path=None):
    with open(path or runs_path(), encoding="utf-8") as f:
        return json.load(f)


def stem(path=None):
    return os.path.splitext(os.path.basename(path or runs_path()))[0]


def blend_path(path=None):
    return output_path("blender", "architecture", f"{stem(path)}.blend")


def glb_path(path=None):
    return output_path("assets", "architecture", "skirting", f"{stem(path)}.glb")


def to_blender(p):
    """Godot (x, z) on the floor -> Blender (x, y, 0)."""
    return Vector((p[0], -p[1], 0.0))


def normal_to_blender(nrm):
    return Vector((nrm[0], -nrm[1], 0.0))


def profile(height):
    """Closed profile (s, v), counter-clockwise, starting at the front bottom edge:
    face, round-over, top, back, bottom. Returns (points, bands per segment)."""
    t, r = THICKNESS, TOP_R
    pts = [(t, 0.0), (t, height - r)]
    for k in range(1, TOP_STEPS):
        a = math.pi / 2 * k / TOP_STEPS
        pts.append((t - r + r * math.cos(a), height - r + r * math.sin(a)))
    pts += [(t - r, height), (0.0, height), (0.0, 0.0)]
    bands = ["paint"] * (len(pts) - 2) + [PLAIN, PLAIN]
    return pts, bands


def segment_count(run):
    return len(run["points"]) - (0 if run["closed"] else 1)


def joint_offsets(length, seed):
    """U offset for one wall segment of `length` m so the sheet's seam (U = 0 mod BOARD)
    falls on realistic joints: none on walls up to a board long, else joints spaced one
    board apart and centered, so both end pieces are longer than half a board. Joint-free
    walls get a deterministic shift (seed) so neighbors show different parts of the sheet."""
    joints = max(0, math.ceil(length / BOARD - 1e-9) - 1)
    if joints == 0:
        room = BOARD - 2 * JOINT_CLEAR - length
        frac = ((seed * 0.618034) % 1.0) if room > 0 else 0.5
        start = JOINT_CLEAR + frac * room if room > 0 else (BOARD - length) / 2
        return start
    first = (length - (joints - 1) * BOARD) / 2   # distance from the start to the first joint
    return -first


def joints_of(length, offset):
    """Distances along a segment where the seam (U = m * BOARD) falls, for checks and reports."""
    out = []
    m = math.ceil(offset / BOARD - 1e-9)
    while m * BOARD - offset <= length + 1e-9:
        out.append(m * BOARD - offset)
        m += 1
    return out


# --- Placements from the apartment generator (parsed, not run) --------------------------------
def _assign(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def apartment_placements():
    """Door frames (glb, Godot position, yaw) and window frames from tools/blockout/apartment.py:
    [(name, glb path, (x, y, z), yaw_deg)]. For renders and the casing checks in verify.py."""
    with open(repo_path(*APARTMENT_PY), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    frames = _assign(tree, "FRAMES")
    out = []
    for name, key, pos, rot in _assign(tree, "INSTANCES"):
        if key in frames:
            out.append((name, repo_path(*frames[key].split("/")), tuple(pos), rot[1]))
    north = _assign(tree, "NORTH")
    for spec, node, x, _ in _assign(tree, "WINDOWS"):
        glb = repo_path("assets", "architecture", "windows", spec, f"{spec}_frame.glb")
        out.append((node, glb, (x, 0.0, north), 0.0))
    return out


def door_leaf_glb(frame_glb):
    p = frame_glb.replace("_frame.glb", "_leaf.glb")
    return p if os.path.exists(p) else None


def g2b(p):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return (p[0], -p[2], p[1])


def import_glb(path, coll):
    """Import a glb into `coll`; returns the new objects (render and verify context, never saved).
    The glTF importer reuses a node group named "glTF Material Output" and expects all of its
    sockets; bake.final_material's group only has Occlusion, so ours is renamed first."""
    import bpy
    ng = bpy.data.node_groups.get("glTF Material Output")
    if ng is not None and "Iridescence Factor" not in ng.interface.items_tree:
        ng.name = "glTF Material Output (occlusion only)"
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    return new


def place(objs, name, loc, yaw_deg, coll, local=(0.0, 0.0, 0.0)):
    """Parent imported objects to an empty at `loc` (Blender) turned by a Godot yaw (= Blender Z);
    `local` shifts them in the empty's frame (a door leaf's hinge in frame coordinates)."""
    import bpy
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    root.location = loc
    root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    for o in objs:
        if o.parent is None:
            o.parent = root
            o.location = Vector(o.location) + Vector(local)
    return root


def skirting_objects():
    return part_objects("body", mesh_only=True)
