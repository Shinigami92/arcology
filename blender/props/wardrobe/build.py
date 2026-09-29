"""Stage 1: build the wardrobe geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/wardrobe/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from wardrobe_common import (  # noqa: E402
    BAY_X0, BAY_X1, BAY_XC, BLEND, BODY_H, BODY_RUNNER_T, BODY_RUNNER_Y0, BODY_RUNNER_Y1, BODY_RUNNER_Z0,
    BODY_RUNNER_Z1, BODY_X, BODY_Y, BOX_H, BOX_HD, BOX_HW, BOX_POS, BOX_WALL, CAV_X, CAV_Y_BACK, CAV_Z0,
    CAV_Z1, CUP_R, CUP_U, DIV_X0, DIV_X1, DOOR_W, DOOR_Y0, DOOR_Y1, DOOR_Z0, DOOR_Z1, DRAWER_BOX_HW,
    DRAWER_BOX_Y0, DRAWER_BOX_Y1, DRAWER_BOX_Z1, DRAWER_FLOOR_Z0, DRAWER_FLOOR_Z1, DRAWER_FRONT_T,
    DRAWER_FRONT_Y, DRAWER_GRIP, DRAWER_H, DRAWER_RUNNER_HX, DRAWER_RUNNER_Z0, DRAWER_RUNNER_Z1,
    DRAWER_W, DRAWER_WALL, DRAWER_Z0S, HANDLE_HALF, HANDLE_U, HANDLE_Y, HANDLE_Z0, HANDLE_Z1,
    HANGERS, HANGER_REST_Z, HANGER_WIRE, HINGE_LEFT, HINGE_RIGHT, HINGE_ZS, LEGS, LEG_H, LEG_R_BOT,
    LEG_R_TOP, LID_HD, LID_HW, LID_POS, LID_SKIRT, LID_TOP, PANEL, RAIL_R, RAIL_X0, RAIL_X1, RAIL_Y,
    RAIL_Z, RIGHT_SHELVES, SHELF_Y0, TOP_SHELF, handle_grip,
)
import lib_candidates as cand  # noqa: E402
from arcology_blender import cloth, fabric, soft, wear  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    assign_by_region, bm_box, bm_cone, bm_cyl, bm_open_box, bm_quad, collision_box, cut, cyl_x, cyl_y, finish,
    instance, new_empty, new_object, remove_attribute, set_uvs, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

WALNUT_GROUND = (0.048, 0.023, 0.010)  # about #402717 in sRGB
WALNUT_LINE = (0.018, 0.008, 0.0035)   # about #29180D
GUNMETAL = (0.028, 0.033, 0.040)       # style guide #2E3238
LAMINATE = (0.62, 0.58, 0.50)          # warm off-white interior back, label card
LINEN = (0.64, 0.60, 0.52)
CHARCOAL = (0.055, 0.055, 0.060)
GREYBLUE = (0.16, 0.19, 0.23)
SOFT = 80.0  # shade angle for soft goods


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def handle_standoffs():
    """World (x, z) of the four handle standoffs (both doors closed)."""
    pts = []
    for sign, hinge in ((1, HINGE_LEFT), (-1, HINGE_RIGHT)):
        x = hinge.x + sign * HANDLE_U
        pts += [(x, HANDLE_Z0 + 0.04), (x, HANDLE_Z1 - 0.04)]
    return pts


def handle_region(g):
    """Door fronts around the handles: where hands touch."""
    front = g.maprange(g.y, -0.31, -0.32)
    return g.mul(g.mul(g.band(g.math("ABSOLUTE", g.x), 0.0, 0.10, 0.05), g.band(g.z, 0.95, 1.45, 0.08)), front)


def mat_walnut():
    """Dark walnut veneer, satin: worn edges, rubbed finish around the handle
    standoffs, fingerprints on the door fronts, one scratch on the right door,
    dust on top, faint scuffs near the floor."""
    g = Graph(new_mat("src_walnut"))
    base, rough, h = cand.wood_veneer(g, WALNUT_GROUND, WALNUT_LINE)
    base, rough = wear.edge_highlight(g, base, rough, smoother=-0.06, brighter=0.14)
    base, rough = wear.fixture_wear(g, base, rough, handle_standoffs(), r_in=0.018, r_out=0.055)
    base, rough = wear.smudges(g, base, rough, handle_region(g), rougher=0.09, darker=0.03)
    base, rough = cand.scratch(g, base, rough, (0.215, 1.025), (0.275, 0.985), color=(0.22, 0.15, 0.09))
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.30, z_full=0.10, rougher=0.15, darker=0.12)
    base, rough = wear.top_dust(g, base, rough, 2.06, 2.095, amount=0.30, rougher=0.25)
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_laminate():
    """Warm off-white laminate on the inside of the back panel (and the box label card)."""
    g = Graph(new_mat("src_laminate"))
    rough = g.add(0.55, g.mul(g.sub(g.noise(30.0), 0.5), 0.10))
    base = g.scale_color(LAMINATE, g.add(1.0, g.mul(g.sub(g.noise(3.0, 2.0), 0.5), 0.08)))
    n = g.bump(g.noise(120.0, 2.0), 1.0, 0.0006)
    return g.finish(base, rough, 0.0, n)


def mat_gunmetal():
    """Brushed gunmetal (handles, rail, hangers, legs, hinges, runners) with
    bright worn edges and greasy fingerprints on the handles."""
    g = Graph(new_mat("src_gunmetal"))
    base, rough, h = cand.brushed_metal(g, GUNMETAL)
    base, rough = wear.edge_highlight(g, base, rough, smoother=0.10, brighter=0.45)
    base, rough = wear.smudges(g, base, rough, handle_region(g), rougher=0.20, darker=-0.30)
    return g.finish(base, rough, 1.0, g.bump(h, 1.0, 1.0))


def mat_cloth(name, color, heather=0.06):
    """Woven cloth (linen shirts, folded knits, a blanket, the storage box) with soft creases."""
    g = Graph(new_mat(f"src_{name}"))
    base, rough, h = fabric.fabric_base(g, color, rough=0.90, heather=heather, mottle=0.05)
    base, h = fabric.creases(g, base, h, 1.0, stretch=(10.0, 10.0, 10.0), depth=0.0012, sharp=0.70)
    return fabric.fabric_finish(g, base, rough, h)


def build_materials():
    return {
        "walnut": mat_walnut(),
        "laminate": mat_laminate(),
        "metal": mat_gunmetal(),
        "linen": mat_cloth("linen", LINEN),
        "charcoal": mat_cloth("charcoal", CHARCOAL, heather=0.04),
        "greyblue": mat_cloth("greyblue", GREYBLUE),
    }


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------
def folded(name, coll, center, size, material, seed, parent=None, part="body"):
    """A folded garment: a soft slab with a slight crown and a hidden underside."""
    bm = soft.soft_box(center, size, 0.012, step=0.04, panel_axis=2, crown={"+z": 0.006}, open_faces=("-z",))
    soft.jitter(bm, 0.002, 8.0, seed)
    ob = new_object(name, bm, coll, material=material, parent=parent)
    remove_attribute(ob, soft.SEAM_ATTR)
    shade(ob, SOFT)
    return tag(ob, part)


def build_body(coll, col_coll, mats):
    walnut, laminate, metal = mats["walnut"], mats["laminate"], mats["metal"]

    def body(ob):
        return tag(ob, "body")

    # Carcass: outer box minus the cavity (open to the front)
    bm = bmesh.new()
    bm_box(bm, (-BODY_X, -BODY_Y, LEG_H), (BODY_X, BODY_Y, BODY_H))
    carcass = new_object("Carcass", bm, coll, material=walnut)
    bm = bmesh.new()
    bm_box(bm, (-CAV_X, -0.40, CAV_Z0), (CAV_X, CAV_Y_BACK, CAV_Z1))
    cut(carcass, bm, coll)
    finish(carcass, 0.002, 2)
    assign_by_region(carcass, [
        (((-CAV_X - 0.001, CAV_Y_BACK - 0.001, CAV_Z0 - 0.001), (CAV_X + 0.001, CAV_Y_BACK + 0.001, CAV_Z1 + 0.001)),
         laminate),
    ], walnut)
    body(carcass)

    def panel(name, lo, hi, material=walnut, bevel=0.0015):
        bm = bmesh.new()
        bm_box(bm, lo, hi)
        ob = new_object(name, bm, coll, material=material)
        finish(ob, bevel, 2)
        return body(ob)

    # Top shelf (full width), divider, right-bay shelves
    panel("TopShelf", (-CAV_X, SHELF_Y0, TOP_SHELF - PANEL), (CAV_X, CAV_Y_BACK, TOP_SHELF))
    panel("Divider", (DIV_X0, -CAV_Y_BACK, CAV_Z0), (DIV_X1, CAV_Y_BACK, TOP_SHELF - PANEL))
    for i, t in enumerate(RIGHT_SHELVES):
        panel(f"ShelfRight{i + 1}", (BAY_X0, SHELF_Y0, t - PANEL), (BAY_X1, CAV_Y_BACK, t))

    # Drawer runners on the bay walls (the drawers' own runners ride on them)
    bm = bmesh.new()
    for z0 in DRAWER_Z0S:
        for xa, xb in ((BAY_X0, BAY_X0 + BODY_RUNNER_T), (BAY_X1 - BODY_RUNNER_T, BAY_X1)):
            bm_box(bm, (xa, BODY_RUNNER_Y0, z0 + BODY_RUNNER_Z0), (xb, BODY_RUNNER_Y1, z0 + BODY_RUNNER_Z1))
    runners = new_object("BodyRunners", bm, coll, material=metal)
    finish(runners, 0.0008, 1)
    body(runners)

    # Hanging rail with end flanges
    bm = bmesh.new()
    bm_cyl(bm, RAIL_R, RAIL_X1 - RAIL_X0, cyl_x(((RAIL_X0 + RAIL_X1) / 2, RAIL_Y, RAIL_Z)), 24)
    for x in (RAIL_X0 - 0.002, RAIL_X1 + 0.002):
        bm_cyl(bm, 0.022, 0.005, cyl_x((x, RAIL_Y, RAIL_Z)), 24)
    rail = new_object("Rail", bm, coll, material=metal)
    finish(rail, 0.001, 1)
    body(rail)

    # Folded clothes on the middle right shelf and a blanket on the top shelf
    folded("Folded1", coll, (BAY_XC - 0.01, 0.03, RIGHT_SHELVES[1] + 0.024), (0.30, 0.36, 0.048), mats["greyblue"], 3.0)
    folded("Folded2", coll, (BAY_XC + 0.01, 0.02, RIGHT_SHELVES[1] + 0.048 + 0.021), (0.28, 0.34, 0.042), mats["linen"], 4.0)
    folded("Blanket", coll, (-0.25, 0.02, TOP_SHELF + 0.05), (0.52, 0.42, 0.10), mats["linen"], 5.0)

    # Legs
    bm = bmesh.new()
    for x, y in LEGS:
        bm_cone(bm, LEG_R_BOT, LEG_R_TOP, LEG_H + 0.002, Matrix.Translation((x, y, LEG_H / 2)), 24)
    legs = new_object("Legs", bm, coll, material=metal)
    finish(legs, 0.0015, 1)
    body(legs)

    # Concealed hinge mounting plates on the side panels (4 per door)
    bm = bmesh.new()
    for z in HINGE_ZS:
        bm_box(bm, (-CAV_X, -0.29, z - 0.02), (-CAV_X + 0.003, -0.235, z + 0.02))
        bm_box(bm, (CAV_X - 0.003, -0.29, z - 0.02), (CAV_X, -0.235, z + 0.02))
    plates = new_object("HingePlates", bm, coll, material=metal)
    finish(plates, 0.0008, 1)
    body(plates)

    # Collision boxes for Godot: carcass pieces and every shelf; the drawer openings and the
    # cubby under the drawers stay free (the drawers bring their own collision)
    def col(name, lo, hi):
        ob = tag(collision_box(name, lo, hi, col_coll), "body_col")
        ob.hide_render = True  # never in thumbnails or bakes (export.py un-hides for the glb)

    col("ColBottom", (-BODY_X, -BODY_Y, 0.0), (BODY_X, BODY_Y, CAV_Z0))
    col("ColSideLeft", (-BODY_X, -BODY_Y, CAV_Z0), (-CAV_X, BODY_Y, CAV_Z1))
    col("ColSideRight", (CAV_X, -BODY_Y, CAV_Z0), (BODY_X, BODY_Y, CAV_Z1))
    col("ColTop", (-BODY_X, -BODY_Y, CAV_Z1), (BODY_X, BODY_Y, BODY_H))
    col("ColBack", (-CAV_X, CAV_Y_BACK, CAV_Z0), (CAV_X, BODY_Y, CAV_Z1))
    col("ColTopShelf", (-CAV_X, SHELF_Y0, TOP_SHELF - PANEL), (CAV_X, CAV_Y_BACK, TOP_SHELF))
    col("ColDivider", (DIV_X0, -CAV_Y_BACK, CAV_Z0), (DIV_X1, CAV_Y_BACK, TOP_SHELF - PANEL))
    for i, t in enumerate(RIGHT_SHELVES):
        col(f"ColShelfRight{i + 1}", (BAY_X0, SHELF_Y0, t - PANEL), (BAY_X1, CAV_Y_BACK, t))
    col("ColRail", (RAIL_X0, RAIL_Y - RAIL_R, RAIL_Z - RAIL_R), (RAIL_X1, RAIL_Y + RAIL_R, RAIL_Z + RAIL_R))


# ---------------------------------------------------------------------------
# Doors
# ---------------------------------------------------------------------------
def build_door(name, hinge, sign, part, coll, mats):
    """One door in local coordinates: u runs from the hinge edge along the door
    (world +X for the left door, -X for the right), y depth, z height."""
    walnut, metal = mats["walnut"], mats["metal"]

    def box(bm, u0, u1, y0, y1, z0, z1):
        xa, xb = sorted((sign * u0, sign * u1))
        return bm_box(bm, (xa, y0, z0), (xb, y1, z1))

    # Door slab with recessed hinge cups on the back
    bm = bmesh.new()
    box(bm, 0.0, DOOR_W, DOOR_Y0, DOOR_Y1, DOOR_Z0, DOOR_Z1)
    door = new_object(name, bm, coll, origin=hinge, material=walnut)
    bm = bmesh.new()
    for z in HINGE_ZS:
        bm_cyl(bm, CUP_R + 0.0005, 0.006, cyl_y((sign * CUP_U, DOOR_Y1 - 0.0005, z)), 32)
    cut(door, bm, coll)
    finish(door, 0.0015, 2)
    tag(door, part)

    def child(name, bm, material, bevel_w=None, segs=1):
        ob = new_object(name, bm, coll, material=material, parent=door)
        if bevel_w:
            finish(ob, bevel_w, segs)
        else:
            shade(ob)
        tag(ob, part)
        return ob

    # Hinge cups (flush discs in the recesses) and arms reaching the side panel plates
    bm = bmesh.new()
    for z in HINGE_ZS:
        bm_cyl(bm, CUP_R, 0.0015, cyl_y((sign * CUP_U, DOOR_Y1 - 0.00275, z)), 32)
    child("HingeCups", bm, metal)
    bm = bmesh.new()
    for z in HINGE_ZS:
        box(bm, PANEL + 0.0045, PANEL + 0.0165, DOOR_Y1, 0.062, z - 0.007, z + 0.007)
        box(bm, PANEL + 0.0015, CUP_U + 0.008, DOOR_Y1, DOOR_Y1 + 0.006, z - 0.007, z + 0.007)
    child("HingeArms", bm, metal, 0.0008, 1)

    # Handle: square bar on two round standoffs
    bm = bmesh.new()
    box(bm, HANDLE_U - HANDLE_HALF, HANDLE_U + HANDLE_HALF, HANDLE_Y - HANDLE_HALF, HANDLE_Y + HANDLE_HALF,
        HANDLE_Z0, HANDLE_Z1)
    for z in (HANDLE_Z0 + 0.04, HANDLE_Z1 - 0.04):
        yc = (DOOR_Y0 + HANDLE_Y) / 2
        bm_cyl(bm, 0.0055, abs(HANDLE_Y - DOOR_Y0) + 0.004, cyl_y((sign * HANDLE_U, yc, z)), 20)
    child("Handle", bm, metal, 0.0015, 2)

    # Grip point for the Godot handle
    tag(new_empty("HandleGrip", coll, handle_grip(sign), parent=door), part)
    return door


# ---------------------------------------------------------------------------
# Moving props: drawer, storage box + lid, hangers
# ---------------------------------------------------------------------------
def build_drawers(coll, mats):
    """One drawer (front + open-top box, walnut; runners, gunmetal), origin at the
    front's bottom center, at the lower slot; the upper slot gets a linked copy."""
    walnut, metal = mats["walnut"], mats["metal"]
    hw = DRAWER_W / 2
    origin = Vector((BAY_XC, DRAWER_FRONT_Y, DRAWER_Z0S[0]))

    bm = bmesh.new()
    bm_box(bm, (-hw, 0.0, 0.0), (hw, DRAWER_FRONT_T, DRAWER_H))
    bm_open_box(bm, (-DRAWER_BOX_HW, DRAWER_BOX_Y0, DRAWER_FLOOR_Z0),
                (DRAWER_BOX_HW, DRAWER_BOX_Y1, DRAWER_BOX_Z1), DRAWER_WALL,
                floor=DRAWER_FLOOR_Z1 - DRAWER_FLOOR_Z0)
    drawer = new_object("DrawerLower", bm, coll, origin=origin, material=walnut)
    bm = bmesh.new()  # routed finger pull along the top edge of the front
    bm_box(bm, (-0.06, -0.01, DRAWER_H - 0.028), (0.06, 0.010, DRAWER_H + 0.01))
    cut(drawer, bm, coll)
    finish(drawer, 0.0015, 2)
    tag(drawer, "drawer_lower")

    bm = bmesh.new()
    for s in (-1, 1):
        xa, xb = sorted((s * DRAWER_BOX_HW, s * DRAWER_RUNNER_HX))
        bm_box(bm, (xa, DRAWER_BOX_Y0 + 0.012, DRAWER_RUNNER_Z0), (xb, DRAWER_BOX_Y1 - 0.008, DRAWER_RUNNER_Z1))
    runners = new_object("DrawerRunners", bm, coll, material=metal, parent=drawer)
    finish(runners, 0.0008, 1)
    tag(runners, "drawer_lower")
    tag(new_empty("HandleGrip", coll, DRAWER_GRIP, parent=drawer), "drawer_lower")

    upper = instance(drawer, "DrawerUpper", (BAY_XC, DRAWER_FRONT_Y, DRAWER_Z0S[1]), collection=coll)
    tag(upper, "drawer_upper")
    tag(instance(runners, "DrawerRunners.upper", (0, 0, 0), collection=coll, parent=upper), "drawer_upper")
    tag(new_empty("HandleGrip.upper", coll, DRAWER_GRIP, parent=upper), "drawer_upper")


