"""Stage 1: build every window of a spec (frame, sash, shade bars) and the kit
(wall panel, button), with trim-sheet UVs and the final material slots; save
the .blend. Textures come in bake.py.

  blender -b --factory-startup --python blender/architecture/windows/build.py [-- --spec tools/props/windows/apartment.json]

All geometry is authored in each window's local Godot frame (see
windows_common.py) and converted by the TrimMesh basis.
"""

import math
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from windows_common import (  # noqa: E402  (first: puts blender/lib on the path)
    DESIGN, GODOT, LED_STRENGTH, MAT_LED, MAT_PANEL_LED, MAT_STATUS, MAT_TRIM, PANEL_LED_STRENGTH, STATUS_COLOR,
    STATUS_STRENGTH, TRIM_PX_PER_M, TRIM_SIZE, blend_path, load_spec, windows,
)
import window_trim  # noqa: E402
from arcology_blender.curves import rounded_rect_profile  # noqa: E402
from arcology_blender.geo import new_empty  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag, tri_count  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.trim import GODOT_TO_BLENDER, TrimMesh  # noqa: E402

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
D = DESIGN
C = D["chamfer"]
BAND_MATS = {"led": MAT_LED, "status": MAT_STATUS, "panel_led": MAT_PANEL_LED}


def gb(p):
    """Godot point -> Blender."""
    return GODOT_TO_BLENDER @ Vector(p)


def metal_band(n):
    """Frame finish by face normal (Godot frame): dust on top, weathered outside."""
    n = Vector(n).normalized()
    if n.y > 0.7:
        return "metal_dust"
    if n.z < -0.7:
        return "metal_ext"
    return "metal"


def u_offset(name):
    """Per-part U offset so neighbors don't repeat the same streaks and veins."""
    return (zlib.crc32(name.encode()) % 1000) / 1000.0 * 2.0


def materials():
    trim = bpy.data.materials.get(MAT_TRIM) or solid_mat(MAT_TRIM, (0.08, 0.07, 0.06), 0.35, 1.0)
    return {
        "trim": trim,
        MAT_LED: solid_mat(MAT_LED, (0.9, 0.9, 0.9), 0.35, 0.0, (1.0, 1.0, 1.0), LED_STRENGTH),
        MAT_STATUS: solid_mat(MAT_STATUS, (0.01, 0.01, 0.01), 0.2, 0.0, STATUS_COLOR, STATUS_STRENGTH),
        MAT_PANEL_LED: solid_mat(MAT_PANEL_LED, (0.9, 0.9, 0.9), 0.3, 0.0, (1.0, 1.0, 1.0), PANEL_LED_STRENGTH),
    }


def tmesh(sheet, name, origin_godot=(0.0, 0.0, 0.0)):
    return TrimMesh(sheet, GODOT_TO_BLENDER, gb(origin_godot), band_mats=BAND_MATS, u_offset=u_offset(name))


def slotted_face(tm, y, x0, x1, z0, z1, slots, slot_z, depth):
    """Downward sightline face at height y (x0..x1, z0..z1) with shade slots
    (list of (xa, xb)) at slot_z, each a black pocket `depth` high."""
    s0, s1 = slot_z
    xcuts = sorted({x0, x1} | {x for sx in slots for x in sx})

    def cell(x, z):
        return None if (s0 < z < s1 and any(a < x < b for a, b in slots)) else "metal"

    tm.grid((0, y, 0), X, Z, xcuts, [z0, s0, s1, z1], cell, -Y, along=X)
    yp = y + depth
    for a, b in slots:
        tm.poly([(a, y, s0), (b, y, s0), (b, yp, s0), (a, yp, s0)], "black_matte", X, Z)
        tm.poly([(a, y, s1), (b, y, s1), (b, yp, s1), (a, yp, s1)], "black_matte", X, -Z)
        tm.poly([(a, yp, s0), (b, yp, s0), (b, yp, s1), (a, yp, s1)], "black_matte", X, -Y)
        tm.poly([(a, y, s0), (a, yp, s0), (a, yp, s1), (a, y, s1)], "black_matte", Z, X)
        tm.poly([(b, y, s0), (b, yp, s0), (b, yp, s1), (b, y, s1)], "black_matte", Z, -X)


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------
def frame_profile(w):
    """Outer frame member (inset from the opening edge, z): exterior face,
    sightline face, interior face, all edges chamfered; back against the wall."""
    ff, z0, z1 = w.ff, w.z0, w.z1
    return [(0.0, z0), (ff - C, z0), (ff, z0 + C), (ff, z1 - C), (ff - C, z1), (0.0, z1)]


