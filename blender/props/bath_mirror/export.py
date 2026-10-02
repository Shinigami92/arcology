"""Stage 3: export the mirror glb (body, glass, light, touch sensor, collision) and the
magnifier's bracket and arm glbs (each with its root at the glb origin).

  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from bath_mirror_common import (  # noqa: E402
    GLB, GLB_ARM, GLB_BRACKET, arm_objects, body_objects, bracket_objects, collision_objects, mirror_fx_objects,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402
from arcology_blender.scene import part_objects  # noqa: E402


def main():
    export_glb(body_objects() + mirror_fx_objects() + collision_objects(), GLB)
    export_glb_at_origin(bpy.data.objects["MagnifierBracket"], bracket_objects() + part_objects("mag_bracket_col"),
                         GLB_BRACKET)
    export_glb_at_origin(bpy.data.objects["MagnifierArm"], arm_objects(), GLB_ARM)


if __name__ == "__main__":
    main()
