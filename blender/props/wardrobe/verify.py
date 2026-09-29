"""Stage 5: swing clearance of both doors, drawer travel with the doors open, then re-import every glb.

  blender -b --factory-startup --python blender/props/wardrobe/verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    BLEND, DRAWER_CHECK_DEG, DRAWER_TRAVEL, GLB_BODY, GLB_BOX, GLB_BOX_LID, GLB_DOOR_LEFT,
    GLB_DOOR_RIGHT, GLB_DRAWER, GLB_HANGER, GLB_HANGER_SHIRT_A, GLB_HANGER_SHIRT_B, OPEN_DEG,
    all_prop_meshes, body_objects, door_meshes, prop_meshes, prop_root,
)
from arcology_blender.checks import hinge_clearance, import_report, slide_clearance  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    angles = range(0, int(OPEN_DEG) + 1, 5)
    left, right = door_meshes("left"), door_meshes("right")
    left_root, right_root = bpy.data.objects["DoorLeft"], bpy.data.objects["DoorRight"]
    props = all_prop_meshes()
    fixed = body_objects() + props
    print("LEFT DOOR SWING (negative angle, vs body, props and the right door)")
    bad_left = hinge_clearance(left_root, left, fixed + right, angles=angles, sign=-1.0)
    print("RIGHT DOOR SWING (positive angle, vs body, props and the left door)")
    bad_right = hinge_clearance(right_root, right, fixed + left, angles=angles, sign=1.0)

    left_root.rotation_euler = (0, 0, math.radians(-DRAWER_CHECK_DEG))
    right_root.rotation_euler = (0, 0, math.radians(DRAWER_CHECK_DEG))
    bpy.context.view_layer.update()
    bad_slide = {}
    for part in ("drawer_lower", "drawer_upper"):
        moving = prop_meshes(part)
        others = [o for o in fixed if o not in moving]
        print(f"{part.upper()} TRAVEL (doors at {DRAWER_CHECK_DEG:.0f} deg, vs body, doors and the other props)")
        bad_slide[part] = slide_clearance(prop_root(part), moving, others + left + right, (0, -1, 0),
                                          DRAWER_TRAVEL, steps=16)
    left_root.rotation_euler = right_root.rotation_euler = (0, 0, 0)
    ok = not bad_left and not bad_right and not any(bad_slide.values())
    print("CLEARANCE", "OK" if ok else f"FAIL left={bad_left} right={bad_right} slide={bad_slide}")
    for path in (GLB_BODY, GLB_DOOR_LEFT, GLB_DOOR_RIGHT, GLB_DRAWER, GLB_BOX, GLB_BOX_LID, GLB_HANGER,
                 GLB_HANGER_SHIRT_A, GLB_HANGER_SHIRT_B):
        import_report(path)


if __name__ == "__main__":
    main()
