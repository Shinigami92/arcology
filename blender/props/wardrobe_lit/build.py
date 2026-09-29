"""Stage 1: build the wardrobe geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/wardrobe_lit/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import lib_candidates as lc  # noqa: E402
import wardrobe_common as C  # noqa: E402
from arcology_blender import curves, fabric, soft, wear, wood  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    bm_box, bm_cyl, bm_merge, bm_quad, bm_square_taper, collision_box, cut, cyl_x, cyl_y, finish, new_empty,
    new_object, set_uvs, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat, solid_mat  # noqa: E402

WORN_WALNUT = (0.100, 0.062, 0.036)   # lacquer rubbed thin: lighter, a little grey
DUST = (0.55, 0.53, 0.50)


def edges(g, radius):
    """This asset's edge mask (softer and fewer Bevel samples than the library defaults)."""
    return wear.bevel_edges(g, radius, 0.02, 0.20, samples=8)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def walnut(axis, extra=None, rough=0.42, seed=0.0):
    """Dark walnut veneer, satin lacquer, grain along `axis`, worn edges, dust on top."""
    g = Graph(new_mat(f"src_walnut_{axis.lower()}"))
    base, r, h = wood.veneer_axis(g, axis, C.WALNUT_MID, C.WALNUT_LIGHT, C.WALNUT_DARK, rough=rough, seed=seed)
    edge = edges(g, 0.003)
    base, r = wear.edge_wear(g, base, r, edge, 1.0, WORN_WALNUT, amount=0.18, rough_delta=-0.04)
    if extra is not None:
        base, r, h = extra(g, base, r, h, edge)
    base, r = wear.top_dust(g, base, r, 2.085, 2.096, color=DUST, amount=0.22, rougher=0.25)
    return g.finish_height(base, r, 0.0, h)


def walnut_z_wear(g, base, r, h, edge):
    """Doors and sides: hands at the pulls, a scratch, kick scuffs, shelf pin holes."""
    ax = g.math("ABSOLUTE", g.x)
    door = g.maprange(g.y, -0.3004, -0.3009)       # every door surface (the body stays at y >= -0.30)
    front = g.maprange(g.y, -0.312, -0.318)        # door fronts (y = -0.321)
    # Meeting edges at pull height: lacquer rubbed thin and polished by hands
    grip = g.mul(g.mul(door, g.maprange(ax, 0.030, 0.006)), g.band(g.z, 0.88, 1.52, 0.16))
    base, r = wear.edge_wear(g, base, r, edge, grip, WORN_WALNUT, amount=0.55, rough_delta=-0.10)
    oil = g.mul(g.mul(front, g.maprange(ax, 0.05, 0.004)), g.band(g.z, 0.95, 1.45, 0.15))
    base = g.scale_color(base, g.sub(1.0, g.mul(oil, 0.10)))
    r = g.sub(r, g.mul(oil, 0.06))
    # Fingerprints around the pulls: glossy on satin
    near = g.mul(g.mul(front, g.band(ax, 0.012, 0.13, 0.04)), g.band(g.z, 0.98, 1.42, 0.14))
    base, r = wear.smudges(g, base, r, near, rougher=-0.035, darker=0.03)
    # A small scratch on the right door, with a shorter one beside it
    base, r, h = wear.scratch(g, base, r, h, (0.232, 1.058), (0.318, 1.026), width=0.0022, mask=front, wobble=0.2)
    base, r, h = wear.scratch(g, base, r, h, (0.258, 1.071), (0.292, 1.060), width=0.0015, mask=front,
                              amount=0.55, wobble=0.2)
    base, r = wear.bottom_scuffs(g, base, r, z_clean=0.32, z_full=0.14, rougher=0.10, darker=0.14, mask=front)
    # 32 mm shelf pin holes on the inner sides
    inner = g.mul(g.band(ax, C.IN_X - 0.0015, C.IN_X + 0.0015, 0.0005),
                  g.maprange(g.math("ABSOLUTE", g.nx), 0.8, 0.95))
    dz = g.mul(g.sub(g.math("FRACT", g.add(g.mul(g.sub(g.z, C.PIN_Z), 1.0 / C.PIN_PITCH), 0.5)), 0.5),
               C.PIN_PITCH)
    dy = g.math("MINIMUM", g.math("ABSOLUTE", g.sub(g.y, C.PIN_Y[0])), g.math("ABSOLUTE", g.sub(g.y, C.PIN_Y[1])))
    d = g.math("SQRT", g.add(g.mul(dz, dz), g.mul(dy, dy)))
    hole = g.mul(g.mul(inner, g.band(g.z, C.PIN_HOLES_Z[0], C.PIN_HOLES_Z[1], 0.002)),
                 g.maprange(d, C.PIN_R + 0.0004, C.PIN_R - 0.0003))
    base = g.mixc(hole, base, (0.006, 0.004, 0.003))
    r = g.mixf(hole, r, 0.9)
    h = g.sub(h, g.mul(hole, 0.0015))
    return base, r, h


