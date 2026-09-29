"""Upholstery fabric layers for `Graph` materials (D-028).

Promoted from the sofa A/B (Opus 5.5 won). Heights accumulate in meters and
become one normal in `fabric_finish` (Bump distance 1.0), so each layer's
depth is physical. Typical order: fabric_base, welt, creases, rub, pilling,
stain, fabric_finish. Keep detail at medium scale and low contrast: a fine,
high-contrast weave shimmers in VR, and ~512 px/m can't hold it anyway.

Also: `quilting` (stitched baffle channels, e.g. a duvet) and `wool_knit`
(a chunky-knit throw) from the padded bed, `braided_cord` (textile cable on
a `curves.tube`) from the nightstand.
"""

import math

from .shading import Graph, new_mat
from .soft import SEAM_ATTR


def fabric_base(g, color, rough=0.90, heather=0.05, slub=0.04, mottle=0.07, weave=0.00022,
                slub_height=0.00012, mottle_height=0.00006):
    """Woven upholstery: medium-scale heathering (a few cm, +-heather), yarn
    slubs stretched along world X (+-slub), a two-tone yarn mottle at about
    1 cm (+-mottle; the finest color detail that survives mipmapping without
    shimmer) and a soft, low weave relief. Keep rough high (0.88-0.95):
    lower values read as leather or vinyl. Returns (base, rough, height in m)."""
    h = g.sub(g.noise(9.0, 3.0, 0.55), 0.5)
    s = g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vec(30.0, 150.0, 150.0)), 0.5)
    m = g.sub(g.maprange(g.noise(95.0, 2.0, 0.6), 0.35, 0.65), 0.5)
    f = g.add(1.0, g.add(g.add(g.mul(h, 2 * heather), g.mul(s, 2 * slub)), g.mul(m, 2 * mottle)))
    base = g.scale_color(color, f)
    r = g.add(rough, g.add(g.mul(h, 0.06), g.mul(m, 0.04)))
    height = g.add(g.mul(g.noise(240.0, 2.0, 0.5), weave),
                   g.add(g.mul(s, slub_height), g.mul(m, mottle_height)))
    return base, r, height


def welt(g, base, rough, height, attr=SEAM_ATTR, cord=0.005, groove=0.0035, bead=0.0022,
         darker=0.28, lighter=0.05, shinier=0.06):
    """Piping along the seams: a rounded cord (1 at the seam, 0 at `cord`
    meters) and a darker stitch groove just outside it. The cord's crest is
    a little lighter and smoother (it rubs first)."""
    d = g.attribute(attr)
    cordm = g.maprange(d, cord, 0.0)
    groovem = g.band(d, cord, cord + groove, 0.0012)
    height = g.add(height, g.sub(g.mul(cordm, bead), g.mul(groovem, bead * 0.6)))
    base = g.scale_color(base, g.add(g.sub(1.0, g.mul(groovem, darker)), g.mul(cordm, lighter)))
    rough = g.sub(rough, g.mul(cordm, shinier))
    return base, rough, height


def creases(g, base, height, mask, stretch=(22.0, 6.0, 12.0), depth=0.0012, sharp=0.72, darker=0.10):
    """Fabric creases inside a 0..1 mask: valleys along the 0.5 contours of a
    noise stretched by `stretch` (world x, y, z; small = long creases along
    that axis), slightly darker in the fold."""
    n = g.noise(1.0, 2.0, 0.5, vector=g.vec(*stretch))
    ridge = g.sub(1.0, g.math("ABSOLUTE", g.sub(g.mul(n, 2.0), 1.0)))
    c = g.mul(g.maprange(ridge, sharp, 1.0), mask)
    height = g.sub(height, g.mul(c, depth))
    base = g.scale_color(base, g.sub(1.0, g.mul(c, darker)))
    return base, height


