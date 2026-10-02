"""Stage 4: studio thumbnails against a plaster wall: front 3/4 (closed), lid open,
seat up, flush plate and roll holder close-ups, a 1.8 m figure for scale. Not saved.

  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/render.py -- [--quick] [--out DIR] [--suffix S] [--views a,b]

Works before baking too (the src_ materials render directly).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

import toilet_common as C  # noqa: E402
from lib_candidates import reference_figure  # noqa: E402
from arcology_blender.geo import bm_box, new_object  # noqa: E402
from arcology_blender.scene import get_collection  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

# name: (lid deg, seat deg, view)
VIEWS = {
    "front": (0.0, 0.0, dict(camera=(1.55, -2.35, 1.35), target=(0.0, -0.25, 0.62), lens=36.0)),
    "lid_open": (C.LID_OPEN_DEG, 0.0, dict(camera=(1.25, -1.75, 1.30), target=(0.0, -0.35, 0.50), lens=36.0)),
    "seat_up": (C.LID_OPEN_DEG, C.SEAT_OPEN_DEG, dict(camera=(-1.05, -1.55, 1.25), target=(0.0, -0.35, 0.50), lens=36.0)),
    "bowl_top": (C.LID_OPEN_DEG, C.SEAT_OPEN_DEG, dict(camera=(0.10, -1.05, 1.15), target=(0.0, -0.45, 0.33), lens=40.0)),
    "plate": (0.0, 0.0, dict(camera=(0.30, -0.75, 1.30), target=(0.0, -0.20, 1.10), lens=55.0)),
    "holder": (0.0, 0.0, dict(camera=(0.75, -0.80, 0.95), target=(0.33, -0.25, 0.70), lens=50.0)),
    "hinge": (60.0, 30.0, dict(camera=(0.55, -0.75, 0.75), target=(0.0, -0.28, 0.43), lens=55.0)),
    "scale": (0.0, 0.0, dict(camera=(2.6, -4.2, 1.5), target=(0.35, -0.3, 0.90), lens=35.0)),
}


def set_hinges(lid_deg, seat_deg):
    bpy.data.objects["Lid"].rotation_euler = (math.radians(-lid_deg), 0.0, 0.0)
    bpy.data.objects["Seat"].rotation_euler = (math.radians(-seat_deg), 0.0, 0.0)
    bpy.context.view_layer.update()


def main():
    opt = render_options(C.SCRATCH)
    scene = bpy.context.scene
    coll = get_collection("RenderOnly")
    bm = bmesh.new()
    bm_box(bm, (-2.0, 0.0, 0.0), (2.0, 0.10, 2.6))
    new_object("RenderWall", bm, coll, material=solid_mat("render_plaster", (0.32, 0.30, 0.27), 0.85))
    bm = bmesh.new()
    reference_figure(bm, (1.25, -0.85, 0.0), 1.8)
    figure = new_object("ReferenceFigure", bm, coll, material=solid_mat("render_figure", (0.20, 0.21, 0.23), 0.6))

    cam = studio(scene, key=420.0, fill=150.0, rim=0.0, **VIEWS["front"][2])
    for ob in C.body_collision_objects():
        ob.hide_render = True
    bpy.data.objects["Roll"].hide_render = True  # the upright original sits inside the box
    only = opt.value("--views")
    for name, (lid, seat, view) in VIEWS.items():
        if only and name not in only.split(","):
            continue
        figure.hide_render = name != "scale"
        set_hinges(lid, seat)
        aim(cam, **view)
        render_still(scene, os.path.join(opt.out, f"{C.NAME}_{name}{opt.suffix}.png"), opt.samples)
    set_hinges(0.0, 0.0)


if __name__ == "__main__":
    main()