def walnut_x_wear(g, base, r, h, edge):
    """Top, bottom, shelves, drawer fronts: fingerprints around the drawer pulls."""
    ax = g.math("ABSOLUTE", g.x)
    dfront = g.band(g.y, C.DRAWER_Y0 - 0.0005, C.DRAWER_Y0 + 0.0005, 0.0008)
    cx = (C.IN_X + C.DIVIDER_T / 2) / 2
    near = g.mul(g.mul(dfront, g.band(ax, cx - 0.12, cx + 0.12, 0.04)), g.band(g.z, C.PULL_Z - 0.05, C.PULL_Z + 0.04, 0.03))
    base, r = wear.smudges(g, base, r, near, rougher=-0.08, darker=0.04)
    return base, r, h


def gunmetal(axis, extra=None):
    g = Graph(new_mat(f"src_gunmetal_{axis.lower()}"))
    base, r, h = lc.brushed_metal(g, axis, C.GUNMETAL, rough=0.30)
    edge = edges(g, 0.0015)
    base, r = wear.edge_wear(g, base, r, edge, 1.0, (0.11, 0.12, 0.13), amount=0.35, rough_delta=-0.08)
    if extra is not None:
        base, r = extra(g, base, r)
    return g.finish_height(base, r, 1.0, h)


def gunmetal_z_wear(g, base, r):
    """Door pulls polished and smudged where the hand closes; legs darker at the floor."""
    grip = g.mul(g.maprange(g.y, -0.338, -0.344), g.band(g.z, 1.06, 1.34, 0.08))
    r = g.sub(r, g.mul(grip, 0.10))
    base = g.scale_color(base, g.add(1.0, g.mul(grip, 0.18)))
    base, r = wear.smudges(g, base, r, grip, rougher=0.14, darker=0.0)
    base = wear.floor_grime(g, base, 0.0, 0.035, 0.7)
    return base, r


def gunmetal_x_wear(g, base, r):
    """The rail's top is polished by sliding hooks."""
    top = g.mul(g.mul(g.maprange(g.nz, 0.5, 0.9), g.band(g.z, C.RAIL_Z, C.RAIL_Z + 0.02, 0.004)),
                g.band(g.y, C.RAIL_Y - 0.02, C.RAIL_Y + 0.02, 0.004))
    slide = g.mul(top, g.maprange(g.noise(1.0, 2.0, 0.5, g.vec(3.0, 400.0, 400.0)), 0.35, 0.65, 0.4, 1.0))
    r = g.sub(r, g.mul(slide, 0.14))
    base = g.scale_color(base, g.add(1.0, g.mul(slide, 0.25)))
    return base, r


def mat_back():
    """Linen-textured laminate back panel: warm off-white, fine slubs."""
    g = Graph(new_mat("src_back"))
    col = tuple(c * 0.88 for c in C.OFF_WHITE)
    base, r, h = fabric.fabric_base(g, col, rough=0.72, heather=0.03, slub=0.06, mottle=0.03,
                                    weave=0.00012, slub_height=0.00008)
    base, r = wear.low_grime(g, base, r, 0.60, 0.12, (0.45, 0.42, 0.36), amount=0.25, rougher=0.05)
    return fabric.fabric_finish(g, base, r, h)


SHIRT_W = 0.46
SHIRT_LENGTHS = (0.74, 0.78)


