"""Stage 1: build the shower geometry, procedural source materials and collision, save the .blend.

  blender -b --factory-startup --python blender/props/shower/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import shower_common as C  # noqa: E402
import lib_candidates as L  # noqa: E402
from arcology_blender import curves, metal, wear  # noqa: E402
from arcology_blender.geo import bm_box, bm_cyl, collision_box, cyl_x, cyl_y, cyl_z, finish, join, new_empty, new_object, shade  # noqa: E402,E501
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

ROT_OUT = Matrix.Rotation(math.radians(90.0), 4, "X")   # lathe +Z -> -Y (out of the back wall)


def lighter(c, f):
    return tuple(min(1.0, v * f) for v in c)


# ---------------------------------------------------------------------------
# Materials (src_*, baked later). Fixture metal: brushed gunmetal PVD, faint
# fingerprints and dried water spots; marble: honed, medium-scale soft veins.
# ---------------------------------------------------------------------------
def fixture_base(g, rough, spots=1.0, spot_amount=0.15, edges=True):
    """Gunmetal color with a soft tonal drift, polished convex edges and water spots."""
    base = g.mixc(g.maprange(g.noise(3.0, 2.0), 0.3, 0.7), C.GUNMETAL, lighter(C.GUNMETAL, 1.12))
    if edges:
        e = wear.convex_edges(g, radius=0.0012)
        base = g.mixc(g.mul(e, 0.25), base, lighter(C.GUNMETAL, 1.8))
        rough = g.sub(rough, g.mul(e, 0.06))
    base, rough = L.water_spots(g, base, rough, spots, amount=spot_amount)
    return base, rough


def mat_fixture(name, axis="Z", spots=1.0, smudge=None):
    g = Graph(new_mat(f"src_{name}"))
    rough, h = metal.brushed(g, 0.30, axis=axis, streak=0.05)
    base, rough = fixture_base(g, rough, spots)
    if smudge is not None:
        base, rough = wear.smudges(g, base, rough, smudge(g), rougher=0.12, darker=0.03)
    return g.finish_height(base, rough, 1.0, h)


def mat_plate():
    """Mixer plate: vertical brushing, engraved ticks around the dial (red hot / blue cold
    dots), position dots around the flow lever, fingerprints around both controls."""
    g = Graph(new_mat("src_plate"))
    rough, h = metal.brushed(g, 0.30, axis="Z", streak=0.05)
    base, rough = fixture_base(g, rough, 0.6)
    dx = g.sub(g.x, C.MIX_X)
    # dial ticks every 30 degrees within +-120, a long one at the top (38 C)
    r, ang = L.polar(g, dx, g.sub(g.z, C.TEMP_PIVOT.z))
    step = math.pi / 6
    k = g.mul(ang, 1.0 / step)
    arc = g.mul(g.mul(g.math("ABSOLUTE", g.sub(g.math("FRACT", g.add(k, 0.5)), 0.5)), step), r)
    ticks = g.mul(g.mul(g.maprange(arc, 0.0009, 0.0005), g.band(r, 0.0345, 0.0390, 0.0004)),
                  g.maprange(g.math("ABSOLUTE", ang), 2.13, 2.08))
    top = g.mul(g.mul(g.maprange(g.math("ABSOLUTE", dx), 0.0010, 0.0006), g.band(r, 0.0345, 0.0435, 0.0004)),
                g.maprange(g.math("ABSOLUTE", ang), 0.3, 0.2))
    engr = g.math("MAXIMUM", ticks, top)

    def dot(cx, cz, rad=0.0017):
        d = g.math("SQRT", g.add(g.mul(g.sub(g.x, cx), g.sub(g.x, cx)), g.mul(g.sub(g.z, cz), g.sub(g.z, cz))))
        return g.maprange(d, rad + 0.0004, rad - 0.0004)

    tz, fz = C.TEMP_PIVOT.z, C.FLOW_PIVOT.z
    hot, cold = dot(C.MIX_X - 0.043, tz, 0.0019), dot(C.MIX_X + 0.043, tz, 0.0019)
    flow = g.math("MAXIMUM", g.math("MAXIMUM", dot(C.MIX_X - 0.048, fz), dot(C.MIX_X + 0.048, fz)),
                  dot(C.MIX_X, fz - 0.046))
    engr = g.math("MAXIMUM", engr, flow)
    front = g.maprange(g.ny, -0.8, -0.95)
    engr = g.mul(engr, front)
    base = g.mixc(g.mul(engr, 0.85), base, (0.012, 0.012, 0.014))
    base = g.mixc(g.mul(g.mul(hot, front), 0.9), base, (0.42, 0.035, 0.025))
    base = g.mixc(g.mul(g.mul(cold, front), 0.9), base, (0.025, 0.09, 0.42))
    rough = g.add(rough, g.mul(engr, 0.25))
    h = g.sub(h, g.mul(g.math("MAXIMUM", engr, g.math("MAXIMUM", hot, cold)), 0.0003))
    region = g.mul(g.band(g.x, C.MIX_X - 0.06, C.MIX_X + 0.06, 0.02), g.band(g.z, 0.98, 1.22, 0.03))
    base, rough = wear.smudges(g, base, rough, region, rougher=0.10, darker=0.03)
    return g.finish_height(base, rough, 1.0, h)


def mat_rain():
    """Ceiling rain plate: brushed along X, a shadow groove around the nozzle field, black
    silicone nozzles on a 21 mm grid, a hint of limescale around a few of them."""
    g = Graph(new_mat("src_rain"))
    rough, h = metal.brushed(g, 0.30, axis="X", streak=0.05)
    base, rough = fixture_base(g, rough, 0.5, 0.1)
    u, v = g.sub(g.x, C.RAIN_C.x), g.sub(g.y, C.RAIN_C.y)
    au, av = g.math("ABSOLUTE", u), g.math("ABSOLUTE", v)
    half = C.RAIN_SIZE / 2 - 0.016
    inner = g.mul(g.maprange(au, half, half - 0.0006), g.maprange(av, half, half - 0.0006))
    inner2 = g.mul(g.maprange(au, half - 0.0012, half - 0.0018), g.maprange(av, half - 0.0012, half - 0.0018))
    groove = g.sub(inner, inner2)
    n_half = C.RAIN_NOZZLES * C.RAIN_PITCH / 2
    field = g.mul(g.maprange(au, n_half, n_half - 0.001), g.maprange(av, n_half, n_half - 0.001))
    nozzle = g.mul(L.dot_grid(g, u, v, C.RAIN_PITCH, 0.0028, 0.0005, -n_half, -n_half), field)
    ring = g.mul(L.dot_grid(g, u, v, C.RAIN_PITCH, 0.0050, 0.0012, -n_half, -n_half), field)
    base, rough, crust = L.limescale(g, base, rough, g.mul(g.sub(ring, nozzle), 0.5), amount=0.25, scale=90.0)
    base = g.mixc(nozzle, base, C.SILICONE)
    base = g.mixc(g.mul(groove, 0.9), base, (0.008, 0.008, 0.009))
    rough = g.mixf(nozzle, rough, 0.55)
    h = g.add(g.sub(h, g.mul(groove, 0.0006)), g.add(g.mul(nozzle, 0.0005), g.mul(crust, 0.00005)))
    return g.finish_height(base, rough, g.sub(1.0, nozzle), h)


def mat_drain():
    """Linear drain sections: brushed frame, a shadow groove around the slotted grate,
    transverse slots (5 mm at 16 mm pitch), slight limescale on the grate."""
    g = Graph(new_mat("src_drain"))
    rough, h = metal.brushed(g, 0.32, axis="X", streak=0.05)
    base, rough = fixture_base(g, rough, 1.0, 0.08, edges=False)
    seg = (2 * C.HX) / C.DRAIN_SECTIONS
    xl = g.mul(g.math("FRACT", g.mul(g.add(g.x, C.HX), 1.0 / seg)), seg)
    y0, y1 = C.DRAIN_Y0, C.DRAIN_Y1
    rim = 0.010
    inner = g.mul(g.band(xl, rim, seg - rim, 0.0005), g.band(g.y, y0 + rim, y1 - rim, 0.0005))
    inner2 = g.mul(g.band(xl, rim + 0.0013, seg - rim - 0.0013, 0.0005),
                   g.band(g.y, y0 + rim + 0.0013, y1 - rim - 0.0013, 0.0005))
    groove = g.sub(inner, inner2)
    field = g.mul(g.band(xl, 0.024, seg - 0.024, 0.0005), g.band(g.y, y0 + 0.022, y1 - 0.022, 0.0005))
    pitch = 0.016
    d = g.mul(g.math("ABSOLUTE", g.sub(g.math("FRACT", g.mul(xl, 1.0 / pitch)), 0.5)), pitch)
    slot = g.mul(g.maprange(d, 0.0029, 0.0022), field)
    near = g.mul(g.maprange(d, 0.0060, 0.0030), field)
    top = g.maprange(g.nz, 0.8, 0.95)
    base, rough, crust = L.limescale(g, base, rough, g.mul(g.add(g.mul(near, 0.7), g.mul(inner2, 0.25)), top),
                                     amount=0.08, rougher=0.25, scale=110.0)
    base = g.mixc(slot, base, (0.006, 0.006, 0.007))
    base = g.mixc(g.mul(groove, 0.9), base, (0.008, 0.008, 0.009))
    rough = g.mixf(slot, rough, 0.75)
    h = g.sub(g.add(h, g.mul(crust, 0.00003)), g.add(g.mul(slot, 0.0012), g.mul(groove, 0.0005)))
    return g.finish_height(base, rough, g.sub(1.0, g.mul(slot, 0.6)), h)


def mat_hose():
    """Braided gunmetal hose (on a curves.tube): crowns brighter and smoother than the gaps."""
    g = Graph(new_mat("src_hose"))
    weave, h = L.braid(g, pitch=0.010, strands=6, depth=0.00035)
    base = g.mixc(weave, lighter(C.GUNMETAL, 0.55), lighter(C.GUNMETAL, 1.45))
    rough = g.add(g.mul(g.sub(1.0, weave), 0.22), 0.26)
    base, rough = L.water_spots(g, base, rough, g.maprange(g.z, 0.9, 0.6), amount=0.1)
    return g.finish_height(base, rough, 1.0, h)


def mat_marble():
    """Honed white marble: soft grey veins at a medium scale (isolines of a distorted noise),
    a faint cloudy drift, roughness 0.22 on the top, 0.35 on the edges."""
    g = Graph(new_mat("src_marble"))
    n1 = g.noise(1.6, 5.0, 0.55)
    n1.node.inputs["Distortion"].default_value = 1.2
    n2 = g.noise(3.4, 4.0, 0.5, vector=g.offset((3.1, 7.7, 1.3)))
    n2.node.inputs["Distortion"].default_value = 0.8
    v1 = g.maprange(g.math("ABSOLUTE", g.sub(n1, 0.5)), 0.020, 0.002)
    v1 = g.mul(v1, g.maprange(g.noise(0.9, 2.0, vector=g.offset((5.0, 1.0, 2.0))), 0.35, 0.6))
    v2 = g.maprange(g.math("ABSOLUTE", g.sub(n2, 0.5)), 0.008, 0.001)
    halo = g.maprange(g.math("ABSOLUTE", g.sub(n1, 0.5)), 0.06, 0.0)
    cloud = g.maprange(g.noise(1.1, 3.0, 0.5, vector=g.offset((9.0, 2.0, 4.0))), 0.3, 0.75)
    base = g.mixc(g.mul(cloud, 0.35), C.MARBLE, (0.70, 0.69, 0.665))
    base = g.mixc(g.mul(halo, 0.24), base, C.VEIN)
    base = g.mixc(g.mul(v1, 0.65), base, C.VEIN)
    base = g.mixc(g.mul(v2, 0.40), base, lighter(C.VEIN, 1.25))
    top = g.maprange(g.nz, 0.85, 0.97)
    rough = g.mixf(top, 0.35, 0.22)
    rough = g.add(rough, g.mul(g.add(v1, v2), 0.05))
    base, rough = L.water_spots(g, base, rough, g.mul(top, 0.5), amount=0.08, rougher=0.10,
                                color=(0.86, 0.85, 0.82))
    h = g.mul(g.add(v1, g.mul(v2, 0.5)), -0.00004)
    return g.finish_height(base, rough, 0.0, h)


def mat_glass_edge():
    """Polished edge of 10 mm low-iron glass (opaque strip around the free edges)."""
    g = Graph(new_mat("src_glass_edge"))
    tone = g.maprange(g.noise(30.0, 2.0), 0.3, 0.7)
    base = g.mixc(tone, (0.50, 0.56, 0.55), (0.60, 0.66, 0.65))
    return g.finish(base, 0.06, 0.0)


def mat_lever():
    """Flow lever: brushed along the paddle (object space, so it turns with it), fingerprints
    toward the tip."""
    g = Graph(new_mat("src_lever"))
    vec, ox, oy, oz = L.object_xyz(g)
    n = g.noise(1.0, 2.0, 0.6, vector=g.vscale(vec, 700.0, 700.0, 3.0))
    rough = g.add(0.30, g.mul(g.sub(n, 0.5), 0.10))
    base, rough = fixture_base(g, rough, 0.4, 0.2)
    base, rough = wear.smudges(g, base, rough, g.maprange(oz, -0.02, -0.07), rougher=0.14, darker=0.03)
    return g.finish_height(base, rough, 1.0, g.mul(n, 0.00002))


def mat_dial():
    """Thermostat dial: knurled rim (40 flutes), spun front with an engraved indicator at the
    top (object space)."""
    g = Graph(new_mat("src_dial"))
    vec, ox, oy, oz = L.object_xyz(g)
    r, ang = L.polar(g, ox, oz)
    side = g.maprange(g.math("ABSOLUTE", g.ny), 0.5, 0.2)
    flute = g.mul(g.add(g.math("SINE", g.mul(ang, 40.0)), 1.0), 0.5)
    flute = g.mul(g.maprange(flute, 0.15, 0.85), side)
    rough, h = L.spun_about(g, ox, oz, oy, 0.28, 0.05)
    rough = g.mixf(side, rough, g.add(0.34, g.mul(flute, 0.06)))
    base, rough = fixture_base(g, rough, 0.4, 0.2)
    ind = g.mul(g.mul(g.maprange(g.math("ABSOLUTE", ox), 0.0009, 0.0005), g.band(oz, 0.009, 0.022, 0.0004)),
                g.maprange(g.ny, -0.8, -0.95))
    base = g.mixc(g.mul(ind, 0.9), base, (0.012, 0.012, 0.014))
    rough = g.add(rough, g.mul(ind, 0.25))
    base, rough = wear.smudges(g, base, rough, side, rougher=0.12, darker=0.03)
    h = g.sub(g.add(h, g.mul(flute, 0.00035)), g.mul(ind, 0.0003))
    return g.finish_height(base, rough, 1.0, h)


def mat_handheld(zh):
    """Hand shower: brushed along the handle (object space), black silicone nozzles in three
    rings on the face, fingerprints on the handle."""
    g = Graph(new_mat("src_handheld"))
    vec, ox, oy, oz = L.object_xyz(g)
    n = g.noise(1.0, 2.0, 0.6, vector=g.vscale(vec, 700.0, 700.0, 3.0))
    rough = g.add(0.30, g.mul(g.sub(n, 0.5), 0.10))
    base, rough = fixture_base(g, rough, 0.6, 0.25)
    r, ang = L.polar(g, ox, g.sub(oz, zh))
    face = g.maprange(oy, -0.0110, -0.0120)
    noz = g.maprange(r, 0.0024, 0.0016)
    for rk, nk in ((0.013, 8), (0.023, 14), (0.033, 20)):
        k = g.mul(ang, nk / (2 * math.pi))
        arc = g.mul(g.math("ABSOLUTE", g.sub(g.math("FRACT", g.add(k, 0.5)), 0.5)), 2 * math.pi * rk / nk)
        dr = g.sub(r, rk)
        d = g.math("SQRT", g.add(g.mul(dr, dr), g.mul(arc, arc)))
        noz = g.math("MAXIMUM", noz, g.maprange(d, 0.0022, 0.0015))
    noz = g.mul(noz, face)
    ring = g.mul(g.maprange(r, 0.0405, 0.0400), g.maprange(r, 0.0390, 0.0395))
    base = g.mixc(noz, base, C.SILICONE)
    base = g.mixc(g.mul(g.mul(ring, face), 0.8), base, (0.01, 0.01, 0.011))
    rough = g.mixf(noz, rough, 0.55)
    base, rough = wear.smudges(g, base, rough, g.band(oz, -0.10, 0.03, 0.02), rougher=0.14, darker=0.03)
    h = g.add(g.mul(n, 0.00002), g.mul(noz, 0.0006))
    return g.finish_height(base, rough, g.sub(1.0, noz), h)


def mat_glass():
    """Unbaked low-iron glass (Godot replaces it with its transparent glass shader)."""
    m = new_mat(C.GLASS_MAT)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.93, 0.96, 0.955, 1.0)
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["IOR"].default_value = 1.52
    b.inputs["Transmission Weight"].default_value = 1.0
    return m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def mesh(name, bm, coll, mat, bevel=None, segs=2, parent=None, sharp=35.0, drops=(), splits=()):
    """Object with optional bevel, smooth/sharp shading, hidden faces against the shell dropped
    (`drops`: (axis, value, sign)) and long members cut into short UV islands (`splits`)."""
    ob = new_object(name, bm, coll, material=mat, parent=parent)
    if bevel:
        finish(ob, bevel, segs, sharp_angle=sharp)
    if splits:
        L.split_planes(ob, splits)
    shade(ob, sharp)
    for axis, value, sign in drops:
        L.drop_faces_on_plane(ob, axis, value, sign)
    return ob


WALL = (1, C.BACK_Y, 1)        # faces on the back wall, facing it
SIDE = (0, C.HX, 1)
SIDE_W = (0, -C.HX, -1)
FLOOR = (2, 0.0, -1)
V_SPLITS = ((2, 0.70), (2, 1.40))                  # UV island cuts along tall members
X_SPLITS = ((0, -0.20), (0, 0.50), (0, 1.00))      # ... and along the glass top edge
CEILING = (2, C.CEIL, 1)


# ---------------------------------------------------------------------------
# Body (world coordinates)
# ---------------------------------------------------------------------------
def build_glass(coll, mats):
    gy, x0, x1, top, r = C.GLASS_Y, C.GLASS_X0, C.GLASS_X1, C.GLASS_H, C.GLASS_CORNER_R
    corner = curves.arc_points((x0 + r, gy, top - r), r, 90.0, 180.0, 6, (1, 0, 0), (0, 0, 1))
    outline = [Vector((x0, gy, 0.0)), Vector((x1, gy, 0.0)), Vector((x1, gy, top))] + corner
    bm = bmesh.new()
    verts = [bm.verts.new(p) for p in outline]
    bm.faces.new(verts)  # counter-clockwise seen from -Y: the normal faces the room
    glass = new_object("ShowerGlass", bm, coll, material=mats["glass"])
    me = glass.data
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = ((co.x - x0) / (x1 - x0), co.z / top)
    tag(glass, "glass")

    # Opaque polished-edge strip along the free vertical edge, the dubbed corner and the top
    path = [Vector((x0, gy, 0.0))] + list(reversed(corner)) + [Vector((x1, gy, top))]
    t, d, a = C.GLASS_T / 2, C.EDGE_DEPTH, 0.0008
    profile = [(-t, d), (-t, a), (-t + a, 0.0), (t - a, 0.0), (t, a), (t, d)]
    bm = bmesh.new()
    curves.sweep(bm, path, profile, up=(1.0, 0.0, 0.0))
    return mesh("GlassEdge", bm, coll, mats["glass_edge"], sharp=50.0, drops=(FLOOR,), splits=V_SPLITS + X_SPLITS)


def build_channel(coll, mats):
    """Gunmetal U-channel on the side wall holding the glass."""
    s, hh, xb = C.CH_SLOT, C.CH_HALF, C.HX - C.CH_BASE
    outline = [(C.HX, -hh), (C.HX, hh), (C.CH_X0, hh), (C.CH_X0, s), (xb, s), (xb, -s), (C.CH_X0, -s), (C.CH_X0, -hh)]
    bm = bmesh.new()
    L.extrude_outline(bm, outline, Matrix.Translation((0.0, C.GLASS_Y, 0.0)), C.GLASS_H)
    return mesh("GlassChannel", bm, coll, mats["fx_z"], 0.0008, 1, drops=(SIDE, FLOOR), splits=V_SPLITS)


def build_bar(coll, mats):
    """Stabiliser bar: through-glass fitting near the free top corner, round bar, wall flange."""
    gy, x, z = C.GLASS_Y, C.BAR_X, C.BAR_Z
    bm = bmesh.new()
    lathe = [(0.0, 0.0), (C.BAR_FIT_R - 0.002, 0.0), (C.BAR_FIT_R, 0.002), (C.BAR_FIT_R, 0.018),
             (C.BAR_FIT_R - 0.004, 0.024), (0.0, 0.024)]
    L.lathe_at(bm, lathe, Matrix.Translation((x, gy + 0.0055, z)) @ Matrix.Rotation(math.radians(-90), 4, "X"), 40)
    cap = [(0.0, 0.0), (0.0155, 0.0), (0.017, 0.0015), (0.017, 0.006), (0.014, 0.0085), (0.0, 0.0085)]
    L.lathe_at(bm, cap, Matrix.Translation((x, gy - 0.0055, z)) @ ROT_OUT, 40)
    bm_cyl(bm, 0.0055, 0.012, cyl_y((x, gy, z)), 16)   # through-bolt with its bushing
    fitting = mesh("BarFitting", bm, coll, mats["fx_y"], sharp=40.0)
    bm = bmesh.new()
    y0, y1 = gy + 0.026, C.BACK_Y - 0.010
    bm_cyl(bm, C.BAR_R, y1 - y0, cyl_y((x, (y0 + y1) / 2, z)), 32)
    bar = mesh("Bar", bm, coll, mats["fx_y"], 0.0012, 2, splits=((1, -0.25), (1, 0.25)))
    bm = bmesh.new()
    flange = [(0.0, 0.0), (0.024, 0.0), (0.024, 0.006), (0.021, 0.0115), (0.012, 0.0125), (0.0, 0.0125)]
    L.lathe_at(bm, flange, Matrix.Translation((x, C.BACK_Y, z)) @ ROT_OUT, 40)
    wall = mesh("BarFlange", bm, coll, mats["fx_y"], sharp=40.0, drops=(WALL,))
    return [fitting, bar, wall]


def build_rain_head(coll, mats):
    c, hs = C.RAIN_C, C.RAIN_SIZE / 2
    bm = bmesh.new()
    bm_box(bm, (c.x - hs, c.y - hs, C.CEIL - C.RAIN_T), (c.x + hs, c.y + hs, C.CEIL))
    return mesh("RainHead", bm, coll, mats["rain"], 0.0025, 3, drops=(CEILING,))


def build_mixer(coll, mats):
    """Concealed thermostat's wall plate (the controls are separate parts)."""
    outline = curves.rounded_rect_profile(C.PLATE_W, C.PLATE_H, 0.016, 5)
    m = Matrix(((1, 0, 0, C.MIX_X), (0, 0, -1, C.BACK_Y), (0, 1, 0, C.MIX_Z), (0, 0, 0, 1)))
    bm = bmesh.new()
    L.extrude_outline(bm, outline, m, C.PLATE_T)
    return mesh("MixerPlate", bm, coll, mats["plate"], 0.0025, 3, sharp=40.0, drops=(WALL,))


