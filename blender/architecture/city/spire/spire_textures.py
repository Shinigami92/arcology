"""Tiling texture sets for the spires (numpy, deterministic, periodic in U and V).

Arrays are (rows, cols) = (V, U), row 0 at the bottom (world z grows with the
row), linear colors. Each set returns a dict with albedo (h, w, 3), normal
(h, w, 3, 0..1), ao, rough, metal (h, w) and optionally emission (h, w, 3).

Glass: one tile = 16 floors x 32 bays (64 x 64 m). Slab tops at z = 4k; a
0.9 m spandrel covers each slab (vision glass 0.30..3.40 m above the slab).
The emission map holds the offices: per floor a state (dark, fully lit, or
mixed runs of 2-7 bays), about 30 % of the cells lit, mostly cool white
(8000-10000 K), a few warm; ceiling glow, desk-height clutter, some blinds,
a few monitors left on in dark offices. Everything is mipmapped texture
detail: no shader logic, so it can't shimmer more than its mip level.
"""

import math

import numpy as np

from arcology_blender import surface, trim

# Colors (linear)
COOL_WHITE = np.array([0.80, 0.90, 1.00])     # ~9000 K
COOL_WHITE_2 = np.array([0.86, 0.93, 1.00])   # ~8000 K
WARM_WHITE = np.array([1.00, 0.72, 0.45])     # ~3300 K
CYAN = np.array([0.0015, 0.69, 0.80])         # #05D9E8
MAGENTA = np.array([1.0, 0.023, 0.15])        # #FF2A6D
ULTRAVIOLET = np.array([0.20, 0.028, 1.0])    # #7B2FFF
AMBER = np.array([1.0, 0.43, 0.0])            # #FFB000
RED = np.array([1.0, 0.025, 0.012])
RUST = np.array([0.195, 0.047, 0.012])        # #7A3E1D


def _grid(size, tile):
    px = tile / size
    c = (np.arange(size) + 0.5) * px
    return px, c[:, None] * np.ones((1, size)), np.ones((size, 1)) * c[None, :]


def _aa_inside(d, px):
    """1 inside (d > 0), 0 outside, antialiased over one pixel (d in meters)."""
    return np.clip(d / px + 0.5, 0.0, 1.0)


def _cell_lookup(table, fi, bi):
    return table[fi, bi]


# --- glass -------------------------------------------------------------------------
VISION = (0.30, 3.40)   # vision glass above the slab top (m); spandrel elsewhere
MULLION_HALF = 0.055    # vertical mullion cap half width
TRANSOM_HALF = 0.045


def office_cells(nf, nb, seed, lit_target=0.30):
    """Per cell (floor, bay): intensity (0 = dark), color (3), blind fraction, monitor flag."""
    rng = np.random.default_rng(seed)
    inten = np.zeros((nf, nb))
    color = np.zeros((nf, nb, 3))
    blind = np.zeros((nf, nb))
    monitor = np.zeros((nf, nb))
    for f in range(nf):
        state = rng.random()
        dim_floor = False
        if state < 0.15:          # dark floor (vacant or after hours)
            p_run = 0.03
        elif state < 0.27:        # trading floor: almost all lit
            p_run = 0.93
        elif state < 0.35:        # cleaning crew / night lighting: everything on, dim
            p_run, dim_floor = 1.0, True
        else:
            p_run = lit_target * 0.95
        floor_level = rng.uniform(0.75, 1.0)
        b = 0
        while b < nb:
            run = int(rng.integers(3, 13))
            if rng.random() < p_run:
                warm = rng.random() < 0.13
                base = WARM_WHITE if warm else (COOL_WHITE if rng.random() < 0.6 else COOL_WHITE_2)
                level = (rng.uniform(0.18, 0.32) if dim_floor else rng.uniform(0.40, 0.95)) * floor_level
                tint = base * (1.0 + rng.uniform(-0.04, 0.04, 3))
                bl = rng.uniform(0.15, 0.7) if rng.random() < 0.22 else 0.0
                for k in range(b, min(b + run, nb)):
                    if rng.random() < 0.05:   # a dark meeting room inside a lit office
                        continue
                    inten[f, k] = level * rng.uniform(0.8, 1.0)
                    color[f, k] = tint
                    blind[f, k] = bl if rng.random() < 0.8 else 0.0
            else:
                for k in range(b, min(b + run, nb)):
                    monitor[f, k] = 1.0 if rng.random() < 0.05 else 0.0
            b += run
    return inten, color, blind, monitor


