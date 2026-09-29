"""Curves and swept shapes: paths, arcs, fillets, tubes, profile sweeps, lathes (D-028).

Paths are lists of `Vector`s in the bmesh's frame. `tube` and `sweep` use
parallel-transported frames, so they don't twist; round sharp corners first
(`round_polyline`, `chaikin`, `catmull_rom`). Promoted from the bedroom set:
`tube`, `lathe`, `catmull_rom` from the nightstand (cords, lamp parts),
`sweep`, the profiles, `arc_points` and `chaikin` from the lit wardrobe
(hangers), `round_polyline` from the wardrobe, `drum_shell` from the square
nightstand.
"""

import math

import bmesh
from mathutils import Vector

ALONG_ATTR = "along"
AROUND_ATTRS = ("around_c", "around_s")


# --- paths ---------------------------------------------------------------------
def catmull_rom(points, samples=6):
    """Catmull-Rom curve through `points` (3-tuples), `samples` steps per span,
    end tangents extrapolated. Returns Vectors including both end points."""
    p = [Vector(q) for q in points]
    if len(p) < 3:
        return p
    ext = [p[0] * 2 - p[1]] + p + [p[-1] * 2 - p[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-1])
    return out


def chaikin(points, iterations=2, closed=False):
    """Chaikin corner cutting: rounds a coarse polyline (keeps the end points of
    open paths). Unlike `catmull_rom` it doesn't pass through the points."""
    pts = [Vector(p) for p in points]
    for _ in range(iterations):
        out = [] if closed else [pts[0]]
        n = len(pts)
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            out += [a.lerp(b, 0.25), a.lerp(b, 0.75)]
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def round_polyline(points, radius, steps=4, closed=False, min_turn=25.0):
    """Fillet the corners of a polyline: every corner turning by more than
    `min_turn` degrees becomes `steps` + 1 points on an arc of `radius`
    (clamped so the fillet never eats more than half of a neighboring
    segment). For bent wire (hangers, hooks, brackets)."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    out = [] if closed else [pts[0]]
    for i in (range(n) if closed else range(1, n - 1)):
        p0, p1, p2 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        d0, d1 = p0 - p1, p2 - p1
        l0, l1 = d0.length, d1.length
        if l0 < 1e-9 or l1 < 1e-9:
            out.append(p1)
            continue
        d0, d1 = d0 / l0, d1 / l1
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))  # interior angle at the corner
        if math.degrees(math.pi - ang) < min_turn:
            out.append(p1)
            continue
        r = min(radius, 0.5 * min(l0, l1) * math.tan(ang / 2))
        t = r / math.tan(ang / 2)  # tangent length
        a, b = p1 + d0 * t, p1 + d1 * t
        bis = (d0 + d1).normalized()
        c = p1 + bis * (r / math.sin(ang / 2))
        va, vb = a - c, b - c
        omega = math.acos(max(-1.0, min(1.0, va.normalized().dot(vb.normalized()))))
        for k in range(steps + 1):
            s = k / steps
            if omega < 1e-6:
                out.append(a.lerp(b, s))
            else:
                out.append(c + (va * math.sin((1 - s) * omega) + vb * math.sin(s * omega)) / math.sin(omega))
    if not closed:
        out.append(pts[-1])
    return out


def arc_points(center, radius, a0, a1, n, u_axis=(0.0, 1.0, 0.0), v_axis=(0.0, 0.0, 1.0)):
    """n + 1 points on a circular arc from angle a0 to a1 (degrees) in the plane
    spanned by u_axis (0 deg) and v_axis (90 deg) around `center`."""
    c, u, v = Vector(center), Vector(u_axis), Vector(v_axis)
    return [c + u * (radius * math.cos(math.radians(a0 + (a1 - a0) * i / n)))
            + v * (radius * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


# --- profiles (closed 2D, counter-clockwise, for `sweep`) ----------------------------
def circle_profile(radius, segments=8):
    """Closed 2D profile (list of (u, v)) for a round tube, counter-clockwise."""
    return [(radius * math.cos(2 * math.pi * i / segments), radius * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]


def rounded_rect_profile(width, height, radius, corner_segments=2):
    """Closed 2D profile of a rounded rectangle (u: width, v: height), counter-clockwise."""
    r = min(radius, 0.499 * min(width, height))
    hw, hh = width / 2 - r, height / 2 - r
    pts = []
    for cx, cy, a0 in ((hw, hh, 0.0), (-hw, hh, 90.0), (-hw, -hh, 180.0), (hw, -hh, 270.0)):
        for k in range(corner_segments + 1):
            a = math.radians(a0 + 90.0 * k / corner_segments)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# --- swept and revolved surfaces ------------------------------------------------------
def tube(bm, path, radius, segments=8, caps=True, along_attr=ALONG_ATTR, around_attrs=AROUND_ATTRS,
         closed=False):
    """Round tube along a polyline (cables, cords, pipes, wire spokes, rings).

    Frames use parallel transport, so the tube doesn't twist. Writes float
    point attributes: `along_attr` (arc length in meters from the start) and
    the cosine/sine of the angle around the tube (`around_attrs`), which
    interpolate without a seam; a material recovers the angle with ARCTAN2
    for braids or stripes (`fabric.braided_cord`). Pass None to skip them,
    or remove them before export (`geo.remove_attribute`). closed: join the
    last point back to the first (a wire ring; no caps). Returns the new
    vertices.
    """
    path = [Vector(p) for p in path]
    n = len(path)
    tangents = []
    for i in range(n):
        if closed:
            a, b = path[(i - 1) % n], path[(i + 1) % n]
        else:
            a = path[max(i - 1, 0)]
            b = path[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    t0 = tangents[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    normal = t0.cross(ref).normalized()
    la = lc = ls = None
    if along_attr:
        la = bm.verts.layers.float.get(along_attr) or bm.verts.layers.float.new(along_attr)
    if around_attrs:
        lc = bm.verts.layers.float.get(around_attrs[0]) or bm.verts.layers.float.new(around_attrs[0])
        ls = bm.verts.layers.float.get(around_attrs[1]) or bm.verts.layers.float.new(around_attrs[1])
    rings = []
    new = []
    dist = 0.0
    for i in range(n):
        t = tangents[i]
        if i > 0:
            dist += (path[i] - path[i - 1]).length
            # parallel transport: remove the tangent component and renormalize
            normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal)
        ring = []
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            v = bm.verts.new(path[i] + (normal * math.cos(a) + binormal * math.sin(a)) * radius)
            if la is not None:
                v[la] = dist
            if lc is not None:
                v[lc] = math.cos(a)
                v[ls] = math.sin(a)
            ring.append(v)
        rings.append(ring)
        new += ring
    faces = []
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for s in range(segments):
            t = (s + 1) % segments
            faces.append(bm.faces.new((a[s], a[t], b[t], b[s])))
    if caps and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return new


def sweep(bm, path, profile, up=(0.0, 0.0, 1.0), scales=None, closed=False, caps=True):
    """Sweep a closed 2D profile along a 3D polyline into `bm` (quads, capped ends).

    The frame follows the path by parallel transport, starting with the
    profile's v axis along `up` (projected off the first tangent) and u along
    tangent x v. For a path in a plane, pass the plane normal as `up` to keep
    the profile's v axis perpendicular to the plane (e.g. a hanger's
    thickness). scales: optional per-point (su, sv) profile scale (tapers).
    Profiles: `circle_profile`, `rounded_rect_profile`. Returns the new faces.
    """
    pts = [Vector(p) for p in path]
    n = len(pts)
    tangents = []
    for i in range(n):
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    upv = Vector(up)
    nrm = upv - tangents[0] * upv.dot(tangents[0])
    if nrm.length < 1e-6:
        nrm = tangents[0].orthogonal()
    nrm.normalize()
    rings = []
    for i in range(n):
        t = tangents[i]
        if i > 0:
            nrm = tangents[i - 1].rotation_difference(t) @ nrm
            nrm = (nrm - t * nrm.dot(t)).normalized()
        bin_ = t.cross(nrm)
        su, sv = scales[i] if scales else (1.0, 1.0)
        rings.append([bm.verts.new(pts[i] + bin_ * (u * su) + nrm * (v * sv)) for u, v in profile])
    m = len(profile)
    faces = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            faces.append(bm.faces.new([a[j], b[j], b[(j + 1) % m], a[(j + 1) % m]]))
    if caps and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def lathe(bm, profile, segments=32, center=(0.0, 0.0, 0.0), closed=False, attrs=None, start_angle=0.0):
    """Revolve a profile about the Z axis through `center` (a surface of
    revolution: lamp bases, stems, knobs, bulbs, bottles).

    profile: [(r, z), ...] in order; points with r == 0 become single pole
    vertices (caps). The surface faces outward when the profile runs bottom
    to top on the outside (counter-clockwise in the r/z plane); normals are
    recalculated anyway. closed: also connect the last profile point to the
    first (a closed cross-section such as a lamp shade with rolled rims).
    attrs: {name: [value per profile point]} written as float point
    attributes (e.g. a per-region emission factor). start_angle (radians)
    turns where each ring starts. Returns the new vertices.
    """
    c = Vector(center)
    layers = {k: bm.verts.layers.float.get(k) or bm.verts.layers.float.new(k) for k in (attrs or {})}
    rings = []
    new = []
    for i, (r, z) in enumerate(profile):
        if r < 1e-7:
            ring = [bm.verts.new(c + Vector((0.0, 0.0, z)))]
        else:
            ring = []
            for s in range(segments):
                a = start_angle + 2.0 * math.pi * s / segments
                ring.append(bm.verts.new(c + Vector((r * math.cos(a), r * math.sin(a), z))))
        for v in ring:
            for k, layer in layers.items():
                v[layer] = attrs[k][i]
        rings.append(ring)
        new += ring
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    faces = []
    for a, b in pairs:
        if len(a) == 1 and len(b) == 1:
            continue
        for s in range(segments):
            t = (s + 1) % segments
            if len(a) == 1:
                faces.append(bm.faces.new((a[0], b[s], b[t])))
            elif len(b) == 1:
                faces.append(bm.faces.new((a[s], b[0], a[t])))
            else:
                faces.append(bm.faces.new((a[s], a[t], b[t], b[s])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return new


def drum_shell(bm, r_bottom, r_top, z0, z1, thickness, segments=48):
    """Thin open shell of a (tapered) drum, e.g. a lamp shade: outer wall, top
    rim, inner wall, bottom rim, closed and manifold, added to `bm`. Returns
    the faces. (For rolled rims and an emission attribute, `lathe` a closed
    profile instead.)"""
    rings = []
    for r, z in ((r_bottom, z0), (r_top, z1), (r_top - thickness, z1), (r_bottom - thickness, z0)):
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / segments),
                                    r * math.sin(2 * math.pi * k / segments), z)) for k in range(segments)])
    faces = []
    for i in range(4):
        a, b = rings[i], rings[(i + 1) % 4]
        for k in range(segments):
            faces.append(bm.faces.new((a[k], a[(k + 1) % segments], b[(k + 1) % segments], b[k])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces
