"""Stage 4: studio thumbnails, doors closed, and doors open with the drawers pulled out. Not saved.

  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/render.py -- [--quick] [--out DIR]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import MOVING_PARTS, NAME, SCRATCH, door_objects, prop_root  # noqa: E402
from arcology_blender.scene import part_objects  # noqa: E402
from arcology_blender.studio import render_options, render_still, studio  # noqa: E402

RENDER_OPEN_DEG = 100.0
RENDER_DRAWER_OUT = 0.25


def main():
    opt = render_options(SCRATCH)
    samples, out = opt.samples, opt.out

    scene = bpy.context.scene
    studio(scene, camera=(2.7, -3.7, 1.7), target=(0.0, -0.45, 1.05), lens=42.0)
    left, right = bpy.data.objects["DoorLeft"], bpy.data.objects["DoorRight"]
    for ob in door_objects("left") + door_objects("right") + [o for p in MOVING_PARTS for o in part_objects(p)]:
        ob.hide_render = False
    drawers = [prop_root("drawer_lower"), prop_root("drawer_upper")]

    left.rotation_euler = right.rotation_euler = (0, 0, 0)
    render_still(scene, os.path.join(out, f"{NAME}_closed.png"), samples)
    left.rotation_euler = (0, 0, math.radians(-RENDER_OPEN_DEG))
    right.rotation_euler = (0, 0, math.radians(RENDER_OPEN_DEG))
    for d in drawers:
        d.location.y -= RENDER_DRAWER_OUT
    render_still(scene, os.path.join(out, f"{NAME}_open.png"), samples)
    for d in drawers:
        d.location.y += RENDER_DRAWER_OUT
    left.rotation_euler = right.rotation_euler = (0, 0, 0)


if __name__ == "__main__":
    main()
