"""Stage 3: export the body glb (with collision), one glb per door, and the pickable and
sliding props, each with its root at the origin.

  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    GLB_BODY, GLB_BOX, GLB_BOX_LID, GLB_DOOR_LEFT, GLB_DOOR_RIGHT, GLB_DRAWER, GLB_HANGER,
    GLB_HANGER_SHIRT_A, GLB_HANGER_SHIRT_B, body_collision_objects, body_objects, door_objects,
    prop_root,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402
from arcology_blender.scene import part_objects  # noqa: E402


def export_part(part, path):
    export_glb_at_origin(prop_root(part), part_objects(part), path)


def main():
    export_glb(body_objects() + body_collision_objects(), GLB_BODY)
    export_glb_at_origin(bpy.data.objects["DoorLeft"], door_objects("left"), GLB_DOOR_LEFT)
    export_glb_at_origin(bpy.data.objects["DoorRight"], door_objects("right"), GLB_DOOR_RIGHT)
    export_part("drawer_lower", GLB_DRAWER)      # both drawers are identical: instance it twice
    export_part("box", GLB_BOX)
    export_part("lid", GLB_BOX_LID)
    export_part("hanger3", GLB_HANGER)           # bare wire hanger (hanger4 is a linked copy)
    export_part("hanger1", GLB_HANGER_SHIRT_A)   # linen shirt
    export_part("hanger2", GLB_HANGER_SHIRT_B)   # charcoal shirt


if __name__ == "__main__":
    main()