FRAME_BANDS = [metal_band, "edge", metal_band, "edge", metal_band, "metal"]


def mullion_profile(w):
    h, z0, z1 = w.mf / 2, w.z0, w.z1
    return [(-h + C, z0), (h - C, z0), (h, z0 + C), (h, z1 - C), (h - C, z1), (-h + C, z1), (-h, z1 - C),
            (-h, z0 + C)]


def gasket_lips(tm, rect, gz):
    """EPDM lips on both sides of the glass plane around a glass rectangle."""
    p, g, t = D["gasket_protrude"], D["gasket_gap"], D["gasket_t"]
    r = 0.0012
    room = [(0.0, gz + g), (p, gz + g), (p, gz + g + t - r), (p - r, gz + g + t), (0.0, gz + g + t)]
    out = [(0.0, gz - g - t), (p - r, gz - g - t), (p, gz - g - t + r), (p, gz - g), (0.0, gz - g)]
    for prof in (room, out):
        tm.rect_sweep(rect, prof, ["rubber"] * 4, closed=False)


def build_frame(w, sheet, coll, mats):
    tm = tmesh(sheet, w.name)
    W, B, T = w.W, w.B, w.T
    z0, ze = w.z0, w.ze

    # outer frame, mitered around the opening; the head rail's sightline face
    # is built separately with the shade slots
    tm.rect_sweep((-W / 2, W / 2, B, T), frame_profile(w), FRAME_BANDS, stretch=(1, 3), skip=(("T", 2),))
    slots = [w.slot_x(i) for i in range(w.n) if w.shade and i != w.vent_bay]
    slotted_face(tm, w.y1, -W / 2 + w.ff, W / 2 - w.ff, z0 + C, w.z1 - C, slots, w.slot_z, D["slot_depth"])
    # mullions between the bays
    for k in range(w.n - 1):
        tm.extrude(mullion_profile(w), (w.mullion_x(k), w.y0, 0.0), X, Z, Y, w.ch,
                   [metal_band, "edge"] * 4, stretch=(1, 3, 5, 7))
    # glazing gaskets (fixed bays) / sash stop with its seal (vent bay)
    for i in range(w.n):
        x0, x1 = w.bay_x(i)
        rect = (x0, x1, w.y0, w.y1)
        if i == w.vent_bay:
            si, sd = D["stop_inset"], D["stop_depth"]
            stop = [(0.0, z0), (si - C, z0), (si, z0 + C), (si, z0 + sd - C), (si - C, z0 + sd), (0.0, z0 + sd)]
            tm.rect_sweep(rect, stop, [metal_band, "edge", metal_band, "edge", "metal"], closed=False,
                          stretch=(1, 3))
            seal = [(0.010, z0 + sd), (0.010, z0 + sd + 0.003), (0.002, z0 + sd + 0.003), (0.002, z0 + sd)]
            tm.rect_sweep(rect, seal, ["rubber"] * 3, closed=False)
        else:
            gasket_lips(tm, rect, w.gz)

    # exterior reveal (only if the frame sits back from the facade)
    if z0 - ze > 0.001:
        tm.rect_sweep((-W / 2, W / 2, B, T), [(0.0, ze), (0.003, ze), (0.003, z0)], ["metal_ext"] * 2,
                      closed=False)

    build_reveal(w, tm)
    build_sill(w, tm)
    build_flashing(w, tm)

    ob = tm.to_object(f"{w.name}_frame", coll, mats)
    tag(ob, f"frame:{w.name}")
    return ob


