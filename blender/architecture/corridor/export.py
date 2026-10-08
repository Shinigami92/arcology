"""Stage 3: export the asset's glb into assets/architecture/corridor/ (textures embedded, no
collision: nothing in the kit is in reach of the body; Godot's wall boxes cover the wainscot).

  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from corridor_common import asset_of_blend, body_objects, glb_path  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def main():
    asset = asset_of_blend(bpy.data.filepath)
    export_glb(body_objects(), glb_path(asset))


if __name__ == "__main__":
    main()
