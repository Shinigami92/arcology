"""Helpers of the lit wardrobe (Opus 5.5, runner-up of the bedroom A/B, D-032).

Everything else this asset wrote moved to the library (curves.sweep and the
profiles, curves.chaikin, curves.arc_points, geo.bm_square_taper,
geo.instance, wood.veneer_axis, wear.scratch, wear.edge_wear,
wear.bevel_edges, wear.bottom_scuffs(mask=), bake.Spread,
Graph.combine, Graph.finish_height). This brushed metal differs from
`metal.brushed` (it also varies the tint), so it stays here and the asset
rebuilds byte-identically; prefer `metal.brushed` for new assets.
"""


def _stretched(g, axis, across, along):
    s = [across, across, across]
    s["XYZ".index(axis)] = along
    return g.vec(*s)


def brushed_metal(g, axis="Z", base=(0.052, 0.060, 0.072), rough=0.32, streak=0.05, tint=0.10,
                  depth=0.00001):
    """Brushed metal (gunmetal defaults), brushed along world `axis`: fine
    streaks in roughness and a faint tint variation. Returns (base, rough, height)."""
    n = g.noise(1.0, 3.0, 0.6, _stretched(g, axis, 260.0, 3.0))
    blotch = g.sub(g.noise(18.0, 2.0), 0.5)
    r = g.add(rough, g.add(g.mul(g.sub(n, 0.5), 2 * streak), g.mul(blotch, 0.05)))
    b = g.scale_color(base, g.add(1.0, g.mul(g.sub(n, 0.5), 2 * tint)))
    height = g.mul(g.sub(n, 0.5), depth)
    return b, r, height
