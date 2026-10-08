"""The corridor wainscot (corridor_trim.glb): profile, trim sheet and sweep.

Profile (s off the wall plane, v up from the floor), back on the wall:

  0.000 .. 0.100  skirting band: powder-coated aluminium, 30 mm proud, chamfered top edge
  0.100 .. 0.990  panel field: anthracite matte laminate, 25 mm proud, V-joints every 1.2 m
  0.990 .. 1.000  LED reveal: a 1 cm slot under the cap; its back face (`corridor_led`) looks
                  out and down at the panel
  1.000 .. 1.050  rail cap: brushed dark bronze, 35 mm proud, rounded top front edge

One mesh, two materials: `corridor_trim` (a numpy trim sheet, U along the run, 2048 x 1024,
2.4 m per repeat = 853 px/m) and `corridor_led` (plain emissive, Godot sets its color).
The V-joints are geometry (TrimMesh.polyline_sweep grooves), measured from each run's start.
Run ends are capped per region (skirting, panel, LED channel, rail); corners are mitered.
"""

import math

import numpy as np

from corridor_common import ANTHRACITE, BRONZE, BRONZE_POLISH, DUST, GRIME, LED_CYAN, LED_STRENGTH, POWDER_BLACK
from arcology_blender.trim import TrimMesh, TrimSheet, noise, smoothstep

MAT = "corridor_trim"
MAT_LED = "corridor_led"

# --- Profile (meters) -------------------------------------------------------------------------
SKIRT_H, SKIRT_D, SKIRT_CHAMFER = 0.100, 0.030, 0.003
PANEL_D, PANEL_TOP = 0.025, 0.990          # contract: 0.025 m off the wall, field 0.10 .. 1.00 with the reveal
SLOT_BACK = 0.012                          # LED channel face: 12 .. 16 mm off the wall, looking out and down
LED_TOP_S = 0.016
CAP_BOTTOM, CAP_TOP, CAP_D = 1.000, 1.050, 0.035
CAP_R, CAP_STEPS = 0.006, 6                # top front round-over
CAP_CHAMFER = 0.001                        # eased bottom front edge

JOINT = 1.2                                # V-joint spacing along each run, from its start (contract)
GROOVE_W, GROOVE_D = 0.008, 0.004          # V-groove width at the face, depth
JOINT_CLEAR = 0.08                         # no groove closer to a corner or an end (the corner is the joint)

# --- Trim sheet --------------------------------------------------------------------------------
REPEAT = 2.4                               # U period (m)
SHEET_W, SHEET_H = 2048, 1024
PX_PER_M = SHEET_W / REPEAT                # 853 px/m
PAD = 6
SEED = 6044
LAMINATE_ROUGH = 0.60
POWDER_ROUGH = 0.42
BRONZE_ROUGH = 0.30


def profile():
    """Closed profile (s, v), counter-clockwise (solid on the left), from the skirting's front
    bottom edge. Returns (points, bands per segment, groove point indices)."""
    pts = [(SKIRT_D, 0.0), (SKIRT_D, SKIRT_H - SKIRT_CHAMFER), (SKIRT_D - SKIRT_CHAMFER, SKIRT_H),
           (PANEL_D, SKIRT_H), (PANEL_D, PANEL_TOP), (SLOT_BACK, PANEL_TOP), (LED_TOP_S, CAP_BOTTOM),
           (CAP_D - CAP_CHAMFER, CAP_BOTTOM), (CAP_D, CAP_BOTTOM + CAP_CHAMFER), (CAP_D, CAP_TOP - CAP_R)]
    cs, cv = CAP_D - CAP_R, CAP_TOP - CAP_R
    for k in range(1, CAP_STEPS):
        a = math.pi / 2 * k / CAP_STEPS
        pts.append((cs + CAP_R * math.cos(a), cv + CAP_R * math.sin(a)))
    pts += [(cs, CAP_TOP), (0.0, CAP_TOP), (0.0, 0.0)]
    bands = (["skirt"] * 3 + ["panel"] * 2 + ["led"] + ["rail"] * (len(pts) - 8) + ["plain", "plain"])
    assert len(bands) == len(pts)
    return pts, bands, (3, 4)


def band_arcs():
    """Arc length of each finish band along the profile (= its V extent on the sheet)."""
    pts, bands, _ = profile()
    out = {}
    for k, b in enumerate(bands):
        a, c = pts[k], pts[(k + 1) % len(pts)]
        out[b] = out.get(b, 0.0) + math.dist(a, c)
    return out


