"""Silena's long leather coat body and its collar (stage 3).

The coat is one grid of rows (neckline -> hem) and columns (her left front edge ->
around the back -> her right front edge), open in front:

- bodice (neckline to the waist, WAIST_Z): rays from a point inside the chest sample
  the torso skin in vertical half-planes (meridians), 1 degree apart; each meridian's
  profile is offset by the ease, pulled toward its convex hull (the coat bridges the
  hollow under the bust, the small of the back), smoothed and resampled by arc length
  into the rows; rows are resampled into columns by arc length between the front
  edges (FRONT_EDGE: x of the edge by height);
- skirt (waist to hem): horizontal rings around everything below it (hips, belt and its
  items, trousers, boots), each ring the convex hull of what it must clear plus a
  clearance, never coming in faster than DRAPE_IN per meter downward (it hangs), with
  an A-line flare toward the hem and soft vertical folds; the lower half has twice the
  columns (pentagons at the transition);
- the stage-2 sleeves sew into armholes: grid faces inside each sleeve's rim ring (the
  ring where the sleeve's closing dome used to start) are cut away and the hole is
  bridged to a band around the rim (garment.zip_loops), then relaxed; bake.py welds
  the rim to the sleeve;
- a lining (violet satin) under the skirt and along the bodice's front edges, joined
  to the leather by rolled edges at the front edges and the hem;
- the high upturned collar is its own mesh on the neckline row (`Collar`).

Bones: six spring chains (COAT_CHAINS x CHAIN_BONES) run down inside the skirt, evenly
spaced around it, children of Hips. Weights: the bodice from the skin (WeightSampler,
smoothed), the skirt from the chains (rig.chain_weights) with Hips at the waist and a
share of the nearer UpperLeg (it follows the legs a little), the collar from the
neckline toward Neck.

Per-vertex data for the coat material (removed after baking): `region` (R_*), `cu` (arc
length along the row from her left front edge, m), `cl` (the row's length, m), `cv`
(distance down from the neckline, m), `hm` (height above the hem along the surface, m),
`ss` (arc distance from the nearest side seam, m), `fold` (fold crest -1..1).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from silena_vesper_common import CHAIN_BONES, CHAIN_INSET, COAT_CHAINS, HEM_Z, WAIST_Z, chain_names
from arcology_blender import garment, rig

AXIS_Y = -0.045                    # vertical axis of the torso (x = 0)
CENTER = Vector((0.0, AXIS_Y, 1.33))
TORSO_BONES = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "LeftShoulder", "RightShoulder")
ALPHAS = np.radians(np.arange(4.0, 176.01, 0.5))
DEGS = np.arange(0, 181)           # left-half meridians, degrees from the front toward +X

N_BODICE_ROWS = 30
N_COLS = 48                        # bodice and upper skirt, front edge to front edge
N_SKIRT_ROWS = 46
SKIRT_DOUBLE_ROW = 20              # skirt rows below this one have 2 * N_COLS columns
SIDE_SEAM_U = 0.285                # side seams at this share of a row from the front edge
THICK = 0.0034                     # leather + lining
ARMHOLE_MARGIN = 0.022             # grid cut back this far around a sleeve's rim
ARMHOLE_BAND = 0.45                # a band around the rim, this share of the way to the cut's edge
ARMHOLE_RELAX = (2, 12)            # rings of grid around the cut that relax, iterations
LINING_STRIP = 4                   # bodice columns lined at each front edge

# neckline height by azimuth (front corner -> back), front edge x by height
NECKLINE = ((0, 1.503), (30, 1.505), (45, 1.540), (60, 1.572), (75, 1.590), (90, 1.598), (120, 1.612),
            (150, 1.618), (180, 1.620))
FRONT_EDGE = ((1.503, 0.064), (1.45, 0.079), (1.40, 0.091), (1.34, 0.098), (1.26, 0.100), (1.14, 0.101),
              (0.95, 0.106), (0.60, 0.120), (0.12, 0.138))
EASE = ((0, 0.011), (40, 0.012), (75, 0.016), (110, 0.016), (150, 0.014), (180, 0.014))
SHOULDER_EASE = 0.008              # on top of the shoulders (the coat rests there)
HULL_BLEND = ((0, 1.0), (45, 0.95), (72, 0.2), (115, 0.15), (140, 0.65), (180, 0.7))

# skirt
CLEAR_HIP, CLEAR_LEG = 0.015, 0.034   # clearance over the hips/belt and over the legs
DRAPE_IN = 0.10                    # how fast the skirt may come back in, per meter down
LEAN_IN = 0.55                     # how fast it may come in going up toward the waist, per meter
FLARE = ((0, 0.075), (60, 0.085), (100, 0.110), (150, 0.125), (180, 0.130))  # extra radius at the hem
FOLD_AMP = 0.032                   # fold depth at the hem
FOLD_EDGE = 0.07                   # folds fade out this close to the front edges

R_OUTER, R_ROLL, R_LINING = 0, 1, 2
ATTRS = ("region", "cu", "cl", "cv", "hm", "ss", "fold", "mate")

# collar
COLLAR_H = ((0.0, 0.066), (0.12, 0.080), (0.3, 0.094), (0.5, 0.100))   # by share along the neckline
COLLAR_THICK = 0.0042
COLLAR_FLARE = 0.016               # the top edge stands this much further out
C_OUTER, C_ROLL, C_INNER = 0, 1, 2
COLLAR_ATTRS = ("region", "cs", "cu", "cl", "cj")


def smoothstep(x, a, b):
    """Smooth 0..1 ramp (floats or numpy arrays)."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def keyed(keys, x):
    """Smooth interpolation through (x, y) keys (clamped)."""
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, y0), (x1, y1) in zip(keys, keys[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * smoothstep(x, x0, x1)
    return keys[-1][1]


def dir_h(deg):
    t = math.radians(deg)
    return Vector((math.sin(t), -math.cos(t), 0.0))


def azimuth(p):
    """Degrees 0..360 of a point around the torso axis (0 = front, 90 = her left)."""
    return math.degrees(math.atan2(p.x, -(p.y - AXIS_Y))) % 360.0


def front_edge_x(z):
    keys = sorted(FRONT_EDGE)
    return keyed(keys, z)


def _farthest(bvh, origin, d, max_r=0.6):
    best, start, r0 = None, origin, 0.0
    for _ in range(8):
        h = bvh.ray_cast(start, d, max_r - r0)
        if h[0] is None:
            break
        best = h[0]
        r0 = (h[0] - origin).length + 1e-5
        start = origin + d * r0
    return best


def _resample(pts, n):
    """n points evenly spaced by arc length along a 2D/3D polyline (numpy)."""
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    acc = np.r_[0.0, np.cumsum(seg)]
    s = np.linspace(0.0, acc[-1], n)
    return np.stack([np.interp(s, acc, pts[:, k]) for k in range(pts.shape[1])], axis=1)


def _smooth(pts, passes, closed=False):
    p = pts.copy()
    for _ in range(passes):
        if closed:
            p = (np.roll(p, 1, axis=0) + 2.0 * p + np.roll(p, -1, axis=0)) * 0.25
        else:
            p[1:-1] = (p[:-2] + 2.0 * p[1:-1] + p[2:]) * 0.25
    return p


def _hull(points):
    """Convex hull (Andrew's monotone chain) of 2D points, counter-clockwise."""
    pts = sorted(set(map(tuple, np.round(points, 7))))
    if len(pts) < 3:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0.0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0.0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def _exit(hull, p, d):
    """Largest t >= 0 with p + t d on the convex polygon `hull` (p inside or on it)."""
    best = 0.0
    n = len(hull)
    for k in range(n):
        a, b = hull[k], hull[(k + 1) % n]
        e = b - a
        den = d[0] * (-e[1]) - d[1] * (-e[0])
        if abs(den) < 1e-12:
            continue
        w = a - p
        t = (w[0] * (-e[1]) - w[1] * (-e[0])) / den
        s = (d[0] * w[1] - d[1] * w[0]) / den
        if -1e-9 <= s <= 1.0 + 1e-9 and t > best:
            best = t
    return best


# --- bodice ---------------------------------------------------------------------------------
class Bodice:
    """Rows x meridians table of the coat's bodice surface (left half, world points)."""

    def __init__(self, skin, top=None):
        ref = skin.copy()
        ref.data = skin.data.copy()
        bpy.context.scene.collection.objects.link(ref)
        rig.extract_by_weight(ref, TORSO_BONES, 0.5)
        self.bvh = garment.bvh_of(ref)
        self.skin = garment.bvh_of(skin)
        self.top = garment.bvh_of(top) if top is not None else None
        rd = ref.data
        bpy.data.objects.remove(ref)
        bpy.data.meshes.remove(rd)
        self.profiles = [self._meridian(deg) for deg in DEGS]   # [deg][row] -> (rho, z)
        self._smooth_across(8)

    def _raw(self, deg):
        dh = dir_h(deg)
        rho, z = [], []
        for a in ALPHAS:
            d = dh * math.sin(a) + Vector((0.0, 0.0, math.cos(a)))
            h = _farthest(self.bvh, CENTER, d)
            if h is None:
                rho.append(np.nan)
                z.append(np.nan)
            else:
                rho.append((h - Vector((0.0, AXIS_Y, h.z))).dot(dh))
                z.append(h.z)
        rho, z = np.array(rho), np.array(z)
        ok = ~np.isnan(rho)
        idx = np.arange(len(rho))
        rho = np.interp(idx, idx[ok], rho[ok])
        z = np.interp(idx, idx[ok], z[ok])
        return rho, np.minimum.accumulate(z)

    def _meridian(self, deg):
        rho, z = self._raw(deg)
        znl = keyed(NECKLINE, deg)
        # z falls along the profile: cut it between the neckline and the waist
        zs = z[::-1]
        r_nl = float(np.interp(znl, zs, rho[::-1]))
        r_w = float(np.interp(WAIST_Z, zs, rho[::-1]))
        inner = (z < znl) & (z > WAIST_Z)
        pts = np.array([(r_nl, znl)] + list(zip(rho[inner], z[inner])) + [(r_w, WAIST_Z)])
        pts = _resample(pts, max(40, int(_length(pts) / 0.002)))
        pts = _smooth(pts, 4)
        t = np.gradient(pts, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None]
        nrm = np.stack([-t[:, 1], t[:, 0]], axis=1)
        if nrm[len(nrm) // 2, 0] < 0.0:
            nrm = -nrm
        top = smoothstep(pts[:, 1], 1.54, 1.585) * (1.0 - smoothstep(abs(deg - 90.0), 35.0, 60.0))
        ease = keyed(EASE, deg) * (1.0 - top) + SHOULDER_EASE * top
        q = pts + nrm * ease[:, None]
        hull = _hull(np.r_[q, [(0.0, q[0, 1]), (0.0, q[-1, 1])]])
        k = keyed(HULL_BLEND, deg)
        q = np.array([p + n * _exit(hull, p, n) * k for p, n in zip(q, nrm)])
        q = _smooth(q, 6)
        return _resample(q, N_BODICE_ROWS + 1)

    def _smooth_across(self, passes=4):
        P = np.array(self.profiles)             # (deg, row, 2)
        for _ in range(passes):
            ext = np.concatenate([P[1:2], P, P[-2:-1]], axis=0)   # mirror at 0 and 180 degrees
            P = (ext[:-2] + 2.0 * P + ext[2:]) * 0.25
        self.profiles = P

    def point(self, deg, row):
        """World point of the bodice at a (fractional) degree on the left half."""
        d = min(max(deg, 0.0), 180.0)
        i = min(int(d), 179)
        f = d - i
        rz = self.profiles[i, row] * (1.0 - f) + self.profiles[i + 1, row] * f
        dh = dir_h(d)
        return Vector((0.0, AXIS_Y, 0.0)) + dh * rz[0] + Vector((0.0, 0.0, rz[1]))


def _length(pts):
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def _row_columns(points, degs, n_half):
    """Left-half row: `points` at increasing degrees `degs` (0..180, dense). Finds her left
    front edge (x = FRONT_EDGE at the point's height), returns n_half + 1 points evenly
    spaced by arc length from the edge to the center back."""
    xs = np.array([p.x - front_edge_x(p.z) for p in points])
    k = int(np.argmax(xs >= 0.0))
    if k == 0:
        k = 1
    f = -xs[k - 1] / (xs[k] - xs[k - 1])
    edge = points[k - 1].lerp(points[k], f)
    pts = np.array([tuple(edge)] + [tuple(p) for p in points[k:]])
    out = _resample(pts, n_half + 1)
    return [Vector(p) for p in out], degs[k - 1] + (degs[k] - degs[k - 1]) * f


def _mirror(v):
    return Vector((-v.x, v.y, v.z))


MIN_CLEAR = 0.0110                 # the bodice never comes closer to the skin (top + lining + air)


TOP_CLEAR = 0.0062                 # ... and from the top under it (lining + air)
ARMHOLE_CALM = (0.07, 0.10)        # no clearance push within this distance of an armhole's center


def _push(bodice, p, holes=()):
    """Displacement that brings p to MIN_CLEAR over the skin and TOP_CLEAR over the top
    (fading out around the armholes' centers `holes`: they are the zip's business, and the
    arms in the skin would push the surface inside them outward)."""
    fade = 1.0
    for h in holes:
        fade = min(fade, float(smoothstep((p - h).length, ARMHOLE_CALM[0], ARMHOLE_CALM[1])))
    if fade <= 0.0:
        return Vector()
    d_out = Vector()
    for bvh, clear in ((bodice.skin, MIN_CLEAR), (bodice.top, TOP_CLEAR)):
        if bvh is None:
            continue
        q = p + d_out
        loc, nrm, _, _ = bvh.find_nearest(q)
        if loc is None:
            continue
        d = (q - loc).dot(nrm)
        if d < clear:
            d_out += nrm * (clear - d)
    return d_out * fade


def _keep_clear(bodice, half_rows, holes, passes=3, smooth=5):
    """Push the left half of the bodice grid out to its clearances (smoothing across the
    meridians lowers the bust's apex): the displacements are smoothed over the grid before
    they apply, so neighbors never fold over each other, then a last exact push."""
    P = np.array([[tuple(p) for p in row] for row in half_rows])
    R, C = P.shape[:2]
    for _ in range(passes):
        D = np.array([[tuple(_push(bodice, Vector(P[r, c]), holes)) for c in range(C)] for r in range(R)])
        for _ in range(smooth):
            E = D.copy()
            E[1:-1, :] = (D[:-2, :] + 2.0 * D[1:-1, :] + D[2:, :]) * 0.25
            F = E.copy()
            F[:, 1:-1] = (E[:, :-2] + 2.0 * E[:, 1:-1] + E[:, 2:]) * 0.25
            F[:, -1] = (E[:, -2] * 2.0 + E[:, -1] * 2.0) * 0.25     # the center back is a mirror line
            D = F
        P += D
    for r in range(R):
        for c in range(C):
            v = Vector(P[r, c])
            v += _push(bodice, v, holes)
            half_rows[r][c] = v
        half_rows[r][-1].x = 0.0


def _relax_grid(half_rows, iterations=10, factor=0.5):
    """Even out the bodice grid: rows resampled per meridian by arc length run wavy over
    the bust and can cross; interior points move toward their neighbors' mean, the front
    edge along itself (neckline, waist and center back stay), _keep_clear restores the
    clearance after."""
    P = np.array([[tuple(p) for p in row] for row in half_rows])
    for _ in range(iterations):
        M = (P[:-2, 1:-1] + P[2:, 1:-1] + P[1:-1, :-2] + P[1:-1, 2:]) * 0.25
        P[1:-1, 1:-1] = P[1:-1, 1:-1] * (1.0 - factor) + M * factor
        # the front edge evens out along itself (its rows bunch up over the bust)
        P[1:-1, 0] = P[1:-1, 0] * (1.0 - factor) + (P[:-2, 0] + P[2:, 0]) * 0.5 * factor
    for r, row in enumerate(half_rows):
        for c in range(0, len(row) - 1):
            if 0 < r < len(half_rows) - 1:
                row[c] = Vector(P[r, c])


def bodice_rows(bodice, rims=()):
    """Rows of the bodice as lists of N_COLS + 1 points, her left front edge first."""
    halves = []
    fine = np.arange(0.0, 180.001, 0.5)
    for r in range(N_BODICE_ROWS + 1):
        pts = [bodice.point(d, r) for d in fine]
        half, _ = _row_columns(pts, fine, N_COLS // 2)
        halves.append(half)
    _relax_grid(halves)
    holes = [sum((Vector(p) for p in rim), Vector()) / len(rim) for rim in rims]
    _keep_clear(bodice, halves, holes)
    return [half + [_mirror(p) for p in reversed(half[:-1])] for half in halves]


# --- skirt ------------------------------------------------------------------------------------
def _fold_wave(deg, side_seed):
    a = math.radians(deg)
    return (0.60 * math.sin(7.0 * a + 0.9 + side_seed) + 0.30 * math.sin(11.0 * a + 2.1 + 1.7 * side_seed)
            + 0.10 * math.sin(17.0 * a + 0.4))


def skirt_rows(waist_row, obstacles):
    """Rings from the waist row (shared) down to the hem, each a list of points from her
    left front edge around the back to her right front edge. `obstacles`: a BVH of
    everything the skirt must clear (rest pose)."""
    s = np.linspace(0.0, 1.0, N_SKIRT_ROWS + 1)
    zs = WAIST_Z - (WAIST_Z - HEM_Z) * (0.55 * s + 0.45 * s * s)   # denser over the hips and the belt
    degs = np.arange(0, 360)
    # waist ring radius by degree (from the bodice's row; full circle by mirroring)
    wr = {}
    for p in waist_row:
        wr[azimuth(p)] = (p - Vector((0.0, AXIS_Y, p.z))).length
    keys = sorted(wr.items())
    kd = np.array([k for k, _ in keys])
    kv = np.array([v for _, v in keys])
    r_prev = np.interp(degs, kd, kv, period=360.0)
    # the front gap at the waist: hold the edge's radius across it
    rings = [r_prev]
    for z in zs[1:]:
        ro = np.zeros(len(degs))
        for dz in (-0.012, 0.0, 0.012):    # what lies between this ring and its neighbors too
            for k, deg in enumerate(degs):
                o = Vector((0.0, AXIS_Y, z + dz))
                h = _farthest(obstacles, o, dir_h(deg), 0.5)
                if h is not None:
                    ro[k] = max(ro[k], (h - o).length)
        clear = CLEAR_LEG + (CLEAR_HIP - CLEAR_LEG) * smoothstep(z, 0.76, 0.95)
        rb = np.where(ro > 0.0, ro + clear, 0.0)
        rb = np.maximum(rb, rb[(360 - degs) % 360])          # symmetric coat
        pts = np.stack([np.sin(np.radians(degs)) * rb, -np.cos(np.radians(degs)) * rb], axis=1)
        hull = _hull(np.r_[pts, [[0.0, 0.0]]])
        rh = np.array([_exit(hull, np.zeros(2), np.array([math.sin(math.radians(d)), -math.cos(math.radians(d))]))
                       for d in degs])
        r = np.maximum(rh, rings[-1] - DRAPE_IN * (zs[len(rings) - 1] - z))
        rings.append(r)
    R = np.array(rings)
    # the panel above a bulge (hips, belt items) leans out toward it gradually, no ledge
    for kk in range(len(zs) - 2, 0, -1):
        R[kk] = np.maximum(R[kk], R[kk + 1] - LEAN_IN * (zs[kk] - zs[kk + 1]))
    # flare toward the hem, smoothing around and along
    for k, z in enumerate(zs):
        if k == 0:
            continue
        w = smoothstep(0.95 - z, 0.0, 0.83)
        R[k] += np.array([keyed(FLARE, d if d <= 180 else 360 - d) for d in degs]) * w
    for _ in range(3):
        R[1:] = (np.roll(R[1:], 1, axis=1) + 2.0 * R[1:] + np.roll(R[1:], -1, axis=1)) * 0.25
    for _ in range(2):
        R[1:-1] = np.maximum(R[1:-1], (R[:-2] + 2.0 * R[1:-1] + R[2:]) * 0.25)
    out, folds = [waist_row], [[0.0] * len(waist_row)]
    for k in range(1, len(zs)):
        z = zs[k]
        amp = FOLD_AMP * smoothstep(1.02 - z, 0.0, 0.75)
        pts = []
        for d in np.arange(0.0, 360.0, 0.5):
            i0 = int(d) % 360
            rr = R[k, i0] * (1.0 - (d - int(d))) + R[k, (i0 + 1) % 360] * (d - int(d))
            pts.append((d, Vector((0.0, AXIS_Y, z)) + dir_h(d) * rr))
        n = N_COLS * (2 if k >= SKIRT_DOUBLE_ROW else 1)
        ring, fl = _skirt_columns(pts, z, n, amp)
        out.append(ring)
        folds.append(fl)
    return out, folds


def _skirt_columns(pts, z, n, amp):
    """One skirt ring: from her left front edge (x = FRONT_EDGE) around the back to the
    right edge, folds added along the normal, n + 1 points evenly by arc length."""
    xe = front_edge_x(z)
    left = [(d, p) for d, p in pts if d <= 90.0]
    right = [(d, p) for d, p in pts if d >= 270.0]
    k = next(i for i, (d, p) in enumerate(left) if p.x >= xe)
    (d0, p0), (d1, p1) = left[k - 1], left[k]
    f = (xe - p0.x) / (p1.x - p0.x)
    start = (d0 + (d1 - d0) * f, p0.lerp(p1, f))
    k2 = next(i for i, (d, p) in enumerate(right) if p.x >= -xe)
    (d0, p0), (d1, p1) = right[k2 - 1], right[k2]
    f = (-xe - p0.x) / (p1.x - p0.x)
    end = (d0 + (d1 - d0) * f, p0.lerp(p1, f))
    seq = [start] + [(d, p) for d, p in pts if start[0] < d < end[0]] + [end]
    # folds: along the ring's outward normal, fading at the front edges
    arc = np.r_[0.0, np.cumsum([(b[1] - a[1]).length for a, b in zip(seq, seq[1:])])]
    total = arc[-1]
    fpts, fv = [], []
    for (d, p), s in zip(seq, arc):
        edge = smoothstep(min(s, total - s), 0.0, FOLD_EDGE)
        w = _fold_wave(d, 0.0 if d <= 180.0 else 2.3) * edge
        out = (p - Vector((0.0, AXIS_Y, p.z))).normalized()
        fpts.append(p + out * amp * w)
        fv.append(w)
    arr = np.array([tuple(p) for p in fpts])
    seg = np.linalg.norm(np.diff(arr, axis=0), axis=1)
    acc = np.r_[0.0, np.cumsum(seg)]
    s = np.linspace(0.0, acc[-1], n + 1)
    ring = [Vector([float(np.interp(x, acc, arr[:, c])) for c in range(3)]) for x in s]
    folds = [float(np.interp(x, acc, np.array(fv))) for x in s]
    return ring, folds


# --- mesh -------------------------------------------------------------------------------------
class CoatMesh:
    def __init__(self, rows, folds, rims, under=None):
        self.rows, self.folds, self.rims = rows, folds, rims
        self.under = under            # BVH of the garment under the bodice (the lining stays off it)
        self.bm = bmesh.new()
        self.layers = {a: self.bm.verts.layers.float.new(a) for a in ATTRS}
        self.mates = []          # (lining or roll vertex, its leather vertex)
        self.armhole_seams = []  # (vertex, vertex) around each armhole band

    def build(self):
        bm, rows = self.bm, self.rows
        self.grid = [[bm.verts.new(p) for p in row] for row in rows]
        faces = []
        for r in range(len(rows) - 1):
            a, b = self.grid[r], self.grid[r + 1]
            if len(b) == len(a):
                for c in range(len(a) - 1):
                    faces.append(bm.faces.new((a[c], a[c + 1], b[c + 1], b[c])))
            else:
                for c in range(len(a) - 1):
                    faces.append(bm.faces.new((a[c], a[c + 1], b[2 * c + 2], b[2 * c + 1], b[2 * c])))
        self.outer_faces = list(faces)       # ordered (sets of bmesh elements iterate by address)
        bm.normal_update()
        probe = faces[(len(rows) // 2) * (N_COLS) + N_COLS // 2]     # back of the skirt
        self.probe = probe
        garment.orient(bm, faces, probe, probe.calc_center_median() - Vector((0.0, AXIS_Y, probe.calc_center_median().z)))
        self._attributes()
        self.armholes = [self._armhole(rim) for rim in self.rims]
        bm.normal_update()
        self._lining()
        bm.verts.index_update()
        L = self.layers
        for v in bm.verts:
            v[L["mate"]] = float(v.index)
        for w, v in self.mates:
            w[L["mate"]] = float(v.index)
        return bm

    # per-vertex coordinates along rows and columns
    def _attributes(self):
        L = self.layers
        n_rows = len(self.grid)
        down = [0.0] * len(self.grid[0])
        prev = self.grid[0]
        self.row_len = []
        cv_rows = []
        for r, row in enumerate(self.grid):
            if r > 0:
                if len(row) == len(prev):
                    down = [down[c] + (row[c].co - prev[c].co).length for c in range(len(row))]
                else:
                    nd = []
                    for c in range(len(row)):
                        if c % 2 == 0:
                            nd.append(down[c // 2] + (row[c].co - prev[c // 2].co).length)
                        else:
                            m = (prev[c // 2].co + prev[c // 2 + 1].co) * 0.5
                            nd.append((down[c // 2] + down[c // 2 + 1]) * 0.5 + (row[c].co - m).length)
                    down = nd
            cv_rows.append(down)
            prev = row
        total = cv_rows[-1]
        for r, row in enumerate(self.grid):
            acc = [0.0]
            for a, b in zip(row, row[1:]):
                acc.append(acc[-1] + (b.co - a.co).length)
            length = acc[-1]
            self.row_len.append(length)
            last_total = total if len(row) == len(total) else [total[min(2 * c, len(total) - 1)] for c in range(len(row))]
            for c, v in enumerate(row):
                u = acc[c]
                v[L["region"]] = float(R_OUTER)
                v[L["cu"]] = u
                v[L["cl"]] = length
                v[L["cv"]] = cv_rows[r][c]
                v[L["hm"]] = max(last_total[c] - cv_rows[r][c], 0.0)
                s0, s1 = (acc[k] for k in self.seam_columns(len(row))[1:])
                v[L["ss"]] = min(abs(u - s0), abs(u - s1))
                v[L["fold"]] = self.folds[r][c] if r < len(self.folds) else 0.0
        self.n_rows = n_rows

    # armholes ---------------------------------------------------------------------------
    def _armhole(self, rim):
        """Cut the grid inside one sleeve rim (with a margin) and bridge the hole to it."""
        bm = self.bm
        L = self.layers
        pts = [Vector(p) for p in rim]
        c = sum(pts, Vector()) / len(pts)
        nrm = Vector()
        for k in range(len(pts)):
            nrm += (pts[k] - c).cross(pts[(k + 1) % len(pts)] - c)
        nrm.normalize()
        if nrm.dot(Vector((c.x, 0.0, 0.0))) < 0.0:
            nrm = -nrm                                  # toward the arm (away from the body)
        e1 = (pts[0] - c)
        e1 = (e1 - nrm * e1.dot(nrm)).normalized()
        e2 = nrm.cross(e1)
        margin = ARMHOLE_MARGIN
        poly = []
        for p in pts:   # the rim in its plane, grown by the margin (star-shaped around c)
            x, y = (p - c).dot(e1), (p - c).dot(e2)
            r = math.hypot(x, y)
            poly.append((x * (r + margin) / r, y * (r + margin) / r))

        def inside(p):
            q = p - c
            if abs(q.dot(nrm)) > 0.07:
                return False
            x, y = q.dot(e1), q.dot(e2)
            hit = False
            for k in range(len(poly)):
                (x0, y0), (x1, y1) = poly[k], poly[(k + 1) % len(poly)]
                if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                    hit = not hit
            return hit

        bvh = BVHTree.FromBMesh(bm)
        doomed = [f for f in self.outer_faces if inside(f.calc_center_median())]
        gone = set(doomed)
        self.outer_faces = [f for f in self.outer_faces if f not in gone]
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.verts.index_update()
        edge_v = {v for e in bm.edges if e.is_boundary for v in e.verts}
        hole = sorted((v for v in edge_v if (v.co - c).length < 0.17 and not self._on_outer_boundary(v)),
                      key=lambda v: v.index)
        loop = garment.boundary_loop(hole)
        if len(loop) != len(hole):
            print(f"COAT armhole: boundary loop {len(loop)} of {len(hole)} vertices")
        self.armhole_seams += list(zip(loop, loop[1:] + loop[:1]))   # the band is its own UV island
        # rim ring (exactly the sleeve's) and a band a share of the way to the cut's edge
        # (never past it, so the strip can't fold back over the rim where the sleeve head
        # stands above the shoulder)
        rim_v = [bm.verts.new(p) for p in pts]
        edge_pts = [v.co.copy() for v in loop]
        band = []
        for p in pts:
            best = None
            for a, b in zip(edge_pts, edge_pts[1:] + edge_pts[:1]):
                ab = b - a
                t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
                q = a + ab * t
                if best is None or (q - p).length < (best - p).length:
                    best = q
            q = p.lerp(best, ARMHOLE_BAND)
            loc = bvh.find_nearest(q)[0]
            band.append(bm.verts.new(loc if loc is not None and (loc - q).length < 0.004 else q))
        new = []
        n = len(pts)
        for k in range(n):
            new.append(bm.faces.new((rim_v[k], rim_v[(k + 1) % n], band[(k + 1) % n], band[k])))
        new += garment.zip_loops(bm, band, loop, c, nrm)
        self.outer_faces += new
        faces = [f for f in self.outer_faces if f.is_valid]
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        probe = self.probe
        out = probe.calc_center_median() - Vector((0.0, AXIS_Y, probe.calc_center_median().z))
        if probe.normal.dot(out) < 0.0:
            bmesh.ops.reverse_faces(bm, faces=faces)
            bm.normal_update()
        # attributes from the nearest old grid vertex
        for v in rim_v + band:
            near = min(hole, key=lambda h: (h.co - v.co).length_squared)
            for a in ATTRS:
                v[L[a]] = near[L[a]]
        # relax the zip: the hole's edge and two rings of grid around it slide toward their
        # neighbors' mean (the rim and band stay)
        fixed = set(rim_v) | set(band)
        zone = set(hole)
        for _ in range(ARMHOLE_RELAX[0]):
            zone |= {e.other_vert(v) for v in list(zone) for e in v.link_edges}
        zone -= fixed
        bm.verts.index_update()
        zone = sorted((v for v in zone if not self._on_outer_boundary(v)), key=lambda v: v.index)
        for _ in range(ARMHOLE_RELAX[1]):
            new_co = {}
            for v in zone:
                nb = [e.other_vert(v).co for e in v.link_edges]
                new_co[v] = v.co * 0.5 + (sum(nb, Vector()) / len(nb)) * 0.5
            for v, co in new_co.items():
                v.co = co
        return {"rim": rim_v, "band": band, "center": c, "normal": nrm}

    def _on_outer_boundary(self, v):
        """Neckline, front edges, hem: boundary vertices that aren't the armhole's."""
        L = self.layers
        if not any(e.is_boundary for e in v.link_edges):
            return False
        cu, cl = v[L["cu"]], v[L["cl"]]
        return v[L["cv"]] < 1e-6 or cu < 1e-6 or cl - cu < 1e-6 or v[L["hm"]] < 1e-6

    # lining and rolled edges ---------------------------------------------------------------------
    def _lining(self):
        bm, L = self.bm, self.layers
        grid = self.grid
        n_b = N_BODICE_ROWS
        lining = {}
        for r, row in enumerate(grid):
            for c, v in enumerate(row):
                lined = r >= n_b or c <= LINING_STRIP or c >= len(row) - 1 - LINING_STRIP
                if not lined or not v.is_valid:
                    continue
                depth = THICK
                while self.under is not None and r < n_b and depth > 0.0009:
                    q = v.co - v.normal * depth           # the lining stays 1.5 mm off the top
                    loc, nrm, _, _ = self.under.find_nearest(q)
                    if loc is None or (q - loc).dot(nrm) >= 0.0015:
                        break
                    depth -= 0.0004
                w = bm.verts.new(v.co - v.normal * depth)
                for a in ATTRS:
                    w[L[a]] = v[L[a]]
                w[L["region"]] = float(R_LINING)
                lining[v] = w
                self.mates.append((w, v))
        faces = []
        for f in list(self.outer_faces):
            if not f.is_valid or not all(v in lining for v in f.verts):
                continue
            faces.append(bm.faces.new([lining[v] for v in reversed(f.verts)]))
        # rolled edges: front edges (first and last column) and the hem (last row), each a
        # half round from the leather to the lining, bulging away from the panel
        rolls, self.roll_seams = [], []
        left = [(row[0], row[1]) for row in grid]
        right = [(row[-1], row[-2]) for row in grid]
        hem = [(v, None) for v in grid[-1]]
        above = grid[-2]
        hem_cuts = set(self.seam_columns(len(grid[-1])))
        for chain in (left, right, hem):
            rings = []
            outs = []
            for k, (v, inner) in enumerate(chain):
                a = chain[max(k - 1, 0)][0].co
                b = chain[min(k + 1, len(chain) - 1)][0].co
                along = (b - a).normalized()
                out = along.cross(v.normal).normalized()
                if inner is None:   # hem: away from the row above
                    c = k if len(above) == len(chain) else k // 2
                    away = v.co - above[min(c, len(above) - 1)].co
                else:
                    away = v.co - inner.co
                outs.append(out if out.dot(away) >= 0.0 else -out)
            for _ in range(3):      # no twist where the edge bends (over the bust)
                outs = [(outs[max(i - 1, 0)] + outs[i] * 2.0 + outs[min(i + 1, len(outs) - 1)]).normalized()
                        for i in range(len(outs))]
            for k, (v, inner) in enumerate(chain):
                if v not in lining:
                    rings.append(None)
                    continue
                out = outs[k]
                out = (out - v.normal * out.dot(v.normal)).normalized()
                mid = v.co - v.normal * (THICK * 0.5)
                ring = [v]
                for ang in (55.0, 125.0):
                    t = math.radians(ang)
                    p = mid + v.normal * (THICK * 0.5 * math.cos(t)) + out * (THICK * 0.62 * math.sin(t))
                    w = bm.verts.new(p)
                    for a_ in ATTRS:
                        w[L[a_]] = v[L[a_]]
                    w[L["region"]] = float(R_ROLL)
                    ring.append(w)
                    self.mates.append((w, v))
                ring.append(lining[v])
                rings.append(ring)
                if inner is None and k in hem_cuts:      # the seams go on through the rolled hem
                    self.roll_seams += [(ring[0], ring[1]), (ring[1], ring[2]), (ring[2], ring[3])]
            for r0, r1 in zip(rings, rings[1:]):
                if r0 is None or r1 is None:
                    continue
                for j in range(3):
                    q = (r0[j], r1[j], r1[j + 1], r0[j + 1])
                    if bm.faces.get(q) is None:
                        rolls.append(bm.faces.new(q))
                self.roll_seams.append((r0[2], r1[2]))
        bm.normal_update()
        self.lining = lining
        self.lining_faces = faces
        self.roll_faces = rolls
        # one consistent winding over leather, rolls and lining, facing out on the leather
        allf = [f for f in bm.faces if f.is_valid]
        bmesh.ops.recalc_face_normals(bm, faces=allf)
        probe = self.probe
        out = probe.calc_center_median() - Vector((0.0, AXIS_Y, probe.calc_center_median().z))
        if probe.normal.dot(out) < 0.0:
            bmesh.ops.reverse_faces(bm, faces=allf)
        bm.normal_update()

    @staticmethod
    def seam_columns(n_points):
        """Column indices of the center back and the two side seams in a row of n points
        (the doubled skirt rows keep the upper rows' seam columns)."""
        n = n_points - 1
        side = round(SIDE_SEAM_U * N_COLS) * (n // N_COLS)
        return n // 2, side, n - side

    def mark_seams(self):
        """UV seams: center back, side seams (and shoulder seams above the armholes, same
        columns), the middle of the rolled edges (leather vs lining)."""
        for a, b in self.roll_seams + self.armhole_seams:
            if not (a.is_valid and b.is_valid):
                continue
            e = self.bm.edges.get((a, b))
            if e is not None:
                e.seam = True
        for r in range(len(self.grid) - 1):
            row, nxt = self.grid[r], self.grid[r + 1]
            for c in self.seam_columns(len(row)):
                c2 = c if len(nxt) == len(row) else 2 * c
                a, b = row[c], nxt[c2]
                for x, y in ((a, b), (self.lining.get(a), self.lining.get(b))):
                    if x is None or y is None or not x.is_valid or not y.is_valid:
                        continue
                    e = self.bm.edges.get((x, y))
                    if e is not None:
                        e.seam = True


def build_coat(skin, obstacles, rims, collection, top=None):
    """The coat body as a new object `Coat` (world coordinates) and its grid rows; `top`
    (the garment under the bodice) is kept clear too."""
    bodice = Bodice(skin, top)
    rows = bodice_rows(bodice, rims)
    skirt, folds = skirt_rows(rows[-1], obstacles)
    all_rows = rows + skirt[1:]
    all_folds = [[0.0] * len(r) for r in rows] + folds[1:]
    cm = CoatMesh(all_rows, all_folds, rims, bodice.top)
    bm = cm.build()
    cm.mark_seams()
    me = bpy.data.meshes.new("Coat")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("Coat", me)
    collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    info = {
        "neckline": [tuple(v.co) for v in cm.grid[0]],
        "rows": [[tuple(v.co) if v.is_valid else None for v in row] for row in cm.grid],
        "rims": [[tuple(v.co) for v in a["rim"]] for a in cm.armholes],
    }
    bm.free()
    return ob, info


# --- chains and weights --------------------------------------------------------------------------
def chain_points(info):
    """Joint positions (armature = world space) and outward normals of each skirt chain:
    evenly spaced around the skirt (chain k at (k + 0.5) / 6 of each row's length),
    joints at every quarter of the skirt's rows, CHAIN_INSET inside the outer surface."""
    rows = info["rows"][N_BODICE_ROWS:]
    picks = [round(k * N_SKIRT_ROWS / CHAIN_BONES) for k in range(CHAIN_BONES + 1)]
    out = []
    for ci, name in enumerate(COAT_CHAINS):
        u = (ci + 0.5) / len(COAT_CHAINS)
        joints, normals = [], []
        for r in picks:
            row = [Vector(p) for p in rows[r]]
            acc = [0.0]
            for a, b in zip(row, row[1:]):
                acc.append(acc[-1] + (b - a).length)
            s = u * acc[-1]
            k = max(i for i in range(len(acc)) if acc[i] <= s)
            k = min(k, len(row) - 2)
            f = (s - acc[k]) / max(acc[k + 1] - acc[k], 1e-9)
            p = row[k].lerp(row[k + 1], f)
            out_dir = (p - Vector((0.0, AXIS_Y, p.z))).normalized()
            joints.append(p - out_dir * CHAIN_INSET)
            normals.append(out_dir)
        out.append((name, joints, normals))
    return out


def add_chains(arm, info):
    """The six coat chains (rig.add_bone_chain), children of Hips."""
    for name, joints, normals in chain_points(info):
        rig.add_bone_chain(arm, "Hips", chain_names(name), joints, normals[:-1])


ARM_FOLLOW = (0.35, 0.07)          # share of UpperArm on the coat at an armhole's rim, fading out over 7 cm


def arm_follow(d):
    """Extra UpperArm share at distance d from an armhole rim (the sleeve's head pulls the
    coat around the armhole along when the arm swings; bake.py gives the sleeves' top the
    same, so both sides of the seam agree)."""
    return ARM_FOLLOW[0] * (1.0 - smoothstep(d, 0.0, ARM_FOLLOW[1]))


def with_arm_follow(w, side, d):
    f = arm_follow(d)
    if f <= 0.0:
        return w
    out = {k: x * (1.0 - f) for k, x in w.items()}
    out[f"{side}UpperArm"] = out.get(f"{side}UpperArm", 0.0) + f
    return out


ARM_REACH = (0.06, 0.10)           # beyond this distance from an armhole the coat has no UpperArm weight


LEG_SHARE = ((0, 0.62), (40, 0.60), (80, 0.52), (120, 0.48), (160, 0.45), (180, 0.45))
BOTH_LEGS = 0.11                   # the middle of the back follows both legs over this half-width


def weight_coat(ob, skin, arm, info):
    """Bodice from the skin (sampled, smoothed); skirt from the chains, Hips toward the
    waist and a share of the nearer UpperLeg; the lining and rolled edges copy their
    leather vertex; the armhole rims keep the plain skin sample (bake.py gives the
    sleeves' rims the same); at most 4 bones, normalized."""
    bones = sorted(b.name for b in arm.data.bones if b.use_deform)
    sampler = garment.WeightSampler(skin, bones)
    chains = [chain_names(n) for n in COAT_CHAINS]
    me = ob.data
    n = len(me.vertices)
    mate = [int(round(d.value)) for d in me.attributes["mate"].data]
    rim_pts = {tuple(round(c, 6) for c in p) for rim in info["rims"] for p in rim}
    rim = {v.index for v in me.vertices if tuple(round(c, 6) for c in v.co) in rim_pts}
    rims = [[Vector(p) for p in r] for r in info["rims"]]

    def rim_dist(p):
        side = "Left" if p.x > 0.0 else "Right"
        r = rims[0] if p.x > 0.0 else rims[1]
        return side, min((p - q).length for q in r)

    weights = [None] * n
    for v in me.vertices:
        if mate[v.index] != v.index:
            continue
        p = v.co
        wb = sampler.at(p)
        if p.z >= WAIST_Z + 1e-4:
            weights[v.index] = garment.limit_dict(with_arm_follow(wb, *rim_dist(p)), 4)
            continue
        f_c = smoothstep(WAIST_Z - p.z, 0.02, 0.17)
        wc = rig.chain_weights(arm, chains, p, power=3.0, joint_blend=0.35)
        deg = azimuth(p)
        a = deg if deg <= 180.0 else 360.0 - deg
        leg = keyed(LEG_SHARE, a) * smoothstep(WAIST_Z - p.z, 0.05, 0.42)
        side = "Left" if p.x > 0.0 else "Right"
        both = 1.0 - smoothstep(abs(p.x), 0.0, BOTH_LEGS)
        wl = {f"{side}UpperLeg": 1.0 - 0.5 * both}
        if both > 0.0:
            other = "Right" if side == "Left" else "Left"
            wl[f"{other}UpperLeg"] = 0.5 * both
        hips = {k: w for k, w in wb.items() if k in ("Hips", "Spine", "LeftUpperLeg", "RightUpperLeg")}
        tot = sum(hips.values())
        hips = {k: w / tot for k, w in hips.items()} if tot > 0.0 else {"Hips": 1.0}
        out = {}
        for d, share in ((hips, 1.0 - f_c), (wc, f_c * (1.0 - leg)), (wl, f_c * leg)):
            for k, w in d.items():
                out[k] = out.get(k, 0.0) + w * share
        weights[v.index] = garment.limit_dict(out, 4)
    for i in range(n):
        if weights[i] is None:
            weights[i] = dict(weights[mate[i]])
    garment.set_weights(ob, weights)
    upper = [i for i in range(n) if mate[i] == i and me.vertices[i].co.z > WAIST_Z - 0.20 and i not in rim]
    garment.smooth_weights(ob, upper, bones, iterations=8, factor=0.5)
    weights = garment.weights_of(ob)
    for i in range(n):          # the yoke away from the armholes doesn't ride the arm (the collar sits on it)
        if mate[i] != i or i in rim:
            continue
        side, d = rim_dist(me.vertices[i].co)
        f = smoothstep(d, ARM_REACH[0], ARM_REACH[1])
        ua = f"{side}UpperArm"
        if f > 0.0 and weights[i].get(ua, 0.0) > 0.0:
            moved = weights[i].pop(ua) * f
            if moved < 1.0 and (1.0 - f) > 0.0:
                weights[i][ua] = moved / f * (1.0 - f)
            sh = f"{side}Shoulder"
            weights[i][sh] = weights[i].get(sh, 0.0) + moved
    for i in range(n):
        if mate[i] != i:
            weights[i] = dict(weights[mate[i]])
    garment.set_weights(ob, [garment.limit_dict(w, 4) for w in weights])
    return rim


# --- collar ------------------------------------------------------------------------------------
def build_collar(info, coat, collection):
    """The upturned collar on the coat's neckline row: outer face, rolled top edge, inner
    face, a narrow bottom strip inside the neckline, closed front ends."""
    base = [Vector(p) for p in info["neckline"]]
    n = len(base)
    rows1 = [Vector(p) for p in info["rows"][1]]
    acc = [0.0]
    for a, b in zip(base, base[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    bm = bmesh.new()
    L = {a: bm.verts.layers.float.new(a) for a in COLLAR_ATTRS}
    rings = []      # rings[j] = list over the cross-section
    for j, (b, r1) in enumerate(zip(base, rows1)):
        s = acc[j] / total
        share = min(s, 1.0 - s)
        h = keyed(COLLAR_H, share)
        out = (b - Vector((0.0, AXIS_Y, b.z)))
        out.z = 0.0
        out.normalize()
        up = (b - r1).normalized()           # continues the coat's surface upward
        d = (up * 0.35 + Vector((0.0, 0.0, 1.0)) * 0.65).normalized()
        sec = []
        for k in range(6):                   # outer face, bottom to top
            t = k / 5.0
            p = b + d * h * t + out * (COLLAR_FLARE * t * t - 0.0008 * math.sin(math.pi * t))
            sec.append((p, C_OUTER, t))
        top = sec[-1][0]
        for ang in (60.0, 120.0):            # the rolled top edge
            a = math.radians(ang)
            p = top - out * (COLLAR_THICK * 0.5 * (1.0 - math.cos(a))) + d * (COLLAR_THICK * 0.55 * math.sin(a))
            sec.append((p, C_ROLL, 1.0))
        for k in range(5, -1, -1):           # inner face, top to bottom
            t = k / 5.0
            p = b + d * h * t + out * (COLLAR_FLARE * t * t - 0.0008 * math.sin(math.pi * t)) - out * COLLAR_THICK
            sec.append((p, C_INNER, t))
        verts = []
        for p, region, t in sec:
            v = bm.verts.new(p)
            v[L["region"]] = float(region)
            v[L["cs"]] = t * h
            v[L["cu"]] = acc[j]
            v[L["cl"]] = total
            v[L["cj"]] = float(j)
            verts.append(v)
        rings.append(verts)
    m = len(rings[0])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(m - 1):
            faces.append(bm.faces.new((a[k], b[k], b[k + 1], a[k + 1])))
        faces.append(bm.faces.new((a[m - 1], b[m - 1], b[0], a[0])))      # bottom strip
    caps = [bm.faces.new(list(reversed(rings[0]))), bm.faces.new(rings[-1])]
    bm.normal_update()
    probe = faces[(n // 2) * m + 2]
    c = probe.calc_center_median()
    garment.orient(bm, faces + caps, probe, c - Vector((0.0, AXIS_Y, c.z)))
    for f in caps:
        f.normal_update()
        cc = f.calc_center_median()
        side = Vector((1.0 if cc.x > 0 else -1.0, -0.6, 0.0))
        if f.normal.dot(side) < 0.0:
            f.normal_flip()
    # UV seam at the back of the rolled edge's middle and around the bottom strip
    for e in bm.edges:
        a, b = e.verts
        if round(a[L["region"]]) == C_ROLL and round(b[L["region"]]) == C_ROLL:
            e.seam = True
    me = bpy.data.meshes.new("Collar")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Collar", me)
    collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def weight_collar(ob, coat, arm, info):
    """The base ring takes the coat's neckline weights exactly (same points); up the
    collar a growing share goes to Neck (more at the back than at the front ends)."""
    from mathutils.kdtree import KDTree

    cme = coat.data
    kd = KDTree(len(cme.vertices))
    for v in cme.vertices:
        kd.insert(coat.matrix_world @ v.co, v.index)
    kd.balance()
    cw = garment.weights_of(coat)
    base = [cw[kd.find(Vector(p))[1]] for p in info["neckline"]]
    me = ob.data
    cs, cu, cl, cj = (me.attributes[a].data for a in ("cs", "cu", "cl", "cj"))
    out = []
    for v in me.vertices:
        i = v.index
        w = dict(base[int(round(cj[i].value))])
        s = cu[i].value / max(cl[i].value, 1e-6)
        back = smoothstep(min(s, 1.0 - s), 0.05, 0.4)
        f = smoothstep(cs[i].value, 0.0, 0.10) * (0.25 + 0.35 * back)
        if f > 0.0:
            w = {k: x * (1.0 - f) for k, x in w.items()}
            w["Neck"] = w.get("Neck", 0.0) + f
        out.append(garment.limit_dict(w, 4))
    garment.set_weights(ob, out)
