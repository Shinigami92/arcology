"""The corridor kit's small fixtures: geometry, materials, bake and render settings.

Each is authored around its contract origin (tools/blockout/corridor_kit.json), Blender axes:
ceiling fixtures hang from z = 0 downward (Godot -Y) with the long axis along X; the exit sign's
back is on the wall plane y = 0 and its face looks along -Y (Godot +Z). The mounting side stays
open (it's against the ceiling or the wall). One baked material per fixture (`src_*` procedural,
bake.bake_part) plus at most one plain emissive material with the contract's slot name, joined
into one mesh after the bake.

  corridor_light  white powder-coated aluminium profile, a regressed opal diffuser (corridor_light_diffuser)
  corridor_vent   two-slot linear diffuser: white flange, black slot interiors with deflector blades,
                  dust halos along the slots (no emissive)
  exit_sign       brushed aluminium box, recessed back-lit face (exit_sign_face): a green pictogram
                  panel with a white running man at a doorway, green EXIT and an invented-kanji line
  holo_emitter    dark anodized puck, black glass lens dome, a proud cyan light-guide ring (holo_emitter_ring)
"""

import math

import bmesh
import numpy as np
from mathutils import Vector

from corridor_common import (
    EXIT_GREEN_HEX, LED_CYAN, LED_STRENGTH, WARM_NEUTRAL, WHITE_POWDER, contract,
)
from arcology_blender import curves, metal, wear
from arcology_blender.geo import new_object
from arcology_blender.scene import get_collection, tag
from arcology_blender.shading import Graph, new_mat, solid_mat
from arcology_blender.trim import GODOT_TO_BLENDER, TrimMesh, TrimSheet

_SHEET = TrimSheet(16, 16, 16.0, pad=0)   # no bands: TrimMesh only for its mitered sweeps, the bake unwraps

BAKE = {
    "corridor_light": dict(material="corridor_light_frame", size=1024, required="corridor_light_diffuser"),
    "corridor_vent": dict(material="corridor_vent", size=1024, required="corridor_vent"),
    "exit_sign": dict(material="exit_sign_housing", size=512, required="exit_sign_face"),
    "holo_emitter": dict(material="holo_emitter_body", size=512, required="holo_emitter_ring"),
}

FLIP = (math.pi, 0.0, 0.0)   # studio: ceiling fixtures face up
STUDIO = {
    "corridor_light": dict(rotation=FLIP, camera=(0.70, -0.95, 0.60), target=(0.0, 0.0, 0.01), lens=50.0,
                           detail=dict(camera=(0.82, -0.26, 0.16), target=(0.50, 0.0, 0.01), lens=45.0)),
    "corridor_vent": dict(rotation=FLIP, camera=(0.55, -0.75, 0.52), target=(0.0, 0.0, 0.0), lens=50.0,
                          detail=dict(camera=(0.60, -0.20, 0.13), target=(0.36, 0.0, 0.005), lens=45.0)),
    "exit_sign": dict(location=(0.0, 0.0, 0.30), camera=(0.32, -0.95, 0.42), target=(0.0, 0.0, 0.30), lens=60.0,
                      detail=dict(camera=(0.14, -0.38, 0.33), target=(0.0, -0.05, 0.30), lens=50.0)),
    "holo_emitter": dict(rotation=FLIP, camera=(0.13, -0.19, 0.17), target=(0.0, 0.0, 0.012), lens=60.0, key=150.0),
}

# Corridor stills (Godot camera, target, lens): render.py places every exported kit glb.
CONTEXT_VIEWS = {
    "corridor_light": {"context": dict(camera=(-1.9, 1.55, 8.75), target=(0.0, 2.75, 8.2), lens=26.0)},
    "corridor_vent": {"context": dict(camera=(0.9, 1.55, 8.75), target=(2.2, 2.78, 8.2), lens=32.0)},
    "exit_sign": {"context": dict(camera=(-3.0, 1.6, 8.7), target=(-7.0, 1.9, 8.2), lens=30.0),
                  "close": dict(camera=(-5.6, 1.75, 8.45), target=(-7.0, 2.33, 8.2), lens=45.0)},
    "holo_emitter": {"context": dict(camera=(6.95, 1.55, 8.3), target=(7.7, 2.78, 9.25), lens=40.0)},
}


def _mesh(tm, name, coll, mat):
    return tm.to_object(name, coll, {"m": mat}, sharp_angle=35.0)


