"""Stage 3: check the written texture sets against the contract.

  blender -b --factory-startup --python blender/surfaces/verify.py

Per set: the three PNGs exist, are square at the contract size, the albedo stays
in realistic linear ranges (plaster <= ~0.71), roughness and metallic are in the
set's range, the normal map points out of the surface, and every map tiles
(seam ratio <= 1.2, see surface.seam_ratio). Exits with 1 on a failure.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from surfaces_common import SETS, texture_paths  # noqa: E402
from arcology_blender.surface import seam_ratio  # noqa: E402

# name: (albedo linear max, roughness p1..p99 window, seam ratio limit)
LIMITS = {
    "vinyl_plank": (0.45, (0.36, 0.66), 1.2),
    "carpet": (0.40, (0.88, 1.0), 1.2),
    "polished_concrete": (0.35, (0.17, 0.46), 1.2),
    "wall_plaster": (0.715, (0.72, 0.88), 1.2),
    "ceiling_plaster": (0.715, (0.84, 0.95), 1.2),
}


def load(path, colorspace):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = colorspace
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)  # the stored values (sRGB for the albedo)
    px = a.reshape(h, w, 4)[..., :3].astype(np.float64)
    if colorspace == "sRGB":
        px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
    return (w, h), px


def main():
    failures = []
    for name, spec in SETS.items():
        paths = texture_paths(name)
        missing = [p for p in paths.values() if not os.path.exists(p)]
        if missing:
            failures.append(f"{name}: missing {missing}")
            continue
        amax, (rlo, rhi), seam_max = LIMITS[name]
        maps = {k: load(p, "sRGB" if k == "albedo" else "Non-Color") for k, p in paths.items()}
        for k, (size, _) in maps.items():
            if size != (spec["size"], spec["size"]):
                failures.append(f"{name}_{k}: size {size}, expected {spec['size']}^2")
        albedo, normal, orm = (maps[k][1] for k in ("albedo", "normal", "orm"))
        rough, metal = orm[..., 1], orm[..., 2]
        r1, r99 = np.percentile(rough, 1), np.percentile(rough, 99)
        nz = normal[..., 2] * 2 - 1
        seams = {k: seam_ratio(v) for k, v in (("albedo", albedo), ("normal", normal), ("orm", orm))}
        worst = max(max(s) for s in seams.values())
        print(f"{name}: {spec['size']}^2, tile {spec['tile_m']} m, albedo max {albedo.max():.3f}, "
              f"rough p1..p99 {r1:.3f}..{r99:.3f}, metal max {metal.max():.3f}, normal z min {nz.min():.3f}, "
              f"seam ratio max {worst:.2f}")
        if albedo.max() > amax:
            failures.append(f"{name}: albedo max {albedo.max():.3f} > {amax}")
        if r1 < rlo or r99 > rhi:
            failures.append(f"{name}: roughness {r1:.3f}..{r99:.3f} outside {rlo}..{rhi}")
        if metal.max() > 0.01:
            failures.append(f"{name}: metallic {metal.max():.3f}")
        if nz.min() < 0.5:
            failures.append(f"{name}: normal tilts past 60 degrees (z {nz.min():.3f})")
        if worst > seam_max:
            failures.append(f"{name}: seam ratio {worst:.2f} > {seam_max} ({seams})")
    for f in failures:
        print("FAIL", f)
    print("VERIFY", "FAIL" if failures else "OK")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
