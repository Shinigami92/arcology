"""The five surface recipes (numpy, deterministic). Each takes (size, tile_m, seed) and
returns linear `albedo` (h, w, 3), `height` (m), `rough`, `metal`, `ao` (extra
occlusion multiplied with the cavity AO) and the cavity settings; build.py turns
height into the normal map and AO and writes the PNGs.

VR readability: fine detail (plank seams, fibers, stipple) lives in the height
and roughness; the albedo only carries medium and low frequencies at low contrast.
"""

import math

import numpy as np

from arcology_blender.surface import cells, contour_lines, oriented_noise, running_bond
from arcology_blender.trim import fbm, noise, smoothstep, warp


def _c(*rgb):
    return np.asarray(rgb, dtype=np.float64)[None, None, :]


def _srgb(hexstr):
    v = np.array([int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def _mix(a, b, t):
    t = np.asarray(t)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def _shift(field, du, dv):
    """Sample a periodic field at integer offsets per pixel (per-piece variation:
    every plank reads its own window of a shared field)."""
    h, w = field.shape
    rr, cc = np.mgrid[0:h, 0:w]
    return field[(rr + dv) % h, (cc + du) % w]


# --- vinyl plank -------------------------------------------------------------------------------
def vinyl_plank(size, tile_m, seed):
    """Oak-look luxury vinyl plank, mid warm grey-brown. Planks along U, random
    staggered end joints, every plank its own cut of grain and tone, micro-bevel
    on all four edges, satin finish with traffic polish and scuffs."""
    L = running_bond(size, tile_m, 0.18, 1.22, seed, min_shift_m=0.30, course_phase=0.5)
    px_m, n = L["px_m"], L["pieces"]
    ids, a, al = L["id"], L["across"], L["along"]
    cw, pl = L["course_m"], L["piece_m"]
    rng = np.random.default_rng(seed + 1)

    # per-plank parameters
    light = np.clip(rng.normal(0.0, 0.26, n), -1.0, 1.0)     # -1 darker/warmer .. +1 lighter/greyer
    warmth = rng.normal(0.0, 0.6, n)
    rift = rng.random(n) < 0.40                              # straight grain planks
    apex = np.where(rift, rng.uniform(-0.6, 0.6, n), rng.uniform(-0.05, cw + 0.05, n))
    radius = np.where(rift, rng.uniform(2.0, 6.0, n), 10 ** rng.uniform(math.log10(0.07), math.log10(0.55), n))
    tilt = rng.uniform(0.012, 0.06, n) * rng.choice([-1.0, 1.0], n)
    spacing = rng.uniform(0.0060, 0.0120, n)
    phase0 = rng.random(n)
    du = rng.integers(0, size, n)
    dv = rng.integers(0, size, n)
    sheen = rng.normal(0.0, 1.0, n)
    along_grad = rng.normal(0.0, 1.0, n)

    # shared fields, read per plank at its own offset
    wander = _shift(noise(size, size, 70.0, 10.0, seed + 2), du[ids], dv[ids])
    figure = _shift(noise(size, size, 80.0, 2.2, seed + 3), du[ids], dv[ids])
    cloud = _shift(fbm(size, size, 140.0, 35.0, 3, 0.5, seed + 4), du[ids], dv[ids])
    pores = _shift(noise(size, size, 9.0, 0.6, seed + 5), du[ids], dv[ids])
    streak = _shift(noise(size, size, 150.0, 2.0, seed + 8), du[ids], dv[ids])  # straight fine lines

    # flat-sawn cathedral rings: parabolic contours whose tips march along the plank
    d_ap = a - apex[ids]
    r_i, t_i, sp = radius[ids], tilt[ids], spacing[ids]
    phase = d_ap ** 2 / (2.0 * r_i) + t_i * al + 0.0045 * wander + phase0[ids] * sp
    cpp = np.sqrt((d_ap / r_i) ** 2 + t_i ** 2) * px_m / sp      # ring cycles per pixel
    fade = 1.0 - smoothstep(cpp, 0.09, 0.25)                     # band-limit: no moire
    g = 0.5 + 0.5 * np.cos(2.0 * math.pi * phase / sp)
    late = g ** 4
    late = late * fade + 0.273 * (1.0 - fade)                    # mean of g^4

    # tone per plank
    mid = _c(0.262, 0.204, 0.150)
    lite = _c(0.345, 0.296, 0.238)
    dark = _c(0.178, 0.124, 0.083)
    lp = light[ids]
    col = _mix(mid, lite, np.clip(lp, 0, 1))
    col = _mix(col, dark, np.clip(-lp, 0, 1))
    wm = warmth[ids]
    col = col * np.dstack([1 + 0.035 * wm, np.ones_like(wm), 1 - 0.05 * wm])
    lengthwise = 1 + 0.025 * along_grad[ids] * (al / pl - 0.5)
    col = col * (lengthwise * (1 + 0.035 * cloud + 0.045 * figure))[..., None]
    col = col * (1 - 0.11 * (late - 0.273) + 0.05 * streak)[..., None] * np.dstack(
        [np.ones_like(late), 1 - 0.02 * late, 1 - 0.06 * late])

    # pin knots on a few planks
    knot_on = rng.random(n) < 0.10
    ka, kc = rng.uniform(0.12, pl - 0.12, n), rng.uniform(0.035, cw - 0.035, n)
    kr = rng.uniform(0.0035, 0.008, n)
    kd = np.sqrt(((al - ka[ids]) / (1.7 * kr[ids])) ** 2 + ((a - kc[ids]) / kr[ids]) ** 2)
    knot = (1 - smoothstep(kd, 0.55, 1.3)) * knot_on[ids]
    halo = (1 - smoothstep(kd, 1.0, 3.2)) * knot_on[ids]
    col = col * (1 - 0.40 * knot - 0.06 * halo)[..., None] * np.dstack(
        [np.ones_like(knot), 1 - 0.08 * knot, 1 - 0.18 * knot])

    pore_m = smoothstep(pores, 1.1, 2.6) * (0.35 + 0.65 * late)
    col = col * (1 - 0.035 * pore_m)[..., None]

    # micro-bevel: long edges a little deeper and wider than the end joints
    bev_s = np.clip(1 - L["d_side"] / 0.0060, 0, 1) ** 2
    bev_e = np.clip(1 - L["d_end"] / 0.0045, 0, 1) ** 2
    bevel = np.maximum(bev_s, 0.8 * bev_e)
    height = -np.maximum(0.00080 * bev_s, 0.00055 * bev_e)
    height += 0.000028 * (late - 0.273) - 0.000014 * pore_m + 0.000035 * knot
    height += 0.00002 * figure + 0.000012 * streak                                     # embossed in register
    col = col * (1 - 0.10 * bevel)[..., None]

    # finish: satin, traffic polish, dull patches, scuffs
    rough = 0.47 + 0.018 * sheen[ids] + 0.03 * (late - 0.273) + 0.03 * pore_m + 0.03 * knot
    wear = fbm(size, size, 230.0, 230.0, 4, 0.5, seed + 6)
    rough -= 0.04 * smoothstep(wear, 0.5, 1.8)
    rough += 0.035 * smoothstep(-wear, 0.7, 2.0)
    scuff_zone = smoothstep(fbm(size, size, 160.0, 160.0, 3, 0.5, seed + 7), -0.2, 0.9)
    scuffs = np.zeros((size, size))
    for k, ang in enumerate((8.0, 31.0, -17.0, 64.0, -48.0, 102.0)):
        s = oriented_noise(size, size, 10.0, 0.9, ang, seed + 20 + k)
        scuffs = np.maximum(scuffs, smoothstep(s, 2.7, 3.5))
    scuffs *= scuff_zone
    rough += 0.10 * scuffs + 0.12 * bevel
    col = col * (1 + 0.04 * scuffs)[..., None]
    return dict(albedo=col, height=height, rough=np.clip(rough, 0.36, 0.66), metal=0.0,
                ao=np.ones((size, size)), cavity=(2.0, 0.0005, 0.45), px_m=px_m,
                info=f"{L['courses']} courses x {L['per_course']} planks = {n} unique, "
                     f"plank {L['piece_m']:.3f} x {L['course_m']:.4f} m")


# --- carpet ------------------------------------------------------------------------------------
def carpet(size, tile_m, seed):
    """Cut-pile wall-to-wall carpet, muted warm taupe/grey: fine tuft and fiber
    height, faint pile lean in four directions blended by a slow field, soft
    tone mottling and pile-direction shading."""
    px_m = tile_m / size
    f1, _, cid, val = cells(size, size, 2.1, seed + 1, jitter=0.9)
    tuft = np.clip(1 - (f1 / 1.45) ** 2, 0, 1)
    tip = 0.65 + 0.35 * val
    fine = noise(size, size, 0.75, 0.75, seed + 2)
    clump = noise(size, size, 3.0, 3.0, seed + 3)

    theta = fbm(size, size, 380.0, 380.0, 3, 0.5, seed + 4) * 1.4      # pile lean (radians)
    lean = np.zeros((size, size))
    for k, ang in enumerate((0.0, 45.0, 90.0, 135.0)):
        wgt = np.cos(theta - math.radians(ang)) ** 2
        wgt = wgt ** 4
        lean += wgt * oriented_noise(size, size, 3.2, 0.8, ang, seed + 10 + k)
    lean /= lean.std() + 1e-9

    height = (0.00030 * tuft * tip + 0.00012 * fine + 0.00016 * clump + 0.00010 * lean)

    base = _c(0.232, 0.203, 0.176)
    mottle = fbm(size, size, 170.0, 170.0, 4, 0.55, seed + 5)
    pile = np.sin(2.0 * theta) * 0.7 + 0.3 * fbm(size, size, 500.0, 300.0, 2, 0.5, seed + 6)
    track = noise(size, size, 520.0, 28.0, seed + 7)
    heather = (val - 0.5)
    odd = (val > 0.93).astype(np.float64)                                # a few lighter fibers
    shade = (1 + 0.040 * mottle + 0.060 * pile + 0.030 * track + 0.05 * heather
             + 0.05 * odd + 0.03 * fine) * (0.9 + 0.1 * tuft * tip)
    albedo = base * shade[..., None] * np.dstack(
        [1 + 0.012 * mottle, np.ones_like(mottle), 1 - 0.015 * mottle])
    rough = np.clip(0.95 + 0.02 * fine - 0.015 * pile - 0.01 * tuft, 0.9, 1.0)
    return dict(albedo=albedo, height=height, rough=rough, metal=0.0,
                ao=np.ones((size, size)), cavity=(1.6, 0.00035, 0.35), px_m=px_m)


# --- polished concrete ------------------------------------------------------------------------
def polished_concrete(size, tile_m, seed):
    """Sealed, ground and polished concrete: cloudy paste, exposed fine aggregate
    (salt and pepper) and a few larger stones, pinholes, faint hairline cracks,
    slight floor undulation; low, varying roughness that catches reflections."""
    px_m = tile_m / size
    paste = _c(0.168, 0.159, 0.146)
    cloud = fbm(size, size, 420.0, 420.0, 5, 0.55, seed + 1)
    cloud2 = fbm(size, size, 90.0, 90.0, 3, 0.5, seed + 2)
    hue = fbm(size, size, 650.0, 650.0, 3, 0.5, seed + 3)
    swirl = np.zeros((size, size))
    for k, ang in enumerate((15.0, 70.0, 130.0)):
        swirl += oriented_noise(size, size, 160.0, 40.0, ang, seed + 30 + k)
    swirl /= 3.0
    tone = 1 + 0.10 * cloud + 0.04 * cloud2 + 0.03 * swirl
    albedo = paste * tone[..., None] * np.dstack([1 + 0.025 * hue, np.ones_like(hue), 1 - 0.03 * hue])

    def spots(cell_px, r_lo, r_hi, presence, s, irregular=0.0):
        f1, _, cid, val = cells(size, size, cell_px, s)
        m = int(cid.max()) + 1
        r = np.random.default_rng(s + 1)
        rad = r.uniform(r_lo, r_hi, m)
        on = r.random(m) < presence
        kind = r.random(m)
        tint = r.random(m)
        rr = rad[cid]
        if irregular:
            rr = rr * (1 + irregular * noise(size, size, max(r_hi * 0.6, 1.0), None, s + 2))
        spot = (1 - smoothstep(f1, rr - 0.55, rr + 0.55)) * on[cid]
        return spot, kind[cid], tint[cid], val

    # fine aggregate: sand-sized flecks, light quartz, dark basalt, warm tan
    sand, kind, tint, _ = spots(3.6, 0.35, 1.5, 0.55, seed + 10)
    light_c = paste * 1.55 * _c(1.02, 1.0, 0.95)
    dark_c = paste * 0.55
    tan_c = paste * _c(1.30, 1.12, 0.90)
    fleck = np.where((kind < 0.45)[..., None], light_c, np.where((kind < 0.8)[..., None], dark_c, tan_c))
    fleck = fleck * (0.85 + 0.3 * tint)[..., None]
    albedo = _mix(albedo, fleck, 0.55 * sand)

    # coarse aggregate: ground-through stones, 5..16 mm, angular (Voronoi polygons
    # clipped by a radius, edges roughened by sampling the cells at jittered offsets)
    f1, f2, cid, _ = cells(size, size, 20.0, seed + 20, jitter=0.95)
    jag_u = np.round(1.3 * noise(size, size, 1.2, 1.2, seed + 22)).astype(np.int64)
    jag_v = np.round(1.3 * noise(size, size, 1.2, 1.2, seed + 23)).astype(np.int64)
    f1, f2, cid = (_shift(f, jag_u, jag_v) for f in (f1, f2, cid))
    m = int(cid.max()) + 1
    sr = np.random.default_rng(seed + 24)
    rad, on = sr.uniform(2.5, 7.5, m), sr.random(m) < 0.16
    skind, stint = sr.random(m)[cid], sr.random(m)[cid]
    stone = (smoothstep(f2 - f1, 1.5, 3.0) * (1 - smoothstep(f1, rad[cid] - 0.7, rad[cid] + 0.7))) * on[cid]
    inner = noise(size, size, 1.6, 1.6, seed + 21)
    stone_c = np.where((skind < 0.5)[..., None], paste * 1.35 * _c(1.0, 0.99, 0.96),
                       np.where((skind < 0.8)[..., None], paste * 0.62 * _c(0.98, 1.0, 1.04),
                                paste * _c(1.22, 1.08, 0.92)))
    stone_c = stone_c * (0.88 + 0.24 * stint + 0.05 * inner)[..., None]
    albedo = _mix(albedo, stone_c, 0.45 * stone)

    # pinholes (air voids)
    pin, _, _, _ = spots(44.0, 0.5, 1.4, 0.35, seed + 40)
    albedo = albedo * (1 - 0.45 * pin)[..., None]

    # hairline cracks: zero contours of a warped field, kept in a few places
    crack = np.zeros((size, size))
    for k, (sz, cover) in enumerate(((300.0, 1.25), (180.0, 1.6))):
        f = noise(size, size, sz, sz, seed + 50 + k)
        f = warp(f, 30.0 * fbm(size, size, 60.0, 60.0, 3, 0.5, seed + 52 + k),
                 30.0 * fbm(size, size, 60.0, 60.0, 3, 0.5, seed + 54 + k))
        mask = smoothstep(fbm(size, size, 420.0, 420.0, 3, 0.5, seed + 56 + k), cover, cover + 0.5)
        crack = np.maximum(crack, contour_lines(f, 0.85) * mask)
    albedo = albedo * (1 - 0.22 * crack)[..., None]

    height = (0.00025 * fbm(size, size, 330.0, 330.0, 3, 0.5, seed + 60)
              + 0.000004 * oriented_noise(size, size, 220.0, 2.0, 37.0, seed + 61)
              - 0.00030 * pin - 0.00010 * crack - 0.000015 * sand)

    wax = oriented_noise(size, size, 260.0, 60.0, -25.0, seed + 70)
    rough = (0.29 + 0.035 * fbm(size, size, 200.0, 200.0, 4, 0.5, seed + 71) + 0.02 * cloud2
             + 0.02 * wax - 0.02 * stone - 0.01 * sand + 0.15 * pin + 0.08 * crack)
    return dict(albedo=albedo, height=height, rough=np.clip(rough, 0.18, 0.45), metal=0.0,
                ao=np.ones((size, size)), cavity=(2.0, 0.0002, 0.5), px_m=px_m)


# --- plaster -----------------------------------------------------------------------------------
def _plaster(size, tile_m, seed, base, tone_amt, stipple_m, stipple_px, trowel_m, rough0, rough_var, stroke_m):
    px_m = tile_m / size
    tone = fbm(size, size, 0.6 / px_m, 0.6 / px_m, 4, 0.5, seed + 1)
    tone2 = fbm(size, size, 0.15 / px_m, 0.15 / px_m, 3, 0.5, seed + 2)
    lanes = oriented_noise(size, size, 0.55 / px_m, 0.12 / px_m, 90.0, seed + 3)
    stip = noise(size, size, stipple_px, stipple_px, seed + 4) + 0.6 * noise(size, size, 2 * stipple_px, None, seed + 5)
    stip /= stip.std()
    density = np.clip(1 + 0.35 * lanes, 0.3, 2.0)
    trowel = fbm(size, size, 0.32 / px_m, 0.32 / px_m, 3, 0.5, seed + 6)
    strokes = np.zeros((size, size))
    patch = smoothstep(fbm(size, size, 0.8 / px_m, 0.8 / px_m, 2, 0.5, seed + 7), -0.3, 1.0)
    for k, ang in enumerate((28.0, -35.0, 62.0, -70.0)):
        strokes += oriented_noise(size, size, 0.22 / px_m, 0.045 / px_m, ang, seed + 10 + k)
    strokes = strokes / 2.0 * patch
    height = stipple_m * stip * density + trowel_m * trowel + stroke_m * strokes
    peaks = smoothstep(stip * density, 0.6, 2.0)
    albedo = base * (1 + tone_amt * tone + 0.4 * tone_amt * tone2 - 0.004 * peaks)[..., None]
    rough = rough0 + rough_var * fbm(size, size, 0.5 / px_m, 0.5 / px_m, 3, 0.5, seed + 8) \
        - 0.025 * peaks + 0.01 * lanes
    return albedo, height, rough, px_m


def wall_plaster(size, tile_m, seed):
    """Smooth skim-coat plaster under matte/eggshell emulsion, warm off-white
    #D8D2C4: roller stipple in lanes, faint trowel undulation and strokes,
    gentle low-frequency tone. No height-dependent wear (tiles vertically)."""
    base = _srgb("D8D2C4")[None, None, :] * 0.98
    albedo, height, rough, px_m = _plaster(size, tile_m, seed, base, tone_amt=0.016, stipple_m=0.000045,
                                           stipple_px=1.4, trowel_m=0.00045, rough0=0.80, rough_var=0.018,
                                           stroke_m=0.00012)
    return dict(albedo=albedo, height=height, rough=np.clip(rough, 0.74, 0.86), metal=0.0,
                ao=np.ones((size, size)), cavity=(1.5, 0.00025, 0.12), px_m=px_m)


def ceiling_plaster(size, tile_m, seed):
    """Flat matte white-ish paint on plaster, a little cooler and lighter than the
    walls and even subtler."""
    base = _c(0.690, 0.680, 0.646)
    albedo, height, rough, px_m = _plaster(size, tile_m, seed, base, tone_amt=0.010, stipple_m=0.000030,
                                           stipple_px=0.9, trowel_m=0.00030, rough0=0.90, rough_var=0.012,
                                           stroke_m=0.00006)
    return dict(albedo=albedo, height=height, rough=np.clip(rough, 0.86, 0.94), metal=0.0,
                ao=np.ones((size, size)), cavity=(1.2, 0.0003, 0.08), px_m=px_m)


RECIPES = {
    "vinyl_plank": vinyl_plank,
    "carpet": carpet,
    "polished_concrete": polished_concrete,
    "wall_plaster": wall_plaster,
    "ceiling_plaster": ceiling_plaster,
}
