"""Stage 3: export the bed glb (render meshes + collision boxes).

  blender -b --factory-startup blender/props/bed__fable-high.blend --python blender/props/bed__fable-high/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bed_common import GLB, bed_objects, collision_objects  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(bed_objects() + collision_objects(), GLB)


if __name__ == "__main__":
    main()