def layout():
    """The sheet with its bands (no pixels yet): the sweep needs it for the UVs."""
    sheet = TrimSheet(SHEET_W, SHEET_H, PX_PER_M, pad=PAD)
    arcs = band_arcs()
    for name in ("skirt", "panel", "rail"):
        sheet.add_band(name, math.ceil(arcs[name] * PX_PER_M) + 2)
    sheet.add_band("plain", 8)
    return sheet


# --- Finishes (numpy; v_m from each band's start along the profile arc) ---------------------------
def _u(w, px_m):
    return np.arange(w)[None, :] * px_m


def _blobs(h, w, px_m, v_m, rng, count, u_len, v_len, v_range):
    """Soft elliptical blobs, periodic along U: a 0..1 mask."""
    u = _u(w, px_m)
    out = np.zeros((h, w))
    for _ in range(count):
        uc, vc = rng.uniform(0.0, REPEAT), rng.uniform(*v_range)
        lu, lv = rng.uniform(*u_len), rng.uniform(*v_len)
        du = (u - uc + REPEAT / 2) % REPEAT - REPEAT / 2
        out += rng.uniform(0.5, 1.0) * np.exp(-2.2 * ((du / (lu / 2)) ** 2 + ((v_m - vc) / (lv / 2)) ** 2))
    return np.clip(out, 0.0, 1.0)


def _scratches(h, w, px_m, v_m, rng, count, length, v_range, slope=0.06):
    """Thin, nearly horizontal scratch lines (luggage, cart corners): a 0..1 mask."""
    u = _u(w, px_m)
    out = np.zeros((h, w))
    for _ in range(count):
        uc, vc = rng.uniform(0.0, REPEAT), rng.uniform(*v_range)
        ln = rng.uniform(*length)
        k = rng.uniform(-slope, slope)
        du = (u - uc + REPEAT / 2) % REPEAT - REPEAT / 2
        along = np.clip(1 - np.abs(du) / (ln / 2), 0.0, 1.0)
        d = np.abs(v_m - (vc + k * du))
        out = np.maximum(out, rng.uniform(0.4, 1.0) * np.exp(-(d / 0.0006) ** 2) * np.sqrt(along))
    return out


def _skirt(h, w, px_m, v_m, seed):
    """Powder-coated aluminium kick band: orange peel, shoe scuffs, vacuum knocks, dust on top."""
    rng = np.random.default_rng(seed)
    top = SKIRT_H - SKIRT_CHAMFER          # v where the chamfer starts
    peel = noise(h, w, 2.2, 2.2, seed + 1)
    tone = noise(h, w, 0.25 / px_m, 0.04 / px_m, seed + 2)
    albedo = np.ones((h, w, 3)) * np.array(POWDER_BLACK) * (1 + 0.04 * tone)[..., None]
    rough = POWDER_ROUGH + 0.03 * peel + 0.02 * tone
    hgt = 0.000008 * peel
    # floor contact: grime and a little lint
    low = np.exp(-np.clip(v_m, 0.0, None) / 0.005)
    albedo = albedo * (1 - 0.10 * low)[..., None] + np.array(DUST) * (0.04 * low)[..., None]
    rough = rough + 0.12 * low
    # shoe scuffs: dull rubber smears (rougher, barely darker) and a few scrapes to bare metal
    scuff = _blobs(h, w, px_m, v_m, rng, 18, (0.04, 0.14), (0.006, 0.02), (0.01, 0.08))
    scuff *= np.clip(0.5 + 0.5 * noise(h, w, 0.03 / px_m, 0.002 / px_m, seed + 3), 0, 1)
    rough = rough + 0.18 * scuff
    albedo = albedo * (1 - 0.15 * scuff)[..., None]
    scrape = _scratches(h, w, px_m, v_m, rng, 10, (0.015, 0.07), (0.01, 0.085), 0.1)
    albedo = albedo + (np.array((0.42, 0.42, 0.43)) - albedo) * (0.35 * scrape)[..., None]
    rough = rough - 0.08 * scrape
    hgt = hgt - 0.00003 * scrape
    # dust on the chamfer and the ledge
    dust = smoothstep(v_m, top - 0.001, top + 0.002) * (0.7 + 0.3 * noise(h, w, 0.02 / px_m, 0.006 / px_m, seed + 4))
    albedo = albedo + (np.array(DUST) - albedo) * (0.12 * dust)[..., None]
    rough = rough + 0.2 * dust
    ao = 1.0 - 0.12 * low - 0.10 * smoothstep(v_m, top + 0.002, top + 0.006)
    return {"albedo": np.clip(albedo, 0, 1), "rough": np.clip(rough, 0.05, 1.0), "metal": 0.0,
            "height": hgt, "ao": np.clip(ao, 0, 1)}


