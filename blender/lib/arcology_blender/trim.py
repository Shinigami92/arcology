"""Trim sheets: tileable texture bands, trim UVs and a mesh builder for profiled
architecture (window frames, reveals, sills, rails, door casings).

A trim sheet is one texture set (albedo, normal, ORM) made of horizontal
bands, each a finish that tiles along U (anodized aluminium, stone, rubber,
a polished edge). Faces map into a band at real-world scale: U runs along the
member (meters * px_per_m, repeating), V across the face inside the band. Every
part that uses the sheet shares one material, so new parts (another
apartment's windows) need no new bake, and long rails never stretch the finish.

Bands are generated with numpy (FFT-filtered noise is periodic, so every band
tiles seamlessly along U); `TrimSheet.images` packs them into Blender images
and `bake.final_material` wires them the way the glTF exporter expects.

`TrimMesh` collects faces with a band each and writes the UVs; its sweeps
build members from 2D profiles: `rect_sweep` (a profile mitered around a
rectangle: frames, gaskets, sashes), `extrude` (a straight member), `loft`
(rings of equal length: plates, knobs), `grid` (a planar face cut into cells,
each with its own band or none: a soffit with slots). Profiles are 2D point
lists, counter-clockwise with the solid on the left; the outward normal of a
segment is on its right.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from .scene import set_colorspace


# --- tileable noise (numpy) ------------------------------------------------------
def noise(h, w, size_u, size_v=None, seed=0):
    """Smooth random field (h rows, w columns), periodic in both directions,
    zero mean and unit deviation. size_u / size_v: feature size in pixels
    along U (columns) and V (rows): anisotropic sizes give streaks (brushed
    metal: long along U, fine across)."""
    size_v = size_u if size_v is None else size_v
    rng = np.random.default_rng(seed)
    f = np.fft.rfft2(rng.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    f *= np.exp(-2.0 * math.pi ** 2 * ((fx * size_u) ** 2 + (fy * size_v) ** 2))
    out = np.fft.irfft2(f, s=(h, w))
    out -= out.mean()
    return out / (out.std() + 1e-12)


def fbm(h, w, size_u, size_v=None, octaves=4, gain=0.5, seed=0):
    """Fractal sum of `noise` octaves (sizes halve each octave), unit deviation."""
    size_v = size_u if size_v is None else size_v
    out = np.zeros((h, w))
    amp = 1.0
    for k in range(octaves):
        out += amp * noise(h, w, max(size_u / 2 ** k, 0.35), max(size_v / 2 ** k, 0.35), seed + 101 * k)
        amp *= gain
    return out / (out.std() + 1e-12)


def warp(field, du, dv):
    """Sample `field` at (row + dv, col + du) with bilinear filtering, wrapping
    in both directions (domain warp: meandering veins, wavy streaks)."""
    h, w = field.shape
    rr, cc = np.mgrid[0:h, 0:w].astype(np.float64)
    y, x = rr + dv, cc + du
    y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
    fy, fx = y - y0, x - x0
    y0, x0 = y0 % h, x0 % w
    y1, x1 = (y0 + 1) % h, (x0 + 1) % w
    return (field[y0, x0] * (1 - fx) * (1 - fy) + field[y0, x1] * fx * (1 - fy)
            + field[y1, x0] * (1 - fx) * fy + field[y1, x1] * fx * fy)


def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def height_to_normal(height, px_m, strength=1.0):
    """Tangent-space normal map (OpenGL / glTF convention, +V = green) from a
    height field in meters sampled every `px_m` meters; periodic along U.
    Returns (h, w, 3) values in 0..1."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5 / px_m
    dy = np.gradient(height, axis=0) / px_m
    n = np.dstack([-dx * strength, -dy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def image_from_array(name, rgb, colorspace="sRGB"):
    """Packed Blender image from an (h, w, 3) or (h, w) array of 0..1 values
    (row 0 is the bottom of the image, as in Blender's pixel buffer).
    Replaces an existing image of that name."""
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    set_colorspace(img, colorspace)
    px = np.ones((h, w, 4), dtype=np.float32)
    px[..., :3] = rgb[..., None] if rgb.ndim == 2 else rgb
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img


def write_png(path, rgb):
    """Write an (h, w, 3) array of 0..1 values (row 0 = bottom, as Blender's
    pixel buffer) to an 8-bit RGB PNG, byte for byte (no color management)."""
    import os
    import struct
    import zlib
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = np.clip(np.round(np.asarray(rgb)[::-1, :, :3] * 255.0), 0, 255).astype(np.uint8)
    h, w = a.shape[:2]
    raw = b"".join(b"\x00" + a[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    print("WROTE", path)


def image_pixels(img):
    """(h, w, 3) float array of a Blender image's stored values (row 0 = bottom)."""
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)[..., :3]


# --- trim sheet ------------------------------------------------------------------
class Band:
    def __init__(self, name, row0, rows, pad):
        self.name, self.row0, self.rows, self.pad = name, row0, rows, pad


class TrimSheet:
    """Layout and pixels of a trim sheet: `width` x `height` pixels at
    `px_per_m` (U repeats every width / px_per_m meters). Bands are added
    bottom-up with `pad` rows of the band's own texture above and below
    (mip bleeding stays inside the band)."""

    def __init__(self, width=1024, height=1024, px_per_m=512.0, pad=6):
        self.width, self.height, self.px_per_m, self.pad = width, height, px_per_m, pad
        self.bands = {}
        self._next = 0
        self.albedo = np.zeros((height, width, 3))
        self.rough = np.ones((height, width))
        self.metal = np.zeros((height, width))
        self.ao = np.ones((height, width))
        self.normal = np.zeros((height, width, 3))
        self.normal[..., 2] = 1.0
        self.normal = self.normal * 0.5 + 0.5

    @property
    def period_m(self):
        return self.width / self.px_per_m

    def add_band(self, name, rows):
        """Reserve `rows` usable rows (plus padding) for a finish."""
        row0 = self._next + self.pad
        if row0 + rows + self.pad > self.height:
            raise ValueError(f"trim sheet full: band {name} needs {rows} rows at {row0}")
        self.bands[name] = Band(name, row0, rows, self.pad)
        self._next = row0 + rows + self.pad
        return self.bands[name]

    def band_height_m(self, name):
        return self.bands[name].rows / self.px_per_m

    def fill(self, name, fn, seed=0):
        """Fill a band: fn(h, w, px_m, v_m, seed) -> dict with 'albedo' (h, w, 3
        linear), 'rough', 'metal', optional 'height' (meters), 'ao', 'normal_strength'.
        h includes the padding; v_m[row] is the distance in meters from the
        band's first usable row (negative in the lower padding)."""
        b = self.bands[name]
        h, w = b.rows + 2 * b.pad, self.width
        px_m = 1.0 / self.px_per_m
        v_m = (np.arange(h) - b.pad) * px_m
        out = fn(h, w, px_m, v_m[:, None], seed)
        sl = slice(b.row0 - b.pad, b.row0 + b.rows + b.pad)
        self.albedo[sl] = out["albedo"]
        self.rough[sl] = np.broadcast_to(out["rough"], (h, w))
        self.metal[sl] = np.broadcast_to(out["metal"], (h, w))
        if "ao" in out:
            self.ao[sl] = np.broadcast_to(out["ao"], (h, w))
        if "height" in out:
            hgt = np.broadcast_to(out["height"], (h, w))
            self.normal[sl] = height_to_normal(hgt, px_m, out.get("normal_strength", 1.0))

    def images(self, prefix):
        """Packed images <prefix>_albedo (sRGB), <prefix>_normal, <prefix>_orm."""
        albedo = image_from_array(f"{prefix}_albedo", linear_to_srgb(self.albedo), "sRGB")
        normal = image_from_array(f"{prefix}_normal", self.normal, "Non-Color")
        orm = np.dstack([np.clip(self.ao, 0, 1), np.clip(self.rough, 0, 1), np.clip(self.metal, 0, 1)])
        orm_img = image_from_array(f"{prefix}_orm", orm, "Non-Color")
        return albedo, normal, orm_img

    def uv(self, band, u_m, v_m):
        """UV of a point u_m meters along and v_m meters across (inside `band`)."""
        b = self.bands[band]
        v_m = min(max(v_m, 0.0), (b.rows - 0.5) / self.px_per_m)
        return (u_m * self.px_per_m / self.width, (b.row0 + v_m * self.px_per_m) / self.height)


def _stretch_value(sheet, band):
    return sheet.band_height_m(band) if band in sheet.bands else 0.0


# --- trim mesh builder ----------------------------------------------------------------
GODOT_TO_BLENDER = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
"""Basis for authoring in Godot axes: Godot (x, y, z) -> Blender (x, -z, y)."""


class TrimMesh:
    """Faces with a trim band each, authored in any linear frame (`basis`,
    e.g. GODOT_TO_BLENDER) around an optional `origin` (subtracted after the
    basis: build a moving part in the parent's frame and put its object at
    the pivot). U is measured along each face's `along` direction in the
    authoring frame plus `u_offset`, so neighbors along a member line up.

    band_mats maps band names to material slot names (default "trim"):
    emissive strips etc. get their own material and no trim band.
    Faces are wound so their normal points along the given outward normal.
    """

    def __init__(self, sheet, basis=None, origin=(0.0, 0.0, 0.0), band_mats=None, u_offset=0.0):
        self.sheet = sheet
        self.basis = Matrix(basis) if basis is not None else Matrix.Identity(3)
        self.origin = Vector(origin)
        self.band_mats = dict(band_mats or {})
        self.u_offset = u_offset
        self.faces = []  # (points, uvs, mat name, smooth)
        self.warnings = []

    # -- single faces --
    def poly(self, pts, band, along, normal=None, v=None, stretch=False, u=None):
        """One planar face. pts in the authoring frame; along: U direction;
        normal: outward hint (winding is fixed to match); v: explicit V per
        point in meters (continuous across a profile), else projected across
        the face from its lowest point; stretch: V spans the whole band
        (chamfers, tiny edges); u: explicit U per point in meters."""
        pts = [Vector(p) for p in pts]
        along = Vector(along).normalized()
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-14 and len(pts) > 3:
            n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
        if normal is not None and n.dot(Vector(normal)) < 0:
            pts = pts[::-1]
            if v is not None:
                v = v[::-1]
            if u is not None:
                u = u[::-1]
            n = -n
        if n.length < 1e-14:
            return
        n.normalize()
        across = n.cross(along)
        if across.length < 1e-6:
            across = n.orthogonal()
        across.normalize()
        us = [p.dot(along) + self.u_offset for p in pts] if u is None else [x + self.u_offset for x in u]
        if v is None:
            vs = [p.dot(across) for p in pts]
            lo = min(vs)
            vs = [x - lo for x in vs]
        else:
            vs = list(v)
        if band in self.sheet.bands:
            bh = self.sheet.band_height_m(band)
            if stretch:
                span = max(max(vs) - min(vs), 1e-9)
                vs = [(x - min(vs)) / span * bh for x in vs]
            elif max(vs) > bh + 1e-4:
                self.warnings.append(f"face wider ({max(vs):.3f} m) than band {band} ({bh:.3f} m)")
            uvs = [self.sheet.uv(band, a, b) for a, b in zip(us, vs)]
        else:
            uvs = [(0.0, 0.0)] * len(pts)
        self.faces.append((pts, uvs, self.band_mats.get(band, "trim"), False))

    def quad_strip(self, a_pts, b_pts, band, along, normal, closed=False):
        """Quads between two point rows of equal length (a loft step)."""
        n = len(a_pts)
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            self.poly([a_pts[k], a_pts[k2], b_pts[k2], b_pts[k]], band, along, normal)

    # -- sweeps --
    @staticmethod
    def _segments(profile, closed):
        m = len(profile)
        return [(k, (k + 1) % m) for k in range(m if closed else m - 1)]

    @staticmethod
    def _arc(profile, segs, bands):
        """V (meters) at both ends of every segment: arc length restarting at
        each run of equal bands, so faces of one finish continue."""
        out = []
        s = 0.0
        prev = None
        for (a, b), band in zip(segs, bands):
            key = band if isinstance(band, str) else id(band)
            if key != prev:
                s = 0.0
            length = (Vector(profile[b]) - Vector(profile[a])).length
            out.append((s, s + length))
            s += length
            prev = key
        return out

    def _band(self, band, normal):
        return band(normal) if callable(band) else band

    def rect_sweep(self, rect, profile, bands, depth_axis=(0.0, 0.0, 1.0), closed=True,
                   side_offset=(0.0, 0.0, 0.0, 0.0), sides=(True, True, True, True), stretch=(), skip=()):
        """Sweep a 2D profile (inset, depth) around the rectangle
        rect = (x0, x1, y0, y1) (in the authoring frame's X/Y), mitered at the
        corners: inset > 0 points into the rectangle, depth along
        `depth_axis`. bands: one per segment (str, or callable(normal) -> str
        for normal-dependent finishes such as dust on upward faces).
        side_offset (left, right, bottom, top) shifts the insets on that side:
        a number, or callable(inset) -> shift (move only the outer edge: a
        sash with a gap on three sides and none on its hinge rail). sides: which of (left, right,
        bottom, top) to build; a side next to a missing one ends square at
        the rectangle's edge. stretch: segment indices whose V spans the band.
        skip: (side, segment) pairs to leave out, e.g. ("T", 2) to build that
        face yourself with `grid` (a slot in a head rail)."""
        x0, x1, y0, y1 = rect
        dz = Vector(depth_axis)
        segs = self._segments(profile, closed)
        seg_bands = [bands[k] for k in range(len(segs))]
        arcs = self._arc(profile, segs, seg_bands)
        offs = [(f if callable(f) else (lambda i, f=f: f)) for f in side_offset]
        hasL, hasR, hasB, hasT = sides
        X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))

        def corner(side, end, i):
            """Point of the inset-i line of `side` at its `end` (0 = low, 1 = high)."""
            oL, oR, oB, oT = (f(i) for f in offs)
            if side in ("B", "T"):
                y = y0 + i + oB if side == "B" else y1 - i - oT
                if end == 0:
                    x = x0 + i + oL if hasL else x0
                else:
                    x = x1 - i - oR if hasR else x1
                return Vector((x, y, 0.0))
            x = x0 + i + oL if side == "L" else x1 - i - oR
            if end == 0:
                y = y0 + i + oB if hasB else y0
            else:
                y = y1 - i - oT if hasT else y1
            return Vector((x, y, 0.0))

        dirs = {"L": X, "R": -X, "B": Y, "T": -Y}
        alongs = {"L": Y, "R": Y, "B": X, "T": X}
        for side, on in zip("LRBT", sides):
            if not on:
                continue
            inward = dirs[side]
            for (a, b), band, (va, vb), si in zip(segs, seg_bands, arcs, range(len(segs))):
                if (side, si) in skip:
                    continue
                (ia, za), (ib, zb) = profile[a], profile[b]
                t2 = (ib - ia, zb - za)
                n2 = (t2[1], -t2[0])  # right of travel = outward
                normal = inward * n2[0] + dz * n2[1]
                pa0, pa1 = corner(side, 0, ia) + dz * za, corner(side, 1, ia) + dz * za
                pb0, pb1 = corner(side, 0, ib) + dz * zb, corner(side, 1, ib) + dz * zb
                self.poly([pa0, pa1, pb1, pb0], self._band(band, normal), alongs[side], normal,
                          v=[va, va, vb, vb], stretch=si in stretch)

    def extrude(self, profile, origin, a_axis, b_axis, d_axis, length, bands, closed=True,
                caps=(False, False), cap_band=None, stretch=()):
        """Straight member: the 2D profile (a, b) in the plane spanned by
        a_axis / b_axis at `origin`, extruded `length` along d_axis (U runs
        along d_axis). caps (start, end): close the ends with the profile
        polygon (convex profiles) in `cap_band`."""
        o, A, B, D = Vector(origin), Vector(a_axis), Vector(b_axis), Vector(d_axis).normalized()
        segs = self._segments(profile, closed)
        seg_bands = [bands[k] for k in range(len(segs))]
        arcs = self._arc(profile, segs, seg_bands)
        for (a, b), band, (va, vb), si in zip(segs, seg_bands, arcs, range(len(segs))):
            pa = o + A * profile[a][0] + B * profile[a][1]
            pb = o + A * profile[b][0] + B * profile[b][1]
            t2 = (profile[b][0] - profile[a][0], profile[b][1] - profile[a][1])
            normal = A * t2[1] - B * t2[0]  # right of travel = outward
            self.poly([pa, pb, pb + D * length, pa + D * length], self._band(band, normal), D, normal,
                      v=[va, vb, vb, va], stretch=si in stretch)
        ring = [o + A * p[0] + B * p[1] for p in profile]
        if caps[0]:
            self.poly(ring, cap_band, A, -D)
        if caps[1]:
            self.poly([p + D * length for p in ring], cap_band, A, D)

    def loft(self, rings, bands, along, closed=True, cap_start=None, cap_end=None, center=None):
        """Quads between consecutive rings (equal point counts): plates with
        chamfers, knobs, hubs. bands: one per ring step. along: U direction.
        Outward is away from `center` (default: the rings' centroid); pass
        center="rings" for long or bent shapes (each quad faces away from its
        two rings' centroids: a lever swept along a path). cap_start / cap_end: band for a
        polygon closing the first / last ring (facing away from the loft)."""
        rings = [[Vector(p) for p in r] for r in rings]
        per_ring = isinstance(center, str)
        if per_ring:
            cents = [sum(r, Vector()) / len(r) for r in rings]
        else:
            c = Vector(center) if center is not None else sum((p for r in rings for p in r), Vector()) / sum(
                len(r) for r in rings)
        n = len(rings[0])
        for j, (r0, r1, band) in enumerate(zip(rings[:-1], rings[1:], bands)):
            if per_ring:
                c = (cents[j] + cents[j + 1]) / 2
            for k in range(n if closed else n - 1):
                k2 = (k + 1) % n
                q = [r0[k], r0[k2], r1[k2], r1[k]]
                mid = sum(q, Vector()) / 4
                self.poly(q, band, along, mid - c)
        for ring, band, other in ((rings[0], cap_start, rings[1]), (rings[-1], cap_end, rings[-2])):
            if band is None:
                continue
            cr = sum(ring, Vector()) / len(ring)
            co = sum(other, Vector()) / len(other)
            self.poly(ring, band, along, cr - co)

    def bridge(self, inner, outer, band, along, normal, center):
        """Fill the planar ring between two closed loops of any point counts
        (a face with a round hole: a panel around a button) with triangles,
        zipping both loops by angle around `center`. Uses the loops' own
        vertices, so neighbors sharing them get no T-junctions."""
        c, nrm = Vector(center), Vector(normal).normalized()
        ref = nrm.orthogonal().normalized()
        ref2 = nrm.cross(ref)

        def ang(p):
            d = Vector(p) - c
            return math.atan2(d.dot(ref2), d.dot(ref)) % (2 * math.pi)

        def ordered(loop):
            loop = [Vector(p) for p in loop]
            k = min(range(len(loop)), key=lambda i: ang(loop[i]))
            loop = loop[k:] + loop[:k]
            if len(loop) > 2 and ang(loop[1]) > ang(loop[-1]):
                loop = [loop[0]] + loop[1:][::-1]
            return loop

        a, b = ordered(inner), ordered(outer)
        na, nb = len(a), len(b)
        ia = ib = 0
        while ia < na or ib < nb:
            ta = ang(a[(ia + 1) % na]) + (2 * math.pi if ia + 1 >= na else 0.0)
            tb = ang(b[(ib + 1) % nb]) + (2 * math.pi if ib + 1 >= nb else 0.0)
            if ib >= nb or (ia < na and ta <= tb):
                self.poly([a[ia % na], a[(ia + 1) % na], b[ib % nb]], band, along, nrm)
                ia += 1
            else:
                self.poly([a[ia % na], b[(ib + 1) % nb], b[ib % nb]], band, along, nrm)
                ib += 1

    def grid(self, origin, u_axis, v_axis, u_cuts, v_cuts, cell, normal, along=None):
        """Planar face at `origin` spanned by u_axis / v_axis, cut at the
        given coordinates into cells; cell(u_mid, v_mid) -> band or None (a
        hole). Cells of one band share continuous UVs (V from v_cuts[0])."""
        o, U, V = Vector(origin), Vector(u_axis), Vector(v_axis)
        al = Vector(along) if along is not None else U
        for i in range(len(u_cuts) - 1):
            for j in range(len(v_cuts) - 1):
                band = cell((u_cuts[i] + u_cuts[i + 1]) / 2, (v_cuts[j] + v_cuts[j + 1]) / 2)
                if band is None:
                    continue
                ua, ub, va, vb = u_cuts[i], u_cuts[i + 1], v_cuts[j], v_cuts[j + 1]
                pts = [o + U * ua + V * va, o + U * ub + V * va, o + U * ub + V * vb, o + U * ua + V * vb]
                vv = [va - v_cuts[0], va - v_cuts[0], vb - v_cuts[0], vb - v_cuts[0]]
                if abs(U.normalized().dot(al.normalized())) < 0.5:  # U along v_axis: V comes from u
                    vv = [ua - u_cuts[0], ub - u_cuts[0], ub - u_cuts[0], ua - u_cuts[0]]
                self.poly(pts, band, al, normal, v=vv)

    # -- output --
    def to_object(self, name, collection, materials, merge=True, sharp_angle=35.0, smooth=True):
        """Mesh object with UVMap and material slots in first-use order.
        materials: {slot name: Material}. merge welds coincident vertices so
        rounded profiles shade smooth; edges sharper than sharp_angle stay
        split (crisp chamfers)."""
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        slots = []
        for pts, uvs, mat, _ in self.faces:
            if mat not in slots:
                slots.append(mat)
            vs = [bm.verts.new(self.basis @ p - self.origin) for p in pts]
            try:
                f = bm.faces.new(vs)
            except ValueError:
                continue
            f.material_index = slots.index(mat)
            for loop, uv in zip(f.loops, uvs):
                loop[uvl].uv = uv
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        for s in slots:
            me.materials.append(materials[s])
        if smooth:
            from .geo import shade
            shade(ob, sharp_angle)
        for w in sorted(set(self.warnings)):
            print(f"TRIM WARNING {name}: {w}")
        return ob
