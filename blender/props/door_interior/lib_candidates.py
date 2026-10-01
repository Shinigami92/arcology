"""Generic helpers written for the interior door, candidates for blender/lib (D-028).

Asset-agnostic; promote them into the named module (with a README line) rather
than copying them into another asset:

- curves: `rounded_polygon` (2D profile with per-corner fillets), `mitered_sweep`
  (profile along a planar polyline with true miters: door linings, casings, stops,
  skirting, picture frames), `lathe_axis` (`curves.lathe` about any axis).
- metal: `spun` (spun finish about any axis; `metal.brushed(center=)` is vertical only).
- studio: `wall_with_opening` (a wall slab for thumbnails of doors and windows),
  `reference_figure` (1.8 m scale mannequin for thumbnails).
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from arcology_blender.curves import lathe


# --- curves ------------------------------------------------------------------------
def rounded_polygon(points, radii, steps=3):
    """Closed 2D polygon (list of (u, v)) with corner i filleted by radii[i]
    (0 keeps it sharp), each fillet `steps` + 1 points. For profiles with some
    eased and some sharp corners (a casing: eased front, sharp back)."""
    pts = [Vector((p[0], p[1])) for p in points]
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        r = radii[i]
        if r <= 0.0:
            out.append((p1.x, p1.y))
            continue
        d0, d1 = (p0 - p1).normalized(), (p2 - p1).normalized()
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))
        t = r / math.tan(ang / 2)
        t = min(t, 0.5 * (p0 - p1).length, 0.5 * (p2 - p1).length)
        r = t * math.tan(ang / 2)
        a, b = p1 + d0 * t, p1 + d1 * t
        c = p1 + (d0 + d1).normalized() * (r / math.sin(ang / 2))
        va, vb = a - c, b - c
        a0 = math.atan2(va.y, va.x)
        sweep = math.atan2(vb.y, vb.x) - a0
        while sweep > math.pi:
            sweep -= 2 * math.pi
        while sweep < -math.pi:
            sweep += 2 * math.pi
        for k in range(steps + 1):
            a_k = a0 + sweep * k / steps
            out.append((c.x + r * math.cos(a_k), c.y + r * math.sin(a_k)))
    return out


def mitered_sweep(bm, path, profile, plane_normal, closed=False, caps=True):
    """Sweep a closed 2D profile along a polyline lying in a plane, with true
    miters at the corners (the profile is stretched by 1/cos(half turn) along
    the miter, so the profile's width stays constant on both legs).

    Profile (u, v): u runs to the side `direction x plane_normal` of the path
    (for a door lining traced up the left jamb, across the head and down the
    right jamb with plane_normal +Y, u points away from the opening); v runs
    along plane_normal. Returns the new faces (normals recalculated: keep the
    result closed with caps or a closed path).
    """
    pts = [Vector(p) for p in path]
    nrm = Vector(plane_normal).normalized()
    n = len(pts)
    rings = []
    for i in range(n):
        if closed:
            d_prev = (pts[i] - pts[i - 1]).normalized()
            d_next = (pts[(i + 1) % n] - pts[i]).normalized()
        else:
            d_prev = (pts[i] - pts[i - 1]).normalized() if i > 0 else (pts[1] - pts[0]).normalized()
            d_next = (pts[i + 1] - pts[i]).normalized() if i < n - 1 else d_prev
        s_prev, s_next = d_prev.cross(nrm), d_next.cross(nrm)
        m = (s_prev + s_next).normalized()
        scale = 1.0 / max(m.dot(s_prev), 1e-3)
        rings.append([bm.verts.new(pts[i] + m * (u * scale) + nrm * v) for u, v in profile])
    k = len(profile)
    faces = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(k):
            faces.append(bm.faces.new([a[j], b[j], b[(j + 1) % k], a[(j + 1) % k]]))
    if caps and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def lathe_axis(bm, profile, matrix, segments=32, start_angle=0.0):
    """`curves.lathe` about the Z axis of `matrix` (a rose facing -Y:
    Matrix.Translation(c) @ Matrix.Rotation(radians(90), 4, "X")). Profile (r, z)
    in that frame. Returns the new vertices."""
    tmp = bmesh.new()
    lathe(tmp, profile, segments=segments, start_angle=start_angle)
    bmesh.ops.transform(tmp, matrix=matrix, verts=tmp.verts)
    me = bpy.data.meshes.new("tmp_lathe_axis")
    tmp.to_mesh(me)
    tmp.free()
    before = len(bm.verts)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    bm.verts.ensure_lookup_table()
    return [bm.verts[i] for i in range(before, len(bm.verts))]


def facing(axis_sign):
    """Rotation matrix taking local +Z to a world axis: "-Y", "+Y", "+X", ... (lathe_axis)."""
    return {
        "-Y": Matrix.Rotation(math.radians(90.0), 4, "X"),
        "+Y": Matrix.Rotation(math.radians(-90.0), 4, "X"),
        "+X": Matrix.Rotation(math.radians(90.0), 4, "Y"),
        "-X": Matrix.Rotation(math.radians(-90.0), 4, "Y"),
        "+Z": Matrix.Identity(4),
    }[axis_sign]


# --- metal ---------------------------------------------------------------------------
def spun(g, rough=0.30, axis="Y", center=(0.0, 0.0, 0.0), streak=0.07, height=0.00002):
    """Spun (lathe-turned) metal about a world axis through `center` (x, y, z):
    fine concentric roughness rings, like `metal.brushed(center=)` but for any
    axis (a door rose faces Y). Returns (rough, height in m)."""
    i = "XYZ".index(axis)
    others = [k for k in range(3) if k != i]
    coords = (g.x, g.y, g.z)
    d0 = g.sub(coords[others[0]], center[others[0]])
    d1 = g.sub(coords[others[1]], center[others[1]])
    d = g.math("SQRT", g.add(g.mul(d0, d0), g.mul(d1, d1)))
    v = g.combine(g.mul(d, 900.0), g.mul(coords[i], 900.0), 0.0)
    n = g.noise(1.0, 2.0, 0.6, vector=v)
    coarse = g.noise(8.0, 2.0)
    r = g.add(g.add(rough, g.mul(g.sub(n, 0.5), streak * 2)), g.mul(g.sub(coarse, 0.5), 0.06))
    return r, g.mul(n, height)


# --- studio ----------------------------------------------------------------------------
def wall_with_opening(bm, x0, x1, height, y0, y1, open_x0, open_x1, open_top):
    """Wall slab from x0..x1, y0..y1, 0..height with a rectangular opening
    open_x0..open_x1 x 0..open_top (no sill), as three boxes (thumbnails of
    doors; not for game geometry)."""
    from arcology_blender.geo import bm_box
    bm_box(bm, (x0, y0, 0.0), (open_x0, y1, height))
    bm_box(bm, (open_x1, y0, 0.0), (x1, y1, height))
    bm_box(bm, (open_x0, y0, open_top), (open_x1, y1, height))


def reference_figure(bm, location=(0.0, 0.0, 0.0), height=1.8, segments=16):
    """Plain 1.8 m mannequin (legs, torso, arms, head) standing at `location`,
    facing -Y, for scale in thumbnails."""
    from arcology_blender.geo import bm_cone
    s = height / 1.8
    x, y, z = location

    def cone(r0, r1, z0, z1, dx=0.0, rot=None):
        m = Matrix.Translation((x + dx * s, y, z + (z0 + z1) / 2 * s))
        if rot is not None:
            m = m @ rot
        bm_cone(bm, r0 * s, r1 * s, (z1 - z0) * s, m, segments)

    for side in (-1, 1):
        cone(0.050, 0.075, 0.0, 0.84, dx=side * 0.09)               # legs
        cone(0.040, 0.050, 0.78, 1.45, dx=side * 0.215)             # arms
    lathe(bm, [(0.0, 0.82 * s), (0.17 * s, 0.84 * s), (0.15 * s, 1.05 * s), (0.20 * s, 1.40 * s),
               (0.12 * s, 1.47 * s), (0.055 * s, 1.50 * s), (0.055 * s, 1.63 * s), (0.0, 1.63 * s)],
          segments=segments, center=(x, y, z))
    head = [(0.10 * s * math.sin(math.pi * k / 8), (1.70 - 0.10 * math.cos(math.pi * k / 8)) * s)
            for k in range(9)]
    lathe(bm, head, segments=segments, center=(x, y, z))
