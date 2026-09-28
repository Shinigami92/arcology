"""Stage 4: studio thumbnails with two pillows on the sofa (3/4 front, fabric close-up). Not saved.

  blender -b --factory-startup blender/props/sofa.blend --python blender/props/sofa/render.py -- [--quick] [--suffix NAME]

Set ARCOLOGY_RENDER_DIR to choose the output folder (thumbnails go to <dir>/sofa/).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sofa_common import NAME, SCRATCH, collision_objects, pillow_objects  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

# (location, rotation in degrees XYZ): one upright in the left corner, one slumped on the right
PILLOW_POSES = [
    ((-0.655, 0.035, 0.635), (74.0, -6.0, -16.0)),
    ((0.64, 0.00, 0.60), (64.0, 24.0, 20.0)),
]
FRONT = dict(camera=(2.25, -2.95, 1.50), target=(0.0, 0.0, 0.44), lens=38.0)
DETAIL = dict(camera=(-0.30, -1.02, 0.92), target=(-0.80, -0.28, 0.48), lens=45.0)


def place_pillows(scene):
    src = pillow_objects()[0]
    src.hide_render = True
    coll = bpy.data.collections.new("RenderPillows")
    scene.collection.children.link(coll)
    for i, (loc, rot) in enumerate(PILLOW_POSES):
        ob = bpy.data.objects.new(f"PillowRender{i}", src.data)
        coll.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = [math.radians(a) for a in rot]


def aim(cam, camera, target, lens):
    cam.location = Vector(camera)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""
    scene = bpy.context.scene
    cam = studio(scene, **FRONT)
    for ob in collision_objects():
        ob.hide_render = True
    place_pillows(scene)
    render_still(scene, os.path.join(SCRATCH, f"{NAME}_front{suffix}.png"), samples)
    aim(cam, **DETAIL)
    render_still(scene, os.path.join(SCRATCH, f"{NAME}_detail{suffix}.png"), samples)


if __name__ == "__main__":
    main()