def mat_shirt(name, color):
    """Linen shirt: long vertical creases, shoulder creases, and on its front (world
    +X while hanging, hanger-local -Y) a button placket."""
    g = Graph(new_mat(f"src_{name}"))
    base, r, h = fabric.fabric_base(g, color, rough=0.90, heather=0.04, slub=0.08, mottle=0.04,
                                    weave=0.00022, slub_height=0.00018)
    base, h = fabric.creases(g, base, h, 1.0, stretch=(10.0, 12.0, 2.2), depth=0.0016, sharp=0.70, darker=0.10)
    base, h = fabric.creases(g, base, h, g.maprange(g.z, 1.35, 1.60), stretch=(14.0, 7.0, 7.0),
                             depth=0.0010, sharp=0.75, darker=0.06)
    z1 = C.RAIL_Z + C.RAIL_R + C.HANGER_ARM_TOP + 0.010
    face = g.maprange(g.nx, 0.45, 0.8)
    dy = g.math("ABSOLUTE", g.sub(g.y, C.RAIL_Y))
    # placket: two stitched edges 14 mm off center, buttons every 9 cm
    seam = g.mul(face, g.band(dy, 0.0135, 0.0150, 0.0008))
    seam = g.mul(seam, g.maprange(g.z, z1 - 0.02, z1 - 0.05))
    base = g.scale_color(base, g.sub(1.0, g.mul(seam, 0.22)))
    h = g.sub(h, g.mul(seam, 0.0004))
    bz = g.sub(g.math("FRACT", g.mul(g.sub(g.z, z1 - 0.085), 1.0 / 0.09)), 0.5)
    bd = g.math("SQRT", g.add(g.mul(dy, dy), g.mul(g.mul(bz, 0.09), g.mul(bz, 0.09))))
    lowest = z1 - 0.085 - 5 * 0.09
    button = g.mul(g.mul(face, g.maprange(bd, 0.0058, 0.0045)), g.band(g.z, lowest - 0.02, z1 - 0.06, 0.004))
    base = g.mixc(button, base, tuple(c * 0.82 for c in color))
    r = g.mixf(button, r, 0.35)
    h = g.add(h, g.mul(button, 0.0012))
    return fabric.fabric_finish(g, base, r, h)


def mat_linen():
    """Folded linen and a blanket on the top shelf (static, in the body)."""
    g = Graph(new_mat("src_linen"))
    left = g.maprange(g.x, 0.02, -0.02)
    # stack A (left): off-white, sand, off-white; stack B (right): charcoal blanket, sand towel
    a_mid = g.band(g.z, 1.878, 1.921, 0.002)
    b_low = g.band(g.z, 1.80, 1.901, 0.002)
    col = g.mixc(g.mul(left, a_mid), C.OFF_WHITE, C.SAND)
    col = g.mixc(g.mul(g.sub(1.0, left), b_low), col, (0.050, 0.050, 0.055))
    col = g.mixc(g.mul(g.sub(1.0, left), g.sub(1.0, b_low)), col, C.SAND)
    base, r, h = fabric.fabric_base(g, col, rough=0.92, heather=0.05, slub=0.06, mottle=0.05)
    base, h = fabric.creases(g, base, h, 1.0, stretch=(3.0, 10.0, 20.0), depth=0.0012, darker=0.08)
    return fabric.fabric_finish(g, base, r, h)


def mat_box():
    """Fabric-covered storage box and lid: taupe linen, a little rubbed on the edges."""
    g = Graph(new_mat("src_box"))
    base, r, h = fabric.fabric_base(g, (0.36, 0.31, 0.24), rough=0.90, heather=0.05, slub=0.06, mottle=0.05)
    edge = edges(g, 0.003)
    base, r = fabric.rub(g, base, r, edge, shinier=0.10, tint=0.08)
    return fabric.fabric_finish(g, base, r, h)


def mat_scarf():
    """Folded knit scarf in the box: deep smog blue wool."""
    g = Graph(new_mat("src_scarf"))
    base, r, h = fabric.fabric_base(g, (0.030, 0.045, 0.070), rough=0.95, heather=0.08, slub=0.03, mottle=0.08,
                                    weave=0.0004)
    base, h = fabric.creases(g, base, h, 1.0, stretch=(4.0, 14.0, 14.0), depth=0.0010, darker=0.08)
    return fabric.fabric_finish(g, base, r, h)


def build_materials():
    return {
        "wz": walnut("Z", walnut_z_wear),
        "wx": walnut("X", walnut_x_wear),
        "wy": walnut("Y", rough=0.38, seed=0.37),
        "gz": gunmetal("Z", gunmetal_z_wear),
        "gx": gunmetal("X", gunmetal_x_wear),
        "back": mat_back(),
        "shirt_a": mat_shirt("shirt_a", C.OFF_WHITE),
        "shirt_b": mat_shirt("shirt_b", C.SAND),
        "linen": mat_linen(),
        "box": mat_box(),
        "scarf": mat_scarf(),
        "light": solid_mat(C.LIGHT_MAT, (0.92, 0.90, 0.86), 0.4, emission=(1.0, 0.80, 0.58),
                           emission_strength=3.0),
    }


