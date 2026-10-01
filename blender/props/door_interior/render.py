"""Stage 4: studio thumbnails in a slab of plaster wall with a 1.8 m reference figure:
closed, open 70 deg, lever close-up, hinge close-up (open), back face (thumb-turn). Not saved.

  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/render.py -- [--quick] [--out DIR] [--suffix NAME]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from door_interior_common import NAME, OPEN_H, OPEN_X, SCRATCH, WALL_PLASTER, WALL_Y, frame_collision_objects, mount_hardware  # noqa: E402
from lib_candidates import reference_figure, wall_with_opening  # noqa: E402
from arcology_blender.geo import new_object  # noqa: E402
from arcology_blender.scene import get_collection  # noqa: E402
from arcology_blender.shading import Graph, new_mat, solid_mat  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

VIEWS = {
    "closed": (0.0, dict(camera=(1.75, -3.6, 1.45), target=(0.0, 0.0, 1.12), lens=36.0)),
    "open70": (70.0, dict(camera=(1.55, -3.3, 1.55), target=(-0.25, -0.35, 1.05), lens=34.0)),
    "lever": (0.0, dict(camera=(0.66, -0.52, 1.24), target=(0.30, -0.13, 1.075), lens=55.0)),
    "hinge": (70.0, dict(camera=(-0.80, -0.62, 1.16), target=(-0.43, -0.11, 1.05), lens=50.0)),
    "thumbturn": (0.0, dict(camera=(0.05, 0.40, 1.20), target=(0.34, -0.06, 1.06), lens=55.0)),
    "corner": (0.0, dict(camera=(0.95, -0.75, 0.42), target=(0.47, -0.10, 0.12), lens=45.0)),
    "back": (0.0, dict(camera=(1.0, 1.42, 1.40), target=(0.12, 0.0, 1.02), lens=30.0)),
}


def plaster():
    g = Graph(new_mat("render_plaster"))
    rough = g.add(0.82, g.mul(g.sub(g.noise(6.0, 2.0), 0.5), 0.08))
    n = g.bump(g.noise(90.0, 3.0, 0.6), 0.08, 1.0)
    base = g.scale_color(WALL_PLASTER, g.add(0.97, g.mul(g.noise(1.5, 2.0), 0.06)))
    return g.finish(base, rough, 0.0, n)


def main():
    opt = render_options(SCRATCH)
    scene = bpy.context.scene
    for ob in frame_collision_objects():
        ob.hide_render = True
    mount_hardware()
    leaf = bpy.data.objects["Leaf"]

    coll = get_collection("RenderContext")
    bm = bmesh.new()
    wall_with_opening(bm, -1.6, 1.6, 2.6, -WALL_Y, WALL_Y, -OPEN_X, OPEN_X, OPEN_H)
    new_object("RenderWall", bm, coll, material=plaster())
    bm = bmesh.new()
    reference_figure(bm, (1.05, -0.55, 0.0), 1.8)
    new_object("ReferenceFigure", bm, coll, material=solid_mat("render_figure", (0.20, 0.21, 0.23), 0.6))

    cam = studio(scene, key=420.0, fill=150.0, rim=160.0, **VIEWS["closed"][1])
    back_light = bpy.data.objects.new("BackKey", bpy.data.lights.new("BackKey", "AREA"))
    back_light.data.energy, back_light.data.size = 0.0, 2.0
    coll.objects.link(back_light)
    back_light.location = (1.6, 2.2, 2.4)
    aim(back_light, back_light.location, (0.0, 0.0, 1.0))
    backdrop = bpy.data.objects["StudioBack"]

    only = opt.value("--views")
    for name, (deg, view) in VIEWS.items():
        if only and name not in only.split(","):
            continue
        leaf.rotation_euler = (0.0, 0.0, math.radians(-deg))
        is_back = name in ("back", "thumbturn")
        backdrop.hide_render = is_back
        back_light.data.energy = 140.0 if is_back else 0.0
        aim(cam, **view)
        render_still(scene, os.path.join(opt.out, f"{NAME}_{name}{opt.suffix}.png"), opt.samples)
    leaf.rotation_euler = (0.0, 0.0, 0.0)


if __name__ == "__main__":
    main()
