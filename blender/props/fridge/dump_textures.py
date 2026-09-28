"""Debug: write the packed atlases to the scratch folder as PNG.

  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/dump_textures.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import NAME, SCRATCH  # noqa: E402


def main():
    for img in bpy.data.images:
        if img.name.startswith(NAME + "_"):
            path = os.path.join(SCRATCH, f"tex_{img.name}.png")
            img.save(filepath=path)
            print("WROTE", path)


if __name__ == "__main__":
    main()
