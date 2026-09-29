"""Stage 3: export the bed glb (frame, linen, throw + collision boxes).

  blender -b --factory-startup blender/props/bed__opus-high.blend --python blender/props/bed__opus-high/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bed_common as C  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(C.bed_objects() + C.collision_objects(), C.GLB)


if __name__ == "__main__":
    main()
