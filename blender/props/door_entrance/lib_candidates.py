"""Generic helpers written for the entrance door, candidates for blender/lib (not promoted yet:
another artist works in parallel and lib/ stays untouched). Asset-agnostic.

- `bm_prism`       extrude a 2D polygon along a world axis (beveled latch edges, threshold profiles)
- `miter_sweep`    sweep a closed 2D profile along a planar polyline with true miters at the
                   corners (door and window frames, casings, gaskets, picture frames)
- `stroke_text`    raised stroke-font text (digits 0-9 and '-') as prisms with round joints
                   (unit numbers, signage) instead of a bitmap, so it stays crisp in VR
- `lathe_along`    `curves.lathe` about any axis (roses, knobs, peepholes on a vertical face)
- `self_union`     merge overlapping closed parts of one mesh (Exact boolean with self intersection)
- `reorigin`       move an object's origin to a world point without moving its geometry
"""

import math

import bmesh
from mathutils import Matrix, Vector

from arcology_blender.curves import lathe


def lathe_along(bm, profile, center, direction, segments=32, closed=False):
    """`curves.lathe` with the profile's z running along `direction` from `center` (world):
    e.g. direction (0, -1, 0) for a knob standing on a -Y facing door. profile [(r, h), ...]."""
    verts = lathe(bm, profile, segments=segments, closed=closed)
    rot = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=verts)
    return verts


def self_union(ob):
    """Merge the overlapping closed parts of one mesh (stroke text, intersecting boxes) into a
    single surface: Exact boolean UNION with self intersection, so coplanar overlaps don't
    render or bake as noise. The operand is a tiny cube far outside the mesh, removed after."""
    from arcology_blender.geo import apply_modifiers, bm_box, new_object, remove
    far = Vector((0.0, 0.0, -50.0))
    bm = bmesh.new()
    bm_box(bm, far - Vector((0.001,) * 3), far + Vector((0.001,) * 3))
    dummy = new_object(ob.name + "UnionOperand", bm, ob.users_collection[0])
    mod = ob.modifiers.new("SelfUnion", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.use_self = True
    mod.object = dummy
    apply_modifiers(ob)
    remove(dummy)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    far_local = ob.matrix_world.inverted() @ far
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co - far_local).length < 0.01], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def reorigin(ob, point):
    """Put the object's origin at world `point` (identity rotation/scale assumed); the
    geometry stays where it is. Used to build a moving part in world coordinates and then
    give it its pivot (hinge axis, spindle)."""
    p = Vector(point)
    ob.data.transform(Matrix.Translation(-(p - ob.location)))
    ob.location = p


def _axis_point(axis, t, a, b):
    if axis == "X":
        return Vector((t, a, b))
    if axis == "Y":
        return Vector((a, t, b))
    return Vector((a, b, t))


def bm_prism(bm, poly, t0, t1, axis="Z"):
    """Extrude the closed 2D polygon `poly` [(a, b), ...] from t0 to t1 along world `axis`.
    The 2D coordinates are the other two axes in order (Z: (x, y), Y: (x, z), X: (y, z)).
    Concave polygons are fine (caps are n-gons; export triangulates). Returns the faces."""
    lo = [bm.verts.new(_axis_point(axis, t0, a, b)) for a, b in poly]
    hi = [bm.verts.new(_axis_point(axis, t1, a, b)) for a, b in poly]
    n = len(poly)
    faces = [bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i])) for i in range(n)]
    faces.append(bm.faces.new(list(reversed(lo))))
    faces.append(bm.faces.new(hi))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def miter_sweep(bm, path, profile, normal, caps=True):
    """Sweep a closed 2D profile [(u, v), ...] along a planar polyline `path` (3D points in a
    plane with unit `normal`), with mitered corners: u runs along tangent x normal (for a door
    frame path up the left jamb, across the head and down the right jamb in the x-z plane with
    normal +Y, that is "outward" from the opening), v along `normal`. At each corner the
    profile is placed on the bisector plane and stretched by 1 / cos(half angle), so straight
    faces stay straight (unlike a parallel-transport sweep). Returns the faces."""
    pts = [Vector(p) for p in path]
    nrm = Vector(normal).normalized()
    n = len(pts)
    sides = []
    for i in range(n - 1):
        t = (pts[i + 1] - pts[i]).normalized()
        sides.append(t.cross(nrm).normalized())
    rings = []
    for i in range(n):
        if i == 0:
            m, k = sides[0], 1.0
        elif i == n - 1:
            m, k = sides[-1], 1.0
        else:
            m = (sides[i - 1] + sides[i]).normalized()
            k = 1.0 / max(m.dot(sides[i - 1]), 1e-4)
        rings.append([bm.verts.new(pts[i] + m * (u * k) + nrm * v) for u, v in profile])
    mlen = len(profile)
    faces = []
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(mlen):
            faces.append(bm.faces.new((a[j], b[j], b[(j + 1) % mlen], a[(j + 1) % mlen])))
    if caps:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


