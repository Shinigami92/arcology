"""Library candidates from the wardrobe (Fable 5.1, A/B winner).

Generic, asset-agnostic helpers written like `arcology_blender` code so they
can be promoted. Nothing here knows the wardrobe's dimensions.

geo candidates        arc_points, round_polyline, bm_tube, bm_tapered_cyl, bm_open_box, linked_copy
soft candidates       wire_hanger, hanging_garment
materials candidates  wood_veneer, brushed_metal
wear candidates       scratch, fixture_wear
"""

import math

import bmesh
import bpy
from mathutils import Vector

from arcology_blender import soft


# ---------------------------------------------------------------------------
# geo candidates
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


def round_polyline(points, radius, steps=4, closed=False, min_turn=25.0):
    """Fillet the corners of a polyline: every corner turning by more than
    `min_turn` degrees becomes `steps` points on an arc of `radius` (clamped so
    the fillet never eats more than half of a neighboring segment)."""
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


def bm_tapered_cyl(bm, r_bottom, r_top, depth, matrix, segments=24):
    """Capped cone frustum along the matrix's Z axis (furniture legs, spikes)."""
    return bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=r_bottom, radius2=r_top, depth=depth, matrix=matrix,
    )["verts"]


def bm_open_box(bm, lo, hi, wall, floor=None, open_axis=2):
    """Open-top box (drawer, tray, bin) as five slabs: a floor `floor` thick
    (default `wall`) and four walls `wall` thick, between corners `lo` and
    `hi`; the open face is the +side of `open_axis`. Watertight slabs that
    share faces, meant for `finish` (bevel) afterwards."""
    from arcology_blender.geo import bm_box
    lo, hi = Vector(lo), Vector(hi)
    f = wall if floor is None else floor
    a, b = [i for i in range(3) if i != open_axis]
    up = open_axis

    def corner(**kw):
        v = Vector((0.0, 0.0, 0.0))
        for k, val in kw.items():
            v[k] = val
        return v

    # floor
    flo, fhi = lo.copy(), hi.copy()
    fhi[up] = lo[up] + f
    bm_box(bm, flo, fhi)
    # walls along axis a (perpendicular to b) and along b
    for axis in (a, b):
        for side in (0, 1):
            wlo, whi = lo.copy(), hi.copy()
            wlo[up] = lo[up] + f
            if side == 0:
                whi[axis] = lo[axis] + wall
            else:
                wlo[axis] = hi[axis] - wall
            if axis == b:  # shorten so the corners don't double up
                wlo[a] += wall
                whi[a] -= wall
            bm_box(bm, wlo, whi)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)


def linked_copy(ob, name, collection, location, rotation=(0.0, 0.0, 0.0), parent=None):
    """Another instance of a mesh object sharing its mesh data (same UVs and
    baked material), placed at `location`. Bake the original once; export it
    once; instance it in Godot."""
    dup = bpy.data.objects.new(name, ob.data)
    dup.location = location
    dup.rotation_euler = rotation
    dup.parent = parent
    collection.objects.link(dup)
    return dup


# ---------------------------------------------------------------------------
# soft candidates
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


def hanging_garment(width=0.42, length=0.68, thick=0.04, shoulder_drop=0.05, taper=0.12,
                    step=(0.04, 0.02, 0.05), drape=0.008, drape_period=0.13, folds=0.003, seed=0.0):
    """A shirt or jacket on a hanger as a new bmesh: a soft slab in the XZ
    plane (panels face +-Y, shoulders along X) with sloping shoulders, thinner
    and narrower toward the hem, vertical drape folds (`drape` amplitude,
    `drape_period` across) that grow toward the hem, and low-frequency
    wrinkles. The shoulder line is z = 0 at the neck, the hanger plane y = 0;
    move it into place with bmesh.ops.translate."""
    bm = soft.soft_box((0.0, 0.0, -length / 2), (width, thick, length), min(0.015, thick * 0.45),
                       step=step, panel_axis=1)
    for v in bm.verts:
        x, z = v.co.x, v.co.z
        d = max(0.0, min(1.0, -z / length))            # 0 at the shoulders, 1 at the hem
        top = max(0.0, min(1.0, 1.0 + z / 0.30))        # 1 at the shoulders, 0 from 30 cm down
        v.co.z -= shoulder_drop * (abs(x) / (width / 2)) * top
        v.co.y *= 1.0 - 0.55 * d
        v.co.x *= 1.0 - taper * d
        v.co.y += drape * (0.25 + 0.75 * d) * math.sin(x * 2 * math.pi / drape_period + seed * 1.7)
    if folds:
        soft.jitter(bm, folds, 7.0, seed)
    bm.normal_update()
    return bm


# ---------------------------------------------------------------------------
# materials candidates (Graph layers; return values like the fabric module)
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
# wear candidates
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


def fixture_wear(g, base, rough, points, r_in=0.02, r_out=0.06, rougher=0.15, lighter=0.10,
                 facing=None):
    """Worn finish around fixtures on a -Y facing face (handle standoffs, knobs):
    a broken-up halo around each world (x, z) point, rougher and lighter (the
    satin coat rubbed through by hands). Returns (base, rough)."""
    if facing is None:
        facing = g.maprange(g.ny, -0.5, -0.8)
    breakup = g.maprange(g.noise(30.0, 3.0, 0.6), 0.35, 0.75)
    m = 0.0
    for px, pz in points:
        dx, dz = g.sub(g.x, px), g.sub(g.z, pz)
        d = g.math("SQRT", g.add(g.mul(dx, dx), g.mul(dz, dz)))
        m = g.add(m, g.maprange(d, r_out, r_in))
    m = g.mul(g.mul(g.math("MINIMUM", m, 1.0), breakup), facing)
    rough = g.add(rough, g.mul(m, rougher))
    base = g.scale_color(base, g.add(1.0, g.mul(m, lighter)))
    return base, rough