# ---------------------------------------------------------------------------
# Body geometry (world coordinates)
# ---------------------------------------------------------------------------
def build_carcass(coll, mats):
    # Sides and the drawer unit divider (vertical grain)
    bm = bmesh.new()
    bm_box(bm, (-C.BX, -C.BY, C.CARCASS_Z0), (-C.IN_X, C.BY, C.BODY_H))
    bm_box(bm, (C.IN_X, -C.BY, C.CARCASS_Z0), (C.BX, C.BY, C.BODY_H))
    bm_box(bm, (-C.DIVIDER_T / 2, C.DRAWER_Y0, C.IN_Z0), (C.DIVIDER_T / 2, C.BACK_Y0, C.BOTTOM_SHELF_Z))
    ob = new_object("CarcassSides", bm, coll, material=mats["wz"])
    finish(ob, 0.0015, 2)
    tag(ob, "body")

    # Top, bottom, shelves (horizontal grain)
    bm = bmesh.new()
    bm_box(bm, (-C.IN_X, -C.BY, C.IN_Z1), (C.IN_X, C.BY, C.BODY_H))
    bm_box(bm, (-C.IN_X, -C.BY, C.CARCASS_Z0), (C.IN_X, C.BY, C.IN_Z0))
    bm_box(bm, (-C.IN_X, C.SHELF_Y0, C.TOP_SHELF_Z), (C.IN_X, C.BACK_Y0, C.TOP_SHELF_Z + C.SHELF_T))
    bm_box(bm, (-C.IN_X, C.BOTTOM_SHELF_Y0, C.BOTTOM_SHELF_Z), (C.IN_X, C.BACK_Y0, C.BOTTOM_SHELF_Z + C.SHELF_T))
    ob = new_object("CarcassPanels", bm, coll, material=mats["wx"])
    finish(ob, 0.0015, 2)
    tag(ob, "body")

    # Drawer runners (carcass rails on the sides and the divider) and top shelf pins
    bm = bmesh.new()
    for s in (-1, 1):
        for xa, xb in ((C.IN_X - C.RUNNER_T, C.IN_X), (C.DIVIDER_T / 2, C.DIVIDER_T / 2 + C.RUNNER_T)):
            lo, hi = sorted((s * xa, s * xb))
            bm_box(bm, (lo, C.RUNNER_Y0, C.RUNNER_Z0), (hi, C.RUNNER_Y1, C.RUNNER_Z1))
    for s in (-1, 1):
        for y in C.PIN_Y:
            bm_cyl(bm, C.PIN_R, 0.012, cyl_x((s * (C.IN_X - 0.004), y, C.PIN_Z)), 10)
    ob = new_object("Hardware", bm, coll, material=mats["gx"])
    finish(ob, 0.0012, 1)
    tag(ob, "body")

    # Legs: tapered square tube with a mounting plate
    bm = bmesh.new()
    for x, y in C.LEGS:
        bm_square_taper(bm, x, y, 0.0, C.LEG_H - 0.003, C.LEG_TOP, C.LEG_BOTTOM)
        bm_box(bm, (x - 0.035, y - 0.035, C.LEG_H - 0.003), (x + 0.035, y + 0.035, C.LEG_H))
    ob = new_object("Legs", bm, coll, material=mats["gz"])
    finish(ob, 0.0015, 2)
    tag(ob, "body")


