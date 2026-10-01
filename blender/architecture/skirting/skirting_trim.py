"""The skirting trim sheet: painted MDF in bands that tile along U (numpy, deterministic).

Layout (bottom-up): `paint` (face, round-over and top of the board; V = profile arc from
the floor), `paint_rub` (the same paint near outside corners, lightly rubbed),
`paint_arris` (the eased arris of an outside corner, rubbed most), `paint_plain` (back and
bottom, hidden). U period = one 2.4 m board; the board joint (a hairline butt joint, in the
normal and roughness only) is at U = 0.

The three paint bands share one field (same size, same seed), so faces can switch band at
a ring without a visible step: only the rub term differs. Wear is low-contrast and
medium-scale (VR shimmer): shoe scuffs and vacuum knocks low on the face, a faint dust line
on the top, the floor contact line, rubbed paint on outside corners.
"""

import math

import numpy as np

from skirting_common import (
    BAND_ROWS, BANDS, BOARD, DUST, FRAME_PAINT, PAINT_ROUGH, PLAIN, PLAIN_ROWS, PRIMER, RUBBER, THICKNESS,
    TOP_R, TRIM_H, TRIM_PAD, TRIM_PX_PER_M, TRIM_W,
)
from arcology_blender.trim import TrimSheet, noise, smoothstep

SEED = 3607
RUB_LEVEL = {"paint": 0.0, "paint_rub": 0.45, "paint_arris": 1.0}


def layout():
    """The sheet with its bands (no pixels yet): build.py needs it for the UVs."""
    sheet = TrimSheet(TRIM_W, TRIM_H, TRIM_PX_PER_M, pad=TRIM_PAD)
    for name in BANDS:
        sheet.add_band(name, BAND_ROWS)
    sheet.add_band(PLAIN, PLAIN_ROWS)
    return sheet


def _blobs(h, w, px_m, v_m, rng, count, u_len, v_len, v_range):
    """Sum of soft elliptical blobs, periodic along U: (mask in 0..1, centers)."""
    u = np.arange(w)[None, :] * px_m
    out = np.zeros((h, w))
    for _ in range(count):
        uc = rng.uniform(0.0, BOARD)
        vc = rng.uniform(*v_range)
        lu = rng.uniform(*u_len)
        lv = rng.uniform(*v_len)
        du = (u - uc + BOARD / 2) % BOARD - BOARD / 2
        d2 = (du / (lu / 2)) ** 2 + ((v_m - vc) / (lv / 2)) ** 2
        out += rng.uniform(0.5, 1.0) * np.exp(-2.2 * d2)
    return np.clip(out, 0.0, 1.0)


