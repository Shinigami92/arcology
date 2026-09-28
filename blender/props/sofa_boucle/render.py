"""Stage 4: studio thumbnails: 3/4 front with two pillows, and a fabric close-up. Not saved.

  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/render.py -- [--quick] [--out DIR]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from sofa_common import NAME, SCRATCH, pillow_objects, sofa_collision_objects  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import _look_at, render_still, studio  # noqa: E402

# Where the two pillows sit for the thumbnail: leaning on the outer back cushions.
PILLOW_POSES = (((-0.72, 0.045, 0.655), (76.0, 4.0, -9.0)),
                ((0.70, 0.040, 0.650), (72.0, -6.0, 11.0)))


def place_pillows():
    src = pillow_objects()[0]
    src.hide_render = True
    coll = bpy.context.scene.collection
    for i, (loc, rot) in enumerate(PILLOW_POSES):
        ob = bpy.data.objects.new(f"PillowRender{i + 1}", src.data)
        ob.location = loc
        ob.rotation_euler = [math.radians(a) for a in rot]
        coll.objects.link(ob)


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else SCRATCH
    os.makedirs(out, exist_ok=True)

    scene = bpy.context.scene
    for ob in sofa_collision_objects():
        ob.hide_render = True
    place_pillows()
    cam = studio(scene, camera=(2.7, -3.2, 1.75), target=(0.0, 0.0, 0.42), lens=45.0, key=800.0, fill=300.0)
    # The studio defaults suit a bright appliance; dark fabric needs less exposure to read as its true color.
    scene.view_settings.exposure = -0.8
    render_still(scene, os.path.join(out, f"{NAME}_front.png"), samples)

    cam.location = (1.42, -1.30, 0.98)
    cam.data.lens = 50.0
    _look_at(cam, (0.72, -0.12, 0.47))
    render_still(scene, os.path.join(out, f"{NAME}_detail.png"), samples)


if __name__ == "__main__":
    main()