def glass_set(size, tile, floor, bay, seed=7):
    px, Z, S = _grid(size, tile)
    nf, nb = int(round(tile / floor)), int(round(tile / bay))
    fi = np.floor(Z / floor).astype(int) % nf
    bi = np.floor(S / bay).astype(int) % nb
    f = Z - np.floor(Z / floor) * floor     # height above the slab top
    b = S - np.floor(S / bay) * bay

    v0, v1 = VISION
    vision = _aa_inside(np.minimum(f - v0, v1 - f), px)
    d_mull = np.minimum(b, bay - b)
    mull = 1.0 - _aa_inside(d_mull - MULLION_HALF, px)
    trans = np.maximum(1.0 - _aa_inside(np.abs(f - v0) - TRANSOM_HALF, px),
                       1.0 - _aa_inside(np.abs(f - v1) - TRANSOM_HALF, px))
    frame = np.maximum(mull, trans)
    pane = vision * (1.0 - frame)          # clear vision glass
    span = (1.0 - vision) * (1.0 - frame)  # spandrel panel

    rng = np.random.default_rng(seed)
    tone = rng.random((nf, nb))[fi, bi]
    prough = rng.random((nf, nb))[fi, bi]
    tilt_x = rng.normal(0, 1, (nf, nb))[fi, bi]
    tilt_y = rng.normal(0, 1, (nf, nb))[fi, bi]

    # dirt: streaks washing down from every horizontal edge (sill, transoms)
    streak = surface.oriented_noise(size, size, 90.0, 1.6, 90.0, seed + 1)
    patches = trim.fbm(size, size, 140.0, octaves=4, seed=seed + 2)
    below = np.minimum((v1 - f) % floor, (v0 - f) % floor)
    run = np.exp(-below / 1.1) * np.clip(streak * 0.45 + 0.35, 0.0, 1.0)
    dirt = np.clip(run * 0.8 + np.clip(patches * 0.25 + 0.1, 0.0, 0.4), 0.0, 1.0)

    glass_col = np.array([0.105, 0.125, 0.155])
    span_col = np.array([0.050, 0.055, 0.062])
    frame_col = np.array([0.090, 0.094, 0.104])
    dirt_col = np.array([0.060, 0.055, 0.050])
    alb = (pane[..., None] * glass_col * (0.88 + 0.24 * tone[..., None])
           + span[..., None] * span_col * (0.92 + 0.16 * tone[..., None])
           + frame[..., None] * frame_col)
    alb = alb * (1.0 - 0.35 * dirt[..., None]) + dirt_col * (0.35 * dirt[..., None]) * 0.5
    rough = pane * (0.07 + 0.07 * prough) + span * 0.30 + frame * 0.45
    rough = np.clip(rough + 0.22 * dirt * (0.6 + 0.4 * pane), 0.0, 1.0)
    metal = pane * 0.90 + span * 0.85 + frame * 1.0
    metal = metal * (1.0 - 0.3 * dirt)

    # relief: caps proud of the glass, spandrel a little recessed; panes tilted (oil canning)
    height = frame * 0.045 - span * 0.012
    height = surface.blur(height, 0.7)
    nrm = surface.height_to_normal_2d(height, px, 0.45) * 2.0 - 1.0
    nrm[..., 0] += pane * tilt_x * 0.010
    nrm[..., 1] += pane * tilt_y * 0.010
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    normal = nrm * 0.5 + 0.5
    ao = surface.cavity_ao(height, 2.0, 0.03, 0.5) * (1.0 - 0.15 * span)

    # offices
    inten, color, blind, monitor = office_cells(nf, nb, seed + 3)
    u = np.clip((f - v0) / (v1 - v0), 0.0, 1.0)       # 0 at the sill, 1 at the head
    furn = np.clip(trim.noise(size, size, 9.0, 5.0, seed + 4) * 0.5 + 0.5, 0.0, 1.0)
    depth = np.clip(trim.noise(size, size, 40.0, 24.0, seed + 5) * 0.12 + 1.0, 0.7, 1.3)
    ceiling = 0.62 + 0.38 * trim.smoothstep(u, 0.45, 0.93)
    lumin = np.exp(-((u - 0.95) / 0.035) ** 2) * (0.5 + 0.5 * np.cos(2 * math.pi * S / 1.0)) ** 2 * 0.35
    desk = 0.40 + 0.35 * furn
    prof = np.where(u < 0.32, desk + (ceiling - desk) * trim.smoothstep(u, 0.18, 0.32), ceiling) + lumin
    bf = blind[fi, bi]
    covered = trim.smoothstep(u, 1.0 - bf - 0.03, 1.0 - bf + 0.03) * (bf > 0)
    prof = prof * (1.0 - 0.7 * covered)
    lit = inten[fi, bi]
    em = color[fi, bi] * (lit * prof * depth)[..., None]
    em = em * (1.0 - 0.25 * covered[..., None]) + covered[..., None] * lit[..., None] * 0.05 * WARM_WHITE
    # monitors left on in dark offices: a soft cool glow at desk height
    mon = monitor[fi, bi] * np.exp(-(((b - bay * 0.5) / 0.35) ** 2 + ((u - 0.22) / 0.07) ** 2))
    em = em + mon[..., None] * np.array([0.25, 0.45, 1.0]) * 0.10
    em = em * pane[..., None]
    em = surface.blur(em, 0.6)   # glass and interior depth soften the cell edges a little

    stats = dict(lit_cells=float((inten > 0).mean()), mean_emission=float(em.mean()),
                 warm_share=float(((color[..., 0] > color[..., 2]) & (inten > 0)).sum() / max((inten > 0).sum(), 1)))
    return dict(albedo=alb, normal=normal, ao=ao, rough=rough, metal=metal, emission=em, stats=stats)


