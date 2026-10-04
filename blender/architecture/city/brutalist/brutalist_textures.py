"""Texture sets of the brutalist towers (numpy, deterministic; no Cycles bake).

Four shared materials, each one texture set:

city_brutal_concrete  2048^2 trim sheet, 64 px/m, U repeats every 32 m. Bands
    (V across, meters): wall_a / wall_b / wall_c (one floor of precast or cast
    concrete: panel joints every 4 m, grime streaks hanging from the floor line
    above, rust runs on wall_c), parapet (balcony and spandrel fronts, 1.4 m:
    coping on top, drip edge below), soffit (undersides, inner faces), top
    (ledges, balcony floors, deck tops), roof (2 m precast roof slabs, ponding
    stains, bitumen patches), foliage (planted balconies, hedges).
city_brutal_windows   2048^2 tile of 32 x 32 window cells (BAY x FH = 3.0 x
    3.2 m each, 64 px): jambs, slab edge, lintel, frames, glass; apartments of
    1-3 bays lit together. Emission map: ~40 % lit, mostly warm (#FFB36B..#FFC58F),
    ~25 % of the lit ones cold (LED white, TV blue); curtains, blinds and
    furniture silhouettes inside, all soft (>= 0.5 m features).
city_brutal_metal     2048^2 trim sheet, 64 px/m: panel (painted cladding),
    louver (HVAC sides), grating (decks), rail (railing infill), rust, dark
    (sign housings, masts) and a decal row: landing pad markings (24 m square),
    fan grille, hazard stripes.
city_brutal_neon      1024^2 atlas: roof sign, six blade signs, small signs, a
    billboard, light swatches (pad, warning and strip lights). Emission map
    with soft halos; albedo dark backing with glass tubes.

Arrays are (rows, cols) with row 0 at the bottom (Blender's pixel order);
colors are linear until the images are made.
"""

import math

import numpy as np

from arcology_blender.trim import TrimSheet, fbm, height_to_normal, linear_to_srgb, noise, smoothstep
from arcology_blender.surface import blur, cells, height_to_normal_2d
from lib_candidates import neon_tubes, pseudo_glyph, text_strokes

from brutalist_common import BAY, CELLS, FH, PX_PER_M, TEX, MAT_CONCRETE, MAT_METAL, MAT_NEON, MAT_WINDOWS

PAD = 10

# --- colors (linear) ---------------------------------------------------------------------
CONC = np.array((0.100, 0.104, 0.110))          # style guide concrete #5A5F66, a touch warmer when weathered
CONC_DARK = np.array((0.058, 0.060, 0.063))
GRIME = np.array((0.020, 0.019, 0.017))
RUST = np.array((0.150, 0.052, 0.016))          # rust #7A3E1D, diluted
DUST = np.array((0.150, 0.140, 0.122))
MOSS = np.array((0.022, 0.032, 0.012))
GUNMETAL = np.array((0.027, 0.032, 0.040))      # #2E3238
STEEL = np.array((0.250, 0.270, 0.300))         # brushed steel #8A9099
GLASS = np.array((0.010, 0.012, 0.017))
PAINT_AMBER = np.array((0.55, 0.30, 0.02))
PAINT_WHITE = np.array((0.55, 0.55, 0.52))

WARM_A = np.array((1.0, 0.459, 0.149))          # #FFB36B
WARM_B = np.array((1.0, 0.567, 0.280))          # #FFC58F
COLD = {
    "led": np.array((0.72, 0.81, 1.0)),          # cool white LED
    "tv": np.array((0.25, 0.42, 1.0)),           # TV glow
    "fluo": np.array((0.58, 0.87, 1.0)),         # cyan-white fluorescent
}
NEON = {
    "magenta": np.array((1.0, 0.023, 0.153)),   # #FF2A6D
    "cyan": np.array((0.0015, 0.693, 0.807)),   # #05D9E8
    "amber": np.array((1.0, 0.434, 0.0)),       # #FFB000
    "uv": np.array((0.198, 0.028, 1.0)),        # #7B2FFF
    "green": np.array((0.040, 1.0, 0.007)),     # #39FF14
    "red": np.array((1.0, 0.030, 0.012)),       # aircraft warning red
    "coolwhite": np.array((0.70, 0.85, 1.0)),
    "warmwhite": np.array((1.0, 0.62, 0.33)),
}
SWATCHES = ("amber", "red", "cyan", "magenta", "uv", "coolwhite", "warmwhite", "green")


def sstep(a, b, x):
    """GLSL-order smoothstep(edge0, edge1, x); edges may be descending."""
    return smoothstep(x, a, b) if a < b else 1.0 - smoothstep(x, b, a)


def _c(c):
    return np.asarray(c, dtype=np.float64)[None, None, :]


def _mix(a, b, t):
    t = np.asarray(t)[..., None]
    return a * (1 - t) + b * t


def _col(w, size_px, seed):
    """1D periodic noise along U (unit deviation)."""
    return noise(4, w, size_px, 1.0, seed)[0]


def _rows(m):
    return int(math.ceil(m * PX_PER_M - 1e-6))


# =========================================================================================
# Concrete trim sheet
# =========================================================================================
CONCRETE_BANDS = (("wall_a", FH), ("wall_b", FH), ("wall_c", FH), ("parapet", 1.4), ("soffit", FH),
                  ("top", 4.0), ("roof", 6.0), ("foliage", 2.0))
PANEL_M = 4.0        # precast panel width on walls and parapets
ROOF_SLAB_M = 2.0    # roof slabs (32 m and 6 m are whole multiples)


def concrete_sheet():
    size = TEX[MAT_CONCRETE]
    sheet = TrimSheet(size, size, PX_PER_M, pad=PAD)
    for name, m in CONCRETE_BANDS:
        sheet.add_band(name, _rows(m))
    return sheet


def _panel_grid(w, period_px, seed, tone_sd):
    cols = np.arange(w)
    idx = cols // period_px
    rng = np.random.default_rng(seed)
    tone = 1.0 + rng.normal(0.0, tone_sd, int(idx.max()) + 1)
    d = np.minimum(cols % period_px, period_px - cols % period_px).astype(np.float64)
    return tone[idx][None, :], d[None, :]


def _streaks(h, w, d_m, seed, amount, length=(0.5, 2.6), width_px=9.0):
    """Grime streaks hanging below a ledge: d_m = meters below it (h, 1)."""
    a = 0.75 * _col(w, width_px, seed) + 0.45 * _col(w, width_px * 0.4, seed + 1)
    a = smoothstep(a, 0.0, 1.8)
    lmix = 0.5 + 0.5 * np.tanh(_col(w, 40.0, seed + 2))
    ln = length[0] + (length[1] - length[0]) * lmix
    d = np.clip(d_m, 0.0, None)
    fall = np.exp(-d / ln[None, :]) * (d >= -0.01)
    wob = 0.8 + 0.2 * noise(h, w, 2.0, 30.0, seed + 3)
    base_film = 0.25 * np.exp(-d / 0.35)      # even film right under the ledge
    return np.clip((a[None, :] * fall * wob + base_film) * amount, 0.0, 1.0)


