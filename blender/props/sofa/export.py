"""Stage 3: export the sofa glb (render meshes + collision boxes) and the pillow glb.

  blender -b --factory-startup blender/props/sofa.blend --python blender/props/sofa/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sofa_common import GLB_PILLOW, GLB_SOFA, collision_objects, pillow_objects, sofa_objects  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(sofa_objects() + collision_objects(), GLB_SOFA)
    export_glb(pillow_objects(), GLB_PILLOW)  # built on the origin: the glb origin is its center


if __name__ == "__main__":
    main()