def _paint(h, w, px_m, v_m, seed, height, rub):
    """Painted MDF: one field for every paint band; `rub` 0..1 adds corner wear."""
    rng = np.random.default_rng(seed)
    u = np.arange(w)[None, :] * px_m
    top_v = (height - TOP_R) + math.pi / 2 * TOP_R          # start of the flat top
    end_v = top_v + (THICKNESS - TOP_R)                     # back edge of the top

    # Base paint: barely visible tone and sheen variation, roller lines along U
    tone = noise(h, w, 0.30 / px_m, 0.03 / px_m, seed + 1)
    sheen = noise(h, w, 0.12 / px_m, 0.12 / px_m, seed + 2)
    roller = noise(h, w, 0.40 / px_m, 0.008 / px_m, seed + 3)
    albedo = np.ones((h, w, 3)) * np.array(FRAME_PAINT) * (1.0 + 0.012 * tone)[..., None]
    rough = PAINT_ROUGH + 0.015 * sheen + 0.010 * roller
    hgt = np.zeros((h, w))

    # Floor contact line and low grime (kick zone)
    low = np.exp(-np.clip(v_m, 0.0, None) / 0.004) * (0.75 + 0.25 * tone)
    albedo *= (1.0 - 0.06 * low)[..., None]
    kick = smoothstep(0.035 - v_m, 0.0, 0.03) * np.clip(0.5 + 0.5 * noise(h, w, 0.20 / px_m, 0.02 / px_m, seed + 4), 0, 1)
    albedo *= (1.0 - 0.035 * kick)[..., None]
    rough = rough + 0.02 * kick

    # Shoe scuffs: soft horizontal rubber smears on the lower face
    scuff = _blobs(h, w, px_m, v_m, rng, 14, (0.05, 0.16), (0.005, 0.016), (0.006, 0.034))
    streak = np.clip(0.55 + 0.45 * noise(h, w, 0.03 / px_m, 0.002 / px_m, seed + 5), 0.0, 1.0)
    scuff = scuff * streak * (v_m < top_v - 0.01)
    albedo = albedo + (np.array(RUBBER) - albedo) * (0.30 * scuff)[..., None]
    rough = rough + 0.05 * scuff

    # Vacuum knocks: small dents with the paint crushed a little lighter, on the low face and
    # on the round-over (where the vacuum head bumps the top edge)
    knocks = np.zeros((h, w))
    dent = np.zeros((h, w))
    for v_range, count in (((0.004, 0.022), 5), ((top_v - 0.004, top_v + 0.002), 4)):
        for _ in range(count):
            uc, vc = rng.uniform(0.0, BOARD), rng.uniform(*v_range)
            r = rng.uniform(0.0025, 0.0045)
            du = (u - uc + BOARD / 2) % BOARD - BOARD / 2
            d2 = (du ** 2 + (v_m - vc) ** 2) / r ** 2
            g = np.exp(-d2)
            dent += rng.uniform(0.6, 1.0) * g
            knocks += smoothstep(1.0 - d2, 0.2, 0.8) * rng.uniform(0.4, 1.0)
    knocks = np.clip(knocks, 0.0, 1.0)
    albedo = albedo + (np.array(PRIMER) - albedo) * (0.20 * knocks)[..., None]
    rough = rough + 0.06 * knocks
    hgt = hgt - 0.00012 * np.clip(dent, 0.0, 1.0)

    # Dust on the top: a faint line, a little more against the wall
    dust = smoothstep(v_m, top_v - 0.003, top_v + 0.0015) * (0.75 + 0.25 * noise(h, w, 0.05 / px_m, 0.01 / px_m, seed + 6))
    dust = dust + 0.6 * smoothstep(v_m, end_v - 0.003, end_v)
    dust = np.clip(dust, 0.0, 1.0)
    albedo = albedo + (np.array(DUST) - albedo) * (0.10 * dust)[..., None]
    rough = rough + 0.10 * dust

    # Ambient occlusion: the floor contact and the top's corner against the wall
    ao = 1.0 - 0.14 * np.exp(-np.clip(v_m, 0.0, None) / 0.003) - 0.10 * smoothstep(v_m, end_v - 0.004, end_v)

    # Board joint at U = 0: a hairline butt joint (eased board ends), normal and roughness only
    du = (u + BOARD / 2) % BOARD - BOARD / 2
    joint = np.exp(-(du / 0.0016) ** 2)
    hgt = hgt - 0.00050 * joint
    rough = rough + 0.12 * joint

    # Outside-corner rub: burnished (glossier) and a few light chips, more low and at the top
    if rub > 0:
        where = 0.6 + 0.4 * smoothstep(0.03 - v_m, 0.0, 0.025) + 0.3 * smoothstep(v_m, top_v - 0.01, top_v)
        burnish = np.clip(0.5 + 0.5 * noise(h, w, 0.012 / px_m, 0.012 / px_m, seed + 7), 0.0, 1.0) * where
        chips = smoothstep(noise(h, w, 0.004 / px_m, 0.006 / px_m, seed + 8), 0.9, 1.8) * where
        albedo = albedo + (np.array(PRIMER) - albedo) * (rub * 0.16 * chips)[..., None]
        albedo = albedo * (1.0 - rub * 0.03 * burnish)[..., None]  # a little hand and shoe grime
        rough = rough - rub * 0.07 * burnish + rub * 0.04 * chips
    return {"albedo": np.clip(albedo, 0, 1), "rough": np.clip(rough, 0.05, 1.0), "metal": 0.0,
            "height": hgt, "ao": np.clip(ao, 0, 1), "normal_strength": 1.0}


def _plain(h, w, px_m, v_m, seed):
    albedo = np.ones((h, w, 3)) * np.array(FRAME_PAINT) * 0.9
    return {"albedo": albedo, "rough": PAINT_ROUGH + 0.06, "metal": 0.0, "ao": 0.8}


def generate(height):
    """The filled sheet (profile height from the run file)."""
    sheet = layout()
    for name in BANDS:
        sheet.fill(name, lambda h, w, px_m, v_m, seed, r=RUB_LEVEL[name]: _paint(h, w, px_m, v_m, seed, height, r),
                   seed=SEED)
    sheet.fill(PLAIN, _plain, seed=SEED)
    return sheet
