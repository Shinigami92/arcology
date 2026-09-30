"""The window kit's shared finishes: one trim sheet (bands tiling along U) and
the shade fabric. Deterministic numpy textures (arcology_blender.trim), so
every spec and every rebuild gets the same pixels.

Bands (the band a face uses is picked in build.py from its role and normal):
  metal        graphite / dark-bronze anodized aluminium, satin, brushed along U
  metal_dust   the same on upward faces (bottom rails), a little dust
  metal_ext    the same weathered (exterior faces)
  edge         polished chamfers (V stretched across the chamfer)
  reveal       bead-blasted dark bronze reveal liner and head cassette
  stone_top    honed black basalt/marble with faint low-frequency veins, faint dust
  stone        the same without dust (nose, underside)
  flashing     powder-coated exterior sill flashing, grime streaks growing along V
  rubber       black EPDM gaskets
  black_matte  slot pockets, the channel floor
  black_gloss  black glass (sensor strip, panel face)
  threshold    brushed dark metal threshold with foot polish
  handle       satin PVD dark bronze (lever, button caps)
"""

import numpy as np

from arcology_blender.trim import TrimSheet, fbm, noise, smoothstep, warp

BANDS = (  # name, rows (512 px/m: 1 row = 1.95 mm)
    ("metal", 80), ("metal_dust", 80), ("metal_ext", 80), ("edge", 16), ("handle", 48),
    ("threshold", 72), ("reveal", 88), ("stone_top", 80), ("stone", 64), ("flashing", 80),
    ("rubber", 16), ("black_matte", 24), ("black_gloss", 40),
)

# linear colors
FRAME = (0.080, 0.070, 0.060)       # graphite / dark bronze anodized
FRAME_EXT = (0.078, 0.073, 0.068)
EDGE = (0.26, 0.23, 0.195)
REVEAL = (0.130, 0.104, 0.078)
STONE = (0.0175, 0.0175, 0.0185)
VEIN = (0.105, 0.100, 0.096)
DUST = (0.20, 0.19, 0.175)
FLASH = (0.030, 0.031, 0.033)
GRIME = (0.011, 0.010, 0.008)
DEPOSIT = (0.085, 0.078, 0.066)     # dried dirt run-off
THRESH = (0.150, 0.132, 0.112)
HANDLE = (0.185, 0.145, 0.105)


def _c(c):
    return np.asarray(c, dtype=np.float64)[None, None, :]


def _mix(a, b, t):
    t = np.asarray(t)[..., None]
    return a * (1 - t) + b * t


def _brushed(h, w, seed, base, rough, streak=0.035, tint=0.05, depth=1.2e-4):
    s = noise(h, w, 140.0, 0.7, seed)
    s2 = noise(h, w, 400.0, 2.5, seed + 1)
    blot = fbm(h, w, 220.0, 120.0, 3, 0.5, seed + 2)
    albedo = _c(base) * (1 + tint * (0.6 * s + 0.4 * s2) + 0.05 * blot)[..., None]
    r = rough + streak * (0.7 * s + 0.3 * s2) + 0.025 * blot
    return albedo, r, depth * (0.8 * s + 0.2 * s2)


def metal(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, FRAME, 0.34)
    return dict(albedo=a, rough=r, metal=1.0, height=hg)


def dust_layer(h, w, seed, amount):
    m = smoothstep(fbm(h, w, 45.0, 45.0, 4, 0.55, seed), 0.2, 2.2) * amount
    m = m + np.clip(noise(h, w, 0.7, 0.7, seed + 7), 0, None) * 0.25 * amount
    return np.clip(m, 0, 1)


def metal_dust(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, FRAME, 0.34)
    m = dust_layer(h, w, seed + 11, 0.13)
    return dict(albedo=_mix(a, _c(DUST), m), rough=r + (0.85 - r) * m, metal=1.0 - m, height=hg)


def metal_ext(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, FRAME_EXT, 0.44, streak=0.03, tint=0.04)
    blot = smoothstep(fbm(h, w, 90.0, 60.0, 4, 0.55, seed + 3), -0.3, 1.8)
    a = _mix(a, _c(DEPOSIT), blot * 0.22)  # weathering: a dull film of city dust
    return dict(albedo=a, rough=r + 0.12 * blot, metal=1.0 - 0.3 * blot, height=hg)


