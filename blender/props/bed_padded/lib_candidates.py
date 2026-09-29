"""Material helpers of the padded bed (Fable 5.1, runner-up of the bedroom A/B, D-032).

Everything else this asset wrote moved to the library: `cloth.drape`,
`cloth.shell_rim`, `cloth.ridge`, `cloth.lumps`, `cloth.smoothstep`,
`fabric.quilting`, `fabric.wool_knit`, and `Graph.wave(wave_type="RINGS",
vector=...)` / `Graph.offset`. This ring-wave veneer and brushed metal differ
from `wood.veneer` and `metal.brushed`, so they stay here and the bed
rebuilds byte-identically; prefer the library versions for new assets.
"""

from arcology_blender import wear
from arcology_blender.shading import Graph, new_mat


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
    pos = g.offset(axis_offset)
    rings = g.wave(ring_scale, ring_distortion, 2.0, grain, wave_type="RINGS", vector=pos)
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
