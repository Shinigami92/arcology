"""Stage 3: export the frame (render meshes + collision boxes), the leaf (origin on the hinge
axis), the lever (origin on the spindle at the leaf face) and the thumb-turn set.

  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from door_interior_common import (  # noqa: E402
    GLB_FRAME, GLB_LEAF, GLB_LEVER, GLB_THUMBTURN, frame_collision_objects, frame_objects, leaf_objects,
    lever_objects, thumbturn_objects,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def main():
    export_glb(frame_objects() + frame_collision_objects(), GLB_FRAME)
    export_glb_at_origin(bpy.data.objects["Leaf"], leaf_objects(), GLB_LEAF)
    export_glb_at_origin(bpy.data.objects["Lever"], lever_objects(), GLB_LEVER)
    export_glb_at_origin(bpy.data.objects["Thumbturn"], thumbturn_objects(), GLB_THUMBTURN)


if __name__ == "__main__":
    main()
