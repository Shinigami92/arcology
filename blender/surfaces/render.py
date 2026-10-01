"""Stage 2: Cycles preview of a room corner, once per floor set (not saved).

  blender -b --factory-startup --python blender/surfaces/render.py -- [--quick] [--out DIR] [--floor a,b] [--close]

A 4 x 4 x 2.6 m room: the floor set on the floor, wall_plaster on the walls,
ceiling_plaster on the ceiling, UVs = world position / tile size (what Godot's
world-space triplanar mapping does). Lights: a warm 2700 K ceiling lamp and a
cool blue window in the left wall. --close adds a low view across the floor.
Reads the PNGs written by build.py.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from surfaces_common import FLOORS, PREVIEW, SETS, texture_paths  # noqa: E402
from arcology_blender.bake import final_material  # noqa: E402
from arcology_blender.scene import clear_scene, set_colorspace, setup_gpu  # noqa: E402
from arcology_blender.studio import aim, render_options  # noqa: E402

ROOM, HEIGHT = 4.0, 2.6
WINDOW = dict(y=(0.9, 2.7), z=(0.85, 2.25))  # in the left wall (x = 0)
VIEWS = {
    "": dict(camera=(3.55, 0.45, 1.62), target=(0.35, 3.5, 0.95), lens=17.0),
    "_close": dict(camera=(2.6, 0.6, 1.15), target=(1.3, 2.8, 0.0), lens=24.0),
}


def material(name):
    p = texture_paths(name)
    imgs = {}
    for k, path in p.items():
        img = bpy.data.images.load(path, check_existing=True)
        set_colorspace(img, "sRGB" if k == "albedo" else "Non-Color")
        imgs[k] = img
    return final_material(f"surf_{name}", imgs["albedo"], imgs["normal"], imgs["orm"])


def plane(name, corners, uv_axes, tile, mat, coll):
    """Quad through 4 corners; UV = (corner . axis) / tile per axis (world-space mapping)."""
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


def emitter(name, corners, color, strength, coll):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    me = bpy.data.meshes.new(name)
    me.from_pydata(corners, [], [(0, 1, 2, 3)])
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def light(name, kind, loc, rot, energy, size, coll, color=None, kelvin=None, size_y=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    if kind == "AREA":
        ld.shape = "RECTANGLE" if size_y else "DISK"
        ld.size = size
        if size_y:
            ld.size_y = size_y
    if kelvin and hasattr(ld, "use_temperature"):
        ld.use_temperature = True
        ld.temperature = kelvin
    elif color:
        ld.color = color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


def build_room(floor):
    clear_scene()
    scene = bpy.context.scene
    coll = scene.collection
    R, H = ROOM, HEIGHT
    plane("Floor", [(0, 0, 0), (R, 0, 0), (R, R, 0), (0, R, 0)], ((1, 0, 0), (0, 1, 0)),
          SETS[floor]["tile_m"], material(floor), coll)
    wall = material("wall_plaster")
    wt = SETS["wall_plaster"]["tile_m"]
    y0, y1 = WINDOW["y"]
    z0, z1 = WINDOW["z"]
    # left wall (x = 0) with a window hole: four quads around the opening
    for nm, (ya, yb, za, zb) in {"L1": (0, y0, 0, H), "L2": (y1, R, 0, H), "L3": (y0, y1, 0, z0),
                                  "L4": (y0, y1, z1, H)}.items():
        plane(f"Wall{nm}", [(0, ya, za), (0, yb, za), (0, yb, zb), (0, ya, zb)],
              ((0, 1, 0), (0, 0, 1)), wt, wall, coll)
    plane("WallBack", [(0, R, 0), (R, R, 0), (R, R, H), (0, R, H)], ((1, 0, 0), (0, 0, 1)), wt, wall, coll)
    plane("WallRight", [(R, R, 0), (R, 0, 0), (R, 0, H), (R, R, H)], ((0, -1, 0), (0, 0, 1)), wt, wall, coll)
    plane("WallFront", [(R, 0, 0), (0, 0, 0), (0, 0, H), (R, 0, H)], ((-1, 0, 0), (0, 0, 1)), wt, wall, coll)
    plane("Ceiling", [(0, 0, H), (0, R, H), (R, R, H), (R, 0, H)], ((1, 0, 0), (0, 1, 0)),
          SETS["ceiling_plaster"]["tile_m"], material("ceiling_plaster"), coll)
    # window reveal (0.3 m deep wall), plaster too
    t = 0.3
    for nm, pts in {"RevealBottom": [(-t, y0, z0), (0, y0, z0), (0, y1, z0), (-t, y1, z0)],
                    "RevealTop": [(-t, y0, z1), (-t, y1, z1), (0, y1, z1), (0, y0, z1)],
                    "RevealLeft": [(-t, y0, z0), (-t, y0, z1), (0, y0, z1), (0, y0, z0)],
                    "RevealRight": [(-t, y1, z0), (0, y1, z0), (0, y1, z1), (-t, y1, z1)]}.items():
        axes = ((1, 0, 0), (0, 1, 0)) if "Bottom" in nm or "Top" in nm else ((1, 0, 0), (0, 0, 1))
        plane(nm, pts, axes, wt, wall, coll)
    # window: a night-city glow behind the opening, plus its soft blue spill
    emitter("WindowGlow", [(-0.3, y0, z0), (-0.3, y1, z0), (-0.3, y1, z1), (-0.3, y0, z1)],
            (0.18, 0.30, 0.75), 0.35, coll)
    light("WindowSpill", "AREA", (0.02, (y0 + y1) / 2, (z0 + z1) / 2), (0, math.radians(-90), 0),
          30.0, y1 - y0, coll, color=(0.42, 0.58, 1.0), size_y=z1 - z0)
    # ceiling lamp: warm 2700 K disc
    light("CeilingLamp", "AREA", (2.0, 2.0, H - 0.04), (0, 0, 0), 45.0, 0.45, coll,
          color=(1.0, 0.62, 0.32), kelvin=2700)
    emitter("LampDisc", [(1.78, 1.78, H - 0.03), (1.78, 2.22, H - 0.03), (2.22, 2.22, H - 0.03),
                         (2.22, 1.78, H - 0.03)], (1.0, 0.70, 0.42), 6.0, coll)
    world = bpy.data.worlds.new("Night")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.03, 0.06, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
    scene.world = world
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    coll.objects.link(cam)
    scene.camera = cam
    return scene, cam


def main():
    opt = render_options(PREVIEW, samples=192, quick_samples=48)
    floors = opt.value("--floor", ",".join(FLOORS)).split(",")
    views = {k: v for k, v in VIEWS.items() if k == "" or opt.has("--close")}
    for floor in floors:
        scene, cam = build_room(floor)
        setup_gpu(scene)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1100
        scene.cycles.samples = opt.samples
        scene.cycles.use_denoising = True
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.exposure = 0.0
        if hasattr(scene.view_settings, "use_white_balance"):  # the eye adapts to warm light
            scene.view_settings.use_white_balance = True
            scene.view_settings.white_balance_temperature = 5000.0
            scene.view_settings.white_balance_tint = 0.0
        scene.render.image_settings.file_format = "PNG"
        for suffix, view in views.items():
            aim(cam, **view)
            scene.render.filepath = os.path.join(opt.out, f"room_{floor}{suffix}{opt.suffix}.png")
            bpy.ops.render.render(write_still=True)
            print("RENDERED", scene.render.filepath)


if __name__ == "__main__":
    main()
