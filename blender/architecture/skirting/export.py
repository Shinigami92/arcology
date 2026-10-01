"""Stage 3: export the skirting glb into assets/architecture/skirting/ (world positions, glb
origin = world origin, textures embedded, no collision).

  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/export.py [-- --runs F]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skirting_common import glb_path, skirting_objects  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    export_glb(skirting_objects(), glb_path())


if __name__ == "__main__":
    main()
