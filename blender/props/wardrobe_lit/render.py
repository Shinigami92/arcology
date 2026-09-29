"""Stage 4: studio thumbnails, doors closed and open (LED strip on, drawers pulled out). Not saved.

  blender -b --factory-startup blender/props/wardrobe_lit.blend --python blender/props/wardrobe_lit/render.py -- [--quick] [--out DIR] [--detail]

Writes wardrobe_lit_closed.png and wardrobe_lit_open.png (and
with --detail a close-up of the pulls) into --out (default: SCRATCH).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import wardrobe_common as C  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

VIEW = dict(camera=(2.55, -3.85, 1.55), target=(0.0, -0.25, 1.04), lens=35.0)
OPEN_VIEW = dict(camera=(1.25, -4.15, 1.55), target=(0.0, -0.35, 1.04), lens=35.0)
DETAIL = dict(camera=(0.55, -1.05, 1.42), target=(0.0, -0.32, 1.12), lens=40.0)
INSIDE = dict(camera=(0.35, -1.9, 1.35), target=(-0.15, 0.0, 1.20), lens=30.0)


def aim(cam, camera, target, lens):
    cam.location = Vector(camera)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else C.SCRATCH
    os.makedirs(out, exist_ok=True)
    prefix = f"{C.NAME}_{C.TAG}"

    scene = bpy.context.scene
    cam = studio(scene, **VIEW)
    for ob in C.body_collision_objects():
        ob.hide_render = True
    left, right = bpy.data.objects["DoorLeft"], bpy.data.objects["DoorRight"]
    led = bpy.data.materials[C.LIGHT_MAT].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]

    led.default_value = 0.0
    render_still(scene, os.path.join(out, f"{prefix}_closed.png"), samples)
    if "--detail" in args:
        aim(cam, **DETAIL)
        render_still(scene, os.path.join(out, f"{prefix}_detail.png"), samples)
        aim(cam, **VIEW)

    left.rotation_euler = (0.0, 0.0, math.radians(-C.RENDER_DEG))
    right.rotation_euler = (0.0, 0.0, math.radians(C.RENDER_DEG))
    led.default_value = 6.0
    for name in ("Drawer", "DrawerRight"):
        bpy.data.objects[name].location.y -= C.RENDER_DRAWER_OUT
    aim(cam, **OPEN_VIEW)
    render_still(scene, os.path.join(out, f"{prefix}_open.png"), samples)
    if "--detail" in args:
        aim(cam, **INSIDE)
        render_still(scene, os.path.join(out, f"{prefix}_inside.png"), samples)


if __name__ == "__main__":
    main()