def _rust_runs(h, w, d_m, seed, count, length=(0.8, 2.4)):
    rng = np.random.default_rng(seed)
    cols = np.arange(w)[None, :].astype(np.float64)
    out = np.zeros((h, w))
    for _ in range(count):
        x = rng.uniform(0, w)
        wd = rng.uniform(4.0, 9.0)
        d0 = rng.uniform(0.0, 0.6)
        ln = rng.uniform(*length)
        dx = np.minimum(np.abs(cols - x), w - np.abs(cols - x))
        across = np.exp(-(dx / wd) ** 2)
        dd = d_m - d0
        along = np.where(dd >= 0, np.exp(-dd / ln), np.exp(dd / 0.05))
        out = np.maximum(out, across * along * rng.uniform(0.5, 1.0))
    return out


def _concrete_wall(variant):
    """Fill fn for one floor of wall concrete. variant: a (precast), b (cast
    in place, darker), c (old: heavy grime, rust runs, damp bottom)."""
    tone_k, grime_k, panel_sd, rust_n = {"a": (1.0, 0.65, 0.05, 1), "b": (0.82, 0.8, 0.035, 2),
                                         "c": (0.72, 1.0, 0.06, 5)}[variant]

    def fn(h, w, px, v, seed):
        top = FH
        tone, dcol = _panel_grid(w, int(PANEL_M * PX_PER_M), seed, panel_sd)
        big = fbm(h, w, 150.0, 110.0, 4, 0.55, seed + 1)
        mid = noise(h, w, 16.0, 16.0, seed + 2)
        fine = noise(h, w, 1.2, 1.2, seed + 3)
        base = _c(CONC * tone_k) * (tone * (1 + 0.09 * big + 0.035 * mid + 0.02 * fine))[..., None]
        if variant == "b":  # pour lifts every 1.6 m, soft tone steps
            base = base * (1 + 0.04 * np.sin(v / 1.6 * 2 * math.pi))[..., None]
        d = top - v
        s = _streaks(h, w, d, seed + 4, grime_k)
        base = _mix(base, _c(GRIME), 0.72 * s)
        r = _rust_runs(h, w, d, seed + 5, rust_n)
        base = _mix(base, _c(RUST), 0.55 * r)
        if variant == "c":
            damp = smoothstep(-v + 0.8, 0.0, 0.8) * (0.5 + 0.5 * smoothstep(fbm(h, w, 60, 30, 3, 0.5, seed + 6),
                                                                            -0.5, 1.0))
            base = _mix(base, _c(MOSS), 0.6 * damp)
        # joints: vertical every PANEL_M, horizontal at the floor lines
        vpx = v * PX_PER_M
        dj = np.minimum(dcol, np.minimum(np.abs(vpx), np.abs(vpx - top * PX_PER_M)))
        joint = sstep(2.6, 0.6, dj)
        base = base * (1 - 0.35 * joint)[..., None]
        rough = 0.9 - 0.08 * s + 0.03 * mid
        height = -0.012 * joint + 0.0006 * fine + 0.0015 * big + 0.002 * (tone - 1) * 10
        ao = (1 - 0.45 * joint) * (1 - 0.2 * np.exp(-np.clip(d, 0, None) / 0.12))
        return dict(albedo=base, rough=rough, metal=0.0, height=height, ao=ao, normal_strength=1.0)

    return fn


def _parapet(h, w, px, v, seed):
    top = 1.4
    tone, dcol = _panel_grid(w, int(PANEL_M * PX_PER_M), seed, 0.05)
    big = fbm(h, w, 120.0, 60.0, 4, 0.55, seed + 1)
    fine = noise(h, w, 1.2, 1.2, seed + 3)
    base = _c(CONC * 0.95) * (tone * (1 + 0.08 * big + 0.02 * fine))[..., None]
    d = top - v
    s = _streaks(h, w, d - 0.06, seed + 4, 0.85, length=(0.3, 1.3), width_px=7.0)
    base = _mix(base, _c(GRIME), 0.75 * s)
    coping = sstep(top - 0.07, top - 0.03, v)
    base = base * (1 + 0.18 * coping)[..., None]
    drip = sstep(0.07, 0.0, v)
    base = base * (1 - 0.45 * drip)[..., None]
    r = _rust_runs(h, w, d, seed + 5, 2, length=(0.4, 1.0))
    base = _mix(base, _c(RUST), 0.5 * r)
    joint = sstep(2.6, 0.6, dcol) * np.ones_like(v)
    base = base * (1 - 0.3 * joint)[..., None]
    height = -0.01 * joint + 0.0006 * fine + 0.004 * coping
    return dict(albedo=base, rough=0.88 - 0.08 * s, metal=0.0, height=height,
                ao=(1 - 0.4 * joint) * (1 - 0.25 * drip))


def _soffit(h, w, px, v, seed):
    big = fbm(h, w, 90.0, 90.0, 4, 0.6, seed + 1)
    fine = noise(h, w, 1.2, 1.2, seed + 3)
    base = _c(CONC * 0.72) * (1 + 0.1 * big + 0.02 * fine)[..., None]
    damp = smoothstep(fbm(h, w, 70.0, 50.0, 4, 0.55, seed + 2), 0.4, 1.6)
    base = _mix(base, _c(GRIME), 0.55 * damp)
    crack = np.exp(-(fbm(h, w, 120.0, 90.0, 3, 0.5, seed + 4) / 0.04) ** 2) * smoothstep(
        noise(h, w, 80.0, 80.0, seed + 5), 0.3, 1.0)
    base = base + (_c(DUST) * 0.2 * crack[..., None])  # efflorescence along cracks
    return dict(albedo=base, rough=0.92 - 0.1 * damp, metal=0.0, height=0.0006 * fine + 0.001 * big,
                ao=0.8 - 0.1 * damp)


def _top(h, w, px, v, seed):
    big = fbm(h, w, 110.0, 110.0, 4, 0.55, seed + 1)
    mid = noise(h, w, 12.0, 12.0, seed + 2)
    fine = noise(h, w, 1.0, 1.0, seed + 3)
    base = _c(CONC * 1.02) * (1 + 0.08 * big + 0.04 * mid + 0.03 * fine)[..., None]
    dust = smoothstep(fbm(h, w, 60.0, 60.0, 4, 0.55, seed + 4), -0.2, 1.4)
    base = _mix(base, _c(DUST), 0.45 * dust)
    dirt = smoothstep(fbm(h, w, 90.0, 90.0, 4, 0.55, seed + 5), 0.5, 1.8)
    base = _mix(base, _c(GRIME), 0.6 * dirt)
    puddle = smoothstep(fbm(h, w, 140.0, 140.0, 3, 0.5, seed + 6), 1.0, 1.5)
    base = base * (1 - 0.25 * puddle)[..., None]
    return dict(albedo=base, rough=np.clip(0.9 - 0.5 * puddle + 0.03 * mid, 0.25, 1.0), metal=0.0,
                height=0.0008 * fine + 0.002 * big, ao=1.0 - 0.1 * dirt)


