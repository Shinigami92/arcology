"""Stage 4: studio thumbnails, door closed (light off) and open (light on). Not saved.

  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/render.py -- [--quick] [--suffix NAME]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import LIGHT_MAT, NAME, OPEN_DEG, SCRATCH, door_objects  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""

    scene = bpy.context.scene
    studio(scene)
    door = bpy.data.objects["Door"]
    strength = bpy.data.materials[LIGHT_MAT].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for ob in door_objects():
        ob.hide_render = False

    saved = strength.default_value
    door.rotation_euler = (0, 0, 0)
    strength.default_value = 0.0
    render_still(scene, os.path.join(SCRATCH, f"{NAME}_closed{suffix}.png"), samples)

    door.rotation_euler = (0, 0, math.radians(-OPEN_DEG))
    strength.default_value = 25.0  # brighter than in game: the studio has no dark interior
    render_still(scene, os.path.join(SCRATCH, f"{NAME}_open{suffix}.png"), samples)
    strength.default_value = saved
    door.rotation_euler = (0, 0, 0)


if __name__ == "__main__":
    main()