def build_box(coll, mats):
    """Fabric-covered storage box (open top) with a folded knit inside and a
    gunmetal label holder on the front; origin at its bottom center."""
    linen, metal, laminate = mats["linen"], mats["metal"], mats["laminate"]
    bm = bmesh.new()
    bm_open_box(bm, (-BOX_HW, -BOX_HD, 0.0), (BOX_HW, BOX_HD, BOX_H), BOX_WALL)
    box = new_object("StorageBox", bm, coll, origin=BOX_POS, material=linen)
    finish(box, 0.003, 2)
    tag(box, "box")
    folded("BoxContent", coll, (0.0, 0.0, BOX_WALL + 0.026), (0.26, 0.30, 0.052), mats["greyblue"], 6.0,
           parent=box, part="box")
    bm = bmesh.new()
    y = -BOX_HD
    bm_box(bm, (-0.036, y - 0.0025, 0.105), (0.036, y - 0.0005, 0.150))
    frame = new_object("BoxLabelFrame", bm, coll, material=metal, parent=box)
    bm = bmesh.new()
    bm_box(bm, (-0.031, y - 0.004, 0.110), (0.031, y + 0.001, 0.145))
    cut(frame, bm, coll)
    finish(frame, 0.0006, 1)
    tag(frame, "box")
    bm = bmesh.new()
    yc = y - 0.0012
    bm_quad(bm, ((-0.031, yc, 0.110), (0.031, yc, 0.110), (0.031, yc, 0.145), (-0.031, yc, 0.145)))
    card = new_object("BoxLabelCard", bm, coll, material=laminate, parent=box)
    set_uvs(card, ((0, 0), (1, 0), (1, 1), (0, 1)))
    shade(card)
    tag(card, "box")