def edge(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, EDGE, 0.22, streak=0.03, tint=0.06, depth=6e-5)
    return dict(albedo=a, rough=r, metal=1.0, height=hg)


def handle(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, HANDLE, 0.24, streak=0.03, tint=0.04, depth=6e-5)
    return dict(albedo=a, rough=r, metal=1.0, height=hg)


def threshold(h, w, px, v, seed):
    a, r, hg = _brushed(h, w, seed, THRESH, 0.30, streak=0.04, tint=0.05)
    rub = smoothstep(fbm(h, w, 60.0, 25.0, 3, 0.5, seed + 4), 0.3, 1.8)
    scr = np.clip(noise(h, w, 35.0, 0.45, seed + 5) - 2.2, 0, None)
    a = a * (1 + 0.25 * rub + 0.8 * scr)[..., None]
    return dict(albedo=a, rough=r - 0.10 * rub + 0.1 * scr, metal=1.0, height=hg - 2e-5 * scr)


def reveal(h, w, px, v, seed):
    g = noise(h, w, 0.7, 0.7, seed)
    blot = fbm(h, w, 160.0, 160.0, 3, 0.5, seed + 1)
    a = _c(REVEAL) * (1 + 0.04 * g + 0.05 * blot)[..., None]
    return dict(albedo=a, rough=0.40 + 0.03 * g + 0.03 * blot, metal=1.0, height=3.5e-5 * g)


def _stone(h, w, seed):
    mottle = fbm(h, w, 40.0, 40.0, 4, 0.55, seed)
    speck = noise(h, w, 0.6, 0.6, seed + 1)
    # veins: zero crossings of noise stretched along U (they run along the slab), gently warped
    n1 = fbm(h, w, 300.0, 34.0, 3, 0.45, seed + 2)
    n2 = fbm(h, w, 160.0, 26.0, 3, 0.45, seed + 3)
    du = fbm(h, w, 120.0, 60.0, 2, 0.5, seed + 4) * 9.0
    dv = fbm(h, w, 120.0, 60.0, 2, 0.5, seed + 5) * 3.0
    v1 = 1 - smoothstep(np.abs(warp(n1, du, dv)), 0.0, 0.07)
    v2 = 1 - smoothstep(np.abs(warp(n2, dv, du)), 0.0, 0.035)
    fade = smoothstep(fbm(h, w, 200.0, 200.0, 2, 0.5, seed + 6), -1.0, 1.0)
    vein = np.clip(0.45 * v1 * (0.4 + 0.6 * fade) + 0.22 * v2 * fade, 0, 1)
    a = _c(STONE) * (1 + 0.10 * mottle + 0.07 * speck)[..., None]
    a = _mix(a, _c(VEIN), vein)
    r = 0.30 + 0.025 * mottle + 0.07 * vein + 0.02 * speck
    return a, r, 8e-6 * speck - 1.5e-5 * vein


def stone(h, w, px, v, seed):
    a, r, hg = _stone(h, w, seed)
    return dict(albedo=a, rough=r, metal=0.0, height=hg)


def stone_top(h, w, px, v, seed):
    a, r, hg = _stone(h, w, seed)
    m = dust_layer(h, w, seed + 12, 0.16)
    return dict(albedo=_mix(a, _c(DUST), m), rough=r + (0.8 - r) * m, metal=0.0, height=hg)