def build_rail(coll, mats):
    """Slide rail with two wall brackets, the slider holder and its tilted cradle."""
    x, y = C.RAIL_X, C.RAIL_Y
    r = C.RAIL_R
    bm = bmesh.new()
    bm_cyl(bm, r, C.RAIL_Z1 - C.RAIL_Z0 - 0.012, cyl_z((x, y, (C.RAIL_Z0 + C.RAIL_Z1) / 2)), 32)
    dome = [(r, 0.0), (r * 0.93, 0.0035), (r * 0.65, 0.0065), (0.0, 0.0075)]
    L.lathe_at(bm, [(0.0, -0.001)] + [(r, -0.001)] + dome, Matrix.Translation((x, y, C.RAIL_Z1 - 0.006)), 32)
    L.lathe_at(bm, [(0.0, -0.001)] + [(r, -0.001)] + dome,
               Matrix.Translation((x, y, C.RAIL_Z0 + 0.006)) @ Matrix.Rotation(math.pi, 4, "X"), 32)
    rail = mesh("Rail", bm, coll, mats["fx_z"], sharp=40.0, splits=((2, 1.40),))
    bm = bmesh.new()
    for z in C.RAIL_BRACKETS:
        bm_cyl(bm, 0.0145, 0.024, cyl_z((x, y, z)), 32)
        bm_cyl(bm, 0.0085, C.BACK_Y - y - 0.006, cyl_y((x, (y + C.BACK_Y - 0.006) / 2, z)), 24)
    brackets = mesh("RailBrackets", bm, coll, mats["fx_y"], 0.0012, 2)
    bm = bmesh.new()
    rose = [(0.0, 0.0), (0.022, 0.0), (0.022, 0.005), (0.019, 0.008), (0.0, 0.0085)]
    for z in C.RAIL_BRACKETS:
        L.lathe_at(bm, rose, Matrix.Translation((x, C.BACK_Y, z)) @ ROT_OUT, 32)
    roses = mesh("RailRosettes", bm, coll, mats["fx_y"], sharp=40.0, drops=(WALL,))

    # Slider: sleeve on the rail, arm out to the cradle, a clamp knob on the side
    seat = C.SEAT
    bm = bmesh.new()
    bm_cyl(bm, 0.0165, 0.046, cyl_z((x, y, seat.z - 0.004)), 32)
    ay0, ay1 = seat.y + 0.021, y - 0.010   # arm ends inside the cradle wall, clear of the handle
    bm_cyl(bm, 0.0078, ay1 - ay0, cyl_y((x, (ay0 + ay1) / 2, seat.z - 0.002)), 20)
    bm_cyl(bm, 0.0085, 0.012, cyl_x((x + 0.020, y, seat.z - 0.004)), 24)
    slider = mesh("Slider", bm, coll, mats["fx_z"], 0.0012, 2)
    bm = bmesh.new()
    cradle = [(0.0159, -0.008), (0.0222, -0.008), (0.0232, -0.005), (0.0232, 0.006), (0.0222, 0.009),
              (0.0166, 0.009)]   # inner cone follows the handle's taper (0.2-0.4 mm clearance)
    L.lathe_at(bm, cradle, Matrix.Translation(seat) @ C.HAND_ROT, 40, closed=True)
    cup = mesh("Cradle", bm, coll, mats["fx_z"], sharp=40.0)
    return [rail, brackets, roses, slider, cup]


