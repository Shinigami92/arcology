"""Stage 4: Cycles stills of the skirting in context (not saved into the .blend).

  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/render.py -- [--quick] [--out DIR] [--views a,b]

Context, built from the run file and tools/blockout/apartment.py (parsed, not run): plaster
wall faces along every run (extended under the casings at open ends, headers above the
doors), vinyl floor (carpet in the bedroom), the door frame glbs (and the interior leaves)
and the window frames at their placements. Views: an inside corner, an archway outside
corner, an end against a door casing, a long hallway run, a joint close-up, wear and arris close-ups, the end at the living-room window frame.
"""

import importlib.util
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from skirting_common import (  # noqa: E402
    CARPET_TILE, SCRATCH, VINYL_TILE, WALL_HEIGHT, WALL_PLASTER_TILE, apartment_placements, door_leaf_glb, g2b,
    import_glb, load_runs, normal_to_blender, place, segment_count, to_blender,
)
from arcology_blender.bake import final_material  # noqa: E402
from arcology_blender.scene import repo_path, set_colorspace, setup_gpu  # noqa: E402
from arcology_blender.studio import aim, render_options  # noqa: E402


# name: camera and target in Godot coordinates, lens, light (Godot position, watts, kelvin)
VIEWS = {
    "inside_corner": dict(camera=(-2.42, 0.42, 1.30), target=(-3.0, 0.045, 2.0), lens=38.0,
                          light=((-2.3, 2.4, 1.0), 120.0, 3300)),
    "archway_corner": dict(camera=(2.42, 0.40, -0.62), target=(3.08, 0.04, -1.2), lens=36.0,
                           light=((2.2, 2.4, -0.4), 120.0, 3300)),
    "door_end": dict(camera=(1.10, 0.36, 1.50), target=(1.55, 0.05, 2.0), lens=42.0,
                     light=((1.0, 2.4, 1.0), 120.0, 3300)),
    "long_run": dict(camera=(0.40, 0.80, 2.40), target=(-4.2, 0.03, 3.6), lens=26.0,
                     light=((-2.5, 2.4, 2.9), 110.0, 4000)),
    "joint_close": dict(camera=(-1.95, 0.30, 3.22), target=(-2.17, 0.045, 3.6), lens=40.0,
                        light=((-1.6, 2.4, 2.9), 120.0, 4000)),
    "wear_close": dict(camera=(-0.75, 0.30, 1.40), target=(-1.25, 0.035, 2.0), lens=35.0,
                       light=((-0.6, 2.4, 1.2), 120.0, 3300)),
    "arris_close": dict(camera=(2.80, 0.17, -0.93), target=(3.02, 0.04, -1.2), lens=40.0,
                        light=((2.4, 2.4, -0.6), 120.0, 3300)),
    "window_end": dict(camera=(-2.05, 0.40, -2.45), target=(-2.53, 0.04, -3.0), lens=40.0,
                       light=((-1.8, 2.4, -2.2), 120.0, 3300)),
}


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


def walls(data, mat, coll, doors, extend=0.07):
    """Wall faces on the runs; open ends next to a door run on under its casing."""
    up = Vector((0, 0, 1))

    def ext(p):
        return extend if any((p - Vector(g2b(d)).to_2d().to_3d()).length < 0.7 for d in doors) else 0.0

    for ri, run in enumerate(data["runs"]):
        pts = [to_blender(p) for p in run["points"]]
        for si in range(segment_count(run)):
            a, b = pts[si], pts[(si + 1) % len(pts)]
            d = (b - a).normalized()
            if not run["closed"] and si == 0:
                a = a - d * ext(a)
            if not run["closed"] and si == segment_count(run) - 1:
                b = b + d * ext(b)
            n = normal_to_blender(run["normals"][si])
            c = [a, b, b + up * WALL_HEIGHT, a + up * WALL_HEIGHT]
            if (c[1] - c[0]).cross(c[3] - c[0]).dot(n) < 0:
                c = [b, a, a + up * WALL_HEIGHT, b + up * WALL_HEIGHT]
            quad(f"Wall{ri}_{si}", c, (tuple(d), (0, 0, 1)), WALL_PLASTER_TILE, mat, coll)


def floors(vinyl, carpet, coll):
    # Godot rects (x0, z0, x1, z1): bedroom carpet, the rest vinyl (apartment.py floor boxes)
    rects = [((-7.0, -3.2, -3.1, 2.1), carpet, CARPET_TILE), ((-3.1, -3.2, 6.6, 3.8), vinyl, VINYL_TILE),
             ((-7.0, 2.1, -3.1, 3.8), vinyl, VINYL_TILE)]
    for k, ((x0, z0, x1, z1), mat, tile) in enumerate(rects):
        quad(f"Floor{k}", [(x0, -z0, 0), (x0, -z1, 0), (x1, -z1, 0), (x1, -z0, 0)][::-1],
             ((1, 0, 0), (0, 1, 0)), tile, mat, coll)


def _door_hinge():
    path = repo_path("blender", "props", "door_interior", "door_interior_common.py")
    spec = importlib.util.spec_from_file_location("door_interior_common", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return tuple(mod.HINGE)


def context(data, coll):
    wall = surface_material("wall_plaster")
    walls(data, wall, coll, [pos for name, _, pos, _ in apartment_placements() if name.startswith("Door")])
    floors(surface_material("vinyl_plank"), surface_material("carpet"), coll)
    hinge = _door_hinge()
    for name, glb, pos, yaw in apartment_placements():
        if not os.path.exists(glb):
            print("MISSING", glb)
            continue
        loc = g2b(pos)
        place(import_glb(glb, coll), name, loc, yaw, coll)
        leaf = door_leaf_glb(glb)
        if leaf and "door_interior" in glb:
            place(import_glb(leaf, coll), name + "Leaf", loc, yaw, coll, local=hinge)
        if "door" in glb:  # wall header above the opening, both faces
            c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            for side in (-0.1, 0.1):
                pts = []
                for lx, lz in ((-0.6, 2.1), (0.6, 2.1), (0.6, WALL_HEIGHT), (-0.6, WALL_HEIGHT)):
                    x, y = lx, side
                    pts.append((loc[0] + x * c - y * s, loc[1] + x * s + y * c, lz))
                quad(f"{name}Header{side}", pts, ((1, 0, 0), (0, 0, 1)), WALL_PLASTER_TILE, wall, coll)


def light(name, loc, energy, kelvin, coll, size=0.6):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.shape = "DISK"
    ld.size = size
    if hasattr(ld, "use_temperature"):
        ld.use_temperature = True
        ld.temperature = kelvin
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def main():
    opt = render_options(SCRATCH, samples=160, quick_samples=40)
    views = opt.value("--views", ",".join(VIEWS)).split(",")
    scene = bpy.context.scene
    data = load_runs()
    coll = bpy.data.collections.new("Context")
    scene.collection.children.link(coll)
    context(data, coll)
    world = bpy.data.worlds.new("Night")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.035, 0.05, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
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
    if hasattr(scene.view_settings, "use_white_balance"):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = 3800.0
    scene.render.image_settings.file_format = "PNG"
    for name in views:
        v = VIEWS[name]
        lamp = light(f"Lamp_{name}", g2b(v["light"][0]), v["light"][1], v["light"][2], coll)
        aim(cam, g2b(v["camera"]), g2b(v["target"]), v["lens"])
        scene.render.filepath = os.path.join(opt.out, f"skirting_{name}{opt.suffix}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)
        bpy.data.objects.remove(lamp, do_unlink=True)


if __name__ == "__main__":
    main()