def build_reveal(w, tm):
    """Jamb liners with the LED returns, head cassette with the LED channel and
    the sensor strip."""
    W, T = w.W, w.T
    z1, zi = w.z1, w.zi
    TL, DR, L = D["liner"], D["led_depth"], D["led_return"]
    hy = w.head_y
    l0, l1 = w.led_z
    ys = w.sill_y
    L = min(L, 0.25 * (hy - ys))
    xa, xb = -W / 2 + TL, W / 2 - TL
    zg = z1 + D["shadow_gap"]  # the liners stand off the frame: a crisp dark line around it
    # the shadow gap's floor (covers the wall's cut faces behind it)
    tm.poly([(-W / 2, T - 0.001, z1), (W / 2, T - 0.001, z1), (W / 2, T - 0.001, zg), (-W / 2, T - 0.001, zg)],
            "black_matte", X, -Y)
    tm.poly([(xa, hy, zg), (xb, hy, zg), (xb, T, zg), (xa, T, zg)], "reveal", X, -Z)

    for s in (-1, 1):  # west jamb (s = -1), east jamb
        xf = s * (W / 2 - TL)          # visible face
        xd = s * (W / 2 - TL + DR)     # LED diffuser (recessed into the liner)
        nrm = Vector((-s, 0, 0))
        xg = s * (W / 2 - 0.001)
        tm.poly([(xg, ys, z1), (xg, T, z1), (xg, T, zg), (xg, ys, zg)], "black_matte", Y, nrm)
        tm.poly([(s * W / 2, ys, zg), (xf, ys, zg), (xf, T, zg), (s * W / 2, T, zg)], "reveal", Y, -Z)

        def cell(y, z):
            return None if (hy - L < y < hy and l0 < z < l1) else "reveal"

        tm.grid((xf, 0, 0), Y, Z, [ys, hy - L, hy], [zg, l0, l1, zi - C], cell, nrm, along=Y)
        # room edge: chamfer up to the soffit, front face to the top
        xe = s * (W / 2 - TL + C)
        tm.poly([(xf, ys, zi - C), (xf, hy, zi - C), (xe, hy, zi), (xe, ys, zi)], "edge", Y,
                Vector((-s, 0, 1)), stretch=True)
        tm.poly([(xf, hy, zi - C), (xe, hy, zi), (xf, hy, zi)], "edge", X, Vector((0, -1, 0)), stretch=True)
        tm.poly([(xe, ys, zi), (xe, hy, zi), (s * W / 2, hy, zi), (s * W / 2, ys, zi)], "reveal", Y, Z)
        tm.poly([(xf, hy, zi), (xf, T, zi), (s * W / 2, T, zi), (s * W / 2, hy, zi)], "reveal", Y, Z)
        # LED return recess
        yb, yt = hy - L, hy + DR
        tm.poly([(xf, yb, l0), (xf, yt, l0), (xd, yt, l0), (xd, yb, l0)], "reveal", Y, Z)
        tm.poly([(xf, yb, l1), (xf, yt, l1), (xd, yt, l1), (xd, yb, l1)], "reveal", Y, -Z)
        tm.poly([(xf, yb, l0), (xd, yb, l0), (xd, yb, l1), (xf, yb, l1)], "reveal", X, Y)
        tm.poly([(xd, yb, l0), (xd, yt, l0), (xd, yt, l1), (xd, yb, l1)], "led", Y, nrm)

    # head cassette soffit: LED channel and a flush black-glass sensor strip
    e0, e1 = w.sensor_z
    sl = D["sensor_len"] / 2

    def soffit(x, z):
        if l0 < z < l1:
            return None
        if e0 < z < e1 and -sl < x < sl:
            return "black_gloss"
        return "reveal"

    tm.grid((0, hy, 0), X, Z, [xa, -sl, sl, xb], [zg, e0, e1, l0, l1, zi - C], soffit, -Y, along=X)
    tm.poly([(xa, hy, zi - C), (xb, hy, zi - C), (xb, hy + C, zi), (xa, hy + C, zi)], "edge", X,
            Vector((0, -1, 1)), stretch=True)
    tm.poly([(xa, hy + C, zi), (xb, hy + C, zi), (xb, T, zi), (xa, T, zi)], "reveal", X, Z)
    # LED channel in the head
    yt = hy + DR
    tm.poly([(xa, hy, l0), (xb, hy, l0), (xb, yt, l0), (xa, yt, l0)], "reveal", X, Z)
    tm.poly([(xa, hy, l1), (xb, hy, l1), (xb, yt, l1), (xa, yt, l1)], "reveal", X, -Z)
    tm.poly([(xa - DR, yt, l0), (xb + DR, yt, l0), (xb + DR, yt, l1), (xa - DR, yt, l1)], "led", X, -Y)
    # status LED: a tiny disc at the sensor strip's east end, 0.3 mm proud
    cx, cz, r = sl - 0.012, (e0 + e1) / 2, D["status_r"]
    disc = [(cx + r * math.cos(2 * math.pi * k / 12), hy - 0.0003, cz + r * math.sin(2 * math.pi * k / 12))
            for k in range(12)]
    tm.poly(disc, "status", X, -Y)


