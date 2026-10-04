"""src_ materials of the traffic (baked into the shared `traffic_vehicle` atlas).

Every vehicle gets its own set (`src_<vehicle>_<slot>`) on a LocalGraph with
the vehicle's authoring offset, so masks use authoring coordinates (z = 0 at
the pod bottoms, y = 0 mid-length, nose +Y) whatever the object's position.
Medium-scale features only: panel seams and grime live in the normal and
albedo maps, nothing finer than ~2 cm (VR shimmer, style guide).

Slots: paint, trim, glass, bus_glass, headlight, taillight, thruster,
bar_red, bar_blue, marker, sign.
"""

from arcology_blender import wear
from arcology_blender.shading import new_mat
from lib_candidates import LocalGraph, decal, end_uv, set_emission, side_uv
from traffic_common import (
    AMBER, AMBER_HOT, BAR_BLUE, BAR_RED, CABIN_WARM, CYAN, CYAN_HOT, DUST, EMISSION, GRIME, GUNMETAL, HEADLIGHT,
    HOT_ATTR, MAGENTA, PRIMER, TAILLIGHT,
)

BLACK = (0.0, 0.0, 0.0)
CABIN_GLASS = (0.75, 0.70, 0.66)  # dim mixed interior light seen through tinted glass


def _scale(c, k):
    return tuple(k * x for x in c)


def _abs(g, v):
    return g.math("ABSOLUTE", v)


def _side(g):
    return g.maprange(_abs(g, g.nx), 0.35, 0.6)


def _add_emit(g, emit, color, mask):
    """emit + color * mask (color sockets, constants or None)."""
    term = g.mixc(mask, BLACK, color)
    if emit is None:
        return term
    n = g.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "ADD"
    n.inputs[0].default_value = 1.0
    g._set([s for s in n.inputs if s.name == "A" and s.type == "RGBA"][0], emit)
    g._set([s for s in n.inputs if s.name == "B" and s.type == "RGBA"][0], term)
    return [s for s in n.outputs if s.name == "Result" and s.type == "RGBA"][0]


# ---------------------------------------------------------------------------------------
# Shared layers
# ---------------------------------------------------------------------------------------
def seams(g, base, spec, width=0.014, depth=0.0025):
    """Panel seams: spec["seams_y"] = [(y, z_lo, z_hi)] cuts around the body at y
    (doors, hood, hatches), spec["seams_z"] = [(z, y_lo, y_hi)] horizontal cuts
    on the sides. Returns (base, height)."""
    m = 0.0
    for y, z0, z1 in spec.get("seams_y", ()):
        m = g.add(m, g.mul(g.band(g.y, y - width / 2, y + width / 2, 0.004), g.band(g.z, z0, z1, 0.004)))
    for z, y0, y1 in spec.get("seams_z", ()):
        m = g.add(m, g.mul(g.mul(g.band(g.z, z - width / 2, z + width / 2, 0.004), g.band(g.y, y0, y1, 0.004)),
                           _side(g)))
    m = g.math("MINIMUM", m, 1.0)
    base = g.scale_color(base, g.sub(1.0, g.mul(m, 0.6)))
    return base, g.mul(m, -depth)


def grime(g, base, rough, spec, metal):
    """Rain streaks below the belt line, dirt toward the belly, a dirty underside,
    soot around the thruster pods. Returns (base, rough, metal, dirt)."""
    belt, belly = spec["belt"], spec["belly"]
    side = _side(g)
    streak_n = g.noise(1.0, 2.0, 0.55, g.vec(2.2, 9.0, 0.55))
    streak = g.mul(g.mul(g.maprange(streak_n, 0.52, 0.74), side), g.maprange(g.z, belt + 0.10, belt - 0.15))
    breakup = g.maprange(g.noise(3.0, 2.0, 0.6), 0.3, 0.7)
    low = g.mul(g.maprange(g.z, belly + 0.32, belly - 0.02), g.add(0.35, g.mul(breakup, 0.65)))
    under = g.maprange(g.nz, -0.35, -0.75)
    dirt = g.math("MAXIMUM", g.mul(streak, 0.28), g.mul(low, 0.6))
    dirt = g.math("MAXIMUM", dirt, g.mul(under, 0.7))
    soot = 0.0
    for x, y, r in spec["pods"]:
        d = g.math("SQRT", g.add(g.mul(g.sub(g.x, x), g.sub(g.x, x)), g.mul(g.sub(g.y, y), g.sub(g.y, y))))
        soot = g.math("MAXIMUM", soot, g.maprange(d, r * 2.1, r * 0.9))
    soot = g.mul(g.mul(soot, g.maprange(g.z, belly + 0.45, belly)), g.add(0.5, g.mul(breakup, 0.5)))
    base = g.mixc(dirt, base, GRIME)
    base = g.mixc(g.mul(soot, 0.8), base, (0.006, 0.006, 0.006))
    rough = g.add(rough, g.add(g.mul(dirt, 0.3), g.mul(soot, 0.2)))
    metal = g.mul(metal, g.sub(1.0, g.math("MAXIMUM", dirt, soot)))
    return base, rough, metal, dirt


