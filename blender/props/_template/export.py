"""Stage 3: export the glb (render meshes + collision boxes) into assets/.

  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/export.py

A moving part (door, drawer, lid) gets its own glb with its root at the
origin (the hinge axis or the slide start) and a `HandleGrip` empty:
    export_glb_at_origin(bpy.data.objects["Door"], door_objects(), GLB_DOOR)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from template_common import GLB, body_objects, collision_objects  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(body_objects() + collision_objects(), GLB)


if __name__ == "__main__":
    main()
