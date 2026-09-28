"""Stage 3: export the sofa (with collision boxes) and the pillow glb files.

  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sofa_common import GLB_PILLOW, GLB_SOFA, pillow_objects, sofa_collision_objects, sofa_objects  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(sofa_objects() + sofa_collision_objects(), GLB_SOFA)
    export_glb(pillow_objects(), GLB_PILLOW)  # built centered on the origin


if __name__ == "__main__":
    main()