def underglow(g, spec, color, amount=0.10):
    """Thruster light spilling onto the belly around each pod (emission)."""
    m = 0.0
    for x, y, r in spec["pods"]:
        d = g.math("SQRT", g.add(g.mul(g.sub(g.x, x), g.sub(g.x, x)), g.mul(g.sub(g.y, y), g.sub(g.y, y))))
        m = g.math("MAXIMUM", m, g.maprange(d, r * 2.6, r * 1.0))
    m = g.mul(g.mul(m, g.maprange(g.nz, -0.2, -0.6)), amount)
    return g.mixc(m, BLACK, color)


def wear_and_dust(g, base, rough):
    edge = wear.convex_edges(g, radius=0.012, lo=0.05, hi=0.30)
    breakup = g.maprange(g.noise(6.0, 2.0, 0.6), 0.4, 0.62)
    base, rough = wear.edge_wear(g, base, rough, g.mul(edge, breakup), 1.0, PRIMER, amount=0.4, rough_delta=0.15)
    # Soft dust film on upward faces, large patches only (fine blotches read as camouflage on dark paint)
    dust = g.mul(g.maprange(g.nz, 0.55, 0.9), g.maprange(g.noise(0.8, 1.0, 0.5), 0.35, 0.75))
    base = g.mixc(g.mul(dust, 0.04), base, DUST)
    rough = g.add(rough, g.mul(dust, 0.12))
    return base, rough


def paint_base(g, color, rough=0.30, mottling=0.08):
    """Metallic paint, slightly uneven (resprays, fading) at large scale."""
    mott = g.maprange(g.noise(0.9, 2.0, 0.5), 0.3, 0.7)
    base = g.scale_color(color, g.add(1.0 - mottling, g.mul(mott, 2 * mottling)))
    r = g.add(rough, g.mul(g.sub(g.noise(2.5, 2.0, 0.5), 0.5), 0.12))
    return base, r


def ink(g, base, emit, image_pair, uv, mask=1.0):
    """Lay a decal (albedo with ink alpha + emission image) over base/emit."""
    alb, emi = image_pair
    col, alpha = decal(g, alb, *uv)
    ecol, _ = decal(g, emi, *uv)
    a = g.mul(alpha, mask)
    base = g.mixc(a, base, col)
    emit = _add_emit(g, emit, ecol, a)
    return base, emit


def finish_paint(g, base, rough, metal, height, emit):
    g.finish_height(base, rough, metal, height)
    if emit is not None:
        set_emission(g, emit, EMISSION)
    return g.mat


# ---------------------------------------------------------------------------------------
# Paint per vehicle
# ---------------------------------------------------------------------------------------
def paint_sedan(g, spec, decals):
    base, rough = paint_base(g, (0.012, 0.016, 0.030), 0.26)
    side = _side(g)
    stripe = g.mul(g.band(g.z, 0.45, 0.51, 0.006), side)            # magenta accent along the flank
    base = g.mixc(stripe, base, (0.55, 0.012, 0.09))
    nose = g.mul(g.band(g.y, 2.12, 2.20, 0.006), g.band(g.z, 0.40, 0.76, 0.01))  # accent lip around the nose
    base = g.mixc(nose, base, (0.55, 0.012, 0.09))
    base, height = seams(g, base, spec)
    base, rough, metal, _ = grime(g, base, rough, spec, 0.55)
    base, rough = wear_and_dust(g, base, rough)
    emit = underglow(g, spec, CYAN)
    emit = _add_emit(g, emit, _scale(MAGENTA, 0.45), g.add(stripe, nose))  # lit accent: the sedan's night signature
    return finish_paint(g, base, rough, metal, height, emit)


