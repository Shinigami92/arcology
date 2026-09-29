"""Stage 4: studio thumbnails (3/4 from the foot, close on pillows and duvet). Not saved.

  blender -b --factory-startup blender/props/bed__opus-high.blend --python blender/props/bed__opus-high/render.py -- [--quick] [--out DIR] [--suffix NAME]

Works on the built (procedural) or the baked .blend. Thumbnails go to
--out DIR (default: the scratch folder from bed_common).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathutils import Vector  # noqa: E402

import bpy  # noqa: E402

import bed_common as C  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

FRONT = dict(camera=(2.55, -3.05, 1.75), target=(0.0, -0.05, 0.42), lens=36.0)
DETAIL = dict(camera=(0.95, -0.15, 1.12), target=(-0.12, 0.62, 0.56), lens=40.0)
VIEWS = {"front": FRONT, "detail": DETAIL}


def aim(cam, camera, target, lens):
    cam.location = Vector(camera)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else C.SCRATCH
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""
    views = args[args.index("--views") + 1].split(";") if "--views" in args else list(VIEWS)
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    cam = studio(scene, **FRONT)
    for ob in C.collision_objects():
        ob.hide_render = True
    for i, v in enumerate(views):
        if v in VIEWS:
            aim(cam, **VIEWS[v])
        else:  # custom "x,y,z,tx,ty,tz,lens", views separated by ";"
            n = [float(a) for a in v.split(",")]
            aim(cam, n[0:3], n[3:6], n[6])
            v = f"custom{i}"
        render_still(scene, os.path.join(out, f"bed_{C.TAG}_{v}{suffix}.png"), samples)


if __name__ == "__main__":
    main()
