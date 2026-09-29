"""Stage 1: build the nightstand, drawer and table lamp with procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/nightstand_square/build.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from nightstand_common import (  # noqa: E402
    BACK_T, BACK_Y0, BASE_H, BASE_R, BLEND, BOTTOM_Z1, BOX_BOTTOM, BOX_HW, BOX_WALL, BOX_Y0, BOX_Y1,
    BOX_Z0, BOX_Z1, BULB_R, BULB_Z, CARC_Z0, CORD_R, DIV_Z0, DIV_Z1, DRAWER_ORIGIN, FRONT_H, FRONT_HW,
    FRONT_T, H, HANDLE_GRIP, HX, HY, INNER_X, LAMP_ORIGIN, LEG_H, LEG_INSET, LEG_S, PANEL, PULL_LEN,
    PULL_R, PULL_STANDOFF_R, PULL_Y, PULL_Z, RAIL_H, RAIL_W, RAIL_X, RAIL_Y0, RAIL_Y1, SHADE_R0,
    SHADE_R1, SHADE_T, SHADE_Z0, SHADE_Z1, SOCKET_R, SOCKET_Z0, SOCKET_Z1, STEM_R, STEM_Z1, TOP_Z0,
)
from lib_candidates import (  # noqa: E402
    bm_drum_shell, bm_tube, brushed_metal_layers, cup_ring, rubbed_finish, smooth_polyline,
    wood_veneer, wood_veneer_layers,
)
from arcology_blender import fabric, materials, wear  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    bm_box, bm_cyl, collision_box, cut, cyl_x, cyl_y, cyl_z, finish, new_empty, new_object,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

# Shared bedroom-set direction: dark walnut veneer, brushed gunmetal (#2E3238), warm off-white linen.
WALNUT_DARK = (0.026, 0.012, 0.0065)
WALNUT_LIGHT = (0.068, 0.034, 0.017)
ASH_DARK = (0.36, 0.27, 0.16)
ASH_LIGHT = (0.50, 0.40, 0.26)
GUNMETAL = (0.0273, 0.0319, 0.0395)  # #2E3238 in linear
LINEN = (0.70, 0.64, 0.52)  # warm off-white #D8D2C4, a touch warmer

CUP_RING = (0.11, -0.09, H)  # a mug's tide mark on the top, front right of the lamp


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_walnut_x():
    """Walnut with the grain along X (top, front, divider, bottom, back, drawer
    front): a cup ring and dust on the top, finish rubbed matte around the pull."""
    g = Graph(new_mat("src_walnut_x"))
    base, rough, height = wood_veneer_layers(g, WALNUT_DARK, WALNUT_LIGHT, "X", seed=0.37)
    base, rough = wear.edge_highlight(g, base, rough, smoother=-0.10, brighter=0.16)
    front = g.maprange(g.y, -0.190, -0.198)  # the drawer front's face (world y = -0.20)
    zc = DRAWER_ORIGIN.z + PULL_Z
    rub = g.mul(g.rect_xz((-0.11, zc - 0.035), (0.11, zc + 0.035), soft=0.045), front)
    base, rough = rubbed_finish(g, base, rough, rub, lighter=0.12, rougher=0.30)
    grease = g.mul(g.rect_xz((-0.10, zc - 0.018), (0.10, zc + 0.022), soft=0.02), front)
    base, rough = wear.smudges(g, base, rough, grease, rougher=-0.10, darker=0.10)
    base, rough = cup_ring(g, base, rough, CUP_RING, 0.041, width=0.006, amount=0.6)
    base, rough = wear.top_dust(g, base, rough, H - 0.005, H, color=(0.30, 0.28, 0.25), amount=0.10, rougher=0.20)
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))


def mat_walnut_z():
    """Walnut with vertical grain (the side panels)."""
    g = Graph(new_mat("src_walnut_z"))
    base, rough, height = wood_veneer_layers(g, WALNUT_DARK, WALNUT_LIGHT, "Z", seed=0.81)
    base, rough = wear.edge_highlight(g, base, rough, smoother=-0.10, brighter=0.16)
    base = wear.floor_grime(g, base, CARC_Z0, CARC_Z0 + 0.06, darkest=0.90)
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))


def mat_gunmetal(name, axis):
    """Brushed gunmetal, brushed along `axis`, edges polished by use."""
    g = Graph(new_mat(f"src_{name}"))
    base, rough, height = brushed_metal_layers(g, GUNMETAL, axis, rough=0.42)
    base, rough = wear.edge_highlight(g, base, rough, smoother=0.14, brighter=0.35)
    return g.finish(base, rough, 1.0, g.bump(height, 1.0, 1.0))


def mat_linen():
    """Warm off-white linen of the lamp shade (baked into LampLight, emissive later)."""
    g = Graph(new_mat("src_linen"))
    base, rough, h = fabric.fabric_base(g, LINEN, rough=0.88, heather=0.04, slub=0.07, mottle=0.06,
                                        weave=0.00030)
    # A little dust settles on the top rim and the upper outside.
    top = g.maprange(g.z, LAMP_ORIGIN.z + SHADE_Z1 - 0.05, LAMP_ORIGIN.z + SHADE_Z1)
    base = g.scale_color(base, g.sub(1.0, g.mul(top, 0.05)))
    return fabric.fabric_finish(g, base, rough, h)


def build_materials():
    return {
        "walnut_x": mat_walnut_x(),
        "walnut_z": mat_walnut_z(),
        "ash": wood_veneer("ash", ASH_DARK, ASH_LIGHT, "Y", rings_per_m=70.0, contrast=0.6, figure=0.05,
                           rough=0.55, pore_depth=0.00012),
        "gunmetal_z": mat_gunmetal("gunmetal_z", "Z"),
        "gunmetal_x": mat_gunmetal("gunmetal_x", "X"),
        "dark": materials.dark_plastic("dark"),
        "cord": materials.dark_plastic("cord", base=(0.030, 0.030, 0.033), rough=0.62),
        "linen": mat_linen(),
        "bulb": materials.gloss_paint("bulb", (0.93, 0.92, 0.89), rough=0.35),
    }


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def panel(name, lo, hi, coll, mat, part, bevel_w=0.0015, segs=2):
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    ob = new_object(name, bm, coll, material=mat)
    finish(ob, bevel_w, segs)
    tag(ob, part)
    return ob


def build_body(coll, col_coll, mats):
    wx, wz, gm, dark = mats["walnut_x"], mats["walnut_z"], mats["gunmetal_z"], mats["dark"]

    # Carcass: top over the sides, bottom and back between them, a fixed divider
    panel("Top", (-HX, -HY, TOP_Z0), (HX, HY, H), coll, wx, "body")
    panel("SideL", (-HX, -HY, CARC_Z0), (-INNER_X, HY, TOP_Z0), coll, wz, "body")
    panel("SideR", (INNER_X, -HY, CARC_Z0), (HX, HY, TOP_Z0), coll, wz, "body")
    panel("Bottom", (-INNER_X, -HY, CARC_Z0), (INNER_X, HY, BOTTOM_Z1), coll, wx, "body")
    panel("Back", (-INNER_X, BACK_Y0, BOTTOM_Z1), (INNER_X, HY, TOP_Z0), coll, wx, "body", 0.001, 1)
    panel("Divider", (-INNER_X, -HY, DIV_Z0), (INNER_X, BACK_Y0, DIV_Z1), coll, wx, "body")

    # Drawer runners on the divider
    bm = bmesh.new()
    for s in (-1, 1):
        bm_box(bm, (s * RAIL_X - RAIL_W / 2, RAIL_Y0, DIV_Z1), (s * RAIL_X + RAIL_W / 2, RAIL_Y1, DIV_Z1 + RAIL_H))
    ob = new_object("Rails", bm, coll, material=dark)
    finish(ob, 0.001, 1)
    tag(ob, "body")

    # Four slim square-tube legs
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (HX - LEG_INSET), sy * (HY - LEG_INSET)
            bm_box(bm, (cx - LEG_S / 2, cy - LEG_S / 2, 0.0), (cx + LEG_S / 2, cy + LEG_S / 2, CARC_Z0))
    ob = new_object("Legs", bm, coll, material=gm)
    finish(ob, 0.0012, 2)
    tag(ob, "body")

    # Collision boxes for Godot; the drawer opening stays free
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColTop", (-HX, -HY, TOP_Z0), (HX, HY, H))
    col("ColSideL", (-HX, -HY, CARC_Z0), (-INNER_X, HY, TOP_Z0))
    col("ColSideR", (INNER_X, -HY, CARC_Z0), (HX, HY, TOP_Z0))
    col("ColBack", (-INNER_X, BACK_Y0, BOTTOM_Z1), (INNER_X, HY, TOP_Z0))
    col("ColBottom", (-INNER_X, -HY, CARC_Z0), (INNER_X, HY, BOTTOM_Z1))
    col("ColShelf", (-INNER_X, -HY, DIV_Z0), (INNER_X, BACK_Y0, DIV_Z1))
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        cx, cy = sx * (HX - LEG_INSET), sy * (HY - LEG_INSET)
        col(f"ColLeg{i + 1}", (cx - LEG_S / 2, cy - LEG_S / 2, 0.0), (cx + LEG_S / 2, cy + LEG_S / 2, CARC_Z0))


def build_drawer(coll, mats):
    wx, ash, gm = mats["walnut_x"], mats["ash"], mats["gunmetal_x"]

    # Inset front (root of the drawer hierarchy, origin at its bottom center)
    bm = bmesh.new()
    bm_box(bm, (-FRONT_HW, 0.0, 0.0), (FRONT_HW, FRONT_T, FRONT_H))
    drawer = new_object("Drawer", bm, coll, origin=DRAWER_ORIGIN, material=wx)
    finish(drawer, 0.0015, 2)
    tag(drawer, "drawer")

    def child(name, bm, material, bevel_w, segs=1):
        ob = new_object(name, bm, coll, material=material, parent=drawer)
        finish(ob, bevel_w, segs)
        tag(ob, "drawer")
        return ob

    # Box: light ash, open at the top, real inner walls
    bm = bmesh.new()
    bm_box(bm, (-BOX_HW, BOX_Y0, BOX_Z0), (BOX_HW, BOX_Y1, BOX_Z1))
    box = new_object("DrawerBox", bm, coll, material=ash, parent=drawer)
    bm = bmesh.new()
    bm_box(bm, (-BOX_HW + BOX_WALL, BOX_Y0 + BOX_WALL, BOX_Z0 + BOX_BOTTOM), (BOX_HW - BOX_WALL, BOX_Y1 - BOX_WALL, BOX_Z1 + 0.05))
    cut(box, bm, coll)
    finish(box, 0.0012, 1)
    tag(box, "drawer")

    # Bar pull on two standoffs
    bm = bmesh.new()
    bm_cyl(bm, PULL_R, PULL_LEN, cyl_x((0.0, PULL_Y, PULL_Z)), 20)
    for x in (-PULL_LEN / 2 + 0.016, PULL_LEN / 2 - 0.016):
        bm_cyl(bm, PULL_STANDOFF_R, abs(PULL_Y) + 0.002, cyl_y((x, PULL_Y / 2, PULL_Z)), 12)
    child("Pull", bm, gm, 0.0012, 2)

    tag(new_empty("HandleGrip", coll, HANDLE_GRIP, parent=drawer), "drawer")
    return drawer


def build_lamp(coll, mats):
    gmz, gmx, cord, linen, bulb = mats["gunmetal_z"], mats["gunmetal_x"], mats["cord"], mats["linen"], mats["bulb"]

    # Base disc (root, origin at its bottom center)
    bm = bmesh.new()
    bm_cyl(bm, BASE_R, BASE_H, cyl_z((0.0, 0.0, BASE_H / 2)), 48)
    lamp = new_object("TableLamp", bm, coll, origin=LAMP_ORIGIN, material=gmx)
    finish(lamp, 0.004, 3)
    tag(lamp, "lamp")

    def child(name, bm, material, bevel_w=None, segs=1, sharp=30.0):
        ob = new_object(name, bm, coll, material=material, parent=lamp)
        finish(ob, bevel_w, segs, sharp_angle=sharp)
        tag(ob, "lamp")
        return ob

    # Stem with a foot collar, socket cup on top
    bm = bmesh.new()
    bm_cyl(bm, STEM_R, STEM_Z1 - BASE_H + 0.002, cyl_z((0.0, 0.0, (STEM_Z1 + BASE_H - 0.002) / 2)), 24)
    bm_cyl(bm, 0.011, 0.012, cyl_z((0.0, 0.0, BASE_H + 0.006 - 0.001)), 32)
    child("LampStem", bm, gmz, 0.0015, 2)
    bm = bmesh.new()
    bm_cyl(bm, SOCKET_R, SOCKET_Z1 - SOCKET_Z0, cyl_z((0.0, 0.0, (SOCKET_Z0 + SOCKET_Z1) / 2)), 32)
    child("LampSocket", bm, gmz, 0.0012, 2)

    # Bulb: LED candle bulb on a short neck
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=BULB_R, matrix=Matrix.Translation((0.0, 0.0, BULB_Z)))
    bm_cyl(bm, 0.010, 0.020, cyl_z((0.0, 0.0, SOCKET_Z1 + 0.007)), 20)
    child("LampBulb", bm, bulb, None, sharp=40.0)

    # Drum shade: thin linen shell open at both ends
    bm = bmesh.new()
    bm_drum_shell(bm, SHADE_R0, SHADE_R1, SHADE_Z0, SHADE_Z1, SHADE_T, 48)
    child("LampShade", bm, linen, None)

    # Spider: collar ring on the socket, three spokes, top ring inside the shade's rim
    bm = bmesh.new()
    collar_r, collar_z = SOCKET_R + 0.0012, SOCKET_Z0 + 0.027
    ring_r, ring_z = SHADE_R1 - SHADE_T - 0.0015, SHADE_Z1 - 0.003
    from math import cos, pi, sin
    bm_tube(bm, [(collar_r * cos(2 * pi * k / 24), collar_r * sin(2 * pi * k / 24), collar_z) for k in range(24)],
            0.0015, 6, closed=True)
    bm_tube(bm, [(ring_r * cos(2 * pi * k / 48), ring_r * sin(2 * pi * k / 48), ring_z) for k in range(48)],
            0.0015, 6, closed=True)
    for k in range(3):
        a = 2 * pi * k / 3 + pi / 2
        bm_tube(bm, [(collar_r * cos(a), collar_r * sin(a), collar_z), (ring_r * cos(a), ring_r * sin(a), ring_z)],
                0.0015, 6)
    child("LampSpider", bm, gmz, None)

    # Cord: out of the base toward +Y, over the back edge of whatever it stands on, down to the floor
    path = [(0.0, 0.055, 0.007), (0.0, 0.078, CORD_R + 0.0005), (0.0, 0.11, CORD_R + 0.0005),
            (0.002, 0.126, CORD_R), (0.003, 0.1325, -0.004), (0.004, 0.1365, -0.03), (0.006, 0.137, -0.20),
            (0.004, 0.1365, -0.40), (0.0, 0.139, -0.52), (0.0, 0.150, -0.543), (0.0, 0.19, -H + CORD_R),
            (0.0, 0.26, -H + CORD_R)]
    bm = bmesh.new()
    bm_tube(bm, smooth_polyline(path, 4), CORD_R, 8)
    child("LampCord", bm, cord, None, sharp=50.0)

    # Inline rocker switch on the cord
    bm = bmesh.new()
    bm_box(bm, (-0.008, 0.086, 0.0), (0.008, 0.124, 0.012))
    child("LampSwitch", bm, cord, 0.003, 2)
    bm = bmesh.new()
    bm_box(bm, (-0.0045, 0.098, 0.011), (0.0045, 0.112, 0.0145))
    child("LampSwitchRocker", bm, cord, 0.001, 1)
    return lamp


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("NightstandBody"), get_collection("NightstandBodyCollision"), mats)
    build_drawer(get_collection("NightstandDrawer"), mats)
    build_lamp(get_collection("TableLamp"), mats)
    body, col, drawer, lamp = part_tris("body"), part_tris("body_col"), part_tris("drawer"), part_tris("lamp")
    print(f"TRIS body={body} collision={col} drawer={drawer} lamp={lamp} total={body + drawer + lamp}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
