"""Silena's boots (stage 3): soft black leather to mid-calf, flat crepe-rubber sole with
a low heel block (quiet: she sneaks). Built for the left foot, mirrored.

The upper is one loft along a path down the shin, around the ankle (a fillet, like the
sleeve's elbow) and along the foot to the toe (garment.PathFrames): each ring's radii
come from rays to the skin, are convexified around the ring (no Achilles hollow, no
toe gaps), eased and flattened onto the sole. The shaft's top edge turns in over a
short lining; the toe closes with a rounded cap. The sole is the footprint's outline
(convex) swept through a rounded profile and filled at the bottom; the bare foot
stands at z = 0, the sole's contact plane is SOLE_Z.

Per-vertex data for the material (removed after baking): `region` (B_*), `bt` (distance
along the path from the shaft top, m), `ba` (angle around the path, radians; 0 = front
of the shin / top of the foot, + toward her outside), `bh` (height, m).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from silena_vesper_common import BOOT_TOP_Z, SOLE_Z
from arcology_blender import curves, garment, rig

COLUMNS = 30
EASE_SHAFT = 0.0090          # over the skin (trousers tucked in: 3.4 mm)
EASE_ANKLE = 0.0060
EASE_FOOT = 0.0042
TOE_ROOM = 0.014             # toe box beyond the toes
SOLE_TOP = 0.004             # the upper sits on the sole here
ANKLE_FILLET = 0.060
FOLD_R = 0.0020              # shaft top: two layers of leather turned in
LINING_DEPTH = 0.030
SOLE_OVERHANG = 0.0035
STEP_SHAFT, STEP_ANKLE, STEP_FOOT = 0.013, 0.007, 0.009

B_UPPER, B_FOLD, B_LINING, B_SOLE = 0, 1, 2, 3
ATTRS = ("region", "bt", "ba", "bh")


def smoothstep(x, a, b):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hull2(pts):
    from coat import _hull
    return _hull(np.asarray(pts))


class BootPath:
    def __init__(self, arm, side="Left"):
        mw = arm.matrix_world
        b = arm.data.bones
        knee = mw @ b[f"{side}LowerLeg"].head_local
        ankle = mw @ b[f"{side}Foot"].head_local
        ball = mw @ b[f"{side}Toes"].head_local
        tip = mw @ b[f"{side}Toes"].tail_local
        axis = (ankle - knee).normalized()
        f = (BOOT_TOP_Z + 0.004 - knee.z) / (ankle.z - knee.z)
        top = knee.lerp(ankle, f)
        fwd = Vector((ball.x - ankle.x, ball.y - ankle.y, 0.0)).normalized()
        mid = Vector((ball.x, ball.y, 0.030))
        toe = Vector((tip.x, tip.y, 0.023)) + fwd * 0.004
        pts = curves.round_polyline([top - axis * 0.05, ankle + Vector((0.0, 0.0, 0.008)), mid, toe], ANKLE_FILLET,
                                    steps=14, min_turn=4.0)
        self.path = garment.PathFrames(pts, Vector((0.0, -1.0, 0.0)), step=0.0005)
        self.t_top = self._closest(top)
        self.t_ankle = self._closest(ankle)
        self.t_toe = self._closest(toe)
        self.side = side
        self.out = Vector((1.0 if side == "Left" else -1.0, 0.0, 0.0))

    def _closest(self, p):
        best = min(range(len(self.path.points)), key=lambda i: (self.path.points[i] - p).length_squared)
        return best * self.path.step


def build_boot(skin, arm, collection, side="Left"):
    bp = BootPath(arm, side)
    ref = skin.copy()
    ref.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(ref)
    rig.extract_by_weight(ref, [f"{side}LowerLeg", f"{side}Foot", f"{side}Toes"], 0.3)
    bvh = garment.bvh_of(ref)
    rd = ref.data
    bpy.data.objects.remove(ref)
    bpy.data.meshes.remove(rd)
    path = bp.path
    n = COLUMNS
    thetas = [2.0 * math.pi * k / n for k in range(n)]
    # ring positions along the path
    ts = []
    t = bp.t_top
    while t < bp.t_toe - 1e-6:
        ts.append(t)
        near = abs(t - bp.t_ankle) < ANKLE_FILLET * 1.6
        t += STEP_ANKLE if near else (STEP_SHAFT if t < bp.t_ankle else STEP_FOOT)
    ts.append(bp.t_toe)
    rings = []
    for t in ts:
        fr = path.frame(t)
        rs = garment.ring_radii(bvh, fr, 0.0, thetas, max_r=0.13)
        pts2 = np.array([(r * math.cos(a), r * math.sin(a)) for r, a in zip(rs, thetas)])
        hull = _hull2(np.r_[pts2, [[0.0, 0.0]]])
        from coat import _exit
        rh = [_exit(hull, np.zeros(2), np.array((math.cos(a), math.sin(a)))) for a in thetas]
        rings.append(rh)
    R = np.array(rings)
    for _ in range(2):   # smooth around and along
        R = (np.roll(R, 1, axis=1) + 2.0 * R + np.roll(R, -1, axis=1)) * 0.25
        R[1:-1] = (R[:-2] + 2.0 * R[1:-1] + R[2:]) * 0.25
    # ease by region, a little calf room
    for i, t in enumerate(ts):
        a = smoothstep(t, bp.t_ankle - 0.10, bp.t_ankle - 0.02)
        b = smoothstep(t, bp.t_ankle + 0.03, bp.t_ankle + 0.08)
        ease = EASE_SHAFT * (1.0 - a) + EASE_ANKLE * a * (1.0 - b) + EASE_FOOT * b
        R[i] += ease
    # toe box: round the front of the foot toward a smooth almond shape
    for i, t in enumerate(ts):
        f = smoothstep(t, bp.t_toe - 0.07, bp.t_toe)
        if f > 0.0:   # never smaller than the toes inside
            R[i] = np.maximum(R[i], R[i] * (1.0 - 0.6 * f) + R[i].max() * 0.6 * f * 0.92)
    bm = bmesh.new()
    L = {a: bm.verts.layers.float.new(a) for a in ATTRS}
    loft_rings, meta = [], []

    def ring_at(t, rr, region, along):
        fr = path.frame(t)
        pts = [fr.point(0.0, a, r) for a, r in zip(thetas, rr)]
        loft_rings.append(pts)
        meta.append((region, along))

    # shaft top: lining inside, fold over the edge, then down the outside
    top_r = R[0]
    for d in (LINING_DEPTH, LINING_DEPTH * 0.5, 0.004):
        ring_at(bp.t_top + d, top_r - 2 * FOLD_R - 0.0015 * (d / LINING_DEPTH), B_LINING, -d)
    for ang in (-90.0, -30.0, 30.0, 90.0):
        a = math.radians(ang)
        ring_at(bp.t_top - FOLD_R * math.cos(a) + 0.0, top_r - FOLD_R + FOLD_R * math.sin(a), B_FOLD, 0.0)
    for i, t in enumerate(ts):
        ring_at(t + 0.0025 if i == 0 else t, R[i], B_UPPER, t - bp.t_top)
    # toe cap: a rounded end
    last = R[-1]
    fr = path.frame(bp.t_toe)
    for s in (0.35, 0.65, 0.88):
        h = TOE_ROOM * math.sin(s * math.pi * 0.5)
        pts = [fr.point(0.0, a, r * math.cos(s * math.pi * 0.5)) + fr.axis * h for a, r in zip(thetas, last)]
        loft_rings.append(pts)
        meta.append((B_UPPER, bp.t_toe - bp.t_top + h))
    # flatten onto the sole
    for ring in loft_rings:
        for p in ring:
            if p.z < SOLE_TOP:
                p.z = SOLE_TOP
    vrings, centers, faces = garment.loft(bm, loft_rings, closed=True, cap_end=True)
    tip = fr.axis * TOE_ROOM + fr.origin
    centers[0].co = Vector((tip.x, tip.y, max(tip.z, SOLE_TOP)))
    probe = faces[len(faces) // 2]
    c = probe.calc_center_median()
    garment.orient(bm, faces, probe, c - path.frame(ts[len(ts) // 2]).origin)
    for ring, (region, along) in zip(vrings, meta):
        for v, a in zip(ring, thetas):
            v[L["region"]] = float(region)
            v[L["bt"]] = along
            v[L["ba"]] = _signed_angle(a, bp)
            v[L["bh"]] = v.co.z
    cv = centers[0]
    cv[L["region"]] = float(B_UPPER)
    cv[L["bt"]] = meta[-1][1] + 0.003
    cv[L["ba"]] = 0.0
    cv[L["bh"]] = cv.co.z
    # the flattened bottom is inside the sole: drop it
    flat = [f for f in bm.faces if all(v.co.z <= SOLE_TOP + 1e-6 for v in f.verts)]
    bmesh.ops.delete(bm, geom=flat, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    _sole(bm, L, [v.co.copy() for v in bm.verts if v.co.z <= SOLE_TOP + 0.003], bp)
    me = bpy.data.meshes.new(f"Boot{side}")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"Boot{side}", me)
    collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def _signed_angle(a, bp):
    """Angle around the path from the front, positive toward her outside (both feet)."""
    a = (a + math.pi) % (2.0 * math.pi) - math.pi
    fr = bp.path.frame(bp.t_top)
    side = fr.lat.dot(bp.out)
    return a if side >= 0.0 else -a


def _sole(bm, L, bottom, bp):
    """Rubber sole: the footprint's convex outline swept through a rounded profile."""
    pts = np.array([(p.x, p.y) for p in bottom])
    hull = _hull2(pts)
    c = hull.mean(axis=0)
    # resample the outline evenly, then grow it
    poly = np.r_[hull, hull[:1]]
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    acc = np.r_[0.0, np.cumsum(seg)]
    m = 56
    s = np.linspace(0.0, acc[-1], m, endpoint=False)
    outline = np.stack([np.interp(s, acc, poly[:, 0]), np.interp(s, acc, poly[:, 1])], axis=1)
    for _ in range(3):
        outline = (np.roll(outline, 1, axis=0) + 2.0 * outline + np.roll(outline, -1, axis=0)) * 0.25
    nrm = []
    for k in range(m):
        a, b = outline[k - 1], outline[(k + 1) % m]
        t = (b - a) / np.linalg.norm(b - a)
        nv = np.array((t[1], -t[0]))
        if np.dot(nv, outline[k] - c) < 0.0:
            nv = -nv
        nrm.append(nv)
    nrm = np.array(nrm)
    ys = outline[:, 1]
    y_heel, y_toe = ys.max(), ys.min()
    length = y_heel - y_toe
    profile = ((-0.0015, SOLE_TOP + 0.0025), (SOLE_OVERHANG - 0.0004, SOLE_TOP), (SOLE_OVERHANG, 0.0),
               (SOLE_OVERHANG - 0.0002, (SOLE_TOP + SOLE_Z) * 0.5 - 0.002), (SOLE_OVERHANG - 0.0008, SOLE_Z + 0.0025),
               (SOLE_OVERHANG - 0.0030, SOLE_Z))
    rings = []
    for off, z in profile:
        ring = []
        for k in range(m):
            p = outline[k] + nrm[k] * off
            # shank: the waist between heel block and forefoot stands off the ground
            u = (y_heel - outline[k][1]) / length
            lift = 0.0045 * smoothstep(u, 0.28, 0.34) * (1.0 - smoothstep(u, 0.50, 0.60)) if z < -0.004 else 0.0
            ring.append(Vector((p[0], p[1], z + lift)))
        rings.append(ring)
    vrings, _, faces = garment.loft(bm, rings, closed=True)
    bottom_ring = vrings[-1]
    # the bottom: a fan from the center (the outline is convex; triangle_fill's output order
    # changes from run to run)
    center = bm.verts.new(sum((v.co for v in bottom_ring), Vector()) / m)
    fill = [bm.faces.new((bottom_ring[(k + 1) % m], bottom_ring[k], center)) for k in range(m)]
    faces += fill
    bm.normal_update()
    probe = faces[m + 2]
    pc = probe.calc_center_median()
    garment.orient(bm, faces, probe, Vector((pc.x - c[0], pc.y - c[1], 0.0)))
    for f in fill:
        f.normal_update()
        if f.normal.z > 0.0:
            f.normal_flip()
    for v in {v for f in faces for v in f.verts}:
        v[L["region"]] = float(B_SOLE)
        v[L["bt"]] = 1.0
        v[L["ba"]] = (y_heel - v.co.y) / length
        v[L["bh"]] = v.co.z


