"""Generic helpers written for the toilet, candidates for blender/lib (D-028).

Asset-agnostic; promote them into the named module (with a README line) rather
than copying them into another asset:

- curves: `egg_outline` (closed plan outline: superellipse with separate front/back
  semi-axes and exponents: toilet bowls, seats, basins, soap dishes, pebbles),
  `loft_rings` (quads between closed rings of equal size, optional n-gon caps),
  `blend_ring` (ring between two corresponding outlines at a metric offset:
  rounded rims and ring-shaped profiles such as seats, gaskets, bezels),
  `rounded_rect_xz` (closed rounded rectangle in a vertical X/Z plane), `prism_y`
  (extrude a closed X/Z outline along Y: plates, buttons, panels with round corners).
- shading: `wave_profile(socket, "TRI")` (set the wave profile of a `Graph.wave` socket,
  thin veins/lines from a triangle wave).
- studio: `reference_figure` (1.8 m mannequin; a copy of the one in
  props/door_interior/lib_candidates.py, promote one of them).
"""

import math

import bmesh
from mathutils import Matrix, Vector

from arcology_blender.curves import lathe
from arcology_blender.geo import bm_cone


# --- curves ------------------------------------------------------------------------
def egg_outline(yc, a_front, a_back, b, n, z=0.0, p_front=2.0, p_back=2.0, x0=0.0):
    """Closed plan outline (n points, counter-clockwise seen from above) of a
    superellipse centred at (x0, yc) whose front (-Y) and back (+Y) halves have
    their own semi-axes (a_front, a_back) and exponents (p 2 = ellipse, higher =
    squarer). Half width b at y = yc. Point i sits at the parameter angle
    2 pi i / n starting at +X, so outlines with the same n correspond index by
    index (loft them with `loft_rings` / `blend_ring`)."""
    pts = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        p = p_back if s > 0 else p_front
        a = a_back if s > 0 else a_front
        x = x0 + b * math.copysign(abs(c) ** (2.0 / p), c)
        y = yc + math.copysign(a * abs(s) ** (2.0 / p), s)
        pts.append(Vector((x, y, z)))
    return pts


def blend_ring(outer, inner, f, d, z):
    """Ring between two corresponding closed outlines: point i is
    lerp(outer_i, inner_i, f) moved d meters along the horizontal direction from
    outer_i toward inner_i, at height z. Profiles given as (f, d, z) give metric
    roundings (d) on rings of varying width (a seat's rounded edges)."""
    ring = []
    for po, pi in zip(outer, inner):
        dvec = Vector((pi.x - po.x, pi.y - po.y, 0.0))
        dirv = dvec.normalized() if dvec.length > 1e-9 else Vector((0.0, 0.0, 0.0))
        p = po.lerp(pi, f) + dirv * d
        ring.append(Vector((p.x, p.y, z)))
    return ring


def loft_rings(bm, rings, closed=False, cap_start=False, cap_end=False):
    """Quads between consecutive closed rings (lists of points of equal length)
    in `bm`; closed connects the last ring back to the first (a torus such as a
    seat), caps close the first/last ring with an n-gon. Normals are
    recalculated (closed surfaces come out facing outward). Returns the faces."""
    vrings = [[bm.verts.new(p) for p in ring] for ring in rings]
    m = len(vrings[0])
    faces = []
    pairs = list(zip(vrings[:-1], vrings[1:]))
    if closed:
        pairs.append((vrings[-1], vrings[0]))
    for a, b in pairs:
        for j in range(m):
            k = (j + 1) % m
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if cap_start and not closed:
        faces.append(bm.faces.new(list(reversed(vrings[0]))))
    if cap_end and not closed:
        faces.append(bm.faces.new(vrings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def rounded_rect_xz(cx, cz, w, h, r, corner_segments=4):
    """Closed rounded rectangle (list of (x, z)) centred at (cx, cz) in a vertical
    X/Z plane, counter-clockwise seen from -Y."""
    r = min(r, 0.499 * min(w, h))
    hw, hh = w / 2 - r, h / 2 - r
    pts = []
    for qx, qz, a0 in ((hw, hh, 0.0), (-hw, hh, 90.0), (-hw, -hh, 180.0), (hw, -hh, 270.0)):
        for k in range(corner_segments + 1):
            a = math.radians(a0 + 90.0 * k / corner_segments)
            pts.append((cx + qx + r * math.cos(a), cz + qz + r * math.sin(a)))
    return pts


def prism_y(bm, outline_xz, y0, y1):
    """Extrude a closed X/Z outline from y0 to y1 into a capped prism in `bm`
    (plates, buttons, panels with rounded corners). Returns the faces."""
    ring0 = [bm.verts.new((x, y0, z)) for x, z in outline_xz]
    ring1 = [bm.verts.new((x, y1, z)) for x, z in outline_xz]
    m = len(ring0)
    faces = [bm.faces.new((ring0[j], ring0[(j + 1) % m], ring1[(j + 1) % m], ring1[j])) for j in range(m)]
    faces.append(bm.faces.new(ring0))
    faces.append(bm.faces.new(list(reversed(ring1))))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


# --- shading -----------------------------------------------------------------------
def wave_profile(socket, profile="TRI"):
    """Set the wave profile ("SIN", "SAW", "TRI") of a `Graph.wave` output socket.
    A triangle wave thresholded near 1 gives thin lines of even width (veins)."""
    socket.node.wave_profile = profile
    return socket


# --- studio ------------------------------------------------------------------------
def reference_figure(bm, location=(0.0, 0.0, 0.0), height=1.8, segments=16):
    """Plain 1.8 m mannequin (legs, torso, arms, head) standing at `location`,
    facing -Y, for scale in thumbnails."""
    s = height / 1.8
    x, y, z = location

    def cone(r0, r1, z0, z1, dx=0.0):
        m = Matrix.Translation((x + dx * s, y, z + (z0 + z1) / 2 * s))
        bm_cone(bm, r0 * s, r1 * s, (z1 - z0) * s, m, segments)

    for side in (-1, 1):
        cone(0.050, 0.075, 0.0, 0.84, dx=side * 0.09)
        cone(0.040, 0.050, 0.78, 1.45, dx=side * 0.215)
    lathe(bm, [(0.0, 0.82 * s), (0.17 * s, 0.84 * s), (0.15 * s, 1.05 * s), (0.20 * s, 1.40 * s),
               (0.12 * s, 1.47 * s), (0.055 * s, 1.50 * s), (0.055 * s, 1.63 * s), (0.0, 1.63 * s)],
          segments=segments, center=(x, y, z))
    head = [(0.10 * s * math.sin(math.pi * k / 8), (1.70 - 0.10 * math.cos(math.pi * k / 8)) * s)
            for k in range(9)]
    lathe(bm, head, segments=segments, center=(x, y, z))
