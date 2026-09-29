"""Stage 1: build the nightstand, drawer and table lamp with procedural source materials, save.

  blender -b --factory-startup --python blender/props/nightstand__opus-high/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from nightstand_common import (  # noqa: E402
    BACK_Y0, BASE_H, BASE_R, BLEND, BOTTOM_Z1, BOX_BACK_Y, BOX_BOTTOM_T, BOX_SIDE, BOX_X, BOX_Z0, BOX_Z1,
    BULB_CENTER_Z, BULB_R, CASE_Z0, CORD_R, DIV_Z0, DIV_Z1, DRAWER_ORIGIN, FRONT_H, FRONT_T, FRONT_W,
    GLIDE_H, H, HANDLE_GRIP, HX, HY, IN_X, LAMP_POS, LEG_BOTTOM, LEG_INSET, LEG_TOP, PLATE, PULL_CENTERS,
    PULL_LEN, PULL_R, PULL_Y, PULL_Z, RUN_BODY_X0, RUN_DRAWER_X1, RUN_Z0, RUN_Z1, SHADE_R0, SHADE_R1,
    SHADE_Z0, SHADE_Z1, SOCKET_R, SOCKET_Z0, SOCKET_Z1, STEM_R, T_BACK, TOP_Z0, WASHER_R, WASHER_Z,
)
from lib_candidates import (  # noqa: E402
    braided_cord, brushed_metal, bm_lathe, bm_tube, convex_edges, cup_ring, set_grain, smooth_path,
    wood_veneer,
)
from arcology_blender import fabric, materials, wear  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    assign_by_region, bm_box, bm_cyl, collision_box, cyl_x, cyl_y, finish, join, new_empty, new_object,
    shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

# Shared set colors (linear)
WALNUT_MID = (0.036, 0.019, 0.011)
WALNUT_DARK = (0.012, 0.0062, 0.0040)
WALNUT_LIGHT = (0.072, 0.040, 0.022)
WALNUT_WORN = (0.105, 0.066, 0.040)     # finish rubbed through at edges
GUNMETAL = (0.085, 0.090, 0.100)         # metallic F0 reading as #2E3238 in a room
STEEL_BARE = (0.36, 0.37, 0.39)          # coating worn through
LINEN = (0.686, 0.644, 0.552)            # #D8D2C4
WARM_2700K = (1.0, 0.40, 0.095)          # 2700 K, linear sRGB


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def walnut_common(g, rough_base=0.44):
    base, rough, h = wood_veneer(g, WALNUT_MID, WALNUT_DARK, WALNUT_LIGHT, rough=rough_base)
    edge = convex_edges(g, radius=0.0025)
    return base, rough, h, edge


def mat_walnut_body():
    """Case: satin walnut, softly worn convex edges, a mug ring on the top
    (front left, where the lamp isn't), faint dust on the top."""
    g = Graph(new_mat("src_walnut_body"))
    base, rough, h, edge = walnut_common(g)
    # front edges wear more than the back
    front = g.maprange(g.y, 0.0, -0.19)
    e = g.mul(edge, g.add(0.35, g.mul(front, 0.45)))
    base = g.mixc(g.mul(e, 0.55), base, WALNUT_WORN)
    rough = g.add(rough, g.mul(e, 0.10))
    base, rough = cup_ring(g, base, rough, (-0.105, -0.080), 0.037, width=0.003, z_band=(H - 0.002, H + 0.002),
                           strength=0.20, duller=0.16, broken=1.2)
    base, rough = wear.top_dust(g, base, rough, H - 0.004, H - 0.001, color=(0.16, 0.15, 0.14),
                                amount=0.05, rougher=0.08)
    # open shelf floor: a little grime and rub where things get pushed in
    shelf = g.mul(g.band(g.z, BOTTOM_Z1 - 0.002, BOTTOM_Z1 + 0.002, 0.001), g.maprange(g.nz, 0.8, 0.95))
    rub = g.mul(shelf, g.mul(g.maprange(g.y, 0.05, -0.18), g.maprange(g.noise(14.0, 2.0), 0.4, 0.7)))
    rough = g.sub(rough, g.mul(rub, 0.10))
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_walnut_drawer():
    """Drawer: the same veneer; the finish around the pull is rubbed glossy by
    fingers, the front's top edge is worn light at the center (where fingers
    catch it when the pull is ignored), fingerprints on the front."""
    g = Graph(new_mat("src_walnut_drawer"))
    base, rough, h, edge = walnut_common(g)
    zc = DRAWER_ORIGIN.z + PULL_Z
    front = g.maprange(g.y, DRAWER_ORIGIN.y + 0.002, DRAWER_ORIGIN.y + 0.0005)
    near_pull = g.mul(g.band(g.x, -0.10, 0.10, 0.06), g.band(g.z, zc - 0.035, zc + 0.035, 0.04))
    top_edge = g.mul(g.band(g.x, -0.13, 0.13, 0.06), g.maprange(g.z, zc + 0.05, DRAWER_ORIGIN.z + FRONT_H))
    e = g.mul(edge, g.add(0.18, g.add(g.mul(top_edge, 1.4), g.mul(near_pull, 0.8))))
    base = g.mixc(g.mul(e, 0.6), base, WALNUT_WORN)
    rough = g.add(rough, g.mul(e, 0.08))
    polish = g.mul(g.mul(near_pull, front), g.maprange(g.noise(9.0, 2.0), 0.3, 0.7))
    rough = g.sub(rough, g.mul(polish, 0.12))
    base = g.scale_color(base, g.add(1.0, g.mul(polish, 0.10)))
    region = g.mul(front, g.band(g.z, zc - 0.05, zc + 0.07, 0.03))
    region = g.mul(region, g.band(g.x, -0.14, 0.14, 0.05))
    base, rough = wear.smudges(g, base, rough, region, rougher=0.10, darker=0.04)
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_gunmetal(name, axis="Z", center=None, grip=None, floor=False):
    """Brushed gunmetal: dark metallic coating, worn to bare steel on convex
    edges; `grip` = (x0, x1, z0, z1) world region rubbed bright (a pull's
    center); `floor` adds scuffs and grime at the bottom (legs)."""
    g = Graph(new_mat(f"src_{name}"))
    rough, h = brushed_metal(g, 0.34, axis=axis, center=center)
    base = GUNMETAL
    edge = convex_edges(g, radius=0.0015)
    base = g.mixc(g.mul(edge, 0.30), base, STEEL_BARE)
    rough = g.sub(rough, g.mul(edge, 0.08))
    if grip is not None:
        x0, x1, z0, z1 = grip
        rub = g.mul(g.band(g.x, x0, x1, 0.02), g.band(g.z, z0, z1, 0.004))
        rub = g.mul(rub, g.maprange(g.noise(60.0, 2.0), 0.3, 0.6))
        base = g.mixc(g.mul(rub, 0.35), base, STEEL_BARE)
        rough = g.sub(rough, g.mul(rub, 0.10))
    if floor:
        base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.06, z_full=0.01, rougher=0.25, darker=0.2)
        base = wear.floor_grime(g, base, 0.0, 0.03, 0.7)
    return g.finish(base, rough, 1.0, g.bump(h, 1.0, 1.0))