def build_lid(coll, mats):
    """Lift-off lid: top panel over a skirt that drops over the box; origin at the skirt's bottom."""
    bm = bmesh.new()
    bm_open_box(bm, (-LID_HW, -LID_HD, 0.0), (LID_HW, LID_HD, LID_SKIRT + LID_TOP), BOX_WALL, floor=LID_TOP)
    bmesh.ops.scale(bm, vec=(1.0, 1.0, -1.0), verts=bm.verts)  # open side down
    bmesh.ops.translate(bm, vec=(0.0, 0.0, LID_SKIRT + LID_TOP), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    lid = new_object("BoxLid", bm, coll, origin=LID_POS, material=mats["linen"])
    finish(lid, 0.003, 2)
    tag(lid, "lid")


def build_hangers(coll, mats):
    """Four hangers on the rail: wire (root, origin at the hook's resting point,
    shoulders along local X) with an optional garment child; roots turned 90
    degrees so the shoulders run across the rail. The second bare hanger is a
    linked copy of the first."""
    metal = mats["metal"]
    rot = (0.0, 0.0, math.radians(90.0))
    bare = None
    for i, (x, garment) in enumerate(HANGERS):
        part = f"hanger{i + 1}"
        pos = (x, RAIL_Y, HANGER_REST_Z)
        if garment is None and bare is not None:
            tag(instance(bare, f"Hanger{i + 1}", pos, rot, collection=coll), part)
            continue
        bm = bmesh.new()
        neck_z = cand.wire_hanger(bm, RAIL_R, HANGER_WIRE)
        hanger = new_object(f"Hanger{i + 1}", bm, coll, origin=pos, material=metal)
        hanger.rotation_euler = rot
        shade(hanger, 60.0)
        tag(hanger, part)
        if garment is None:
            bare = hanger
            continue
        bm = cloth.hanging_garment(seed=float(i))
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, neck_z + 0.004))
        ob = new_object(f"Garment{i + 1}", bm, coll, material=mats[garment], parent=hanger)
        remove_attribute(ob, soft.SEAM_ATTR)
        shade(ob, SOFT)
        tag(ob, part)


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("WardrobeBody"), get_collection("WardrobeBodyCollision"), mats)
    build_door("DoorLeft", HINGE_LEFT, 1, "door_left", get_collection("WardrobeDoorLeft"), mats)
    build_door("DoorRight", HINGE_RIGHT, -1, "door_right", get_collection("WardrobeDoorRight"), mats)
    props = get_collection("WardrobeProps")
    build_drawers(props, mats)
    build_box(props, mats)
    build_lid(props, mats)
    build_hangers(props, mats)
    counts = {p: part_tris(p) for p in ("body", "body_col", "door_left", "door_right", "drawer_lower",
                                        "drawer_upper", "box", "lid", "hanger1", "hanger2", "hanger3", "hanger4")}
    print("TRIS " + " ".join(f"{k}={v}" for k, v in counts.items()) + f" total={sum(counts.values())}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
