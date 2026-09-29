"""Stage 4: studio thumbnails, drawer closed and pulled out 0.2 m, lamp lit. Not saved.

  blender -b --factory-startup blender/props/nightstand_square.blend --python blender/props/nightstand_square/render.py -- [--quick] [--out DIR]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import DRAWER_ORIGIN, LIGHT_MAT, SCRATCH  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

OPEN = 0.20  # thumbnail pull-out (the contract allows 0.28)
LIT_STRENGTH = 3.5  # brighter than the exported 1.0: the studio lights are strong


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else SCRATCH
    os.makedirs(out, exist_ok=True)

    scene = bpy.context.scene
    # Close camera for a 0.55 m prop with a 0.4 m lamp on top; the studio's floor is at z = 0.
    studio(scene, camera=(1.02, -1.28, 1.02), target=(0.0, -0.02, 0.47), lens=50.0, key=700.0, fill=300.0)
    drawer = bpy.data.objects["Drawer"]
    bsdf = [n for n in bpy.data.materials[LIGHT_MAT].node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
    strength = bsdf.inputs["Emission Strength"]
    saved = strength.default_value
    strength.default_value = LIT_STRENGTH

    drawer.location = DRAWER_ORIGIN
    render_still(scene, os.path.join(out, "nightstand_square_closed.png"), samples)
    drawer.location = DRAWER_ORIGIN + type(DRAWER_ORIGIN)((0.0, -OPEN, 0.0))
    render_still(scene, os.path.join(out, "nightstand_square_open.png"), samples)

    drawer.location = DRAWER_ORIGIN
    strength.default_value = saved


if __name__ == "__main__":
    main()
