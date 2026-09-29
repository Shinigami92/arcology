"""Candidate library code from the bed A/B (Fable 5.1). Nothing here knows the bed.

Written as if it lived in `arcology_blender`, so the winner's helpers can be
promoted without edits: `drape`, `shell_rim`, `ridge` and `lumps` belong in
`soft`; `wood_veneer`, `brushed_metal`, `wool_knit` in `materials`; `quilting`
in `fabric`; `wave_at` on `Graph`.

Geometry
    drape        a cloth sheet lying on a rounded rectangle and hanging over
                 chosen edges (duvet on a mattress, throw over an arm,
                 tablecloth), with vertical folds in the hanging parts and a
                 rolled rim of the cloth's thickness
    shell_rim    close an open surface's boundary with a rounded rim of quads
    ridge        a soft fold ridge along a segment (for height callbacks)
    lumps        low-frequency filling lumps (for height callbacks)
    smoothstep   Hermite 0..1 ramp

Materials (procedural, baked)
    wood_veneer    walnut-like veneer with 3D growth rings around a grain axis
    brushed_metal  metallic satin finish with brushing streaks along an axis
    wool_knit      chunky-knit wool throw (returns the graph for asset wear)
    quilting       stitched channel lines every `spacing` meters on a fabric
"""

import math

import bmesh
from mathutils import Vector, noise

from arcology_blender import fabric, wear
from arcology_blender.shading import Graph, new_mat

# --- small math ------------------------------------------------------------------