def flashing(h, w, px, v, seed):
    base = fbm(h, w, 70.0, 70.0, 3, 0.5, seed)
    a = _c(FLASH) * (1 + 0.06 * base)[..., None]
    streak = noise(h, w, 2.5, 45.0, seed + 1) + 0.5 * noise(h, w, 8.0, 90.0, seed + 2)
    grow = smoothstep(v, 0.01, 0.10)  # dirtier toward the drip and down the front
    s = smoothstep(streak, -0.2, 1.6) * (0.25 + 0.75 * grow)
    dirt = smoothstep(fbm(h, w, 40.0, 40.0, 4, 0.55, seed + 3), 0.0, 2.0) * 0.4
    light = np.clip(noise(h, w, 2.0, 30.0, seed + 4) - 2.0, 0, None) * grow
    peel = noise(h, w, 1.6, 1.6, seed + 5)  # powder-coat orange peel
    # on dark powder coat, dried run-off shows as pale deposits; wet-looking dark streaks at the drip
    a = _mix(a, _c(DEPOSIT), np.clip(0.6 * s + 0.5 * dirt, 0, 0.7))
    a = _mix(a, _c(GRIME), np.clip(0.5 * s * grow, 0, 0.4))
    a = _mix(a, _c((0.16, 0.155, 0.145)), np.clip(light * 0.5, 0, 0.18))
    return dict(albedo=a, rough=0.55 + 0.2 * s + 0.1 * dirt, metal=0.0, height=1.8e-5 * peel)


def rubber(h, w, px, v, seed):
    g = noise(h, w, 1.2, 1.2, seed)
    return dict(albedo=_c((0.011, 0.011, 0.012)) * (1 + 0.1 * g)[..., None], rough=0.72 + 0.04 * g,
                metal=0.0, height=3e-6 * g)


def black_matte(h, w, px, v, seed):
    return dict(albedo=np.broadcast_to(_c((0.006, 0.006, 0.006)), (h, w, 3)), rough=0.92, metal=0.0)


def black_gloss(h, w, px, v, seed):
    sm = fbm(h, w, 30.0, 30.0, 3, 0.5, seed)
    return dict(albedo=np.broadcast_to(_c((0.004, 0.004, 0.0045)), (h, w, 3)).copy(),
                rough=0.06 + 0.03 * smoothstep(sm, 0.5, 2.0), metal=0.0)


RECIPES = dict(metal=metal, metal_dust=metal_dust, metal_ext=metal_ext, edge=edge, handle=handle,
               threshold=threshold, reveal=reveal, stone_top=stone_top, stone=stone, flashing=flashing,
               rubber=rubber, black_matte=black_matte, black_gloss=black_gloss)


def layout(size, px_per_m):
    """The sheet's band layout only (build.py needs it for the UVs)."""
    sheet = TrimSheet(size, size, px_per_m)
    for name, rows in BANDS:
        sheet.add_band(name, rows)
    return sheet


def generate(size, px_per_m):
    """The full sheet with pixels (bake.py)."""
    sheet = layout(size, px_per_m)
    for k, (name, _) in enumerate(BANDS):
        sheet.fill(name, RECIPES[name], seed=1000 + 37 * k)
    return sheet


# --- shade fabric: tileable 1 m x 1 m blackout cloth -----------------------------------------
def shade_fabric(size, seed=77):
    """(albedo linear (h, w, 3), normal (h, w, 3) 0..1) for a 1 m tile: dark
    charcoal, faint weft slubs, a very low-contrast plain weave, low-frequency
    mottling (no crisp fine grid: it would shimmer in VR)."""
    from arcology_blender.trim import height_to_normal
    h = w = size
    px_m = 1.0 / size
    mottle = fbm(h, w, 140.0, 140.0, 3, 0.5, seed)
    slub = noise(h, w, 38.0, 1.3, seed + 1)
    slub_m = smoothstep(slub, 1.0, 2.6)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    jx = noise(h, w, 6.0, 6.0, seed + 2) * 0.6
    jy = noise(h, w, 6.0, 6.0, seed + 3) * 0.6
    period = 8.0  # two threads of 4 mm; 1024 / 8 tiles exactly
    weave = np.cos(2 * np.pi * (xx + jx) / period) * np.cos(2 * np.pi * (yy + jy) / period)
    base = np.asarray((0.021, 0.022, 0.024))[None, None, :]
    albedo = base * (1 + 0.05 * mottle + 0.07 * slub_m + 0.015 * weave)[..., None]
    height = 6e-5 * weave + 1.2e-4 * slub_m + 1.5e-4 * mottle
    normal = height_to_normal(height, px_m, 1.0)
    return albedo, normal