def _panel(h, w, px_m, v_m, seed):
    """Anthracite matte laminate (fine linen emboss): low cart and bag scuffs, burnished and
    smudged where hands trail along under the rail, dust on the top edge in the reveal."""
    rng = np.random.default_rng(seed)
    face_top = PANEL_TOP - SKIRT_H          # v_m where the face ends and the slot floor begins
    z = v_m + SKIRT_H                       # height above the floor on the face
    emb_a = noise(h, w, 1.6, 0.7, seed + 1)
    emb_b = noise(h, w, 0.7, 1.6, seed + 2)
    emboss = 0.5 * (emb_a + emb_b)
    tone = noise(h, w, 0.35 / px_m, 0.20 / px_m, seed + 3)
    albedo = np.ones((h, w, 3)) * np.array(ANTHRACITE) * (1 + 0.035 * tone + 0.03 * emboss)[..., None]
    rough = LAMINATE_ROUGH + 0.025 * emboss + 0.015 * noise(h, w, 0.10 / px_m, 0.10 / px_m, seed + 4)
    hgt = 0.000012 * emboss
    # low scuffs: bags, cleaning carts (glossier burnish, slightly lighter) and fine scratches
    burn = _blobs(h, w, px_m, v_m, rng, 22, (0.06, 0.30), (0.01, 0.05), (0.04, 0.42))
    burn *= smoothstep(0.55 - z, 0.0, 0.2)
    rough = rough - 0.12 * burn
    albedo = albedo * (1 + 0.10 * burn)[..., None]
    scr = _scratches(h, w, px_m, v_m, rng, 26, (0.02, 0.14), (0.05, 0.48), 0.05)
    albedo = albedo + (np.array((0.10, 0.10, 0.10)) - albedo) * (0.35 * scr)[..., None]
    rough = rough - 0.05 * scr
    # hand zone under the rail: burnished band and a few greasy smudges
    hand = smoothstep(z, 0.80, 0.93) * (1 - smoothstep(z, PANEL_TOP - 0.004, PANEL_TOP))
    trail = np.clip(0.55 + 0.45 * noise(h, w, 0.30 / px_m, 0.03 / px_m, seed + 5), 0, 1)
    smudge = _blobs(h, w, px_m, v_m, rng, 16, (0.03, 0.08), (0.025, 0.06), (0.74, 0.86))
    rough = rough - 0.07 * hand * trail - 0.14 * smudge
    albedo = albedo * (1 - 0.04 * smudge)[..., None]
    # top of the panel (inside the reveal): dust; shadow under the cap
    in_slot = smoothstep(v_m, face_top - 0.0005, face_top + 0.001)
    dust = in_slot * (0.7 + 0.3 * noise(h, w, 0.02 / px_m, 0.004 / px_m, seed + 6))
    albedo = albedo + (np.array(DUST) - albedo) * (0.18 * dust)[..., None]
    rough = rough + 0.25 * dust
    # low grime above the skirting
    grime = np.exp(-np.clip(v_m, 0.0, None) / 0.01) * (0.6 + 0.4 * tone)
    albedo = albedo * (1 - 0.06 * grime)[..., None]
    ao = (1.0 - 0.10 * np.exp(-np.clip(v_m, 0.0, None) / 0.004)
          - 0.18 * smoothstep(v_m, face_top - 0.025, face_top) - 0.2 * in_slot)
    return {"albedo": np.clip(albedo, 0, 1), "rough": np.clip(rough, 0.05, 1.0), "metal": 0.0,
            "height": hgt, "ao": np.clip(ao, 0, 1)}