def build_sill(w, tm):
    W, B = w.W, w.B
    z1, zi, ze, ov = w.z1, w.zi, w.ze, w.ov
    TL = D["liner"]
    if w.sill == "stone":
        # a through-wall slab (Godot: SILL_T, SILL_EARS): top exactly at `bottom`,
        # the room-side nose with ears past the opening
        ys, yb = B, B - GODOT["sill_t"]
        xe = W / 2 + GODOT["sill_ears"]
        r, r2 = D["stone_round"], D["stone_round_low"]
        zf = zi + ov
        prof = [(zi, yb), (zf - r2, yb)]
        prof += [(zf - r2 + r2 * math.sin(math.radians(a)), yb + r2 - r2 * math.cos(math.radians(a)))
                 for a in (45, 90)]
        prof += [(zf - r + r * math.cos(math.radians(a)), ys - r + r * math.sin(math.radians(a)))
                 for a in (0, 22.5, 45, 67.5, 90)]
        prof += [(zi, ys)]
        bands = ["stone"] * (len(prof) - 2) + ["stone_top"]
        tm.extrude(prof, (-xe, 0, 0), Z, Y, X, 2 * xe, bands, closed=False)
        for s in (-1, 1):  # nose ends
            tm.poly([(s * xe, y, z) for z, y in prof], "stone", Z, Vector((s, 0, 0)))
        # top inside the opening, V continuing from the nose's top
        v0 = zf - r - zi
        tm.poly([(-W / 2, ys, zi), (W / 2, ys, zi), (W / 2, ys, z1), (-W / 2, ys, z1)], "stone_top", X, Y,
                v=[v0, v0, v0 + zi - z1, v0 + zi - z1])
        # outside: the slab's end grain flush with the facade (under the flashing)
        z_out = max(ze, min(w.z0, ze))
        tm.poly([(-W / 2, yb, z_out), (W / 2, yb, z_out), (W / 2, ys, z_out), (-W / 2, ys, z_out)], "stone", X, -Z)
        if w.z0 - ze > 0.001:
            tm.poly([(-W / 2, ys, ze), (W / 2, ys, ze), (W / 2, ys, w.z0), (-W / 2, ys, w.z0)], "stone_top", X, Y)
    else:  # floor: flush metal threshold with a drain channel
        t, tb = w.sill_y, B - D["threshold_below"]
        c2 = 0.002
        zc = (z1 + zi) / 2
        cz0, cz1 = zc - D["channel_w"] / 2, zc + D["channel_w"] / 2
        cd = D["channel_d"]
        flat = [(zi, tb), (zi, t - c2), (zi - c2, t), (z1, t)]
        chan = [(zi, tb), (zi, t - c2), (zi - c2, t), (cz1, t), (cz1, t - cd), (cz0, t - cd), (cz0, t), (z1, t)]
        xa, xb = -W / 2 + TL, W / 2 - TL
        tm.extrude(flat, (-W / 2, 0, 0), Z, Y, X, TL, ["threshold", "edge", "threshold"], closed=False,
                   stretch=(1,))
        tm.extrude(flat, (xb, 0, 0), Z, Y, X, TL, ["threshold", "edge", "threshold"], closed=False, stretch=(1,))
        tm.extrude(chan, (xa, 0, 0), Z, Y, X, xb - xa,
                   ["threshold", "edge", "threshold", "metal", "black_matte", "metal", "threshold"],
                   closed=False, stretch=(1,))
        for x, n in ((xa, X), (xb, -X)):  # channel ends under the jamb liners
            tm.poly([(x, t - cd, cz0), (x, t - cd, cz1), (x, t, cz1), (x, t, cz0)], "metal", Z, n)


