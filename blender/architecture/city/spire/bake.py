"""Stage 2: generate the shared texture sets (numpy + the ad atlas render), pack them
and wire the four city_spire_* materials. No Cycles bake: every tower maps the same
tiling sets at real-world scale, so towers added later reuse exactly these pixels.

  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/bake.py

Sets (all 8-bit PNG, albedo and emission sRGB):
  city_spire_glass   2048^2 albedo, normal, orm, emission   (64 x 64 m tile, 32 px/m)
  city_spire_metal   2048^2 albedo, normal, orm             (64 x 64 m tile, 32 px/m)
  city_spire_lights  1024^2 albedo, orm, emission           (trim bands, 16 px/m along)
  city_spire_ads     2048^2 albedo, emission                (ad atlas)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from spire_common import (  # noqa: E402
    BAY, EMISSION, FLOOR, GLASS_SIZE, GLASS_TILE, LIGHT_PAD, LIGHT_ROWS, LIGHTS_PX_M, LIGHTS_SIZE, LOUVER_V,
    MAT_ADS, MAT_GLASS, MAT_LIGHTS, MAT_METAL, METAL_SIZE, METAL_TILE,
)
import spire_ads  # noqa: E402
import spire_textures as tex  # noqa: E402
from lib_candidates import textured_material  # noqa: E402
from arcology_blender.bake import report_images  # noqa: E402
from arcology_blender.trim import image_from_array, linear_to_srgb  # noqa: E402


def orm(s):
    h, w = s["rough"].shape
    return np.dstack([np.broadcast_to(np.clip(s[k], 0, 1), (h, w)) for k in ("ao", "rough", "metal")])


def images(prefix, s, normal=True, emission=True):
    out = {"albedo": image_from_array(f"{prefix}_albedo", linear_to_srgb(s["albedo"]), "sRGB"),
           "orm": image_from_array(f"{prefix}_orm", orm(s), "Non-Color")}
    if normal:
        out["normal"] = image_from_array(f"{prefix}_normal", s["normal"], "Non-Color")
    if emission:
        out["emission"] = image_from_array(f"{prefix}_emission", linear_to_srgb(s["emission"]), "sRGB")
    return out


def main():
    t0 = time.time()
    glass = tex.glass_set(GLASS_SIZE, GLASS_TILE, FLOOR, BAY)
    print("GLASS", {k: round(v, 3) for k, v in glass["stats"].items()})
    im = images(MAT_GLASS, glass)
    textured_material(MAT_GLASS, im["albedo"], im["orm"], im["normal"], im["emission"], EMISSION[MAT_GLASS])

    metal = tex.metal_set(METAL_SIZE, METAL_TILE, FLOOR, BAY, LOUVER_V)
    im = images(MAT_METAL, metal, emission=False)
    textured_material(MAT_METAL, im["albedo"], im["orm"], im["normal"])

    lights = tex.lights_set(LIGHTS_SIZE, LIGHTS_PX_M, LIGHT_ROWS, LIGHT_PAD)
    im = images(MAT_LIGHTS, lights, normal=False)
    textured_material(MAT_LIGHTS, im["albedo"], im["orm"], None, im["emission"], EMISSION[MAT_LIGHTS])

    em = spire_ads.render_atlas()
    ads = dict(albedo=em * 0.22 + 0.008, emission=em)
    a_alb = image_from_array(f"{MAT_ADS}_albedo", linear_to_srgb(ads["albedo"]), "sRGB")
    a_em = image_from_array(f"{MAT_ADS}_emission", linear_to_srgb(ads["emission"]), "sRGB")
    textured_material(MAT_ADS, a_alb, None, None, a_em, EMISSION[MAT_ADS], rough=0.28, metal=0.0)

    report_images()
    print(f"BAKE done in {time.time() - t0:.1f}s")
    bpy.ops.wm.save_mainfile(compress=False)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
