"""Stage 3: export body (with collision), drawer (origin at the front's bottom center) and lamp glb files.

  blender -b --factory-startup blender/props/nightstand__fable-high.blend --python blender/props/nightstand__fable-high/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import (  # noqa: E402
    GLB_BODY, GLB_DRAWER, GLB_LAMP, body_collision_objects, body_objects, drawer_objects, lamp_objects,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def main():
    export_glb(body_objects() + body_collision_objects(), GLB_BODY)
    export_glb_at_origin(bpy.data.objects["Drawer"], drawer_objects(), GLB_DRAWER)
    export_glb_at_origin(bpy.data.objects["TableLamp"], lamp_objects(), GLB_LAMP)


if __name__ == "__main__":
    main()
