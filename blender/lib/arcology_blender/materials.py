"""Generic procedural source materials (baked later). Defaults are the fridge's.

Each recipe returns a `src_<name>` material. Asset-specific looks (a door's
fingerprints around its own handle, a sticker at a fixed spot) stay in the
asset's script and use `Graph` and `wear` directly.
"""

from . import wear
from .shading import Graph, new_mat


def white_plastic(name="liner", base=(0.90, 0.90, 0.87), grime_below=0.32, grime_full=0.13,
                  grime_color=(0.80, 0.77, 0.70)):
    """Molded white ABS (appliance liners, housings) with grime settling low."""
    g = Graph(new_mat(f"src_{name}"))
    rough = g.add(0.40, g.mul(g.sub(g.noise(20.0), 0.5), 0.10))
    base, rough = wear.low_grime(g, base, rough, grime_below, grime_full, grime_color)
    n = g.bump(g.noise(140.0, 2.0), 1.0, 0.001)
    return g.finish(base, rough, 0.0, n)


def frosted_plastic(name="frosted", base=(0.72, 0.78, 0.82), rough=0.14):
    """Opaque frosted polystyrene/acrylic (bins, drawers): glossy, slightly uneven."""
    g = Graph(new_mat(f"src_{name}"))
    r = g.add(rough, g.mul(g.sub(g.noise(15.0), 0.5), 0.08))
    n = g.bump(g.noise(60.0, 2.0), 1.0, 0.0015)
    return g.finish(base, r, 0.0, n)


def dark_plastic(name="dark", base=(0.045, 0.046, 0.05), rough=0.45):
    """Near-black satin plastic (trims, grilles, bezels)."""
    g = Graph(new_mat(f"src_{name}"))
    r = g.add(rough, g.mul(g.sub(g.noise(25.0), 0.5), 0.10))
    n = g.bump(g.noise(200.0, 2.0), 1.0, 0.0008)
    return g.finish(base, r, 0.0, n)


def rubber(name="rubber", base=(0.60, 0.60, 0.58), rough=0.72):
    """Soft rubber (gaskets, feet, bumpers)."""
    g = Graph(new_mat(f"src_{name}"))
    r = g.add(rough, g.mul(g.sub(g.noise(40.0), 0.5), 0.06))
    n = g.bump(g.noise(300.0, 1.0), 1.0, 0.0005)
    return g.finish(base, r, 0.0, n)


def gloss_paint(name, base, rough=0.25):
    """Flat glossy colored surface (magnets, painted accents)."""
    g = Graph(new_mat(f"src_{name}"))
    return g.finish(base, rough, 0.0, None)


def note_paper(name, scribble_lo, scribble_hi, base=(0.94, 0.93, 0.89), ruling=(0.55, 0.65, 0.85),
               ink=(0.12, 0.12, 0.30), lines_per_m=125.0):
    """Ruled paper with a handwritten scribble inside an x/z rectangle (world, facing -Y)."""
    g = Graph(new_mat(f"src_{name}"))
    line = g.maprange(g.math("FRACT", g.mul(g.z, lines_per_m)), 0.10, 0.06)
    base = g.mixc(g.mul(line, 0.8), base, ruling)
    # Ink: thin iso-lines of a distorted wave.
    w = g.wave(30.0, 9.0, 2.0, "X")
    stroke = g.mul(g.maprange(w, 0.42, 0.50), g.maprange(w, 0.58, 0.50))
    region = g.rect_xz(scribble_lo, scribble_hi, 0.005)
    base = g.mixc(g.mul(stroke, region), base, ink)
    return g.finish(base, 0.85, 0.0, None)
