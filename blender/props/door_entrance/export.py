"""Stage 3: export the frame (render mesh + collision boxes), the leaf (origin on the hinge
axis, LED and HandleGrip empties included), both levers and the thumb-turn (origin on their
axis) into assets/props/door_entrance/.

  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from door_entrance_common import (  # noqa: E402
    GLB_FRAME, GLB_LEAF, GLB_LEVER_APT, GLB_LEVER_COR, GLB_THUMBTURN, frame_collision_objects, frame_objects,
    leaf_objects, lever_apartment, lever_corridor, thumbturn,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def main():
    export_glb(frame_objects() + frame_collision_objects(), GLB_FRAME)
    export_glb_at_origin(bpy.data.objects["Leaf"], leaf_objects(), GLB_LEAF)
    for objs, path in ((lever_apartment(), GLB_LEVER_APT), (lever_corridor(), GLB_LEVER_COR),
                       (thumbturn(), GLB_THUMBTURN)):
        export_glb_at_origin(objs[0], objs, path)


if __name__ == "__main__":
    main()
