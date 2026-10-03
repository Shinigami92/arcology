"""Silena's coat sleeve (built for the left arm; bake.py mirrors it with the glove).

One lofted surface around the arm's centerline (wrist, elbow fillet, shoulder;
garment.PathFrames), ring by ring from inside the opening up to the shoulder:
- lining: the inside of the sleeve seen in the opening, widening upward around
  the glove's gauntlet (the glove above GLOVE_HIDE_T is deleted; its cut edge
  hides behind the opening, which is the narrowest point);
- fold: the rounded edge of the opening;
- cuff: the turned-back cuff over the gauntlet, flaring a little toward its free
  top edge (lip), which stands off the sleeve; under the lip it meets the sleeve;
- body: the sleeve, loose over the forearm and fuller at the upper arm, with
  compression folds in the crook of the elbow, ease over the elbow's point and a
  few long soft folds along the forearm and down from the front of the armhole;
- armhole: a piped seam, slanted like a set-in sleeve (high over the shoulder,
  low in the armpit), where stage 3's coat body attaches;
- cap: a shallow dome closing the sleeve inside the armhole.

Per-vertex data for the coat material (removed after baking):
- `region` (R_*), `pt` (distance along the centerline from the wrist, m), `so` /
  `si` (arc distance from the outer / inner sleeve seam, m), `ct` (cuff: distance
  above the opening's fold, m), `at` (distance below the armhole seam, m),
  `crook` and `rub` (0..1 masks: the elbow's crook, the elbow's point);
- UV maps `OrnUV` (u = signed arc distance from the ornament line, v = pt: the
  embroidery and the stitch rows around the sleeve) and `BakeUV` (surface-true
  unwrap in meters: u = arc length around from the inner seam, v = distance along
  each column; islands opening+cuff, sleeve, cap), packed into `UVMap` by bake.py.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from silena_vesper_common import (
    ARMHOLE_C0, ARMHOLE_C1, CAP_DOME, CUFF_GAP, CUFF_STANDOFF, CUFF_TOP_T, ELBOW_FILLET, FOLD_R, LIP_R,
    PAST_SHOULDER, SLEEVE_COLUMNS, SLEEVE_LINING_TOP_T, SLEEVE_OPEN_T, twist_inflation,
)
from arcology_blender import curves, garment, rig

R_LINING, R_FOLD, R_CUFF, R_LIP, R_UNDER, R_BODY, R_SEAM, R_CAP = range(8)
ATTRS = ("region", "pt", "so", "si", "ct", "at", "crook", "rub")
UV_HELPERS = ("OrnUV", "BakeUV")
FAR = 1.0   # attribute value for "not near this feature"

# Ease over the skin (m) along the sleeve: keys (t relative to the elbow "E" or the shoulder
# "S", or absolute), loose over the forearm, fuller at the upper arm.
EASE = (("0", 0.100, 0.0110), ("0", 0.160, 0.0125), ("E", -0.050, 0.0150), ("E", 0.0, 0.0165),
        ("E", 0.060, 0.0175), ("E", 0.150, 0.0190), ("S", -0.060, 0.0175), ("S", 0.0, 0.0150),
        ("S", 0.060, 0.0120))
ROUND = 0.5            # the sleeve's cross-section is this much rounder than the arm's
STEP_FOREARM = 0.008   # ring spacing
STEP_ELBOW = 0.006
STEP_UPPER = 0.009
ELBOW_ZONE = 0.070     # fine rings within this distance of the elbow
TOP_START = 0.130      # slanted rings toward the armhole start this far below the shoulder
CAP_PLEATS = 9         # gathers in the lining closing the armhole
CAP_PLEAT = 0.0018


def smoothstep(x, a, b):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def smooth_ring(values, passes=2):
    v = list(values)
    n = len(v)
    for _ in range(passes):
        v = [(v[(i - 1) % n] + 2.0 * v[i] + v[(i + 1) % n]) * 0.25 for i in range(n)]
    return v


class SleeveFrame:
    """The arm's centerline (rest pose, world) and the named directions around it."""

    def __init__(self, arm, hf):
        side = hf.side
        bones, mw = arm.data.bones, arm.matrix_world
        self.wrist = mw @ bones[f"{side}Hand"].head_local
        self.elbow = mw @ bones[f"{side}LowerArm"].head_local
        self.shoulder = mw @ bones[f"{side}UpperArm"].head_local
        up_arm = (self.shoulder - self.elbow).normalized()
        pts = curves.round_polyline([self.wrist, self.elbow, self.shoulder, self.shoulder + up_arm * PAST_SHOULDER],
                                    ELBOW_FILLET, steps=16, min_turn=5.0)
        self.path = garment.PathFrames(pts, hf.dorsal, step=0.0005)
        self.t_E = self.closest(self.elbow)
        self.t_S = self.closest(self.shoulder)
        sx = 1.0 if side == "Left" else -1.0
        lateral, up = Vector((sx, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))
        anterior, posterior = Vector((0.0, -1.0, 0.0)), Vector((0.0, 1.0, 0.0))
        u = (self.elbow - self.shoulder).normalized()
        f = (self.wrist - self.elbow).normalized()
        self.crook_dir = (f - u).normalized()
        d = lambda v: Vector(v).normalized()  # noqa: E731
        # named lines along the sleeve: (t, direction) keys, angles interpolated in between
        self.lines = {
            "orn": [(0.0, hf.dorsal), (self.t_E, d(lateral + up * 0.35)), (self.t_S, d(lateral + up * 0.8))],
            "out": [(0.0, d(-hf.across * 0.8 + hf.dorsal * 0.6)), (self.t_E, d(posterior + lateral * 0.35)),
                    (self.t_S, d(posterior + up * 0.5))],
            "in": [(0.0, d(hf.across * 0.8 + hf.palm * 0.6)), (self.t_E, d(anterior * 0.5 - lateral)),
                   (self.t_S, d(-up - lateral * 0.3))],
        }
        self.th_crook = self.path.theta(self.t_E, self.crook_dir)
        self.th_point = self.path.theta(self.t_E, -self.crook_dir)
        self.th_up = self.path.theta(self.t_S, up)
        self.th_front = self.path.theta(self.t_S - 0.08, anterior)
        self.th_palm = self.path.theta(0.15, hf.palm)
        self.th_radial = self.path.theta(0.15, hf.across)

    def closest(self, p):
        best = min(range(len(self.path.points)), key=lambda i: (self.path.points[i] - p).length_squared)
        return best * self.path.step

    def line(self, name, t):
        keys = self.lines[name]
        ths = [self.path.theta(kt, kd) for kt, kd in keys]
        if t <= keys[0][0]:
            return ths[0]
        for (t0, _), (t1, _), a, b in zip(keys, keys[1:], ths, ths[1:]):
            if t <= t1:
                return a + wrap(b - a) * smoothstep(t, t0, t1)
        return ths[-1]

    def t_top(self, th):
        return self.t_S + ARMHOLE_C0 + ARMHOLE_C1 * math.cos(wrap(th - self.th_up))

    def point(self, t, th, r):
        return self.path.frame(t).point(0.0, th, r)

    def ease(self, t):
        ref = {"0": 0.0, "E": self.t_E, "S": self.t_S}
        keys = [(ref[a] + dt, e) for a, dt, e in EASE]
        if t <= keys[0][0]:
            return keys[0][1]
        for (t0, e0), (t1, e1) in zip(keys, keys[1:]):
            if t <= t1:
                return e0 + (e1 - e0) * smoothstep(t, t0, t1)
        return keys[-1][1]


