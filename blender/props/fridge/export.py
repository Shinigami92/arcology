"""Stage 3: export the body and door glb files (door with its origin on the hinge axis).

  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import GLB_BODY, GLB_DOOR, body_collision_objects, body_objects, door_objects  # noqa: E402
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def main():
    export_glb(body_objects() + body_collision_objects(), GLB_BODY)
    export_glb_at_origin(bpy.data.objects["Door"], door_objects(), GLB_DOOR)


if __name__ == "__main__":
    main()
