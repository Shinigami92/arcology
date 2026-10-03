"""Silena's utility belt and what hangs on it (stage 3), and the thigh holster strap.

- `Belt` (rigid on Hips): a wide black leather belt sitting on the hips (lower at the
  front), a gunmetal frame buckle with its prong, the belt's end through a keeper,
  two pouches with snap flaps (her left and right front), a row of five vials in
  elastic loops on a leather backing (left of the buckle).
- `Hangers` (Hips, the lower parts partly on her right thigh so they ride along when it
  swings): handcuffs on a D-ring clip, the maglock passkey on a leather tab with its
  violet strip (own material `SilenaPasskeyGlow`, faces with region H_GLOW).
- `ThighStrap` (right thigh; the drop strap blends from Hips): a band around the right
  thigh with a buckle and the strap down from the belt.

Items are built in a local frame on the belt (x along the belt toward her left, y out
of the body, z up) and placed with `BeltRing.frame(deg, z)`. Per-vertex `region`
(H_*) picks the sub-material in outfit_materials.py; `hu`, `hv` are item-local
coordinates (m) for stitching and holes.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from silena_vesper_common import BELT_FRONT_DROP, BELT_Z
from arcology_blender import curves, garment, soft

AXIS_Y = -0.045
BELT_W = 0.055
BELT_T = 0.0042
BELT_GAP = 0.0022            # over the top / trousers
COLUMNS = 72
H_LEATHER, H_METAL, H_GLASS, H_POLY, H_ELASTIC, H_GLOW, H_STRAP = range(7)
ATTRS = ("region", "hu", "hv")

BUCKLE_DEG = 4.0
TONGUE_DEGS = (6.0, 21.0)
KEEPER_DEG = 14.0
VIALS_DEG = 33.0
POUCH_DEGS = (62.0, -60.0)
CUFFS_DEG = -26.0
PASSKEY_DEG = -11.0
DROP_DEG = -98.0
THIGH_Z = 0.715
THIGH_W = 0.034


def smoothstep(x, a, b):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def dir_h(deg):
    t = math.radians(deg)
    return Vector((math.sin(t), -math.cos(t), 0.0))


def _farthest(bvh, origin, d, max_r=0.5):
    best, start, r0 = None, origin, 0.0
    for _ in range(8):
        h = bvh.ray_cast(start, d, max_r - r0)
        if h[0] is None:
            break
        best = h[0]
        r0 = (h[0] - origin).length + 1e-5
        start = origin + d * r0
    return best


class Builder:
    """A bmesh with the item attributes; `add(bm2, matrix, region)` merges a part."""

    def __init__(self):
        self.bm = bmesh.new()
        self.L = {a: self.bm.verts.layers.float.new(a) for a in ATTRS}

    def add(self, part, matrix, region, uv=None):
        L = self.L
        vmap = {}
        for v in part.verts:
            w = self.bm.verts.new(matrix @ v.co)
            w[L["region"]] = float(region)
            u = uv(v.co) if uv else (v.co.x, v.co.z)
            w[L["hu"]], w[L["hv"]] = u
            vmap[v] = w
        for f in part.faces:
            try:
                self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
        part.free()

    def to_object(self, name, collection):
        bm = self.bm
        bm.normal_update()
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        for p in me.polygons:
            p.use_smooth = True
        return ob


def _shade_flat_regions(ob, regions):
    """Hard metal edges: flat shading for faces whose vertices are all in `regions`."""
    reg = ob.data.attributes["region"].data
    for p in ob.data.polygons:
        if all(round(reg[i].value) in regions for i in p.vertices):
            p.use_smooth = False


# --- the belt ring ----------------------------------------------------------------------------
class BeltRing:
    """Frames around the hips on the outer garment surface (top + trousers BVH)."""

    def __init__(self, bvh):
        self.bvh = bvh
        self.rows = []
        for k in range(COLUMNS):
            self.rows.append(self.section(360.0 * k / COLUMNS))

    @staticmethod
    def center_z(deg):
        front = max(0.0, math.cos(math.radians(deg)))
        return 0.5 * (BELT_Z[0] + BELT_Z[1]) - BELT_FRONT_DROP * front ** 1.5

    def section(self, deg):
        zc = self.center_z(deg)
        d = dir_h(deg)
        pts = []
        for z in (zc - BELT_W * 0.5, zc - BELT_W * 0.25, zc, zc + BELT_W * 0.25, zc + BELT_W * 0.5):
            o = Vector((0.0, AXIS_Y, z))
            h = _farthest(self.bvh, o, d)
            pts.append(h if h is not None else o + d * 0.15)
        bot, top = pts[0], pts[-1]
        # the belt is stiff: it spans straight from bottom to top, held off the body (and off
        # the hip's bulge between its edges)
        up = (top - bot).normalized()
        out = d - up * d.dot(up)
        out.normalize()
        mid = (bot + top) * 0.5
        bulge = max(0.0, max((p - mid).dot(out) for p in pts))
        center = mid + out * (bulge + BELT_GAP + BELT_T * 0.5)
        return center, up, out

    def frame(self, deg, dz=0.0, lift=0.0):
        """Matrix of a local item frame on the belt's outer face at azimuth `deg`."""
        center, up, out = self.section(deg)
        x = out.cross(up).normalized()              # along the belt (toward her right): x, out, up is right-handed
        o = center + out * (BELT_T * 0.5 + lift) + up * dz
        m = Matrix((x, out, up)).transposed().to_4x4()
        m.translation = o
        return m