def hose_path():
    a = C.HAND_ROT.to_3x3() @ Vector((0.0, 0.0, 1.0))
    bottom = C.SEAT + a * C.HAND_BOTTOM
    f = bottom - a * 0.030
    o = C.OUTLET
    yo = C.BACK_Y - 0.048
    pts = [f, f - a * 0.04, (-0.052, 0.622, 1.32), (-0.060, 0.614, 1.20), (-0.074, 0.603, 1.02),
           (-0.094, 0.595, 0.84), (-0.124, 0.590, 0.665), (-0.165, 0.595, 0.565), (-0.215, 0.610, 0.548),
           (-0.262, 0.628, 0.600), (-0.290, 0.643, 0.680), (o.x, yo, 0.752), (o.x, yo, o.z - 0.078)]
    return bottom, a, catmull_rom_dense(pts)


def catmull_rom_dense(pts):
    return curves.catmull_rom([tuple(p) for p in pts], samples=7)


def build_hose(coll, mats):
    """Braided hose from the hand shower down in a loop and up into the wall outlet, with
    conical ferrules at both ends and the outlet elbow."""
    bottom, a, path = hose_path()
    bm = bmesh.new()
    curves.tube(bm, path, C.HOSE_R, segments=12, caps=True)
    hose = new_object("Hose", bm, coll, material=mats["hose"])
    L.split_planes(hose, ((2, 1.0), (0, -0.20)))
    shade(hose, 60.0)

    bm = bmesh.new()
    ferrule = [(0.0, 0.0), (0.0098, 0.0), (0.0098, 0.010), (0.0090, 0.026), (0.0080, 0.034), (0.0, 0.034)]
    rot = Vector((0, 0, 1)).rotation_difference(-a).to_matrix().to_4x4()
    L.lathe_at(bm, ferrule, Matrix.Translation(bottom) @ rot, 24)
    o = C.OUTLET
    yo = C.BACK_Y - 0.048
    L.lathe_at(bm, ferrule, Matrix.Translation((o.x, yo, o.z - 0.048)) @ Matrix.Rotation(math.pi, 4, "X"), 24)
    ends = mesh("HoseFerrules", bm, coll, mats["fx_z"], sharp=40.0)

    # Wall outlet: rosette, stub, elbow down, hex nut
    bm = bmesh.new()
    rose = [(0.0, 0.0), (0.025, 0.0), (0.025, 0.005), (0.022, 0.008), (0.0, 0.0085)]
    L.lathe_at(bm, rose, Matrix.Translation((o.x, C.BACK_Y, o.z)) @ ROT_OUT, 32)
    roses = mesh("OutletRosette", bm, coll, mats["fx_y"], sharp=40.0, drops=(WALL,))
    bm = bmesh.new()
    bm_cyl(bm, 0.0105, C.BACK_Y - 0.006 - yo, cyl_y((o.x, (C.BACK_Y - 0.006 + yo) / 2, o.z)), 24)
    bm_cyl(bm, 0.0105, 0.0105 + 0.030, cyl_z((o.x, yo, o.z + (0.0105 - 0.030) / 2)), 24)
    elbow = mesh("OutletElbow", bm, coll, mats["fx_y"], 0.003, 3)
    bm = bmesh.new()
    bm_cyl(bm, 0.0128, 0.018, cyl_z((o.x, yo, o.z - 0.039)), 6)
    nut = mesh("OutletNut", bm, coll, mats["fx_z"], 0.0012, 2)
    return [hose, ends, roses, elbow, nut]


