"""Stage 5: door swing and crisper travel clearance in the source, then re-import the glb files.

  blender -b --factory-startup --python blender/props/fridge/verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import (  # noqa: E402
    BLEND, CRISPER_TRAVEL, GLB_BODY, GLB_DOOR, OPEN_DEG, body_objects, door_objects,
)
from arcology_blender.checks import hinge_clearance, import_report, slide_clearance  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    door = bpy.data.objects["Door"]
    drawer = bpy.data.objects["CrisperDrawer"]
    cabinet = [o for o in body_objects() if o is not drawer]
    print("DOOR SWING (door vs body)")
    swing = hinge_clearance(door, door_objects(), body_objects(), angles=range(0, int(OPEN_DEG) + 1, 5))
    print("CRISPER TRAVEL (drawer vs cabinet, door open)")
    door.rotation_euler = (0, 0, math.radians(-OPEN_DEG))
    bpy.context.view_layer.update()
    slide = slide_clearance(drawer, [drawer], cabinet + door_objects(), (0, -1, 0), CRISPER_TRAVEL)
    door.rotation_euler = (0, 0, 0)
    print("CLEARANCE", "OK" if not swing and not slide else f"FAIL swing={swing} slide={slide}")
    import_report(GLB_BODY)
    import_report(GLB_DOOR)


if __name__ == "__main__":
    main()