def _finish(objs):
    for ob in objs:
        tag(ob, "body")
    return objs


# --- corridor_light ----------------------------------------------------------------------------------
def mat_light_frame():
    """White powder coat: orange peel, a glossier white reflector inside the recess, a faint grey
    film on the outer edges (ceiling dust), slight yellowing near the diffuser."""
    g = Graph(new_mat("src_light_frame"))
    peel = g.noise(900.0, 2.0, 0.5)
    base = g.scale_color(WHITE_POWDER, g.add(0.985, g.mul(g.noise(25.0, 3.0), 0.03)))
    rough = g.add(0.40, g.mul(g.sub(peel, 0.5), 0.06))
    recess = g.mul(g.mul(g.maprange(g.z, -0.0255, -0.0245), g.maprange(g.math("ABSOLUTE", g.y), 0.0625, 0.0615)),
                   g.maprange(g.math("ABSOLUTE", g.x), 0.5735, 0.5725))
    rough = g.mixf(recess, rough, 0.22)
    base = g.mixc(g.mul(recess, 0.5), base, (0.72, 0.70, 0.64))
    edge = wear.convex_edges(g, radius=0.002)
    film = g.mul(g.maprange(g.math("ABSOLUTE", g.y), 0.080, 0.090), g.maprange(g.noise(30.0, 3.0), 0.35, 0.7))
    base = g.mixc(g.mul(film, 0.25), base, (0.42, 0.41, 0.39))
    base, rough = wear.edge_wear(g, base, rough, edge, 1.0, (0.80, 0.80, 0.78), amount=0.25, rough_delta=-0.05)
    return g.finish_height(base, rough, 0.0, g.mul(peel, 0.000006))


def build_light():
    c = contract("corridor_light")
    L, D_, W = c["size"][0], c["size"][1], c["size"][2]
    coll = get_collection("Light")
    hw = W / 2
    inset, recess = 0.030, 0.010
    # (inset from the outer edge, depth below the ceiling), from the diffuser edge out to the ceiling
    prof = [(inset, recess), (0.028, 0.012), (0.028, 0.0275), (0.0255, D_), (0.005, D_)]
    for k in range(1, 4):   # rounded outer bottom edge
        a = math.pi / 2 * k / 4
        prof.append((0.005 - 0.005 * math.sin(a), D_ - 0.005 + 0.005 * math.cos(a)))
    prof += [(0.0, D_ - 0.005), (0.0, 0.0)]
    tm = TrimMesh(_SHEET, band_mats={"f": "m"})
    tm.rect_sweep((-L / 2, L / 2, -hw, hw), prof, ["f"] * (len(prof) - 1), depth_axis=(0.0, 0.0, -1.0), closed=False)
    frame = _mesh(tm, "LightFrame", coll, mat_light_frame())
    # opal diffuser, bowed 2 mm down at the middle
    tm2 = TrimMesh(_SHEET, band_mats={"d": "m"})
    x0, x1, y0 = -L / 2 + inset, L / 2 - inset, hw - inset
    ys = [-y0 + 2 * y0 * k / 6 for k in range(7)]
    zs = [-recess - 0.002 * (1 - (y / y0) ** 2) for y in ys]
    for k in range(6):
        tm2.poly([(x0, ys[k], zs[k]), (x1, ys[k], zs[k]), (x1, ys[k + 1], zs[k + 1]), (x0, ys[k + 1], zs[k + 1])],
                 "d", (1, 0, 0), (0, 0, -1))
    # the diffuser's short ends close against the recess walls (the bow leaves a sliver)
    for x, nx in ((x0, -1.0), (x1, 1.0)):   # the bow's outline; its chord is the frame's straight edge
        tm2.poly([(x, y, z) for y, z in zip(ys, zs)], "d", (0, 1, 0), (-nx, 0, 0))
    diff = _mesh(tm2, "LightDiffuser", coll, solid_mat(BAKE["corridor_light"]["required"], (0.86, 0.85, 0.83), 0.45,
                                                        0.0, WARM_NEUTRAL, LED_STRENGTH))
    return _finish([frame, diff])


# --- corridor_vent -----------------------------------------------------------------------------------
VENT_SLOTS = ((-0.046, -0.014), (0.014, 0.046))   # y ranges of the two slots
VENT_SLOT_X = 0.432
VENT_BACK = 0.004                                  # slot back (plenum) below the ceiling