def smoothstep(x, a, b):
    """0 below a, 1 above b, Hermite in between."""
    if b == a:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def ridge(x, y, a, b, amp, width, taper=0.15):
    """Height of a soft fold ridge along the segment a-b (world x/y): a Gaussian
    of `amp` meters and `width` (1/e half width) across the line, fading over
    `taper` meters at both ends. Negative amp is a furrow."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return 0.0
    t = ((x - ax) * dx + (y - ay) * dy) / l2
    tc = max(0.0, min(1.0, t))
    dist = math.hypot(x - (ax + tc * dx), y - (ay + tc * dy))
    length = math.sqrt(l2)
    end = smoothstep(min(t * length, (1.0 - t) * length), 0.0, taper)
    return amp * math.exp(-(dist / width) ** 2) * end


def lumps(x, y, amp, scale, seed=0.0, octaves=2):
    """Filling lumps for a height callback: Perlin noise at `scale` features per
    meter, +-amp meters, with a half-amplitude octave at twice the frequency."""
    p = Vector((x * scale, y * scale, seed))
    h = noise.noise(p)
    if octaves > 1:
        h += 0.5 * noise.noise(p * 2.1 + Vector((3.7, 1.3, 9.1)))
    return amp * h


# --- cloth --------------------------------------------------------------------------

RIM_PROFILE = ((0.42, 0.28), (0.42, 0.78), (-0.25, 1.0))


def shell_rim(bm, loop, inward, thickness, profile=RIM_PROFILE):
    """Close the boundary of an open surface with a rounded rim: `loop` is the
    boundary vertices in order (counter-clockwise seen from the surface's
    front), `inward` the interior neighbor of each (for the tangent). Each
    profile point (out, down) is in units of `thickness`: out along the
    surface away from the interior, down along the negative normal. Returns
    the new faces. The default profile is a half-round edge that turns
    under, like the hem of a duvet."""
    n = len(loop)
    rings = []
    for v, vin in zip(loop, inward):
        nrm = v.normal.copy()
        t_in = vin.co - v.co
        t_in -= nrm * t_in.dot(nrm)
        if t_in.length < 1e-9:
            t_in = Vector((1.0, 0.0, 0.0))
        t_in.normalize()
        out = -t_in
        ring = [v]
        for o, d in profile:
            ring.append(bm.verts.new(v.co + out * (o * thickness) - nrm * (d * thickness)))
        rings.append(ring)
    faces = []
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for s in range(len(a) - 1):
            faces.append(bm.faces.new([a[s], a[s + 1], b[s + 1], b[s]]))
    return faces


def _rrect(u, v, rect, rc):
    """Rounded rectangle helper: for a point (u, v) return (d, b, n, s):
    signed distance to the boundary (> 0 outside), the closest boundary point,
    the outward normal there and the perimeter coordinate s (meters,
    counter-clockwise from the start of the -y side). b, n, s are None inside."""
    x0, y0, x1, y1 = rect
    ix0, ix1, iy0, iy1 = x0 + rc, x1 - rc, y0 + rc, y1 - rc
    qx, qy = min(max(u, ix0), ix1), min(max(v, iy0), iy1)
    dx, dy = u - qx, v - qy
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return -min(u - x0, x1 - u, v - y0, y1 - v), None, None, None
    nx, ny = dx / length, dy / length
    wi, hi, arc = ix1 - ix0, iy1 - iy0, rc * math.pi / 2
    if dy < 0 and dx == 0:
        s = qx - ix0
    elif dx > 0 and dy == 0:
        s = wi + arc + (qy - iy0)
    elif dy > 0 and dx == 0:
        s = wi + 2 * arc + hi + (ix1 - qx)
    elif dx < 0 and dy == 0:
        s = 2 * wi + 3 * arc + hi + (iy1 - qy)
    else:
        th = math.atan2(dy, dx)
        if dx > 0 and dy < 0:
            s = wi + (th + math.pi / 2) * rc
        elif dx > 0 and dy > 0:
            s = wi + arc + hi + th * rc
        elif dx < 0 and dy > 0:
            s = 2 * wi + 2 * arc + hi + (th - math.pi / 2) * rc
        else:
            s = 2 * wi + 3 * arc + 2 * hi + (th + math.pi) * rc
    return length - rc, (qx + nx * rc, qy + ny * rc), (nx, ny), s


def _perimeter(rect, rc):
    x0, y0, x1, y1 = rect
    return 2 * (x1 - x0 - 2 * rc) + 2 * (y1 - y0 - 2 * rc) + 2 * math.pi * rc


def _axis_coords(lo, hi, ov_lo, ov_hi, r_lo, r_hi, res):
    """Cloth coordinates along one axis: uniform over the top, 4 steps over
    each roll, then ~0.8 res steps down the hang."""
    n = max(1, int(round((hi - lo) / res)))
    inner = [lo + (hi - lo) * i / n for i in range(n + 1)]

    def ext(ov, r):
        if ov <= 1e-9:
            return []
        arc = r * math.pi / 2
        a = min(ov, arc)
        pts = [a * j / 4 for j in range(1, 5)] if a > 0 else []
        if ov > arc + 1e-6:
            m = max(1, int(round((ov - arc) / (res * 0.8))))
            pts += [arc + (ov - arc) * j / m for j in range(1, m + 1)]
        return pts

    return [lo - d for d in reversed(ext(ov_lo, r_lo))] + inner + [hi + d for d in ext(ov_hi, r_hi)]


def _soft_clamp(t):
    """t for t <= 0.85, then saturating toward ~1.12 (a cloth corner hangs a
    little lower than the sides but doesn't reach the floor)."""
    if t <= 0.85:
        return t
    return 0.85 + 0.27 * math.tanh((t - 0.85) / 0.27)


def drape(rect, top_z, overhang, thickness, res=0.03, radius=0.04, corner_radius=0.08,
          fold_amp=0.010, fold_period=0.18, hem_wave=0.006, flare=0.05, seed=0.0, rim_profile=RIM_PROFILE):
    """Cloth sheet lying on a rounded rectangle and hanging over its edges, as
    a new bmesh (world coordinates): a duvet on a mattress, a throw over an
    arm, a tablecloth.

    rect: (x0, y0, x1, y1), the covered top (a mattress top; corners rounded
    by corner_radius so the hanging cloth turns the corner instead of
    stretching). top_z(x, y): height of the cloth's top surface over the top
    region, including the cloth's thickness and any rumples (see `ridge`,
    `lumps`). overhang: {"-x": m, "+x": m, "-y": m, "+y": m}, cloth length
    past each edge (missing = 0: the cloth ends at that edge); radius: roll
    radius at the edges, a float or the same kind of dict (a fold-back edge
    gets a fatter roll). The hanging cloth gets vertical folds (fold_amp
    meters, fold_period meters along the edge, growing toward the hem), a
    wavy hem (+-hem_wave) and flares outward by `flare` meters per meter of
    drop. Cloth corners hang up to ~12% lower than the sides. The boundary is
    closed with `shell_rim` (thickness, rim_profile). Quads of about `res`.
    """
    x0, y0, x1, y1 = rect
    ov = {k: overhang.get(k, 0.0) for k in ("-x", "+x", "-y", "+y")}
    rad = {k: (radius.get(k, 0.04) if isinstance(radius, dict) else radius) for k in ov}
    us = _axis_coords(x0, x1, ov["-x"], ov["+x"], rad["-x"], rad["+x"], res)
    vs = _axis_coords(y0, y1, ov["-y"], ov["+y"], rad["-y"], rad["+y"], res)
    per = _perimeter(rect, corner_radius)
    k1 = max(1, int(round(per / fold_period)))
    k2 = max(1, int(round(per / (fold_period * 2.7))))
    ph1, ph2 = seed * 2.39, seed * 1.17 + 0.8

    def blend(d, n):
        """Per-side values blended by the outward normal."""
        wx, wy = abs(n[0]), abs(n[1])
        kx, ky = ("+x" if n[0] > 0 else "-x"), ("+y" if n[1] > 0 else "-y")
        return (wx * d[kx] + wy * d[ky]) / max(wx + wy, 1e-9)

    def point(u, v):
        d, b, n, s = _rrect(u, v, rect, corner_radius)
        if d <= 0.0:
            return Vector((u, v, top_z(u, v)))
        r = blend(rad, n)
        total = blend(ov, n)
        arc = r * math.pi / 2
        ztop = top_z(b[0], b[1])
        nv = Vector((n[0], n[1], 0.0))
        base = Vector((b[0], b[1], 0.0))
        max_drop = max(total - arc, 1e-6)
        if d < arc:
            a = d / r
            p = base + nv * (r * math.sin(a))
            p.z = ztop - r * (1.0 - math.cos(a))
            drop = 0.0
        else:
            drop = max_drop * _soft_clamp((d - arc) / max_drop)
            p = base + nv * (r + flare * drop)
            p.z = ztop - r - drop
        prog = min(1.0, d / max(total, 1e-6)) ** 1.5
        if fold_amp and total > arc:
            amp_mod = 0.6 + 0.4 * noise.noise(Vector((s * 2.0, seed, 0.0)))
            f = (math.sin(2 * math.pi * k1 * s / per + ph1)
                 + 0.5 * math.sin(2 * math.pi * k2 * s / per + ph2))
            p += nv * (fold_amp * amp_mod * prog * f)
        if hem_wave and drop > 0:
            p.z -= hem_wave * (drop / max_drop) * (0.5 + 0.5 * math.sin(2 * math.pi * k2 * s / per + ph2 * 1.7))
        return p

    bm = bmesh.new()
    grid = [[bm.verts.new(point(u, v)) for v in vs] for u in us]
    nu, nv_ = len(us), len(vs)
    for i in range(nu - 1):
        for j in range(nv_ - 1):
            bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    bm.normal_update()
    loop_idx = ([(i, 0) for i in range(nu - 1)] + [(nu - 1, j) for j in range(nv_ - 1)]
                + [(i, nv_ - 1) for i in range(nu - 1, 0, -1)] + [(0, j) for j in range(nv_ - 1, 0, -1)])

    def inward(i, j):
        ii = 1 if i == 0 else (nu - 2 if i == nu - 1 else i)
        jj = 1 if j == 0 else (nv_ - 2 if j == nv_ - 1 else j)
        return grid[ii][jj]

    shell_rim(bm, [grid[i][j] for i, j in loop_idx], [inward(i, j) for i, j in loop_idx], thickness, rim_profile)
    bm.normal_update()
    return bm


# --- material helpers -----------------------------------------------------------------


def wave_at(g, scale, distortion, detail=2.0, wave_type="RINGS", direction="X", vector=None):
    """Wave texture on `Graph` g with a choice of type (BANDS/RINGS), direction
    and input vector (default: world position). Rings around an axis are
    what a 3D wood needs: growth rings stay consistent across all faces."""
    n = g.nodes.new("ShaderNodeTexWave")
    n.wave_type = wave_type
    if wave_type == "RINGS":
        n.rings_direction = direction
    else:
        n.bands_direction = direction
    n.inputs["Scale"].default_value = scale
    n.inputs["Distortion"].default_value = distortion
    n.inputs["Detail"].default_value = detail
    g.links.new(vector if vector is not None else g.geo.outputs["Position"], n.inputs["Vector"])
    return n.outputs["Fac"]


def offset_pos(g, offset):
    """World position shifted by `offset` (a vector socket for textures whose
    axis should sit elsewhere, e.g. a log's core behind a panel)."""
    n = g.nodes.new("ShaderNodeVectorMath")
    n.operation = "ADD"
    g.links.new(g.geo.outputs["Position"], n.inputs[0])
    n.inputs[1].default_value = offset
    return n.outputs[0]


def wood_veneer(name, base=(0.052, 0.025, 0.013), grain="X", axis_offset=(0.0, 0.0, 0.0), rough=0.50,
                ring_scale=16.0, ring_distortion=1.4, contrast=0.28, figure=0.12, pores=0.00008):
    """Satin-finished hardwood veneer (walnut by default) as a `src_<name>`
    material. Growth rings are concentric around the world axis `grain`
    ("X"/"Y"/"Z"), so every face of a board shows rings crossing it the right
    way; period ~0.31/ring_scale meters at the axis' distance (keep it over
    2 cm: finer rings shimmer in VR). axis_offset is added to the position:
    put the axis (where the two other coordinates are 0 after the offset)
    about a meter outside the board, beside its widest face, so the radius
    changes across the face and the rings become nearly straight lines; an
    axis in the plane of a face makes it show one ring 10 cm wide. contrast
    darkens the latewood bands, figure adds broad flitch-to-flitch color
    variation, pores are fine streaks along the grain in the normal map.
    Returns (g, base, rough, height): finish with
    `g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))` after adding wear."""
    g = Graph(new_mat(f"src_{name}"))
    pos = offset_pos(g, axis_offset)
    rings = wave_at(g, ring_scale, ring_distortion, 2.0, "RINGS", grain, pos)
    late = g.maprange(rings, 0.40, 0.90)
    stretch = {"X": (1.5, 110.0, 110.0), "Y": (110.0, 1.5, 110.0), "Z": (110.0, 110.0, 1.5)}[grain]
    pore = g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vec(*stretch)), 0.5)
    flitch = g.sub(g.noise(1.6, 2.0, 0.5), 0.5)
    f = g.add(g.sub(1.0, g.mul(late, contrast)), g.add(g.mul(flitch, 2 * figure), g.mul(pore, 0.14)))
    col = g.scale_color(base, f)
    r = g.add(rough, g.add(g.mul(late, 0.05), g.mul(pore, 0.06)))
    height = g.add(g.mul(pore, pores), g.mul(late, pores * 0.5))
    col, r = wear.edge_highlight(g, col, r, brighter=0.12, smoother=0.06)
    return g, col, r, height


