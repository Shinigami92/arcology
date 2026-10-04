"""Building-scale kit for the brutalist towers: blocks with facades on the
BAY x FH grid, roofs with parapets, access galleries, sky bridges, signs and
rooftop plant. Everything is written into AtlasMesh objects with UVs into the
shared texture layouts (brutalist_textures.py).

Conventions: tower-local Blender coordinates (Z up, meters, origin at the base
center on the street, front = -Y). Block outlines are axis-aligned rectangles
walked counter-clockwise from above (front edge first: -Y, +X, +Y, -X); an
edge's outward normal is to the right of travel. Floor lines sit at
z_ref + k * FH; z_ref (the ground floor height) is chosen per tower so the top
floor ends exactly at the roof slab.
"""

import math

import numpy as np
from mathutils import Vector

from brutalist_common import BAY, CELLS, FH, MAT_CONCRETE as C, MAT_METAL as M, MAT_NEON as N, MAT_WINDOWS as W
from brutalist_textures import decal_rect, neon_rect_uv
from lib_candidates import AtlasMesh

UP = Vector((0, 0, 1))
FIN_W = 0.45
BALCONY_FRONT = 0.35        # balcony fronts sit this far behind the block outline (piers stand proud)
PARAPET_H = 1.05            # balcony parapet above the floor
ROOF_PARAPET = 1.0
EDGES = ("front", "right", "back", "left")


def edge_frame(a, b):
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    e = (b - a).normalized()
    o = Vector((e.y, -e.x, 0))
    return a, e, o, (b - a).length


