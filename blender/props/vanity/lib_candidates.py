"""Generic helpers written for the vanity, candidates for blender/lib (not promoted yet:
other artists work in parallel and lib/ stays untouched). Asset-agnostic.

- `rounded_rect_loop`  closed loop of 3D points on a rounded rectangle at a height
                       (basins, trays, cutouts; same point count for any size, so loops loft)
- `offset_rings`       grow a stack of rounded-rectangle rings outward along their profile
                       normal (the outside of a shell: basins, tubs, bowls)
- `rect_loop_around`   points on an outer rectangle matched one-to-one to a rounded-rectangle
                       loop inside it (a slab with a rounded hole as clean quads: worktop cutouts)
- `loft_loops`         quads between consecutive closed loops of equal length (optionally
                       closing the sequence into a watertight shell)
- `convex_collider`    a `-convcolonly` object from the convex hull of points (sloped
                       colliders that boxes can't follow: basin walls, ramps)
- `lathe_along`        `curves.lathe` about any axis (pipe fittings, roses)
- `renamed`            temporarily rename objects (several parts in one .blend each export a
                       `HandleGrip` empty under that exact name)
- `reorigin`           move an object's origin to a world point without moving its geometry
                       (`lathe_along` and `reorigin` are the entrance door's candidates, copied:
                       promote them once)
"""

import math

import bmesh
from mathutils import Matrix, Vector

from arcology_blender.curves import rounded_rect_profile
from arcology_blender.geo import new_object


def rounded_rect_loop(center, width, depth, radius, z, corner_segments=8):
    """Closed loop (list of Vectors) on a rounded rectangle centered at `center`
    (x, y) at height z. Starts at the +x side's +y end and runs counter-clockwise
    (seen from above), 4 * (corner_segments + 1) points for any size, so loops of
    different sizes (and radius = half the size: a circle) loft into quads."""
    cx, cy = center[0], center[1]
    return [Vector((cx + u, cy + v, z)) for u, v in rounded_rect_profile(width, depth, radius, corner_segments)]


def offset_rings(rings, thickness):
    """Offset a stack of rounded-rectangle rings [(z, width, depth, radius), ...]
    (ordered along the profile, e.g. a basin's inner surface from rim to drain)
    by `thickness` along the profile's outward normal in the (half width, z)
    plane. Returns the outer stack in the same order and format."""
    out = []
    n = len(rings)
    for i, (z, w, d, r) in enumerate(rings):
        a0, z0 = rings[max(i - 1, 0)][1] / 2, rings[max(i - 1, 0)][0]
        a1, z1 = rings[min(i + 1, n - 1)][1] / 2, rings[min(i + 1, n - 1)][0]
        ta, tz = a1 - a0, z1 - z0
        length = math.hypot(ta, tz) or 1.0
        na, nz = tz / length, -ta / length          # perpendicular to the tangent
        if na < 0 or (abs(na) < 1e-9 and nz > 0):  # point away from the bowl's inside
            na, nz = -na, -nz
        out.append((z + thickness * nz, w + 2 * thickness * na, d + 2 * thickness * na, r + thickness * na))
    return out


def rect_loop_around(center, width, depth, radius, z, rect_lo, rect_hi, corner_segments=8):
    """Points on the rectangle rect_lo..rect_hi (x, y) at height z, one per point of
    `rounded_rect_loop(center, width, depth, radius, z, corner_segments)`: each
    corner arc maps onto its slab corner (the arc's middle point onto the corner
    itself, so corner_segments must be even), the straight runs onto the sides.
    Lofting the two loops gives the face of a slab with a rounded cutout in
    clean quads."""
    if corner_segments % 2:
        raise ValueError("corner_segments must be even")
    inner = rounded_rect_loop(center, width, depth, radius, z, corner_segments)
    k = corner_segments + 1
    half = corner_segments // 2
    out = []
    for c in range(4):
        a0 = math.radians(90.0 * c)
        mid = a0 + math.radians(45.0)
        corner = Vector((rect_hi[0] if math.cos(mid) > 0 else rect_lo[0],
                         rect_hi[1] if math.sin(mid) > 0 else rect_lo[1], z))
        p_start, p_end = inner[c * k], inner[c * k + k - 1]

        def project(p, ang):
            n = Vector((math.cos(ang), math.sin(ang)))
            if abs(n.x) > 0.5:
                return Vector((corner.x, p.y, z))
            return Vector((p.x, corner.y, z))

        s, e = project(p_start, a0), project(p_end, a0 + math.radians(90.0))
        for j in range(k):
            if j <= half:
                out.append(s.lerp(corner, j / half))
            else:
                out.append(corner.lerp(e, (j - half) / half))
    return out


def loft_loops(bm, loops, close=False):
    """Quads between consecutive closed loops (lists of 3D points of equal length)
    in `bm`; close=True also joins the last loop back to the first (a watertight
    shell from one closed cross-section). Shared vertices per loop; normals are
    recalculated. Returns the faces."""
    rings = [[bm.verts.new(p) for p in loop] for loop in loops]
    pairs = list(zip(rings[:-1], rings[1:]))
    if close:
        pairs.append((rings[-1], rings[0]))
    faces = []
    for a, b in pairs:
        m = len(a)
        for j in range(m):
            t = (j + 1) % m
            faces.append(bm.faces.new((a[j], a[t], b[t], b[j])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def convex_collider(name, points, collection):
    """`-convcolonly` collider from the convex hull of world points (Godot imports
    it as a ConvexPolygonShape3D on a StaticBody3D), for sloped surfaces that
    axis-aligned boxes can't follow. Keep the point sets small and each piece
    nearly planar: the hull fills any concavity."""
    bm = bmesh.new()
    verts = [bm.verts.new(p) for p in points]
    res = bmesh.ops.convex_hull(bm, input=verts)
    loose = {v for v in res["geom_interior"] + res["geom_unused"] if isinstance(v, bmesh.types.BMVert)}
    bmesh.ops.delete(bm, geom=list(loose), context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_object(f"{name}-convcolonly", bm, collection)
    ob.display_type = "WIRE"
    return ob


def lathe_along(bm, profile, center, direction, segments=32, closed=False):
    """`curves.lathe` with the profile's z running along `direction` from `center` (world),
    e.g. (0, 1, 0) for a pipe fitting along +Y. profile [(r, h), ...]. (Same as the
    entrance door's candidate.)"""
    from arcology_blender.curves import lathe
    verts = lathe(bm, profile, segments=segments, closed=closed)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=verts)
    return verts


def reorigin(ob, point):
    """Put the object's origin at world `point` (identity rotation/scale assumed); the
    geometry stays where it is. Build a moving part in world coordinates, then give
    it its pivot (hinge axis, slide origin, spindle)."""
    p = Vector(point)
    ob.data.transform(Matrix.Translation(-(p - ob.location)))
    ob.location = p


class renamed:
    """Context manager: temporarily rename objects ({object: name}), e.g. to export
    several parts from one .blend that each need an empty called `HandleGrip`
    (Blender names are unique, glTF node names come from them)."""

    def __init__(self, names):
        self.names = names
        self.saved = {}

    def __enter__(self):
        for ob, name in self.names.items():
            self.saved[ob] = ob.name
            ob.name = name
        return self

    def __exit__(self, *args):
        for ob, name in self.saved.items():
            ob.name = name