def brushed_metal(name, base=(0.028, 0.033, 0.040), rough=0.36, along="Z", streak=0.10, metallic=1.0,
                  edge_brighter=0.5):
    """Brushed or powder-coated metal (gunmetal by default): metallic, satin,
    brushing streaks along world axis `along` in roughness and a faint
    height, worn lighter edges. Returns the finished `src_<name>` material."""
    g = Graph(new_mat(f"src_{name}"))
    sv = {"X": (1.5, 220.0, 220.0), "Y": (220.0, 1.5, 220.0), "Z": (220.0, 220.0, 1.5)}[along]
    streaks = g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vec(*sv)), 0.5)
    r = g.add(rough, g.add(g.mul(streaks, 2 * streak), g.mul(g.sub(g.noise(8.0), 0.5), 0.06)))
    col, r = wear.edge_highlight(g, base, r, brighter=edge_brighter, smoother=0.12)
    return g.finish(col, r, metallic, g.bump(g.mul(streaks, 0.00015), 1.0, 1.0))


def wool_knit(name, color, rough=0.95, rib_period=0.013, rib_height=0.0005, rib_direction="Y", fuzz=0.35):
    """Chunky-knit wool (throws, blankets): heathered yarn color, soft knit
    ribs running perpendicular to `rib_direction` (bands vary along that
    world axis), fuzz pills, very rough. Returns (g, base, rough, height)."""
    g = Graph(new_mat(f"src_{name}"))
    base, r, h = fabric.fabric_base(g, color, rough=rough, heather=0.07, slub=0.03, mottle=0.06, weave=0.00010)
    ribs = wave_at(g, 0.314 / rib_period, 1.2, 1.0, "BANDS", rib_direction)
    h = g.add(h, g.mul(ribs, rib_height))
    base = g.scale_color(base, g.add(0.95, g.mul(ribs, 0.10)))
    base, h = fabric.pilling(g, base, h, fuzz, scale=110.0, amount=0.0004, lighter=0.06)
    return g, base, r, h


