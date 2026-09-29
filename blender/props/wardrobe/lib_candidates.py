"""Helpers of the wardrobe (Fable 5.1, won the bedroom A/B, D-032).

The library has its own versions of these (`curves.arc_points`, `curves.tube`,
`wood.veneer_axis`, `metal.brushed`, `wear.scratch`), but they compute
slightly different geometry or node graphs, so this asset keeps its
originals and rebuilds byte-identically; `wire_hanger` stays with them
because it is built from these `arc_points` and `bm_tube`. Prefer the
library for new assets. Promoted from here: round_polyline
(`curves.round_polyline`), bm_tapered_cyl (`geo.bm_cone`), bm_open_box
(`geo.bm_open_box`), linked_copy (`geo.instance`), hanging_garment
(`cloth.hanging_garment`), fixture_wear (`wear.fixture_wear`).
"""

import math

import bmesh
from mathutils import Vector

from arcology_blender.curves import round_polyline


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def arc_points(center, radius, a0, a1, n, axes=(1, 2)):
    """`n` points on a circular arc from angle `a0` to `a1` (degrees) in the
    plane spanned by `axes` (xyz indices; default the YZ plane, angle measured
    from the first axis toward the second)."""
    c = Vector(center)
    pts = []
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / max(n - 1, 1))
        p = c.copy()
        p[axes[0]] += radius * math.cos(a)
        p[axes[1]] += radius * math.sin(a)
        pts.append(p)
    return pts


