"""Stage 1: build the sofa and pillow geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/sofa__fable-high/build.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402

from sofa_common import (  # noqa: E402
    ARM_TOP, ARM_W, ARM_X0, BACK_CUSHION_R, BACK_CUSHION_Y0, BACK_CUSHION_Y1, BACK_CUSHION_Z0,
    BACK_CUSHION_Z1, BACK_R, BACK_TAPER, BACK_TOP, BACK_Y0, BLEND, CUSHION_W, CUSHION_XS, DECK_TOP,
    HX, HY, LEG_H, LEG_R, PILLOW_R, PILLOW_T, PILLOW_W, SEAT_R, SEAT_SAG, SEAT_TOP, SEAT_Y0, SEAT_Y1,
    SEAT_Z0, SEAT_Z1,
)
import lib_candidates as soft  # noqa: E402
from arcology_blender import wear  # noqa: E402
from arcology_blender.geo import bm_cyl, collision_box, cyl_z, finish, new_object  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_fabric():
    """Slate blue-grey boucle upholstery with lived-in wear: flattened, pilled
    fabric on the arm tops, seat fronts and the two most-used seats, a lumbar
    sheen on the back cushions, a faint dried spill on the left seat, grime
    along the bottom rail and a little dust on the back rail."""
    g, base, rough, height = soft.fabric("fabric", base=(0.095, 0.115, 0.145))
    ax = g.math("ABSOLUTE", g.x)
    arm_tops = g.mul(g.maprange(g.z, 0.55, 0.61), g.maprange(ax, 0.86, 0.90))
    seat_fronts = g.mul(g.band(g.y, -0.50, -0.41, 0.03), g.band(g.z, SEAT_Z0, SEAT_Z1 + 0.01, 0.02))
    seat_z = g.band(g.z, 0.40, 0.47, 0.02)
    seat_right = g.mul(g.mul(g.band(g.x, 0.40, 0.80, 0.12), g.band(g.y, -0.36, 0.02, 0.10)), seat_z)
    seat_mid = g.mul(g.mul(g.band(g.x, -0.18, 0.18, 0.12), g.band(g.y, -0.34, 0.0, 0.10)), seat_z)
    lumbar = g.mul(g.band(g.z, 0.46, 0.62, 0.06), g.band(g.y, 0.06, 0.20, 0.04))
    region = g.add(g.add(g.mul(arm_tops, 0.9), g.mul(seat_fronts, 0.7)),
                   g.add(g.add(seat_right, g.mul(seat_mid, 0.6)), g.mul(lumbar, 0.5)))
    base, rough = soft.sheen_wear(g, base, rough, g.math("MINIMUM", region, 1.0))
    base, rough = soft.stain(g, base, rough, (-0.56, -0.13), 0.07, color=(0.22, 0.17, 0.11), amount=0.22,
                             z_lo=0.40, z_hi=0.47)
    base = wear.floor_grime(g, base, LEG_H, LEG_H + 0.06, darkest=0.82)
    base, rough = wear.top_dust(g, base, rough, BACK_TOP - 0.03, BACK_TOP, amount=0.18, rougher=0.1)
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))


def build_materials():
    return {
        "fabric": mat_fabric(),
        "metal": soft.dark_metal("metal"),
        "velvet": soft.velvet("velvet"),
    }


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def build_sofa(coll, col_coll, mats):
    fabric, metal = mats["fabric"], mats["metal"]

    # Six black metal legs, 2 cm up into the frame
    bm = bmesh.new()
    for x in (-HX + 0.07, 0.0, HX - 0.07):
        for y in (-HY + 0.09, HY - 0.09):
            bm_cyl(bm, LEG_R, LEG_H + 0.02, cyl_z((x, y, (LEG_H + 0.02) / 2)), 16)
    legs = new_object("SofaLegs", bm, coll, material=metal)
    finish(legs, 0.002, 1)
    tag(legs, "sofa")

    # Upholstered base frame between the arms (reaches 2 cm into each arm)
    ob = soft.soft_object("SofaBase", coll, (2 * (ARM_X0 + 0.02), 2 * HY - 0.02, DECK_TOP - LEG_H), 0.02,
                          (18, 10, 4), (0.0, 0.0, (LEG_H + DECK_TOP) / 2), fabric,
                          puff_amount=0.004, wrinkle=(0.0012, 5.0), seed=11.0)
    tag(ob, "sofa")

    # Back frame
    ob = soft.soft_object("SofaBack", coll, (2 * (ARM_X0 + 0.02), HY - BACK_Y0, BACK_TOP - LEG_H), BACK_R,
                          (18, 3, 10), (0.0, (BACK_Y0 + HY) / 2, (LEG_H + BACK_TOP) / 2), fabric,
                          puff_amount=0.004, wrinkle=(0.0015, 4.0), seed=23.0)
    tag(ob, "sofa")

    # Arms: full-depth slabs
    for name, sx in (("SofaArmLeft", -1), ("SofaArmRight", 1)):
        ob = soft.soft_object(name, coll, (ARM_W, 2 * HY, ARM_TOP - LEG_H), 0.04, (4, 14, 8),
                              (sx * (ARM_X0 + ARM_W / 2), 0.0, (LEG_H + ARM_TOP) / 2), fabric,
                              puff_amount=0.004, wrinkle=(0.0015, 5.0), seed=31.0 + sx)
        tag(ob, "sofa")

    # Seat cushions: puffed, lumpy, with a sat-in sag (deepest on the right seat)
    sags = {-0.60: 0.7, 0.0: 0.8, 0.60: 1.0}
    for i, cx in enumerate(CUSHION_XS):
        ob = soft.soft_object(f"SofaSeatCushion{i + 1}", coll, (CUSHION_W, SEAT_Y1 - SEAT_Y0, SEAT_Z1 - SEAT_Z0),
                              SEAT_R, (16, 14, 5), (cx, (SEAT_Y0 + SEAT_Y1) / 2, (SEAT_Z0 + SEAT_Z1) / 2), fabric,
                              puff_amount=0.008, wrinkle=(0.0025, 6.0), seed=40.0 + i * 7)
        depth = SEAT_SAG * sags[cx]
        soft.edit(ob, lambda bm, vs, cx=cx, depth=depth: soft.dent(bm, vs, (cx, -0.16, SEAT_Z1), (0.20, 0.17), depth))
        tag(ob, "sofa")

    # Back cushions: thick at the seat, thinner at the top, lumbar hollow
    for i, cx in enumerate(CUSHION_XS):
        ob = soft.soft_object(f"SofaBackCushion{i + 1}", coll,
                              (CUSHION_W, BACK_CUSHION_Y1 - BACK_CUSHION_Y0, BACK_CUSHION_Z1 - BACK_CUSHION_Z0),
                              BACK_CUSHION_R, (16, 4, 12),
                              (cx, (BACK_CUSHION_Y0 + BACK_CUSHION_Y1) / 2, (BACK_CUSHION_Z0 + BACK_CUSHION_Z1) / 2),
                              fabric, puff_amount=0.010, wrinkle=(0.003, 5.0), seed=60.0 + i * 5)

        def shape(bm, vs, cx=cx, i=i):
            soft.taper(bm, vs, BACK_CUSHION_Z0, BACK_CUSHION_Z1, BACK_TAPER, BACK_CUSHION_Y1)
            soft.dent(bm, vs, (cx, BACK_CUSHION_Y0, 0.56), (0.16, 0.10), 0.010 + 0.004 * i, (0.0, -1.0, 0.0))
        soft.edit(ob, shape)
        tag(ob, "sofa")

    # Collision boxes for Godot: solid seat block, back (two boxes follow the
    # cushion taper), both arms.
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "sofa_col")

    col("ColSeat", (-ARM_X0, -HY, 0.0), (ARM_X0, HY, SEAT_TOP))
    col("ColBackLower", (-ARM_X0, BACK_CUSHION_Y0, SEAT_TOP), (ARM_X0, HY, 0.62))
    col("ColBackUpper", (-ARM_X0, 0.17, 0.62), (ARM_X0, HY, BACK_TOP))
    col("ColArmLeft", (-HX, -HY, 0.0), (-ARM_X0, HY, ARM_TOP))
    col("ColArmRight", (ARM_X0, -HY, 0.0), (HX, HY, ARM_TOP))


def build_pillow(coll, mats):
    """Square throw pillow centered on the origin: thin welted edge, fat middle."""
    ob = soft.soft_object("SofaPillow", coll, (PILLOW_W, PILLOW_W, PILLOW_T), PILLOW_R, (16, 16, 4),
                          (0.0, 0.0, 0.0), mats["velvet"], puff_amount=(0.006, 0.006, 0.045),
                          wrinkle=(0.004, 6.0), seed=77.0)
    tag(ob, "pillow")
    return ob


def main():
    clear_scene()
    mats = build_materials()
    build_sofa(get_collection("Sofa"), get_collection("SofaCollision"), mats)
    pillow = build_pillow(get_collection("SofaPillow"), mats)
    sofa, col, pil = part_tris("sofa"), part_tris("sofa_col"), part_tris("pillow")
    print(f"TRIS sofa={sofa} collision={col} pillow={pil} total={sofa + col + pil}")
    print("PILLOW dims", tuple(round(v, 3) for v in pillow.dimensions))
    save_blend(BLEND)


if __name__ == "__main__":
    main()
