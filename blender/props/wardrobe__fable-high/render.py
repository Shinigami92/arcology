"""Stage 4: studio thumbnails, doors closed and both open. Not saved.

  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/render.py -- [--quick] [--out DIR]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import SCRATCH, TAG, door_objects  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

RENDER_OPEN_DEG = 100.0


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else SCRATCH
    os.makedirs(out, exist_ok=True)

    scene = bpy.context.scene
    studio(scene, camera=(2.7, -3.7, 1.7), target=(0.0, -0.45, 1.05), lens=42.0)
    left, right = bpy.data.objects["DoorLeft"], bpy.data.objects["DoorRight"]
    for ob in door_objects("left") + door_objects("right"):
        ob.hide_render = False

    left.rotation_euler = right.rotation_euler = (0, 0, 0)
    render_still(scene, os.path.join(out, f"wardrobe_{TAG}_closed.png"), samples)
    left.rotation_euler = (0, 0, math.radians(-RENDER_OPEN_DEG))
    right.rotation_euler = (0, 0, math.radians(RENDER_OPEN_DEG))
    render_still(scene, os.path.join(out, f"wardrobe_{TAG}_open.png"), samples)
    left.rotation_euler = right.rotation_euler = (0, 0, 0)


if __name__ == "__main__":
    main()