def build_hardware(coll, mats):
    """Back panel, rail with its brackets, LED strip."""
    bm = bmesh.new()
    bm_box(bm, (-C.IN_X - 0.0055, C.BACK_Y0, C.IN_Z0 - 0.0055), (C.IN_X + 0.0055, C.BACK_Y1, C.IN_Z1 + 0.0055))
    ob = new_object("BackPanel", bm, coll, material=mats["back"])
    shade(ob)
    tag(ob, "body")

    bm = bmesh.new()
    bm_cyl(bm, C.RAIL_R, 2 * C.IN_X - 0.002, cyl_x((0.0, C.RAIL_Y, C.RAIL_Z)), 20)
    for s in (-1, 1):
        bm_cyl(bm, 0.022, 0.005, cyl_x((s * (C.IN_X - 0.0025), C.RAIL_Y, C.RAIL_Z)), 20)   # end flanges
        bm_cyl(bm, 0.0155, 0.014, cyl_x((s * (C.IN_X - 0.007), C.RAIL_Y, C.RAIL_Z)), 20)  # sockets
    # center support hanging from the top shelf
    bm_box(bm, (-0.003, C.RAIL_Y - 0.010, C.RAIL_Z), (0.003, C.RAIL_Y + 0.010, C.TOP_SHELF_Z - 0.003))
    bm_box(bm, (-0.020, C.RAIL_Y - 0.030, C.TOP_SHELF_Z - 0.003), (0.020, C.RAIL_Y + 0.030, C.TOP_SHELF_Z))
    bm_cyl(bm, C.RAIL_R + 0.003, 0.016, cyl_x((0.0, C.RAIL_Y, C.RAIL_Z)), 20)
    # LED channel under the top shelf front
    bm_box(bm, (-0.68, C.LED_Y0, C.TOP_SHELF_Z - 0.010), (0.68, C.LED_Y1, C.TOP_SHELF_Z))
    ob = new_object("Rail", bm, coll, material=mats["gx"])
    finish(ob, 0.0012, 1)
    tag(ob, "body")

    bm = bmesh.new()
    z = C.TOP_SHELF_Z - 0.0102
    bm_quad(bm, ((-0.675, C.LED_Y0 + 0.002, z), (0.675, C.LED_Y0 + 0.002, z),
                 (0.675, C.LED_Y1 - 0.002, z), (-0.675, C.LED_Y1 - 0.002, z)))
    ob = new_object("LedStrip", bm, coll, material=mats["light"])
    set_uvs(ob, ((0, 0), (1, 0), (1, 1), (0, 1)))
    tag(ob, "body")


def folded(center, size, yaw, seed, crown=0.004):
    bm = soft.soft_box(center, size, min(size[2] * 0.45, 0.022), step=0.05, band_segments=2, panel_axis=None,
                       crown={"+z": crown, "-y": 0.004}, open_faces=("-z",))
    soft.jitter(bm, 0.002, 8.0, seed=seed)
    soft.rotate_verts(bm, center, yaw, "Z")
    return bm


def build_linen(coll, mats):
    """Folded linen on the top shelf (two stacks, static)."""
    top = C.TOP_SHELF_Z + C.SHELF_T
    bm = bmesh.new()
    z = top
    for k, (sz, dx, dy, yaw) in enumerate((((0.34, 0.27, 0.056), 0.0, 0.0, 1.5),
                                           ((0.33, 0.26, 0.050), 0.008, -0.006, -2.5),
                                           ((0.34, 0.27, 0.052), -0.006, 0.004, 3.0))):
        bm_merge(bm, folded((-0.43 + dx, -0.03 + dy, z + sz[2] / 2), sz, yaw, seed=11.0 + k))
        z += sz[2] - 0.002
    z = top
    for k, (sz, dx, dy, yaw) in enumerate((((0.40, 0.30, 0.085), 0.0, 0.0, -1.0),
                                           ((0.32, 0.24, 0.048), 0.012, -0.01, 4.0))):
        bm_merge(bm, folded((0.40 + dx, -0.02 + dy, z + sz[2] / 2), sz, yaw, seed=21.0 + k, crown=0.006))
        z += sz[2] - 0.003
    ob = new_object("Linen", bm, coll, material=mats["linen"])
    shade(ob, 70.0)
    tag(ob, "body")


def build_collision(coll):
    for name, (lo, hi) in C.COLLISION.items():
        tag(collision_box(name, lo, hi, coll), "body_col")