def bm_tube(bm, points, radius, segments=8, closed=False, caps=True):
    """Tube swept along a polyline (wire, cable, pipe, hanger). Frames are
    parallel-transported, so round sharp corners first (`round_polyline`).
    Returns the list of rings (lists of verts)."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    tangents = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[(i - 1) % n]
        elif i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tangents.append(t.normalized())
    t0 = tangents[0]
    ref = Vector((0.0, 0.0, 1.0)) if abs(t0.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    nrm = (ref - t0 * ref.dot(t0)).normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        bn = t.cross(nrm)
        ring = []
        for k in range(segments):
            a = 2 * math.pi * k / segments
            ring.append(bm.verts.new(pts[i] + (nrm * math.cos(a) + bn * math.sin(a)) * radius))
        rings.append(ring)
    faces = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(segments):
            faces.append(bm.faces.new((a[k], b[k], b[(k + 1) % segments], a[(k + 1) % segments])))
    if caps and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return rings




# ---------------------------------------------------------------------------
# soft goods
# ---------------------------------------------------------------------------
def wire_hanger(bm, rail_radius=0.0125, wire=0.0021, width=0.42, drop=0.10, neck=0.05,
                hook_gap=0.0, segments=6):
    """Wire clothes hanger in the XZ plane: shoulders along X, the hook wraps
    a rail that runs along Y. The bmesh origin is the hook's resting point,
    where the inside of the hook sits on the rail top (rail axis at z =
    -rail_radius), so a pickable built from it snaps onto a rail by its
    origin. Hook, neck, two shoulders and the bottom bar are one swept wire.
    Returns the z of the neck bottom (shoulder line) for garments."""
    hook_r = rail_radius + wire + hook_gap
    pts = arc_points((0, 0, 0), hook_r, -20.0, 250.0, 18, axes=(0, 2))
    neck_z = -hook_r - neck
    pts += [Vector((hook_r * math.cos(math.radians(250.0)), 0.0, neck_z + 0.02)),
            Vector((0.0, 0.0, neck_z)),
            Vector((-width / 2, 0.0, neck_z - drop)),
            Vector((width / 2, 0.0, neck_z - drop)),
            Vector((0.004, 0.0, neck_z - 0.002))]
    pts = round_polyline(pts, 0.012, steps=3)
    shift = Vector((0.0, 0.0, -rail_radius))
    bm_tube(bm, [p + shift for p in pts], wire, segments=segments)
    return neck_z - rail_radius


# ---------------------------------------------------------------------------
# materials (Graph layers; return values like the fabric module)
# ---------------------------------------------------------------------------
def wood_veneer(g, ground, line, period=0.028, distortion=20.0, line_strength=0.42,
                fine_period=0.009, fine=0.10, figure=0.12, rough=0.40, pores=0.00012):
    """Sliced veneer from world position: grain runs vertically on vertical
    faces and along X on horizontal faces. Thin latewood lines of color `line`
    (about `period` meters apart, irregular: a wave warped by a multi-octave
    noise, `distortion`) sit on the `ground` color at `line_strength`; a finer,
    low-contrast grain (`fine_period`, weight `fine`) and a large-scale figure
    (+-`figure` brightness) break the panels up. Satin finish, roughness
    following the grain. Keep both periods at medium scale and the contrast
    low: fine high-contrast grain shimmers in VR.
    Returns (base, rough, height in meters)."""
    def wave(p, dist, direction, detail_scale, detail=3.0):
        s = g.wave(2 * math.pi / (20.0 * p), dist, detail, direction)
        node = s.node
        node.inputs["Detail Scale"].default_value = detail_scale
        node.inputs["Detail Roughness"].default_value = 0.6
        return s

    front = g.maprange(g.math("ABSOLUTE", g.ny), 0.5, 0.8)
    # Distortion in radians: 20 rad at 28 mm bands warps the lines by ~9 cm at 0.6 m scale
    # (cathedral figure); the finer octaves vary the band widths by about 2x.
    bands = g.mixf(front, wave(period, distortion, "Y", 0.15), wave(period, distortion, "X", 0.15))
    fine_g = g.mixf(front, wave(fine_period, 2.0, "Y", 0.08, 1.0), wave(fine_period, 2.0, "X", 0.08, 1.0))
    lines = g.maprange(bands, 0.62, 0.98)                     # thin, soft-edged latewood lines
    grain = g.add(g.mul(lines, line_strength), g.mul(g.sub(fine_g, 0.5), fine))
    fig = g.sub(g.noise(0.9, 2.0, 0.5), 0.5)
    mottle = g.sub(g.noise(18.0, 2.0, 0.5), 0.5)
    base = g.mixc(grain, ground, line)
    base = g.scale_color(base, g.add(1.0, g.add(g.mul(fig, 2 * figure), g.mul(mottle, 0.08))))
    r = g.add(rough, g.add(g.mul(lines, 0.05), g.mul(mottle, 0.04)))
    height = g.mul(grain, pores)
    return base, r, height


def brushed_metal(g, color, rough=0.38, streak=0.16, along=(60.0, 60.0, 2.0), relief=0.0004):
    """Brushed metal: roughness streaks from a noise stretched along the brush
    direction (`along` scales world x, y, z; small = long streaks), a faint
    relief, metallic 1. Returns (base, rough, height in meters)."""
    b = g.sub(g.noise(1.0, 3.0, 0.7, vector=g.vec(*along)), 0.5)
    fine = g.sub(g.noise(9.0, 2.0, 0.5), 0.5)
    r = g.add(rough, g.add(g.mul(b, 2 * streak), g.mul(fine, 0.06)))
    height = g.mul(b, relief)
    return color, r, height


# ---------------------------------------------------------------------------
# wear
# ---------------------------------------------------------------------------
def scratch(g, base, rough, start, end, width=0.0015, color=(0.30, 0.22, 0.15), rougher=0.30,
            facing=None):
    """A thin straight scratch on a -Y facing face between two world (x, z)
    points, exposing `color` under the finish. `facing` masks the face (default:
    normals toward -Y). Returns (base, rough)."""
    sx, sz = start
    dx, dz = end[0] - sx, end[1] - sz
    length = math.hypot(dx, dz)
    ux, uz = dx / length, dz / length
    rx, rz = g.sub(g.x, sx), g.sub(g.z, sz)
    along = g.add(g.mul(rx, ux), g.mul(rz, uz))
    across = g.sub(g.mul(rz, ux), g.mul(rx, uz))
    if facing is None:
        facing = g.maprange(g.ny, -0.5, -0.8)
    m = g.mul(g.mul(g.band(along, 0.0, length, 0.004), g.band(across, -width / 2, width / 2, width / 2)),
              facing)
    base = g.mixc(m, base, color)
    rough = g.add(rough, g.mul(m, rougher))
    return base, rough
