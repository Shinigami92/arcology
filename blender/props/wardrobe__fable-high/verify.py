"""Stage 5: swing clearance of both doors in the source, then re-import the glb files.

  blender -b --factory-startup --python blender/props/wardrobe__fable-high/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    BLEND, GLB_BODY, GLB_DOOR_LEFT, GLB_DOOR_RIGHT, OPEN_DEG, body_objects, door_meshes,
)
from arcology_blender.checks import hinge_clearance, import_report  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    angles = range(0, int(OPEN_DEG) + 1, 5)
    left, right = door_meshes("left"), door_meshes("right")
    print("LEFT DOOR SWING (negative angle, vs body and the right door)")
    bad_left = hinge_clearance(bpy.data.objects["DoorLeft"], left, body_objects() + right, angles=angles, sign=-1.0)
    print("RIGHT DOOR SWING (positive angle, vs body and the left door)")
    bad_right = hinge_clearance(bpy.data.objects["DoorRight"], right, body_objects() + left, angles=angles, sign=1.0)
    print("CLEARANCE", "OK" if not bad_left and not bad_right else f"FAIL left={bad_left} right={bad_right}")
    import_report(GLB_BODY)
    import_report(GLB_DOOR_LEFT)
    import_report(GLB_DOOR_RIGHT)


if __name__ == "__main__":
    main()