def _rail(h, w, px_m, v_m, seed):
    """Brushed dark bronze cap: brushing along the run, polished and smudged by hands on the
    front edge and the round-over, dust on the top against the wall, a few dings."""
    rng = np.random.default_rng(seed)
    under = (CAP_D - CAP_CHAMFER) - LED_TOP_S                    # underside arc (slot to front)
    front0 = under + CAP_CHAMFER * math.sqrt(2)
    front1 = front0 + (CAP_TOP - CAP_R) - (CAP_BOTTOM + CAP_CHAMFER)
    top0 = front1 + math.pi / 2 * CAP_R
    top1 = top0 + (CAP_D - CAP_R)
    brush = noise(h, w, 0.25 / px_m, 0.6, seed + 1)
    brush2 = noise(h, w, 0.04 / px_m, 0.9, seed + 2)
    tone = noise(h, w, 0.5 / px_m, 0.02 / px_m, seed + 3)
    albedo = np.ones((h, w, 3)) * np.array(BRONZE) * (1 + 0.05 * tone + 0.03 * brush)[..., None]
    rough = BRONZE_ROUGH + 0.03 * brush + 0.02 * brush2
    hgt = 0.000006 * brush + 0.000004 * brush2
    metal = np.ones((h, w))
    # hand polish: the front, the round-over and the front of the top
    pol = smoothstep(v_m, front0 + 0.01, top0) * (1 - smoothstep(v_m, top0 + 0.006, top0 + 0.02))
    pol = pol * np.clip(0.6 + 0.4 * noise(h, w, 0.4 / px_m, 0.01 / px_m, seed + 4), 0, 1)
    albedo = albedo + (np.array(BRONZE_POLISH) - albedo) * (0.5 * pol)[..., None]
    rough = rough - 0.08 * pol
    prints = _blobs(h, w, px_m, v_m, rng, 26, (0.015, 0.04), (0.008, 0.02), (front0 + 0.015, top0 + 0.01))
    prints *= np.clip(0.5 + 0.5 * noise(h, w, 1.5, 1.5, seed + 5), 0, 1)
    rough = rough + 0.12 * prints
    # dust on the top toward the wall
    dust = smoothstep(v_m, top0 + 0.012, top1 - 0.002) * (0.7 + 0.3 * noise(h, w, 0.03 / px_m, 0.005 / px_m, seed + 6))
    albedo = albedo + (np.array(DUST) - albedo) * (0.22 * dust)[..., None]
    rough = rough + 0.25 * dust
    metal = metal - 0.4 * dust
    # the underside (in the reveal) is unpolished and a little grimy
    low = 1 - smoothstep(v_m, under - 0.002, under + 0.001)
    albedo = albedo + (np.array(GRIME) - albedo) * (0.25 * low)[..., None]
    rough = rough + 0.08 * low
    # dings on the front edge
    dings = np.zeros((h, w))
    u = _u(w, px_m)
    for _ in range(9):
        uc, vc, r = rng.uniform(0, REPEAT), rng.uniform(front0, top0), rng.uniform(0.0008, 0.0018)
        du = (u - uc + REPEAT / 2) % REPEAT - REPEAT / 2
        dings += np.exp(-(du ** 2 + (v_m - vc) ** 2) / r ** 2)
    dings = np.clip(dings, 0, 1)
    hgt = hgt - 0.00006 * dings
    rough = rough + 0.06 * dings
    ao = 1.0 - 0.35 * low - 0.10 * smoothstep(v_m, top1 - 0.004, top1)
    return {"albedo": np.clip(albedo, 0, 1), "rough": np.clip(rough, 0.05, 1.0), "metal": np.clip(metal, 0, 1),
            "height": hgt, "ao": np.clip(ao, 0, 1)}


def _plain(h, w, px_m, v_m, seed):
    return {"albedo": np.ones((h, w, 3)) * np.array(POWDER_BLACK), "rough": 0.6, "metal": 0.0, "ao": 0.6}


def generate():
    """The filled sheet."""
    sheet = layout()
    sheet.fill("skirt", _skirt, seed=SEED)
    sheet.fill("panel", _panel, seed=SEED + 100)
    sheet.fill("rail", _rail, seed=SEED + 200)
    sheet.fill("plain", _plain, seed=SEED + 300)
    return sheet


# --- Sweep --------------------------------------------------------------------------------------
def segment_count(run):
    return len(run["points"]) - (0 if run["closed"] else 1)


