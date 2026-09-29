"""Stage 3: export the body glb (with collision) and one glb per door (origin on its hinge axis).

  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    GLB_BODY, GLB_DOOR_LEFT, GLB_DOOR_RIGHT, body_collision_objects, body_objects, door_objects,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def main():
    export_glb(body_objects() + body_collision_objects(), GLB_BODY)
    export_glb_at_origin(bpy.data.objects["DoorLeft"], door_objects("left"), GLB_DOOR_LEFT)
    export_glb_at_origin(bpy.data.objects["DoorRight"], door_objects("right"), GLB_DOOR_RIGHT)


if __name__ == "__main__":
    main()