def paint_taxi(g, spec, decals):
    base, rough = paint_base(g, (0.78, 0.40, 0.012), 0.32, 0.08)
    side = _side(g)
    skirt = g.maprange(g.z, 0.44, 0.40)                              # black lower body
    base = g.mixc(skirt, base, (0.015, 0.015, 0.016))
    pin = g.mul(g.band(g.z, 0.62, 0.65, 0.004), side)                 # black pinstripe
    base = g.mixc(pin, base, (0.015, 0.015, 0.016))
    base, emit = ink(g, base, None, decals["taxi_door"], side_uv(g, -0.55, 0.67, 0.9, 0.26), side)
    base, height = seams(g, base, spec)
    base, rough, metal, _ = grime(g, base, rough, spec, 0.35)
    base, rough = wear_and_dust(g, base, rough)
    emit = _add_emit(g, emit, underglow(g, spec, AMBER), 1.0)
    return finish_paint(g, base, rough, metal, height, emit)


def paint_van(g, spec, decals):
    base, rough = paint_base(g, (0.50, 0.48, 0.43), 0.38, 0.08)
    side = _side(g)
    skirt = g.maprange(g.z, 0.62, 0.58)
    base = g.mixc(skirt, base, GUNMETAL)
    cargo = g.mul(g.band(g.y, -3.12, 1.10, 0.004), side)
    diag = g.add(g.y, g.mul(g.z, 0.8))                                # amber livery band, slanted
    band = g.mul(g.band(diag, -1.2, -0.45, 0.006), g.mul(cargo, g.maprange(g.z, 0.62, 0.66)))
    base = g.mixc(band, base, (0.70, 0.30, 0.01))
    base, emit = ink(g, base, None, decals["van_logo"], side_uv(g, -0.75, 0.86, 3.4, 1.15), cargo)
    marker = g.mul(g.band(g.z, 2.30, 2.35, 0.004), cargo)             # amber clearance strip under the roof edge
    emit = _add_emit(g, emit, _scale(AMBER, 0.9), marker)
    base = g.mixc(marker, base, (0.8, 0.5, 0.2))
    base, height = seams(g, base, spec)
    base, rough, metal, _ = grime(g, base, rough, spec, 0.25)
    base, rough = wear_and_dust(g, base, rough)
    emit = _add_emit(g, emit, underglow(g, spec, AMBER), 1.0)
    return finish_paint(g, base, rough, metal, height, emit)


def paint_patrol(g, spec, decals):
    base, rough = paint_base(g, (0.008, 0.010, 0.020), 0.24)
    side = _side(g)
    doors = g.mul(g.mul(g.band(g.y, -1.30, 1.25, 0.006), g.band(g.z, 0.46, 0.76, 0.006)), side)
    base = g.mixc(doors, base, (0.62, 0.63, 0.64))
    base, emit = ink(g, base, None, decals["patrol_side"], side_uv(g, -0.05, 0.46, 2.3, 0.30), doors)
    strip = g.mul(g.band(g.z, 0.415, 0.44, 0.003), side)              # reflective cyan strip, faintly lit
    base = g.mixc(strip, base, (0.05, 0.45, 0.55))
    emit = _add_emit(g, emit, _scale(CYAN, 0.35), strip)
    base, height = seams(g, base, spec)
    base, rough, metal, _ = grime(g, base, rough, spec, 0.55)
    base, rough = wear_and_dust(g, base, rough)
    emit = _add_emit(g, emit, underglow(g, spec, CYAN), 1.0)
    return finish_paint(g, base, rough, metal, height, emit)


def paint_bus(g, spec, decals):
    base, rough = paint_base(g, (0.44, 0.43, 0.41), 0.36, 0.08)
    side = _side(g)
    lower = g.maprange(g.z, 1.36, 1.32)                               # transit teal below the windows
    base = g.mixc(lower, base, (0.010, 0.085, 0.10))
    line = g.mul(g.band(g.z, 1.20, 1.27, 0.004), side)                # cyan line under the window band
    base = g.mixc(line, base, (0.04, 0.42, 0.50))
    emit = _add_emit(g, None, _scale(CYAN, 0.30), line)
    skirt = g.maprange(g.z, 0.66, 0.62)
    base = g.mixc(skirt, base, GUNMETAL)
    body = g.band(g.y, -5.5, 5.0, 0.01)
    base, emit = ink(g, base, emit, decals["bus_side"], side_uv(g, -0.4, 0.66, 4.6, 0.55), g.mul(side, body))
    base, height = seams(g, base, spec)
    base, rough, metal, _ = grime(g, base, rough, spec, 0.30)
    base, rough = wear_and_dust(g, base, rough)
    emit = _add_emit(g, emit, underglow(g, spec, CYAN), 1.0)
    return finish_paint(g, base, rough, metal, height, emit)


