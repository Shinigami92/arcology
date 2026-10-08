"""Stage 4: Cycles stills (not saved into the .blend).

  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/render.py -- [--quick] [--out DIR] [--views a,b] [--studio | --context] [--wb K]

Every asset renders in the corridor at night: plaster walls on the trim runs up to the ceiling
(2.8 m), carpet_tiles floor, ceiling plaster, the neighbor doors (entrance frame and leaf) as
tools/blockout/corridor.py places them (its constants are evaluated from the source, not run),
the other kit glbs that exist at their generator positions, warm-neutral ceiling light and a
1.8 m grey reference figure. The fixtures also get a studio close-up.
"""

import ast
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from corridor_common import (  # noqa: E402
    ASSETS, SCRATCH, WARM_NEUTRAL, asset_of_blend, body_objects, glb_path, load_runs, to_blender,
)
from arcology_blender.bake import final_material  # noqa: E402
from arcology_blender.scene import repo_path, set_colorspace, setup_gpu  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

CEILING = 2.8
FLOOR_TILE, WALL_TILE = 4.0, 4.0


def g2b(p):
    """Godot (x, y, z) -> Blender (x, -z, y)."""
    return Vector((p[0], -p[2], p[1]))


# name: camera, target (Godot), lens
TRIM_VIEWS = {
    "main_long": dict(camera=(-5.6, 1.62, 8.0), target=(4.0, 1.0, 8.4), lens=24.0),
    "outside_corner": dict(camera=(7.75, 1.35, 8.25), target=(8.8, 0.75, 7.0), lens=30.0),
    "rail_close": dict(camera=(10.05, 1.30, 7.42), target=(10.5, 0.98, 7.0), lens=32.0),
    "joint_close": dict(camera=(10.25, 0.70, 7.40), target=(10.5, 0.55, 7.0), lens=35.0),
    "door_end": dict(camera=(3.5, 1.25, 8.35), target=(4.5, 0.55, 9.4), lens=30.0),
    "side_corridor": dict(camera=(7.6, 1.6, -2.4), target=(7.8, 0.9, 6.0), lens=24.0),
}


# --- generator constants (evaluated, not run) ----------------------------------------------------
_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.USub: lambda a: -a, ast.UAdd: lambda a: a}


