"""Stage 1: generate the surface texture sets (PNG) and their seam previews.

  blender -b --factory-startup --python blender/surfaces/build.py -- [--only a,b] [--preview DIR]

Writes assets/materials/surfaces/<name>/<name>_{albedo,normal,orm}.png and, into the
preview folder, <name>_tile2x2.png (albedo | grazing-light normal | roughness, the
tile repeated 2 x 2, downsampled) and <name>_seam.png (the same three at full
resolution around the corner where four tiles meet). Prints value ranges and
seam ratios (about 1 = seamless).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

from surfaces_common import PREVIEW, SETS, texture_dir  # noqa: E402
from textures import RECIPES  # noqa: E402
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.surface import (cavity_ao, downsample, height_to_normal_2d, seam_ratio,  # noqa: E402
                                      shade_normal, write_set)
from arcology_blender.trim import linear_to_srgb, write_png  # noqa: E402


def previews(out, name, albedo, normal, rough):
    size = albedo.shape[0]
    rough3 = np.repeat(rough[..., None], 3, axis=2)
    panels = (linear_to_srgb(albedo), shade_normal(normal, albedo=albedo), rough3)
    tiled = [downsample(np.tile(p, (2, 2, 1)), max(1, (2 * size) // 1024)) for p in panels]
    write_png(os.path.join(out, f"{name}_tile2x2.png"), np.concatenate(tiled, axis=1))
    c = 384  # full-resolution crop centered on the tile corner
    crops = [np.tile(p, (2, 2, 1))[size - c:size + c, size - c:size + c] for p in panels]
    write_png(os.path.join(out, f"{name}_seam.png"), np.concatenate(crops, axis=1))


def pct(a, lo=0.5, hi=99.5):
    return f"{np.percentile(a, lo):.3f}..{np.percentile(a, hi):.3f} (mean {a.mean():.3f})"


def main():
    args = script_args()
    only = args[args.index("--only") + 1].split(",") if "--only" in args else list(SETS)
    out = args[args.index("--preview") + 1] if "--preview" in args else PREVIEW
    os.makedirs(out, exist_ok=True)
    for name in only:
        spec = SETS[name]
        t0 = time.time()
        r = RECIPES[name](spec["size"], spec["tile_m"], spec["seed"])
        radius, depth, strength = r["cavity"]
        normal = height_to_normal_2d(r["height"], r["px_m"])
        ao = np.clip(cavity_ao(r["height"], radius, depth, strength) * r["ao"], 0.0, 1.0)
        albedo = np.clip(r["albedo"], 0.0, 1.0)
        write_set(texture_dir(name), name, albedo, normal, ao, r["rough"], r["metal"])
        previews(out, name, albedo, normal, r["rough"])
        lum = albedo @ np.array([0.2126, 0.7152, 0.0722])
        print(f"SET {name}: {spec['size']}^2, tile {spec['tile_m']} m "
              f"({spec['size'] / spec['tile_m']:.0f} px/m), {time.time() - t0:.1f} s")
        if "info" in r:
            print("  ", r["info"])
        print("   albedo linear luminance", pct(lum), "| max channel", f"{albedo.max():.3f}")
        print("   albedo sRGB mean", np.round(linear_to_srgb(albedo.reshape(-1, 3).mean(0)) * 255).astype(int))
        print("   roughness", pct(r["rough"]), "| AO", pct(ao))
        print("   seam ratio u/v: albedo %.2f/%.2f normal %.2f/%.2f rough %.2f/%.2f"
              % (seam_ratio(albedo) + seam_ratio(normal) + seam_ratio(r["rough"])))


if __name__ == "__main__":
    main()
