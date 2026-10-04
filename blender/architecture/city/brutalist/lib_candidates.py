"""Generic helpers written for the brutalist city towers that blender/lib lacks.
Asset-agnostic; candidates for promotion into arcology_blender (not changed
during this task, see CLAUDE.md "A/B an asset" / parallel artists).

- AtlasMesh: faces on several materials at once, each with explicit UVs or
  real-world UVs in a trim-sheet band (like trim.TrimMesh.poly, but one mesh
  can mix sheets, a 2D tile and atlas rectangles). Box, strip and sweep
  helpers for architecture at building scale.
- link_emission: public version of bake._link_emission.
- Neon text: a small stroke font (A-Z, 0-9), pseudo-CJK glyphs and a
  numpy tube rasterizer (core, hot center, soft halo) for sign atlases.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

UP = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------------------
def link_emission(mat, image, strength):
    """Connect an emission image to a final material's Emission Color with `strength`
    (glTF exports strength > 1 as KHR_materials_emissive_strength)."""
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    te = nt.nodes.new("ShaderNodeTexImage")
    te.image = image
    te.location = (-400, -600)
    nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    return te


# ---------------------------------------------------------------------------------------
# AtlasMesh
# ---------------------------------------------------------------------------------------
class AtlasMesh:
    """Collects faces (points, UVs, material slot) and writes one mesh object.

    sheets: {slot: trim.TrimSheet} for `band_face` (U along the face in meters,
    repeating; V across inside the band). Other slots take explicit UVs
    (`face`). Winding follows the `normal` hint."""

    def __init__(self, sheets=None):
        self.sheets = dict(sheets or {})
        self.faces = []
        self.warnings = set()

    # -- raw faces --
    def face(self, pts, uvs, slot, normal=None):
        pts = [Vector(p) for p in pts]
        uvs = list(uvs)
        n = _poly_normal(pts)
        if n is None:
            return
        if normal is not None and n.dot(Vector(normal)) < 0:
            pts, uvs = pts[::-1], uvs[::-1]
        self.faces.append((pts, uvs, slot))

    def band_face(self, pts, slot, band, along, normal, u=None, v=None, u_off=0.0, stretch=False):
        """A planar face in a trim band of `slot`'s sheet: U = position along
        `along` (or explicit u, meters) + u_off; V = explicit v (meters) or the
        distance across from the face's lowest point (across = normal x along)."""
        sheet = self.sheets[slot]
        pts = [Vector(p) for p in pts]
        along = Vector(along).normalized()
        nrm = Vector(normal).normalized()
        across = nrm.cross(along)
        if across.length < 1e-6:
            across = nrm.orthogonal()
        across.normalize()
        us = [p.dot(along) for p in pts] if u is None else list(u)
        us = [x + u_off for x in us]
        if v is None:
            vs = [p.dot(across) for p in pts]
            lo = min(vs)
            vs = [x - lo for x in vs]
        else:
            vs = list(v)
        bh = sheet.band_height_m(band)
        if stretch:
            lo, hi = min(vs), max(vs)
            vs = [(x - lo) / max(hi - lo, 1e-9) * bh for x in vs]
        elif max(vs) > bh + 1e-3:
            self.warnings.add(f"face {max(vs):.2f} m across, band {band} is {bh:.2f} m")
        self.face(pts, [sheet.uv(band, a, b) for a, b in zip(us, vs)], slot, nrm)

    # -- building-scale helpers (Z up) --
    def wall(self, a, b, z0, z1, slot, band, u_off=0.0, strip=3.2, z_ref=0.0, u_jitter=None, max_len=None):
        """Vertical wall from 2D point a to b (outward = right of a->b, seen from
        above), z0..z1, cut into strips at z_ref + k * strip so each strip's V
        (z - strip bottom) stays inside the band (top of the band = top of the
        strip: grime hangs from the floor line above). u_jitter(k) -> extra U
        offset per strip index k. max_len splits long walls into pieces."""
        a, b = Vector((a[0], a[1], 0.0)), Vector((b[0], b[1], 0.0))
        d = b - a
        length = d.length
        if length < 1e-6 or z1 - z0 < 1e-6:
            return
        dirn = d / length
        nrm = Vector((dirn.y, -dirn.x, 0.0))
        k0 = math.floor((z0 - z_ref) / strip + 1e-6)
        k1 = math.ceil((z1 - z_ref) / strip - 1e-6)
        pieces = max(1, math.ceil(length / max_len)) if max_len else 1
        for k in range(k0, k1):
            sb = z_ref + k * strip
            za, zb = max(z0, sb), min(z1, sb + strip)
            if zb - za < 1e-4:
                continue
            uo = u_off + (u_jitter(k) if u_jitter else 0.0)
            for p in range(pieces):
                t0, t1 = p / pieces * length, (p + 1) / pieces * length
                pa, pb = a + dirn * t0, a + dirn * t1
                pts = [Vector((pa.x, pa.y, za)), Vector((pb.x, pb.y, za)),
                       Vector((pb.x, pb.y, zb)), Vector((pa.x, pa.y, zb))]
                self.band_face(pts, slot, band, dirn, nrm, u=[t0, t1, t1, t0],
                               v=[za - sb, za - sb, zb - sb, zb - sb], u_off=uo)

    def flat(self, x0, x1, y0, y1, z, slot, band, up=True, strip=None, u_off=0.0, u_jitter=None, max_len=None):
        """Horizontal rectangle at height z (facing up or down), U along X, V
        along Y cut into strips of `strip` meters (default: the band height)."""
        sheet = self.sheets[slot]
        strip = strip or sheet.band_height_m(band)
        nrm = UP if up else -UP
        ny = max(1, math.ceil((y1 - y0) / strip - 1e-6))
        nx = max(1, math.ceil((x1 - x0) / max_len)) if max_len else 1
        for j in range(ny):
            ya, yb = y0 + j * strip, min(y1, y0 + (j + 1) * strip)
            if yb - ya < 1e-4:
                continue
            uo = u_off + (u_jitter(j) if u_jitter else 0.0)
            for i in range(nx):
                xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
                pts = [(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)]
                v = [0.0, 0.0, yb - ya, yb - ya] if up else [yb - ya, yb - ya, 0.0, 0.0]
                if not up:
                    pts = [(xa, yb, z), (xb, yb, z), (xb, ya, z), (xa, ya, z)]
                self.band_face(pts, slot, band, (1, 0, 0), nrm, u=[xa, xb, xb, xa], v=v, u_off=uo)

    def box(self, lo, hi, slot, side, top=None, bottom=None, strip=3.2, z_ref=None, sides=(1, 1, 1, 1),
            u_off=0.0, top_slot=None):
        """Axis-aligned box: vertical sides in `side` band (strips), top / bottom
        faces in their bands (None = no face). sides = (-Y, +X, +Y, -X) flags."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        zr = z0 if z_ref is None else z_ref
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        u = u_off
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            if sides[i]:
                self.wall(a, b, z0, z1, slot, side, u_off=u, strip=strip, z_ref=zr)
            u += (Vector(b) - Vector(a)).length
        ts = top_slot or slot
        if top is not None:
            self.flat(x0, x1, y0, y1, z1, ts, top, up=True)
        if bottom is not None:
            self.flat(x0, x1, y0, y1, z0, ts, bottom, up=False)

    def sweep(self, path, z, profile, bands, slot, closed=True, caps=(False, False), cap_band=None, u_off=0.0):
        """Profile (s outward, v up) swept along a horizontal polyline at height z
        with miters. The path runs counter-clockwise seen from above (outward =
        right of travel); the profile is counter-clockwise with the solid on the
        left. bands: one per profile segment (None = skip that face). U along each
        segment from its start + u_off (continuing around the path), V = arc
        length along the profile restarting per run of equal bands."""
        P = [Vector((p[0], p[1], 0.0)) for p in path]
        n = len(P)
        nseg = n if closed else n - 1
        D, S, L = [], [], []
        for i in range(nseg):
            d = P[(i + 1) % n] - P[i]
            L.append(d.length)
            d.normalize()
            D.append(d)
            S.append(Vector((d.y, -d.x, 0.0)))
        m = len(profile)
        segs = [(k, (k + 1) % m) for k in range(m)]
        arcs, s_acc, prev = [], 0.0, object()
        for (a, b), band in zip(segs, bands):
            if band != prev:
                s_acc = 0.0
            ln = math.hypot(profile[b][0] - profile[a][0], profile[b][1] - profile[a][1])
            arcs.append((s_acc, s_acc + ln))
            s_acc += ln
            prev = band

        def ring(i, seg):
            if not closed and (i == 0 or i == n - 1):
                return [P[i] + S[seg] * s + UP * (z + v) for s, v in profile]
            sa, sb = S[(i - 1) % nseg], S[i % nseg]
            mm = (sa + sb).normalized()
            k = 1.0 / max(mm.dot(sa), 1e-3)
            return [P[i] + mm * (s * k) + UP * (z + v) for s, v in profile]

        u_run = u_off
        for seg in range(nseg):
            i0, i1 = seg, (seg + 1) % n
            r0, r1 = ring(i0, seg), ring(i1, seg)
            for k, (a, b) in enumerate(segs):
                band = bands[k]
                if band is None:
                    continue
                ds, dv = profile[b][0] - profile[a][0], profile[b][1] - profile[a][1]
                nrm = S[seg] * dv - UP * ds
                pts = [r0[a], r1[a], r1[b], r0[b]]
                us = [(p - P[seg]).dot(D[seg]) for p in pts]
                va, vb = arcs[k]
                self.band_face(pts, slot, band, D[seg], nrm, u=us, v=[va, va, vb, vb], u_off=u_run)
            u_run += L[seg]
        if not closed and cap_band is not None:
            for end, (seg, i) in enumerate(((0, 0), (nseg - 1, n - 1))):
                if caps[end]:
                    rg = ring(i, seg)
                    nrm = -D[seg] if end == 0 else D[seg]
                    self.band_face(rg, slot, cap_band, S[seg], nrm)

    def cylinder(self, center, r, z0, z1, slot, band, segs=12, top=None, bottom=None, top_slot=None,
                 r_top=None, top_uv=None):
        """Vertical cylinder (or frustum with r_top): sides in `band` (U around,
        V up, one strip: keep z1 - z0 within the band), optional caps (`top_uv`:
        (u0, v0, u1, v1) maps the top disc into an atlas rectangle instead)."""
        cx, cy = center
        rt = r if r_top is None else r_top
        circ = 2 * math.pi * r
        pts0 = [Vector((cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), z0))
                for i in range(segs)]
        pts1 = [Vector((cx + rt * math.cos(2 * math.pi * i / segs), cy + rt * math.sin(2 * math.pi * i / segs), z1))
                for i in range(segs)]
        for i in range(segs):
            j = (i + 1) % segs
            ua, ub = circ * i / segs, circ * (i + 1) / segs
            mid = (pts0[i] + pts0[j]) / 2 - Vector((cx, cy, z0))
            self.band_face([pts0[i], pts0[j], pts1[j], pts1[i]], slot, band, (pts0[j] - pts0[i]).normalized(), mid,
                           u=[ua, ub, ub, ua], v=[0, 0, z1 - z0, z1 - z0])
        ts = top_slot or slot
        if top_uv is not None:
            u0, v0, u1, v1 = top_uv
            uvs = [((p.x - cx) / rt * 0.5 + 0.5, (p.y - cy) / rt * 0.5 + 0.5) for p in pts1]
            self.face(pts1, [(u0 + (u1 - u0) * a, v0 + (v1 - v0) * b) for a, b in uvs], ts, UP)
        elif top is not None:
            self.band_face(pts1, ts, top, (1, 0, 0), UP, stretch=2 * rt > self.sheets[ts].band_height_m(top))
        if bottom is not None:
            self.band_face(pts0[::-1], ts, bottom, (1, 0, 0), -UP, stretch=2 * r > self.sheets[ts].band_height_m(bottom))

    def tube(self, path, r, slot, band, segs=6):
        """Round tube (pipes, masts, rails) along a 3D polyline, square ends."""
        P = [Vector(p) for p in path]
        rings = []
        for i, p in enumerate(P):
            d = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
            ref = UP if abs(d.dot(UP)) < 0.9 else Vector((1, 0, 0))
            x = d.cross(ref).normalized()
            y = d.cross(x)
            rings.append([p + (x * math.cos(2 * math.pi * k / segs) + y * math.sin(2 * math.pi * k / segs)) * r
                          for k in range(segs)])
        circ = min(2 * math.pi * r, self.sheets[slot].band_height_m(band))  # V around, squeezed into the band
        s = 0.0
        for i in range(len(P) - 1):
            ln = (P[i + 1] - P[i]).length
            d = (P[i + 1] - P[i]).normalized()
            for k in range(segs):
                k2 = (k + 1) % segs
                q = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
                mid = sum(q, Vector()) / 4 - (P[i] + P[i + 1]) / 2
                self.band_face(q, slot, band, d, mid, u=[s, s, s + ln, s + ln],
                               v=[circ * k / segs, circ * (k + 1) / segs, circ * (k + 1) / segs, circ * k / segs])
            s += ln

    def quad_uv(self, origin, right, up, w, h, slot, rect, normal=None):
        """Rectangle origin + right * [0, w] + up * [0, h] mapped onto the atlas
        rectangle rect = (u0, v0, u1, v1) (a sign face, a decal)."""
        o, R, U = Vector(origin), Vector(right).normalized(), Vector(up).normalized()
        u0, v0, u1, v1 = rect
        pts = [o, o + R * w, o + R * w + U * h, o + U * h]
        self.face(pts, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], slot, normal or R.cross(U))

    def tris(self):
        return sum(len(p) - 2 for p, _, _ in self.faces)

    def to_object(self, name, collection, materials, merge=1e-4, sharp_angle=35.0):
        """Mesh object (UVMap, slots in `materials` order: {slot: Material})."""
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        slots = list(materials.keys())
        for pts, uvs, slot in self.faces:
            vs = [bm.verts.new(p) for p in pts]
            try:
                f = bm.faces.new(vs)
            except ValueError:
                continue
            f.material_index = slots.index(slot)
            for loop, uv in zip(f.loops, uvs):
                loop[uvl].uv = uv
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        for s in slots:
            me.materials.append(materials[s])
        from arcology_blender.geo import shade
        shade(ob, sharp_angle)
        used = {p.material_index for p in me.polygons}
        for i in sorted(set(range(len(slots))) - used, reverse=True):  # drop unused slots
            ob.active_material_index = i
            me.materials.pop(index=i)
        for w in sorted(self.warnings):
            print(f"ATLAS WARNING {name}: {w}")
        return ob


def _poly_normal(pts):
    n = Vector()
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    return n.normalized() if n.length > 1e-12 else None


# ---------------------------------------------------------------------------------------
# Neon text: stroke font, pseudo-CJK glyphs, tube rasterizer (numpy)
# ---------------------------------------------------------------------------------------
# Glyphs on a 4 x 6 grid (x right, y up), polylines of points.
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


def text_strokes(text, x0, y0, height, gap=0.35, vertical=False):
    """Segments ((x, y), (x, y)) of `text` in the stroke font, glyph cells
    height x (height * 4/6), left-bottom at (x0, y0); vertical stacks the
    glyphs top-down from y0 (the top). Returns (segments, width, height)."""
    s = height / 6.0
    adv = (4 + 6 * gap) * s
    segs = []
    for i, ch in enumerate(text.upper()):
        ox, oy = (x0 + i * adv, y0) if not vertical else (x0, y0 - (i + 1) * height * (1 + gap) + gap * height)
        for line in STROKE_FONT.get(ch, []):
            for a, b in zip(line[:-1], line[1:]):
                segs.append(((ox + a[0] * s, oy + a[1] * s), (ox + b[0] * s, oy + b[1] * s)))
    n = len(text)
    if vertical:
        return segs, 4 * s, n * height * (1 + gap) - gap * height
    return segs, n * adv - 6 * gap * s, height


def pseudo_glyph(rng, x0, y0, size):
    """Segments of an invented CJK-like character in a size x size box at
    (x0, y0): radical layouts (left/right, top/bottom, enclosure) filled with
    horizontal and vertical strokes, boxes and slanted 'legs'. Readable as
    Asian signage at a distance, means nothing."""
    segs = []

    def part(bx0, by0, bx1, by1, depth=0):
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
        else:  # comb: vertical strokes under a roof
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
    bottom, x = column) to the nearest segment; only evaluated within `pad`
    of each segment's bounding box (inf elsewhere)."""
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


def neon_tubes(shape, segs, radius, halo=3.0):
    """Neon tube masks from segments (pixels): (core, hot, glow, height)
    core = the lit tube (antialiased), hot = its white-hot center line region,
    glow = soft halo (Gaussian, `halo` x radius), height = tube profile (0..1)."""
    d = segment_distance(shape, segs, radius * halo * 2.5)
    core = np.clip(radius + 0.75 - d, 0.0, 1.5) / 1.5
    core = core * core * (3 - 2 * core)
    hot = np.clip(1.0 - d / max(radius * 0.55, 0.6), 0.0, 1.0)
    glow = np.exp(-(d / (radius * halo)) ** 2)
    height = np.sqrt(np.clip(1.0 - (d / radius) ** 2, 0.0, 1.0))
    return core, hot, glow, height