def mat_runner():
    """Black zinc-plated steel drawer runners."""
    g = Graph(new_mat("src_runner"))
    r = g.add(0.38, g.mul(g.sub(g.noise(30.0), 0.5), 0.1))
    return g.finish((0.05, 0.05, 0.055), r, 0.85, None)


def mat_cap():
    """Aluminium E27 bulb cap."""
    g = Graph(new_mat("src_cap"))
    r, h = brushed_metal(g, 0.30, axis="Z", streak=0.04)
    return g.finish((0.62, 0.62, 0.63), r, 1.0, g.bump(h, 1.0, 1.0))


def mat_cord():
    g = Graph(new_mat("src_cord"))
    base, rough, h = braided_cord(g, (0.028, 0.027, 0.026))
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_shade():
    """Linen drum shade: slub linen outside, a smooth white liner inside,
    bound rims, an overlap seam at the back. Emission Color carries the
    glow pattern for the LampLight emission atlas (glow attribute: outer
    wall, inner liner, rims), brighter near the bulb, darker at the seam."""
    g = Graph(new_mat("src_shade"))
    glow = g.attribute("glow")
    inner = g.maprange(glow, 0.5, 0.6)
    rim = g.maprange(glow, 0.2, 0.1)
    base, rough, h = fabric.fabric_base(g, LINEN, rough=0.92, heather=0.04, slub=0.07, mottle=0.05,
                                        weave=0.00018, slub_height=0.00016)
    base = g.mixc(inner, base, (0.80, 0.78, 0.72))
    rough = g.mixf(inner, rough, 0.62)
    h = g.mixf(inner, h, 0.0)
    # rim binding: slightly darker, denser tape
    base = g.scale_color(base, g.sub(1.0, g.mul(rim, 0.08)))
    # overlap seam at the back (+Y), 8 mm wide, a small ridge
    lx, ly = LAMP_POS.x, LAMP_POS.y
    seam = g.mul(g.band(g.x, lx - 0.004, lx + 0.004, 0.0008), g.maprange(g.y, ly + 0.05, ly + 0.08))
    h = g.add(h, g.mul(seam, 0.0002))
    base = g.scale_color(base, g.sub(1.0, g.mul(seam, 0.05)))
    # glow: thin spots of the weave glow brighter; brightest level with the bulb
    zb = LAMP_POS.z + BULB_CENTER_Z
    level = g.maprange(g.math("ABSOLUTE", g.sub(g.z, zb)), 0.02, 0.12, 1.0, 0.72)
    weave = g.sub(1.25, g.mul(g.noise(95.0, 2.0, 0.6), 0.5))
    k = g.mul(g.mul(glow, level), g.mixf(inner, weave, 1.0))
    k = g.mul(k, g.sub(1.0, g.mul(seam, 0.45)))
    g._set(g.bsdf.inputs["Emission Color"], g.scale_color(WARM_2700K, k))
    return fabric.fabric_finish(g, base, rough, h)