def build_shelf(coll, mats):
    bm = bmesh.new()
    bm_box(bm, (C.SHELF_X0, C.SHELF_Y0, C.SHELF_TOP - C.SHELF_T), (C.HX, C.BACK_Y, C.SHELF_TOP))
    return mesh("Shelf", bm, coll, mats["marble"], 0.002, 2, drops=(WALL, SIDE), splits=((0, 0.85),))


def build_drain(coll, mats):
    seg = 2 * C.HX / C.DRAIN_SECTIONS
    bm = bmesh.new()
    for i in range(C.DRAIN_SECTIONS):
        x0 = -C.HX + i * seg + (0.0003 if i > 0 else 0.0)
        x1 = -C.HX + (i + 1) * seg - (0.0003 if i < C.DRAIN_SECTIONS - 1 else 0.0)
        bm_box(bm, (x0, C.DRAIN_Y0, 0.0), (x1, C.DRAIN_Y1, C.DRAIN_H))
    return mesh("Drain", bm, coll, mats["drain"], 0.0008, 1, drops=(FLOOR, WALL, SIDE, SIDE_W))


def build_body(coll, col_coll, mats):
    parts = [build_glass(coll, mats), build_channel(coll, mats), build_rain_head(coll, mats),
             build_mixer(coll, mats), build_shelf(coll, mats), build_drain(coll, mats)]
    parts += build_bar(coll, mats) + build_rail(coll, mats) + build_hose(coll, mats)
    body = join(parts, "Shower")
    tag(body, "body")

    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColGlass", (C.GLASS_X0, C.GLASS_Y - 0.010, 0.0), (C.HX, C.GLASS_Y + 0.010, C.GLASS_H))
    col("ColShelf", (C.SHELF_X0, C.SHELF_Y0, C.SHELF_TOP - C.SHELF_T), (C.HX, C.BACK_Y, C.SHELF_TOP))
    col("ColBar", (C.BAR_X - 0.012, C.GLASS_Y + 0.005, C.BAR_Z - 0.012), (C.BAR_X + 0.012, C.BACK_Y, C.BAR_Z + 0.012))
    return body


