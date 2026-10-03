"""Silena's glove geometry (built for the left side; bake.py mirrors it).

Pieces of the one `Glove<Side>` mesh:
- hand shell: the MPFB skin of the hand cut at the strap, nails smoothed,
  fingertips lengthened a little, pushed out along the normals;
- cuff: a loft around the forearm axis (gauntlet, flared, soft folds), a rolled
  hem at the top, a short lining inside and a disk closing the opening;
- wrist strap with an overlapping tab and a gunmetal snap, covering the joint
  between hand shell and cuff.

Per-vertex data for the leather material (removed after baking):
- attributes `region` (REGION_* codes), finger coordinates `fs` (signed distance
  from the finger's side seam plane, + toward the back), `fu` (distance along the
  finger, continuing over the tip), `fj` (distance from the nearest finger joint),
  `fjk` (that joint: 0 base, 1 middle, 2 last), `fm` (finger mask), `fid` (finger),
  `hd` (rest-pose normal . back of the hand: masks that must not follow the pose);
- cuff attributes `ct` (distance below the cuff's top edge), `ca` (fraction of the
  way around from the seam), `cs` (arc distance from the seam);
- UV maps `CuffUV` (cuff/strap: arc length around from the seam, distance up the
  arm, meters) and `OrnUV` (back of the hand: meters across/along, for the
  filigree panel).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from silena_vesper_common import (
    CUFF_FLARE, CUFF_OFFSET, CUFF_RING_STEP, CUFF_SEGMENTS, CUFF_SLANT, CUFF_START_T, CUFF_TOP_T, FOLD_AMP,
    FOLD_PERIOD, GLOVE_OFFSET, HEM, JUNCTION_T, LINING_DEPTH, PALM_OFFSET, SNAP_R, STRAP_T, STRAP_THICK, STRAP_W,
    TIP_SLACK,
)
from arcology_blender import garment, rig

REGION_SHELL, REGION_CUFF, REGION_HEM, REGION_LINING, REGION_STRAP, REGION_TAB, REGION_SNAP = range(7)
FINGER_ATTRS = ("fs", "fu", "fj", "fjk", "fm", "fid", "hd")
CUFF_ATTRS = ("ct", "ca", "cs")    # cuff: below the top edge (m; negative over the hem), around (0..1), from the seam (m)
UV_HELPERS = ("CuffUV", "OrnUV")


def smoothstep(x, a, b):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def chain(side, finger):
    segs = ("Metacarpal", "Proximal", "Distal") if finger == "Thumb" else ("Proximal", "Intermediate", "Distal")
    return [f"{side}{finger}{s}" for s in segs]


def arm_bones(side):
    return [f"{side}LowerArm", f"{side}Hand"] + [b for f in rig.FINGERS for b in chain(side, f)]


class HandFrame:
    """Directions of one hand in the rest pose (world)."""

    def __init__(self, arm, side):
        mw = arm.matrix_world
        bones = arm.data.bones
        self.side = side
        self.wrist = mw @ bones[f"{side}Hand"].head_local
        elbow = mw @ bones[f"{side}LowerArm"].head_local
        i1 = mw @ bones[f"{side}IndexProximal"].head_local
        l1 = mw @ bones[f"{side}LittleProximal"].head_local
        m1 = mw @ bones[f"{side}MiddleProximal"].head_local
        self.along = (m1 - self.wrist).normalized()
        across = i1 - l1
        self.across = (across - self.along * across.dot(self.along)).normalized()  # toward the index
        palm = -self.across.cross(self.along) if side == "Left" else self.across.cross(self.along)
        self.palm = palm.normalized()
        self.dorsal = -self.palm
        self.palm_length = (m1 - self.wrist).length
        self.limb = garment.limb_frame(self.wrist, elbow - self.wrist, self.dorsal)
        self.theta_ulnar = self.angle(-self.across)
        self.theta_dorsal = 0.0

    def angle(self, direction):
        d = Vector(direction)
        return math.atan2(d.dot(self.limb.lat), d.dot(self.limb.ref))

    def radial(self, theta):
        return (self.limb.ref * math.cos(theta) + self.limb.lat * math.sin(theta)).normalized()


# --- hand shell ---------------------------------------------------------------------------
def _largest_island(bm):
    seen, best = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        if len(island) > len(best):
            best = island
    keep = set(best)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")


def hand_shell(skin, arm, hf, collection):
    """The hand part of the glove from the skin copy (world coordinates)."""
    side = hf.side
    ob = skin.copy()
    ob.data = skin.data.copy()
    ob.name = ob.data.name = f"Glove{side}"
    collection.objects.link(ob)
    rig.extract_by_weight(ob, arm_bones(side), 0.5)
    ob.data.materials.clear()

    bm = bmesh.new()
    bm.from_mesh(ob.data)
    plane = hf.wrist + hf.limb.axis * JUNCTION_T
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                           plane_co=plane, plane_no=hf.limb.axis, clear_outer=True)
    _largest_island(bm)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()

    weights = garment.weights_of(ob)
    nails = [i for i, wd in enumerate(weights) if wd.get("fingernails", 0.0) > 0.01]
    # nail rims and their neighbors smooth out under the leather
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    ring = set(nails)
    for _ in range(2):
        ring |= {e.other_vert(bm.verts[i]).index for i in list(ring) for e in bm.verts[i].link_edges}
    bm.free()
    garment.smooth_verts(ob, sorted(ring), factor=0.5, iterations=8)

    # fingertips: a little slack beyond the finger (gloves are never skin tight there)
    mw = arm.matrix_world
    me = ob.data
    for f in rig.FINGERS:
        distal = arm.data.bones[chain(side, f)[-1]]
        head, tail = mw @ distal.head_local, mw @ distal.tail_local
        d = tail - head
        length = d.length
        d.normalize()
        for i, wd in enumerate(weights):
            if wd.get(distal.name, 0.0) < 0.3:
                continue
            u = (me.vertices[i].co - head).dot(d) / length
            if u > 0.45:
                me.vertices[i].co += d * TIP_SLACK * smoothstep(u, 0.45, 1.05) * wd[distal.name]
    me.update()

    # gentle overall smoothing removes skin detail (veins, tendons) but keeps the knuckles
    bm = bmesh.new()
    bm.from_mesh(me)
    inner = [v.index for v in bm.verts if not v.is_boundary]
    bm.free()
    garment.smooth_verts(ob, inner, factor=0.35, iterations=2, preserve_volume=True)

    palm = hf.palm

    def offset(i, co, n):
        p = max(0.0, n.dot(palm)) * min(1.0, weights[i].get(f"{side}Hand", 0.0) * 1.5)
        return GLOVE_OFFSET + (PALM_OFFSET - GLOVE_OFFSET) * p

    garment.offset_shell(ob, offset)
    for vg in [vg for vg in ob.vertex_groups
               if (not vg.name.startswith(side) or vg.name == side) and vg.name != "fingernails"]:
        ob.vertex_groups.remove(vg)  # MPFB masks and other bones (the nails mark the backs of the fingers)
    return ob


# --- cuff, hem, lining ---------------------------------------------------------------------
def _smooth_ring(values, passes=2):
    v = list(values)
    n = len(v)
    for _ in range(passes):
        v = [(v[(i - 1) % n] + 2.0 * v[i] + v[(i + 1) % n]) * 0.25 for i in range(n)]
    return v


def _ring_uvs(vrings, faces, uv, vfun, closed, cap_uv=(0.0, 0.0)):
    """CuffUV for lofted faces: u = arc length around each ring (the closing
    column wraps to the full length), v = vfun(ring, column)."""
    n = len(vrings[0])
    arcs = []
    for ring in vrings:
        acc = [0.0]
        for k in range(1, n + (1 if closed else 0)):
            acc.append(acc[-1] + (ring[k % n].co - ring[k - 1].co).length)
        arcs.append(acc)
    index = {v: (j, k) for j, ring in enumerate(vrings) for k, v in enumerate(ring)}
    for f in faces:
        if any(v not in index for v in f.verts):
            for loop in f.loops:
                loop[uv].uv = cap_uv
            continue
        ks = [index[v][1] for v in f.verts]
        wrap = closed and max(ks) == n - 1 and min(ks) == 0
        for loop in f.loops:
            j, k = index[loop.vert]
            kk = n if (wrap and k == 0) else k
            loop[uv].uv = (arcs[j][kk], vfun(j, k))


class CuffBuilder:
    """The gauntlet cuff: rings around the forearm sampled from the skin."""

    def __init__(self, hf, skin_bvh):
        self.hf = hf
        self.lf = hf.limb
        self.bvh = skin_bvh
        n = CUFF_SEGMENTS
        self.thetas = [hf.theta_ulnar + 2.0 * math.pi * k / n for k in range(n)]  # column 0 = the seam
        self._cache = {}

    def skin(self, t):
        key = round(t, 5)
        if key not in self._cache:
            self._cache[key] = _smooth_ring(garment.ring_radii(self.bvh, self.lf, t, self.thetas, max_r=0.09), 3)
        return self._cache[key]

    def top(self, th):
        return CUFF_TOP_T - CUFF_SLANT * 0.5 * (1.0 - math.cos(th - self.hf.theta_dorsal))

    def phase(self, th):
        a = th - self.hf.theta_ulnar
        return 1.3 * math.sin(a + 0.6) + 0.55 * math.sin(2.0 * a + 1.1)

    def radius(self, t, k):
        """Outer cuff radius at t for column k."""
        rs = self.skin(t)
        mean = sum(rs) / len(rs)
        th = self.thetas[k]
        s = smoothstep(t, STRAP_T + STRAP_W * 0.5 - 0.004, self.top(th))
        fold_in = smoothstep(t, STRAP_T + STRAP_W * 0.5 + 0.004, STRAP_T + STRAP_W * 0.5 + 0.014)
        fold = FOLD_AMP * fold_in * (1.0 - 0.35 * s) * math.sin(
            2.0 * math.pi * (t - CUFF_START_T) / FOLD_PERIOD + self.phase(th))
        return rs[k] + (mean - rs[k]) * 0.35 * s + CUFF_OFFSET + CUFF_FLARE * s ** 1.6 + fold

    def build(self, bm, layers):
        lf, n = self.lf, CUFF_SEGMENTS
        steps = max(4, int(round((CUFF_TOP_T - CUFF_START_T) / CUFF_RING_STEP)))
        rings, vs = [], []
        for j in range(steps + 1):
            ring, v_ring = [], []
            for k, th in enumerate(self.thetas):
                t = CUFF_START_T + (self.top(th) - CUFF_START_T) * j / steps
                ring.append(lf.point(t, th, self.radius(t, k)))
                v_ring.append(t)
            rings.append(ring)
            vs.append(v_ring)
        regions = [REGION_CUFF] * len(rings)

        # rolled hem: over the edge and down the inside
        top = rings[-1]
        tops = [self.top(th) for th in self.thetas]
        hem_profile = [(0.00045, 0.00012), (0.00072, 0.00055), (0.00078, 0.0010), (0.00050, 0.00142),
                       (0.0, HEM)]
        for da, dr in hem_profile:
            rings.append([top[k] + lf.axis * da - self.hf.radial(th) * dr for k, th in enumerate(self.thetas)])
            regions.append(REGION_HEM)
        # lining down the inside, then a disk closing the opening
        lining_t = [tt - LINING_DEPTH for tt in tops]
        rings.append([lf.point(lining_t[k], th, self.radius(lining_t[k], k) - HEM - 0.0006)
                      for k, th in enumerate(self.thetas)])
        regions.append(REGION_LINING)
        rs = self.skin(min(lining_t) - 0.003)
        rings.append([lf.point(lining_t[k] - 0.003, th, rs[k] * 0.55) for k, th in enumerate(self.thetas)])
        regions.append(REGION_LINING)
        vrings, centers, faces = garment.loft(bm, rings, closed=True, cap_end=True)
        fset = set(faces)
        probe = [f for f in vrings[1][0].link_faces if f in fset][0]
        garment.orient(bm, faces, probe, self.hf.radial(self.thetas[0]))

        # path length up the cuff (v) per column, continuing over the hem and the lining
        vcoord = []
        for k in range(n):
            acc = [vs[0][k]]
            for j in range(1, len(vrings)):
                acc.append(vs[j][k] if j < len(vs) else acc[-1] + (vrings[j][k].co - vrings[j - 1][k].co).length)
            vcoord.append(acc)
        uv, reg = layers["CuffUV"], layers["region"]
        for j, ring in enumerate(vrings):
            for v in ring:
                v[reg] = float(regions[j])
        for c in centers:
            c[reg] = float(REGION_LINING)
        _ring_uvs(vrings, faces, uv, lambda j, k: vcoord[k][j], closed=True, cap_uv=(0.0, vcoord[0][-1] + 0.01))
        # cuff coordinates for the material: below the edge, around (fraction), from the seam
        ct, ca, cs = layers["ct"], layers["ca"], layers["cs"]
        for j, ring in enumerate(vrings):
            full = sum((ring[(k + 1) % n].co - ring[k].co).length for k in range(n))
            arc = 0.0
            for k, v in enumerate(ring):
                v[ct] = (tops[k] - vs[j][k]) if j < len(vs) else -(vcoord[k][j] - vcoord[k][len(vs) - 1])
                v[ca] = k / n
                v[cs] = min(arc, full - arc)
                arc += (ring[(k + 1) % n].co - v.co).length
        return vrings


# --- strap, tab, snap -------------------------------------------------------------------------
def build_strap(bm, layers, cb, hf):
    """Wrist strap (closed ring) + overlapping tab + snap. Returns the snap center and normal."""
    lf, n = hf.limb, CUFF_SEGMENTS
    thetas = cb.thetas
    uv, reg = layers["CuffUV"], layers["region"]
    t0, t1 = STRAP_T - STRAP_W * 0.5, STRAP_T + STRAP_W * 0.5
    samples = [t0 + (t1 - t0) * i / 6 for i in range(7)]
    # base: the highest glove surface under the strap (hand shell or cuff start)
    base = [max(max(cb.skin(t)[k] for t in samples) + max(GLOVE_OFFSET, CUFF_OFFSET) + 0.0002,
                cb.radius(CUFF_START_T, k) + 0.0002) for k in range(n)]
    base = _smooth_ring(base, 3)

    w, th = STRAP_W, STRAP_THICK
    profile = [(-w / 2 + 0.0004, -0.0009), (-w / 2, 0.0002), (-w / 2 + 0.0003, th * 0.72),
               (-w / 2 + 0.0010, th), (0.0, th * 1.03), (w / 2 - 0.0010, th), (w / 2 - 0.0003, th * 0.72),
               (w / 2, 0.0002), (w / 2 - 0.0004, -0.0009)]
    rings = [[lf.point(STRAP_T + dt, thetas[k], base[k] + dr) for k in range(n)] for dt, dr in profile]
    vrings, _, faces = garment.loft(bm, rings, closed=True)
    fset = set(faces)
    probe = [f for f in vrings[4][0].link_faces if f in fset][0]
    garment.orient(bm, faces, probe, hf.radial(thetas[0]))
    across = [0.0]
    for a, b in zip(profile, profile[1:]):
        across.append(across[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    for ring in vrings:
        for v in ring:
            v[reg] = float(REGION_STRAP)
    _ring_uvs(vrings, faces, uv, lambda j, k: across[j] - across[-1] * 0.5, closed=True)

    # tab: the strap's end lying over it, toward the back of the wrist
    th_end = hf.theta_ulnar + math.radians(55.0)
    th_start = th_end - math.radians(80.0)
    m = 18
    tab_t = [th_start + (th_end - th_start) * i / m for i in range(m + 1)]
    wt = w - 0.0016

    def base_at(tt):
        k = (tt - thetas[0]) / (2 * math.pi) * n
        k0 = int(math.floor(k)) % n
        fk = k - math.floor(k)
        return base[k0] * (1 - fk) + base[(k0 + 1) % n] * fk

    ptab = [(-0.5, -0.0004), (-0.5, 0.0003), (-0.47, 0.0011), (-0.40, 0.00145), (0.0, 0.0015),
            (0.40, 0.00145), (0.47, 0.0011), (0.5, 0.0003), (0.5, -0.0004)]
    cols = [[] for _ in ptab]
    for i, tt in enumerate(tab_t):
        b = base_at(tt) + th * 1.03
        s_end = (tt - (th_end - math.radians(12.0))) / math.radians(12.0)
        width = wt * (math.sqrt(1.0 - min(s_end, 0.94) ** 2) if s_end > 0 else 1.0)
        rise = smoothstep(i / m, 0.0, 0.18)  # emerges from the strap at the start
        for j, (a, dr) in enumerate(ptab):
            cols[j].append(lf.point(STRAP_T + a * width, tt, b - 0.0012 * (1 - rise) + dr * (0.25 + 0.75 * rise)))
    tv, _, tfaces = garment.loft(bm, cols, closed=False)
    tfaces.append(bm.faces.new([tv[j][-1] for j in range(len(ptab))]))  # the rounded free end
    tset = set(tfaces)
    probe = [f for f in tv[4][m // 2].link_faces if f in tset][0]
    garment.orient(bm, tfaces, probe, hf.radial(tab_t[m // 2]))
    for col in tv:
        for v in col:
            v[reg] = float(REGION_TAB)
    tab_across = [a * wt for a, _ in ptab]
    _ring_uvs(tv, tfaces, uv, lambda j, k: tab_across[j], closed=False)

    # snap on the tab
    th_snap = th_start + (th_end - th_start) * 0.52
    nrm = hf.radial(th_snap)
    center = lf.point(STRAP_T, th_snap, base_at(th_snap) + th * 1.03 + 0.0013)
    _snap(bm, layers, center, nrm, lf.axis)
    return center, nrm


def _snap(bm, layers, center, normal, up):
    """Low domed snap cap: a lathe around `normal`."""
    reg, uv = layers["region"], layers["CuffUV"]
    x = (up - normal * up.dot(normal)).normalized()
    y = normal.cross(x)
    r = SNAP_R
    profile = [(r * 0.96, -0.0004), (r, 0.0002), (r * 0.97, 0.00065), (r * 0.86, 0.0011), (r * 0.62, 0.00145),
               (r * 0.30, 0.0016)]
    segs = 20
    rings = [[center + (x * math.cos(2 * math.pi * i / segs) + y * math.sin(2 * math.pi * i / segs)) * pr
              + normal * pz for i in range(segs)] for pr, pz in profile]
    vrings, centers, faces = garment.loft(bm, rings, closed=True, cap_end=True)
    cap = [f for f in faces if centers[0] in f.verts][0]
    garment.orient(bm, faces, cap, normal)
    for v in [v for ring in vrings for v in ring] + centers:
        v[reg] = float(REGION_SNAP)
    for f in faces:
        for loop in f.loops:
            d = loop.vert.co - center
            loop[uv].uv = (d.dot(x), d.dot(y))


# --- assembly ---------------------------------------------------------------------------------
def build_glove(skin, arm, side, collection):
    hf = HandFrame(arm, side)
    ob = hand_shell(skin, arm, hf, collection)
    me = ob.data
    for name in UV_HELPERS:
        me.uv_layers.new(name=name)
    for name in ("region",) + CUFF_ATTRS:
        me.attributes.new(name, "FLOAT", "POINT")

    # forearm skin BVH (lower arm and hand only, so rays can't reach the body)
    ref = skin.copy()
    ref.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(ref)
    rig.extract_by_weight(ref, [f"{side}LowerArm", f"{side}Hand"], 0.5)
    cb = CuffBuilder(hf, garment.bvh_of(ref))

    bm = bmesh.new()
    bm.from_mesh(me)
    layers = {"CuffUV": bm.loops.layers.uv["CuffUV"], "OrnUV": bm.loops.layers.uv["OrnUV"]}
    for name in ("region",) + CUFF_ATTRS:
        layers[name] = bm.verts.layers.float[name]
    for v in bm.verts:
        v[layers["region"]] = float(REGION_SHELL)
        v[layers["ct"]] = -1.0
        v[layers["cs"]] = 1.0
    shell_faces = list(bm.faces)
    cb.build(bm, layers)
    snap_center, snap_normal = build_strap(bm, layers, cb, hf)
    # back-of-hand projection for the filigree panel
    o = hf.wrist + hf.along * hf.palm_length * 0.48
    for f in shell_faces:
        for loop in f.loops:
            d = loop.vert.co - o
            loop[layers["OrnUV"]].uv = (d.dot(hf.across), d.dot(hf.along))
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    rd = ref.data
    bpy.data.objects.remove(ref)
    bpy.data.meshes.remove(rd)
    finger_coords(ob, arm, hf)
    ob["snap_center"] = tuple(snap_center)
    ob["snap_normal"] = tuple(snap_normal)
    ob["orn_origin"] = tuple(o)
    for p in me.polygons:
        p.use_smooth = True
    return ob, hf


# --- finger coordinates for the material ---------------------------------------------------------
def finger_coords(ob, arm, hf):
    side = hf.side
    me = ob.data
    mw = arm.matrix_world
    weights = garment.weights_of(ob)
    n = len(me.vertices)
    co = np.array([v.co[:] for v in me.vertices])
    region = np.zeros(n, dtype=np.float32)
    me.attributes["region"].data.foreach_get("value", region)
    attrs = {k: np.zeros(n) for k in FINGER_ATTRS}
    owner = np.zeros(n)
    for fi, finger in enumerate(rig.FINGERS):
        names = chain(side, finger)
        bones = [arm.data.bones[b] for b in names]
        pts = [mw @ b.head_local for b in bones] + [mw @ bones[-1].tail_local]
        segs = [(np.array(pts[i][:]), np.array(pts[i + 1][:])) for i in range(3)]
        lens = [float(np.linalg.norm(b - a)) for a, b in segs]
        starts = [0.0, lens[0], lens[0] + lens[1]]
        if finger == "Thumb":
            dors = _thumb_dorsal(co, weights, names, pts, hf)
        else:
            dors = [-(mw.to_3x3() @ b.matrix_local.to_3x3()).col[2].normalized() for b in bones]
        member = np.array([sum(wd.get(b, 0.0) for b in names) for wd in weights])
        # nearest point on the bone chain
        best = np.full(n, np.inf)
        u = np.zeros(n)
        segi = np.zeros(n, dtype=int)
        cpt = np.zeros((n, 3))
        for si, (a, b) in enumerate(segs):
            d = b - a
            L = lens[si]
            s = np.clip(((co - a) @ d) / (L * L), 0.0, 1.0)
            c = a + s[:, None] * d
            dist = np.linalg.norm(co - c, axis=1)
            better = dist < best
            best[better] = dist[better]
            u[better] = starts[si] + s[better] * L
            segi[better] = si
            cpt[better] = c[better]
        # dorsal direction blended by the vertex's weights inside the chain
        dmat = np.array([d[:] for d in dors])
        wmat = np.array([[wd.get(b, 0.0) for b in names] for wd in weights])
        wsum = wmat.sum(axis=1)
        dvec = np.where(wsum[:, None] > 1e-4, wmat @ dmat, dmat[segi])
        dvec /= np.linalg.norm(dvec, axis=1)[:, None]
        h = np.einsum("ij,ij->i", co - cpt, dvec)
        own = (member > 0.3) & (region == REGION_SHELL)
        # center of each segment's cross-section (bones don't run through the middle)
        h0s = []
        for si in range(3):
            sel = own & (segi == si)
            h0s.append(0.5 * (h[sel].max() + h[sel].min()) if sel.sum() > 8 else 0.0)
        mids = [starts[i] + lens[i] * 0.5 for i in range(3)]
        fs = h - np.interp(u, mids, h0s)
        # distance along, continuing over the tip
        tip = segs[2][1]
        tdir = (segs[2][1] - segs[2][0]) / lens[2]
        e = (co - tip) @ tdir
        lat_dir = np.cross(tdir, dmat[2])
        w = np.abs((co - tip) @ lat_dir)
        fu = u.copy()
        beyond = e > 0
        fu[beyond] = starts[2] + lens[2] + np.arctan2(e[beyond], w[beyond]) * np.hypot(e[beyond], w[beyond])
        joints = np.array(starts)
        dj = u[:, None] - joints[None, :]
        jk = np.argmin(np.abs(dj), axis=1)
        fj = dj[np.arange(n), jk]
        mask = np.clip(member, 0.0, 1.0)
        if finger == "Thumb":  # the thumb's seams start where it leaves the palm
            mask = mask * np.clip((u - (starts[1] - 0.012)) / 0.008, 0.0, 1.0)
        sel = own & (member > owner)
        owner[sel] = member[sel]
        attrs["fs"][sel] = fs[sel]
        attrs["fu"][sel] = fu[sel]
        attrs["fj"][sel] = fj[sel]
        attrs["fjk"][sel] = jk[sel]
        attrs["fid"][sel] = fi
        attrs["fm"][sel] = mask[sel]
    # back-of-hand facing in the rest pose (the material's masks must not follow the pose)
    nrm = np.empty(n * 3, dtype=np.float32)
    me.vertex_normals.foreach_get("vector", nrm)
    attrs["hd"] = nrm.reshape(-1, 3) @ np.array(hf.dorsal[:], dtype=np.float32)
    for name, values in attrs.items():
        a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", values.astype(np.float32))


def _thumb_dorsal(co, weights, names, pts, hf):
    """The back of the thumb from its nail (the thumb bones' rolls don't follow it)."""
    nails = np.array([wd.get("fingernails", 0.0) > 0.01 and wd.get(names[-1], 0.0) > 0.3 for wd in weights])
    a, b = np.array(pts[2][:]), np.array(pts[3][:])
    L = np.linalg.norm(b - a)
    if nails.sum() > 3:
        c = co[nails].mean(axis=0)
        s = np.clip((c - a) @ (b - a) / (L * L), 0.0, 1.0)
        nd = c - (a + s * (b - a))
    else:
        nd = np.array(hf.dorsal[:])
    out = []
    for i in range(3):
        sd = np.array((pts[i + 1] - pts[i]).normalized()[:])
        v = nd - sd * (nd @ sd)
        out.append(Vector(v / np.linalg.norm(v)))
    return out