# Stroke font: polylines in a 1 x 1 cell (x right, y up); the glyph is drawn `width` wide.
STROKE_GLYPHS = {
    "0": [[(0.2, 0), (0.8, 0), (1, 0.18), (1, 0.82), (0.8, 1), (0.2, 1), (0, 0.82), (0, 0.18), (0.2, 0)]],
    "1": [[(0.15, 0.76), (0.55, 1), (0.55, 0)], [(0.15, 0), (0.95, 0)]],
    "2": [[(0, 0.8), (0.2, 1), (0.8, 1), (1, 0.8), (1, 0.62), (0, 0), (1, 0)]],
    "3": [[(0, 1), (1, 1), (0.45, 0.58), (0.78, 0.58), (1, 0.38), (1, 0.2), (0.8, 0), (0.2, 0), (0, 0.2)]],
    "4": [[(0.72, 0), (0.72, 1), (0, 0.3), (1, 0.3)]],
    "5": [[(1, 1), (0.05, 1), (0, 0.56), (0.78, 0.58), (1, 0.38), (1, 0.2), (0.8, 0), (0, 0)]],
    "6": [[(0.85, 1), (0.35, 1), (0, 0.62), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 0.4), (0.8, 0.58),
           (0, 0.58)]],
    "7": [[(0, 1), (1, 1), (0.35, 0)]],
    "8": [[(0.2, 0.56), (0.8, 0.56), (1, 0.36), (1, 0.18), (0.82, 0), (0.18, 0), (0, 0.18), (0, 0.36),
           (0.2, 0.56), (0.08, 0.68), (0.08, 0.86), (0.24, 1), (0.76, 1), (0.92, 0.86), (0.92, 0.68),
           (0.8, 0.56)]],
    "9": [[(0.15, 0), (0.65, 0), (1, 0.38), (1, 0.8), (0.8, 1), (0.2, 1), (0, 0.8), (0, 0.6), (0.2, 0.42),
           (1, 0.42)]],
    "-": [[(0.15, 0.5), (0.85, 0.5)]],
    " ": [],
}


def _stroke_segment(bm, p, q, half, n_axis, depth):
    d = (q - p)
    if d.length < 1e-9:
        return
    side = n_axis.cross(d.normalized()).normalized() * half
    corners = (p - side, q - side, q + side, p + side)
    lo = [bm.verts.new(c) for c in corners]
    hi = [bm.verts.new(c + n_axis * depth) for c in corners]
    faces = [bm.faces.new((lo[i], lo[(i + 1) % 4], hi[(i + 1) % 4], hi[i])) for i in range(4)]
    faces += [bm.faces.new(list(reversed(lo))), bm.faces.new(hi)]
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def _stroke_joint(bm, c, half, u_axis, v_axis, n_axis, depth, segments):
    ring = [c + (u_axis * math.cos(2 * math.pi * k / segments) + v_axis * math.sin(2 * math.pi * k / segments)) * half
            for k in range(segments)]
    lo = [bm.verts.new(p) for p in ring]
    hi = [bm.verts.new(p + n_axis * depth) for p in ring]
    faces = [bm.faces.new((lo[i], lo[(i + 1) % segments], hi[(i + 1) % segments], hi[i])) for i in range(segments)]
    faces += [bm.faces.new(list(reversed(lo))), bm.faces.new(hi)]
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def stroke_text(bm, text, origin, height, width, stroke, depth, pitch, u_axis, v_axis, n_axis,
                joint_segments=8, align="center"):
    """Raised text on a plane: each glyph is a set of straight strokes `stroke` wide and
    `depth` high along `n_axis` (the face's outward normal), with round joints and caps.
    origin: the text's baseline point (center or left, see `align`); u_axis: reading
    direction (seen from outside the face: on a +Y facing door that is -X), v_axis: up.
    Glyphs are `height` x `width`, advanced by `pitch`. Strokes overlap at the joints (no
    booleans): cheap and fine for raised letters. Returns the number of glyphs drawn."""
    u, v, nn = Vector(u_axis).normalized(), Vector(v_axis).normalized(), Vector(n_axis).normalized()
    o = Vector(origin)
    total = pitch * (len(text) - 1) + width
    if align == "center":
        o = o - u * (total / 2)
    half = stroke / 2
    inner_w, inner_h = width - stroke, height - stroke
    count = 0
    for ci, ch in enumerate(text):
        base = o + u * (ci * pitch + half) + v * half
        for line in STROKE_GLYPHS.get(ch, []):
            pts = [base + u * (x * inner_w) + v * (y * inner_h) for x, y in line]
            for a, b in zip(pts[:-1], pts[1:]):
                _stroke_segment(bm, a, b, half, nn, depth)
            for p in pts:
                _stroke_joint(bm, p, half, u, v, nn, depth, joint_segments)
        count += 1
    return count