def rub(g, base, rough, mask, shinier=0.20, tint=0.0):
    """Abrasion inside a 0..1 mask: compressed fibers are smoother (a soft
    shine); tint > 0 lightens (worn fuzz), < 0 darkens (skin oils)."""
    rough = g.sub(rough, g.mul(mask, shinier))
    base = g.scale_color(base, g.add(1.0, g.mul(mask, tint)))
    return base, rough


def pilling(g, base, height, mask, scale=140.0, amount=0.0005, lighter=0.05):
    """Small fuzz balls inside a 0..1 mask (low contrast; they sit on worn areas)."""
    p = g.mul(g.maprange(g.noise(scale, 1.0, 0.5), 0.60, 0.70), mask)
    height = g.add(height, g.mul(p, amount))
    base = g.scale_color(base, g.add(1.0, g.mul(p, lighter)))
    return base, height


def stain(g, base, rough, center, radius, z_band=0.03, strength=0.12, ring=0.18,
          color=(0.045, 0.034, 0.020)):
    """A faint dried spill on an upward-facing surface: an irregular disc
    around world `center` (x, y, z) with a darker tide mark at its rim."""
    cx, cy, cz = center
    d = g.add(g.dist_xy(cx, cy), g.mul(g.sub(g.noise(28.0, 2.0), 0.5), radius * 0.6))
    region = g.mul(g.band(g.z, cz - z_band, cz + z_band, 0.01), g.maprange(g.nz, 0.4, 0.8))
    inside = g.maprange(d, radius, radius * 0.75)
    rim = g.band(d, radius * 0.86, radius, radius * 0.07)
    fac = g.mul(region, g.add(g.mul(inside, strength), g.mul(rim, ring)))
    base = g.mixc(fac, base, color)
    rough = g.sub(rough, g.mul(fac, 0.25))
    return base, rough


def fabric_finish(g, base, rough, height):
    """Normal from the accumulated height (meters) and connect the BSDF."""
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))


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


def wool_knit(name, color, rough=0.95, rib_period=0.013, rib_height=0.0005, rib_direction="Y", fuzz=0.35):
    """Chunky-knit wool (throws, blankets) as a new `src_<name>` graph:
    heathered yarn color, soft knit ribs running perpendicular to
    `rib_direction` (bands vary along that world axis), fuzz pills, very
    rough. Returns (g, base, rough, height): add wear, then `fabric_finish`."""
    g = Graph(new_mat(f"src_{name}"))
    base, r, h = fabric_base(g, color, rough=rough, heather=0.07, slub=0.03, mottle=0.06, weave=0.00010)
    ribs = g.wave(0.314 / rib_period, 1.2, 1.0, rib_direction)
    h = g.add(h, g.mul(ribs, rib_height))
    base = g.scale_color(base, g.add(0.95, g.mul(ribs, 0.10)))
    base, h = pilling(g, base, h, fuzz, scale=110.0, amount=0.0004, lighter=0.06)
    return g, base, r, h


def braided_cord(g, color, pitch=0.007, strands=4, depth=0.00025, contrast=0.18,
                 along_attr="along", around_attrs=("around_c", "around_s")):
    """Textile braid on a `curves.tube` (reads its along/around attributes): two
    counter-rotating sets of `strands` helices with `pitch` meters per turn.
    Returns (base, rough, height in meters)."""
    s = g.attribute(along_attr)
    ang = g.math("ARCTAN2", g.attribute(around_attrs[1]), g.attribute(around_attrs[0]))
    k = 2.0 * math.pi / pitch
    p1 = g.math("SINE", g.add(g.mul(s, k), g.mul(ang, strands)))
    p2 = g.math("SINE", g.sub(g.mul(s, k), g.mul(ang, strands)))
    weave = g.mul(g.add(g.mul(p1, p2), 1.0), 0.5)
    fuzz = g.noise(400.0, 2.0)
    base = g.scale_color(color, g.add(1.0 - contrast, g.mul(weave, 2 * contrast)))
    rough = g.add(0.78, g.mul(g.sub(fuzz, 0.5), 0.1))
    return base, rough, g.mul(weave, depth)