def mat_bulb():
    """Frosted G45 globe, glowing fully (dimmer toward the neck)."""
    g = Graph(new_mat("src_bulb"))
    zn = LAMP_POS.z + BULB_CENTER_Z - BULB_R
    k = g.maprange(g.z, zn - 0.004, zn + 0.012, 0.35, 1.0)
    g._set(g.bsdf.inputs["Emission Color"], g.scale_color(WARM_2700K, k))
    return g.finish((0.86, 0.85, 0.82), 0.35, 0.0, None)


def build_materials():
    grip_z = DRAWER_ORIGIN.z + PULL_Z
    return {
        "walnut": mat_walnut_body(),
        "walnut_drawer": mat_walnut_drawer(),
        "legs": mat_gunmetal("gunmetal_legs", axis="Z", floor=True),
        "pull": mat_gunmetal("gunmetal_pull", axis="X", grip=(-0.035, 0.035, grip_z - 0.008, grip_z + 0.008)),
        "lamp_base": mat_gunmetal("gunmetal_lamp_base", center=(LAMP_POS.x, LAMP_POS.y)),
        "lamp_stem": mat_gunmetal("gunmetal_lamp_stem", axis="Z"),
        "runner": mat_runner(),
        "dark": materials.dark_plastic("dark", base=(0.03, 0.03, 0.032), rough=0.5),
        "rubber": materials.rubber("rubber", base=(0.035, 0.035, 0.035), rough=0.7),
        "cap": mat_cap(),
        "cord": mat_cord(),
        "shade": mat_shade(),
        "bulb": mat_bulb(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
AXIS = {"x": 0, "y": 1, "z": 2}


def board(name, lo, hi, coll, mat, grain, thick, seed, bevel=0.0018, parent=None, face=1):
    """A veneered board: beveled box with its grain frame as attributes.

    grain/thick: axis the grain runs along / through the thickness. face:
    +1/-1 = the side of the thickness axis that shows most (the log axis
    of the growth rings sits behind it)."""
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    ob = new_object(name, bm, coll, material=mat, parent=parent)
    finish(ob, bevel, 2)
    u, b = AXIS[grain], AXIS[thick]
    a = 3 - u - b
    # frame positions in world meters (parents only translate)
    off = parent.location if parent is not None else Vector((0, 0, 0))
    lo_w, hi_w = Vector(lo) + off, Vector(hi) + off
    size_a = hi_w[a] - lo_w[a]
    a0 = (lo_w[a] + hi_w[a]) / 2 + (seed - 0.5) * 0.5 * size_a
    b0 = (lo_w[b] + hi_w[b]) / 2 - face * 0.045
    set_grain(ob, u, b, seed, a0, b0)
    return ob


def mesh(name, bm, coll, mat, bevel=None, segs=2, parent=None, sharp=30.0):
    ob = new_object(name, bm, coll, material=mat, parent=parent)
    if bevel:
        finish(ob, bevel, segs, sharp_angle=sharp)
    else:
        shade(ob, sharp)
    return ob


def tapered_leg(bm, cx, cy, z0, z1, top, bottom):
    verts = bm_box(bm, (cx - top / 2, cy - top / 2, z0), (cx + top / 2, cy + top / 2, z1))
    s = bottom / top
    for v in verts:
        if v.co.z < (z0 + z1) / 2:
            v.co.x = cx + (v.co.x - cx) * s
            v.co.y = cy + (v.co.y - cy) * s


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------
def build_body(coll, col_coll, mats):
    wal = mats["walnut"]
    parts = [
        board("Top", (-HX, -HY, TOP_Z0), (HX, HY, H), coll, wal, "x", "z", 0.1),
        board("SideL", (-HX, -HY, CASE_Z0), (-IN_X, HY, TOP_Z0), coll, wal, "z", "x", 0.4, face=-1),
        board("SideR", (IN_X, -HY, CASE_Z0), (HX, HY, TOP_Z0), coll, wal, "z", "x", 0.7),
        board("Bottom", (-IN_X, -HY, CASE_Z0), (IN_X, BACK_Y0, BOTTOM_Z1), coll, wal, "x", "z", 0.25),
        board("Divider", (-IN_X, -HY, DIV_Z0), (IN_X, BACK_Y0, DIV_Z1), coll, wal, "x", "z", 0.55),
        board("Back", (-IN_X, BACK_Y0, CASE_Z0), (IN_X, HY, TOP_Z0), coll, wal, "x", "y", 0.85, bevel=0.0012, face=-1),
    ]
    # Drawer runners (fixed members) on the side walls
    bm = bmesh.new()
    z0 = DRAWER_ORIGIN.z + RUN_Z0 - 0.003
    z1 = DRAWER_ORIGIN.z + RUN_Z1 + 0.003
    for s in (-1, 1):
        xa, xb = sorted((s * RUN_BODY_X0, s * IN_X))
        bm_box(bm, (xa, -HY + FRONT_T + 0.002, z0), (xb, BACK_Y0 - 0.008, z1))
    parts.append(mesh("Runners", bm, coll, mats["runner"], 0.0008, 1))

    # Legs: mounting plate, tapered square tube, glide
    lx, ly = HX - LEG_INSET, HY - LEG_INSET
    bm_leg, bm_plate, bm_glide = bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * lx, sy * ly
            bm_box(bm_plate, (cx - PLATE / 2, cy - PLATE / 2, CASE_Z0 - 0.003), (cx + PLATE / 2, cy + PLATE / 2, CASE_Z0))
            tapered_leg(bm_leg, cx, cy, GLIDE_H, CASE_Z0 - 0.003, LEG_TOP, LEG_BOTTOM)
            bm_cyl(bm_glide, 0.0075, GLIDE_H + 0.001, Matrix.Translation((cx, cy, (GLIDE_H + 0.001) / 2)), 12)
    parts.append(mesh("LegPlates", bm_plate, coll, mats["legs"], 0.0008, 1))
    parts.append(mesh("Legs", bm_leg, coll, mats["legs"], 0.0015, 2))
    parts.append(mesh("Glides", bm_glide, coll, mats["rubber"], 0.001, 1))

    body = join(parts, "Nightstand")
    tag(body, "body")

    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColTop", (-HX, -HY, TOP_Z0), (HX, HY, H))
    col("ColSideL", (-HX, -HY, CASE_Z0), (-IN_X, HY, TOP_Z0))
    col("ColSideR", (IN_X, -HY, CASE_Z0), (HX, HY, TOP_Z0))
    col("ColBack", (-IN_X, BACK_Y0, CASE_Z0), (IN_X, HY, TOP_Z0))
    col("ColBottom", (-IN_X, -HY, CASE_Z0), (IN_X, BACK_Y0, BOTTOM_Z1))
    col("ColShelf", (-IN_X, -HY, DIV_Z0), (IN_X, BACK_Y0, DIV_Z1))
    for sx, sn in ((-1, "L"), (1, "R")):
        for sy, fn in ((-1, "F"), (1, "B")):
            cx, cy = sx * lx, sy * ly
            col(f"ColLeg{fn}{sn}", (cx - LEG_TOP / 2, cy - LEG_TOP / 2, 0.0), (cx + LEG_TOP / 2, cy + LEG_TOP / 2, CASE_Z0))
    return body


# ---------------------------------------------------------------------------
# Drawer (drawer-local coordinates: origin at the front's bottom center, box toward +Y)
# ---------------------------------------------------------------------------
def build_drawer(coll, mats):
    wal = mats["walnut_drawer"]
    fw = FRONT_W / 2
    ix = BOX_X - BOX_SIDE
    root = board("Drawer", (-fw, 0.0, 0.0), (fw, FRONT_T, FRONT_H), coll, wal, "x", "y", 0.33, bevel=0.0015,
                 face=-1)
    root.location = DRAWER_ORIGIN  # geometry is drawer-local
    set_grain(root, 0, 1, 0.33, DRAWER_ORIGIN.z + FRONT_H * 0.42, DRAWER_ORIGIN.y + FRONT_T / 2 + 0.045)
    parts = [root]
    parts.append(board("DrawerSideL", (-BOX_X, FRONT_T, BOX_Z0), (-ix, BOX_BACK_Y, BOX_Z1), coll, wal,
                       "y", "x", 0.61, bevel=0.0015, parent=root))
    parts.append(board("DrawerSideR", (ix, FRONT_T, BOX_Z0), (BOX_X, BOX_BACK_Y, BOX_Z1), coll, wal,
                       "y", "x", 0.92, bevel=0.0015, parent=root))
    parts.append(board("DrawerBack", (-ix, BOX_BACK_Y - BOX_SIDE, BOX_Z0), (ix, BOX_BACK_Y, BOX_Z1 - 0.004),
                       coll, wal, "x", "y", 0.18, bevel=0.0015, parent=root))
    parts.append(board("DrawerBottom", (-ix, FRONT_T, BOX_Z0), (ix, BOX_BACK_Y - BOX_SIDE, BOX_Z0 + BOX_BOTTOM_T),
                       coll, wal, "y", "z", 0.47, bevel=0.001, parent=root))
    # Moving runner members
    bm = bmesh.new()
    for s in (-1, 1):
        xa, xb = sorted((s * BOX_X, s * RUN_DRAWER_X1))
        bm_box(bm, (xa, FRONT_T + 0.006, RUN_Z0), (xb, BOX_BACK_Y - 0.006, RUN_Z1))
    parts.append(mesh("DrawerRunners", bm, coll, mats["runner"], 0.0008, 1, parent=root))
    # Bar pull on two standoffs
    bm = bmesh.new()
    bm_cyl(bm, PULL_R, PULL_LEN, cyl_x((0.0, PULL_Y, PULL_Z)), 20)
    parts.append(mesh("PullBar", bm, coll, mats["pull"], 0.0025, 3, parent=root))
    bm = bmesh.new()
    for x in (-PULL_CENTERS / 2, PULL_CENTERS / 2):
        depth = abs(PULL_Y) + 0.001
        bm_cyl(bm, 0.0042, depth, cyl_y((x, PULL_Y / 2 + 0.0005, PULL_Z)), 16)
        # a thin rosette where the standoff meets the front
        bm_cyl(bm, 0.0062, 0.0016, cyl_y((x, -0.0008 + 0.0001, PULL_Z)), 16)
    parts.append(mesh("PullStandoffs", bm, coll, mats["pull"], 0.0006, 1, parent=root))
    drawer = join(parts, "Drawer")
    tag(drawer, "drawer")
    tag(new_empty("HandleGrip", coll, HANDLE_GRIP, parent=drawer), "drawer")
    return drawer


# ---------------------------------------------------------------------------
# Lamp (lamp-local coordinates: origin at the base's bottom center)
# ---------------------------------------------------------------------------
def shade_profile():
    """Closed r/z cross-section of the drum shade: outer wall up, top rim,
    inner liner down, bottom rim. Returns (points, glow per point)."""
    wall = 0.0012
    rb = 0.0026

    def radius(z):
        return SHADE_R0 + (SHADE_R1 - SHADE_R0) * (z - SHADE_Z0) / (SHADE_Z1 - SHADE_Z0)

    pts, glow = [], []
    OUT, IN, RIM = 0.30, 0.75, 0.08

    def bead(cr, cz, angles, g_mid, g_ends):
        for i, a in enumerate(angles):
            t = math.radians(a)
            pts.append((cr + rb * math.cos(t), cz + rb * math.sin(t)))
            glow.append(g_ends[0] if i == 0 else g_ends[1] if i == len(angles) - 1 else g_mid)

    zb, zt = SHADE_Z0 + rb, SHADE_Z1 - rb
    rbot, rtop = radius(zb) - wall / 2, radius(zt) - wall / 2
    bead(rbot, zb, (-90, -30, 20, 60), RIM, (RIM, OUT))
    for f in (0.30, 0.55, 0.80):  # extra outer rings: smoother glow gradient and silhouette
        z = SHADE_Z0 + f * (SHADE_Z1 - SHADE_Z0)
        pts.append((radius(z), z))
        glow.append(OUT)
    bead(rtop, zt, (-60, -20, 30, 90, 150, 200, 240), RIM, (OUT, IN))
    for f in (0.80, 0.30):
        z = SHADE_Z0 + f * (SHADE_Z1 - SHADE_Z0)
        pts.append((radius(z) - wall, z))
        glow.append(IN)
    bead(rbot, zb, (120, 160, 210), RIM, (IN, RIM))
    return pts, glow


def build_lamp(coll, mats):
    # Base: weighted disc with a softly rounded rim and a slight dome
    prof = [(0.0, 0.0), (0.066, 0.0), (0.0686, 0.0008), (0.0698, 0.0024), (BASE_R, 0.0042),
            (BASE_R, 0.0132), (0.0697, 0.0152), (0.0688, 0.0166), (0.0672, 0.0176), (0.0648, 0.0181),
            (0.036, 0.0186), (0.0, BASE_H + 0.0008)]
    bm = bmesh.new()
    bm_lathe(bm, prof, 56)
    root = new_object("TableLamp", bm, coll, material=mats["lamp_base"])
    root.location = LAMP_POS
    shade(root, 40.0)
    parts = [root]

    # Collar, stem, socket and bulb cap in one lathe
    prof = [(0.0, BASE_H), (0.0125, BASE_H), (0.0125, 0.0255), (0.0118, 0.0272), (0.0102, 0.0282),
            (STEM_R + 0.0008, 0.0286), (STEM_R, 0.0292), (STEM_R, SOCKET_Z0 - 0.0012),
            (STEM_R + 0.0012, SOCKET_Z0 - 0.0004), (0.0158, SOCKET_Z0), (SOCKET_R - 0.0004, SOCKET_Z0 + 0.0006),
            (SOCKET_R, SOCKET_Z0 + 0.002), (SOCKET_R, SOCKET_Z1 - 0.002), (SOCKET_R - 0.0006, SOCKET_Z1 - 0.0004),
            (0.0160, SOCKET_Z1), (0.0132, SOCKET_Z1), (0.0132, SOCKET_Z1 + 0.003),
            (0.0134, SOCKET_Z1 + 0.005), (0.0130, SOCKET_Z1 + 0.007), (0.0134, SOCKET_Z1 + 0.009),
            (0.0130, SOCKET_Z1 + 0.011), (0.0126, SOCKET_Z1 + 0.014), (0.0, SOCKET_Z1 + 0.014)]
    bm = bmesh.new()
    bm_lathe(bm, prof, 24)
    stem = new_object("Stem", bm, coll, material=mats["lamp_stem"], parent=root)
    shade(stem, 40.0)
    assign_by_region(stem, [(((-1, -1, SOCKET_Z1 + 0.0005), (1, 1, 1)), mats["cap"])], mats["lamp_stem"])
    parts.append(stem)

    # Shade fitter: washer and the threaded ring that clamps it, three wire spokes
    bm = bmesh.new()
    bm_lathe(bm, [(SOCKET_R + 0.0002, WASHER_Z - 0.001), (WASHER_R, WASHER_Z - 0.001), (WASHER_R, WASHER_Z + 0.001),
                  (SOCKET_R + 0.0002, WASHER_Z + 0.001)], 32, closed=True)
    bm_lathe(bm, [(SOCKET_R + 0.0002, WASHER_Z + 0.001), (0.0205, WASHER_Z + 0.001), (0.0212, WASHER_Z + 0.0025),
                  (0.0205, WASHER_Z + 0.006), (SOCKET_R + 0.0002, WASHER_Z + 0.006)], 24, closed=True)
    for a in (30.0, 150.0, 270.0):
        t = math.radians(a)
        d = Vector((math.cos(t), math.sin(t), 0.0))
        p0 = d * (WASHER_R - 0.002) + Vector((0, 0, WASHER_Z))
        p1 = d * (SHADE_R0 - 0.0035) + Vector((0, 0, SHADE_Z0 + 0.0026))
        bm_tube(bm, [p0, p0.lerp(p1, 0.5), p1], 0.0012, 6, along_attr=None, around_attrs=None)
    parts.append(mesh("Fitter", bm, coll, mats["lamp_stem"], parent=root, sharp=40.0))

    # Push switch on the base, front
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, 0.0180), (0.0078, 0.0180), (0.0078, 0.0196), (0.0060, 0.0198), (0.0058, 0.0212),
                  (0.0050, 0.0222), (0.0, 0.0225)], 20, center=(0.0, -0.043, 0.0))
    parts.append(mesh("Switch", bm, coll, mats["dark"], parent=root, sharp=40.0))

    # Cord: strain relief grommet at the back of the base, braided cord over the back edge
    edge_y = HY - LAMP_POS.y                  # the top's back edge in lamp coordinates
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, -0.004), (0.0045, -0.004), (0.0045, 0.004), (0.0038, 0.009), (0.0032, 0.012),
                  (0.0, 0.012)], 16)
    bmesh.ops.transform(bm, verts=bm.verts, matrix=Matrix.Translation((0.0, BASE_R - 0.002, 0.0085))
                        @ Matrix.Rotation(math.radians(-90), 4, "X"))
    parts.append(mesh("Grommet", bm, coll, mats["rubber"], parent=root, sharp=40.0))

    r = CORD_R
    ctrl = [(0.0, BASE_R - 0.006, 0.0085), (0.0, BASE_R + 0.010, 0.0085), (0.001, BASE_R + 0.022, 0.0068),
            (0.004, BASE_R + 0.036, r + 0.0006), (0.009, 0.122, r), (0.011, 0.138, r), (0.009, edge_y - 0.004, r)]
    for a in (0.0, 35.0, 70.0, 90.0):         # wrap around the edge (2 mm bevel) at a cord radius
        t = math.radians(a)
        ctrl.append((0.008, edge_y - 0.0012 + (r + 0.0012) * math.sin(t), -0.0012 + (r + 0.0012) * math.cos(t)))
    hang_y = edge_y + r + 0.0006
    ctrl += [(0.007, hang_y, -0.03), (0.004, hang_y + 0.0004, -0.12), (-0.002, hang_y + 0.001, -0.25),
             (-0.010, hang_y + 0.002, -0.38), (-0.020, hang_y + 0.004, -0.50)]
    path = smooth_path(ctrl, 5)
    bm = bmesh.new()
    bm_tube(bm, path, r, 8)
    parts.append(mesh("Cord", bm, coll, mats["cord"], parent=root, sharp=50.0))

    lamp = join(parts, "TableLamp")
    tag(lamp, "lamp")

    # Shade and bulb: the LampLight part
    pts, glow = shade_profile()
    bm = bmesh.new()
    bm_lathe(bm, pts, 64, closed=True, attrs={"glow": glow}, start_angle=math.radians(90.0))
    shade_ob = new_object("LampShade", bm, coll, material=mats["shade"], parent=lamp)
    shade(shade_ob, 70.0)
    # G45 globe on a short neck into the cap
    zc = BULB_CENTER_Z
    prof = [(0.0, SOCKET_Z1 + 0.013), (0.0118, SOCKET_Z1 + 0.013), (0.0122, SOCKET_Z1 + 0.017)]
    for a in range(-58, 91, 12):
        t = math.radians(a)
        prof.append((BULB_R * math.cos(t), zc + BULB_R * math.sin(t)))
    prof[-1] = (0.0, zc + BULB_R)
    bm = bmesh.new()
    bm_lathe(bm, prof, 24)
    bulb = new_object("Bulb", bm, coll, material=mats["bulb"], parent=lamp)
    shade(bulb, 50.0)
    light = join([shade_ob, bulb], "LampShade")
    tag(light, "lamp_light")
    return lamp, light


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("NightstandBody"), get_collection("NightstandCollision"), mats)
    build_drawer(get_collection("NightstandDrawer"), mats)
    build_lamp(get_collection("TableLamp"), mats)
    body, col, drawer = part_tris("body"), part_tris("body_col"), part_tris("drawer")
    lamp, light = part_tris("lamp"), part_tris("lamp_light")
    print(f"TRIS body={body} collision={col} drawer={drawer} lamp={lamp} lamp_light={light} "
          f"render_total={body + drawer + lamp + light}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
