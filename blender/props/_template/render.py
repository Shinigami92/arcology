"""Stage 4: studio thumbnails (3/4 front, close-up). Not saved into the .blend.

  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/render.py -- [--quick] [--out DIR] [--suffix NAME]

Works before baking too (the src_ materials render directly). Look at the result.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from template_common import NAME, SCRATCH, collision_objects  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

FRONT = dict(camera=(1.05, -1.35, 0.95), target=(0.0, 0.0, 0.26), lens=45.0)
DETAIL = dict(camera=(0.40, -0.55, 0.70), target=(0.05, -0.05, 0.42), lens=50.0)


def main():
    opt = render_options(SCRATCH)
    scene = bpy.context.scene
    cam = studio(scene, key=500.0, fill=200.0, rim=300.0, **FRONT)  # a small prop needs less light
    for ob in collision_objects():
        ob.hide_render = True
    render_still(scene, os.path.join(opt.out, f"{NAME}_front{opt.suffix}.png"), opt.samples)
    aim(cam, **DETAIL)
    render_still(scene, os.path.join(opt.out, f"{NAME}_detail{opt.suffix}.png"), opt.samples)


if __name__ == "__main__":
    main()
