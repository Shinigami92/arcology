"""Material helpers of the bed (Opus 5.5, won the bedroom A/B, D-032).

Everything else this asset wrote moved to the library: the cloth workflow
(`cloth.cloth_grid`, `fold_path`, `cloth_settle`, `thicken`, `soft_bounds`,
`bumps`), `soft.flatten_against`, `geo.set_float_attr`, `geo.bvh`,
`geo.trim_hidden`, texel weighting (`bake.bake_part(weight=...)`), the
heightfield collider (`collision.heightfield_collider`) and its checks
(`checks.surface_gap`, `checks.probe_gap`). This veneer and brushed metal
differ from `wood.veneer` and `metal.brushed`, so they stay here and the
bed rebuilds byte-identically; prefer the library versions for new assets.
"""


# --- Material layers ---------------------------------------------------------------
def wood_veneer(g, across, figure_vec, dark, mid, light, lines_per_m=22.0, figure=3.0, rough=0.40,
                pore_vec=None, streak_vec=None, line_contrast=0.55):
    """Sliced-veneer wood (walnut, oak) for `Graph`: meandering growth lines
    of varying strength, finer secondary lines, color streaks along the
    grain, broad variation between flitches, and pores.

    across: socket, a world coordinate across the grain in meters (e.g. world
    z on vertical faces with horizontal grain); figure_vec: vector socket
    (e.g. g.vec(0.9, 0.9, 3.5)) for the low-frequency noise that makes the
    lines meander (low values along the grain); streak_vec: vector stretched
    along the grain for the color streaks (defaults to figure_vec); pore_vec:
    vector stretched along the grain for the pores (defaults to figure_vec).
    Medium scale by default (lines every ~4.5 cm, low contrast pores) so it
    survives mipmapping without shimmer. rough is a satin lacquer.
    Returns (base, rough, height in m)."""
    fig = g.noise(1.0, 3.0, 0.55, vector=figure_vec)
    t = g.add(g.mul(across, lines_per_m), g.mul(fig, figure))
    tri = g.math("ABSOLUTE", g.sub(g.mul(g.math("FRACT", t), 2.0), 1.0))
    # line strength varies along the grain, so lines fade in and out
    strength = g.maprange(g.noise(2.3, 2.0, 0.5, vector=figure_vec), 0.30, 0.70, 0.35, 1.0)
    late = g.mul(g.maprange(tri, 0.55, 0.98), strength)
    t2 = g.add(g.mul(across, lines_per_m * 3.3), g.mul(fig, figure * 2.1))
    tri2 = g.math("ABSOLUTE", g.sub(g.mul(g.math("FRACT", t2), 2.0), 1.0))
    fine = g.maprange(tri2, 0.72, 0.98)
    sv = streak_vec if streak_vec is not None else figure_vec
    streak = g.maprange(g.noise(1.0, 3.0, 0.6, vector=sv), 0.25, 0.75)
    broad = g.maprange(g.noise(1.0, 2.0, 0.5, vector=g.vec(1.2, 1.2, 1.2)), 0.30, 0.70)
    base = g.mixc(g.mul(g.add(streak, broad), 0.5), mid, light)
    base = g.mixc(g.add(g.mul(late, line_contrast), g.mul(fine, 0.18)), base, dark)
    pv = pore_vec if pore_vec is not None else figure_vec
    pores = g.maprange(g.noise(90.0, 2.0, 0.5, vector=pv), 0.63, 0.72)
    base = g.scale_color(base, g.sub(1.0, g.mul(pores, 0.22)))
    r = g.add(rough, g.add(g.mul(late, 0.04), g.mul(pores, 0.10)))
    r = g.add(r, g.mul(g.sub(g.noise(6.0, 2.0), 0.5), 0.06))
    height = g.sub(0.0, g.add(g.mul(late, 0.00004), g.mul(pores, 0.00010)))
    return base, r, height


def brushed_metal(g, base, rough, brush_vec, streak=0.07, height=0.00002):
    """Brushed finish for `Graph`: roughness and slight color streaks along
    the brush direction. brush_vec stretches the position so the noise is
    long along the brushing (e.g. g.vec(3, 150, 150) brushes along X).
    Returns (base, rough, height in m)."""
    n = g.noise(1.0, 3.0, 0.6, vector=brush_vec)
    s = g.sub(n, 0.5)
    rough = g.add(rough, g.mul(s, 2 * streak))
    base = g.scale_color(base, g.add(1.0, g.mul(s, 0.25)))
    return base, rough, g.mul(n, height)