def _roof(h, w, px, v, seed):
    slab = ROOF_SLAB_M * PX_PER_M
    vpx = v * PX_PER_M + 0.0 * np.zeros((1, w))
    cols = np.arange(w)[None, :].astype(np.float64)
    iu = np.floor(cols / slab).astype(int)
    iv = np.floor(vpx / slab).astype(int)
    rng = np.random.default_rng(seed)
    tone_tab = 1.0 + rng.normal(0.0, 0.09, (64, 64))
    patch_tab = rng.random((64, 64)) < 0.07
    tone = tone_tab[iv % 64, iu % 64]
    patch = patch_tab[iv % 64, iu % 64].astype(np.float64)
    du = np.minimum(cols % slab, slab - cols % slab)
    dv = np.minimum(vpx % slab, slab - vpx % slab)
    joint = sstep(2.4, 0.6, np.minimum(du, dv))
    big = fbm(h, w, 160.0, 160.0, 4, 0.55, seed + 1)
    mid = noise(h, w, 14.0, 14.0, seed + 2)
    fine = noise(h, w, 1.0, 1.0, seed + 3)
    base = _c(CONC * 0.9) * (tone * (1 + 0.08 * big + 0.04 * mid + 0.025 * fine))[..., None]
    bitumen = _c((0.016, 0.016, 0.017)) * (1 + 0.1 * mid)[..., None]
    base = _mix(base, bitumen, 0.75 * patch)
    pond = smoothstep(fbm(h, w, 200.0, 200.0, 3, 0.5, seed + 4), 0.6, 1.4)
    base = base * (1 - 0.35 * pond)[..., None]
    moss = joint * smoothstep(noise(h, w, 40.0, 40.0, seed + 5), 0.0, 1.0)
    base = _mix(base, _c(MOSS), 0.5 * moss)
    base = base * (1 - 0.3 * joint)[..., None]
    rough = np.clip(0.88 - 0.55 * pond + 0.04 * mid - 0.1 * patch, 0.2, 1.0)
    height = -0.008 * joint + 0.0008 * fine + 0.003 * (tone - 1) * 3
    return dict(albedo=base, rough=rough, metal=0.0, height=height, ao=1 - 0.35 * joint)


def _foliage(h, w, px, v, seed):
    f1, f2, idx, val = cells(h, w, 20.0, seed, 1.0)
    clump = smoothstep(f2 - f1, 0.0, 8.0)
    shade = np.clip(1.0 - f1 / 14.0, 0.0, 1.0)
    rng = np.random.default_rng(seed)
    hue = rng.random(int(idx.max()) + 1)
    g = hue[idx]
    leaf = noise(h, w, 2.0, 2.0, seed + 1)
    dark = np.array((0.010, 0.022, 0.008))
    mid = np.array((0.025, 0.055, 0.015))
    olive = np.array((0.045, 0.050, 0.018))
    base = _mix(_mix(_c(dark), _c(mid), shade * 0.9), _c(olive), 0.4 * g)
    base = base * (1 + 0.15 * leaf)[..., None]
    low = sstep(0.5, 0.0, v)
    base = base * (1 - 0.5 * low)[..., None]
    height = 0.04 * shade * clump + 0.004 * leaf
    return dict(albedo=base, rough=0.75, metal=0.0, height=height, ao=0.6 + 0.4 * shade, normal_strength=0.6)


CONCRETE_FILL = {"wall_a": _concrete_wall("a"), "wall_b": _concrete_wall("b"), "wall_c": _concrete_wall("c"),
                 "parapet": _parapet, "soffit": _soffit, "top": _top, "roof": _roof, "foliage": _foliage}


def fill_concrete(sheet):
    for k, (name, _) in enumerate(CONCRETE_BANDS):
        sheet.fill(name, CONCRETE_FILL[name], seed=1000 + 37 * k)
    return sheet


# =========================================================================================
# Metal trim sheet (+ decal row)
# =========================================================================================
METAL_BANDS = (("panel", FH), ("louver", 2.4), ("grating", FH), ("rail", 1.2), ("rust", FH), ("dark", 1.0))
DECAL_ROWS = 768
PAD_M = 24.0                     # landing pad decal: a 24 m square
DECALS = {                       # decal rectangles inside the decal band (px: x0, y0, x1, y1)
    "pad": (0, 0, 768, 768),
    "fan": (768, 0, 1280, 512),
    "hazard": (1280, 0, 1536, 256),
}


def metal_sheet():
    size = TEX[MAT_METAL]
    sheet = TrimSheet(size, size, PX_PER_M, pad=PAD)
    for name, m in METAL_BANDS:
        sheet.add_band(name, _rows(m))
    sheet.add_band("decals", DECAL_ROWS)
    return sheet


def decal_rect(sheet, name):
    """UV rectangle (u0, v0, u1, v1) of a metal decal."""
    b = sheet.bands["decals"]
    x0, y0, x1, y1 = DECALS[name]
    return (x0 / sheet.width, (b.row0 + y0) / sheet.height, x1 / sheet.width, (b.row0 + y1) / sheet.height)


def _paint_wear(h, w, seed, base, amount):
    chips = smoothstep(fbm(h, w, 25.0, 25.0, 4, 0.6, seed), 1.7, 2.4) * amount
    return _mix(base, _c(RUST * 0.8), chips), chips


def _panel(h, w, px, v, seed):
    seam_px = 32
    cols = np.arange(w)
    d = np.minimum(cols % seam_px, seam_px - cols % seam_px)[None, :].astype(np.float64)
    seam = sstep(2.0, 0.3, d) * np.ones_like(v)
    rng = np.random.default_rng(seed)
    pidx = cols // 96
    accents = [GUNMETAL, GUNMETAL, GUNMETAL, GUNMETAL * 1.6, np.array((0.030, 0.055, 0.055)),
               np.array((0.075, 0.030, 0.016)), np.array((0.09, 0.07, 0.025))]
    pick = rng.integers(0, len(accents), int(pidx.max()) + 1)
    col = np.stack([accents[k] for k in pick])[pidx][None, :, :] * np.ones((h, 1, 1))
    big = fbm(h, w, 120.0, 80.0, 4, 0.55, seed + 1)
    col = col * (1 + 0.12 * big)[..., None]
    col, chips = _paint_wear(h, w, seed + 2, col, 0.6)
    s = _streaks(h, w, FH - v, seed + 3, 0.6, length=(0.4, 2.0))
    col = _mix(col, _c(GRIME), 0.6 * s)
    r = _rust_runs(h, w, FH - v, seed + 4, 4)
    col = _mix(col, _c(RUST), 0.6 * r)
    dirt = sstep(0.6, 0.0, v)
    col = _mix(col, _c(GRIME), 0.5 * dirt)
    return dict(albedo=col, rough=0.55 + 0.15 * s + 0.2 * chips, metal=0.15 + 0.4 * chips,
                height=0.008 * seam + 0.0005 * big, ao=1 - 0.2 * seam)


