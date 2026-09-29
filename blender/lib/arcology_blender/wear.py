"""Wear layers for `Graph` materials. Each takes and returns (base, rough) or base.

The style guide asks for wear everywhere: edges catch light, bottoms get
scuffed, tops get dusty, handles get smudged. Keep features at medium scale;
fine high-contrast grain shimmers in VR. Heights are world z in meters.

Edge masks: `edge_highlight` uses Cycles pointiness, which needs vertex
density (bevels, soft goods); on sparse boxes (a board with vertices only at
its corners) pointiness is a face-wide gradient, so use `bevel_edges` /
`convex_edges` (raytraced Bevel node) and `edge_wear` there.
"""


def edge_highlight(g, base, rough, lo=0.52, hi=0.64, smoother=0.10, brighter=0.12):
    """Worn, brighter and smoother convex edges (Cycles pointiness)."""
    edge = g.maprange(g.pointiness(), lo, hi)
    rough = g.sub(rough, g.mul(edge, smoother))
    base = g.scale_color(base, g.add(1.0, g.mul(edge, brighter)))
    return base, rough


def smudges(g, base, rough, region, rougher=0.22, darker=0.06):
    """Fingerprint haze inside a 0..1 mask (e.g. a rect_xz around a handle)."""
    fp = g.mul(region, g.mul(g.maprange(g.noise(45.0, 5.0, 0.7), 0.50, 0.58),
                             g.maprange(g.noise(7.0, 2.0), 0.40, 0.62)))
    rough = g.add(rough, g.mul(fp, rougher))
    base = g.scale_color(base, g.sub(1.0, g.mul(fp, darker)))
    return base, rough


def bottom_scuffs(g, base, rough, z_clean=0.26, z_full=0.10, rougher=0.35, darker=0.30, mask=None):
    """Horizontal kick scuffs, fading in below z_clean and full at z_full;
    `mask` (0..1) limits them, e.g. to the door fronts."""
    low = g.maprange(g.z, z_clean, z_full)
    if mask is not None:
        low = g.mul(low, mask)
    scuff = g.mul(low, g.maprange(g.noise(1.0, 3.0, 0.6, g.vec(5.0, 5.0, 90.0)), 0.52, 0.66))
    rough = g.add(rough, g.mul(scuff, rougher))
    base = g.scale_color(base, g.sub(1.0, g.mul(scuff, darker)))
    return base, rough


def floor_grime(g, base, z0=0.0, z1=0.10, darkest=0.78):
    """Darkening toward the floor (darkest at z0, clean from z1)."""
    return g.scale_color(base, g.maprange(g.z, z0, z1, darkest, 1.0))


def top_dust(g, base, rough, z0, z1, color=(0.62, 0.60, 0.57), amount=0.35, rougher=0.30):
    """Dust on upward-facing surfaces, fading in from z0 to z1."""
    dust = g.mul(g.mul(g.maprange(g.nz, 0.8, 0.95), g.maprange(g.z, z0, z1)),
                 g.maprange(g.noise(12.0, 2.0), 0.3, 0.7))
    rough = g.add(rough, g.mul(dust, rougher))
    base = g.mixc(g.mul(dust, amount), base, color)
    return base, rough


def low_grime(g, base, rough, z_clean, z_full, color, amount=0.5, rougher=0.2):
    """Patchy grime collecting low in a compartment (none above z_clean, most at z_full)."""
    grime = g.mul(g.maprange(g.z, z_clean, z_full), g.maprange(g.noise(9.0, 2.0), 0.3, 0.7))
    base = g.mixc(g.mul(grime, amount), base, color)
    rough = g.add(rough, g.mul(grime, rougher))
    return base, rough


# --- edge masks (raytraced; work on sparse box geometry) -------------------------
def bevel_edges(g, radius=0.003, lo=0.03, hi=0.25, samples=16):
    """0..1 mask on geometric edges (convex and concave) from Cycles' Bevel node:
    1 - dot(rounded normal, shading normal), remapped lo..hi. Works on sparse
    box geometry where pointiness only gives face-wide gradients. Raytraced,
    so it bakes (slightly noisy at 1 sample; keep lo/hi soft)."""
    bev = g.nodes.new("ShaderNodeBevel")
    bev.samples = samples
    bev.inputs["Radius"].default_value = radius
    dot = g.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    g.links.new(bev.outputs["Normal"], dot.inputs[0])
    g.links.new(g.geo.outputs["Normal"], dot.inputs[1])
    return g.maprange(g.sub(1.0, dot.outputs["Value"]), lo, hi)


def convex_edges(g, radius=0.003, lo=0.03, hi=0.25, ao_distance=0.01, samples=16):
    """`bevel_edges` restricted to convex edges (outer corners that wear):
    concave corners are rejected by a short-range local AO test."""
    ao = g.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = samples
    ao.only_local = True
    ao.inputs["Distance"].default_value = ao_distance
    open_ = g.maprange(ao.outputs["AO"], 0.75, 0.95)
    return g.mul(bevel_edges(g, radius, lo, hi, samples), open_)