def joints(lengths):
    """Groove positions per segment: every JOINT m along the run from its start, except within
    JOINT_CLEAR of a corner or an end. Returns ({segment: [t]}, skipped count)."""
    out, skipped = {}, 0
    total = sum(lengths)
    k = 1
    while k * JOINT < total - 1e-9:
        d = k * JOINT
        k += 1
        acc = 0.0
        for si, ln in enumerate(lengths):
            if d <= acc + ln + 1e-9:
                t = d - acc
                if JOINT_CLEAR <= t <= ln - JOINT_CLEAR:
                    out.setdefault(si, []).append(t)
                else:
                    skipped += 1
                break
            acc += ln
    return out, skipped


def end_caps(mesh, ring_at, normal, side):
    """Close an open end per region, each with its own band (the profile polygon is concave)."""
    regions = [
        ("skirt", [(0.0, 0.0), (SKIRT_D, 0.0), (SKIRT_D, SKIRT_H - SKIRT_CHAMFER), (SKIRT_D - SKIRT_CHAMFER, SKIRT_H),
                   (PANEL_D, SKIRT_H), (0.0, SKIRT_H)], 0.0),
        ("panel", [(0.0, SKIRT_H), (PANEL_D, SKIRT_H), (PANEL_D, PANEL_TOP), (0.0, PANEL_TOP)], SKIRT_H),
        ("rail", [(0.0, PANEL_TOP), (SLOT_BACK, PANEL_TOP), (LED_TOP_S, CAP_BOTTOM), (0.0, CAP_BOTTOM)], PANEL_TOP),
    ]
    pts, _, _ = profile()
    cap = [(0.0, CAP_BOTTOM)] + [p for p in pts[6:-1]]   # LED top .. top back edge
    regions.append(("rail", cap, CAP_BOTTOM))
    for band, poly, v0 in regions:
        mesh.poly([ring_at(s, v) for s, v in poly], band, side, normal,
                  v=[v - v0 for _, v in poly], u=[s for s, _ in poly])


def build(data, sheet, coll, materials):
    """One object for every run. Returns (object, report lines)."""
    from mathutils import Vector

    from corridor_common import to_blender

    pts, bands, moved = profile()
    plain = [k for k, b in enumerate(bands) if b == "plain"]
    mesh = TrimMesh(sheet, band_mats={"skirt": MAT, "panel": MAT, "rail": MAT, "plain": MAT, "led": MAT_LED})
    up = Vector((0, 0, 1))
    report, n_grooves, n_skipped = [], 0, 0
    for ri, run in enumerate(data["runs"]):
        path = [to_blender(p) for p in run["points"]]
        sides = [Vector((n[0], -n[1], 0.0)) for n in run["normals"]]
        n = len(path)
        nseg = segment_count(run)
        lengths = [(path[(i + 1) % n] - path[i]).length for i in range(nseg)]
        grooves, skipped = joints(lengths)
        n_grooves += sum(len(v) for v in grooves.values())
        n_skipped += skipped
        phase = (ri * 0.618034 % 1.0) * REPEAT        # each run shows its own part of the sheet
        offsets, acc = [], 0.0
        for ln in lengths:
            offsets.append(phase + acc)
            acc += ln
        mesh.polyline_sweep(path, pts, bands, up=(0.0, 0.0, 1.0), sides=sides, closed=run["closed"],
                            u_offsets=offsets, caps=(False, False), stretch=plain, grooves=grooves,
                            groove=(GROOVE_W, GROOVE_D, moved))
        if not run["closed"]:
            for p, seg, sign in ((path[0], 0, -1.0), (path[-1], nseg - 1, 1.0)):
                d = (path[(seg + 1) % n] - path[seg]).normalized()
                s_vec = sides[seg]
                mesh_ring = (lambda s, v, p=p, s_vec=s_vec: p + s_vec * s + up * v)
                end_caps(mesh, mesh_ring, d * sign, s_vec)
        report.append(f"RUN {ri}: {nseg} segments {', '.join(f'{x:.2f}' for x in lengths)} m, "
                      f"joints {sum(len(v) for v in grooves.values())} (+{skipped} at corners/ends)")
    ob = mesh.to_object("CorridorTrim", coll, materials, sharp_angle=35.0)
    report.append(f"GROOVES {n_grooves} (skipped {n_skipped} within {JOINT_CLEAR} m of a corner or end)")
    return ob, report


def led_material():
    from arcology_blender.shading import solid_mat
    return solid_mat(MAT_LED, (0.80, 0.82, 0.82), 0.35, 0.0, LED_CYAN, LED_STRENGTH)