def _value(node, ns):
    """Literals, earlier constants, + - * / and tuples/lists of them; anything else raises."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in ns:
        return ns[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_value(node.left, ns), _value(node.right, ns))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_value(node.operand, ns))
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_value(e, ns) for e in node.elts]
    raise ValueError(ast.dump(node))


def generator_constants():
    """Module-level constants of the blockout generators (parsed; nothing is executed)."""
    ns = {}
    for rel in (("tools", "blockout", "blockout.py"), ("tools", "blockout", "corridor.py")):
        with open(repo_path(*rel), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            try:
                val = _value(node.value, ns)
            except (ValueError, TypeError, ZeroDivisionError):
                continue
            if isinstance(target, ast.Name):
                ns[target.id] = val
            elif isinstance(target, ast.Tuple) and all(isinstance(e, ast.Name) for e in target.elts):
                for e, v in zip(target.elts, val):  # MAIN_N, MAIN_S = 6.9, 9.5
                    ns[e.id] = v
    return ns


def door_entrance_hinge():
    import importlib.util
    path = repo_path("blender", "props", "door_entrance", "door_entrance_common.py")
    spec = importlib.util.spec_from_file_location("door_entrance_common", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return tuple(mod.HINGE)


def import_glb(path, coll):
    """Import a glb into `coll` (render context, never saved). The glTF importer reuses a node
    group named "glTF Material Output" and expects all of its sockets; bake.final_material's
    group only has Occlusion, so ours is renamed first."""
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


def place(objs, name, loc, yaw_deg, coll, local=(0.0, 0.0, 0.0), roll=None):
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    root.location = loc
    root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg)) if roll is None else roll
    for o in objs:
        if o.parent is None:
            o.parent = root
            o.location = Vector(o.location) + Vector(local)
    return root


# --- context -------------------------------------------------------------------------------------
def surface_material(name):
    imgs = {}
    for k in ("albedo", "normal", "orm"):
        img = bpy.data.images.load(repo_path("assets", "materials", "surfaces", name, f"{name}_{k}.png"),
                                   check_existing=True)
        set_colorspace(img, "sRGB" if k == "albedo" else "Non-Color")
        imgs[k] = img
    return final_material(f"surf_{name}", imgs["albedo"], imgs["normal"], imgs["orm"])


def quad(name, corners, uv_axes, tile, mat, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in corners], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        c = Vector(corners[loop.vertex_index])
        uv.data[li].uv = (c.dot(Vector(uv_axes[0])) / tile, c.dot(Vector(uv_axes[1])) / tile)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def corridor(coll, skip=()):
    """Walls, floor, ceiling, doors, the other kit glbs, lights. Returns the generator constants."""
    c = generator_constants()
    data = load_runs()
    up = Vector((0, 0, 1))
    wall = surface_material("wall_plaster")
    for ri, run in enumerate(data["runs"]):
        pts = [to_blender(p) for p in run["points"]]
        nseg = len(pts) - (0 if run["closed"] else 1)
        for si in range(nseg):
            a, b = pts[si], pts[(si + 1) % len(pts)]
            n = Vector((run["normals"][si][0], -run["normals"][si][1], 0.0))
            d = (b - a).normalized()
            corners = [a, b, b + up * CEILING, a + up * CEILING]
            if (corners[1] - corners[0]).cross(corners[3] - corners[0]).dot(n) < 0:
                corners = [b, a, a + up * CEILING, b + up * CEILING]
            quad(f"Wall{ri}_{si}", corners, (tuple(d), (0, 0, 1)), WALL_TILE, wall, coll)
    xs = [p[0] for r in data["runs"] for p in r["points"]]
    zs = [p[1] for r in data["runs"] for p in r["points"]]
    x0, x1, z0, z1 = min(xs) - 1, max(xs) + 1, min(zs) - 1, max(zs) + 1
    floor = [(x0, -z0, 0), (x1, -z0, 0), (x1, -z1, 0), (x0, -z1, 0)]
    quad("Floor", floor, ((1, 0, 0), (0, 1, 0)), FLOOR_TILE, surface_material("carpet_tiles"), coll)
    ceil = [(x0, -z0, CEILING), (x0, -z1, CEILING), (x1, -z1, CEILING), (x1, -z0, CEILING)]
    quad("Ceiling", ceil, ((1, 0, 0), (0, 1, 0)), WALL_TILE, surface_material("ceiling_plaster"), coll)

    # neighbor doors: the entrance door's frame and leaf, header above
    frame = repo_path("assets", "props", "door_entrance", "door_entrance_frame.glb")
    leaf = repo_path("assets", "props", "door_entrance", "door_entrance_leaf.glb")
    hinge = door_entrance_hinge()
    T = c.get("T", 0.2)
    doors = [(name, (line, 0, at) if axis == "z" else (at, 0, line), yaw) for name, axis, line, at, yaw, _ in c["DOORS"]]
    if "ENTRANCE" in c:
        doors.append(("Entrance", tuple(c["ENTRANCE"][0]), c["ENTRANCE"][1]))
    for name, pos, yaw in doors:
        loc = g2b(pos)
        place(import_glb(frame, coll), name, loc, yaw, coll)
        place(import_glb(leaf, coll), name + "Leaf", loc, yaw, coll, local=hinge)
        cs, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        for side in (-T / 2, T / 2):
            pts = []
            for lx, lz in ((-0.7, 2.0), (0.7, 2.0), (0.7, CEILING), (-0.7, CEILING)):
                pts.append((loc[0] + lx * cs - side * sn, loc[1] + lx * sn + side * cs, lz))
            quad(f"{name}Header{side}", pts, ((1, 0, 0), (0, 0, 1)), WALL_TILE, wall, coll)

    # the other kit glbs at the generator's spots
    H = c["H"]
    lamps = ([(c["SIDE_X"], z, 90) for z in (-1.5, 2.0, 5.2)]
             + [(x, c["MAIN_Z"], 0) for x in (-5.0, 0.0, 4.5, 9.5, 17.5)] + [(c["LOBBY_X"], 10.8, 0)])
    if "corridor_trim" not in skip and os.path.exists(glb_path("corridor_trim")):
        import_glb(glb_path("corridor_trim"), coll)
    if "corridor_light" not in skip and os.path.exists(glb_path("corridor_light")):
        for i, (x, z, yaw) in enumerate(lamps):
            place(import_glb(glb_path("corridor_light"), coll), f"Lamp{i}", g2b((x, H, z)), yaw, coll)
    vents = [(c["SIDE_X"], 0.3, 90), (c["SIDE_X"], 3.6, 90), (-2.5, c["MAIN_Z"], 0), (2.2, c["MAIN_Z"], 0),
             (7.0, c["MAIN_Z"], 0), (15.5, c["MAIN_Z"], 0), (19.5, c["MAIN_Z"], 0)]
    if "corridor_vent" not in skip and os.path.exists(glb_path("corridor_vent")):
        for i, (x, z, yaw) in enumerate(vents):
            place(import_glb(glb_path("corridor_vent"), coll), f"Vent{i}", g2b((x, H, z)), yaw, coll)
    if "exit_sign" not in skip and os.path.exists(glb_path("exit_sign")):
        place(import_glb(glb_path("exit_sign"), coll), "Exit", g2b((c["MAIN_W"] + T / 2, 2.35, c["MAIN_Z"])), 90, coll)
    if "holo_emitter" not in skip and os.path.exists(glb_path("holo_emitter")):
        for i, (x, z) in enumerate(((c["SIDE_X"], c["MAIN_S"] - T / 2 - 0.15), (1.5, c["MAIN_N"] + T / 2 + 0.15),
                                    (17.0, c["MAIN_N"] + T / 2 + 0.15))):
            place(import_glb(glb_path("holo_emitter"), coll), f"Emitter{i}", g2b((x, H, z)), 0, coll)
    for i, (x, z, yaw) in enumerate(lamps):
        ld = bpy.data.lights.new(f"LampLight{i}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = (1.1, 0.12) if yaw == 0 else (0.12, 1.1)
        ld.energy = 140.0
        ld.color = WARM_NEUTRAL
        ob = bpy.data.objects.new(f"LampLight{i}", ld)
        ob.location = g2b((x, H - 0.035, z))
        ob.rotation_euler = (0, 0, 0)  # area lights shine down -Z
        coll.objects.link(ob)
    return c


def reference_figure(coll, pos):
    """A 1.8 m grey capsule person (scale check)."""
    import bmesh
    m = bpy.data.materials.new("RefFigure")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.36, 1)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.17, radius2=0.19, depth=1.5,
                          matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.75)))
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.12,
                              matrix=__import__("mathutils").Matrix.Translation((0, 0, 1.68)))
    me = bpy.data.meshes.new("RefFigure")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new("RefFigure", me)
    ob.location = g2b(pos)
    coll.objects.link(ob)


def night(scene):
    world = bpy.data.worlds.new("Night")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.025, 0.04, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12
    scene.world = world


def render_context(asset, views, opt):
    scene = bpy.context.scene
    coll = bpy.data.collections.new("Context")
    scene.collection.children.link(coll)
    if asset == "corridor_trim":
        corridor(coll, skip=(asset,))      # the trim is in this .blend at its world position
    else:
        for ob in body_objects():          # the fixture sits at the origin here: show the exported glb in place
            ob.hide_render = True
        corridor(coll)
    reference_figure(coll, (-2.2, 0.0, 8.6))
    night(scene)
    setup_gpu(scene)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.clip_start = 0.01
    coll.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.resolution_percentage = 100
    scene.cycles.samples = opt.samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    wb = float(opt.value("--wb", "0"))     # the ceiling light is warm-neutral on purpose: no correction by default
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = wb > 0
        if wb > 0:
            scene.view_settings.white_balance_temperature = wb
    scene.render.image_settings.file_format = "PNG"
    names = opt.value("--views", ",".join(views)).split(",")
    for name in names:
        v = views[name]
        aim(cam, g2b(v["camera"]), g2b(v["target"]), v["lens"])
        scene.render.filepath = os.path.join(opt.out, f"{asset}_{name}{opt.suffix}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)


def render_studio(asset, opt):
    """Close-up of a fixture on a studio floor (turned so its face looks at the camera)."""
    import fixtures
    spec = fixtures.STUDIO[asset]
    scene = bpy.context.scene
    for ob in body_objects():
        ob.rotation_euler = spec.get("rotation", (0.0, 0.0, 0.0))
        ob.location = spec.get("location", (0.0, 0.0, 0.0))
    cam = studio(scene, key=spec.get("key", 300.0), fill=120.0, rim=200.0, camera=spec["camera"],
                 target=spec["target"], lens=spec["lens"])
    render_still(scene, os.path.join(opt.out, f"{asset}_studio{opt.suffix}.png"), opt.samples)
    if "detail" in spec:
        aim(cam, **spec["detail"])
        render_still(scene, os.path.join(opt.out, f"{asset}_detail{opt.suffix}.png"), opt.samples)


def main():
    asset = asset_of_blend(bpy.data.filepath)
    opt = render_options(SCRATCH, samples=128, quick_samples=32)
    if asset == "corridor_trim":
        render_context(asset, TRIM_VIEWS, opt)
        return
    import fixtures
    if opt.has("--studio") or not opt.has("--context"):
        render_studio(asset, opt)
    if opt.has("--context") or not opt.has("--studio"):
        bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)  # undo the studio turn
        render_context(asset, fixtures.CONTEXT_VIEWS[asset], opt)


if __name__ == "__main__":
    assert set(ASSETS)
    main()
