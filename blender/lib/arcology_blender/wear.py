"""Wear layers for `Graph` materials. Each takes and returns (base, rough) or base.

The style guide asks for wear everywhere: edges catch light, bottoms get
scuffed, tops get dusty, handles get smudged. Keep features at medium scale;
fine high-contrast grain shimmers in VR. Heights are world z in meters.
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


def bottom_scuffs(g, base, rough, z_clean=0.26, z_full=0.10, rougher=0.35, darker=0.30):
    """Horizontal kick scuffs, fading in below z_clean and full at z_full."""
    low = g.maprange(g.z, z_clean, z_full)
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