PAINT = {"aircar_sedan": paint_sedan, "aircar_taxi": paint_taxi, "hover_van": paint_van,
         "patrol_cruiser": paint_patrol, "sky_bus": paint_bus}


# ---------------------------------------------------------------------------------------
# Other slots
# ---------------------------------------------------------------------------------------
def trim(g, spec):
    """Dark gunmetal: belly, pods, bezels, struts. Sooty toward the nozzles."""
    base = g.scale_color(GUNMETAL, g.add(0.75, g.mul(g.noise(2.0, 2.0, 0.5), 0.5)))
    rough = g.add(0.42, g.mul(g.sub(g.noise(4.0, 2.0, 0.5), 0.5), 0.15))
    soot = g.mul(g.maprange(g.z, spec["belly"] + 0.05, 0.0), g.maprange(g.noise(5.0, 2.0, 0.6), 0.25, 0.65))
    base = g.mixc(g.mul(soot, 0.85), base, (0.006, 0.006, 0.006))
    rough = g.add(rough, g.mul(soot, 0.25))
    edge = wear.convex_edges(g, radius=0.01, lo=0.05, hi=0.3)
    base, rough = wear.edge_wear(g, base, rough, edge, 1.0, (0.20, 0.21, 0.22), amount=0.35, rough_delta=-0.05)
    return g.finish(base, rough, g.sub(0.7, g.mul(soot, 0.5)))


def glass(g, glow=0.012):
    """Dark tinted cabin glass: glossy, a faint rain/dirt haze toward the bottom
    edge, a dim warm interior glow."""
    haze = g.mul(g.maprange(g.noise(1.2, 2.0, 0.5), 0.4, 0.7), 0.5)
    base = g.mixc(g.mul(haze, 0.35), (0.006, 0.007, 0.009), (0.03, 0.03, 0.032))
    rough = g.add(0.04, g.mul(haze, 0.10))
    lit = g.add(0.6, g.mul(g.maprange(g.noise(0.8, 1.0, 0.5), 0.3, 0.7), 0.4))
    g.finish(base, rough, 0.0)
    set_emission(g, g.mixc(g.mul(lit, glow), BLACK, CABIN_GLASS), EMISSION)
    return g.mat


def bus_glass(g, spec):
    """Passenger windows: lit cells between dark pillars, each cell its own
    brightness, a brighter ceiling strip, soft seated silhouettes low down."""
    y0, period, pillar = spec["window_y0"], spec["window_period"], 0.16
    zs, zg = spec["belt"], spec["glass_top"]
    cell_t = g.mul(g.sub(g.y, y0), 1.0 / period)
    t = g.math("FRACT", cell_t)
    cell = g.math("FLOOR", cell_t)
    win = g.mul(g.band(t, pillar / period, 1.0, 0.004), g.band(g.z, zs + 0.08, zg - 0.10, 0.008))
    rnd = g.noise(1.0, 0.0, 0.5, g.combine(g.mul(cell, 3.17), g.mul(g.sign(g.nx), 5.3), 0.4))
    level = g.maprange(rnd, 0.3, 0.7, 0.55, 1.0)
    grad = g.maprange(g.z, zs + 0.1, zg - 0.12, 0.65, 1.0)
    ceiling = g.mul(g.band(g.z, zg - 0.22, zg - 0.13, 0.02), 0.35)
    heads = g.maprange(g.noise(1.0, 0.0, 0.5, g.combine(g.mul(g.y, 2.3), g.mul(g.sign(g.nx), 7.0), 0.0)), 0.5, 0.58)
    heads = g.mul(heads, g.band(g.z, zs + 0.18, zs + 0.62, 0.08))
    lit = g.mul(g.mul(win, level), g.add(g.mul(grad, g.sub(1.0, g.mul(heads, 0.7))), ceiling))
    base = g.mixc(win, (0.010, 0.011, 0.013), (0.09, 0.08, 0.07))
    g.finish(base, g.mixf(win, 0.45, 0.06), 0.0)
    set_emission(g, g.mixc(g.mul(lit, 0.40), BLACK, CABIN_WARM), EMISSION)
    return g.mat


def lamp(g, albedo, emit):
    g.finish(albedo, 0.10, 0.0)
    set_emission(g, emit, EMISSION)
    return g.mat