class RadiusTable:
    """Smoothed radii around the path on a grid of t (ray casts from the centerline),
    looked up per column with linear interpolation."""

    def __init__(self, sf, bvh, thetas, t0, t1, step=0.004, max_r=0.12, around=3, along=1, envelope=False):
        self.t0, self.step = t0, step
        n = int(math.ceil((t1 - t0) / step)) + 1
        rows = []
        for i in range(n):
            t = t0 + i * step
            rs = garment.ring_radii(bvh, sf.path.frame(t), 0.0, thetas, max_r=max_r)
            rows.append(smooth_ring(rs, around))
        for _ in range(along):
            rows = [[(rows[max(i - 1, 0)][k] + 2.0 * rows[i][k] + rows[min(i + 1, n - 1)][k]) * 0.25
                     for k in range(len(thetas))] for i in range(n)]
        if envelope:  # radius never shrinks with t (the glove's flaring cuff)
            for i in range(1, n):
                rows[i] = [max(a, b) for a, b in zip(rows[i], rows[i - 1])]
        self.rows = rows

    def __call__(self, t, k):
        x = min(max((t - self.t0) / self.step, 0.0), len(self.rows) - 1.000001)
        i = int(x)
        f = x - i
        return self.rows[i][k] * (1.0 - f) + self.rows[i + 1][k] * f