def _louver(h, w, px, v, seed):
    period = 0.2
    ph = np.mod(v, period) / period
    blade = np.where(ph < 0.75, ph / 0.75, (1 - ph) / 0.25)
    height = 0.02 * blade
    gap = sstep(0.86, 0.95, ph) * sstep(1.0, 0.96, ph)
    big = fbm(h, w, 100.0, 60.0, 4, 0.55, seed + 1)
    col = _c(GUNMETAL * 1.7) * (1 + 0.1 * big + 0.12 * blade)[..., None]
    col = col * (1 - 0.45 * gap)[..., None]
    col, chips = _paint_wear(h, w, seed + 2, col, 0.4)
    frame = sstep(0.08, 0.04, v) + sstep(2.32, 2.36, v)
    col = _mix(col, _c(GUNMETAL), np.clip(frame, 0, 1))
    return dict(albedo=col, rough=0.5 + 0.2 * chips, metal=0.3, height=height * (1 - np.clip(frame, 0, 1)),
                ao=1 - 0.4 * gap, normal_strength=0.5)


def _grating(h, w, px, v, seed):
    big = fbm(h, w, 100.0, 100.0, 4, 0.55, seed + 1)
    fine = noise(h, w, 1.5, 1.5, seed + 2)
    col = _c(GUNMETAL * 1.3) * (1 + 0.12 * big + 0.1 * fine)[..., None]
    rust = smoothstep(fbm(h, w, 50.0, 50.0, 4, 0.55, seed + 3), 1.3, 2.2)
    col = _mix(col, _c(RUST * 0.7), 0.6 * rust)
    cols = np.arange(w)[None, :]
    d = np.minimum(cols % 64, 64 - cols % 64) * np.ones_like(v)
    dv = np.minimum(np.mod(v * 64, 64), 64 - np.mod(v * 64, 64))
    joint = sstep(1.8, 0.4, np.minimum(d, dv))
    col = col * (1 - 0.4 * joint)[..., None]
    return dict(albedo=col, rough=0.6 + 0.2 * rust, metal=0.6 - 0.4 * rust, height=0.001 * fine - 0.004 * joint,
                ao=1 - 0.3 * joint)


def _rail(h, w, px, v, seed):
    cols = np.arange(w)[None, :].astype(np.float64)
    post_px = w / 20.0
    d = np.minimum(np.mod(cols, post_px), post_px - np.mod(cols, post_px)) * np.ones_like(v)
    post = sstep(2.6, 1.6, d)
    toprail = sstep(1.05, 1.09, v)
    kick = sstep(0.16, 0.12, v)
    mesh = 0.07 * (1 + 0.15 * noise(h, w, 1.0, 1.0, seed))
    col = _c(GUNMETAL * 1.4) * (1 + 0.12 * fbm(h, w, 80.0, 40.0, 3, 0.5, seed + 1))[..., None]
    col = col * (mesh / 0.07)[..., None]
    col = _mix(col, _c(STEEL * 0.6), np.clip(post + toprail, 0, 1))
    col = _mix(col, _c(GUNMETAL * 0.8), kick)
    s = _streaks(h, w, 1.2 - v, seed + 2, 0.5, length=(0.2, 0.8))
    col = _mix(col, _c(GRIME), 0.5 * s)
    return dict(albedo=col, rough=0.5 - 0.15 * toprail, metal=0.5 + 0.3 * np.clip(post + toprail, 0, 1),
                height=0.01 * np.clip(post + toprail, 0, 1), ao=1 - 0.3 * kick)


def _rust(h, w, px, v, seed):
    big = fbm(h, w, 80.0, 120.0, 5, 0.55, seed + 1)
    mask = smoothstep(big, -0.6, 0.9)
    paint = _c(np.array((0.10, 0.10, 0.095)))
    rustc = _c(RUST) * (1 + 0.25 * noise(h, w, 3.0, 3.0, seed + 2))[..., None]
    col = _mix(paint, rustc, mask)
    s = _streaks(h, w, FH - v, seed + 3, 0.7, length=(0.6, 2.4))
    col = _mix(col, _c(RUST * 0.6), 0.5 * s)
    return dict(albedo=col, rough=0.6 + 0.3 * mask, metal=0.3 * (1 - mask),
                height=0.0015 * noise(h, w, 2.0, 2.0, seed + 4) * mask)


def _dark(h, w, px, v, seed):
    big = fbm(h, w, 80.0, 40.0, 3, 0.5, seed + 1)
    col = _c(np.array((0.012, 0.013, 0.015))) * (1 + 0.15 * big)[..., None]
    return dict(albedo=col, rough=0.45 + 0.05 * big, metal=0.6, height=0.0003 * big)