# --- metal cladding ------------------------------------------------------------------
def metal_set(size, tile, floor, bay, louver=(56.0, 64.0), seed=11):
    px, Z, S = _grid(size, tile)
    nr, nc = int(round(tile / floor)), int(round(tile / bay))
    ri = np.floor(Z / floor).astype(int) % nr
    ci = np.floor(S / bay).astype(int) % nc
    f = Z - np.floor(Z / floor) * floor
    b = S - np.floor(S / bay) * bay
    lv = ((Z >= louver[0]) & (Z < louver[1])).astype(float)
    lv = np.clip(lv, 0, 1)

    rng = np.random.default_rng(seed)
    tone = rng.random((nr, nc))[ri, ci]
    prough = rng.random((nr, nc))[ri, ci]
    tx = rng.normal(0, 1, (nr, nc))[ri, ci]
    ty = rng.normal(0, 1, (nr, nc))[ri, ci]

    joint_h = 1.0 - _aa_inside(np.minimum(f, floor - f) - 0.022, px)
    joint_v = 1.0 - _aa_inside(np.minimum(b, bay - b) - 0.020, px)
    joint = np.maximum(joint_h, joint_v)

    # louvers: blades every 0.25 m (sawtooth), mullion frames every 2 m
    pitch = 0.25
    t = (Z % pitch) / pitch
    blade_h = -0.06 * t                          # blade slopes down and out
    groove = trim.smoothstep(t, 0.70, 0.98)      # deep shadow under each blade
    lframe = 1.0 - _aa_inside(np.minimum(b, bay - b) - 0.08, px)
    lframe = np.maximum(lframe, 1.0 - _aa_inside(np.minimum(Z - louver[0], louver[1] - Z) - 0.12, px))

    streak = surface.oriented_noise(size, size, 110.0, 2.0, 90.0, seed + 1)
    patches = trim.fbm(size, size, 180.0, octaves=5, seed=seed + 2)
    below = (floor - f) % floor   # distance below the joint above
    run = np.exp(-below / 1.6) * np.clip(streak * 0.5 + 0.35, 0.0, 1.0)
    grime = np.clip(run * 0.9 + np.clip(patches * 0.3 + 0.15, 0.0, 0.6), 0.0, 1.0)
    # sparse rust: a few joints bleed rust down the panel below
    rust_seed = rng.random((nr, nc))[ri, ci]
    rust_x = rng.random((nr, nc))[ri, ci] * bay
    rust_col = np.exp(-((b - rust_x) / 0.18) ** 2) * np.exp(-((floor - f) % floor) / 1.3)
    rust = np.clip((rust_seed > 0.965) * rust_col * np.clip(streak * 0.4 + 0.8, 0, 1), 0, 1) * (1 - lv)

    base = np.array([0.046, 0.049, 0.056])
    alb = base * (0.86 + 0.28 * tone[..., None])
    alb = alb * (1.0 - 0.45 * grime[..., None]) + np.array([0.035, 0.032, 0.028]) * 0.45 * grime[..., None]
    alb = alb * (1.0 - rust[..., None]) + RUST * 0.8 * rust[..., None]
    alb = alb * (1.0 - 0.6 * joint[..., None])
    lv_alb = base * 0.8 * (1.0 - 0.75 * groove[..., None]) * (1.0 - 0.3 * grime[..., None])
    lv_alb = lv_alb * (1.0 - lframe[..., None]) + base * 1.1 * lframe[..., None]
    alb = alb * (1.0 - lv[..., None]) + lv_alb * lv[..., None]

    rough = 0.40 + 0.10 * prough + 0.25 * grime + 0.35 * rust
    rough = rough * (1 - lv) + (0.55 + 0.15 * grime) * lv
    metal = np.clip(0.80 - 0.35 * grime - 0.8 * rust, 0.0, 1.0)
    metal = metal * (1 - lv) + 0.7 * lv

    height = -0.02 * joint + lv * (blade_h * (1 - lframe) + 0.03 * lframe) + (1 - lv) * 0.0
    height = surface.blur(height, 0.6)
    nrm = surface.height_to_normal_2d(height, px, 0.6) * 2.0 - 1.0
    nrm[..., 0] += (1 - lv) * tx * 0.008
    nrm[..., 1] += (1 - lv) * ty * 0.008
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    ao = surface.cavity_ao(height, 2.0, 0.03, 0.5) * (1.0 - 0.45 * groove * lv * (1 - lframe))
    return dict(albedo=alb, normal=nrm * 0.5 + 0.5, ao=ao, rough=np.clip(rough, 0, 1), metal=metal)