def build_flashing(w, tm):
    """Exterior sill flashing: sloped top, drip face, kick-out lip."""
    W, B = w.W, w.B
    zs = w.z0
    zf = w.ze - D["flashing_proj"]
    y1 = B - D["flashing_drop"]
    fh, ts, fe = D["flashing_face"], D["flashing_t"], D["flashing_ext"]
    prof = [(zs, B), (zf, y1), (zf, y1 - fh), (zf + ts, y1 - fh), (zf + ts, y1 - ts), (zs, B - ts)]
    x0 = -W / 2 - fe
    tm.extrude(prof, (x0, 0, 0), Z, Y, X, W + 2 * fe, ["flashing"] * 2 + ["metal_ext"] * 3, closed=False)
    for s in (-1, 1):
        x = s * (W / 2 + fe)
        n = Vector((s, 0, 0))
        tm.poly([(x, B, zs), (x, y1, zf), (x, y1 - ts, zf + ts), (x, B - ts, zs)], "flashing", Z, n)
        tm.poly([(x, y1, zf), (x, y1 - fh, zf), (x, y1 - fh, zf + ts), (x, y1 - ts, zf + ts)], "flashing", Z, n)


# ---------------------------------------------------------------------------
# Tilt sash (vent) with its lever handle and the vent shade's slot
# ---------------------------------------------------------------------------
def build_sash(w, sheet, coll, mats):
    hinge = w.hinge
    tm = tmesh(sheet, w.name + "_sash", hinge)
    gr = w.glass_rect(w.vent_bay)
    sf, g = w.sf, D["sash_gap"]
    a, b = w.sz0, w.sz1
    prof = [(-sf + C, a), (-C, a), (0.0, a + C), (0.0, b - C), (-C, b), (-sf + C, b), (-sf, b - C), (-sf, a + C)]
    outer = lambda i: g if i <= -sf + C + 1e-9 else 0.0  # noqa: E731  gap on the outer edge only
    tm.rect_sweep(gr, prof, [metal_band, "edge"] * 4, side_offset=(outer, outer, 0.0, outer),
                  stretch=(1, 3, 5, 7), skip=(("T", 2),))
    slots = [w.slot_x(w.vent_bay)] if w.shade else []
    slotted_face(tm, gr[3], gr[0], gr[1], a + C, b - C, slots, w.slot_z, D["slot_depth"])
    gasket_lips(tm, gr, w.gz)
    grip = build_handle(w, tm)

    ob = tm.to_object(f"{w.name}_sash", coll, mats)
    ob.location = gb(hinge)
    tag(ob, f"sash:{w.name}")
    tag(new_empty("HandleGrip", coll, gb(grip) - gb(hinge), parent=ob, size=0.02), f"sash:{w.name}")
    return ob