def thruster(g, color, hot):
    """Pod exhaust disc: colored glow ring, white-hot core (HOT_ATTR)."""
    h = g.attribute(HOT_ATTR)
    em = g.mixc(g.maprange(h, 0.2, 1.0), _scale(color, 0.8), hot)
    g.finish((0.25, 0.25, 0.26), 0.3, 0.0)
    set_emission(g, em, EMISSION)
    return g.mat


def taxi_sign(g, decals):
    is_side = g.maprange(_abs(g, g.nx), 0.5, 0.7)
    is_end = g.maprange(_abs(g, g.ny), 0.5, 0.7)
    sc, _ = decal(g, decals["taxi_sign_side"][0], *side_uv(g, -0.15, 1.51, 1.0, 0.28))
    se, _ = decal(g, decals["taxi_sign_side"][1], *side_uv(g, -0.15, 1.51, 1.0, 0.28))
    ec, _ = decal(g, decals["taxi_sign_end"][0], *end_uv(g, 0.0, 1.51, 0.26, 0.28))
    ee, _ = decal(g, decals["taxi_sign_end"][1], *end_uv(g, 0.0, 1.51, 0.26, 0.28))
    dark = (0.012, 0.012, 0.014)
    base = g.mixc(is_end, g.mixc(is_side, dark, sc), ec)
    emit = g.mixc(is_end, g.mixc(is_side, BLACK, se), ee)
    g.finish(base, 0.2, 0.0)
    set_emission(g, emit, EMISSION)
    return g.mat


def bus_sign(g, spec, decals):
    front = g.maprange(g.ny, 0.0, 0.3)
    fz, rz = spec["sign_front_z"], spec["sign_rear_z"]
    fc, _ = decal(g, decals["bus_destination"][0], *end_uv(g, 0.0, fz, 1.6, 0.26))
    fe, _ = decal(g, decals["bus_destination"][1], *end_uv(g, 0.0, fz, 1.6, 0.26))
    rc, _ = decal(g, decals["bus_rear"][0], *end_uv(g, 0.0, rz, 0.9, 0.30))
    re, _ = decal(g, decals["bus_rear"][1], *end_uv(g, 0.0, rz, 0.9, 0.30))
    g.finish(g.mixc(front, rc, fc), 0.2, 0.0)
    set_emission(g, g.mixc(front, re, fe), EMISSION)
    return g.mat


def build_materials(vehicle, offset, spec, decals):
    """{slot: Material} for one vehicle (only the slots it may use)."""

    def lg(slot):
        return LocalGraph(new_mat(f"src_{vehicle}_{slot}"), offset)

    hot_color = {"cyan": (CYAN, CYAN_HOT), "amber": (AMBER, AMBER_HOT)}[spec["thrust"]]
    mats = {
        "paint": PAINT[vehicle](lg("paint"), spec, decals),
        "trim": trim(lg("trim"), spec),
        "glass": glass(lg("glass"), spec.get("cabin_glow", 0.012)),
        "headlight": lamp(lg("headlight"), (0.75, 0.75, 0.74), HEADLIGHT),
        "taillight": lamp(lg("taillight"), (0.40, 0.012, 0.010), _scale(TAILLIGHT, 0.9)),
        "thruster": thruster(lg("thruster"), *hot_color),
        "marker": lamp(lg("marker"), (0.6, 0.35, 0.05), _scale(AMBER, 0.85)),
    }
    if vehicle == "patrol_cruiser":
        mats["bar_red"] = lamp(lg("bar_red"), (0.45, 0.02, 0.02), BAR_RED)
        mats["bar_blue"] = lamp(lg("bar_blue"), (0.02, 0.06, 0.45), BAR_BLUE)
    if vehicle == "aircar_taxi":
        mats["sign"] = taxi_sign(lg("sign"), decals)
    if vehicle == "sky_bus":
        mats["bus_glass"] = bus_glass(lg("bus_glass"), spec)
        mats["sign"] = bus_sign(lg("sign"), spec, decals)
    for m in mats.values():
        # The emission bake reads "Emission Color" whatever the strength, and
        # Principled's default is white: non-emissive sources must say black.
        sock = m.node_tree.nodes["BSDF"].inputs["Emission Color"]
        if not sock.is_linked and m.node_tree.nodes["BSDF"].inputs["Emission Strength"].default_value == 0.0:
            sock.default_value = (0.0, 0.0, 0.0, 1.0)
    return mats