# --- lights trim sheet -----------------------------------------------------------------
STRIP_COLORS = {"white": COOL_WHITE, "cyan": CYAN, "magenta": MAGENTA, "uv": ULTRAVIOLET, "amber": AMBER}


def lights_set(size, px_m, rows, pad, seed=23):
    """rows: {band: (row0, n)} (spire_common.LIGHT_ROWS). Returns albedo, ao, rough, metal, emission."""
    h = w = size
    alb = np.zeros((h, w, 3))
    em = np.zeros((h, w, 3))
    rough = np.full((h, w), 0.5)
    metal = np.full((h, w), 0.6)
    u_m = (np.arange(w) + 0.5) / px_m           # meters along the strip, period w / px_m
    housing = np.array([0.04, 0.042, 0.046])
    rng = np.random.default_rng(seed)

    def band_slice(name):
        r0, n = rows[name]
        sl = slice(r0 - pad, r0 + n + pad)
        v = np.clip((np.arange(r0 - pad, r0 + n + pad) - r0 + 0.5) / n, 0.0, 1.0)[:, None]
        return sl, v * np.ones((1, w))

    along = np.clip(trim.noise(1, w, 24.0, 1.0, seed)[0] * 0.06 + 1.0, 0.85, 1.15)[None, :]
    for name, col in STRIP_COLORS.items():
        sl, v = band_slice(name)
        core = trim.smoothstep(v, 0.16, 0.36) * trim.smoothstep(1.0 - v, 0.16, 0.36)
        hot = trim.smoothstep(v, 0.38, 0.5) * trim.smoothstep(1.0 - v, 0.38, 0.5)
        c = col[None, None, :] * (1.0 - 0.35 * hot[..., None]) + 0.35 * hot[..., None] * np.ones(3)
        em[sl] = c * (core * along)[..., None]
        alb[sl] = housing * (1 - core[..., None]) + (0.25 + 0.5 * c) * core[..., None]
        rough[sl] = 0.5 - 0.3 * core
        metal[sl] = 0.7 * (1 - core)

    sl, v = band_slice("red")
    core = trim.smoothstep(v, 0.05, 0.2) * trim.smoothstep(1.0 - v, 0.05, 0.2)
    em[sl] = RED * core[..., None]
    alb[sl] = housing * (1 - core[..., None]) + np.array([0.6, 0.05, 0.03]) * core[..., None]
    rough[sl], metal[sl] = 0.3, 0.0

    # landing pad edge: amber lights 1 m long every 3 m on dark metal
    sl, v = band_slice("pad")
    U = np.ones_like(v) * u_m[None, :]
    dash = _aa_inside(0.5 - np.abs((U % 3.0) - 1.5), 1.0 / px_m)
    core = trim.smoothstep(v, 0.25, 0.45) * trim.smoothstep(1.0 - v, 0.25, 0.45) * dash
    em[sl] = AMBER * core[..., None]
    alb[sl] = housing * (1 - core[..., None]) + np.array([0.7, 0.4, 0.1]) * core[..., None]
    rough[sl], metal[sl] = 0.45, 0.5

    # sky lobbies: tall glazing onto a lit double-height hall; columns every 8 m,
    # ceiling coffers glowing, a few people and planters as soft silhouettes
    for name, tint, accent in (("lobby", np.array([0.80, 0.88, 1.0]), np.array([1.0, 0.70, 0.42])),
                               ("lobby_warm", np.array([1.0, 0.80, 0.58]), np.array([0.6, 0.8, 1.0]))):
        sl, v = band_slice(name)
        U = np.ones_like(v) * u_m[None, :]
        n_rows = v.shape[0]
        ceiling = 0.35 + 0.65 * trim.smoothstep(v, 0.78, 0.93) * (1.0 - trim.smoothstep(v, 0.96, 1.0))
        coffer = 0.75 + 0.25 * np.cos(2 * math.pi * U / 4.0) ** 2
        floor_glow = 0.18 + 0.25 * trim.smoothstep(v, 0.12, 0.0)
        val = np.where(v > 0.6, ceiling * coffer, 0.30 + 0.06 * np.cos(2 * math.pi * U / 16.0))
        val = np.where(v < 0.12, floor_glow + 0.1, val)
        col_d = np.abs(((U + 4.0) % 8.0) - 4.0)
        column = 1.0 - _aa_inside(col_d - 0.6, 1.0 / px_m)
        people = np.zeros_like(val)
        for _ in range(14):
            x = rng.uniform(0, w / px_m)
            hgt = rng.uniform(0.13, 0.17)
            dx = np.abs(((U - x + 32.0) % 64.0) - 32.0)
            people = np.maximum(people, np.exp(-(dx / 0.28) ** 2) * trim.smoothstep(v, hgt, hgt - 0.03)
                                * (v > 0.04))
        plants = np.zeros_like(val)
        for _ in range(6):
            x = rng.uniform(0, w / px_m)
            dx = np.abs(((U - x + 32.0) % 64.0) - 32.0)
            plants = np.maximum(plants, trim.smoothstep(dx, 1.4, 0.6) * trim.smoothstep(v, 0.22, 0.12))
        warm_spot = np.zeros_like(val)
        for _ in range(5):
            x = rng.uniform(0, w / px_m)
            dx = np.abs(((U - x + 32.0) % 64.0) - 32.0)
            warm_spot = np.maximum(warm_spot, np.exp(-(dx / 1.2) ** 2 - ((v - 0.25) / 0.12) ** 2))
        mull = 1.0 - _aa_inside(np.abs(((U + 1.0) % 2.0) - 1.0) - 0.05, 1.0 / px_m)
        val = val * (1 - 0.85 * column) * (1 - 0.7 * people) * (1 - 0.6 * plants) * (1 - 0.5 * mull)
        e = tint * val[..., None] * 0.30 + accent * (0.22 * warm_spot)[..., None]
        em[sl] = e
        alb[sl] = 0.12 * e + 0.02
        rough[sl], metal[sl] = 0.1, 0.5
        del n_rows

    # crown lantern: uplit facets, bright at the bottom, ribs every 2 m
    sl, v = band_slice("crown")
    U = np.ones_like(v) * u_m[None, :]
    rib = 1.0 - _aa_inside(np.abs(((U + 1.0) % 2.0) - 1.0) - 0.12, 1.0 / px_m)
    glow = 0.12 + 0.88 * np.exp(-v * 2.6)
    tint = COOL_WHITE * 0.4 + CYAN * 0.6
    em[sl] = tint * (0.42 * glow * (1 - 0.8 * rib))[..., None]
    alb[sl] = 0.1 * em[sl] + 0.03
    rough[sl], metal[sl] = 0.2, 0.4
    return dict(albedo=alb, ao=np.ones((h, w)), rough=rough, metal=metal, emission=em)
