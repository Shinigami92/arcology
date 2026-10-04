"""Geometry kit for the spires: faces with material and UVs by rule, stacked
plan sections, setback rings, roof caps, boxes, masts, ad panels, blink lights.

UV rules (all in meters, so every tower shares the tiling sets):
- glass:  U = (distance along the face from its bottom edge's middle + whole bays) / GLASS_TILE,
          V = (z + whole floors) / GLASS_TILE: slabs stay on z = 4k, the lit-office
          pattern shifts per face and per height band in whole cells.
- metal:  vertical faces like glass, but V restarts per band inside the panel rows
          (below LOUVER_V); horizontal faces planar in x / y. louver: V spans LOUVER_V.
- lights: strips U along z, V across the face width (soft-edged profile);
          lobby / crown: U along the face, V across the section height.
- ads:    separate objects, the quad spans its atlas region.

Faces of one section share their band cuts (no T-junctions between faces).
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

from spire_common import (
    BAY, FLOOR, GLASS_TILE, LIGHTS_PX_M, LIGHTS_SIZE, LOUVER_V, MAT_ADS, MAT_GLASS, MAT_LIGHTS, MAT_METAL,
    MATERIALS, METAL_TILE, ad_aspect, ad_uv, light_uv, seed_of,
)
from lib_candidates import offset_polygon, polygon_area, scale_polygon, whole_steps
from arcology_blender.scene import tag

LIGHT_PERIOD = LIGHTS_SIZE / LIGHTS_PX_M     # 64 m along a strip
GLASS_FLOORS = int(round(GLASS_TILE / FLOOR))
GLASS_BAYS = int(round(GLASS_TILE / BAY))
PANEL_ROWS = int(round(LOUVER_V[0] / FLOOR))  # panel rows below the louvers


class Builder:
    """Collects faces (points, uvs, material name) for one mesh object."""

    def __init__(self, seed):
        self.faces = []
        self.rng = random.Random(seed)

    def add(self, pts, mat, uvs):
        self.faces.append(([Vector(p) for p in pts], uvs, mat))

    # --- UV rules -------------------------------------------------------------------
    def glass(self, pts, origin, along, u_off, v_off):
        o, t = Vector(origin), Vector(along).normalized()
        uvs = [(((p - o).dot(t) + u_off) / GLASS_TILE, (p.z + v_off) / GLASS_TILE) for p in map(Vector, pts)]
        self.add(pts, MAT_GLASS, uvs)

    def metal_wall(self, pts, origin, along, u_off, z_base, v0):
        o, t = Vector(origin), Vector(along).normalized()
        uvs = [(((p - o).dot(t) + u_off) / METAL_TILE, (p.z - z_base + v0) / METAL_TILE) for p in map(Vector, pts)]
        self.add(pts, MAT_METAL, uvs)

    def louver(self, pts, origin, along, u_off, z0, z1):
        o, t = Vector(origin), Vector(along).normalized()
        span = LOUVER_V[1] - LOUVER_V[0] - 0.1
        uvs = [(((p - o).dot(t) + u_off) / METAL_TILE,
                (LOUVER_V[0] + 0.05 + (p.z - z0) / max(z1 - z0, 1e-6) * span) / METAL_TILE) for p in map(Vector, pts)]
        self.add(pts, MAT_METAL, uvs)

    def metal_flat(self, pts, u_off=0.0, v_off=0.0):
        uvs = [((p[0] + u_off) / METAL_TILE, (p[1] + v_off) / METAL_TILE) for p in pts]
        self.add(pts, MAT_METAL, uvs)

    def metal_auto(self, pts, u_off=0.0, v_off=0.0):
        """Any planar face: planar mapping on flat faces, U along / V up on walls (V within the panel rows)."""
        P = [Vector(p) for p in pts]
        n = (P[1] - P[0]).cross(P[2] - P[0])
        if n.length < 1e-12 and len(P) > 3:
            n = (P[2] - P[0]).cross(P[3] - P[0])
        n = n.normalized() if n.length > 1e-12 else Vector((0, 0, 1))
        if abs(n.z) > 0.7:
            self.metal_flat(pts, u_off, v_off)
            return
        t = Vector((-n.y, n.x, 0.0)).normalized()
        zmin = min(p.z for p in P)
        self.metal_wall(pts, (0, 0, 0), t, u_off, zmin, v_off % (PANEL_ROWS * FLOOR))

    def strip(self, pts_a, pts_b, color):
        """Light strip face between side A (frac 0) and side B (frac 1); each side a
        (low, high) point pair; U runs along z."""
        (a0, a1), (b0, b1) = pts_a, pts_b
        pts = [a0, b0, b1, a1]
        uvs = [light_uv(color, Vector(a0).z, 0.0), light_uv(color, Vector(b0).z, 1.0),
               light_uv(color, Vector(b1).z, 1.0), light_uv(color, Vector(a1).z, 0.0)]
        self.add(pts, MAT_LIGHTS, uvs)

    def light_band(self, pts, band, origin, along, z0, z1, u_off=0.0):
        """Lobby / crown glow: U along the face, V across z0..z1 (stretched)."""
        o, t = Vector(origin), Vector(along).normalized()
        uvs = [light_uv(band, (p - o).dot(t) + u_off, (p.z - z0) / max(z1 - z0, 1e-6)) for p in map(Vector, pts)]
        self.add(pts, MAT_LIGHTS, uvs)

    def light_solid(self, pts, band):
        """Uniform light (blink, small glowing parts): every UV in the band's center."""
        self.add(pts, MAT_LIGHTS, [light_uv(band, 1.0, 0.5)] * len(pts))

    # --- solids ---------------------------------------------------------------------
    def box(self, lo, hi, rot=0.0, center=(0.0, 0.0), mat="metal", band=None, skip=()):
        """Axis box (lo/hi in the box's frame) rotated by rot degrees about z around center.
        mat "metal" maps with metal_auto, "light" with light_solid(band). skip: face keys
        among -x +x -y +y -z +z."""
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        cx, cy = center

        def P(x, y, z):
            return Vector((cx + x * c - y * s, cy + x * s + y * c, z))

        faces = {
            "-x": [P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)],
            "+x": [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)],
            "-y": [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)],
            "+y": [P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)],
            "-z": [P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0), P(x0, y0, z0)],
            "+z": [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)],
        }
        uo, vo = whole_steps(self.rng, 32, BAY), whole_steps(self.rng, 16, FLOOR)
        for key, pts in faces.items():
            if key in skip:
                continue
            if mat == "light":
                self.light_solid(pts, band)
            else:
                self.metal_auto(pts, uo, vo)

    def beam(self, a, b, w, h=None, up=(0, 0, 1)):
        """Square-ish beam (w x h) from point a to point b (struts, braces), metal."""
        h = w if h is None else h
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        upv = Vector(up)
        if abs(d.dot(upv)) > 0.95:
            upv = Vector((1, 0, 0))
        side = d.cross(upv).normalized() * (w / 2)
        top = side.cross(d).normalized() * (h / 2)
        ring = [-side - top, side - top, side + top, -side + top]
        A = [a + r for r in ring]
        B = [b + r for r in ring]
        uo = whole_steps(self.rng, 32, BAY)
        for k in range(4):
            k2 = (k + 1) % 4
            self.metal_auto([A[k], B[k], B[k2], A[k2]], uo)
        self.metal_auto([A[0], A[1], A[2], A[3]], uo)
        self.metal_auto([B[3], B[2], B[1], B[0]], uo)

    def mast(self, x, y, z0, z1, w0, w1, sides=4):
        """Tapered square (or n-sided) tube, open at the bottom, capped on top."""
        ring = lambda z, w: [Vector((x + w / 2 * math.cos(math.radians(45 + 360 * k / sides)) * math.sqrt(2),
                                     y + w / 2 * math.sin(math.radians(45 + 360 * k / sides)) * math.sqrt(2), z))
                             for k in range(sides)]
        A, B = ring(z0, w0), ring(z1, w1)
        uo = whole_steps(self.rng, 32, BAY)
        for k in range(sides):
            k2 = (k + 1) % sides
            self.metal_auto([A[k], A[k2], B[k2], B[k]], uo)
        self.metal_auto(B, uo)

    # --- output ---------------------------------------------------------------------
    def to_object(self, name, coll, part, weld=1e-3):
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        used = [m for m in MATERIALS if any(f[2] == m for f in self.faces)]
        for pts, uvs, mat in self.faces:
            vs = [bm.verts.new(p) for p in pts]
            try:
                f = bm.faces.new(vs)
            except ValueError:
                continue
            f.material_index = used.index(mat)
            f.smooth = False
            for loop, uv in zip(f.loops, uvs):
                loop[uvl].uv = uv
        if weld:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in used:
            me.materials.append(bpy.data.materials[m])
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        tag(ob, part)
        return ob


