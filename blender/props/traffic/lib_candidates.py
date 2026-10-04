"""Generic helpers written for the flying traffic that blender/lib lacks.
Asset-agnostic; candidates for promotion into arcology_blender (blender/lib was
not changed during this task).

- PartMesh: one mesh assembled from many pieces, each face on a named material
  slot, with an optional per-vertex float attribute (glow cores).
- Lofted hulls: monotone cubic (PCHIP) interpolation of keyed cross-section parameters
  (`interpolate_keys`) and `loft_rings` (quads between rings, n-gon caps,
  a material per (station, profile segment)).
- `lathe_part` (any axis, material per profile segment), `box_part`.
- `conform_patch`: a lamp lens or badge projected onto a curved surface along
  a direction, with a rim skirt sunk into the surface (its own UV island).
- LocalGraph: a `shading.Graph` whose position is object-local (+ an offset),
  so objects can move apart (`bake.Spread`) without changing their masks.
- Planar image decals on a Graph (`decal`), sampled from numpy canvases.
- Text for decals: the stroke font, pseudo-CJK glyphs and segment distance
  copied from blender/architecture/city/brutalist/lib_candidates.py (merge
  them when either is promoted), plus `stroke_mask` (antialiased strokes).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from arcology_blender.scene import set_colorspace
from arcology_blender.shading import Graph


# ---------------------------------------------------------------------------------------
# PartMesh
# ---------------------------------------------------------------------------------------
class PartMesh:
    """A bmesh with named material slots and an optional float point attribute.

    pm.vert(co, attr=0.0) -> BMVert; pm.face(verts, slot) -> BMFace; slots are
    created on first use (order kept). `to_object(name, coll, materials)` maps
    slot names to Material datablocks and writes the attribute `attr_name`.
    """

    def __init__(self, attr_name=None):
        self.bm = bmesh.new()
        self.slots = []
        self.faces = []
        self._mark = 0
        self.attr_name = attr_name
        self.layer = self.bm.verts.layers.float.new(attr_name) if attr_name else None

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def vert(self, co, attr=0.0):
        v = self.bm.verts.new(Vector(co))
        if self.layer is not None:
            v[self.layer] = attr
        return v

    def face(self, verts, slot):
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(slot)
        self.faces.append(f)
        return f

    def end_piece(self):
        """Orient the faces added since the last call outward: flip them all if
        most of their area faces toward the piece's centroid (closed or nearly
        closed shapes: hulls, boxes, pods, lens patches with a sunk skirt)."""
        faces = self.faces[self._mark:]
        self._mark = len(self.faces)
        if not faces:
            return
        verts = {v for f in faces for v in f.verts}
        c = sum((v.co for v in verts), Vector()) / len(verts)
        score = 0.0
        for f in faces:
            f.normal_update()
            score += f.normal.dot(f.calc_center_median() - c) * f.calc_area()
        if score < 0.0:
            for f in faces:
                f.normal_flip()

    def to_object(self, name, coll, materials):
        """Build the object (call end_piece after each piece first)."""
        self.end_piece()
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for s in self.slots:
            me.materials.append(materials[s])
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


# ---------------------------------------------------------------------------------------
# Lofts
# ---------------------------------------------------------------------------------------
def _pchip_slopes(xs, ys):
    """Fritsch-Carlson monotone slopes: no overshoot, flats stay flat."""
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0.0:
            m[i] = 0.0
        else:
            h0, h1 = xs[i] - xs[i - 1], xs[i + 1] - xs[i]
            w1, w2 = 2 * h1 + h0, h1 + 2 * h0
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def interpolate_keys(keys, steps, along="y"):
    """Dense stations from key stations (dicts of floats with the same keys).
    `along` (strictly increasing over the keys) is spaced evenly within each
    key interval, `steps` stations per interval (an int or one per interval);
    every other value follows a monotone cubic (PCHIP) of `along`, so uneven
    key spacing never overshoots and constant runs stay straight. Every key
    appears exactly; each station gets `key` = its interval index + fraction,
    so materials can follow key ranges."""
    n = len(keys)
    if isinstance(steps, int):
        steps = [steps] * (n - 1)
    xs = [k[along] for k in keys]
    names = [k for k in keys[0].keys() if k != along]
    slopes = {k: _pchip_slopes(xs, [key[k] for key in keys]) for k in names}
    out = []
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        for s in range(steps[i]):
            t = s / steps[i]
            h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
            h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            d = {along: xs[i] + t * h}
            for k in names:
                d[k] = (h00 * keys[i][k] + h10 * h * slopes[k][i] + h01 * keys[i + 1][k]
                        + h11 * h * slopes[k][i + 1])
            d["key"] = i + t
            out.append(d)
    last = dict(keys[-1])
    last["key"] = float(n - 1)
    out.append(last)
    return out


def loft_rings(pm, rings, face_slot, cap_start=None, cap_end=None, attrs=None):
    """Quads between consecutive closed rings (equal point counts) in a PartMesh.

    face_slot(i, j) -> slot name for the quad between ring i and i+1 and ring
    points j and j+1. cap_start / cap_end: slot names for planar n-gon caps
    (None = open). attrs: optional per-ring list of point attribute values.
    Returns the vertex rings."""
    vr = []
    for i, ring in enumerate(rings):
        a = attrs[i] if attrs else None
        vr.append([pm.vert(p, a[j] if a else 0.0) for j, p in enumerate(ring)])
    n = len(rings[0])
    for i in range(len(vr) - 1):
        for j in range(n):
            k = (j + 1) % n
            pm.face((vr[i][j], vr[i][k], vr[i + 1][k], vr[i + 1][j]), face_slot(i, j))
    if cap_start:
        pm.face(list(reversed(vr[0])), cap_start)
    if cap_end:
        pm.face(list(vr[-1]), cap_end)
    return vr


def lathe_part(pm, profile, segments, matrix, slots, attrs=None, start_angle=0.0):
    """Surface of revolution about local Z, placed by `matrix` (4x4), in a PartMesh.

    profile: [(r, z), ...]; r == 0 makes a pole (fan). slots: one slot name per
    profile segment (len(profile) - 1). attrs: optional value per profile point.
    An open end stays open (embed it in another surface)."""
    rings = []
    for i, (r, z) in enumerate(profile):
        a = attrs[i] if attrs else 0.0
        if r < 1e-7:
            rings.append([pm.vert(matrix @ Vector((0.0, 0.0, z)), a)])
        else:
            ring = []
            for s in range(segments):
                ang = start_angle + 2.0 * math.pi * s / segments
                ring.append(pm.vert(matrix @ Vector((r * math.cos(ang), r * math.sin(ang), z)), a))
            rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for s in range(segments):
            t = (s + 1) % segments
            if len(a) == 1:
                pm.face((a[0], b[s], b[t]), slots[i])
            elif len(b) == 1:
                pm.face((a[s], a[t], b[0]), slots[i])
            else:
                pm.face((a[s], a[t], b[t], b[s]), slots[i])
    return rings


def box_part(pm, lo, hi, slot_fn, matrix=None, attr=0.0):
    """Axis-aligned box lo..hi (optionally transformed by `matrix`) in a PartMesh;
    slot_fn(normal: Vector) -> slot name per face (e.g. emissive ends only)."""
    lo, hi = Vector(lo), Vector(hi)
    m = matrix or Matrix.Identity(4)
    c = [Vector((x, y, z)) for z in (lo.z, hi.z) for y in (lo.y, hi.y) for x in (lo.x, hi.x)]
    v = [pm.vert(m @ p, attr) for p in c]
    quads = [((0, 2, 3, 1), (0, 0, -1)), ((4, 5, 7, 6), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
             ((2, 6, 7, 3), (0, 1, 0)), ((0, 4, 6, 2), (-1, 0, 0)), ((1, 3, 7, 5), (1, 0, 0))]
    rot = m.to_3x3()
    for idx, n in quads:
        pm.face([v[i] for i in idx], slot_fn((rot @ Vector(n)).normalized()))
    return v


def bvh_of_partmesh(pm):
    pm.bm.normal_update()
    return BVHTree.FromBMesh(pm.bm)


def conform_patch(pm, bvh, center, u_axis, v_axis, size, direction, slot, rim_slot,
                  nu=3, nv=2, lift=0.012, depth=0.03, attr=0.0, round_corners=0.0, reach=30.0):
    """A lens or badge: an nu x nv grid of size (w, h) around `center`, spanned
    by u_axis / v_axis, projected along `direction` onto `bvh` (rays start
    `reach` m back from the center plane), lifted `lift` back toward the ray origin, with a skirt sunk `depth`
    into the surface (rim_slot) so no gap shows from the side.
    round_corners (0..0.5) pulls the four corner points inward (softer shape).
    Returns (patch vertices, hit centroid) or (None, None) if any ray misses."""
    c, u, v, d = Vector(center), Vector(u_axis).normalized(), Vector(v_axis).normalized(), Vector(direction).normalized()
    w, h = size
    grid = []
    hits = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            fu, fv = i / nu - 0.5, j / nv - 0.5
            if round_corners and i in (0, nu) and j in (0, nv):
                fu *= 1.0 - round_corners
                fv *= 1.0 - round_corners * 0.6
            p = c + u * (fu * w) + v * (fv * h)
            hit = bvh.ray_cast(p - d * reach, d, 2.0 * reach)
            if hit[0] is None:
                return None, None
            row.append(hit[0])
            hits.append(hit[0])
        grid.append(row)
    top = [[pm.vert(p - d * lift, attr) for p in row] for row in grid]
    for j in range(nv):
        for i in range(nu):
            pm.face((top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]), slot)
    ring = ([top[0][i] for i in range(nu + 1)] + [top[j][nu] for j in range(1, nv + 1)]
            + [top[nv][i] for i in range(nu - 1, -1, -1)] + [top[j][0] for j in range(nv - 1, 0, -1)])
    low = [pm.vert(t.co + d * (lift + depth), attr) for t in ring]
    for k in range(len(ring)):
        m = (k + 1) % len(ring)
        pm.face((ring[k], low[k], low[m], ring[m]), rim_slot)
    centroid = sum(hits, Vector()) / len(hits)
    return [p for row in top for p in row], centroid


# ---------------------------------------------------------------------------------------
# LocalGraph and decals
# ---------------------------------------------------------------------------------------
class _GeoProxy:
    """Stands in for a Geometry node: Position replaced, other outputs passed through."""

    def __init__(self, geo, position):
        self.outputs = {o.name: o for o in geo.outputs}
        self.outputs["Position"] = position


class LocalGraph(Graph):
    """Graph whose x/y/z (and every noise/vec/offset) use the object-local
    position plus `offset` (the authoring frame), so the object can be moved
    (bake.Spread), turned or recentered without changing its masks. nx/ny/nz
    are object-space normals; geo.outputs["Normal"] stays world-space (the
    Bevel-based edge masks compare against it)."""

    def __init__(self, mat, offset=(0.0, 0.0, 0.0)):
        super().__init__(mat)
        tc = self.nodes.new("ShaderNodeTexCoord")
        add = self.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        self.links.new(tc.outputs["Object"], add.inputs[0])
        add.inputs[1].default_value = tuple(offset)
        self.links.new(add.outputs[0], self.pos.inputs[0])
        self.links.new(tc.outputs["Normal"], self.nrm.inputs[0])  # nx/ny/nz object-space too
        self.geo = _GeoProxy(self.geo, add.outputs[0])
        self.local = add.outputs[0]

    def sign(self, v):
        """-1 / 0 / +1 (e.g. which side a face is on)."""
        return self.math("SIGN", v)


def image_from_canvas(name, rgba, colorspace="sRGB"):
    """Packed image from an (h, w, 4) float canvas (row 0 = bottom)."""
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    set_colorspace(img, colorspace)
    img.pixels.foreach_set(np.ascontiguousarray(rgba, dtype=np.float32).ravel())
    img.pack()
    return img


def decal(g, image, u, v, interpolation="Cubic"):
    """Sample `image` at (u, v) sockets (0..1 over the image, CLIP outside).
    Returns (color, alpha) sockets; alpha is 0 outside the decal."""
    tex = g.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.extension = "CLIP"
    tex.interpolation = interpolation
    g.links.new(g.combine(u, v, 0.0), tex.inputs["Vector"])
    return tex.outputs["Color"], tex.outputs["Alpha"]


def side_uv(g, y_center, z_bottom, width, height):
    """(u, v) for a decal on both X sides (left-to-right as seen from outside on
    either side; nose at +Y): u runs along +Y on the +X side, -Y on the -X side."""
    s = g.sign(g.nx)
    u = g.add(g.mul(g.mul(g.sub(g.y, y_center), s), 1.0 / width), 0.5)
    v = g.mul(g.sub(g.z, z_bottom), 1.0 / height)
    return u, v


def end_uv(g, x_center, z_bottom, width, height):
    """(u, v) for a decal on both Y ends (front +Y and back -Y), read from outside."""
    s = g.sign(g.ny)
    u = g.add(g.mul(g.mul(g.sub(g.x, x_center), g.mul(s, -1.0)), 1.0 / width), 0.5)
    v = g.mul(g.sub(g.z, z_bottom), 1.0 / height)
    return u, v


def set_emission(g, color, strength=1.0):
    """Wire an Emission Color socket/constant (bake.bake_part(emission=...) bakes it)."""
    g._set(g.bsdf.inputs["Emission Color"], color)
    g.bsdf.inputs["Emission Strength"].default_value = strength


# ---------------------------------------------------------------------------------------
# Text for decals (copied from city/brutalist/lib_candidates.py; keep in sync)
# ---------------------------------------------------------------------------------------
STROKE_FONT = {
    "A": [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 3), (4, 3)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "C": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1)]],
    "D": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 1), (3, 0), (0, 0)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "F": [[(4, 6), (0, 6), (0, 0)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(1, 6), (3, 6)], [(2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "J": [[(4, 6), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2)], [(1, 3), (4, 0)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "Q": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)], [(2, 2), (4, 0)]],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
    "X": [[(0, 6), (4, 0)], [(4, 6), (0, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    "Z": [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    "0": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)], [(1, 3), (3, 3)]],
    "4": [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    "5": [[(4, 6), (0, 6), (0, 3), (3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "6": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)]],
    "7": [[(0, 6), (4, 6), (1, 0)]],
    "8": [[(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0), (3, 0),
           (4, 1), (4, 2), (3, 3)]],
    "9": [[(4, 3), (1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "-": [[(1, 3), (3, 3)]],
    "+": [[(2, 1), (2, 5)], [(0, 3), (4, 3)]],
    " ": [],
}


def text_strokes(text, x0, y0, height, gap=0.35):
    """Segments of `text` in the stroke font, glyphs `height` tall, left-bottom
    at (x0, y0). Returns (segments, width)."""
    s = height / 6.0
    adv = (4 + 6 * gap) * s
    segs = []
    for i, ch in enumerate(text.upper()):
        ox = x0 + i * adv
        for line in STROKE_FONT.get(ch, []):
            for a, b in zip(line[:-1], line[1:]):
                segs.append(((ox + a[0] * s, y0 + a[1] * s), (ox + b[0] * s, y0 + b[1] * s)))
    return segs, len(text) * adv - 6 * gap * s


def text_width(text, height, gap=0.35):
    s = height / 6.0
    return len(text) * (4 + 6 * gap) * s - 6 * gap * s


def pseudo_glyph(rng, x0, y0, size):
    """Segments of an invented CJK-like character in a size x size box at (x0, y0)."""
    segs = []

    def part(bx0, by0, bx1, by1):
        w, h = bx1 - bx0, by1 - by0
        kind = rng.choice(["bars", "box", "cross", "legs", "comb"], p=[0.3, 0.2, 0.2, 0.15, 0.15])
        if kind == "bars":
            n = rng.integers(2, 4)
            for k in range(n):
                y = by0 + h * (k + 0.5) / n
                inset = w * (0.1 if k in (0, n - 1) else rng.uniform(0.05, 0.2))
                segs.append(((bx0 + inset, y), (bx1 - inset, y)))
            if rng.random() < 0.7:
                x = bx0 + w * rng.uniform(0.35, 0.65)
                segs.append(((x, by0), (x, by1)))
        elif kind == "box":
            ix, iy = w * 0.12, h * 0.12
            pts = [(bx0 + ix, by0 + iy), (bx1 - ix, by0 + iy), (bx1 - ix, by1 - iy), (bx0 + ix, by1 - iy)]
            for k in range(4):
                segs.append((pts[k], pts[(k + 1) % 4]))
            if rng.random() < 0.6:
                segs.append(((bx0 + ix, (by0 + by1) / 2), (bx1 - ix, (by0 + by1) / 2)))
        elif kind == "cross":
            segs.append(((bx0 + w * 0.08, by0 + h * 0.6), (bx1 - w * 0.08, by0 + h * 0.6)))
            segs.append(((bx0 + w * 0.5, by1 - h * 0.05), (bx0 + w * 0.5, by0 + h * 0.05)))
            if rng.random() < 0.5:
                segs.append(((bx0 + w * 0.2, by0 + h * 0.25), (bx1 - w * 0.2, by0 + h * 0.25)))
        elif kind == "legs":
            top = (bx0 + w * 0.5, by1 - h * 0.08)
            segs.append((top, (bx0 + w * 0.1, by0 + h * 0.08)))
            segs.append(((bx0 + w * 0.45, by0 + h * 0.55), (bx1 - w * 0.08, by0 + h * 0.08)))
            if rng.random() < 0.6:
                segs.append(((bx0 + w * 0.15, by0 + h * 0.72), (bx1 - w * 0.15, by0 + h * 0.72)))
        else:
            segs.append(((bx0 + w * 0.08, by1 - h * 0.12), (bx1 - w * 0.08, by1 - h * 0.12)))
            n = rng.integers(2, 4)
            for k in range(n):
                x = bx0 + w * (0.2 + 0.6 * k / max(n - 1, 1))
                segs.append(((x, by1 - h * 0.12), (x, by0 + h * 0.1)))

    layout = rng.choice(["lr", "tb", "enc", "single"], p=[0.4, 0.3, 0.15, 0.15])
    x1, y1 = x0 + size, y0 + size
    if layout == "lr":
        split = x0 + size * rng.uniform(0.35, 0.45)
        part(x0, y0, split, y1)
        part(split + size * 0.05, y0, x1, y1)
    elif layout == "tb":
        split = y0 + size * rng.uniform(0.4, 0.55)
        part(x0, split + size * 0.04, x1, y1)
        part(x0, y0, x1, split)
    elif layout == "enc":
        m = size * 0.06
        segs.append(((x0 + m, y0 + m), (x0 + m, y1 - m)))
        segs.append(((x0 + m, y1 - m), (x1 - m, y1 - m)))
        segs.append(((x1 - m, y1 - m), (x1 - m, y0 + m)))
        part(x0 + size * 0.22, y0 + size * 0.12, x1 - size * 0.22, y1 - size * 0.25)
    else:
        part(x0, y0, x1, y1)
    return segs


def segment_distance(shape, segs, pad):
    """Distance (pixels) from every pixel center of an (h, w) grid (row 0 =
    bottom) to the nearest segment, within `pad` of each segment (inf elsewhere)."""
    h, w = shape
    out = np.full((h, w), np.inf)
    for (ax, ay), (bx, by) in segs:
        c0, c1 = int(max(0, math.floor(min(ax, bx) - pad))), int(min(w, math.ceil(max(ax, bx) + pad) + 1))
        r0, r1 = int(max(0, math.floor(min(ay, by) - pad))), int(min(h, math.ceil(max(ay, by) + pad) + 1))
        if c1 <= c0 or r1 <= r0:
            continue
        yy, xx = np.mgrid[r0:r1, c0:c1].astype(np.float64)
        xx += 0.5
        yy += 0.5
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / ll, 0.0, 1.0) if ll > 1e-12 else 0.0
        d = np.hypot(xx - (ax + t * dx), yy - (ay + t * dy))
        out[r0:r1, c0:c1] = np.minimum(out[r0:r1, c0:c1], d)
    return out


def stroke_mask(shape, segs, radius):
    """Antialiased 0..1 mask of strokes `radius` px wide (half width) on an (h, w) grid."""
    d = segment_distance(shape, segs, radius + 2.0)
    return np.clip(radius + 0.5 - d, 0.0, 1.0)


def rect_mask(shape, x0, y0, x1, y1, radius=0.0):
    """Antialiased 0..1 mask of a (rounded) rectangle in pixels (row 0 = bottom)."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64) + 0.5
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - radius, (y1 - y0) / 2 - radius
    qx, qy = np.abs(xx - cx) - hx, np.abs(yy - cy) - hy
    d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - radius
    return np.clip(0.5 - d, 0.0, 1.0)


def compose(mask, color, under):
    """Lay `color` (3-tuple or (h, w, 3)) over `under` (h, w, 3) by a 0..1 mask."""
    m = mask[..., None]
    return under * (1.0 - m) + np.asarray(color, dtype=np.float64) * m