def build_belt(top, trousers, collection):
    from mathutils.bvhtree import BVHTree

    verts, polys = [], []
    for ob in (top, trousers):
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        polys += [[i + off for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    ring = BeltRing(bvh)
    b = Builder()
    _belt_band(b, ring)
    _tongue(b, ring)
    _keeper(b, ring)
    _buckle(b, ring)
    _vials(b, ring)
    for deg in POUCH_DEGS:
        _pouch(b, ring, deg)
    belt = b.to_object("Belt", collection)
    _shade_flat_regions(belt, (H_METAL,))
    h = Builder()
    glow = Builder()
    _cuffs(h, ring)
    _passkey(h, ring, glow)
    hangers = h.to_object("Hangers", collection)
    glow_ob = glow.to_object("PasskeyGlow", collection)
    return belt, hangers, glow_ob, ring


def _belt_band(b, ring):
    rows = ring.rows
    prof = curves.rounded_rect_profile(BELT_T, BELT_W, 0.0016, 1)
    bm = bmesh.new()
    vr = [[bm.verts.new(c + out * u + up * v) for u, v in prof] for c, up, out in rows]
    m = len(prof)
    for k in range(len(vr)):
        a, bb = vr[k], vr[(k + 1) % len(vr)]
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], bb[(j + 1) % m], bb[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    hv = {}
    for k, r in enumerate(vr):
        for (u, v), vert in zip(prof, r):
            hv[vert] = (1000.0 + 360.0 * k / COLUMNS, v)   # hu >= 1000: the belt band (degrees + 1000)
    _add_with(b, bm, H_LEATHER, hv)


def _add_with(b, bm, region, uvmap):
    L = b.L
    vmap = {}
    for v in bm.verts:
        w = b.bm.verts.new(v.co)
        w[L["region"]] = float(region)
        w[L["hu"]], w[L["hv"]] = uvmap.get(v, (0.0, 0.0))
        vmap[v] = w
    for f in bm.faces:
        b.bm.faces.new([vmap[v] for v in f.verts])
    bm.free()


def _tongue(b, ring):
    """The belt's end: over the belt from the buckle toward her left, a rounded tip."""
    d0, d1 = TONGUE_DEGS
    n = 14
    rows = []
    for k in range(n + 1):
        deg = d0 + (d1 - d0) * k / n
        c, up, out = ring.section(deg)
        rows.append((c + out * (BELT_T + 0.0004), up, out))
    prof = curves.rounded_rect_profile(BELT_T * 0.9, BELT_W * 0.86, 0.0014, 2)
    bm = bmesh.new()
    vr = []
    for k, (c, up, out) in enumerate(rows):
        s = k / n
        taper = 1.0 if s < 0.8 else math.cos((s - 0.8) / 0.2 * math.pi * 0.47)
        vr.append([bm.verts.new(c + out * u + up * v * max(taper, 0.15)) for u, v in prof])
    m = len(prof)
    for a, bb in zip(vr, vr[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], bb[(j + 1) % m], bb[j]))
    bm.faces.new(list(reversed(vr[0])))
    bm.faces.new(vr[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    hv = {}
    for k, r in enumerate(vr):
        for (u, v), vert in zip(prof, r):
            hv[vert] = (100.0 + k / n, v)     # hu > 100: the tongue (holes in the material)
    _add_with(b, bm, H_LEATHER, hv)


def _keeper(b, ring):
    m = ring.frame(KEEPER_DEG, lift=0.0)
    bm = bmesh.new()
    path = [Vector((0.0, y, z)) for y, z in ((-BELT_T - 0.0009, -0.032), (0.0062, -0.032), (0.0062, 0.032),
                                               (-BELT_T - 0.0009, 0.032))]
    path = curves.round_polyline(path, 0.003, steps=3, closed=True)
    curves.sweep(bm, path, curves.rounded_rect_profile(0.014, 0.0022, 0.0009, 1), up=(1.0, 0.0, 0.0),
                 closed=True, caps=False)
    b.add(bm, m, H_LEATHER)


def _buckle(b, ring):
    """Rectangular gunmetal frame with a center bar and a prong."""
    m = ring.frame(BUCKLE_DEG, lift=0.0012)
    bm = bmesh.new()
    w, h = 0.050, 0.068
    rect = [Vector((x, 0.0, z)) for x, z in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
    rect = curves.round_polyline(rect, 0.008, steps=4, closed=True)
    curves.sweep(bm, rect, curves.rounded_rect_profile(0.0062, 0.0046, 0.0018, 2), up=(0.0, 1.0, 0.0),
                 closed=True, caps=False)
    bar = [Vector((-w / 2 + 0.012, 0.0, -h / 2 + 0.004)), Vector((-w / 2 + 0.012, 0.0, h / 2 - 0.004))]
    curves.sweep(bm, bar, curves.circle_profile(0.0025, 8), up=(0.0, 1.0, 0.0))
    prong = [Vector((-w / 2 + 0.012, 0.0028, 0.0)), Vector((0.006, 0.0042, 0.0)), Vector((w / 2 - 0.001, 0.0030, 0.0))]
    curves.sweep(bm, prong, curves.circle_profile(0.0016, 6), up=(0.0, 0.0, 1.0))
    b.add(bm, m, H_METAL)


def _lathe_part(profile, segments=16):
    bm = bmesh.new()
    curves.lathe(bm, profile, segments=segments)
    return bm


def _vials(b, ring):
    """Five vials in elastic loops on a leather backing."""
    m = ring.frame(VIALS_DEG, dz=-0.004, lift=0.0)
    m = rest_on_body(ring, m, [(x, 0.0, z) for x in (-0.044, 0.0, 0.044) for z in (-0.018, -0.024, -0.042)], 0.012,
                     upper=[(x, 0.004, z) for x in (-0.034, 0.0, 0.034) for z in (0.03, 0.04)])
    back = soft.soft_box((0.0, 0.0018, -0.004), (0.088, 0.0036, 0.036), 0.0014, step=0.02, band_segments=1,
                         panel_axis=1)
    b.add(back, m, H_LEATHER)
    for k in range(5):
        x = -0.034 + 0.017 * k
        mm = m @ Matrix.Translation((x, 0.0105, 0.0))
        glass = [(0.0, -0.042), (0.0040, -0.0412), (0.0058, -0.038), (0.0062, -0.032), (0.0062, 0.022),
                 (0.0055, 0.025), (0.0048, 0.026)]
        b.add(_lathe_part(glass, 10), mm, H_GLASS)
        cap = [(0.0050, 0.0255), (0.0066, 0.0265), (0.0067, 0.0365), (0.0058, 0.0392), (0.0, 0.0396)]
        b.add(_lathe_part(cap, 10), mm, H_METAL)
        loop = [(0.0064, -0.016), (0.0077, -0.0152), (0.0077, 0.0042), (0.0064, 0.0046)]
        b.add(_lathe_part(loop, 10), mm, H_ELASTIC)


def _pouch(b, ring, deg):
    """A leather pouch with a snap flap, hanging from the belt."""
    m = ring.frame(deg, dz=-0.026, lift=0.0)
    w, d, h = 0.080, 0.032, 0.100
    m = rest_on_body(ring, m, [(x, 0.001, z) for x in (-0.038, 0.0, 0.038) for z in (-0.03, -0.06)], 0.035,
                     upper=[(x, 0.001, z) for x in (-0.04, 0.0, 0.04) for z in (0.02, 0.045)])
    body = soft.soft_box((0.0, d * 0.5 + 0.001, -0.012), (w, d, h), 0.009, step=0.03, band_segments=2,
                         panel_axis=1, crown={"+y": 0.004})
    b.add(body, m, H_LEATHER, uv=lambda co: (co.x, co.z))
    flap = soft.soft_box((0.0, d + 0.004, 0.022), (w + 0.006, 0.006, 0.050), 0.0026, step=0.02, band_segments=1,
                         panel_axis=1, crown={"+y": 0.0015})
    b.add(flap, m, H_LEATHER, uv=lambda co: (co.x + 10.0, co.z))   # hu > 5: the flap
    snap = [(0.0, 0.0), (0.0058, 0.0), (0.0062, 0.0016), (0.0045, 0.0034), (0.0, 0.0038)]
    sm = m @ Matrix.Translation((0.0, d + 0.0072, 0.006)) @ Matrix.Rotation(-math.pi / 2, 4, "X")
    b.add(_lathe_part(snap, 14), sm, H_METAL)


def rest_on_body(ring, m, probes, pivot_z, clear=0.004, upper=()):
    """Tilt an item's frame `m` about its local x axis through the local point (0, 0,
    pivot_z) (where it hangs from the belt) until every local `probe` point (its back,
    below the belt) is `clear` outside the garments: pouches and vials rest on the hip."""
    x = m.col[0].to_3d()
    pivot = m @ Vector((0.0, 0.0, pivot_z))
    mm = m
    for step in range(40):
        a = math.radians(step * 1.0)
        mm = Matrix.Translation(pivot) @ Matrix.Rotation(a, 4, x) @ Matrix.Translation(-pivot) @ m
        ok = True
        for q in probes:
            p = mm @ Vector(q)
            h = ring.bvh.find_nearest(p)
            if h[0] is not None and (p - h[0]).dot(h[1]) < clear:
                ok = False
                break
        if ok:
            break
    out = mm.col[1].to_3d()
    for _ in range(30):         # then off the body until the upper part clears too
        if all(_clear(ring, mm @ Vector(q), clear) for q in list(probes) + list(upper)):
            break
        mm = Matrix.Translation(out * 0.001) @ mm
    return mm


def _clear(ring, p, clear):
    h = ring.bvh.find_nearest(p)
    return h[0] is None or (p - h[0]).dot(h[1]) >= clear


def gravity_frame(ring, deg):
    """Frame at the belt's bottom edge for things hanging from it: z up (gravity), y out
    (horizontal), x along the belt."""
    m = ring.frame(deg, dz=-BELT_W * 0.5 + 0.004, lift=0.0)
    o = m.translation.copy()
    up = Vector((0.0, 0.0, 1.0))
    out = m.col[1].to_3d()
    out = Vector((out.x, out.y, 0.0)).normalized()
    x = out.cross(up).normalized()
    g = Matrix((x, out, up)).transposed().to_4x4()
    g.translation = o
    return g


def fit_hanging(ring, deg, parts, clear=0.005, max_tilt=32.0):
    """World matrix for items hanging from the belt (`parts`: [(bmesh, local matrix,
    region)] in a gravity_frame): swung forward about the clip (at most `max_tilt`
    degrees) until what hangs below the belt clears the thigh, then pushed off the body
    until every vertex clears it: they rest on the thigh instead of sinking into it."""
    g = gravity_frame(ring, deg)
    pts = []
    for bm, lm, _ in parts:
        vs = bm.verts[:]
        step = max(1, len(vs) // 40)
        pts += [lm @ v.co for v in vs[::step]]
    low = [p for p in pts if p.z < -0.02]
    x = g.col[0].to_3d()
    o = g.translation.copy()
    best = g
    for k in range(int(max_tilt) + 1):
        r = Matrix.Translation(o) @ Matrix.Rotation(math.radians(k), 4, x) @ Matrix.Translation(-o)
        best = r @ g
        if all(_clear(ring, best @ p, clear) for p in low):
            break
    out = best.col[1].to_3d()
    for _ in range(40):
        if all(_clear(ring, best @ p, clear) for p in pts if p.z < 0.0):
            break
        best = Matrix.Translation(out * 0.001) @ best
    return best


def _add_parts(b, m, parts):
    for bm, lm, region in parts:
        b.add(bm, m @ lm, region)


def _cuffs(b, ring):
    """Handcuffs hanging from a D-ring clip on the belt's bottom edge."""
    parts = []
    tab = soft.soft_box((0.0, 0.0014, -0.012), (0.022, 0.0028, 0.034), 0.0010, step=0.02, band_segments=1,
                        panel_axis=1)
    parts.append((tab, Matrix.Identity(4), H_LEATHER))
    bm = bmesh.new()
    d_path = [Vector((x, 0.006, z)) for x, z in ((-0.012, -0.022), (0.012, -0.022), (0.014, -0.040),
                                                   (0.0, -0.058), (-0.014, -0.040))]
    d_path = curves.round_polyline(d_path, 0.006, steps=4, closed=True)
    curves.sweep(bm, d_path, curves.circle_profile(0.0022, 8), up=(0.0, 1.0, 0.0), closed=True, caps=False)
    parts.append((bm, Matrix.Identity(4), H_METAL))
    tilt = Matrix.Rotation(math.radians(18.0), 4, "Z")
    for k, (cz, ang) in enumerate(((-0.090, 8.0), (-0.172, -12.0))):
        cm = Matrix.Translation((0.004 * (1 - 2 * k), 0.010, cz)) @ tilt @ Matrix.Rotation(math.radians(ang), 4, "Y")
        bm = bmesh.new()
        circle = [Vector((0.031 * math.cos(a), 0.0, 0.031 * math.sin(a)))
                  for a in np.linspace(0.0, 2.0 * math.pi, 22, endpoint=False)]
        curves.sweep(bm, circle, curves.rounded_rect_profile(0.0048, 0.0034, 0.0012, 1), up=(0.0, 1.0, 0.0),
                     closed=True, caps=False)
        side = 1.0 if k == 0 else -1.0
        lock = soft.soft_box((side * 0.034, 0.0, 0.004), (0.010, 0.0085, 0.030), 0.0018, step=0.02,
                             band_segments=1, panel_axis=1)
        parts.append((bm, cm, H_METAL))
        parts.append((lock, cm, H_METAL))
    for j, z in enumerate((-0.1235, -0.1325, -0.1415)):
        lm = Matrix.Translation((0.002, 0.010, z))
        if j % 2:
            lm = lm @ Matrix.Rotation(math.pi / 2, 4, "Z")
        bm = bmesh.new()
        path = [Vector((0.0028 * math.cos(a), 0.0, 0.0058 * math.sin(a)))
                for a in np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)]
        curves.sweep(bm, path, curves.circle_profile(0.0011, 6), up=(0.0, 1.0, 0.0), closed=True, caps=False)
        parts.append((bm, lm, H_METAL))
    _add_parts(b, fit_hanging(ring, CUFFS_DEG, parts), parts)


def _passkey(b, ring, glow):
    """The maglock passkey: a black polymer card on a leather tab, a violet glowing strip."""
    parts, glow_parts = [], []
    tab = soft.soft_box((0.0, 0.0014, -0.014), (0.016, 0.0028, 0.040), 0.0010, step=0.02, band_segments=1,
                        panel_axis=1)
    parts.append((tab, Matrix.Identity(4), H_LEATHER))
    bm = bmesh.new()
    ringp = [Vector((0.0075 * math.cos(a), 0.0045, -0.036 + 0.0075 * math.sin(a)))
             for a in np.linspace(0.0, 2.0 * math.pi, 14, endpoint=False)]
    curves.sweep(bm, ringp, curves.circle_profile(0.0013, 6), up=(0.0, 1.0, 0.0), closed=True, caps=False)
    parts.append((bm, Matrix.Identity(4), H_METAL))
    km = Matrix.Translation((0.0, 0.0065, -0.083)) @ Matrix.Rotation(math.radians(-6.0), 4, "Y")
    body = soft.soft_box((0.0, 0.0, 0.0), (0.031, 0.0072, 0.074), 0.0030, step=0.012, band_segments=2,
                         panel_axis=1)
    parts.append((body, km, H_POLY))
    eye = soft.soft_box((0.0, 0.0, 0.0405), (0.012, 0.0050, 0.012), 0.0024, step=0.02, band_segments=1,
                        panel_axis=1)
    parts.append((eye, km, H_POLY))
    strip = soft.soft_box((0.0, 0.0036, -0.002), (0.0056, 0.0014, 0.050), 0.0006, step=0.01, band_segments=1,
                          panel_axis=1)
    glow_parts.append((strip, km, H_GLOW))
    m = fit_hanging(ring, PASSKEY_DEG, parts + glow_parts)
    _add_parts(b, m, parts)
    _add_parts(glow, m, glow_parts)


# --- thigh strap ------------------------------------------------------------------------------------
def build_thigh_strap(trousers, arm, collection, ring=None):
    """A band around her right thigh with a buckle, and a drop strap up to the belt."""
    from mathutils.bvhtree import BVHTree

    me = trousers.data
    mw = trousers.matrix_world
    bvh = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
    bones = arm.data.bones
    hip = arm.matrix_world @ bones["RightUpperLeg"].head_local
    knee = arm.matrix_world @ bones["RightUpperLeg"].tail_local
    f = (THIGH_Z - hip.z) / (knee.z - hip.z)
    c = hip.lerp(knee, f)
    axis = (hip - knee).normalized()
    b = Builder()
    rows = []
    n = 40
    for k in range(n):
        a = 2.0 * math.pi * k / n
        d = Vector((math.sin(a), -math.cos(a), 0.0))
        d = (d - axis * d.dot(axis)).normalized()
        pts = []
        for dz in (-THIGH_W * 0.5, -THIGH_W * 0.25, 0.0, THIGH_W * 0.25, THIGH_W * 0.5):
            o = c + axis * dz
            h = bvh.ray_cast(o, d, 0.2)[0]
            pts.append(h if h is not None else o + d * 0.08)
        bot, top = pts[0], pts[-1]
        up = (top - bot).normalized()
        out = (d - up * d.dot(up)).normalized()
        mid = (bot + top) * 0.5
        bulge = max(0.0, max((p - mid).dot(out) for p in pts))
        rows.append((mid + out * (bulge + 0.0012 + 0.0015), up, out))
    prof = curves.rounded_rect_profile(0.0030, THIGH_W, 0.0012, 2)
    bm = bmesh.new()
    vr = [[bm.verts.new(cc + out * u + up * v) for u, v in prof] for cc, up, out in rows]
    m = len(prof)
    for k in range(n):
        a, bb = vr[k], vr[(k + 1) % n]
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], bb[(j + 1) % m], bb[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _add_with(b, bm, H_STRAP, {})
    # buckle on the outer front of the band
    k = int(n * (1.0 - 0.14)) % n         # her right front (-x, -y)
    cc, up, out = rows[k]
    x = out.cross(up).normalized()
    mb = Matrix((x, out, up)).transposed().to_4x4()
    mb.translation = cc + out * 0.0042
    bm = bmesh.new()
    w, h = 0.028, 0.044
    rect = [Vector((xx, 0.0, z)) for xx, z in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
    rect = curves.round_polyline(rect, 0.006, steps=3, closed=True)
    curves.sweep(bm, rect, curves.rounded_rect_profile(0.0045, 0.0036, 0.0014, 1), up=(0.0, 1.0, 0.0),
                 closed=True, caps=False)
    b.add(bm, mb, H_METAL)
    # drop strap: from the belt's bottom edge down the outside of the thigh to the band
    top_z = BELT_Z[0] + 0.022
    pts = []
    steps = 12
    side = Vector((-0.94, -0.34, 0.0)).normalized()
    for i in range(steps + 1):
        z = top_z + (THIGH_Z + THIGH_W * 0.5 - 0.004 - top_z) * i / steps
        g = (z - hip.z) / (knee.z - hip.z)
        o = hip.lerp(knee, max(g, 0.0))
        o.z = z
        h = _farthest(bvh, Vector((o.x * 0.5, o.y, z)), side, 0.3)
        pts.append(h if h is not None else o + side * 0.09)
    rows = []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        bb = pts[min(i + 1, steps)]
        along = (bb - a).normalized()
        out = (side - along * side.dot(along)).normalized()
        across = along.cross(out).normalized()
        lift = 0.0045
        if ring is not None and p.z > BELT_Z[0] - 0.02:     # over the belt's lower edge
            c, up_b, out_b = ring.section(DROP_DEG)
            over = (c + out_b * (BELT_T * 0.5 + 0.0018) - p).dot(out)
            f = smoothstep(p.z, BELT_Z[0] - 0.02, BELT_Z[0])
            lift = max(lift, lift * (1.0 - f) + over * f)
        rows.append((p + out * lift, across, out))
    prof = curves.rounded_rect_profile(0.0028, 0.030, 0.0011, 2)
    bm = bmesh.new()
    vr = [[bm.verts.new(cc + out * u + ac * v) for u, v in prof] for cc, ac, out in rows]
    m = len(prof)
    for a, bb in zip(vr, vr[1:]):
        for j in range(m):
            bm.faces.new((a[j], a[(j + 1) % m], bb[(j + 1) % m], bb[j]))
    bm.faces.new(list(reversed(vr[0])))
    bm.faces.new(vr[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _add_with(b, bm, H_STRAP, {v: (1.0, (v.co.z - THIGH_Z)) for v in bm.verts})
    ob = b.to_object("ThighStrap", collection)
    _shade_flat_regions(ob, (H_METAL,))
    return ob


# --- weights ---------------------------------------------------------------------------------------
def weight_rigid(ob, bone):
    garment.set_weights(ob, [{bone: 1.0} for _ in ob.data.vertices])


def weight_hangers(ob, belt_bottom=BELT_Z[0]):
    """Clip and tab on Hips; the hanging parts take up to 40 % of the right thigh's swing
    toward their bottom, so the thigh doesn't run through them in a stride."""
    out = []
    for v in ob.data.vertices:
        f = 0.40 * smoothstep(belt_bottom - v.co.z, 0.03, 0.20)
        side = "Right" if v.co.x < 0.0 else "Left"
        out.append({"Hips": 1.0 - f, f"{side}UpperLeg": f} if f > 0.0 else {"Hips": 1.0})
    garment.set_weights(ob, out)


def weight_thigh_strap(ob):
    out = []
    for v in ob.data.vertices:
        f = smoothstep(v.co.z, THIGH_Z + 0.06, BELT_Z[0] - 0.01)
        out.append({"RightUpperLeg": 1.0 - f, "Hips": f} if f > 0.0 else {"RightUpperLeg": 1.0})
    garment.set_weights(ob, out)