# --- plans --------------------------------------------------------------------------------
def chamfer_rect(w, d, c, cx=0.0, cy=0.0):
    """Counter-clockwise octagon (a w x d rectangle with c chamfers) and edge tags."""
    hw, hd = w / 2, d / 2
    pts = [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
           (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]
    tags = ["front", "corner", "right", "corner", "back", "corner", "left", "corner"]
    return [(x + cx, y + cy) for x, y in pts], tags


class Section:
    """Prism slice z0..z1. plan(z) -> CCW points (same count for every section of a stack);
    kind(tag) -> "glass", "metal", "louver", "strip:<color>", "lobby", "lobby_warm",
    "crown", "none"; cuts: band heights in floors (glass/metal sections)."""

    def __init__(self, z0, z1, plan, kind, tags, columns=None, fins=None, ledges=None):
        self.z0, self.z1, self.plan, self.kind, self.tags = z0, z1, plan, kind, tags
        self.columns = columns  # (plan(z) of the column line, spacing, width) for sky lobbies
        self.fins = fins        # (tags, spacing, width, depth): vertical metal fins on those faces
        self.ledges = ledges    # (every_m, height, depth): horizontal metal ledges around the plan


def _cuts(rng, z0, z1, lo=5, hi=11):
    zs = [z0]
    z = z0
    while True:
        z = (math.floor(z / FLOOR) + rng.randint(lo, hi)) * FLOOR
        if z >= z1 - 2 * FLOOR:
            break
        zs.append(z)
    zs.append(z1)
    return zs


def _edge_at(plan, z, k):
    pts = plan(z)
    a, b = pts[k], pts[(k + 1) % len(pts)]
    return Vector((a[0], a[1], z)), Vector((b[0], b[1], z))


STRIP_FACE_MAX = 3.0    # corner faces up to this width are a light strip edge to edge
FIXTURE_W, FIXTURE_D = 1.2, 0.3


def _surface(b, kind, pts, origin, along, za, zb):
    if kind == "glass":
        b.glass(pts, origin, along, whole_steps(b.rng, GLASS_BAYS, BAY), whole_steps(b.rng, GLASS_FLOORS, FLOOR))
    elif kind == "metal":
        rows = int((zb - za) // FLOOR) + 1
        b.metal_wall(pts, origin, along, whole_steps(b.rng, 32, BAY), za,
                     whole_steps(b.rng, max(1, PANEL_ROWS - rows), FLOOR))
    elif kind == "louver":
        b.louver(pts, origin, along, whole_steps(b.rng, 32, BAY), za, zb)
    else:
        raise ValueError(f"unknown surface {kind}")


def fixture(b, A0, B0, A1, B1, color, caps=(True, True)):
    """A light strip fixture (FIXTURE_W wide, FIXTURE_D proud) centered on a wide corner face."""
    t = (B0 - A0).normalized()
    n = Vector((t.y, -t.x, 0.0))
    M0, M1 = (A0 + B0) / 2, (A1 + B1) / 2
    hw, d = FIXTURE_W / 2, n * FIXTURE_D
    l0, r0, l1, r1 = M0 - t * hw, M0 + t * hw, M1 - t * hw, M1 + t * hw
    b.strip((l0 + d, l1 + d), (r0 + d, r1 + d), color)
    b.metal_auto([l0, l0 + d, l1 + d, l1])
    b.metal_auto([r0 + d, r0, r1, r1 + d])
    if caps[0]:
        b.metal_auto([l0, r0, r0 + d, l0 + d])
    if caps[1]:
        b.metal_auto([l1 + d, r1 + d, r1, l1])


def fin(b, Q0, Q1, t, w, d):
    """Vertical metal fin w wide, d deep, from Q0 (bottom) to Q1 (top) on a face with direction t."""
    n = Vector((t.y, -t.x, 0.0))
    hw, dd = t * (w / 2), n * d
    l0, r0, l1, r1 = Q0 - hw, Q0 + hw, Q1 - hw, Q1 + hw
    uo = whole_steps(b.rng, 32, BAY)
    b.metal_auto([l0 + dd, r0 + dd, r1 + dd, l1 + dd], uo)
    b.metal_auto([l0, l0 + dd, l1 + dd, l1], uo)
    b.metal_auto([r0 + dd, r0, r1, r1 + dd], uo)
    b.metal_auto([l1 + dd, r1 + dd, r1, l1], uo)
    b.metal_auto([l0, r0, r0 + dd, l0 + dd], uo)


def ledge(b, P, z, h, d):
    """Horizontal metal ledge h tall projecting d around the plan P at height z."""
    O = offset_polygon(P, -d)
    m = len(P)
    for k in range(m):
        k2 = (k + 1) % m
        a, c = Vector((O[k][0], O[k][1], z)), Vector((O[k2][0], O[k2][1], z))
        up = Vector((0, 0, h))
        b.metal_wall([a, c, c + up, a + up], (a + c) / 2, (c - a).normalized(), whole_steps(b.rng, 32, BAY), z, 0.0)
    ring(b, O, P, z + h, True)
    ring(b, O, P, z, False)


def build_section(b, sec):
    kinds = [sec.kind(t) if callable(sec.kind) else sec.kind for t in sec.tags]
    banded = any(k in ("glass", "metal") for k in kinds)
    zs = _cuts(b.rng, sec.z0, sec.z1) if banded else [sec.z0, sec.z1]
    n = len(sec.plan(sec.z0))
    for k in range(n):
        kind = kinds[k]
        if kind == "none":
            continue
        a0, b0 = _edge_at(sec.plan, sec.z0, k)
        origin = (a0 + b0) / 2
        along = (b0 - a0).normalized()
        for za, zb in zip(zs[:-1], zs[1:]):
            A0, B0 = _edge_at(sec.plan, za, k)
            A1, B1 = _edge_at(sec.plan, zb, k)
            pts = [A0, B0, B1, A1]
            if kind.startswith("strip:"):
                color, _, under = kind[6:].partition("/")
                if (B0 - A0).length <= STRIP_FACE_MAX:
                    b.strip((A0, A1), (B0, B1), color)
                else:
                    _surface(b, under or "glass", pts, origin, along, za, zb)
                    fixture(b, A0, B0, A1, B1, color, caps=(za == zs[0], zb == zs[-1]))
            elif kind in ("lobby", "lobby_warm", "crown"):
                b.light_band(pts, kind, origin, along, sec.z0, sec.z1, whole_steps(b.rng, 8, 8.0))
            else:
                _surface(b, kind, pts, origin, along, za, zb)
    if sec.fins is not None:
        fin_tags, spacing, fw, fd = sec.fins
        for k in range(n):
            if sec.tags[k] not in fin_tags or kinds[k] == "none":
                continue
            A0, B0 = _edge_at(sec.plan, sec.z0, k)
            A1, B1 = _edge_at(sec.plan, sec.z1, k)
            m = max(2, round((B0 - A0).length / spacing))
            for j in range(1, m):
                f = j / m
                fin(b, A0 + (B0 - A0) * f, A1 + (B1 - A1) * f, (B0 - A0).normalized(), fw, fd)
    if sec.ledges is not None:
        every, lh, ld = sec.ledges
        z = sec.z0 + every
        while z < sec.z1 - FLOOR:
            ledge(b, sec.plan(z), z, lh, ld)
            z += every
    if sec.columns is not None:
        col_plan, spacing, width = sec.columns
        pts = col_plan(sec.z0)
        for k in range(len(pts)):
            a, c = Vector(pts[k]), Vector(pts[(k + 1) % len(pts)])
            length = (c - a).length
            m = max(1, round(length / spacing))
            t = (c - a).normalized()
            rot = math.degrees(math.atan2(t.y, t.x))
            for j in range(m):
                p = a + t * (length * j / m)
                inward = Vector((-t.y, t.x)) * (width / 2)
                q = p + inward + t * (width / 2 if j == 0 else 0.0)
                b.box((-width / 2, -width / 2, sec.z0), (width / 2, width / 2, sec.z1), rot, (q.x, q.y),
                      skip=("-z", "+z"))


def ring(b, outer, inner, z, up):
    """Horizontal faces between two loops (same count) at height z: terrace (up) or soffit."""
    n = len(outer)
    uo, vo = whole_steps(b.rng, 32, BAY), whole_steps(b.rng, 16, FLOOR)
    for k in range(n):
        k2 = (k + 1) % n
        q = [Vector((outer[k][0], outer[k][1], z)), Vector((outer[k2][0], outer[k2][1], z)),
             Vector((inner[k2][0], inner[k2][1], z)), Vector((inner[k][0], inner[k][1], z))]
        nz = (q[1] - q[0]).cross(q[2] - q[0]).z
        if (nz > 0) != up:
            q = q[::-1]
        if (q[1] - q[0]).cross(q[2] - q[0]).length < 1e-8 and (q[2] - q[0]).cross(q[3] - q[0]).length < 1e-8:
            continue
        b.metal_flat([tuple(p) for p in q], uo, vo)


def cap(b, pts, z, up=True):
    P = [(x, y, z) for x, y in pts]
    if (polygon_area(pts) > 0) != up:
        P = P[::-1]
    b.metal_flat(P, whole_steps(b.rng, 32, BAY), whole_steps(b.rng, 16, FLOOR))


def stack(b, sections, roof=True):
    """Build sections bottom-up with rings at every plan change and a roof cap."""
    for i, sec in enumerate(sections):
        build_section(b, sec)
        if i + 1 < len(sections):
            nxt = sections[i + 1]
            lo, hi = sec.plan(sec.z1), nxt.plan(nxt.z0)
            if max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(lo, hi)) > 1e-4:
                up = abs(polygon_area(hi)) < abs(polygon_area(lo))
                ring(b, lo if up else hi, hi if up else lo, sec.z1, up)
    if roof:
        top = sections[-1]
        cap(b, top.plan(top.z1), top.z1)


def taper_plan(base, h, top_scale, inset=0.0, center=(0.0, 0.0)):
    """plan(z): base scaled linearly from 1 at z = 0 to top_scale at z = h, then inset."""
    def plan(z):
        p = scale_polygon(base, 1.0 + (top_scale - 1.0) * z / h, center)
        return offset_polygon(p, inset) if inset else p
    return plan


# --- ads and lights ---------------------------------------------------------------------
def ad_panel(name, coll, part, region, center, normal, width, body=None, stand_off=1.0, frame=0.4,
             depth=0.9, struts=()):
    """Holo ad: a separate quad object facing `normal` (2D outward), its bottom at center.z,
    height from the region's aspect; optional frame box and struts in `body` (metal).
    center = (x, y, z_bottom) on the panel plane. struts: [(x_along, z, length)] back to the facade."""
    n = Vector((normal[0], normal[1], 0.0)).normalized()
    right = (-n).cross(Vector((0.0, 0.0, 1.0)))   # the viewer faces -n
    h = width / ad_aspect(region)
    c = Vector(center)
    p00 = c - right * (width / 2)
    p10 = c + right * (width / 2)
    pts = [p00, p10, p10 + Vector((0, 0, h)), p00 + Vector((0, 0, h))]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    for loop, uv in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop[uvl].uv = ad_uv(region, *uv)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials[MAT_ADS])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    tag(ob, part)
    if body is not None:
        rot = math.degrees(math.atan2(right.y, right.x))
        back = c - n * 0.05
        mid = back - n * (depth / 2)
        b = body
        b.box((-width / 2 - frame, -depth / 2, c.z - frame), (width / 2 + frame, depth / 2, c.z + h + frame),
              rot, (mid.x, mid.y))
        for along, z, length in struts:
            p = back - n * depth + right * along
            b.beam(Vector((p.x, p.y, z)), Vector((p.x, p.y, z)) - n * length, 0.8)
    return ob, h


def blink_lights(name, coll, part, points, size=1.4):
    """Aircraft warning lights: one object, red cubes (>= 1 m) at the given points."""
    b = Builder(seed_of(name))
    for p in points:
        x, y, z = p
        s = size / 2
        b.box((-s, -s, z - s), (s, s, z + s), 0.0, (x, y), mat="light", band="red")
    return b.to_object(name, coll, part, weld=0)