class Tower:
    """Mesh builders and per-tower randomness for one tower."""

    def __init__(self, name, conc_sheet, metal_sheet, plan, seed, z_ref):
        self.name = name
        sheets = {C: conc_sheet, M: metal_sheet}
        self.m = AtlasMesh(sheets)
        self.blink = AtlasMesh(sheets)
        self.rng = np.random.default_rng(seed)
        self.plan = plan
        self.z_ref = z_ref
        self.metal = metal_sheet

    # ---------------------------------------------------------------- helpers
    def floor_lines(self, z0, z1):
        k0 = max(0, math.ceil((z0 - self.z_ref) / FH - 1e-6))  # the ground floor is one tall storey
        k1 = math.floor((z1 - self.z_ref) / FH + 1e-6)
        return [self.z_ref + k * FH for k in range(k0, k1 + 1)]

    def uj(self, step=4.0, span=32.0):
        """Random U offset in whole `step`s (keeps panel joints on the grid)."""
        return float(self.rng.integers(0, int(span / step))) * step

    def wall(self, a, b, z0, z1, band="wall_a", m=None):
        (m or self.m).wall(a, b, z0, z1, C, band, u_off=self.uj(), strip=FH, z_ref=self.z_ref,
                           u_jitter=lambda k: self.uj(), max_len=24.0)

    def window_run(self, p0, e, o, length, z0, z1, m=None, skip=()):
        """Window wall (one quad per floor, random whole-cell UV offsets) from p0
        along e, facing o, floors between z0 and z1 (except floor lines in `skip`)."""
        m = m or self.m
        nb = length / BAY
        lines = self.floor_lines(z0, z1 - 0.5)
        rows = [(zf, FH) for zf in lines]
        if not lines or lines[0] > z0 + 0.05:  # ground floor below the grid: one stretched row
            rows.insert(0, (z0, (lines[0] if lines else z1) - z0))
        for zf, fh in rows:
            za, zb = max(zf, z0), min(zf + fh, z1)
            if zb - za < 0.05 or any(abs(zf - k) < 0.01 for k in skip):
                continue
            dc = float(self.rng.integers(0, CELLS))
            dr = float(self.rng.integers(0, CELLS))
            ta, tb = (za - zf) / fh, (zb - zf) / fh
            pts = [p0 + UP * za, p0 + e * length + UP * za, p0 + e * length + UP * zb, p0 + UP * zb]
            uvs = [(dc / CELLS, (dr + ta) / CELLS), ((dc + nb) / CELLS, (dr + ta) / CELLS),
                   ((dc + nb) / CELLS, (dr + tb) / CELLS), (dc / CELLS, (dr + tb) / CELLS)]
            m.face(pts, uvs, W, o)

    def window_cell_quad(self, pts, cell, normal, m=None):
        """A quad showing exactly one window cell (c, r) of the tile (skylights, a lit door)."""
        c, r = cell
        uvs = [(c / CELLS, r / CELLS), ((c + 1) / CELLS, r / CELLS), ((c + 1) / CELLS, (r + 1) / CELLS),
               (c / CELLS, (r + 1) / CELLS)]
        (m or self.m).face(pts, uvs, W, normal)

    # ---------------------------------------------------------------- facades
    @staticmethod
    def layout(length, cp_min, run_bays, fin_w=FIN_W):
        """Field layout along an edge: (pier width, [(s0, s1) window runs]).
        run_bays None: one run of as many bays as fit."""
        avail = length - 2 * cp_min
        if run_bays is None:
            n = int(math.floor(avail / BAY + 1e-6))
            width = n * BAY
            cp = (length - width) / 2
            return cp, [(cp, cp + width)] if n > 0 else []
        unit = run_bays * BAY + fin_w
        n = int(math.floor((avail + fin_w) / unit + 1e-6))
        if n < 1:
            return Tower.layout(length, cp_min, None)
        width = n * unit - fin_w
        cp = (length - width) / 2
        runs = [(cp + i * unit, cp + i * unit + run_bays * BAY) for i in range(n)]
        return cp, runs

    def facade(self, a, b, z0, z1, style, cp_min=4.0, run_bays=3, bd=1.6, band="wall_a", plants=0.0,
               skip_floors=(), slot=False, every=1, mech=()):
        """One block face from outline corner a to b (CCW), floors z0..z1.

        style: 'balcony' (window wall behind a balcony per floor, fins between
        runs, piers at the ends), 'ribbon' (spandrel bands, window strips), or
        'blank' (concrete, `slot` = a recessed one-bay window column).
        mech: floor lines of mechanical floors (louvers instead of windows, a
        heavy slab band instead of the balcony).
        Returns the window plane depth behind the outline (roof soffit reach)."""
        mech = [z for z in mech if z0 - 0.01 <= z <= z1 - FH + 0.01]
        p, e, o, L = edge_frame(a, b)

        def P(s, d):
            return p + e * s - o * d

        if style == "blank":
            if not slot:
                self.wall(a, b, z0, z1, band)
                return 0.0
            s0 = (L - BAY) / 2
            s1 = s0 + BAY
            dep = 0.6
            self.wall(P(0, 0), P(s0, 0), z0, z1, band)
            self.wall(P(s1, 0), P(L, 0), z0, z1, band)
            self.wall(P(s0, 0), P(s0, dep), z0, z1, band)
            self.wall(P(s1, dep), P(s1, 0), z0, z1, band)
            self.window_run(P(s0, dep), e, o, BAY, z0, z1, skip=mech)
            self.mech_floors(P(s0, dep), e, o, BAY, mech)
            for zf in self.floor_lines(z0 + 0.1, z1 - 0.1):  # thin slab lip per floor
                self.m.sweep([P(s0, dep), P(s1, dep)], zf, [(-0.05, -0.3), (0.25, -0.3), (0.25, 0.0), (-0.05, 0.0)],
                             ["soffit", "parapet", "top", None], C, closed=False)
            return dep
        if style == "ribbon":
            cp, runs = self.layout(L, cp_min, None)
            dep = 0.95
        else:
            cp, runs = self.layout(L, cp_min, run_bays)
            dep = BALCONY_FRONT + bd
        # piers (fronts and returns)
        self.wall(P(0, 0), P(cp, 0), z0, z1, band)
        self.wall(P(L - cp, 0), P(L, 0), z0, z1, band)
        self.wall(P(cp, 0), P(cp, dep), z0, z1, band)
        self.wall(P(L - cp, dep), P(L - cp, 0), z0, z1, band)
        floors = [zf for zf in self.floor_lines(z0 + 0.1, z1 - 0.1)]
        if style == "ribbon":
            s0, s1 = runs[0]
            self.window_run(P(s0, dep), e, o, s1 - s0, z0, z1, skip=mech)
            self.mech_floors(P(s0, dep), e, o, s1 - s0, mech)
            prof = [(-0.05, -0.55), (dep - 0.12, -0.55), (dep - 0.12, 0.85), (-0.05, 0.85)]
            heavy = [(-0.05, -0.55), (dep + 0.1, -0.55), (dep + 0.1, 0.85), (-0.05, 0.85)]
            for zf in floors:
                if zf in skip_floors:
                    continue
                pr = heavy if any(abs(zf - k) < 0.01 or abs(zf - k - FH) < 0.01 for k in mech) else prof
                self.m.sweep([P(s0, dep), P(s1, dep)], zf, pr, ["soffit", "parapet", "top", None], C, closed=False)
            return dep
        # balcony style: fins between runs
        for (s0, s1), nxt in zip(runs[:-1], runs[1:]):
            fa, fb = s1, nxt[0]
            self.wall(P(fa, 0.15), P(fb, 0.15), z0, z1, band)
            self.wall(P(fa, dep), P(fa, 0.15), z0, z1, band)
            self.wall(P(fb, 0.15), P(fb, dep), z0, z1, band)
        prof = [(-0.05, -0.35), (bd, -0.35), (bd, PARAPET_H), (bd - 0.18, PARAPET_H), (bd - 0.18, 0.0), (-0.05, 0.0)]
        bands = ["soffit", "parapet", "top", "soffit", "top", None]
        heavy = [(-0.05, -0.35), (bd + 0.15, -0.35), (bd + 0.15, 0.6), (-0.05, 0.6)]
        for s0, s1 in runs:
            self.window_run(P(s0, dep), e, o, s1 - s0, z0, z1, skip=mech)
            self.mech_floors(P(s0, dep), e, o, s1 - s0, mech)
            for i, zf in enumerate(floors):
                if zf in skip_floors:
                    continue
                if any(abs(zf - k) < 0.01 for k in mech):
                    self.m.sweep([P(s0, dep), P(s1, dep)], zf, heavy, ["soffit", "parapet", "top", None], C,
                                 closed=False)
                    continue
                if (i % every) != (every - 1):
                    continue
                self.m.sweep([P(s0, dep), P(s1, dep)], zf, prof, bands, C, closed=False)
                if plants and self.rng.random() < plants:
                    inner = dep - (bd - 0.18)  # inner face of the parapet
                    self.hedge(P(s0 + 0.3, inner + 0.5), e, o, s1 - s0 - 0.6, zf, 0.5, 1.5)
        return dep

    def mech_floors(self, p0, e, o, length, mech):
        """Mechanical floors in a window run: dark louvers between concrete bands."""
        for zf in mech:
            q = p0 + o * 0.03
            self.m.band_face([q + UP * (zf + 0.4), q + e * length + UP * (zf + 0.4), q + e * length + UP * (zf + 2.8),
                              q + UP * (zf + 2.8)], M, "louver", e, o, u=[0, length, length, 0],
                             v=[0, 0, 2.4, 2.4], u_off=self.uj(1.0))
            for za, zb in ((zf, zf + 0.4), (zf + 2.8, zf + FH)):
                self.m.wall(p0, p0 + e * length, za, zb, C, "wall_b", u_off=self.uj(), strip=FH, z_ref=self.z_ref)

    def pod(self, a, b, s0, nbays, z0, nfl, depth=3.6, back=2.05, band="wall_b"):
        """A cantilevered box on an outline edge: window front `depth` out from the
        outline (nbays wide, nfl floors from z0), concrete cheeks, spandrel bands,
        a roof with a parapet band and a soffit; reaches `back` into the facade."""
        p, e, o, L = edge_frame(a, b)

        def P(s, d):
            return p + e * s - o * d

        w = nbays * BAY
        s1 = s0 + w
        z1 = z0 + nfl * FH
        sa, sb = s0 - 0.35, s1 + 0.35
        self.window_run(P(s0, -depth), e, o, w, z0, z1)
        self.wall(P(sa, -depth), P(s0, -depth), z0, z1, band)
        self.wall(P(s1, -depth), P(sb, -depth), z0, z1, band)
        self.wall(P(sa, back), P(sa, -depth), z0 - 0.5, z1 + 0.6, band)
        self.wall(P(sb, -depth), P(sb, back), z0 - 0.5, z1 + 0.6, band)
        for k in range(nfl + 1):
            zf = z0 + k * FH
            hi = 0.6 if k == nfl else 0.45
            self.m.sweep([P(sa, -depth), P(sb, -depth)], zf, [(-0.05, -0.5), (0.3, -0.5), (0.3, hi), (-0.05, hi)],
                         ["soffit", "parapet", "top", None], C, closed=False)
        top = [P(sa, back) + UP * (z1 + 0.6), P(sb, back) + UP * (z1 + 0.6), P(sb, -depth - 0.3) + UP * (z1 + 0.6),
               P(sa, -depth - 0.3) + UP * (z1 + 0.6)]
        self.m.band_face(top, C, "roof", e, UP, u_off=self.uj(2.0))
        bot = [p_ - UP * (z1 + 0.6) + UP * (z0 - 0.5) for p_ in top]
        self.m.band_face(bot, C, "soffit", e, -UP, stretch=True)

    def frustum(self, lo, hi, z0, z1, slot, band, top_band=None, center=(0, 0), yaw=0.0, top_rect=None):
        """Box tapering from a lo (half x, half y) footprint at z0 to hi at z1
        (top offset (dx, dy) via top_rect), rotated by yaw about `center`: hulls, cabins."""
        ca, sa = math.cos(yaw), math.sin(yaw)
        cx, cy = center

        def T(x, y, z):
            return Vector((cx + x * ca - y * sa, cy + x * sa + y * ca, z))

        dx, dy = top_rect or (0.0, 0.0)
        b = [T(-lo[0], -lo[1], z0), T(lo[0], -lo[1], z0), T(lo[0], lo[1], z0), T(-lo[0], lo[1], z0)]
        t = [T(dx - hi[0], dy - hi[1], z1), T(dx + hi[0], dy - hi[1], z1), T(dx + hi[0], dy + hi[1], z1),
             T(dx - hi[0], dy + hi[1], z1)]
        mid = sum(b + t, Vector()) / 8
        for i in range(4):
            j = (i + 1) % 4
            q = [b[i], b[j], t[j], t[i]]
            n_ = sum(q, Vector()) / 4 - mid
            n_.z *= 0.3
            self.m.band_face(q, slot, band, (b[j] - b[i]).normalized(), n_, stretch=True)
        if top_band:
            self.m.band_face(t, slot, top_band, (t[1] - t[0]).normalized(), UP, stretch=True)
        return b, t

    def aircar(self, cx, cy, z, yaw):
        """A parked aircar (Fifth Element taxi scale, 5.4 x 2.4 m): tapered hull,
        cabin, tail and head lights from the neon swatches."""
        self.frustum((2.7, 1.2), (2.4, 1.05), z + 0.35, z + 1.0, M, "panel", center=(cx, cy), yaw=yaw)
        self.frustum((2.4, 1.05), (1.3, 0.85), z + 1.0, z + 1.65, M, "dark", top_band="dark", center=(cx, cy),
                     yaw=yaw, top_rect=(-0.3, 0.0))
        self.frustum((2.2, 0.9), (2.6, 1.15), z, z + 0.35, M, "dark", center=(cx, cy), yaw=yaw)
        ca, sa = math.cos(yaw), math.sin(yaw)
        fwd, side = Vector((ca, sa, 0)), Vector((-sa, ca, 0))
        c = Vector((cx, cy, 0))
        for sgn, color in ((-1, "red"), (1, "coolwhite")):
            u0, v0, u1, v1 = neon_rect_uv(f"swatch_{color}", 6)
            for k in (-1, 1):
                q = c + fwd * (sgn * 2.72) + side * (k * 0.75) + UP * (z + 0.62)
                pts = [q - side * 0.35, q + side * 0.35, q + side * 0.35 + UP * 0.22, q - side * 0.35 + UP * 0.22]
                self.m.face(pts, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], N, fwd * sgn)

    def block(self, x0, x1, y0, y1, z0, z1, faces, roof=True, roof_band="roof", parapet=True):
        """A rectangular block: faces = {edge: dict(style=..., ...)} for front/right/back/left.
        Returns the roof rectangle inside the parapet (x0, x1, y0, y1, z)."""
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        reach = 0.0
        for i, ename in enumerate(EDGES):
            kw = dict(faces.get(ename, dict(style="blank")))
            style = kw.pop("style")
            reach = max(reach, self.facade(corners[i], corners[(i + 1) % 4], z0, z1, style, **kw))
        if roof:
            return self.roof(x0, x1, y0, y1, z1, reach, roof_band, parapet)
        return None

    def roof(self, x0, x1, y0, y1, z, reach, band="roof", parapet=True):
        w_in = max(reach, 0.2) + 0.25
        path = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if parapet:
            prof = [(-w_in, -0.4), (0.1, -0.4), (0.1, ROOF_PARAPET), (-0.2, ROOF_PARAPET), (-0.2, 0.0),
                    (-w_in, 0.0)]
            self.m.sweep(path, z, prof, ["soffit", "parapet", "top", "soffit", "top", None], C, closed=True,
                         u_off=self.uj())
        else:
            prof = [(-w_in, -0.45), (0.1, -0.45), (0.1, 0.0), (-w_in, 0.0)]
            self.m.sweep(path, z, prof, ["soffit", "parapet", "top", None], C, closed=True)
        self.m.flat(x0 + w_in, x1 - w_in, y0 + w_in, y1 - w_in, z, C, band, u_off=self.uj(2.0),
                    u_jitter=lambda j: self.uj(2.0), max_len=16.0)
        return (x0 + w_in, x1 - w_in, y0 + w_in, y1 - w_in, z)

    # ---------------------------------------------------------------- additions
    def gallery(self, a, b, zf, depth=2.8, light="coolwhite", ext=(0.0, 0.0), brackets=9.0):
        """External access deck along an outline edge at floor zf: slab, metal
        railing, a soft light strip on the slab front, concrete brackets."""
        p, e, o, L = edge_frame(a, b)
        s0, s1 = -ext[0], L + ext[1]
        A, B = p + e * s0, p + e * s1
        prof = [(-0.3, -0.55), (depth, -0.55), (depth, 0.15), (-0.3, 0.15)]
        self.m.sweep([A, B], zf, prof, ["soffit", "parapet", "top", None], C, closed=False,
                     caps=(True, True), cap_band="soffit")
        # railing: front and back faces of a 1.1 m panel on the deck edge
        r0, r1 = depth - 0.12, depth - 0.04
        for d, nrm in ((r1, o), (r0, -o)):
            pa, pb = A + o * d, B + o * d
            self.m.band_face([pa + UP * (zf + 0.15), pb + UP * (zf + 0.15), pb + UP * (zf + 1.25),
                              pa + UP * (zf + 1.25)], M, "rail", e, nrm, u=[s0, s1, s1, s0],
                             v=[0, 0, 1.1, 1.1])
        self.m.band_face([A + o * r0 + UP * (zf + 1.25), B + o * r0 + UP * (zf + 1.25), B + o * r1 + UP * (zf + 1.25),
                          A + o * r1 + UP * (zf + 1.25)], M, "rail", e, UP, stretch=True, v=[1.1, 1.1, 1.2, 1.2])
        # lamps on the slab front every 6 m: soft blobs (no thin bright line)
        if light:
            n_l = max(1, int((s1 - s0) / 6.0))
            for i in range(n_l):
                s = s0 + (s1 - s0) * (i + 0.5) / n_l
                q = p + e * (s - 0.7) + o * (depth + 0.03) + UP * (zf - 0.5)
                self.m.quad_uv(q, e, UP, 1.4, 0.62, N, neon_rect_uv(f"pool_{light}", 1), o)
        # brackets: triangular concrete knees under the deck
        n = max(1, int((s1 - s0) / brackets))
        for i in range(n + 1):
            s = s0 + 0.6 + (s1 - s0 - 1.2) * i / max(n, 1)
            for side in (-0.2, 0.2):
                q = p + e * (s + side)
                top_in, top_out, low = q + UP * (zf - 0.55), q + o * (depth - 0.4) + UP * (zf - 0.55), \
                    q + UP * (zf - 2.6)
                nrm = e if side > 0 else -e
                self.m.band_face([top_in, top_out, low], C, "soffit", o, nrm)
            qa, qb = p + e * (s - 0.2), p + e * (s + 0.2)
            self.m.band_face([qa + o * (depth - 0.4) + UP * (zf - 0.55), qb + o * (depth - 0.4) + UP * (zf - 0.55),
                              qb + UP * (zf - 2.6), qa + UP * (zf - 2.6)], C, "soffit", e,
                             o * 0.9 - UP * 0.45)

    def hedge(self, p0, e, o, length, z, depth, height):
        """A planter hedge (foliage box) on a ledge: front, top, back faces."""
        q0, q1 = p0, p0 + e * length
        for d, nrm in ((depth, o), (0.0, -o)):
            a, b = q0 + o * d, q1 + o * d
            self.m.band_face([a + UP * z, b + UP * z, b + UP * (z + height), a + UP * (z + height)], C, "foliage",
                             e, nrm, v=[0, 0, height, height])
        self.m.band_face([q0 + UP * (z + height), q1 + UP * (z + height), q1 + o * depth + UP * (z + height),
                          q0 + o * depth + UP * (z + height)], C, "foliage", e, UP, v=[0.5, 0.5, 0.5 + depth,
                                                                                         0.5 + depth])

    def shrub(self, x, y, z, r, h):
        """A tree / shrub crown: six-sided frustum stack in the foliage band."""
        self.m.cylinder((x, y), r * 0.25, z, z + h * 0.35, C, "soffit", segs=5)
        self.m.cylinder((x, y), r * 0.8, z + h * 0.3, z + h * 0.6, C, "foliage", segs=7, r_top=r)
        self.m.cylinder((x, y), r, z + h * 0.6, z + h, C, "foliage", segs=7, r_top=r * 0.45, top="foliage")

    def bridge(self, x0, x1, y0, y1, z0, z1, truss=True):
        """Sky bridge between two towers along X: glazed sides on the floor grid,
        concrete slab bands, a soffit and steel trusses under it."""
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y1), (x0, y1))):
            p, e, o, L = edge_frame(a, b)
            self.window_run(p - o * 0.6, e, o, L, z0, z1)
            for zf in self.floor_lines(z0, z1):
                self.m.sweep([p - o * 0.6, p + e * L - o * 0.6], zf,
                             [(-0.05, -0.6), (0.6, -0.6), (0.6, 0.6), (-0.05, 0.6)],
                             ["soffit", "parapet", "top", None], C, closed=False)
        self.m.flat(x0, x1, y0 + 0.6, y1 - 0.6, z0 - 0.6, C, "soffit", up=False)
        self.roof(x0, x1, y0, y1, z1, 0.6, "roof")
        if truss:
            for y in (y0 + 0.4, y1 - 0.4):
                n = int((x1 - x0) / 6.0)
                pts = []
                for i in range(n + 1):
                    x = x0 + (x1 - x0) * i / n
                    pts.append(Vector((x, y, z0 - 0.6 - (3.2 if i % 2 else 0.4))))
                self.m.tube(pts, 0.28, M, "dark", segs=6)
                self.m.tube([Vector((x0, y, z0 - 3.8)), Vector((x1, y, z0 - 3.8))], 0.3, M, "dark", segs=6)

    # ---------------------------------------------------------------- signs
    def sign_panel(self, center, right, w, h, rect, depth=0.5, mount=None):
        """Flat sign: dark metal housing, the neon atlas rectangle on the front
        (facing right x up)."""
        c, R = Vector(center), Vector(right).normalized()
        nrm = R.cross(UP)
        back = c - nrm * depth
        o = c - R * (w / 2) - UP * (h / 2)
        self.m.quad_uv(o, R, UP, w, h, N, neon_rect_uv(rect, 0.5), nrm)
        # housing: sides, top, bottom and back in dark metal
        corners = [o, o + R * w, o + R * w + UP * h, o + UP * h]
        cb = [p - nrm * depth for p in corners]
        faces = [([corners[1], cb[1], cb[2], corners[2]], R), ([cb[0], corners[0], corners[3], cb[3]], -R),
                 ([corners[3], corners[2], cb[2], cb[3]], UP), ([cb[0], cb[1], corners[1], corners[0]], -UP),
                 ([cb[1], cb[0], cb[3], cb[2]], -nrm)]
        for pts, n_ in faces:
            self.m.band_face(pts, M, "dark", R if abs(n_.dot(UP)) > 0.5 else UP, n_, stretch=True)
        if mount:  # struts back to a wall at distance `mount`
            for f in (0.2, 0.8):
                for zf in (0.25, 0.75):
                    q = o + R * (w * f) + UP * (h * zf) - nrm * depth
                    self.m.tube([q, q - nrm * mount], 0.12, M, "dark", segs=4)

    def blade_sign(self, base, out, z0, rect, width=3.4, height=16.4, thick=0.6):
        """Vertical blade sign sticking out of a facade: `base` = wall point,
        `out` = outward direction. Both faces show the atlas rectangle (the
        back one mirrored so it reads)."""
        b, O = Vector(base), Vector(out).normalized()
        side = O.cross(UP).normalized()          # face normal of one side
        u0, v0, u1, v1 = neon_rect_uv(rect, 0.5)
        p0 = b + O * 0.6 + UP * z0
        for sgn in (1, -1):
            n_ = side * sgn
            q = p0 + n_ * (thick / 2)
            pts = [q, q + O * width, q + O * width + UP * height, q + UP * height]
            # read left-to-right for a viewer facing the face
            right = UP.cross(n_)
            flip = (O.dot(right) < 0)
            us = [u1, u0, u0, u1] if flip else [u0, u1, u1, u0]
            self.m.face(pts, [(us[0], v0), (us[1], v0), (us[2], v1), (us[3], v1)], N, n_)
        # edges in dark metal
        qa, qb = p0 + side * (thick / 2), p0 - side * (thick / 2)
        outer = [qa + O * width, qb + O * width]
        self.m.band_face([outer[1], outer[0], outer[0] + UP * height, outer[1] + UP * height], M, "dark", UP, O,
                         stretch=True)
        self.m.band_face([qa + UP * height, outer[0] + UP * height, outer[1] + UP * height, qb + UP * height], M,
                         "dark", O, UP, stretch=True)
        self.m.band_face([qb, outer[1], outer[0], qa], M, "dark", O, -UP, stretch=True)
        for zz in (1.0, height - 1.0):
            self.m.tube([b + UP * (z0 + zz) - O * 0.1, p0 + UP * zz], 0.15, M, "dark", segs=4)

    # ---------------------------------------------------------------- rooftop plant
    def hvac(self, x, y, z, w, d, h, fans=2, along_x=True):
        self.m.box((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + h), M, "louver", top="panel",
                   strip=2.4, z_ref=z)
        fan_uv = decal_rect(self.metal, "fan")
        for i in range(fans):
            t = (i + 0.5) / fans
            fx = x - w / 2 + w * t if along_x else x
            fy = y if along_x else y - d / 2 + d * t
            r = min(w / fans, d) * 0.42 if along_x else min(d / fans, w) * 0.42
            self.m.cylinder((fx, fy), r, z + h, z + h + 0.5, M, "panel", segs=10, top_uv=fan_uv)

    def tank(self, x, y, z, r, h, legs=2.0, band="rust"):
        if legs > 0:
            for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                q = (x + dx * r * 0.6, y + dy * r * 0.6)
                self.m.box((q[0] - 0.2, q[1] - 0.2, z), (q[0] + 0.2, q[1] + 0.2, z + legs), M, "dark", strip=1.0,
                           z_ref=z)
        zt = z + legs
        self.m.cylinder((x, y), r, zt, zt + h, M, band, segs=14, bottom="panel")
        self.m.cylinder((x, y), r, zt + h, zt + h + r * 0.35, M, band, segs=14, r_top=r * 0.15, top="panel")

    def penthouse(self, x0, x1, y0, y1, z, h, door_side="front", lit_cell=None):
        self.m.box((x0, y0, z), (x1, y1, z + h), C, "wall_b", strip=FH, z_ref=z)
        self.roof(x0, x1, y0, y1, z + h, 0.0, "top", parapet=True)
        if lit_cell is not None:  # a lit door / window (one cell of the window tile, 1.2 x 2.4 m)
            if door_side == "front":
                p = Vector(((x0 + x1) / 2 - 0.6, y0 - 0.03, z))
                self.window_cell_quad([p, p + Vector((1.5, 0, 0)), p + Vector((1.5, 0, 2.6)), p + Vector((0, 0, 2.6))],
                                      lit_cell, Vector((0, -1, 0)))
                self.wall_lamp(Vector(((x0 + x1) / 2 + 2.0, y0, z + min(h - 0.5, 2.8))), (0, -1, 0), ground=z)
            else:
                p = Vector((x1 + 0.03, (y0 + y1) / 2 - 0.75, z))
                self.window_cell_quad([p, p + Vector((0, 1.5, 0)), p + Vector((0, 1.5, 2.6)), p + Vector((0, 0, 2.6))],
                                      lit_cell, Vector((1, 0, 0)))
                self.wall_lamp(Vector((x1, (y0 + y1) / 2 + 2.0, z + min(h - 0.5, 2.8))), (1, 0, 0), ground=z)

    def mast(self, x, y, z, h, r=0.35, blink="red", dishes=1):
        self.m.tube([Vector((x, y, z)), Vector((x, y, z + h))], r, M, "dark", segs=6)
        self.m.tube([Vector((x, y, z)), Vector((x, y, z + h * 0.55))], r * 1.8, M, "panel", segs=6)
        for i in range(dishes):
            a = self.rng.uniform(0, 2 * math.pi)
            zz = z + h * (0.35 + 0.15 * i)
            d = Vector((math.cos(a), math.sin(a), 0.15)).normalized()
            c = Vector((x, y, zz)) + d * 0.9
            self.dish(c, d, 1.1)
        if blink:
            self.light(Vector((x, y, z + h + 0.3)), 0.6, blink)

    def dish(self, center, direction, r):
        d = Vector(direction).normalized()
        ref = UP if abs(d.dot(UP)) < 0.9 else Vector((1, 0, 0))
        x = d.cross(ref).normalized()
        y = d.cross(x)
        segs = 8
        rim = [center + (x * math.cos(2 * math.pi * k / segs) + y * math.sin(2 * math.pi * k / segs)) * r
               for k in range(segs)]
        apex = center - d * r * 0.45
        for k in range(segs):
            a, b = rim[k], rim[(k + 1) % segs]
            self.m.band_face([a, b, apex], M, "panel", (b - a).normalized(), d)
            self.m.band_face([b, a, apex], M, "panel", (a - b).normalized(), -d)

    def light(self, c, s, color, blink=True):
        """A small emissive light box (s meters) mapped to a swatch; blink=True puts it in <tower>_blink."""
        m = self.blink if blink else self.m
        u0, v0, u1, v1 = neon_rect_uv(f"swatch_{color}", 4)
        h = s / 2
        x0, y0, z0 = c.x - h, c.y - h, c.z - h * 0.6
        x1, y1, z1 = c.x + h, c.y + h, c.z + h * 0.6
        quads = [([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
                 ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
                 ([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0)),
                 ([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0)),
                 ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))]
        for pts, n_ in quads:
            m.face(pts, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], N, n_)

    def pool(self, c, r, color, normal=UP, kind="pool"):
        """A soft light pool (octagon decal 2-3 cm above a surface) from the neon atlas:
        reads as light from a lamp without a light. Albedo is close to concrete."""
        c, nrm = Vector(c), Vector(normal).normalized()
        ref = Vector((1, 0, 0)) if abs(nrm.x) < 0.9 else Vector((0, 1, 0))
        X = nrm.cross(ref).normalized()
        Y = nrm.cross(X)
        u0, v0, u1, v1 = neon_rect_uv(f"{kind}_{color}", 1)
        pts, uvs = [], []
        for k in range(8):
            a = math.pi / 8 + k * math.pi / 4
            ca, sa = math.cos(a), math.sin(a)
            pts.append(c + X * (ca * r) + Y * (sa * r))
            uvs.append((u0 + (u1 - u0) * (0.5 + 0.5 * ca), v0 + (v1 - v0) * (0.5 + 0.5 * sa)))
        cu = ((u0 + u1) / 2, (v0 + v1) / 2)
        for k in range(8):
            j = (k + 1) % 8
            self.m.face([c, pts[k], pts[j]], [cu, uvs[k], uvs[j]], N, nrm)

    def wall_lamp(self, p, out, color="warmwhite", pool_r=3.0, ground=None):
        """A small lamp box on a wall (0.5 m, steady) with a pool on the wall below it
        and, if `ground` (z) is given, one on the ground in front."""
        p, O = Vector(p), Vector(out).normalized()
        self.light(p + O * 0.25, 0.5, color, blink=False)
        self.pool(p + O * 0.02 - UP * 0.5, 1.0, color, O)
        if ground is not None:
            self.pool(Vector((p.x, p.y, ground + 0.03)) + O * (pool_r * 0.7), pool_r, color)

    def pipe(self, pts, r=0.3, band="rust"):
        self.m.tube([Vector(p) for p in pts], r, M, band, segs=6)
        for p in pts[1:-1]:  # supports at the bends
            q = Vector(p)
            self.m.box((q.x - 0.15, q.y - 0.15, q.z - 0.9), (q.x + 0.15, q.y + 0.15, q.z - r), M, "dark", strip=1.0,
                       z_ref=q.z - 0.9)

    def landing_pad(self, cx, cy, z, size=24.0, height=1.8, lights=12):
        """Octagonal steel landing pad on a frame: decal deck (markings), panel
        edge, a soft amber edge strip and blinking perimeter lights (_blink)."""
        r_out = size / 2 / math.cos(math.pi / 8)
        pts = [Vector((cx + r_out * math.cos(math.pi / 8 + k * math.pi / 4),
                       cy + r_out * math.sin(math.pi / 8 + k * math.pi / 4), z + height)) for k in range(8)]
        u0, v0, u1, v1 = decal_rect(self.metal, "pad")
        cpt = Vector((cx, cy, z + height))

        def uv(p):
            return (u0 + (u1 - u0) * ((p.x - cx) / size + 0.5), v0 + (v1 - v0) * ((p.y - cy) / size + 0.5))

        for k in range(8):  # fan of triangles (no slivers)
            a, b = pts[k], pts[(k + 1) % 8]
            self.m.face([cpt, a, b], [uv(cpt), uv(a), uv(b)], M, UP)
        su0, sv0, su1, sv1 = neon_rect_uv("dimstrip_amber", 2)
        for k in range(8):
            a, b = pts[k], pts[(k + 1) % 8]
            n_ = ((a + b) / 2 - cpt)
            n_.z = 0
            n_.normalize()
            self.m.band_face([a - UP * 0.7, b - UP * 0.7, b - UP * 0.3, a - UP * 0.3], M, "panel", (b - a).normalized(),
                             n_)
            self.m.band_face([a - UP * 0.3, b - UP * 0.3, b, a], M, "dark", (b - a).normalized(), n_,
                             stretch=True)
            self.m.face([a - UP * 0.7, b - UP * 0.7, cpt - UP * 0.7],
                        [uv(a), uv(b), uv(cpt)], M, -UP)
        # frame legs
        for k in range(0, 8, 2):
            q = cpt + (pts[k] - cpt) * 0.7
            self.m.box((q.x - 0.3, q.y - 0.3, z), (q.x + 0.3, q.y + 0.3, z + height - 0.7), M, "dark", strip=1.0,
                       z_ref=z)
        self.m.box((cx - 1.2, cy - 1.2, z), (cx + 1.2, cy + 1.2, z + height - 0.7), M, "panel", strip=3.2, z_ref=z)
        # perimeter lights (blink)
        for k in range(lights):
            t = k / lights * 8
            i = int(t)
            f = t - i
            a, b = pts[i % 8], pts[(i + 1) % 8]
            p = a + (b - a) * f
            self.light(Vector((p.x, p.y, z + height + 0.15)), 0.5, "amber", blink=True)
            self.pool(cpt + (p - cpt) * 0.93 + UP * 0.03, 2.2, "amber")
        self.pool(cpt + UP * 0.025, size * 0.45, "warmwhite", kind="dimpool")  # floodlit deck
