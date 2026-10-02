"""Stage 4: thumbnails in a stand-in bathroom shell (floor, walls, ceiling, warm light, a 1.8 m
reference figure): front 3/4 from the room, inside the shower, the controls (closed and turned,
hand shower lifted out), the rain head and the drain. Nothing is saved into the .blend.

  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/render.py -- [--quick] [--out DIR] [--suffix S] [--only NAME]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import shower_common as C  # noqa: E402
from arcology_blender import curves  # noqa: E402
from arcology_blender.scene import setup_gpu  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still  # noqa: E402

ROOM_Y = -3.50                   # the bathroom extends 3.5 m in front of the glass line
WARM = (1.0, 0.78, 0.58)         # ~3000 K

VIEWS = {
    "front": dict(camera=(-0.95, -2.70, 1.62), target=(0.20, 0.10, 1.12), lens=20.0),
    "inside": dict(camera=(-1.25, -0.55, 1.62), target=(0.55, 0.45, 1.25), lens=16.0),
    "controls": dict(camera=(-0.36, -0.28, 1.36), target=(-0.33, 0.70, 1.30), lens=30.0),
    "controls_open": dict(camera=(-0.36, -0.28, 1.36), target=(-0.33, 0.70, 1.30), lens=30.0),
    "rain": dict(camera=(-0.35, -0.45, 1.55), target=(0.50, 0.0, 2.60), lens=26.0),
    "shelf": dict(camera=(0.20, -0.25, 1.50), target=(0.85, 0.63, 1.17), lens=28.0),
    "drain": dict(camera=(-0.15, 0.15, 0.55), target=(0.35, 0.66, 0.0), lens=35.0),
}


def mat(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(color) + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def quad(name, pts, material, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata(pts, [], [(0, 1, 2, 3)])
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def area(coll, name, loc, look, size, energy, color=WARM, shape="SQUARE", size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size, ld.color = energy, size, color
    if size_y is not None:
        ld.shape, ld.size_y = "RECTANGLE", size_y
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


def figure(coll, material, base=(-0.90, -1.35, 0.0)):
    """1.8 m reference figure (lathed mannequin)."""
    prof = [(0.0, 0.0), (0.13, 0.0), (0.15, 0.40), (0.17, 0.85), (0.20, 1.10), (0.22, 1.35), (0.20, 1.45),
            (0.07, 1.52), (0.06, 1.56), (0.10, 1.62), (0.11, 1.70), (0.09, 1.77), (0.05, 1.795), (0.0, 1.80)]
    bm = bmesh.new()
    curves.lathe(bm, prof, segments=24, center=base)
    me = bpy.data.meshes.new("RefFigure")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new("RefFigure", me)
    for p in me.polygons:
        p.use_smooth = True
    coll.objects.link(ob)
    return ob


def shell(scene):
    coll = bpy.data.collections.new("RenderShell")
    scene.collection.children.link(coll)
    floor = mat("r_floor", (0.20, 0.20, 0.205), 0.35)
    plaster = mat("r_plaster", (0.62, 0.59, 0.54), 0.85)
    ceil = mat("r_ceiling", (0.70, 0.69, 0.66), 0.9)
    hx, hy, top = C.HX, C.HY, C.CEIL
    quad("r_floor", [(-hx, ROOM_Y, 0), (hx, ROOM_Y, 0), (hx, hy, 0), (-hx, hy, 0)], floor, coll)
    quad("r_back", [(-hx, hy, 0), (hx, hy, 0), (hx, hy, top), (-hx, hy, top)], plaster, coll)
    quad("r_north", [(hx, ROOM_Y, 0), (hx, hy, 0), (hx, hy, top), (hx, ROOM_Y, top)], plaster, coll)
    quad("r_south", [(-hx, hy, 0), (-hx, ROOM_Y, 0), (-hx, ROOM_Y, top), (-hx, hy, top)], plaster, coll)
    quad("r_ceiling", [(-hx, hy, top), (hx, hy, top), (hx, ROOM_Y, top), (-hx, ROOM_Y, top)], ceil, coll)
    fig = figure(coll, mat("r_figure", (0.35, 0.36, 0.38), 0.6))
    # Room light (a ceiling panel), a downlight in the shower, a weak fill from the room side
    area(coll, "r_room", (0.0, -2.2, top - 0.02), (0.0, -2.2, 0.0), 1.2, 260.0)
    area(coll, "r_shower", (-0.60, 0.05, top - 0.02), (-0.60, 0.05, 0.0), 0.25, 70.0)
    area(coll, "r_niche", (0.85, 0.62, top - 0.02), (0.85, 0.62, 0.0), 0.2, 30.0, size_y=1.0)
    area(coll, "r_fill", (0.6, -3.3, 1.6), (0.0, 0.0, 1.2), 1.5, 60.0, (0.95, 0.97, 1.0))
    world = scene.world or bpy.data.worlds.new("RenderWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.20, 0.19, 0.18, 1)
    bg.inputs["Strength"].default_value = 0.25
    return fig


def pose(open_=False):
    flow, temp, hand = (bpy.data.objects[n] for n in ("MixerFlow", "MixerTemp", "Handheld"))
    flow.rotation_euler = (0.0, math.radians(-C.FLOW_TRAVEL) if open_ else 0.0, 0.0)
    temp.rotation_euler = (0.0, math.radians(-60.0) if open_ else 0.0, 0.0)
    a = C.HAND_ROT.to_3x3() @ Vector((0.0, 0.0, 1.0))
    hand.location = C.SEAT + (a * 0.16 + Vector((0.0, -0.10, 0.0)) if open_ else Vector())
    bpy.context.view_layer.update()


def main():
    opt = render_options(C.SCRATCH)
    only = opt.value("--only")
    scene = bpy.context.scene
    setup_gpu(scene)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.8
    for ob in C.collision_objects():
        ob.hide_render = True
    fig = shell(scene)
    cam = bpy.data.objects.new("RenderCam", bpy.data.cameras.new("RenderCam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.clip_start = 0.02
    for name, view in VIEWS.items():
        if only and name not in only.split(","):
            continue
        pose(open_=name == "controls_open")
        fig.hide_render = name != "front"
        aim(cam, **view)
        render_still(scene, os.path.join(opt.out, f"{C.NAME}_{name}{opt.suffix}.png"), opt.samples)
    pose(False)


if __name__ == "__main__":
    main()