def build_handle(w, tm):
    """Lever handle on the sash's room face (z = sash_z[1]): rosette, hub and
    a lever hanging down; returns the grip point (Godot, window frame)."""
    hx, hy, z = w.handle_x, w.handle_y, w.sz1
    yp = hy + 0.065  # pivot above the grip
    rr = lambda wd, ht, r: [(hx + u, yp + v) for u, v in rounded_rect_profile(wd, ht, r, 3)]  # noqa: E731
    r0 = [(x, y, z) for x, y in rr(0.026, 0.064, 0.006)]
    r1 = [(x, y, z + 0.0055) for x, y in rr(0.026, 0.064, 0.006)]
    r2 = [(x, y, z + 0.0070) for x, y in rr(0.023, 0.061, 0.0045)]
    tm.loft([r0, r1, r2], ["handle", "edge"], Y, cap_end="handle")
    n = 24
    circ = lambda r, zz: [(hx + r * math.cos(2 * math.pi * k / n), yp + r * math.sin(2 * math.pi * k / n), zz)  # noqa: E731
                          for k in range(n)]
    tm.loft([circ(0.011, z + 0.007), circ(0.011, z + 0.027), circ(0.0098, z + 0.0298), circ(0.0085, z + 0.0305)],
            ["handle", "edge", "handle"], Y, cap_end="handle")
    # lever arm: rounded section 16 x 12 mm tapering to 14 x 11, bending out at the tip
    ts = [0.0, 0.12, 0.25, 0.4, 0.55, 0.68, 0.8, 0.9, 1.0]
    length = 0.100
    zc = z + 0.023
    path = [Vector((hx, yp - length * t, zc + 0.006 * max(0.0, (t - 0.55) / 0.45) ** 2)) for t in ts]
    rings = []
    for k, (p, t) in enumerate(zip(path, ts)):
        tan = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
        vv = tan.cross(X).normalized()
        wdt, thk = 0.016 - 0.002 * t, 0.012 - 0.001 * t
        rings.append([p + X * u + vv * v for u, v in rounded_rect_profile(wdt, thk, 0.0045, 3)])
    tip = path[-1]
    rt = [tip + (q - tip) * 0.82 + (path[-1] - path[-2]).normalized() * 0.0022 for q in rings[-1]]
    tm.loft(rings + [rt], ["handle"] * (len(rings) - 1) + ["edge"], Y, cap_end="handle", center="rings")
    return (hx, hy, zc)