def mat_vent():
    """White powder-coated flange, matte black slot interiors, grey dust halos along the slots."""
    g = Graph(new_mat("src_vent"))
    peel = g.noise(900.0, 2.0, 0.5)
    ay = g.math("ABSOLUTE", g.y)
    ax = g.math("ABSOLUTE", g.x)
    inside = g.mul(g.mul(g.maprange(g.z, -0.0196, -0.0192), g.maprange(ay, 0.0468, 0.0462)),
                   g.maprange(ax, VENT_SLOT_X + 0.0008, VENT_SLOT_X + 0.0002))
    base = g.scale_color(WHITE_POWDER, g.add(0.985, g.mul(g.noise(25.0, 3.0), 0.03)))
    rough = g.add(0.42, g.mul(g.sub(peel, 0.5), 0.06))
    # dust: the air leaves a soft grey stain on the flange along each slot edge
    near = g.math("MINIMUM", g.math("ABSOLUTE", g.sub(ay, 0.046)), g.math("ABSOLUTE", g.sub(ay, 0.014)))
    halo = g.mul(g.maprange(near, 0.012, 0.0), g.maprange(ax, VENT_SLOT_X + 0.03, VENT_SLOT_X - 0.05))
    halo = g.mul(halo, g.maprange(g.noise(18.0, 4.0, 0.6), 0.25, 0.55))
    halo = g.mul(halo, g.maprange(g.nz, -0.5, -0.9))
    base = g.mixc(g.mul(halo, 0.6), base, (0.24, 0.23, 0.22))
    rough = g.add(rough, g.mul(halo, 0.15))
    black = g.scale_color((0.018, 0.018, 0.019), g.add(1.0, g.mul(g.noise(60.0, 2.0), 0.3)))
    base = g.mixc(inside, base, black)
    rough = g.mixf(inside, rough, 0.62)
    return g.finish_height(base, rough, 0.0, g.mul(peel, 0.000006))


def build_vent():
    c = contract("corridor_vent")
    L, D_, W = c["size"][0], c["size"][1], c["size"][2]
    coll = get_collection("Vent")
    hl, hw = L / 2, W / 2
    tm = TrimMesh(_SHEET, band_mats={"v": "m"})
    edge = 0.004
    prof = [(edge, D_)]
    for k in range(1, 4):
        a = math.pi / 2 * k / 4
        prof.append((edge - edge * math.sin(a), D_ - edge + edge * math.cos(a)))
    prof += [(0.0, D_ - edge), (0.0, 0.0)]
    tm.rect_sweep((-hl, hl, -hw, hw), prof, ["v"] * (len(prof) - 1), depth_axis=(0.0, 0.0, -1.0), closed=False)
    # bottom face with the two slots
    xs = [-hl + edge, -VENT_SLOT_X, VENT_SLOT_X, hl - edge]
    ys = [-hw + edge, VENT_SLOTS[0][0], VENT_SLOTS[0][1], VENT_SLOTS[1][0], VENT_SLOTS[1][1], hw - edge]

    def cell(u, v):
        slot = abs(u) < VENT_SLOT_X and any(a < v < b for a, b in VENT_SLOTS)
        return None if slot else "v"

    tm.grid((0.0, 0.0, -D_), (1, 0, 0), (0, 1, 0), xs, ys, cell, (0, 0, -1))
    for a, b in VENT_SLOTS:
        # slot walls up to the black back, and the back itself
        tm.rect_sweep((-VENT_SLOT_X, VENT_SLOT_X, a, b), [(0.0, VENT_BACK), (0.0, D_)], ["v"],
                      depth_axis=(0.0, 0.0, -1.0), closed=False)
        tm.poly([(-VENT_SLOT_X, a, -VENT_BACK), (VENT_SLOT_X, a, -VENT_BACK), (VENT_SLOT_X, b, -VENT_BACK),
                 (-VENT_SLOT_X, b, -VENT_BACK)], "v", (1, 0, 0), (0, 0, -1))
        # pattern-controller blade: a thin slanted vane along the slot, throwing the air outward
        yc = (a + b) / 2
        s = 1.0 if yc > 0 else -1.0
        blade = [(yc - s * 0.010, -0.0060), (yc - s * 0.008, -0.0060), (yc + s * 0.010, -0.0160),
                 (yc + s * 0.008, -0.0160)]
        area = sum(blade[i][0] * blade[(i + 1) % 4][1] - blade[(i + 1) % 4][0] * blade[i][1] for i in range(4))
        if area < 0:   # counter-clockwise in (y, z): extrude's faces look outward
            blade = blade[::-1]
        tm.extrude(blade,
                   (-VENT_SLOT_X + 0.0005, 0.0, 0.0), (0, 1, 0), (0, 0, 1), (1, 0, 0), 2 * VENT_SLOT_X - 0.001,
                   ["v"] * 4, closed=True, caps=(True, True), cap_band="v")
    ob = _mesh(tm, "Vent", coll, mat_vent())
    return _finish([ob])