class SleeveBuilder:
    def __init__(self, sf, skin_bvh, glove_bvh):
        self.sf = sf
        n = SLEEVE_COLUMNS
        self.th_cut = sf.line("in", sf.t_E)   # the UV cut runs along the inner seam
        self.thetas = [self.th_cut + 2.0 * math.pi * k / n for k in range(n)]
        self.skin = RadiusTable(sf, skin_bvh, self.thetas, 0.0, sf.t_S + PAST_SHOULDER, along=2)
        self.glove = RadiusTable(sf, glove_bvh, self.thetas, SLEEVE_OPEN_T - 0.004, SLEEVE_LINING_TOP_T + 0.004,
                                 step=0.002, max_r=0.09, around=1, along=0, envelope=True)

    # --- radii ----------------------------------------------------------------------------
    def folds(self, t, th):
        sf = self.sf
        d = 0.0
        # crook of the elbow: chevron compression folds, bunched outward
        dth = wrap(th - sf.th_crook)
        dt = t - sf.t_E
        env = (1.0 - smoothstep(abs(dth), 0.9, 1.6)) * (1.0 - smoothstep(abs(dt), 0.030, 0.068))
        x = dt / 0.022 + 0.45 * (dth / 1.0) ** 2
        d += env * (0.0022 + 0.0030 * math.cos(2.0 * math.pi * x))
        # ease over the elbow's point
        dpt = wrap(th - sf.th_point)
        d += 0.0030 * (1.0 - smoothstep(abs(dpt), 0.5, 1.4)) * (1.0 - smoothstep(abs(t - sf.t_E - 0.005), 0.02, 0.075))
        # long soft folds along the forearm (twisting a little as they run)
        for th0, slope, ta, tb, amp, width in (
                (sf.th_palm + 0.35, 1.6, 0.125, 0.235, 0.0024, 0.30),
                (sf.th_palm - 0.55, -1.1, 0.135, 0.225, 0.0018, 0.26),
                (sf.th_radial + 0.2, 0.9, 0.150, 0.240, 0.0014, 0.30)):
            win = smoothstep(t, ta, ta + 0.03) * (1.0 - smoothstep(t, tb - 0.03, tb))
            if win > 0.0:
                c = th0 + slope * (t - 0.5 * (ta + tb))
                d += amp * win * math.exp(-(wrap(th - c) / width) ** 2)
        # drape down from the front of the armhole
        for off, amp in ((-0.30, 0.0016), (0.25, 0.0012)):
            ta, tb = sf.t_S - 0.16, sf.t_S - 0.03
            win = smoothstep(t, ta, ta + 0.04) * (1.0 - smoothstep(t, tb - 0.03, tb))
            if win > 0.0:
                c = sf.th_front + off + 0.8 * (t - ta)
                d += amp * win * math.exp(-(wrap(th - c) / 0.24) ** 2)
        return d

    def body_r(self, t, k):
        rs = [self.skin(t, j) for j in range(len(self.thetas))]
        mean = sum(rs) / len(rs)
        r = rs[k] + (mean - rs[k]) * ROUND
        return (r + self.sf.ease(t) + self.folds(t, self.thetas[k])) * twist_inflation(t)

    def body_ring_r(self, t):
        rs = [self.skin(t, j) for j in range(len(self.thetas))]
        mean = sum(rs) / len(rs)
        g = twist_inflation(t)
        return [(r + (mean - r) * ROUND + self.sf.ease(t) + self.folds(t, th)) * g for r, th in zip(rs, self.thetas)]

    # --- rings -----------------------------------------------------------------------------
    def build(self, bm, layers):
        sf, n = self.sf, SLEEVE_COLUMNS
        ths = self.thetas
        rings, regions = [], []  # rings[j][k] = (t, r) per column

        def add(region, tr):
            rings.append(tr)
            regions.append(region)

        # lining: from its hidden top down to the opening, the narrowest point
        t_in = SLEEVE_OPEN_T + FOLD_R
        r_in = smooth_ring([self.glove(t_in, k) + CUFF_GAP for k in range(n)], 2)
        for t in (SLEEVE_LINING_TOP_T, 0.080, 0.070, 0.0615):
            gap = 0.0016 + (CUFF_GAP - 0.0016) * smoothstep(t, SLEEVE_LINING_TOP_T, t_in)
            rr = smooth_ring([max(self.glove(t, k) + gap, r_in[k]) for k in range(n)], 2)
            add(R_LINING, [(t, rr[k]) for k in range(n)])
        # fold at the opening: a half round from the lining to the cuff's face
        for phi in (-90.0, -135.0, 180.0, 135.0):
            a = math.radians(phi)
            region = R_LINING if phi == -90.0 else R_FOLD
            add(region, [(t_in + FOLD_R * math.cos(a), r_in[k] + FOLD_R + FOLD_R * math.sin(a)) for k in range(n)])
        # cuff: up to its top edge, flaring a little, a soft roll in the middle
        r_body_top = self.body_ring_r(CUFF_TOP_T)
        r_top = [max(r_body_top[k] + CUFF_STANDOFF, r_in[k] + 2 * FOLD_R + 0.002) for k in range(n)]
        r_top = smooth_ring(r_top, 2)
        c0, c1 = t_in, CUFF_TOP_T - LIP_R
        steps = 11
        for j in range(steps + 1):
            s = j / steps
            t = c0 + (c1 - c0) * s
            ring = []
            for k in range(n):
                r = (r_in[k] + 2 * FOLD_R) + (r_top[k] - r_in[k] - 2 * FOLD_R) * s ** 1.3 + 0.0008 * math.sin(math.pi * s)
                if t <= SLEEVE_LINING_TOP_T + 0.002:  # keep the lining inside
                    gap = 0.0016 + (CUFF_GAP - 0.0016) * smoothstep(t, SLEEVE_LINING_TOP_T, t_in)
                    r = max(r, self.glove(t, k) + gap + 2 * FOLD_R + 0.0006)
                ring.append((t, r))
            add(R_CUFF, ring)
        # lip: the cuff's rolled top edge, then the underside down to the sleeve
        for phi in (45.0, 0.0, -45.0, -90.0):
            a = math.radians(phi)
            add(R_LIP, [(CUFF_TOP_T - LIP_R + LIP_R * math.cos(a), r_top[k] - LIP_R + LIP_R * math.sin(a))
                        for k in range(n)])
        add(R_UNDER, [(CUFF_TOP_T - 0.0055, r_top[k] - 2 * LIP_R - 0.0006) for k in range(n)])
        add(R_UNDER, [(CUFF_TOP_T - 0.0105, r_top[k] - 2 * LIP_R - 0.0022) for k in range(n)])
        a_end = len(rings) - 1

        # sleeve body: straight rings up to the slanted top section
        t = CUFF_TOP_T - 0.0095
        t_slant = sf.t_S - TOP_START
        while t < t_slant - 1e-6:
            rr = self.body_ring_r(t)
            add(R_BODY, [(t, rr[k]) for k in range(n)])
            near = abs(t - sf.t_E) < ELBOW_ZONE
            step = STEP_ELBOW if near else (STEP_FOREARM if t < sf.t_E else STEP_UPPER)
            t = min(t + step, t_slant)
        tops = [sf.t_top(th) for th in ths]
        m = int(math.ceil((max(tops) - 0.006 - t_slant) / STEP_UPPER))
        for j in range(m + 1):
            ring = []
            for k in range(n):
                tk = t_slant + (tops[k] - 0.006 - t_slant) * j / m
                ring.append((tk, self.body_r(tk, k)))
            add(R_BODY, ring)
        # armhole: piped seam
        r_arm = [self.body_r(tops[k] - 0.006, k) for k in range(n)]
        for dt, dr in ((-0.0032, 0.0005), (-0.0016, 0.0014), (-0.0002, 0.0010)):
            add(R_SEAM, [(tops[k] + dt, r_arm[k] + dr) for k in range(n)])
        b_end = len(rings) - 1
        add(R_CAP, [(tops[k] + 0.0006, r_arm[k] - 0.0012) for k in range(n)])

        # to points
        pts = []
        for ring in rings:
            pts.append([sf.point(t, ths[k], r) for k, (t, r) in enumerate(ring)])
        # cap: a dome in the armhole's plane, bulging toward the body
        rim = pts[-1]
        c = sum(rim, Vector()) / n
        normal = Vector()
        for k in range(n):  # Newell
            a, b = rim[k] - c, rim[(k + 1) % n] - c
            normal += a.cross(b)
        normal.normalize()
        if normal.dot(sf.path.frame(sf.t_S).axis) < 0.0:
            normal = -normal
        for s in (0.30, 0.58, 0.82):
            h = CAP_DOME * math.sqrt(1.0 - (1.0 - s) ** 2)
            # the lining is gathered toward the middle: soft radial pleats
            pleat = [CAP_PLEAT * math.sin(math.pi * s) * math.sin(CAP_PLEATS * th + 0.7) for th in ths]
            pts.append([c + (p - c) * (1.0 - s) + normal * (h + pleat[k]) for k, p in enumerate(rim)])
            rings.append([(sf.t_S, 0.0)] * n)
            regions.append(R_CAP)
        vrings, centers, faces = garment.loft(bm, pts, closed=True, cap_end=True)
        centers[0].co = c + normal * CAP_DOME
        fset = set(faces)
        jb = a_end + 8
        probe = [f for f in vrings[jb][0].link_faces if f in fset][0]
        garment.orient(bm, faces, probe, sf.path.frame(rings[jb][0][0]).point(0.0, ths[0], 1.0)
                       - sf.path.frame(rings[jb][0][0]).origin)
        self.vrings, self.center, self.faces = vrings, centers[0], faces
        self.rings, self.regions, self.a_end, self.b_end = rings, regions, a_end, b_end
        self.tops, self.cap_c, self.cap_n = tops, c, normal
        self._attributes(bm, layers)
        return vrings

    # --- per-vertex data -------------------------------------------------------------------------
    def _attributes(self, bm, layers):
        sf, n = self.sf, SLEEVE_COLUMNS
        vrings, rings = self.vrings, self.rings
        L = {name: layers[name] for name in ATTRS}
        arcs, full = [], []
        for ring in vrings:
            acc = [0.0]
            for k in range(1, n + 1):
                acc.append(acc[-1] + (ring[k % n].co - ring[k - 1].co).length)
            arcs.append(acc)
            full.append(acc[-1])

        def arc_at(j, th):
            """Arc position (from column 0) of angle th on ring j."""
            x = (wrap(th - self.th_cut) % (2.0 * math.pi)) / (2.0 * math.pi) * n
            k = int(math.floor(x)) % n
            f = x - math.floor(x)
            return arcs[j][k] * (1.0 - f) + arcs[j][k + 1] * f

        def dist(j, k, a):
            d = abs(arcs[j][k] - a)
            return min(d, full[j] - d)

        orn_u = []
        for j, ring in enumerate(vrings):
            reg = self.regions[j]
            us = []
            for k, v in enumerate(ring):
                t, _ = rings[j][k]
                th = self.thetas[k]
                v[L["region"]] = float(reg)
                v[L["pt"]] = t
                a_orn = arc_at(j, sf.line("orn", t))
                u = arcs[j][k] - a_orn
                u = (u + 0.5 * full[j]) % full[j] - 0.5 * full[j]
                us.append(u)
                seamy = reg in (R_FOLD, R_CUFF, R_LIP, R_UNDER, R_BODY, R_SEAM)
                v[L["so"]] = dist(j, k, arc_at(j, sf.line("out", t))) if seamy else FAR
                v[L["si"]] = dist(j, k, arc_at(j, sf.line("in", t))) if seamy else FAR
                v[L["ct"]] = (t - SLEEVE_OPEN_T) if reg in (R_FOLD, R_CUFF, R_LIP) else -FAR
                v[L["at"]] = (self.tops[k] - t) if reg in (R_BODY, R_SEAM) else (0.0 if reg == R_CAP else FAR)
                dth = wrap(th - sf.th_crook)
                v[L["crook"]] = ((1.0 - smoothstep(abs(dth), 0.8, 1.5)) * (1.0 - smoothstep(abs(t - sf.t_E), 0.03, 0.07))
                                 if reg == R_BODY else 0.0)
                dpt = wrap(th - sf.th_point)
                v[L["rub"]] = ((1.0 - smoothstep(abs(dpt), 0.25, 0.9)) * (1.0 - smoothstep(abs(t - sf.t_E - 0.008), 0.008, 0.045))
                               if reg == R_BODY else 0.0)
            orn_u.append(us)
        c = self.center
        c[L["region"]] = float(R_CAP)
        c[L["pt"]] = sf.t_S
        for name in ("so", "si"):
            c[L[name]] = FAR
        c[L["ct"]] = -FAR
        c[L["at"]] = 0.0
        c[L["crook"]] = 0.0
        c[L["rub"]] = 0.0

        # UVs
        index = {v: (j, k) for j, ring in enumerate(vrings) for k, v in enumerate(ring)}
        orn, bake_uv = layers["OrnUV"], layers["BakeUV"]
        # per-column distance along the surface, restarting at each island
        starts = (0, self.a_end, self.b_end)
        vcol = [[0.0] * n for _ in vrings]
        for j in range(1, len(vrings)):
            for k in range(n):
                vcol[j][k] = vcol[j - 1][k] + (vrings[j][k].co - vrings[j - 1][k].co).length
        e1 = (vrings[-1][0].co - self.cap_c)
        e1 = (e1 - self.cap_n * e1.dot(self.cap_n)).normalized()
        e2 = self.cap_n.cross(e1)
        for f in self.faces:
            js = [index[v][0] if v in index else len(vrings) for v in f.verts]
            jmax = max(js)
            island = 0 if jmax <= self.a_end else (1 if jmax <= self.b_end else 2)
            ks = [index[v][1] for v in f.verts if v in index]
            wrap_face = max(ks) == n - 1 and min(ks) == 0
            # ornament UV (continuous across the back of the sleeve)
            us = []
            for loop in f.loops:
                if loop.vert in index:
                    j, k = index[loop.vert]
                    us.append([orn_u[j][k], j])
                else:
                    us.append([0.0, len(vrings) - 1])
            if max(u for u, _ in us) - min(u for u, _ in us) > 0.25 * min(full[j] for _, j in us):
                for e in us:
                    if e[0] < 0.0:
                        e[0] += full[e[1]]
            for loop, (u, _) in zip(f.loops, us):
                j = index[loop.vert][0] if loop.vert in index else None
                pt = rings[j][index[loop.vert][1]][0] if j is not None else sf.t_S
                loop[orn].uv = (u, pt)
            # bake UV: surface-true strips, the cap projected on its plane
            for loop in f.loops:
                if island == 2:
                    d = loop.vert.co - self.cap_c
                    loop[bake_uv].uv = (d.dot(e1), d.dot(e2))
                    continue
                j, k = index[loop.vert]
                kk = n if (wrap_face and k == 0) else k
                v0 = vcol[starts[island]][k]
                loop[bake_uv].uv = (arcs[j][kk] - 0.5 * full[j], vcol[j][k] - v0)


def build_sleeve(skin, arm, glove_ob, hf, collection, name):
    """The left sleeve as a new mesh object (world coordinates) + its SleeveFrame."""
    sf = SleeveFrame(arm, hf)
    side = hf.side
    ref = skin.copy()
    ref.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(ref)
    rig.extract_by_weight(ref, [f"{side}Shoulder", f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"], 0.5)
    sb = SleeveBuilder(sf, garment.bvh_of(ref), garment.bvh_of(glove_ob))
    rd = ref.data
    bpy.data.objects.remove(ref)
    bpy.data.meshes.remove(rd)

    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    bm = bmesh.new()
    layers = {}
    for uv in UV_HELPERS:
        layers[uv] = bm.loops.layers.uv.new(uv)
    for a in ATTRS:
        layers[a] = bm.verts.layers.float.new(a)
    sb.build(bm, layers)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    return ob, sf, sb