def _decals(h, w, px, v, seed):
    """Decal row: pad markings, fan grille, hazard stripes (edge-padded)."""
    H = DECAL_ROWS
    alb = np.zeros((H, w, 3))
    alb[:] = GUNMETAL * 1.3
    rough = np.full((H, w), 0.6)
    metal = np.full((H, w), 0.5)
    hgt = np.zeros((H, w))
    ao = np.ones((H, w))
    # --- landing pad: 24 m steel deck, painted rings, numerals, worn paint, skid marks
    x0, y0, x1, y1 = DECALS["pad"]
    n = x1 - x0
    ppm = n / PAD_M
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    X, Y = (xx + 0.5) / ppm - PAD_M / 2, (yy + 0.5) / ppm - PAD_M / 2
    R = np.hypot(X, Y)
    big = fbm(n, n, 90.0, 90.0, 4, 0.55, seed + 11)
    deck = _c(np.array((0.055, 0.058, 0.062))) * (1 + 0.12 * big)[..., None]
    plate = np.minimum(np.mod(X, 2.0), 2.0 - np.mod(X, 2.0))
    plate = np.minimum(plate, np.minimum(np.mod(Y, 2.0), 2.0 - np.mod(Y, 2.0)))
    seam = sstep(0.05, 0.015, plate)
    deck = deck * (1 - 0.3 * seam)[..., None]
    ring_o = sstep(0.32, 0.26, np.abs(R - 10.6))
    ring_i = sstep(0.2, 0.15, np.abs(R - 6.5))
    raw, tw, th = text_strokes("07", 0, 0, 5.0)

    def to_px(p):
        return ((p[0] - tw / 2) * ppm + n / 2, (p[1] - th / 2) * ppm + n / 2)

    segs = [(to_px(a), to_px(b)) for a, b in raw]
    core, _, _, _ = neon_tubes((n, n), segs, 0.32 * ppm, halo=1.0)
    ticks = np.zeros((n, n))
    for ang in (0, 90, 180, 270):
        a = math.radians(ang + 45)
        u = X * math.cos(a) + Y * math.sin(a)
        vv = -X * math.sin(a) + Y * math.cos(a)
        ticks = np.maximum(ticks, sstep(0.32, 0.26, np.abs(vv)) * sstep(7.6, 7.7, u) * sstep(
            9.6, 9.5, u))
    wear = smoothstep(fbm(n, n, 30.0, 30.0, 4, 0.6, seed + 12), 0.9, 1.6)
    paint_y = np.clip(ring_o + ticks, 0, 1) * (1 - 0.7 * wear)
    paint_w = np.clip(ring_i + core, 0, 1) * (1 - 0.7 * wear)
    pad = _mix(_mix(deck, _c(PAINT_AMBER), paint_y), _c(PAINT_WHITE), paint_w)
    skid = smoothstep(fbm(n, n, 40.0, 12.0, 3, 0.5, seed + 13), 1.0, 2.0) * sstep(9.0, 4.0, R)
    pad = _mix(pad, _c(np.array((0.012, 0.012, 0.012))), 0.6 * skid)
    edge = sstep(11.6, 11.8, np.maximum(np.abs(X), np.abs(Y)))
    hz = (np.mod((X + Y) / 1.0, 2.0) < 1.0).astype(np.float64)
    pad = _mix(pad, _mix(_c(np.array((0.02, 0.02, 0.02))), _c(PAINT_AMBER), hz), edge * (1 - 0.5 * wear))
    alb[y0:y1, x0:x1] = pad
    rough[y0:y1, x0:x1] = 0.55 + 0.15 * big * 0.3 - 0.1 * np.clip(paint_y + paint_w, 0, 1) + 0.25 * skid
    metal[y0:y1, x0:x1] = 0.6 * (1 - np.clip(paint_y + paint_w + edge, 0, 1))
    hgt[y0:y1, x0:x1] = -0.006 * seam + 0.0008 * big
    # --- fan grille (2.4 m fan, seen from above)
    x0, y0, x1, y1 = DECALS["fan"]
    n = x1 - x0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    X, Y = (xx + 0.5) / n * 2 - 1, (yy + 0.5) / n * 2 - 1
    R = np.hypot(X, Y)
    A = np.arctan2(Y, X)
    blades = 0.5 + 0.5 * np.cos(7 * A + 3.0 * R)
    hub = sstep(0.2, 0.17, R)
    inside = sstep(0.93, 0.9, R)
    rim = sstep(0.9, 0.93, R) * sstep(1.0, 0.97, R)
    guard = 0.5 + 0.5 * np.cos(R * 2 * math.pi * 6)
    fan = _c(np.array((0.008, 0.008, 0.009))) * np.ones((n, n, 1))
    fan = _mix(fan, _c(GUNMETAL * 1.8), 0.6 * blades * inside * sstep(0.2, 0.3, R))
    fan = _mix(fan, _c(GUNMETAL * 2.2), np.clip(hub + rim + 0.25 * guard * inside, 0, 1))
    alb[y0:y1, x0:x1] = fan
    rough[y0:y1, x0:x1] = 0.5
    metal[y0:y1, x0:x1] = 0.6
    ao[y0:y1, x0:x1] = 0.45 + 0.55 * (1 - inside) + 0.3 * hub
    hgt[y0:y1, x0:x1] = 0.01 * (rim + hub) - 0.03 * inside * (1 - hub)
    # --- hazard stripes (4 m square, 0.5 m stripes)
    x0, y0, x1, y1 = DECALS["hazard"]
    n = x1 - x0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    st = (np.mod((xx + yy) / (n / 8.0), 2.0) < 1.0).astype(np.float64)
    st = blur(st, 1.0)
    alb[y0:y1, x0:x1] = _mix(_c(np.array((0.02, 0.02, 0.02))), _c(PAINT_AMBER), st)
    rough[y0:y1, x0:x1] = 0.6
    metal[y0:y1, x0:x1] = 0.1
    # edge-pad to the band's rows
    idx = np.clip(np.arange(h) - PAD, 0, H - 1)
    return dict(albedo=alb[idx], rough=rough[idx], metal=metal[idx], height=hgt[idx], ao=ao[idx])


METAL_FILL = {"panel": _panel, "louver": _louver, "grating": _grating, "rail": _rail, "rust": _rust,
              "dark": _dark, "decals": _decals}


def fill_metal(sheet):
    for k, name in enumerate([n for n, _ in METAL_BANDS] + ["decals"]):
        sheet.fill(name, METAL_FILL[name], seed=2000 + 41 * k)
    return sheet


# =========================================================================================
# Window tile
# =========================================================================================
CELL_PX = TEX[MAT_WINDOWS] // CELLS        # 64
JAMB, SLAB, LINTEL = 0.14, 0.15, 2.80       # meters: jamb width each side, slab edge, opening top
FRAME = 0.07
LIT_UNIT = 0.52                              # chance an apartment (1-3 bays) is lit
LIT_ROOM = 0.86                              # chance a bay of a lit apartment is lit
COLD_SHARE = 0.25


def window_plan(seed=7):
    """Per-cell states (row r = floor, column c = bay): dict with kind
    ('window' / 'blank' / 'shutter'), lit, color, intensity, details. Pure
    numbers, used by build.py (lit cells for skylights) and window_tile."""
    rng = np.random.default_rng(seed)
    plan = [[None] * CELLS for _ in range(CELLS)]
    for r in range(CELLS):
        c = 0
        while c < CELLS:
            width = int(rng.choice([1, 2, 2, 3, 3]))
            lit = rng.random() < LIT_UNIT
            cold = rng.random() < COLD_SHARE
            cold_kind = str(rng.choice(["led", "tv", "fluo"], p=[0.5, 0.3, 0.2]))
            warm_t = rng.random()
            curtains = rng.random() < 0.45
            for k in range(width):
                cc = (c + k) % CELLS
                kind = str(rng.choice(["window", "blank", "shutter"], p=[0.88, 0.06, 0.06]))
                on = lit and kind != "blank" and rng.random() < LIT_ROOM
                dim = (not on) and kind == "window" and rng.random() < 0.12
                if on:
                    color = COLD[cold_kind] if cold else WARM_A * (1 - warm_t) + WARM_B * warm_t
                    inten = float(np.clip(rng.beta(2.2, 1.6), 0.3, 1.0))
                elif dim:
                    color = WARM_A * 0.8 + WARM_B * 0.2
                    inten = float(rng.uniform(0.06, 0.16))
                else:
                    color, inten = None, 0.0
                plan[r][cc] = dict(kind=kind, lit=bool(on), dim=bool(dim), color=color, inten=inten,
                                   cold=bool(cold and on), curtains=curtains and rng.random() < 0.8,
                                   blinds=rng.random() < 0.14, split=float(rng.choice([0.38, 0.5, 0.62])),
                                   transom=rng.random() < 0.5, shutter=float(rng.uniform(0.3, 1.0)),
                                   seed=int(rng.integers(1 << 30)))
            c += width
    return plan