# --- exit_sign ---------------------------------------------------------------------------------------
EXIT_FACE_PX = (1024, 512)
EXIT_STRENGTH = 1.0        # keeps the green saturated under AgX (stronger washes it out to mint)


def _srgb(hexstr):
    return np.array([int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def _seg_cov(px, py, a, b, w):
    """Antialiased coverage of a round-capped stroke from a to b, width w (pixels)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / ll, 0.0, 1.0) if ll > 0 else 0.0
    d = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
    return np.clip(w / 2 - d + 0.5, 0.0, 1.0)


def _rect_cov(px, py, x0, y0, x1, y1):
    cx = np.clip(np.minimum(px - x0, x1 - px) + 0.5, 0.0, 1.0)
    cy = np.clip(np.minimum(py - y0, y1 - py) + 0.5, 0.0, 1.0)
    return cx * cy


def _rounded_rect_cov(px, py, x0, y0, x1, y1, r):
    qx = np.maximum(np.maximum(x0 + r - px, px - (x1 - r)), 0.0)
    qy = np.maximum(np.maximum(y0 + r - py, py - (y1 - r)), 0.0)
    inside = (px >= x0) & (px <= x1) & (py >= y0) & (py <= y1)
    d = np.hypot(qx, qy) - r
    return np.where(inside, np.clip(0.5 - d, 0.0, 1.0), 0.0)


def _letters_exit(px, py, x0, y0, h):
    """E X I T in a geometric sans (straight strokes): coverage. (x0, y0) bottom-left, h cap height."""
    sw = 0.17 * h                                  # stroke weight
    cov = np.zeros_like(px)
    adv = 0.0
    # E
    w = 0.56 * h
    cov = np.maximum(cov, _rect_cov(px, py, x0, y0, x0 + sw, y0 + h))
    cov = np.maximum(cov, _rect_cov(px, py, x0, y0 + h - sw, x0 + w, y0 + h))
    cov = np.maximum(cov, _rect_cov(px, py, x0, y0 + h / 2 - sw / 2, x0 + w * 0.9, y0 + h / 2 + sw / 2))
    cov = np.maximum(cov, _rect_cov(px, py, x0, y0, x0 + w, y0 + sw))
    adv += w + 0.20 * h
    # X
    w = 0.66 * h
    xa = x0 + adv
    box = _rect_cov(px, py, xa, y0, xa + w, y0 + h)
    cov = np.maximum(cov, box * _seg_cov(px, py, (xa + 0.06 * h, y0 - 0.1 * h), (xa + w - 0.06 * h, y0 + 1.1 * h), sw * 1.08))
    cov = np.maximum(cov, box * _seg_cov(px, py, (xa + 0.06 * h, y0 + 1.1 * h), (xa + w - 0.06 * h, y0 - 0.1 * h), sw * 1.08))
    adv += w + 0.20 * h
    # I
    xa = x0 + adv
    cov = np.maximum(cov, _rect_cov(px, py, xa, y0, xa + sw, y0 + h))
    adv += sw + 0.20 * h
    # T
    w = 0.60 * h
    xa = x0 + adv
    cov = np.maximum(cov, _rect_cov(px, py, xa, y0 + h - sw, xa + w, y0 + h))
    cov = np.maximum(cov, _rect_cov(px, py, xa + w / 2 - sw / 2, y0, xa + w / 2 + sw / 2, y0 + h))
    adv += w
    return cov, adv


def exit_letters_width(h):
    return (0.56 + 0.20 + 0.66 + 0.20 + 0.17 + 0.20 + 0.60) * h


def _kanji(px, py, x0, y0, size, seed, count):
    """A line of invented kanji-like glyphs: strokes on a square grid (horizontals, verticals,
    falling sweeps, dots), each glyph a deterministic composition. Coverage."""
    rng = np.random.default_rng(seed)
    cov = np.zeros_like(px)
    sw = 0.11 * size
    for k in range(count):
        gx = x0 + k * size * 1.18
        strokes = []
        kind = rng.integers(0, 3)
        if kind == 0:     # radical on the left, body on the right
            strokes += [((0.18, 0.12), (0.18, 0.88)), ((0.05, 0.62), (0.32, 0.62))]
            for yy in rng.choice([0.2, 0.42, 0.62, 0.84], size=2, replace=False):
                strokes.append(((0.45, yy), (0.95, yy)))
            strokes.append(((0.70, 0.92), (0.70, 0.08)))
        elif kind == 1:   # roof over a box
            strokes += [((0.5, 0.97), (0.5, 0.86)), ((0.08, 0.82), (0.92, 0.82)), ((0.08, 0.82), (0.08, 0.70))]
            strokes += [((0.25, 0.55), (0.25, 0.10)), ((0.25, 0.55), (0.75, 0.55)), ((0.75, 0.55), (0.75, 0.10)),
                        ((0.25, 0.10), (0.75, 0.10))]
            if rng.random() < 0.5:
                strokes.append(((0.25, 0.33), (0.75, 0.33)))
        else:             # crossing strokes with sweeps
            strokes += [((0.10, 0.70), (0.90, 0.70)), ((0.5, 0.95), (0.5, 0.45)), ((0.5, 0.45), (0.12, 0.08)),
                        ((0.5, 0.45), (0.88, 0.08))]
            strokes += [((0.20, 0.30), (0.80, 0.30)), ((0.14, 0.95), (0.26, 0.84))]   # never a plain 大
        for (ax, ay), (bx, by) in strokes:
            j = rng.normal(0.0, 0.015, 4)
            a = (gx + (ax + j[0]) * size, y0 + (ay + j[1]) * size)
            b = (gx + (bx + j[2]) * size, y0 + (by + j[3]) * size)
            cov = np.maximum(cov, _seg_cov(px, py, a, b, sw))
    return cov


def _running_man(px, py, x0, y0, s):
    """ISO-style running figure (running toward -x, the doorway) in a unit box at (x0, y0) of size s: coverage."""
    def P(x, y):   # drawn running toward +x, mirrored so it runs toward -x (into the doorway on its left)
        return (x0 + (1.0 - x) * s, y0 + y * s)
    cov = np.zeros_like(px)
    hx, hy = P(0.60, 0.86)
    cov = np.maximum(cov, np.clip(0.085 * s - np.hypot(px - hx, py - hy) + 0.5, 0.0, 1.0))
    limbs = [
        (P(0.55, 0.70), P(0.45, 0.43), 0.15),    # torso
        (P(0.53, 0.68), P(0.37, 0.58), 0.085), (P(0.37, 0.58), P(0.24, 0.66), 0.08),   # front arm
        (P(0.55, 0.66), P(0.70, 0.55), 0.085), (P(0.70, 0.55), P(0.80, 0.64), 0.08),   # back arm
        (P(0.45, 0.43), P(0.31, 0.27), 0.10), (P(0.31, 0.27), P(0.28, 0.06), 0.09),    # front leg
        (P(0.28, 0.06), P(0.18, 0.06), 0.08),
        (P(0.46, 0.42), P(0.62, 0.25), 0.10), (P(0.62, 0.25), P(0.82, 0.18), 0.09),    # back leg
    ]
    for a, b, w in limbs:
        cov = np.maximum(cov, _seg_cov(px, py, a, b, w * s))
    return cov


def exit_face_pixels():
    """The face print (sRGB 0..1, row 0 at the bottom): near-white diffuser, a green pictogram
    panel with a white running man at a doorway, green EXIT and a smaller invented-kanji line."""
    w, h = EXIT_FACE_PX
    used = h * 0.824                                 # the face's aspect (0.34 x 0.14) on a 1024 x 512 image
    v0 = (h - used) / 2
    py, px = np.mgrid[0:h, 0:w].astype(np.float64) + 0.5
    green = _srgb(EXIT_GREEN_HEX)
    white = np.array([0.95, 0.96, 0.94])
    img = np.ones((h, w, 3)) * white
    # soft back-light falloff toward the edges (an edge-lit panel), very slight
    ex = np.minimum(px, w - px) / w
    ey = np.minimum(py - v0, v0 + used - py) / used
    img *= (0.95 + 0.05 * np.clip(np.minimum(ex * 6, ey * 4), 0, 1))[..., None]
    m = 34.0
    panel = _rounded_rect_cov(px, py, m, v0 + m, m + used - 2 * m, v0 + used - m, 18.0)
    img = img * (1 - panel[..., None]) + green * panel[..., None]
    ps = used - 2 * m
    door = np.maximum(_rect_cov(px, py, m + 0.10 * ps, v0 + m + 0.10 * ps, m + 0.16 * ps, v0 + m + 0.88 * ps),
                      _rect_cov(px, py, m + 0.10 * ps, v0 + m + 0.82 * ps, m + 0.40 * ps, v0 + m + 0.88 * ps))
    door = np.maximum(door, _rect_cov(px, py, m + 0.34 * ps, v0 + m + 0.60 * ps, m + 0.40 * ps, v0 + m + 0.88 * ps))
    man = _running_man(px, py, m + 0.22 * ps, v0 + m + 0.10 * ps, 0.74 * ps)
    fig = np.maximum(door, man) * panel
    img = img * (1 - fig[..., None]) + white * fig[..., None]
    # EXIT and the kanji line, centered in the space right of the panel
    left = m + ps + 40.0
    cap = 0.46 * used
    tw = exit_letters_width(cap)
    tx = left + (w - m - left - tw) / 2
    letters, _ = _letters_exit(px, py, tx, v0 + used * 0.40, cap)
    ks = 0.20 * used
    n = 4
    kw = (n - 1) * ks * 1.18 + ks
    kan = _kanji(px, py, left + (w - m - left - kw) / 2, v0 + used * 0.10, ks, 4417, n)
    text = np.maximum(letters, kan)
    img = img * (1 - text[..., None]) + green * text[..., None]
    return np.clip(img, 0.0, 1.0), (v0 / h, (v0 + used) / h)


def mat_exit_housing():
    """Brushed aluminium: brushing along X, a little dust on the top, finger marks on the bezel."""
    g = Graph(new_mat("src_exit_housing"))
    rough, h = metal.brushed(g, 0.30, axis="X", streak=0.05)
    base = g.scale_color((0.56, 0.57, 0.58), g.add(0.97, g.mul(g.noise(40.0, 3.0), 0.06)))
    top = g.maprange(g.nz, 0.6, 0.9)
    base = g.mixc(g.mul(top, 0.35), base, (0.40, 0.39, 0.37))
    rough = g.add(rough, g.mul(top, 0.25))
    smudge = g.mul(g.maprange(g.noise(35.0, 3.0, 0.6), 0.62, 0.75), g.maprange(g.ny, -0.6, -0.9))
    rough = g.add(rough, g.mul(smudge, 0.15))
    return g.finish_height(base, rough, 1.0, h)


def build_exit_sign():
    import bpy
    c = contract("exit_sign")
    sx, sy, sz = c["size"]               # Godot: width, height, depth
    coll = get_collection("ExitSign")
    face_d, lip = sz - 0.003, 0.010
    # authored in Godot axes (rect in X/Y, depth along +Z = the face direction)
    prof = [(lip, face_d), (lip, sz), (0.004, sz)]
    for k in range(1, 4):
        a = math.pi / 2 * k / 4
        prof.append((0.004 - 0.004 * math.sin(a), sz - 0.004 + 0.004 * math.cos(a)))
    prof += [(0.0, sz - 0.004), (0.0, 0.0)]
    tm = TrimMesh(_SHEET, basis=GODOT_TO_BLENDER, band_mats={"h": "m"})
    tm.rect_sweep((-sx / 2, sx / 2, -sy / 2, sy / 2), prof, ["h"] * (len(prof) - 1), depth_axis=(0.0, 0.0, 1.0),
                  closed=False)
    housing = _mesh(tm, "ExitHousing", coll, mat_exit_housing())
    # the face: one quad, the print as albedo and emission
    pixels, (va, vb) = exit_face_pixels()
    w, h = EXIT_FACE_PX
    img = bpy.data.images.new("exit_sign_face", w, h, alpha=False)
    img.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = pixels
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    fx, fy = sx / 2 - lip, sy / 2 - lip
    bm = bmesh.new()
    vs = [bm.verts.new(GODOT_TO_BLENDER @ Vector(p)) for p in
          ((-fx, -fy, face_d), (fx, -fy, face_d), (fx, fy, face_d), (-fx, fy, face_d))]
    bm.faces.new(vs)
    face = new_object("ExitFace", bm, coll)
    uv = face.data.uv_layers.new(name="UVMap")
    for loop, (u, v) in zip(uv.data, ((0.0, va), (1.0, va), (1.0, vb), (0.0, vb))):
        loop.uv = (u, v)
    m = solid_mat(BAKE["exit_sign"]["required"], (1.0, 1.0, 1.0), 0.18)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = EXIT_STRENGTH
    face.data.materials.append(m)
    if face.data.polygons[0].normal.y > 0:   # must look along -Y (Godot +Z)
        face.data.flip_normals()
    return _finish([housing, face])


def _face_down(ob):
    """Lathe recalculates normals, which can guess wrong on open surfaces: the lowest face must look down."""
    low = min(ob.data.polygons, key=lambda p: p.center.z)
    if low.normal.z > 0:
        ob.data.flip_normals()


# --- holo_emitter ------------------------------------------------------------------------------------
EMITTER_SEGMENTS = 40
LENS_R = 0.0175


def mat_emitter():
    """Dark anodized aluminium, spun on the bottom; black glass lens (glossy)."""
    g = Graph(new_mat("src_holo_body"))
    rough, h = metal.brushed(g, 0.34, center=(0.0, 0.0), streak=0.05)
    base = g.scale_color((0.075, 0.078, 0.085), g.add(0.97, g.mul(g.noise(80.0, 3.0), 0.06)))
    r = g.dist_xy(0.0, 0.0)
    lens = g.mul(g.maprange(r, LENS_R + 0.0004, LENS_R - 0.0002), g.maprange(g.z, -0.0302, -0.0308))
    base = g.mixc(lens, base, (0.008, 0.009, 0.011))
    rough = g.mixf(lens, rough, 0.04)
    metal_v = g.mixf(lens, 1.0, 0.0)
    edge = wear.convex_edges(g, radius=0.0015)
    base, rough = wear.edge_wear(g, base, rough, edge, g.sub(1.0, lens), (0.30, 0.31, 0.33), amount=0.35,
                                 rough_delta=-0.06)
    return g.finish_height(base, rough, metal_v, g.mul(h, g.sub(1.0, lens)))


def build_holo_emitter():
    c = contract("holo_emitter")
    R, H = c["size"][0] / 2, c["size"][1]
    coll = get_collection("HoloEmitter")
    seg = EMITTER_SEGMENTS
    bottom, ring_o, ring_i = -0.028, 0.0255, 0.0215
    body = [(R, 0.0), (R, -0.022)]
    for k in range(1, 5):
        a = math.pi / 2 * k / 5
        body.append((R - 0.006 + 0.006 * math.cos(a), -0.022 - 0.006 * math.sin(a)))
    body += [(R - 0.006, bottom), (ring_o, bottom)]
    bm = bmesh.new()
    curves.lathe(bm, body[::-1], segments=seg)
    inner = [(ring_i, bottom), (LENS_R, bottom), (LENS_R, -0.0305), (0.015, -0.0325), (0.010, -0.0341),
             (0.005, -0.0348), (0.0, -H)]
    curves.lathe(bm, inner[::-1], segments=seg)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    body_ob = new_object("EmitterBody", bm, coll, material=mat_emitter())
    bm2 = bmesh.new()
    curves.lathe(bm2, [(ring_i, bottom), (ring_i, -0.029), (ring_o, -0.029), (ring_o, bottom)], segments=seg)
    ring = new_object("EmitterRing", bm2, coll, material=solid_mat(BAKE["holo_emitter"]["required"],
                                                                     (0.55, 0.85, 0.90), 0.3, 0.0, LED_CYAN,
                                                                     LED_STRENGTH))
    from arcology_blender.geo import shade
    for ob in (body_ob, ring):
        _face_down(ob)
        shade(ob, 35.0)
    return _finish([body_ob, ring])


BUILDERS = {
    "corridor_light": build_light,
    "corridor_vent": build_vent,
    "exit_sign": build_exit_sign,
    "holo_emitter": build_holo_emitter,
}
JOINED_NAME = {"corridor_light": "CorridorLight", "corridor_vent": "CorridorVent", "exit_sign": "ExitSign",
               "holo_emitter": "HoloEmitter"}