def edge_wear(g, base, rough, edge, mask, color, amount=0.4, rough_delta=-0.08):
    """Edges (a 0..1 `edge` mask, e.g. bevel_edges) inside a 0..1 `mask` shift
    toward `color` by `amount` and change roughness by rough_delta (negative:
    polished by hands, positive: worn matte)."""
    e = g.mul(edge, mask)
    base = g.mixc(g.mul(e, amount), base, color)
    rough = g.add(rough, g.mul(e, rough_delta))
    return base, rough


# --- marks ------------------------------------------------------------------------
def cup_ring(g, base, rough, center, radius, width=0.0025, z_band=(0.0, 10.0), strength=0.35,
             haze=(0.16, 0.13, 0.105), duller=0.22, broken=0.5, second=(0.011, -0.006, 0.6)):
    """Water/coffee ring left by a mug on a finished top: a thin, broken ring
    around world `center` (x, y) on upward-facing faces at world z within
    z_band, where the finish turned hazy (lighter, grayer) and dull.
    `second` = (dx, dy, fraction): a fainter offset ring from another time
    (fraction 0 for none). Returns (base, rough)."""
    cx, cy = center[0], center[1]
    up = g.mul(g.maprange(g.nz, 0.8, 0.95), g.band(g.z, z_band[0], z_band[1], 0.002))

    def ring(x, y, amount):
        d = g.add(g.dist_xy(x, y), g.mul(g.sub(g.noise(35.0, 2.0), 0.5), width * 1.2))
        rim = g.band(d, radius - width, radius, width * 0.5)
        inner = g.mul(g.maprange(d, radius, radius * 0.85), 0.12)
        gaps = g.maprange(g.noise(18.0, 2.0), 0.35 * broken, 0.35 * broken + 0.2)
        return g.mul(g.add(g.mul(rim, gaps), inner), amount)

    m = g.mul(up, g.math("MAXIMUM", ring(cx, cy, 1.0), ring(cx + second[0], cy + second[1], second[2])))
    base = g.mixc(g.mul(m, strength), base, haze)
    rough = g.add(rough, g.mul(m, duller))
    return base, rough


def scratch(g, base, rough, height, p0, p1, width=0.0012, mask=1.0, color=(0.26, 0.19, 0.13),
            amount=0.8, rougher=0.25, depth=0.00008, wobble=0.5):
    """A thin straight scratch on a front- or back-facing surface, from world
    (x, z) p0 to p1, tapering to the ends and wobbling by `wobble` x width.
    Scratched lacquer turns lighter and duller. mask limits it (e.g. to a
    door front, `g.maprange(g.y, ...)`). Returns (base, rough, height)."""
    x0, z0 = p0
    ex, ez = p1[0] - x0, p1[1] - z0
    l2 = ex * ex + ez * ez
    dx, dz = g.sub(g.x, x0), g.sub(g.z, z0)
    t = g.math("MINIMUM", g.math("MAXIMUM", g.mul(g.add(g.mul(dx, ex), g.mul(dz, ez)), 1.0 / l2), 0.0), 1.0)
    qx, qz = g.sub(dx, g.mul(t, ex)), g.sub(dz, g.mul(t, ez))
    d = g.math("SQRT", g.add(g.mul(qx, qx), g.mul(qz, qz)))
    d = g.add(d, g.mul(g.sub(g.noise(260.0, 2.0), 0.5), width * wobble))
    tt = g.sub(g.mul(t, 2.0), 1.0)
    w = g.mul(g.sub(1.0, g.mul(tt, tt)), width)  # widest in the middle
    s = g.mul(g.math("GREATER_THAN", w, 0.00005), g.maprange(g.math("DIVIDE", d, g.add(w, 1e-6)), 1.0, 0.35))
    s = g.mul(s, mask)
    base = g.mixc(g.mul(s, amount), base, color)
    rough = g.add(rough, g.mul(s, rougher))
    height = g.sub(height, g.mul(s, depth))
    return base, rough, height


def fixture_wear(g, base, rough, points, r_in=0.02, r_out=0.06, rougher=0.15, lighter=0.10,
                 facing=None):
    """Worn finish around fixtures on a -Y facing face (handle standoffs, knobs):
    a broken-up halo around each world (x, z) point, rougher and lighter (the
    satin coat rubbed through by hands). `facing` masks the face (default:
    normals toward -Y). Returns (base, rough)."""
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


def rubbed_finish(g, base, rough, mask, lighter=0.14, rougher=0.28):
    """A finish worn through by hands inside a 0..1 mask (around a pull, a
    chair's arm): the wood shows lighter and matte, with a mottled breakup."""
    fac = g.mul(mask, g.maprange(g.noise(18.0, 3.0, 0.6), 0.35, 0.65))
    base = g.scale_color(base, g.add(1.0, g.mul(fac, lighter)))
    rough = g.add(rough, g.mul(fac, rougher))
    return base, rough