# ---------------------------------------------------------------------------
# Moving parts (local coordinates, root mesh at the pivot)
# ---------------------------------------------------------------------------
def build_flow(coll, mats):
    """Flow/diverter lever: hub and a teardrop paddle pointing down (off)."""
    bm = bmesh.new()
    hub = [(0.0, 0.0005), (0.0200, 0.0005), (0.0212, 0.0018), (0.0212, 0.021), (0.0, 0.021)]
    L.lathe_at(bm, hub, ROT_OUT, 48)
    paddle = L.tapered_capsule_outline(0.0235, 0.0085, C.LEVER_LEN, 32)
    m = Matrix(((1, 0, 0, 0), (0, 0, -1, -0.019), (0, 1, 0, 0), (0, 0, 0, 1)))
    L.extrude_outline(bm, paddle, m, 0.011)
    lever = new_object("MixerFlow", bm, coll, origin=C.FLOW_PIVOT, material=mats["lever"])
    finish(lever, 0.0018, 3, angle=40.0, sharp_angle=40.0)
    tag(lever, "flow")
    tag(new_empty("FlowGrip", coll, C.FLOW_GRIP, parent=lever), "flow")
    return lever


def build_temp(coll, mats):
    """Thermostat dial: knurled cylinder with a shallow dished front."""
    bm = bmesh.new()
    prof = [(0.0, 0.0005), (0.0282, 0.0005), (0.0298, 0.0020), (0.0300, 0.0040), (0.0300, 0.0360),
            (0.0293, 0.0392), (0.0276, 0.0404), (0.0200, 0.0399), (0.0100, 0.0393), (0.0, 0.0391)]
    L.lathe_at(bm, prof, ROT_OUT, 64)
    dial = new_object("MixerTemp", bm, coll, origin=C.TEMP_PIVOT, material=mats["dial"])
    shade(dial, 40.0)
    tag(dial, "temp")
    tag(new_empty("TempGrip", coll, C.TEMP_GRIP, parent=dial), "temp")
    return dial