# ---------------------------------------------------------------------------
# Moving parts (each in its own local frame, placed where it rests in the wardrobe)
# ---------------------------------------------------------------------------
def build_drawer(coll, mats):
    """Left drawer, drawer-local: origin at the front's outer face, bottom edge, centered;
    the open-top box extends +Y (it slides out along -Y). The right drawer is an instance."""
    hw, t, h = C.DR_FRONT_HW, C.DR_FRONT_T, C.DR_FRONT_H
    bm = bmesh.new()
    bm_box(bm, (-hw, 0.0, 0.0), (hw, t, h))
    root = new_object("Drawer", bm, coll, origin=C.DRAWER_ORIGINS[0], material=mats["wx"])
    finish(root, 0.0015, 2)
    tag(root, "drawer")

    def child(name, bm, mat, bevel_w=None):
        ob = new_object(name, bm, coll, material=mat, parent=root)
        finish(ob, bevel_w, 1)
        tag(ob, "drawer")
        return ob

    bw, w = C.DR_BOX_HW, C.DR_WALL
    y0, y1, z0, z1 = C.DR_BOX_Y0, C.DR_BOX_Y1, C.DR_BOX_Z0, C.DR_BOX_Z1
    bm = bmesh.new()
    bm_box(bm, (-bw, y0, z0), (-bw + w, y1, z1))
    bm_box(bm, (bw - w, y0, z0), (bw, y1, z1))
    child("DrawerSides", bm, mats["wy"], 0.0012)
    bm = bmesh.new()
    bm_box(bm, (-bw + w, y0, z0), (bw - w, y0 + w, z1 - 0.004))   # inner front
    bm_box(bm, (-bw + w, y1 - w, z0), (bw - w, y1, z1 - 0.004))   # back
    child("DrawerEnds", bm, mats["wx"], 0.0012)
    bm = bmesh.new()
    bm_box(bm, (-bw + w, y0 + w, z0), (bw - w, y1 - w, z0 + C.DR_FLOOR))
    child("DrawerFloor", bm, mats["back"], 0.0008)
    # slide members on the box sides, and the pull (128 mm centers)
    bm = bmesh.new()
    mz0, mz1 = C.RUNNER_Z0 + 0.006 - C.DRAWER_Z0, C.RUNNER_Z1 - 0.006 - C.DRAWER_Z0
    for s in (-1, 1):
        lo, hi = sorted((s * bw, s * (bw + C.DR_MEMBER_T)))
        bm_box(bm, (lo, y0 + 0.02, mz0), (hi, y1 - 0.01, mz1))
    py, pz = C.PULL_Y - C.DRAWER_Y0, C.PULL_Z - C.DRAWER_Z0
    bm_cyl(bm, C.PULL_R, C.PULL_LEN, cyl_x((0.0, py, pz)), 16)
    for dx in (-0.064, 0.064):
        bm_cyl(bm, 0.0035, abs(py) + 0.001, cyl_y((dx, (py + 0.001) / 2, pz)), 12)
    child("DrawerHardware", bm, mats["gx"], 0.0012)
    tag(new_empty("HandleGrip.D", coll, (0.0, py, pz), parent=root), "drawer")
    return root


def build_box(coll, mats):
    """Fabric storage box (open top, origin at its bottom center) with a folded scarf, and its lid
    (origin at the lid's bottom center, i.e. the skirt's lower edge)."""
    bx, by, bz = C.BOX_SIZE
    w = C.BOX_WALL
    bm = bmesh.new()
    bm_box(bm, (-bx / 2, -by / 2, 0.0), (bx / 2, by / 2, bz))
    box = new_object("Box", bm, coll, origin=C.BOX_ORIGIN, material=mats["box"])
    bm = bmesh.new()
    bm_box(bm, (-bx / 2 + w, -by / 2 + w, w), (bx / 2 - w, by / 2 - w, bz + 0.05))
    cut(box, bm, coll)
    finish(box, 0.002, 2)
    tag(box, "box")
    sc = new_object("BoxScarf", folded((0.005, -0.004, w + 0.026), (0.30, 0.23, 0.052), 3.0, seed=31.0, crown=0.008),
                    coll, material=mats["scarf"], parent=box)
    shade(sc, 70.0)
    tag(sc, "box")

    lx, ly, lz = C.LID_SIZE
    bm = bmesh.new()
    bm_box(bm, (-lx / 2, -ly / 2, 0.0), (lx / 2, ly / 2, lz))
    lid = new_object("Lid", bm, coll, origin=C.LID_ORIGIN, material=mats["box"])
    bm = bmesh.new()
    bm_box(bm, (-lx / 2 + C.LID_WALL, -ly / 2 + C.LID_WALL, -0.01),
           (lx / 2 - C.LID_WALL, ly / 2 - C.LID_WALL, lz - C.LID_TOP))
    cut(lid, bm, coll)
    finish(lid, 0.002, 2)
    tag(lid, "lid")