def lit_cells(plan, warm=True):
    return [(c, r) for r in range(CELLS) for c in range(CELLS)
            if plan[r][c]["lit"] and plan[r][c]["kind"] == "window" and plan[r][c]["cold"] != warm
            and plan[r][c]["inten"] > 0.6]


def _sm(d, w=0.6):
    """Antialiased inside mask from a signed distance in pixels (positive inside)."""
    return np.clip(d / w * 0.5 + 0.5, 0.0, 1.0)


def _cell(st, conc_tex):
    n = CELL_PX
    sx, sy = BAY / n, FH / n          # meters per pixel
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    xm, ym = (xx + 0.5) * sx, (yy + 0.5) * sy
    rng = np.random.default_rng(st["seed"])
    # signed distances (px) of the opening and the glass
    ox0, ox1, oy0, oy1 = JAMB, BAY - JAMB, SLAB, LINTEL
    d_open = np.minimum(np.minimum(xm - ox0, ox1 - xm) / sx, np.minimum(ym - oy0, oy1 - ym) / sy)
    opening = _sm(d_open)
    d_glass = d_open - FRAME / sx
    split = ox0 + (ox1 - ox0) * st["split"]
    d_mull = np.abs(xm - split) / sx - FRAME * 0.5 / sx
    d_glass = np.minimum(d_glass, d_mull)
    if st["transom"]:
        d_glass = np.minimum(d_glass, np.abs(ym - 2.2) / sy - FRAME * 0.5 / sy)
    glass = _sm(d_glass) * opening
    frame = opening * (1 - glass)
    albedo = conc_tex.copy()
    rough = np.full((n, n), 0.9)
    metal = np.zeros((n, n))
    height = np.zeros((n, n))
    ao = np.ones((n, n))
    emis = np.zeros((n, n, 3))
    slab = _sm((SLAB - ym) / sy)
    albedo = albedo * (1 - 0.35 * slab)[..., None]
    if st["kind"] == "blank":
        inset = _sm(np.minimum(np.minimum(xm - 0.3, BAY - 0.3 - xm) / sx, np.minimum(ym - 0.3, 2.7 - ym) / sy))
        albedo = albedo * (1 - 0.12 * inset)[..., None]
        height = -0.02 * inset
        return albedo, rough, metal, height, ao, emis
    # frames: gunmetal; glass: dark, glossy
    albedo = _mix(albedo, _c(GUNMETAL * 1.2), frame)
    g = GLASS * (1 + 0.25 * rng.normal())
    albedo = _mix(albedo, _c(g), glass)
    rough = rough * (1 - opening) + opening * (0.45 * frame + glass * rng.uniform(0.05, 0.14))
    metal = 0.5 * frame
    height = -0.06 * opening - 0.05 * glass
    lintel_sh = np.exp(-np.clip(oy1 - ym, 0, None) / 0.35)
    ao = 1 - opening * (0.35 * lintel_sh + 0.15 * frame)
    if st["kind"] == "shutter":
        ytop = oy1 - (oy1 - oy0) * st["shutter"]
        sh = opening * _sm((ym - ytop) / sy)
        slats = 0.5 + 0.5 * np.cos(ym / 0.3 * 2 * math.pi)
        albedo = _mix(albedo, _c(GUNMETAL * 2.0) * (1 + 0.08 * slats)[..., None], sh)
        rough = rough * (1 - sh) + 0.6 * sh
        glass = glass * (1 - sh)
    # interior light
    if st["lit"] or st["dim"]:
        col = np.asarray(st["color"])
        inten = st["inten"]
        gx0, gx1 = ox0 + FRAME, ox1 - FRAME
        gy0, gy1 = oy0 + FRAME, oy1 - FRAME
        ty = np.clip((ym - gy0) / (gy1 - gy0), 0, 1)
        tx = np.clip((xm - gx0) / (gx1 - gx0), 0, 1)
        light = 0.62 + 0.38 * ty
        if rng.random() < 0.55:  # a lamp: soft hotspot
            lx, ly = rng.uniform(0.2, 0.8), rng.uniform(0.25, 0.6)
            light = light + 0.45 * np.exp(-((tx - lx) ** 2 + (ty - ly) ** 2) / 0.08)
        light = light * (1 - 0.25 * np.abs(tx - 0.5))
        lit = light * inten
        if st["cold"] and st["color"] is COLD["tv"]:
            lit = lit * (0.55 + 0.45 * np.exp(-((tx - 0.5) ** 2 + (ty - 0.35) ** 2) / 0.12))
        tint = np.ones((n, n, 3)) * col[None, None, :]
        if st["curtains"]:
            side = rng.choice(["left", "right", "both", "full", "half"])
            cw = rng.uniform(0.2, 0.42)
            if side == "left":
                cm = _sm((cw - tx) * (gx1 - gx0) / sx, 1.5)
            elif side == "right":
                cm = _sm((tx - (1 - cw)) * (gx1 - gx0) / sx, 1.5)
            elif side == "both":
                cm = np.maximum(_sm((cw - tx) * (gx1 - gx0) / sx, 1.5), _sm((tx - (1 - cw)) * (gx1 - gx0) / sx, 1.5))
            elif side == "half":
                cm = _sm((tx - 0.5) * (gx1 - gx0) / sx, 1.5) if rng.random() < 0.5 else _sm(
                    (0.5 - tx) * (gx1 - gx0) / sx, 1.5)
            else:
                cm = np.ones_like(tx)
            folds = 0.92 + 0.08 * np.cos(tx * (gx1 - gx0) / 0.6 * 2 * math.pi + rng.uniform(0, 6))
            ccol = col * np.array((1.0, 0.86, 0.68)) if not st["cold"] else col * np.array((0.9, 0.95, 1.0))
            lit = lit * (1 - cm) + cm * inten * 0.68 * folds
            tint = _mix(tint, _c(ccol), cm)
            albedo = _mix(albedo, _c(np.array((0.05, 0.042, 0.032))), cm * glass * 0.6)
        if st["blinds"]:
            lit = lit * (0.55 + 0.08 * np.cos(ym / 0.4 * 2 * math.pi))
        # silhouettes: furniture, plants, the odd person (soft, dark)
        sil = np.zeros((n, n))
        for _ in range(int(rng.integers(0, 3))):
            kind = rng.choice(["sofa", "plant", "shelf", "person"], p=[0.45, 0.3, 0.17, 0.08])
            cx = rng.uniform(gx0 + 0.3, gx1 - 0.3)
            if kind == "sofa":
                wd, ht = rng.uniform(0.5, 0.9), rng.uniform(0.75, 0.95)
                dd = np.minimum((wd - np.abs(xm - cx)) / sx, (ht - ym) / sy)
            elif kind == "plant":
                r = rng.uniform(0.28, 0.42)
                cy = rng.uniform(1.0, 1.4)
                dd = np.maximum((r - np.hypot(xm - cx, (ym - cy) * 1.1)) / sx, np.minimum(
                    (0.06 - np.abs(xm - cx)) / sx, (cy - ym) / sy))
            elif kind == "shelf":
                wd = rng.uniform(0.3, 0.5)
                dd = np.minimum((wd - np.abs(xm - cx)) / sx, (rng.uniform(1.6, 2.1) - ym) / sy)
            else:
                head = (0.13 - np.hypot(xm - cx, ym - 1.62)) / sx
                torso = np.minimum((0.24 - np.abs(xm - cx)) / sx, (1.45 - ym) / sy)
                dd = np.maximum(head, torso)
            sil = np.maximum(sil, _sm(dd, 2.0))
        lit = lit * (1 - 0.82 * sil)
        lit = blur(lit, 0.6)
        emis = tint * (lit * glass)[..., None]
    return albedo, rough, metal, height, ao, emis