# ---------------------------------------------------------------------------
# Shade bottom bar, origin at its top center
# ---------------------------------------------------------------------------
def bar_profile():
    """Section (z, y) around the bar's center line, top at y = 0: flat bottom,
    rounded top, counter-clockwise."""
    d, h = D["bar_d"], D["bar_h"]
    rb, rt = 0.0015, 0.0045
    pts = []
    for cz, cy, a0, r in ((d / 2 - rb, -h + rb, 270, rb), (d / 2 - rt, -rt, 0, rt), (-d / 2 + rt, -rt, 90, rt),
                          (-d / 2 + rb, -h + rb, 180, rb)):
        for k in range(4):
            a = math.radians(a0 + 90 * k / 3)
            pts.append((cz + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def build_bar(w, bay, sheet, coll, mats, vent=False):
    top = w.shade_top(bay)
    xc = top[0]
    L, cap = w.shade_width(bay), D["bar_cap"]
    label = f"{w.name}_shade_bar{'_vent' if vent else ''}"
    tm = tmesh(sheet, label, top)
    prof = [(top[2] + a, top[1] + b) for a, b in bar_profile()]
    tm.extrude(prof, (xc - L / 2 + cap, 0, 0), Z, Y, X, L - 2 * cap, ["metal"] * len(prof))
    yc = top[1] - D["bar_h"] / 2
    for s in (-1, 1):
        xe = xc + s * (L / 2 - cap)
        ring = lambda x, k: [(x, yc + (b - yc) * k, top[2] + (a - top[2]) * k) for a, b in prof]  # noqa: E731
        rings = [ring(xe, 1.0), ring(xe + s * (cap - 0.0012), 1.0), ring(xe + s * cap, 0.86)]
        tm.loft(rings, ["rubber", "rubber"], X, cap_end="rubber")
    ob = tm.to_object(label, coll, mats)
    ob.location = gb(top)
    tag(ob, f"{'barvent' if vent else 'bar'}:{w.name}")
    return ob


# ---------------------------------------------------------------------------
# Kit: wall panel (70 x 140 mm) with two button recesses and icons, and the button cap
# ---------------------------------------------------------------------------
PANEL = dict(w=0.070, h=0.140, r=0.004, side=0.0055, face=0.0070, button_y=0.035,
             ring=(0.0126, 0.0142), recess_r=0.0120, recess_floor=0.0008, cap_back=0.0050,
             cap_r=0.0106, cap_h=0.0030, icon_y=0.058, icon=0.010)
PANEL_SHOW = Vector((4.0, 0.0, 1.2))  # where the kit sits in the .blend (exported at the origin)


def rr_loop(w, h, r, z, cs=3):
    """Rounded rectangle loop (x, y, z) with extra points at the middle of each
    edge (so faces can split there without T-junctions), counter-clockwise."""
    base = rounded_rect_profile(w, h, max(r, 1e-4), cs)
    out = []
    n = len(base)
    for k in range(n):
        out.append(base[k])
        if k % (cs + 1) == cs:  # end of a corner arc: add the edge midpoint
            a, b = base[k], base[(k + 1) % n]
            out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    return [(x, y, z) for x, y in out]


def panel_icons(tm, P):
    """Emissive icons (panel_led) on the glass: a half-lowered shade above the
    top button, a half-filled circle (tint) below the bottom one."""
    z = P["face"] + 0.00015
    s, k = P["icon"] / 2, 0.0011  # half size, stroke
    cy = P["icon_y"]
    rect = lambda x0, x1, y0, y1: [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]  # noqa: E731
    for q in (rect(-s, s, cy + s - k, cy + s), rect(-s, s, cy - s, cy - s + k), rect(-s, -s + k, cy - s + k, cy + s - k),
              rect(s - k, s, cy - s + k, cy + s - k), rect(-s + k + 0.0008, s - k - 0.0008, cy + 0.0004, cy + s - k - 0.0008)):
        tm.poly(q, "panel_led", X, Z)
    cy = -P["icon_y"]
    n = 32
    ring = lambda rad: [(rad * math.cos(2 * math.pi * j / n), cy + rad * math.sin(2 * math.pi * j / n), z)  # noqa: E731
                        for j in range(n)]
    tm.loft([ring(s - k), ring(s)], ["panel_led"], X, center=(0, cy, z - 0.01))
    half = [(0.0, cy - (s - k - 0.0008), z)] + [
        ((s - k - 0.0008) * math.cos(math.radians(a)), cy + (s - k - 0.0008) * math.sin(math.radians(a)), z)
        for a in range(90, 271, 15)]
    tm.poly(half[1:], "panel_led", X, Z)


def build_panel(sheet, coll, mats):
    P = PANEL
    tm = TrimMesh(sheet, GODOT_TO_BLENDER, band_mats=BAND_MATS, u_offset=0.37)
    w, h, r = P["w"], P["h"], P["r"]
    L0 = rr_loop(w, h, r, 0.0)
    L1 = rr_loop(w, h, r, P["side"])
    L2 = rr_loop(w - 0.0024, h - 0.0024, r - 0.0012, P["face"] - 0.0003)
    L3 = rr_loop(w - 0.005, h - 0.005, 0.0015, P["face"] - 0.0003)
    L4 = rr_loop(w - 0.005, h - 0.005, 0.0015, P["face"])
    tm.loft([L0, L1, L2, L3, L4], ["metal", "edge", "metal", "edge"], Y, cap_start="metal")
    top = [p for p in L4 if p[1] >= -1e-9]
    bot = [p for p in L4 if p[1] <= 1e-9]
    ring_in, ring_out = P["ring"]
    for half, sy in ((top, 1), (bot, -1)):
        cy = sy * P["button_y"]
        n = 32
        circ = lambda rad, zz: [(rad * math.cos(2 * math.pi * k / n), cy + rad * math.sin(2 * math.pi * k / n), zz)  # noqa: E731
                                for k in range(n)]
        tm.bridge(circ(ring_out, P["face"]), half, "black_gloss", Y, Z, (0, cy, P["face"]))
        tm.loft([circ(ring_in, P["face"]), circ(ring_out, P["face"])], ["panel_led"], Y,
                center=(0, cy, P["face"] - 0.01))
        rz = P["face"] - 0.0006
        tm.loft([circ(ring_in, P["face"]), circ(P["recess_r"], rz), circ(P["recess_r"], P["recess_floor"])],
                ["edge", "metal"], Y, center=(0, cy, P["face"] + 0.02))
        tm.poly(circ(P["recess_r"], P["recess_floor"]), "black_matte", Y, Z)
    panel_icons(tm, P)
    ob = tm.to_object("window_panel", coll, mats)
    ob.location = PANEL_SHOW
    tag(ob, "panel")
    for name, sy in (("ButtonTop", 1), ("ButtonBottom", -1)):
        e = new_empty(name, coll, gb((0.0, sy * P["button_y"], P["cap_back"])), parent=ob, size=0.01)
        tag(e, "panel")
    return ob


def build_button(sheet, coll, mats):
    P = PANEL
    tm = TrimMesh(sheet, GODOT_TO_BLENDER, band_mats=BAND_MATS, u_offset=0.81)
    n = 32
    r, hh = P["cap_r"], P["cap_h"]
    circ = lambda rad, zz: [(rad * math.cos(2 * math.pi * k / n), rad * math.sin(2 * math.pi * k / n), zz)  # noqa: E731
                            for k in range(n)]
    rings = [circ(r, 0.0), circ(r, hh - 0.0008), circ(r - 0.0004, hh - 0.0002), circ(r - 0.0010, hh),
             circ(r - 0.0022, hh), circ(0.0045, hh - 0.00025), circ(0.0, hh - 0.0004)]
    tm.loft(rings, ["handle", "edge", "edge", "edge", "edge", "edge"], X, cap_start="handle",
            center=(0, 0, -0.01))
    ob = tm.to_object("window_panel_button", coll, mats)
    ob.location = PANEL_SHOW + gb((0.0, P["button_y"], P["cap_back"]))
    tag(ob, "button")
    return ob


def main():
    path, data = load_spec()
    print("SPEC", path)
    clear_scene()
    sheet = window_trim.layout(TRIM_SIZE, TRIM_PX_PER_M)
    mats = materials()
    report = []
    for w in windows(data):
        w.check_fits()
        coll = get_collection(f"win_{w.name}")
        f = build_frame(w, sheet, coll, mats)
        parts = [f"frame={tri_count(f)}"]
        if w.vent:
            s = build_sash(w, sheet, coll, mats)
            parts.append(f"sash={tri_count(s)}")
        if w.shade:
            fixed = [i for i in range(w.n) if i != w.vent_bay]
            if fixed:
                parts.append(f"bar={tri_count(build_bar(w, fixed[0], sheet, coll, mats))}")
            if w.vent:
                parts.append(f"bar_vent={tri_count(build_bar(w, w.vent_bay, sheet, coll, mats, vent=True))}")
        report.append(f"TRIS {w.name}: " + " ".join(parts))
    kit = get_collection("kit")
    p = build_panel(sheet, kit, mats)
    btn = build_button(sheet, kit, mats)
    report.append(f"TRIS kit: panel={tri_count(p)} button={tri_count(btn)}")
    print("\n".join(report))
    save_blend(blend_path(path))


if __name__ == "__main__":
    main()