def hanger_geometry(bm_wood, bm_wire):
    """Walnut hanger with a gunmetal hook and trouser wire, hanger-local (see wardrobe_common)."""
    zt = C.HANGER_ARM_TOP
    hw = C.HANGER_W / 2

    def arm_z(t):
        return zt - 0.012 - 0.048 * abs(t) ** 1.7

    ts = [i / 10.0 for i in range(-10, 11)]
    path = [(t * hw, 0.0, arm_z(t)) for t in ts]
    scales = [(1.0 - 0.38 * abs(t), 1.0 - 0.12 * abs(t)) for t in ts]
    path.insert(0, (-(hw + 0.006), 0.0, arm_z(1.0) + 0.001))
    path.append((hw + 0.006, 0.0, arm_z(1.0) + 0.001))
    scales = [(0.42, 0.70)] + scales + [(0.42, 0.70)]
    curves.sweep(bm_wood, path, curves.rounded_rect_profile(0.024, 0.011, 0.004, 1), up=(0, 1, 0), scales=scales)

    zb = zt - 0.165
    coarse = [(-0.186, 0.0, arm_z(0.87)), (-0.180, 0.0, zt - 0.10), (-0.168, 0.0, zb),
              (0.168, 0.0, zb), (0.180, 0.0, zt - 0.10), (0.186, 0.0, arm_z(0.87))]
    curves.sweep(bm_wire, curves.chaikin(coarse, 2), curves.circle_profile(0.0022, 6), up=(0, 1, 0))
    # hook: neck centered under the rest point, an S-bend forward, then around the rail
    neck = curves.chaikin([(0.0, 0.0, zt - 0.006), (0.0, 0.0, -0.055), (-C.HOOK_R, 0.0, -0.038),
                           (-C.HOOK_R, 0.0, C.HOOK_CENTER_Z)], 2)
    arc = curves.arc_points((0.0, 0.0, C.HOOK_CENTER_Z), C.HOOK_R, 180.0, -40.0, 10,
                        u_axis=(1.0, 0.0, 0.0), v_axis=(0.0, 0.0, 1.0))
    curves.sweep(bm_wire, neck + arc[1:], curves.circle_profile(C.HOOK_WIRE, 6), up=(0, 1, 0))
    bm_cyl(bm_wire, 0.0045, 0.010, Matrix.Translation((0.0, 0.0, zt + 0.003)), 10)  # ferrule


def shirt_geometry(length, seed):
    """Linen shirt on the hanger, hanger-local: shoulders along X, front toward -Y.

    The body is a thin soft slab reshaped column by column: straight sloping
    shoulders from the collar, a standing collar, a slight waist and a curved
    shirt-tail hem. Two sleeves hang along its edges as separate soft tubes,
    ending in cuffs 16 cm above the hem, so the silhouette steps like a shirt.
    """
    z1 = C.HANGER_ARM_TOP + 0.010          # shoulder line at the collar, just above the hanger
    z0 = z1 - length
    w, t = SHIRT_W, 0.026

    def shoulder(a):
        return z1 - 0.072 * max(0.0, (a - 0.16) / 0.84)

    bm = soft.soft_box((0.0, 0.0, (z0 + z1) / 2), (w, t, length), 0.007, step=(0.032, 0.03, 0.032),
                       band_segments=2, panel_axis=None)
    for v in bm.verts:
        a = abs(v.co.x / (w / 2))
        tz = min(1.0, max(0.0, (v.co.z - z0) / length))
        hem = 0.035 * a ** 2.2                                  # shirt tails longer in the middle
        v.co.z = z0 + hem + (shoulder(a) - z0 - hem) * tz
        v.co.x *= 1.0 - 0.03 * math.exp(-((tz - 0.45) / 0.18) ** 2)  # waist
        v.co.y *= 1.0 - 0.35 * (1.0 - tz) ** 0.7                # hanger inside at the top, flat below
        if a < 0.16 and tz > 0.97:
            v.co.z += 0.018 * (1.0 - (a / 0.16) ** 2)           # collar stand
    soft.jitter(bm, 0.0015, 9.0, seed=seed)

    cuff_z = z0 + 0.16
    for sgn in (-1.0, 1.0):
        xs = sgn * (w / 2 - 0.040)
        top = shoulder(abs(xs) / (w / 2)) - 0.004
        sl = soft.soft_box((xs, 0.0, (cuff_z + top) / 2), (0.080, 0.034, top - cuff_z), 0.011,
                           step=(0.03, 0.03, 0.037), band_segments=2, panel_axis=None)
        for v in sl.verts:
            tz = min(1.0, max(0.0, (v.co.z - cuff_z) / (top - cuff_z)))
            v.co.x = xs + (v.co.x - xs) * (0.85 + 0.25 * tz) + sgn * 0.006 * tz   # narrower toward the cuff
            v.co.y *= 0.80 + 0.35 * tz
            v.co.z = min(v.co.z, shoulder(min(1.0, abs(v.co.x) / (w / 2))) - 0.003)
        soft.jitter(sl, 0.0015, 9.0, seed=seed + sgn * 3.0)
        bm_merge(bm, sl)
    return bm


