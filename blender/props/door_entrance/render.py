"""Stage 4: studio thumbnails with a slab of plaster wall around the frame and a 1.8 m
reference figure: apartment side closed, corridor side closed, leaf open 70 degrees, close-ups
of the smart lock / thumb-turn and of the corridor hardware. Not saved into the .blend.

  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/render.py -- [--quick] [--out DIR] [--suffix S]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from door_entrance_common import (  # noqa: E402
    BOLT_Z, LX, NAME, OPEN_H, OX, SCRATCH, WALL_Y, frame_collision_objects, frame_objects, hardware_objects,
)
from arcology_blender.curves import lathe  # noqa: E402
from arcology_blender.geo import bm_box, new_object  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

APT = dict(camera=(1.55, -3.0, 1.45), target=(0.05, 0.0, 1.07), lens=30.0)
OPEN = dict(camera=(1.65, -2.55, 1.6), target=(-0.15, -0.35, 1.0), lens=27.0)
LOCK = dict(camera=(LX + 0.30, -0.60, 1.46), target=(LX - 0.03, -0.13, 1.21), lens=50.0)
COR_DETAIL = dict(camera=(-0.02, -0.95, 1.52), target=(-0.17, 0.04, 1.42), lens=38.0)


def wall_and_figure():
    """Plaster wall slab around the opening and a 1.8 m reference figure (render only)."""
    coll = bpy.data.collections.new("RenderProps")
    bpy.context.scene.collection.children.link(coll)
    plaster = solid_mat("RenderPlaster", (0.686, 0.645, 0.552), 0.85)
    bm = bmesh.new()
    bm_box(bm, (-1.6, -WALL_Y, 0.0), (-OX, WALL_Y, 2.6))
    bm_box(bm, (OX, -WALL_Y, 0.0), (1.6, WALL_Y, 2.6))
    bm_box(bm, (-OX, -WALL_Y, OPEN_H), (OX, WALL_Y, 2.6))
    wall = new_object("RenderWall", bm, coll, material=plaster)
    gray = solid_mat("RenderFigure", (0.30, 0.30, 0.31), 0.6)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.13, 0.0), (0.15, 0.10), (0.15, 0.85), (0.17, 1.10), (0.19, 1.40), (0.17, 1.46),
               (0.065, 1.50), (0.065, 1.56), (0.095, 1.62), (0.10, 1.70), (0.085, 1.77), (0.04, 1.80), (0.0, 1.80)],
          segments=24)
    fig = new_object("RenderFigure1.8m", bm, coll, material=gray)
    fig.location = (1.10, -0.75, 0.0)
    for p in fig.data.polygons:
        p.use_smooth = True
    return wall, fig


def main():
    opt = render_options(SCRATCH)
    scene = bpy.context.scene
    cam = studio(scene, key=420.0, fill=150.0, rim=160.0, **APT)
    for ob in frame_collision_objects():
        ob.hide_render = True
    leaf = bpy.data.objects["Leaf"]
    for ob in hardware_objects():
        ob.parent = leaf
        ob.matrix_parent_inverse = leaf.matrix_world.inverted()
    wall, fig = wall_and_figure()

    rig = bpy.data.objects.new("Rig", None)
    scene.collection.objects.link(rig)
    for ob in frame_objects() + frame_collision_objects() + [leaf, wall]:
        ob.parent = rig
    bpy.context.view_layer.update()

    def shot(name, view, rig_deg=0.0, leaf_deg=0.0):
        rig.rotation_euler = (0, 0, math.radians(rig_deg))
        leaf.rotation_euler = (0, 0, math.radians(-leaf_deg))
        aim(cam, **view)
        render_still(scene, os.path.join(opt.out, f"{NAME}_{name}{opt.suffix}.png"), opt.samples)

    shot("apartment_closed", APT)
    shot("corridor_closed", APT, rig_deg=180.0)
    shot("open70", OPEN, leaf_deg=70.0)
    fig.hide_render = True
    shot("lock_closeup", LOCK)
    shot("corridor_detail", COR_DETAIL, rig_deg=180.0)
    print(f"lock at x={LX} z={BOLT_Z}")


if __name__ == "__main__":
    main()
