"""Stage 1: build the entrance door (frame, leaf, levers, thumb-turn) and its procedural
source materials, save the .blend.

  blender -b --factory-startup --python blender/props/door_entrance/build.py

Everything is modeled in world coordinates around the opening (see door_entrance_common);
each exported part is joined into one mesh (one draw call, one baked material), then the
moving parts get their pivot as origin (`reorigin`).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

from door_entrance_common import (  # noqa: E402
    APT_PAINT, BARREL_R, BLEND, BOLT_Z, CASING_OUT, GRIME, GRIP_APT, GRIP_COR, GUNMETAL,
    GUNMETAL_WORN, HEAD_SOFFIT_Z, HINGE, HINGE_ZS, KNUCKLE, LATCH_BEVEL, LEAF_CX, LEAF_T, LEAF_X0,
    LEAF_X1, LEAF_Y0, LEAF_Y1, LEAF_Z0, LEAF_Z1, LED_CYAN, LED_MAT, LED_R0, LED_R1, LED_STRENGTH,
    LEVER_LEN, LEVER_REACH, LEVER_Z, LOCK_FRONT_Y, LOCK_W, LOCK_Z0, LOCK_Z1, LX, OPEN_H, OX, PEEP_Z,
    PLATE_Z, REBATE_IN, ROSE_PROUD, SEAL_Y0, SEAL_Y1, SEAL_Z0, SOFFIT_X, STEEL, STOP_IN, STOP_X,
    STOP_Y, HEAD_STOP_Z, THRESHOLD_H, THRESHOLD_Y, UNIT_NUMBER, WALL_Y, Y_APT, Y_COR,
)
from lib_candidates import bm_prism, lathe_along, miter_sweep, reorigin, self_union, stroke_text  # noqa: E402
from arcology_blender import materials, metal, wear  # noqa: E402
from arcology_blender.curves import round_polyline, rounded_rect_profile, sweep  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    assign_by_region, bm_box, collision_box, cut, finish, join, new_empty, new_object, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat, solid_mat  # noqa: E402

SCRATCH_COAT = (0.085, 0.088, 0.094)  # scratched powder coat: lighter, not bare-steel bright
KEEPS = (  # latch and deadbolt keeps in the latch jamb: (y0, y1, z0, z1)
    (-0.0860, -0.0690, LEVER_Z - 0.017, LEVER_Z + 0.017),
    (-0.0870, -0.0680, BOLT_Z - 0.015, BOLT_Z + 0.015),
)
STRIKES = ((LEVER_Z - 0.055, LEVER_Z + 0.055), (BOLT_Z - 0.045, BOLT_Z + 0.045))  # z ranges
STRIKE_Y = (-0.0955, -0.0595)


# ---------------------------------------------------------------------------
# Materials (src_*, baked). Medium-scale wear only: fine contrast shimmers in VR.
# ---------------------------------------------------------------------------
def facing_cor(g):
    return g.maprange(g.ny, 0.5, 0.8)


def facing_apt(g):
    return g.maprange(g.ny, -0.5, -0.8)


def mat_frame_paint():
    """Gunmetal powder-coated pressed steel: orange peel, chipped convex edges (more at the
    floor and around the strike), kick scuffs, floor grime, dust on the head casing."""
    g = Graph(new_mat("src_frame_paint"))
    base = g.scale_color(GUNMETAL, g.add(0.94, g.mul(g.noise(3.0, 2.0), 0.12)))
    rough = g.add(0.46, g.mul(g.sub(g.noise(9.0, 2.0), 0.5), 0.10))
    h = g.mul(g.noise(160.0, 2.0), 0.00006)  # orange peel
    edge = wear.convex_edges(g, radius=0.002)
    low = g.maprange(g.z, 0.45, 0.05)
    latch = g.mul(g.band(g.x, 0.38, 0.52, 0.03), g.band(g.z, 0.95, 1.45, 0.08))
    mask = g.math("MAXIMUM", g.math("MAXIMUM", low, latch), 0.22)
    mask = g.mul(mask, g.maprange(g.noise(14.0, 2.0), 0.35, 0.6))
    base, rough = wear.edge_wear(g, base, rough, edge, mask, GUNMETAL_WORN, amount=0.75, rough_delta=-0.12)
    met = g.mul(g.mul(edge, mask), 0.8)
    base, rough = wear.bottom_scuffs(g, base, rough, 0.30, 0.06, rougher=0.25, darker=0.20)
    base = wear.floor_grime(g, base, 0.0, 0.12, 0.70)
    base, rough = wear.top_dust(g, base, rough, OPEN_H + CASING_OUT - 0.012, OPEN_H + CASING_OUT - 0.002,
                                amount=0.30)
    # Key and ring scratches on the corridor casing next to the lock
    m = facing_cor(g)
    for p0, p1 in (((0.47, 1.18), (0.485, 1.26)), ((0.462, 1.30), (0.49, 1.33)), ((0.468, 1.05), (0.476, 1.12))):
        base, rough, h = wear.scratch(g, base, rough, h, p0, p1, width=0.0030, mask=m, color=SCRATCH_COAT,
                                      amount=0.35, rougher=0.10, wobble=0.25)
    return g.finish_height(base, rough, met, h)


def mat_steel(name, axis="X", rough=0.30, scuffs=False, grime_z=0.10, darker=1.0):
    """Brushed stainless (hinges, strikes, roses, kick plate): streaks along `axis`."""
    g = Graph(new_mat(f"src_{name}"))
    r, h = metal.brushed(g, rough, axis=axis)
    base = g.scale_color(tuple(c * darker for c in STEEL), g.add(0.95, g.mul(g.noise(6.0, 2.0), 0.10)))
    if scuffs:
        base, r = wear.bottom_scuffs(g, base, r, 0.30, 0.05, rougher=0.22, darker=0.18)
    base = wear.floor_grime(g, base, 0.0, grime_z, 0.65)
    return g.finish_height(base, r, 1.0, h)


def mat_threshold():
    """Brushed steel threshold: walked-on middle rougher and duller, grime toward the jambs."""
    g = Graph(new_mat("src_threshold"))
    r, h = metal.brushed(g, 0.34, axis="X")
    base = g.scale_color(STEEL, g.add(0.92, g.mul(g.noise(6.0, 2.0), 0.12)))
    walk = g.mul(g.band(g.x, -0.25, 0.25, 0.15), g.maprange(g.noise(1.0, 3.0, 0.6, g.vec(4.0, 40.0, 4.0)), 0.4, 0.7))
    r = g.add(r, g.mul(walk, 0.18))
    base = g.scale_color(base, g.sub(1.0, g.mul(walk, 0.15)))
    ends = g.maprange(g.math("ABSOLUTE", g.x), 0.33, 0.42)
    base = g.mixc(g.mul(ends, 0.45), base, GRIME)
    r = g.add(r, g.mul(ends, 0.2))
    return g.finish_height(base, r, g.sub(1.0, g.mul(ends, 0.45)), h)


def leaf_side_chain(g, corridor):
    """One face's finish: (base, rough, metal, height) for the corridor (gunmetal, battered)
    or the apartment (greige satin paint, cleaner)."""
    edge = wear.convex_edges(g, radius=0.0025)
    if corridor:
        base = g.scale_color(GUNMETAL, g.add(0.93, g.mul(g.noise(2.5, 2.0), 0.14)))
        rough = g.add(0.55, g.mul(g.sub(g.noise(11.0, 2.0), 0.5), 0.10))
        h = g.mul(g.noise(320.0, 2.0), 0.00004)  # fine structured coat
        # Recessed panel outline (V-groove), medium scale
        x0, x1, z0, z1, w = LEAF_CX - 0.28, LEAF_CX + 0.28, 0.42, 1.95, 0.0025
        vert = g.mul(g.add(g.band(g.x, x0 - w, x0 + w, 0.0012), g.band(g.x, x1 - w, x1 + w, 0.0012)),
                     g.band(g.z, z0 - w, z1 + w, 0.0005))
        horiz = g.mul(g.add(g.band(g.z, z0 - w, z0 + w, 0.0012), g.band(g.z, z1 - w, z1 + w, 0.0012)),
                      g.band(g.x, x0 - w, x1 + w, 0.0005))
        groove = g.math("MINIMUM", g.add(vert, horiz), 1.0)
        h = g.sub(h, g.mul(groove, 0.0012))
        base = g.scale_color(base, g.sub(1.0, g.mul(groove, 0.25)))
        # Dents, low on the leaf (kicked luggage, trolleys)
        dent = g.mul(g.maprange(g.noise(5.0, 2.0, 0.5, g.offset((3.1, 0.0, 1.7))), 0.68, 0.80),
                     g.maprange(g.z, 1.1, 0.5))
        h = g.sub(h, g.mul(dent, 0.0007))
        base = g.scale_color(base, g.sub(1.0, g.mul(dent, 0.12)))
        m = facing_cor(g)
        # Keys missing the cylinder, a ring scraping past the lever
        for p0, p1 in (((0.322, 1.34), (0.345, 1.29)), ((0.39, 1.33), (0.372, 1.276)), ((0.33, 1.255), (0.352, 1.24)),
                       ((0.395, 1.27), (0.41, 1.31)), ((0.30, 1.125), (0.345, 1.09)), ((0.29, 1.07), (0.33, 1.06)),
                       ((0.385, 1.06), (0.40, 1.02)), ((0.34, 1.36), (0.36, 1.40))):
            base, rough, h = wear.scratch(g, base, rough, h, p0, p1, width=0.0030, mask=m, color=SCRATCH_COAT,
                                          amount=0.40, rougher=0.10, depth=0.00008, wobble=0.25)
        # Sticker residue: ragged pale rectangle with a dirty adhesive rim
        rect = g.mul(g.rect_xz((-0.22, 1.16), (-0.10, 1.245), 0.002), m)
        rag = g.maprange(g.noise(25.0, 2.0, 0.5), 0.25, 0.60)
        res = g.mul(rect, rag)
        base = g.mixc(g.mul(res, 0.16), base, (0.085, 0.082, 0.072))
        rough = g.add(rough, g.mul(res, 0.18))
        rim = g.mul(g.sub(g.rect_xz((-0.226, 1.154), (-0.094, 1.251), 0.003), rect), m)
        base = g.mixc(g.mul(rim, 0.35), base, GRIME)
        # Grime low and at the floor
        base, rough = wear.low_grime(g, base, rough, 0.50, 0.02, GRIME, amount=0.55, rougher=0.15)
        base, rough = wear.bottom_scuffs(g, base, rough, 0.40, 0.08, rougher=0.20, darker=0.25)
        base = wear.floor_grime(g, base, 0.0, 0.10, 0.6)
        emask = g.mul(g.math("MAXIMUM", g.maprange(g.z, 0.5, 0.05), 0.35), g.maprange(g.noise(12.0, 2.0), 0.3, 0.6))
        base, rough = wear.edge_wear(g, base, rough, edge, emask, GUNMETAL_WORN, amount=0.8, rough_delta=-0.12)
        met = g.mul(g.mul(edge, emask), 0.8)
    else:
        base = g.scale_color(APT_PAINT, g.add(0.96, g.mul(g.noise(2.0, 2.0), 0.08)))
        rough = g.add(0.38, g.mul(g.sub(g.noise(8.0, 2.0), 0.5), 0.08))
        h = g.mul(g.noise(90.0, 2.0), 0.00002)  # roller texture
        base, rough = wear.fixture_wear(g, base, rough, [(LX, LEVER_Z), (LX, BOLT_Z)], r_in=0.03, r_out=0.075,
                                        rougher=0.14, lighter=0.12)
        region = g.mul(g.band(g.x, 0.18, 0.43, 0.04), g.band(g.z, 0.95, 1.55, 0.08))
        base, rough = wear.smudges(g, base, rough, g.mul(region, facing_apt(g)), rougher=0.20, darker=0.07)
        # Shoe scuffs at the bottom, a little dust on the top edge
        base, rough = wear.bottom_scuffs(g, base, rough, 0.32, 0.05, rougher=0.25, darker=0.22, mask=facing_apt(g))
        base = wear.floor_grime(g, base, 0.0, 0.08, 0.8)
        emask = g.mul(g.math("MAXIMUM", g.maprange(g.z, 0.35, 0.05), 0.15), g.maprange(g.noise(12.0, 2.0), 0.35, 0.6))
        base, rough = wear.edge_wear(g, base, rough, edge, emask, (0.36, 0.35, 0.33), amount=0.6, rough_delta=0.05)
        met = 0.0
    return base, rough, met, h


def mat_leaf_paint():
    """Two-sided leaf finish split at the leaf's mid-plane: battered gunmetal corridor face,
    clean greige apartment face. Dust on the top edge."""
    g = Graph(new_mat("src_leaf_paint"))
    side = g.maprange(g.y, LEAF_Y0 + LEAF_T / 2 - 0.002, LEAF_Y0 + LEAF_T / 2 + 0.002)  # 1 = corridor
    ab, ar, am, ah = leaf_side_chain(g, corridor=False)
    cb, cr, cm, ch = leaf_side_chain(g, corridor=True)
    base = g.mixc(side, ab, cb)
    rough = g.mixf(side, ar, cr)
    met = g.mul(side, cm)
    h = g.mixf(side, ah, ch)
    base, rough = wear.top_dust(g, base, rough, LEAF_Z1 - 0.004, LEAF_Z1 - 0.001, amount=0.35)
    return g.finish_height(base, rough, met, h)


def mat_hardware():
    """Brushed stainless levers and thumb-turn, polished and smudged by hands."""
    g = Graph(new_mat("src_hw_steel"))
    r, h = metal.brushed(g, 0.27, axis="X")
    base = g.scale_color(STEEL, g.add(0.96, g.mul(g.noise(8.0, 2.0), 0.08)))
    base, r = wear.smudges(g, base, r, 1.0, rougher=0.12, darker=0.04)
    base, r = wear.edge_highlight(g, base, r, smoother=0.08, brighter=0.08)
    return g.finish_height(base, r, 1.0, h)


def mat_satin(name, base, rough, height=0.00003, scale=400.0):
    """Smooth satin finish (anodized plate, smart-lock housing): faint roughness mottling."""
    g = Graph(new_mat(f"src_{name}"))
    r = g.add(rough, g.mul(g.sub(g.noise(18.0, 2.0), 0.5), 0.08))
    base = g.scale_color(base, g.add(0.95, g.mul(g.noise(5.0, 2.0), 0.10)))
    return g.finish_height(base, r, 0.0, g.mul(g.noise(scale, 2.0), height))


def build_materials():
    return {
        "frame": mat_frame_paint(),
        "frame_steel": mat_steel("frame_steel", axis="Z", rough=0.34, darker=0.62),
        "hinge_leaf": mat_steel("hinge_leaf", axis="Z", rough=0.34, darker=0.62),
        "threshold": mat_threshold(),
        "seal": materials.rubber("seal", base=(0.022, 0.022, 0.024), rough=0.78),
        "keep": materials.dark_plastic("keep", base=(0.012, 0.012, 0.013), rough=0.6),
        "leaf": mat_leaf_paint(),
        "leaf_steel": mat_steel("leaf_steel", axis="X", rough=0.29, scuffs=True),
        "digits": mat_satin("digits", (0.70, 0.69, 0.655), 0.45),  # enamel: readable under any light
        "plate": mat_satin("plate", (0.016, 0.017, 0.019), 0.36),
        "housing": mat_satin("lock_housing", (0.026, 0.028, 0.032), 0.30),
        "lens": materials.gloss_paint("lens", (0.004, 0.005, 0.007), rough=0.06),
        "pad": mat_satin("finger_pad", (0.045, 0.050, 0.058), 0.14, height=0.0),
        "hw": mat_hardware(),
        "led": solid_mat(LED_MAT, (0.02, 0.10, 0.12), 0.25, emission=LED_CYAN, emission_strength=LED_STRENGTH),
    }


# ---------------------------------------------------------------------------
# Frame (static, world coordinates)
# ---------------------------------------------------------------------------
FRAME_PATH = [(-OX, 0.0, 0.0), (-OX, 0.0, OPEN_H), (OX, 0.0, OPEN_H), (OX, 0.0, 0.0)]
# Profile (u outward from the rough opening edge, v = y): apartment casing, rebate soffit,
# stop face, stop soffit, corridor casing, back over the wall faces and the reveal.
FRAME_PROFILE = [
    (CASING_OUT, Y_APT), (-REBATE_IN, Y_APT), (-REBATE_IN, STOP_Y), (-STOP_IN, STOP_Y), (-STOP_IN, Y_COR),
    (CASING_OUT, Y_COR), (CASING_OUT, WALL_Y), (0.0, WALL_Y), (0.0, -WALL_Y), (CASING_OUT, -WALL_Y),
]


def build_frame(coll, col_coll, mats):
    parts = []

    bm = bmesh.new()
    miter_sweep(bm, FRAME_PATH, FRAME_PROFILE, (0.0, 1.0, 0.0))
    frame = new_object("FrameProfile", bm, coll, material=mats["frame"])
    finish(frame, 0.0015, 2)
    bm = bmesh.new()
    for y0, y1, z0, z1 in KEEPS:
        bm_box(bm, (SOFFIT_X - 0.002, y0, z0), (OX - 0.004, y1, z1))
    cut(frame, bm, coll)
    shade(frame)
    box = ((SOFFIT_X + 0.0003, -0.10, 0.9), (OX - 0.0035, -0.05, 1.5))
    assign_by_region(frame, [(box, mats["keep"])], mats["frame"])
    parts.append(frame)

    # Strike plates on the latch-jamb rebate soffit, with the keep openings
    bm = bmesh.new()
    for z0, z1 in STRIKES:
        bm_box(bm, (SOFFIT_X - 0.0024, STRIKE_Y[0], z0), (SOFFIT_X + 0.0004, STRIKE_Y[1], z1))
    strikes = new_object("Strikes", bm, coll, material=mats["frame_steel"])
    finish(strikes, 0.0007, 1)
    bm = bmesh.new()
    for y0, y1, z0, z1 in KEEPS:
        bm_box(bm, (SOFFIT_X - 0.004, y0, z0), (SOFFIT_X + 0.002, y1, z1))
    cut(strikes, bm, coll)
    shade(strikes)
    parts.append(strikes)

    # Rubber seal in the rebate, on the stop face
    seal_profile = [(-0.0420, SEAL_Y1), (-0.0420, -0.0425), (-0.0405, SEAL_Y0), (-0.0280, SEAL_Y0),
                    (-0.0265, -0.0425), (-0.0265, SEAL_Y1)]
    path = [(-OX, 0.0, THRESHOLD_H + 0.0015), (-OX, 0.0, OPEN_H), (OX, 0.0, OPEN_H), (OX, 0.0, THRESHOLD_H + 0.0015)]
    bm = bmesh.new()
    miter_sweep(bm, path, seal_profile, (0.0, 1.0, 0.0))
    seal = new_object("Seal", bm, coll, material=mats["seal"])
    shade(seal, 50.0)
    parts.append(seal)

    # Threshold: low beveled steel plate across the reveal
    poly = [(-THRESHOLD_Y, 0.0), (THRESHOLD_Y, 0.0), (THRESHOLD_Y, 0.0015), (0.085, THRESHOLD_H),
            (-0.085, THRESHOLD_H), (-THRESHOLD_Y, 0.0015)]
    bm = bmesh.new()
    bm_prism(bm, poly, -SOFFIT_X, SOFFIT_X, axis="X")
    thr = new_object("Threshold", bm, coll, material=mats["threshold"])
    finish(thr, 0.0008, 1)
    parts.append(thr)

    # Frame halves of the three weld-on barrel hinges (lower knuckle + wing on the casing)
    bm = bmesh.new()
    wings = bmesh.new()
    for zc in HINGE_ZS:
        b, t = zc - 0.001 - KNUCKLE, zc - 0.001
        prof = [(0.0, b - 0.010), (0.0045, b - 0.009), (0.0075, b - 0.006), (0.0090, b - 0.003), (BARREL_R, b),
                (BARREL_R, t - 0.0008), (BARREL_R - 0.0007, t), (0.0, t)]
        lathe_along(bm, prof, (HINGE.x, HINGE.y, 0.0), (0, 0, 1), segments=20)
        bm_box(wings, (HINGE.x - 0.042, -0.117, b + 0.005), (HINGE.x - 0.002, Y_APT + 0.0004, t - 0.005))
    knuckles = new_object("HingeFrameKnuckles", bm, coll, material=mats["frame_steel"])
    shade(knuckles, 40.0)
    parts.append(knuckles)
    w = new_object("HingeFrameWings", wings, coll, material=mats["frame_steel"])
    finish(w, 0.0012, 1)
    parts.append(w)

    body = join(parts, "Frame")
    tag(body, "body")

    # Collision: jambs (reveal lining + casings) and the stops, head and head stop. The
    # threshold (10 mm, beveled) gets none: the floor carries the player.
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    top = OPEN_H + CASING_OUT
    col("ColJambHinge", (-OX - CASING_OUT, Y_APT, 0.0), (-SOFFIT_X, Y_COR, top))
    col("ColJambLatch", (SOFFIT_X, Y_APT, 0.0), (OX + CASING_OUT, Y_COR, top))
    col("ColStopHinge", (-SOFFIT_X, STOP_Y, 0.0), (-STOP_X, Y_COR, HEAD_STOP_Z))
    col("ColStopLatch", (STOP_X, STOP_Y, 0.0), (SOFFIT_X, Y_COR, HEAD_STOP_Z))
    col("ColHead", (-SOFFIT_X, Y_APT, HEAD_SOFFIT_Z), (SOFFIT_X, Y_COR, top))
    col("ColHeadStop", (-STOP_X, STOP_Y, HEAD_STOP_Z), (STOP_X, Y_COR, HEAD_SOFFIT_Z))
    return body


# ---------------------------------------------------------------------------
# Leaf (moving): built in world coordinates (closed), joined, origin moved to the hinge axis
# ---------------------------------------------------------------------------
def latch_edge_x(y):
    return LEAF_X1 - (y - LEAF_Y0) * LATCH_BEVEL


def build_leaf(coll, mats):
    parts = []

    def piece(name, bm, mat, bevel=None, segs=1, sharp=30.0):
        ob = new_object(name, bm, coll, material=mats[mat])
        if bevel:
            finish(ob, bevel, segs, sharp_angle=sharp)
        else:
            shade(ob, sharp)
        parts.append(ob)
        return ob

    # Slab, latch edge beveled 3 degrees so it clears the latch jamb through the swing
    poly = [(LEAF_X0, LEAF_Y0), (LEAF_X1, LEAF_Y0), (latch_edge_x(LEAF_Y1), LEAF_Y1), (LEAF_X0, LEAF_Y1)]
    bm = bmesh.new()
    bm_prism(bm, poly, LEAF_Z0, LEAF_Z1, axis="Z")
    piece("Slab", bm, "leaf", 0.002, 2)

    # Drop seal under the leaf
    bm = bmesh.new()
    bm_box(bm, (LEAF_X0 + 0.006, -0.095, SEAL_Z0), (LEAF_X1 - 0.008, -0.060, LEAF_Z0 + 0.001))
    piece("DropSeal", bm, "seal", 0.0012, 1)

    # Kick plate with six screws (corridor face)
    kx0, kx1 = LEAF_X0 + 0.025, latch_edge_x(LEAF_Y1) - 0.025
    bm = bmesh.new()
    bm_box(bm, (kx0, LEAF_Y1 - 0.0003, 0.035), (kx1, LEAF_Y1 + 0.0015, 0.285))
    piece("KickPlate", bm, "leaf_steel", 0.0007, 1)
    bm = bmesh.new()
    for x in (kx0 + 0.02, (kx0 + kx1) / 2, kx1 - 0.02):
        for z in (0.052, 0.268):
            lathe_along(bm, [(0.0, 0.0), (0.0036, 0.0), (0.0034, 0.0006), (0.0022, 0.0011), (0.0, 0.0013)],
                        (x, LEAF_Y1 + 0.0014, z), (0, 1, 0), segments=10)
    piece("KickScrews", bm, "leaf_steel", sharp=50.0)

    # Unit number plate (corridor face): dark plate, raised off-white enamel digits, 4 screws
    px0, px1, pz0, pz1 = LEAF_CX - 0.118, LEAF_CX + 0.118, PLATE_Z - 0.052, PLATE_Z + 0.052
    face = LEAF_Y1 + 0.004
    bm = bmesh.new()
    bm_box(bm, (px0, LEAF_Y1 - 0.0003, pz0), (px1, face, pz1))
    piece("NumberPlate", bm, "plate", 0.0016, 2)
    bm = bmesh.new()
    stroke_text(bm, UNIT_NUMBER, (LEAF_CX, face - 0.0003, PLATE_Z - 0.032), height=0.064, width=0.040,
                stroke=0.0088, depth=0.0024, pitch=0.051, u_axis=(-1, 0, 0), v_axis=(0, 0, 1), n_axis=(0, 1, 0))
    digits = new_object("Digits", bm, coll, material=mats["digits"])
    self_union(digits)  # strokes overlap at the joints: one clean surface for render and bake
    shade(digits, 40.0)
    parts.append(digits)
    bm = bmesh.new()
    for x in (px0 + 0.009, px1 - 0.009):
        for z in (pz0 + 0.009, pz1 - 0.009):
            lathe_along(bm, [(0.0, 0.0), (0.0028, 0.0), (0.0026, 0.0005), (0.0016, 0.0009), (0.0, 0.001)],
                        (x, face - 0.0002, z), (0, 1, 0), segments=10)
    piece("PlateScrews", bm, "leaf_steel", sharp=50.0)

    # Peepholes
    bm = bmesh.new()
    lathe_along(bm, [(0.0, -0.0003), (0.0115, -0.0003), (0.0115, 0.0015), (0.0105, 0.003), (0.0075, 0.0038),
                     (0.0, 0.0038)], (LEAF_CX, LEAF_Y1, PEEP_Z), (0, 1, 0), segments=24)
    lathe_along(bm, [(0.0, -0.0003), (0.016, -0.0003), (0.016, 0.006), (0.0145, 0.0085), (0.0085, 0.0095),
                     (0.0, 0.0095)], (LEAF_CX, LEAF_Y0, PEEP_Z), (0, -1, 0), segments=24)
    piece("Peepholes", bm, "leaf_steel", sharp=40.0)
    bm = bmesh.new()
    lathe_along(bm, [(0.0, 0.0034), (0.0072, 0.0034), (0.0058, 0.0044), (0.0032, 0.0050), (0.0, 0.0052)],
                (LEAF_CX, LEAF_Y1, PEEP_Z), (0, 1, 0), segments=24)
    lathe_along(bm, [(0.0, 0.0090), (0.0080, 0.0090), (0.0062, 0.0100), (0.0035, 0.0106), (0.0, 0.0108)],
                (LEAF_CX, LEAF_Y0, PEEP_Z), (0, -1, 0), segments=24)
    piece("PeepLenses", bm, "lens", sharp=60.0)

    # Lever roses (both faces) and the armored key-cylinder rose (corridor)
    rose = [(0.0, -0.0003), (0.026, -0.0003), (0.026, 0.004), (0.024, 0.0075), (0.020, ROSE_PROUD),
            (0.0, ROSE_PROUD)]
    bm = bmesh.new()
    lathe_along(bm, rose, (LX, LEAF_Y0, LEVER_Z), (0, -1, 0), segments=32)
    lathe_along(bm, rose, (LX, LEAF_Y1, LEVER_Z), (0, 1, 0), segments=32)
    lathe_along(bm, [(0.0, -0.0003), (0.028, -0.0003), (0.028, 0.005), (0.025, 0.010), (0.0165, 0.0128),
                     (0.0, 0.0128)], (LX, LEAF_Y1, BOLT_Z), (0, 1, 0), segments=32)
    piece("Roses", bm, "leaf_steel", sharp=40.0)
    bm = bmesh.new()
    lathe_along(bm, [(0.0, 0.012), (0.0095, 0.012), (0.0095, 0.0146), (0.0088, 0.0152), (0.0, 0.0152)],
                (LX, LEAF_Y1, BOLT_Z), (0, 1, 0), segments=24)
    plug = new_object("CylinderPlug", bm, coll, material=mats["leaf_steel"])
    bm = bmesh.new()
    bm_box(bm, (LX - 0.0009, LEAF_Y1 + 0.0135, BOLT_Z - 0.0062), (LX + 0.0009, LEAF_Y1 + 0.017, BOLT_Z + 0.0042))
    cut(plug, bm, coll)
    shade(plug, 40.0)
    parts.append(plug)

    # Smart-lock housing (apartment face) with a fingerprint pad above the thumb-turn
    bm = bmesh.new()
    bm_box(bm, (LX - LOCK_W / 2, LOCK_FRONT_Y, LOCK_Z0), (LX + LOCK_W / 2, LEAF_Y0 + 0.0003, LOCK_Z1))
    piece("LockHousing", bm, "housing", 0.0065, 3)
    bm = bmesh.new()
    bm_box(bm, (LX - 0.0115, LOCK_FRONT_Y - 0.0006, 1.344), (LX + 0.0115, LOCK_FRONT_Y + 0.001, 1.368))
    piece("FingerPad", bm, "pad", 0.0025, 2)

    # Lock faceplate on the latch edge, latch and bolt fronts (retracted, flush)
    def edge_plate(y0, y1, z0, z1, out):
        return [(latch_edge_x(y0) - 0.0004, y0), (latch_edge_x(y0) + out, y0),
                (latch_edge_x(y1) + out, y1), (latch_edge_x(y1) - 0.0004, y1)], z0, z1

    bm = bmesh.new()
    for poly, z0, z1 in (edge_plate(-0.0905, -0.0645, 1.03, 1.37, 0.0008),
                         edge_plate(-0.0830, -0.0720, LEVER_Z - 0.015, LEVER_Z + 0.015, 0.0012),
                         edge_plate(-0.0860, -0.0690, BOLT_Z - 0.012, BOLT_Z + 0.012, 0.0012)):
        bm_prism(bm, poly, z0, z1, axis="Z")
    piece("Faceplate", bm, "leaf_steel", 0.0003, 1)

    # Leaf halves of the hinges (upper knuckle with finial + wing on the leaf face)
    bm = bmesh.new()
    wings = bmesh.new()
    for zc in HINGE_ZS:
        b, t = zc + 0.001, zc + 0.001 + KNUCKLE
        prof = [(0.0, b), (BARREL_R - 0.0007, b), (BARREL_R, b + 0.0008), (BARREL_R, t), (0.0090, t + 0.003),
                (0.0075, t + 0.006), (0.0045, t + 0.009), (0.0, t + 0.010)]
        lathe_along(bm, prof, (HINGE.x, HINGE.y, 0.0), (0, 0, 1), segments=20)
        bm_box(wings, (HINGE.x + 0.002, -0.117, b + 0.005), (HINGE.x + 0.042, LEAF_Y0 + 0.0004, t - 0.005))
    piece("HingeLeafKnuckles", bm, "hinge_leaf", sharp=40.0)
    piece("HingeLeafWings", wings, "hinge_leaf", 0.0012, 1)

    leaf = join(parts, "Leaf")
    reorigin(leaf, HINGE)
    tag(leaf, "door")

    # Smart-lock status LED ring: own unbaked material, Godot switches its color
    bm = bmesh.new()
    lathe_along(bm, [(LED_R0, -0.0002), (LED_R1, -0.0002), (LED_R1, 0.0006), (LED_R0, 0.0006)],
                (LX, LOCK_FRONT_Y, BOLT_Z), (0, -1, 0), segments=40, closed=True)
    led = new_object("LockLED", bm, coll, material=mats["led"])
    shade(led, 60.0)
    led.data.transform(_translation(-HINGE))
    led.parent = leaf
    tag(led, "door")

    tag(new_empty("HandleGripApartment", coll, GRIP_APT - HINGE, parent=leaf), "door")
    tag(new_empty("HandleGripCorridor", coll, GRIP_COR - HINGE, parent=leaf), "door")
    return leaf


def _translation(v):
    from mathutils import Matrix
    return Matrix.Translation(v)


# ---------------------------------------------------------------------------
# Levers and thumb-turn (separate glbs, origin on their axis)
# ---------------------------------------------------------------------------
def build_lever(name, part, face_y, s, coll, mats):
    """Lever on the face at y = face_y, protruding toward s * Y (s = -1 apartment, +1
    corridor), arm pointing to the hinge (-X). Origin: spindle axis on the leaf face."""
    o = Vector((LX, face_y, LEVER_Z))
    bm = bmesh.new()
    lathe_along(bm, [(0.0, 0.0), (0.0105, 0.0), (0.0105, 0.0065), (0.0095, 0.0085), (0.0, 0.0085)],
                o + Vector((0, s * (ROSE_PROUD - 0.0005), 0)), (0, s, 0), segments=24)
    pts = [(0.0, s * (ROSE_PROUD + 0.004), 0.0), (0.0, s * (LEVER_REACH - 0.002), 0.0),
           (-0.030, s * LEVER_REACH, 0.0), (-(LEVER_LEN - 0.012), s * (LEVER_REACH - 0.002), 0.0),
           (-LEVER_LEN, s * (LEVER_REACH - 0.009), 0.0)]
    path = round_polyline(pts, 0.016, steps=5, min_turn=8.0)
    scales = [(1.0, 0.90 + 0.22 * max(0.0, -p.x / LEVER_LEN)) for p in path]
    sweep(bm, [o + p for p in path], rounded_rect_profile(0.0165, 0.019, 0.0065, 3), up=(0, 0, 1), scales=scales)
    ob = new_object(name, bm, coll, material=mats["hw"])
    finish(ob, 0.0018, 2, angle=40.0, sharp_angle=40.0)
    reorigin(ob, o)
    tag(ob, part)
    return ob


def build_thumbturn(coll, mats):
    """Deadbolt thumb-turn on the smart-lock housing, fin vertical (built in the unlocked
    position). Origin: deadbolt axis on the housing front."""
    o = Vector((LX, LOCK_FRONT_Y, BOLT_Z))
    bm = bmesh.new()
    lathe_along(bm, [(0.0, -0.0003), (0.016, -0.0003), (0.016, 0.0022), (0.015, 0.0032), (0.0, 0.0032)],
                o, (0, -1, 0), segments=32)
    disc = new_object("ThumbTurnDisc", bm, coll, material=mats["hw"])
    shade(disc, 40.0)
    bm = bmesh.new()
    bm_box(bm, o + Vector((-0.0055, -0.0215, -0.021)), o + Vector((0.0055, -0.0028, 0.021)))
    fin = new_object("ThumbTurnFin", bm, coll, material=mats["hw"])
    finish(fin, 0.0034, 3, sharp_angle=40.0)
    ob = join([fin, disc], "ThumbTurn")
    reorigin(ob, o)
    tag(ob, "thumbturn")
    return ob


def main():
    clear_scene()
    mats = build_materials()
    build_frame(get_collection("Frame"), get_collection("FrameCollision"), mats)
    build_leaf(get_collection("Leaf"), mats)
    hw = get_collection("Hardware")
    build_lever("LeverApartment", "lever_apartment", LEAF_Y0, -1, hw, mats)
    build_lever("LeverCorridor", "lever_corridor", LEAF_Y1, 1, hw, mats)
    build_thumbturn(hw, mats)
    t = {p: part_tris(p) for p in ("body", "body_col", "door", "lever_apartment", "lever_corridor", "thumbturn")}
    print("TRIS " + " ".join(f"{k}={v}" for k, v in t.items()) + f" total={sum(t.values()) - t['body_col']}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