def quilting(g, base, height, spacing, mask, width=0.010, depth=0.0012, darker=0.03, puff=0.003, axes="XY"):
    """Stitched quilt channels every `spacing` meters along the world axes in
    `axes` (a duvet's baffle boxes), inside a 0..1 mask: a soft valley of
    `depth` with a slightly darker stitch line, and each box puffed up by
    `puff` meters at its center. Lines along an axis only show on faces
    roughly perpendicular to it, so they don't smear down the sides.
    Returns (base, height)."""
    hw = width / spacing / 2
    lines, bulge = 0.0, 1.0
    for ax in axes:
        coord, ncomp = {"X": (g.x, g.nx), "Y": (g.y, g.ny)}[ax]
        t = g.math("FRACT", g.mul(coord, 1.0 / spacing))
        facing = g.maprange(g.math("ABSOLUTE", ncomp), 0.7, 0.3)
        lines = g.add(lines, g.mul(g.band(t, 0.5 - hw, 0.5 + hw, hw), facing))
        # 1 at the box center, 0 at the seams (t = 0.5); flat where the axis' lines don't show
        arch = g.math("SINE", g.mul(g.sub(t, 0.5), math.pi))
        arch = g.math("ABSOLUTE", arch)
        bulge = g.mul(bulge, g.mixf(facing, 1.0, arch))
    lines = g.mul(g.maprange(lines, 0.0, 1.0), mask)
    height = g.add(g.sub(height, g.mul(lines, depth)), g.mul(g.mul(bulge, mask), puff))
    base = g.scale_color(base, g.sub(1.0, g.mul(lines, darker)))
    return base, height
