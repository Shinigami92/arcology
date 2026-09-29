"""Stage 4: studio thumbnails (3/4 view from the foot, close-up of pillows and duvet). Not saved.

  blender -b --factory-startup blender/props/bed_padded.blend --python blender/props/bed_padded/render.py -- [--quick] [--out DIR]

Thumbnails go to --out, else ARCOLOGY_RENDER_DIR/<name>/ (default <temp>/arcology/<name>/).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from bed_common import RENDER_NAME, SCRATCH, collision_objects  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

FRONT = dict(camera=(2.45, -3.15, 1.75), target=(0.0, -0.05, 0.50), lens=35.0)
DETAIL = dict(camera=(0.95, -0.55, 1.20), target=(-0.05, 0.50, 0.58), lens=45.0)


def main():
    opt = render_options(SCRATCH)
    samples, out = opt.samples, opt.out
    scene = bpy.context.scene
    # dimmer than the default: off-white linen fills the frame and would blow out
    cam = studio(scene, key=600.0, fill=260.0, rim=380.0, **FRONT)
    for ob in collision_objects():
        ob.hide_render = True
    render_still(scene, os.path.join(out, f"{RENDER_NAME}_front.png"), samples)
    aim(cam, **DETAIL)
    render_still(scene, os.path.join(out, f"{RENDER_NAME}_detail.png"), samples)


if __name__ == "__main__":
    main()