def window_tile(plan=None, seed=7):
    """The 32 x 32 cell window tile: dict of albedo, rough, metal, ao, normal, emission (linear)."""
    plan = plan or window_plan(seed)
    size = TEX[MAT_WINDOWS]
    n = CELL_PX
    # concrete under everything: a periodic, low-contrast field
    big = fbm(size, size, 140.0, 140.0, 4, 0.55, seed + 1)
    fine = noise(size, size, 1.2, 1.2, seed + 2)
    conc = _c(CONC * 0.95) * (1 + 0.08 * big + 0.025 * fine)[..., None]
    streak = smoothstep(noise(size, size, 5.0, 60.0, seed + 3), 0.6, 2.0)
    conc = _mix(conc, _c(GRIME), 0.5 * streak)
    albedo = np.zeros((size, size, 3))
    rough = np.zeros((size, size))
    metal = np.zeros((size, size))
    height = np.zeros((size, size))
    ao = np.zeros((size, size))
    emis = np.zeros((size, size, 3))
    for r in range(CELLS):
        for c in range(CELLS):
            sl = (slice(r * n, (r + 1) * n), slice(c * n, (c + 1) * n))
            a, ro, me, he, o, e = _cell(plan[r][c], conc[sl])
            albedo[sl], rough[sl], metal[sl], height[sl], ao[sl], emis[sl] = a, ro, me, he, o, e
    height = blur(height, 0.6)
    normal = height_to_normal_2d(height, BAY / n, 0.6)
    return dict(albedo=albedo, rough=rough, metal=metal, ao=ao, normal=normal, emission=emis, plan=plan)


# =========================================================================================
# Neon atlas
# =========================================================================================
NEON_PX_PER_M = 32.0
NEON_RECTS = {
    "roof_sign": (0, 832, 1024, 1024),          # 32 x 6 m
    "blade_0": (0, 256, 96, 768),                # 3 x 16 m each
    "blade_1": (96, 256, 192, 768),
    "blade_2": (192, 256, 288, 768),
    "blade_3": (288, 256, 384, 768),
    "blade_4": (384, 256, 480, 768),
    "blade_5": (480, 256, 576, 768),
    "small_0": (576, 736, 800, 832),             # 7 x 3 m each
    "small_1": (800, 736, 1024, 832),
    "small_2": (576, 640, 800, 736),
    "small_3": (800, 640, 1024, 736),
    "small_4": (576, 544, 800, 640),
    "small_5": (800, 544, 1024, 640),
    "small_6": (576, 448, 800, 544),
    "small_7": (800, 448, 1024, 544),
    "billboard": (576, 208, 1024, 432),          # 20 x 10 m
}
for _k, _name in enumerate(SWATCHES):
    NEON_RECTS[f"swatch_{_name}"] = (_k * 64, 0, _k * 64 + 64, 64)
    NEON_RECTS[f"strip_{_name}"] = (_k * 64, 64, _k * 64 + 64, 128)
    NEON_RECTS[f"dimstrip_{_name}"] = (_k * 64, 128, _k * 64 + 64, 192)
    NEON_RECTS[f"pool_{_name}"] = (_k * 64, 192, _k * 64 + 64, 256)
    NEON_RECTS[f"dimpool_{_name}"] = (_k * 64, 256, _k * 64 + 64, 320)


def neon_rect_uv(name, inset=0.0):
    x0, y0, x1, y1 = NEON_RECTS[name]
    s = float(TEX[MAT_NEON])
    return ((x0 + inset) / s, (y0 + inset) / s, (x1 - inset) / s, (y1 - inset) / s)


def neon_rect_size(name):
    x0, y0, x1, y1 = NEON_RECTS[name]
    return (x1 - x0) / NEON_PX_PER_M, (y1 - y0) / NEON_PX_PER_M


def _neon_sign(layers, rect, glyph_specs, rng):
    """glyph_specs: list of (segments in sign-local px, color name, tube radius px)."""
    x0, y0, x1, y1 = rect
    for segs, cname, rad in glyph_specs:
        layers.append((rect, [((a[0] + x0, a[1] + y0), (b[0] + x0, b[1] + y0)) for a, b in segs], cname, rad))


def _glyph_row(rng, count, size, x, y, step):
    segs = []
    for k in range(count):
        segs += pseudo_glyph(rng, x + k * step, y, size)
    return segs


def _glyph_col(rng, count, size, x, y_top, step):
    segs = []
    for k in range(count):
        segs += pseudo_glyph(rng, x, y_top - size - k * step, size)
    return segs


def _centered_text(text, w, h, height, vertical=False):
    segs, tw, th = text_strokes(text, 0, 0, height, vertical=vertical)
    if vertical:
        segs, tw, th = text_strokes(text, 0, 0, height, vertical=True)
        ox, oy = (w - tw) / 2, h - (h - th) / 2
        return [((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)) for a, b in segs]
    ox, oy = (w - tw) / 2, (h - th) / 2
    return [((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)) for a, b in segs]


