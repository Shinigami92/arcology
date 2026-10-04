"""Brutalist half of the near city ring (Fifth Element megablocks): contract,
grid, materials, texture layout and paths. Built on blender/lib (D-028); quick
reference: blender/lib/README.md.

The contract comes from tools/city/near_towers.json (the five "brutalist"
towers): name, footprint [x, z] (Godot), top_y (roof slab height in the world,
street at y = -180). Each tower is one glb, origin at the base center on the
street, unrotated; the front (Godot +Z) is Blender -Y.

Stages (Blender 5.2, background, from the repo root):

  blender -b --factory-startup --python blender/architecture/city/brutalist/build.py
  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/bake.py
  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/export.py
  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/render.py -- [--quick] [--out DIR] [--night-only] [--thumbs-only]
  blender -b --factory-startup --python blender/architecture/city/brutalist/verify.py

build.py makes the geometry with UVs into the shared texture layouts
(brutalist_textures.py), bake.py generates the textures (numpy, deterministic,
no Cycles bake: everything tiles) and wires the four shared materials,
export.py writes one glb per tower plus the kit PNGs.

Grid: every facade is laid out in window cells of BAY x FH meters (one
apartment bay by one floor); the window texture is 32 x 32 cells, so faces
offset their UVs in whole cells and the panes stay on the geometry's bays.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, repo_path, scratch_dir  # noqa: E402

NAME = "city_brutalist"
STYLE = "brutalist"
SPEC = repo_path("tools", "city", "near_towers.json")
BLEND = output_path("blender", "architecture", f"{NAME}.blend")
SCRATCH = scratch_dir(NAME)


def asset_dir(*parts):
    return output_path("assets", "architecture", "city", *parts)


def glb_path(tower):
    return asset_dir(tower, f"{tower}.glb")


KIT_DIR = asset_dir("_kit", "brutalist")


def kit_png(mat, kind):
    return os.path.join(KIT_DIR, f"{mat}_{kind}.png")


# --- Contract ------------------------------------------------------------------------
def load_spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def towers(spec=None):
    """The brutalist towers of the JSON, in file order (dicts with the JSON keys plus
    `height` = roof slab above the origin, W (Blender X), D (Blender Y))."""
    spec = spec or load_spec()
    out = []
    for t in spec["towers"]:
        if t["style"] != STYLE:
            continue
        t = dict(t)
        t["height"] = t["top_y"] - spec["street_y"]
        t["W"], t["D"] = t["footprint"]
        out.append(t)
    return out


def eye_blender(spec=None):
    """The apartment eye in Blender world coordinates."""
    spec = spec or load_spec()
    x, y, z = spec["eye"]
    return (x, -z, y)


# --- Grid ------------------------------------------------------------------------------
FH = 3.2       # floor to floor (m)
BAY = 3.0      # window bay (m)
CELLS = 32     # window texture: CELLS x CELLS cells (bays x floors)

# --- Materials (Godot maps each name to one shared material) ---------------------
MAT_CONCRETE = "city_brutal_concrete"
MAT_WINDOWS = "city_brutal_windows"
MAT_METAL = "city_brutal_metal"
MAT_NEON = "city_brutal_neon"
MATERIALS = (MAT_CONCRETE, MAT_WINDOWS, MAT_METAL, MAT_NEON)

TEX = {MAT_CONCRETE: 2048, MAT_WINDOWS: 2048, MAT_METAL: 2048, MAT_NEON: 1024}
PX_PER_M = 64.0              # concrete and metal trim sheets (U repeats every 32 m)
WINDOW_EMISSION = 3.0        # glTF emissive strength of lit windows (Godot: emission energy)
NEON_EMISSION = 6.0          # signs, pad and warning lights

# --- Parts ----------------------------------------------------------------------------
PART_KEY_TOWER = "city_tower"


def tower_objects(name):
    """Render meshes of a tower's glb: the tower and its `<name>_blink` (if any)."""
    return [o for o in part_objects(name, mesh_only=True)]


def all_tower_objects():
    return [o for t in towers() for o in tower_objects(t["name"])]
