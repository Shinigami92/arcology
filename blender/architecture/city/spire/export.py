"""Stage 3: one glb per tower into assets/architecture/city/<tower>/, plus the shared kit PNGs.

  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/export.py

Each glb holds the body mesh (<tower>: city_spire_glass / _metal / _lights), the ad
panels (<tower>_ad<n>: city_spire_ads) and the warning lights (<tower>_blink:
city_spire_lights); origin at the base center on the street, unrotated. The kit
PNGs in assets/architecture/city/_kit/spire/ are the same pixels every glb embeds,
for one shared Godot material per name.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from spire_common import MATERIALS, glb_path, kit_png, tower_objects, towers  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402
from arcology_blender.trim import image_pixels, write_png  # noqa: E402


def main():
    for t in towers():
        export_glb(tower_objects(t["name"]), glb_path(t["name"]))
    for m in MATERIALS:
        for kind in ("albedo", "normal", "orm", "emission"):
            img = bpy.data.images.get(f"{m}_{kind}")
            if img is not None:
                write_png(kit_png(m, kind), image_pixels(img))


if __name__ == "__main__":
    main()