def neon_atlas(seed=11):
    size = TEX[MAT_NEON]
    rng = np.random.default_rng(seed)
    layers = []
    # roof sign (deck): three pseudo-glyphs in magenta, KAZE in cyan
    x0, y0, x1, y1 = NEON_RECTS["roof_sign"]
    w, h = x1 - x0, y1 - y0
    gs = 140
    _neon_sign(layers, NEON_RECTS["roof_sign"], [
        (_glyph_row(rng, 3, gs, 28, (h - gs) / 2, gs + 26), "magenta", 6.0),
        ([((a[0] + 560, a[1]), (b[0] + 560, b[1])) for a, b in _centered_text("KAZE", 440, h, 104)], "cyan", 5.5),
    ], rng)
    # blades: vertical glyph stacks
    blade_cols = ["magenta", "cyan", "amber", "uv", "amber", "magenta"]
    for k in range(6):
        name = f"blade_{k}"
        bx0, by0, bx1, by1 = NEON_RECTS[name]
        bw, bh = bx1 - bx0, by1 - by0
        if k == 4:
            segs = _centered_text("HOTEL", bw, bh, 70, vertical=True)
            layers.append((NEON_RECTS[name], [((a[0] + bx0, a[1] + by0), (b[0] + bx0, b[1] + by0)) for a, b in segs],
                           blade_cols[k], 4.5))
            continue
        gsz = 72
        n = 4 if k != 2 else 3
        step = (bh - 30 - (120 if k == 2 else 0)) / n
        segs = _glyph_col(rng, n, gsz, (bw - gsz) / 2, bh - 15 - (step - gsz) / 2, step)
        if k == 2:
            segs += _centered_text("24", bw, 130, 52)
        layers.append((NEON_RECTS[name], [((a[0] + bx0, a[1] + by0), (b[0] + bx0, b[1] + by0)) for a, b in segs],
                       blade_cols[k], 4.5))
    # small signs
    smalls = [("RAMEN", "amber"), ("NOVA", "uv"), ("OKAMI", "cyan"), ("24H", "green"), ("+", "green"),
              (None, "magenta"), ("BAR", "magenta"), (None, "cyan")]
    for k, (text, cname) in enumerate(smalls):
        name = f"small_{k}"
        sx0, sy0, sx1, sy1 = NEON_RECTS[name]
        sw, sh = sx1 - sx0, sy1 - sy0
        if text is None:
            segs = _glyph_row(rng, 3, 62, 18, (sh - 62) / 2, 66)
        elif text == "+":
            segs = _centered_text("+", sw, sh, 76)
        else:
            segs = _centered_text(text, sw, sh, 44 if len(text) > 3 else 52)
        layers.append((NEON_RECTS[name], [((a[0] + sx0, a[1] + sy0), (b[0] + sx0, b[1] + sy0)) for a, b in segs],
                       cname, 4.0))
    # billboard: NOVA in ultraviolet over a magenta glyph line
    bx0, by0, bx1, by1 = NEON_RECTS["billboard"]
    bw, bh = bx1 - bx0, by1 - by0
    segs = [((a[0], a[1] + 40), (b[0], b[1] + 40)) for a, b in _centered_text("NOVA", bw, bh - 40, 110)]
    layers.append((NEON_RECTS["billboard"], [((a[0] + bx0, a[1] + by0), (b[0] + bx0, b[1] + by0)) for a, b in segs],
                   "uv", 6.0))
    segs = _glyph_row(rng, 5, 46, 40, 18, 76)
    layers.append((NEON_RECTS["billboard"], [((a[0] + bx0, a[1] + by0), (b[0] + bx0, b[1] + by0)) for a, b in segs],
                   "magenta", 3.5))

    emis = np.zeros((size, size, 3))
    albedo = np.zeros((size, size, 3)) + 0.012
    rough = np.full((size, size), 0.55)
    hgt = np.zeros((size, size))
    for rect, segs, cname, rad in layers:
        x0, y0, x1, y1 = rect
        core, hot, glow, prof = neon_tubes((y1 - y0, x1 - x0), [((a[0] - x0, a[1] - y0), (b[0] - x0, b[1] - y0))
                                                               for a, b in segs], rad, halo=3.2)
        col = NEON[cname]
        e = _c(col) * (core + 0.22 * glow)[..., None] + _c(np.ones(3)) * (0.35 * hot * core)[..., None]
        sl = (slice(y0, y1), slice(x0, x1))
        emis[sl] = np.maximum(emis[sl], e)
        albedo[sl] = _mix(albedo[sl], _c(0.25 + 0.5 * col), core * 0.6)
        rough[sl] = rough[sl] * (1 - core) + 0.15 * core
        hgt[sl] = np.maximum(hgt[sl], 0.03 * prof)
    # swatches (lights): bright plateau, soft edge; strips: soft across V only
    for name in SWATCHES:
        col = NEON[name]
        for kind in ("swatch", "strip", "dimstrip", "pool", "dimpool"):
            x0, y0, x1, y1 = NEON_RECTS[f"{kind}_{name}"]
            n = x1 - x0
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
            t = np.abs((yy + 0.5) / n - 0.5) * 2
            if kind == "swatch":
                t = np.maximum(t, np.abs((xx + 0.5) / n - 0.5) * 2)
            m = 0.25 + 0.75 * sstep(1.0, 0.55, t)
            if kind == "dimstrip":  # walkway / pad edge wash: about a lit window's brightness, very soft edges
                m = 0.32 * sstep(1.0, 0.0, t) ** 1.5
            if kind in ("pool", "dimpool"):  # light pool on the ground: radial, soft, dim; albedo close to concrete
                r = np.hypot((xx + 0.5) / n - 0.5, (yy + 0.5) / n - 0.5) * 2
                m = (0.16 if kind == "pool" else 0.055) * np.clip(1 - r, 0, 1) ** (2.2 if kind == "pool" else 1.4)
                emis[y0:y1, x0:x1] = _c(col) * m[..., None]
                albedo[y0:y1, x0:x1] = _c(np.array((0.085, 0.086, 0.089)))
                rough[y0:y1, x0:x1] = 0.85
                continue
            emis[y0:y1, x0:x1] = _c(col) * m[..., None]
            albedo[y0:y1, x0:x1] = _c(0.4 + 0.5 * col)
            rough[y0:y1, x0:x1] = 0.3
    emis = np.clip(emis, 0.0, 1.0)
    normal = height_to_normal_2d(blur(hgt, 0.8), 1.0 / NEON_PX_PER_M, 1.0)
    ao = np.ones((size, size))
    metal = np.zeros((size, size))
    return dict(albedo=albedo, rough=rough, metal=metal, ao=ao, normal=normal, emission=emis)


# =========================================================================================
# Images
# =========================================================================================
def _orm(ao, rough, metal):
    h, w = rough.shape
    return np.dstack([np.broadcast_to(np.clip(c, 0, 1), (h, w)) for c in (ao, rough, metal)])


def sheet_arrays(sheet):
    """(albedo sRGB, normal, ORM) arrays of a filled TrimSheet."""
    return linear_to_srgb(sheet.albedo), sheet.normal, _orm(sheet.ao, sheet.rough, sheet.metal)


def set_arrays(tex):
    """(albedo sRGB, normal, ORM, emission sRGB) arrays of a window / neon dict."""
    return (linear_to_srgb(tex["albedo"]), tex["normal"], _orm(tex["ao"], tex["rough"], tex["metal"]),
            linear_to_srgb(tex["emission"]))


def all_sets():
    """{material: {kind: array}} for every texture set (kinds albedo, normal, orm[, emission])."""
    out = {}
    conc = fill_concrete(concrete_sheet())
    a, n, o = sheet_arrays(conc)
    out[MAT_CONCRETE] = dict(albedo=a, normal=n, orm=o)
    del conc
    met = fill_metal(metal_sheet())
    a, n, o = sheet_arrays(met)
    out[MAT_METAL] = dict(albedo=a, normal=n, orm=o)
    del met
    a, n, o, e = set_arrays(window_tile())
    out[MAT_WINDOWS] = dict(albedo=a, normal=n, orm=o, emission=e)
    a, n, o, e = set_arrays(neon_atlas())
    out[MAT_NEON] = dict(albedo=a, normal=n, orm=o, emission=e)
    return out
