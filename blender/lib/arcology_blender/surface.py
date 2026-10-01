"""Seamless surface textures (numpy): square tiles that repeat in both directions,
for floors, walls and ceilings mapped by world-space (triplanar) projection.

Every function here is periodic in U and V: FFT filters, wrapped neighbors and
cell lookups all wrap around the tile, so a texture made only from these (and
from `trim.noise` / `trim.fbm` / `trim.warp`, which are 2D-periodic too) tiles
without seams. Only `trim.height_to_normal` isn't periodic along V (it was made
for trim bands); use `height_to_normal_2d` here.

Arrays are (rows, columns) = (V, U) with row 0 at the bottom of the image, as
in Blender's pixel buffer and `trim.write_png`; colors are linear until
`write_set` converts the albedo to sRGB. Heights are in meters.
"""

import math
import os

import numpy as np

from .trim import linear_to_srgb, write_png


# --- filters and fields ---------------------------------------------------------------
def _freqs(h, w):
    return np.fft.fftfreq(h)[:, None], np.fft.rfftfreq(w)[None, :]


def oriented_noise(h, w, size_along, size_across, angle_deg=0.0, seed=0):
    """Like `trim.noise` (periodic, zero mean, unit deviation) but its streaks run
    at `angle_deg` from U (counter-clockwise, toward +V): scuffs, trowel strokes
    and brush marks that aren't axis-aligned. Sizes in pixels."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfft2(rng.standard_normal((h, w)))
    fy, fx = _freqs(h, w)
    a = math.radians(angle_deg)
    fu = fx * math.cos(a) + fy * math.sin(a)
    fv = -fx * math.sin(a) + fy * math.cos(a)
    f *= np.exp(-2.0 * math.pi ** 2 * ((fu * size_along) ** 2 + (fv * size_across) ** 2))
    out = np.fft.irfft2(f, s=(h, w))
    out -= out.mean()
    return out / (out.std() + 1e-12)


def blur(field, sigma_px):
    """Periodic Gaussian blur (sigma in pixels) of an (h, w) or (h, w, c) array."""
    if sigma_px <= 0:
        return np.array(field, dtype=np.float64)
    if field.ndim == 3:
        return np.dstack([blur(field[..., k], sigma_px) for k in range(field.shape[2])])
    h, w = field.shape
    fy, fx = _freqs(h, w)
    f = np.fft.rfft2(field) * np.exp(-2.0 * math.pi ** 2 * sigma_px ** 2 * (fx ** 2 + fy ** 2))
    return np.fft.irfft2(f, s=(h, w))


def height_to_normal_2d(height, px_m, strength=1.0):
    """Tangent-space normal map (OpenGL / glTF / Godot convention, +V = green up)
    from a height field in meters sampled every `px_m` meters, periodic in both
    directions (central differences that wrap). Returns (h, w, 3) in 0..1."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5 / px_m
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5 / px_m
    n = np.dstack([-dx * strength, -dy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def cavity_ao(height, radius_px, depth_m, strength=1.0):
    """Ambient occlusion from a height field: how far each texel lies below its
    blurred neighborhood (radius in pixels), `depth_m` below it = fully occluded.
    Returns 1 (open) .. 1 - strength (deep in a groove), periodic."""
    occ = np.clip((blur(height, radius_px) - height) / depth_m, 0.0, 1.0)
    return 1.0 - strength * occ


def contour_lines(field, width_px):
    """Antialiased lines along the zero contour of a smooth field, `width_px`
    wide (distance estimated as |f| / |grad f|): cracks, veins, scratches.
    Returns 0..1 (1 on the line). Mask the result to keep only some segments."""
    gx = (np.roll(field, -1, axis=1) - np.roll(field, 1, axis=1)) * 0.5
    gy = (np.roll(field, -1, axis=0) - np.roll(field, 1, axis=0)) * 0.5
    d = np.abs(field) / (np.hypot(gx, gy) + 1e-9)
    t = np.clip(d / max(width_px, 1e-6), 0.0, 1.0)
    return 1.0 - t * t * (3 - 2 * t)


def cells(h, w, cell_px, seed=0, jitter=1.0):
    """Periodic Worley (cellular) noise: one random point per cell of about
    `cell_px` pixels (cell counts are rounded so the grid tiles). Returns
    (f1, f2, cell, value): distance in pixels to the nearest and second-nearest
    point, the nearest point's cell index (0 .. cells-1) and its random value
    in 0..1. Spots (aggregate, tufts, pores): threshold f1 with per-cell radii,
    looked up by `cell` in an array of length ncells (= cell.max() + 1 at most
    round(h / cell_px) * round(w / cell_px))."""
    nx, ny = max(1, round(w / cell_px)), max(1, round(h / cell_px))
    cw, ch = w / nx, h / ny
    rng = np.random.default_rng(seed)
    ox, oy, val = rng.random((ny, nx)), rng.random((ny, nx)), rng.random((ny, nx))
    rr, cc = np.mgrid[0:h, 0:w].astype(np.float64)
    rr += 0.5
    cc += 0.5
    gx, gy = np.floor(cc / cw).astype(np.int64), np.floor(rr / ch).astype(np.int64)
    f1 = np.full((h, w), np.inf)
    f2 = np.full((h, w), np.inf)
    idx = np.zeros((h, w), dtype=np.int64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            jx, jy = gx + dx, gy + dy
            mx, my = jx % nx, jy % ny
            px = (jx + 0.5 + jitter * (ox[my, mx] - 0.5)) * cw
            py = (jy + 0.5 + jitter * (oy[my, mx] - 0.5)) * ch
            d = np.hypot(cc - px, rr - py)
            nearer = d < f1
            f2 = np.where(nearer, f1, np.minimum(f2, d))
            idx = np.where(nearer, my * nx + mx, idx)
            f1 = np.where(nearer, d, f1)
    return f1, f2, idx, val.ravel()[idx]


# --- layouts --------------------------------------------------------------------------------
def running_bond(size, tile_m, course_m, piece_m, seed=0, min_shift_m=0.2, start_offsets=None, course_phase=0.0):
    """Staggered layout of equal pieces in courses along U (planks, bricks, tiles
    with random end joints), periodic in both directions over a square tile of
    `tile_m` meters and `size` pixels.

    Course width and piece length are rounded so whole numbers fit the tile
    (returned as `course_m` / `piece_m`). Each course gets a random offset; the
    end joints of neighboring courses (including the last and first) are at
    least `min_shift_m` apart, so no H-joints. `course_phase` (fraction of a
    course) shifts the courses across V, e.g. 0.5 keeps a long edge off the
    texture border (cleaner seam checks). Returns a dict of (size, size)
    arrays sampled at pixel centers: `id` (unique piece index, 0 .. pieces-1),
    `course`, `along` / `across` (meters from the piece's start / course's
    bottom edge), `d_side` / `d_end` (meters to the nearest long / end edge),
    plus the scalars `courses`, `per_course`, `pieces`, `course_m`, `piece_m`,
    `px_m` and the `offsets` used."""
    courses = max(1, round(tile_m / course_m))
    per = max(1, round(tile_m / piece_m))
    cw, pl = tile_m / courses, tile_m / per
    rng = np.random.default_rng(seed)
    if start_offsets is None:
        min_shift = min(min_shift_m, pl / 3.0)

        def ok(a, b):
            d = abs(a - b) % pl
            return min(d, pl - d) >= min_shift

        offs = []
        for i in range(courses):
            for _ in range(200):
                o = rng.random() * pl
                if (not offs or ok(o, offs[-1])) and (i < courses - 1 or ok(o, offs[0])):
                    break
            offs.append(o)
        offsets = np.asarray(offs)
    else:
        offsets = np.asarray(start_offsets, dtype=np.float64)
    px_m = tile_m / size
    coord = (np.arange(size) + 0.5) * px_m
    y = np.mod(coord[:, None] + course_phase * cw, tile_m) * np.ones((1, size))
    x = np.ones((size, 1)) * coord[None, :]
    course = np.minimum(np.floor(y / cw).astype(np.int64), courses - 1)
    across = y - course * cw
    xs = np.mod(x - offsets[course], tile_m)
    k = np.minimum(np.floor(xs / pl).astype(np.int64), per - 1)
    along = xs - k * pl
    return dict(id=course * per + k, course=course, along=along, across=across,
                d_side=np.minimum(across, cw - across), d_end=np.minimum(along, pl - along),
                courses=courses, per_course=per, pieces=courses * per, course_m=cw, piece_m=pl,
                px_m=px_m, offsets=offsets)


# --- output and checks ---------------------------------------------------------------------
def write_set(folder, name, albedo, normal, ao, rough, metal=0.0):
    """Write `<name>_albedo.png` (sRGB, from linear `albedo`), `<name>_normal.png`
    (0..1 OpenGL normal) and `<name>_orm.png` (R = AO, G = roughness, B = metallic,
    linear) into `folder` as 8-bit PNGs. Returns the three paths."""
    h, w = albedo.shape[:2]
    orm = np.dstack([np.broadcast_to(np.clip(c, 0.0, 1.0), (h, w)) for c in (ao, rough, metal)])
    paths = [os.path.join(folder, f"{name}_{s}.png") for s in ("albedo", "normal", "orm")]
    write_png(paths[0], linear_to_srgb(albedo))
    write_png(paths[1], normal)
    write_png(paths[2], orm)
    return paths


def seam_ratio(img, percentile=99.0):
    """Seamlessness check for U and V: the mean step across the wrap seam (last
    column to first, last row to first) divided by the `percentile` of the same
    mean over every interior column (row) pair. A seamless tile scores <= ~1
    (the border looks like any other pair, plank joints included); a seam
    scores well above 1."""
    a = np.asarray(img, dtype=np.float64)
    if a.ndim == 2:
        a = a[..., None]

    def ratio(axis):
        other = tuple(k for k in range(a.ndim) if k != axis)
        steps = np.abs(np.diff(np.concatenate([a, np.take(a, [0], axis)], axis=axis), axis=axis))
        means = steps.mean(axis=other)
        return float(means[-1] / (np.percentile(means[:-1], percentile) + 1e-12))

    return ratio(1), ratio(0)


def downsample(img, factor):
    """Box-filter an (h, w[, c]) array by an integer factor (previews)."""
    if factor <= 1:
        return img
    h, w = img.shape[:2]
    a = img[: h - h % factor, : w - w % factor]
    shape = (a.shape[0] // factor, factor, a.shape[1] // factor, factor) + a.shape[2:]
    return a.reshape(shape).mean(axis=(1, 3))


def shade_normal(normal, light=(-0.55, 0.45, 0.70), albedo=None):
    """Grazing-light Lambert view of a 0..1 normal map (and optional linear
    albedo), as display values 0..1: makes bevels, cracks and seams visible."""
    n = normal * 2.0 - 1.0
    l_dir = np.asarray(light, dtype=np.float64)
    l_dir /= np.linalg.norm(l_dir)
    lam = np.clip((n * l_dir).sum(axis=2), 0.0, 1.0)
    base = albedo if albedo is not None else np.full(normal.shape, 0.5)
    return linear_to_srgb(base * (0.15 + 1.1 * lam)[..., None])