def build_hanger(name, part, x, coll, mats, shirt=None):
    """One hanger at its rest point on the rail (root = the wooden arms, rotated so
    local X runs along the wardrobe's depth); shirt = (length, material, seed)."""
    bm_wood, bm_wire = bmesh.new(), bmesh.new()
    hanger_geometry(bm_wood, bm_wire)
    root = new_object(name, bm_wood, coll, origin=(x, C.RAIL_Y, C.RAIL_Z + C.RAIL_R), material=mats["wy"])
    root.rotation_euler = (0.0, 0.0, math.radians(C.HANGER_ROT_Z))
    finish(root, None, sharp_angle=50.0)
    tag(root, part)
    hook = new_object(f"{name}Hook", bm_wire, coll, material=mats["gx"], parent=root)
    finish(hook, None, sharp_angle=50.0)
    tag(hook, part)
    if shirt is not None:
        length, mat, seed = shirt
        sh = new_object(f"{name}Shirt", shirt_geometry(length, seed), coll, material=mat, parent=root)
        shade(sh, 80.0)
        tag(sh, part)
    return root


def build_hangers(coll, mats):
    build_hanger("Hanger", "hanger", C.HANGERS_X[C.BARE_HANGERS[0]], coll, mats)
    for k, (name, part, key) in enumerate((("HangerShirtA", "hanger_a", "shirt_a"),
                                            ("HangerShirtB", "hanger_b", "shirt_b"))):
        build_hanger(name, part, C.HANGERS_X[C.SHIRTS[k]], coll, mats, (SHIRT_LENGTHS[k], mats[key], 5.0 + k))


# ---------------------------------------------------------------------------
# Doors (door-local coordinates, hinge axis at the origin)
# ---------------------------------------------------------------------------
def build_door(side, coll, mats):
    s = 1.0 if side == "left" else -1.0
    part = f"door_{side}"
    label = "Left" if side == "left" else "Right"
    bm = bmesh.new()
    xa, xb = sorted((0.0, s * C.DOOR_W))
    bm_box(bm, (xa, C.DOOR_Y0, C.DOOR_Z0), (xb, C.DOOR_Y1, C.DOOR_Z1))
    door = new_object(f"Door{label}", bm, coll, origin=C.HINGE_L if s > 0 else C.HINGE_R, material=mats["wz"])
    finish(door, 0.0025, 2)
    tag(door, part)

    hx = s * C.HANDLE_LOCAL_X
    bm = bmesh.new()
    bm_cyl(bm, C.HANDLE_R, C.HANDLE_Z1 - C.HANDLE_Z0,
           Matrix.Translation((hx, C.HANDLE_LOCAL_Y, (C.HANDLE_Z0 + C.HANDLE_Z1) / 2)), 24)
    for z in C.HANDLE_POSTS:
        y0, y1 = C.DOOR_Y0 + 0.001, C.HANDLE_LOCAL_Y
        bm_cyl(bm, 0.0055, abs(y1 - y0), cyl_y((hx, (y0 + y1) / 2, z)), 16)
        bm_cyl(bm, 0.009, 0.0025, cyl_y((hx, C.DOOR_Y0 - 0.00125, z)), 20)  # rosette on the door face
    handle = new_object(f"Door{label}Pull", bm, coll, material=mats["gz"], parent=door)
    finish(handle, 0.0022, 2)
    tag(handle, part)

    tag(new_empty(f"HandleGrip.{label[0]}", coll, (hx, C.HANDLE_LOCAL_Y, C.GRIP_Z), parent=door), part)
    return door


def main():
    clear_scene()
    mats = build_materials()
    body = get_collection("WardrobeBody")
    build_carcass(body, mats)
    build_hardware(body, mats)
    build_linen(body, mats)
    build_collision(get_collection("WardrobeBodyCollision"))
    props = get_collection("WardrobeProps")
    build_drawer(props, mats)
    build_box(props, mats)
    build_hangers(props, mats)
    doors = get_collection("WardrobeDoors")
    build_door("left", doors, mats)
    build_door("right", doors, mats)
    t = {p: part_tris(p) for p in ("body", "body_col", "door_left", "door_right") + tuple(C.PROPS)}
    print("TRIS", t, "total", sum(t.values()))
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