HEAD_Z = 0.115


def build_handheld(coll, mats):
    """Hand shower in its holder: the handle axis is local +Z, the round head's spray face
    looks along local -Y; origin at the holder seat."""
    bm = bmesh.new()
    zb = C.HAND_BOTTOM
    handle = [(0.0, zb), (0.0106, zb), (0.0112, zb + 0.0015), (0.0112, zb + 0.012), (0.0121, zb + 0.013),
              (0.0128, zb + 0.017), (0.0140, -0.060), (0.0152, -0.020), (0.0160, 0.0), (0.0165, 0.020),
              (0.0162, 0.036), (0.0150, 0.050), (0.0132, 0.062), (0.0120, 0.072), (0.0116, 0.082),
              (0.0, 0.082)]
    curves.lathe(bm, handle, segments=32)
    head = [(0.0, -0.013), (0.040, -0.013), (0.0485, -0.0118), (0.0528, -0.0075), (0.0540, -0.001),
            (0.0535, 0.0055), (0.0515, 0.0105), (0.0480, 0.0128), (0.0450, 0.0130), (0.0442, 0.0124),
            (0.0, 0.0124)]
    L.lathe_at(bm, head, Matrix.Translation((0.0, 0.0, HEAD_Z)) @ ROT_OUT, 48)
    hand = new_object("Handheld", bm, coll, origin=C.SEAT, material=mats["handheld"])
    hand.rotation_euler = (math.radians(C.TILT_DEG), 0.0, 0.0)
    shade(hand, 40.0)
    tag(hand, "handheld")
    tag(new_empty("HandGrip", coll, C.HAND_GRIP, parent=hand), "handheld")
    return hand


def build_materials():
    return {
        "glass": mat_glass(), "glass_edge": mat_glass_edge(),
        "fx_z": mat_fixture("fx_z", "Z"), "fx_y": mat_fixture("fx_y", "Y"),
        "plate": mat_plate(), "rain": mat_rain(), "drain": mat_drain(), "hose": mat_hose(),
        "marble": mat_marble(), "lever": mat_lever(), "dial": mat_dial(), "handheld": mat_handheld(HEAD_Z),
    }


def main():
    clear_scene()
    mats = build_materials()
    coll = get_collection("Shower")
    build_body(coll, get_collection("ShowerCollision"), mats)
    parts = get_collection("ShowerParts")
    build_flow(parts, mats)
    build_temp(parts, mats)
    build_handheld(parts, mats)
    bpy.context.view_layer.update()
    print(f"TRIS body={part_tris('body')} glass={part_tris('glass')} flow={part_tris('flow')} "
          f"temp={part_tris('temp')} handheld={part_tris('handheld')} collision={part_tris('body_col')}")
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
