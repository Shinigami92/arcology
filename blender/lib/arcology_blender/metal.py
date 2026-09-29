"""Metal finish layers for `Graph` materials (D-028).

`brushed` gives the roughness streaks and relief of a brushed or spun finish;
the color, metallic and wear stay with the asset (see `wear.convex_edges` for
coating worn to bare metal on the edges). Finish with
`g.finish_height(base, rough, 1.0, height)`. Promoted from the nightstand
(Opus 5.5). For plain generic plastics and rubber see `materials`.
"""


def brushed(g, rough=0.32, axis="Z", center=None, streak=0.07, height=0.00002):
    """Brushed finish: fine roughness streaks along a world axis ("X", "Y",
    "Z"), or circular (spun, like a lamp base or a knob) around a vertical
    axis through `center` (x, y). `streak` is the +- roughness variation,
    `height` the relief in meters. Returns (rough, height in m)."""
    if center is not None:
        d = g.dist_xy(center[0], center[1])
        v = g.combine(g.mul(d, 900.0), g.mul(g.z, 900.0), 0.0)
        n = g.noise(1.0, 2.0, 0.6, vector=v)
    else:
        s = {"X": (3.0, 700.0, 700.0), "Y": (700.0, 3.0, 700.0), "Z": (700.0, 700.0, 3.0)}[axis]
        n = g.noise(1.0, 2.0, 0.6, vector=g.vec(*s))
    coarse = g.noise(8.0, 2.0)
    r = g.add(g.add(rough, g.mul(g.sub(n, 0.5), streak * 2)), g.mul(g.sub(coarse, 0.5), 0.06))
    return r, g.mul(n, height)
