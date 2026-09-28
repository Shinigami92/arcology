"""Stage 1: build the sofa, the throw pillow and the procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/sofa/build.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix  # noqa: E402

from sofa_common import (  # noqa: E402
    ARM_TOP, ARM_X_IN, ARM_X_OUT, BACK_H, BACK_PIVOT_Y, BACK_PIVOT_Z, BACK_T, BACK_TILT, BACK_W, BACK_Y,
    BACK_LEAN, BACK_YAW, BASE_Y0, BASE_Y1, BLEND, COLLISION, DECK_Z, FRAME_Y0, FRAME_Y1, FRAME_Z0, FRAME_Z1, FRONT_Y, LEG_COLOR,
    LEG_H, LEG_R_BOTTOM, LEG_R_TOP, LEGS, PILLOW_COLOR, PILLOW_SIZE, PILLOW_T, SEAT_CROWN, SEAT_SAG,
    SEAT_SAG_Y, SEAT_W, SEAT_YAW, SEAT_X, SEAT_Y0, SEAT_Y1, SEAT_Z0, SEAT_Z1, SOFA_COLOR,
)
from arcology_blender import fabric, geo, materials, soft, wear  # noqa: E402
from arcology_blender.geo import collision_box, finish, new_object, shade  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

SEAT_USE = [1.0, 0.45, 0.65]  # how much each seat is used (left is the favorite)
SOFT = 80.0                   # shade angle for upholstery: smooth everywhere


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_sofa_fabric():
    """Petrol woven upholstery with welts, sitting creases, worn seat fronts
    and arm tops, a head mark on the favorite back cushion, dust on the back
    frame, a faint coffee stain on the middle seat and one on the right arm."""
    g = Graph(new_mat("src_sofa_fabric"))
    base, rough, h = fabric.fabric_base(g, SOFA_COLOR, rough=0.92, mottle=0.045)
    base, rough, h = fabric.welt(g, base, rough, h)

    breakup = g.maprange(g.noise(5.0, 2.0), 0.30, 0.70)
    absx = g.math("ABSOLUTE", g.x)

    # Seat fronts: creases from sitting, abrasion shine and pilling on the front roll
    crease_m, rub_seat = 0.0, 0.0
    for cx, use in zip(SEAT_X, SEAT_USE):
        bx = g.band(g.x, cx - 0.20, cx + 0.20, 0.08)
        zone = g.mul(g.mul(bx, g.maprange(g.y, -0.18, -0.40)), g.maprange(g.z, 0.33, 0.42))
        crease_m = g.add(crease_m, g.mul(zone, use))
        roll = g.mul(g.mul(g.band(g.x, cx - 0.23, cx + 0.23, 0.06), g.maprange(g.y, -0.37, -0.445)),
                     g.maprange(g.z, 0.35, 0.425))
        rub_seat = g.add(rub_seat, g.mul(roll, use))
    base, h = fabric.creases(g, base, h, crease_m, stretch=(24.0, 6.0, 11.0), depth=0.0016)
    # Slack fabric wrinkling softly inside each seat's sag (top only, irregular, broad)
    top = g.mul(g.maprange(g.nz, 0.5, 0.85), g.maprange(g.z, 0.40, 0.43))
    sag_m = 0.0
    for cx, use in zip(SEAT_X, SEAT_USE):
        dent = g.mul(g.band(g.x, cx - 0.17, cx + 0.17, 0.08), g.band(g.y, SEAT_SAG_Y - 0.13, SEAT_SAG_Y + 0.10, 0.08))
        sag_m = g.add(sag_m, g.mul(dent, use))
    sag_m = g.mul(g.mul(sag_m, top), g.maprange(g.noise(2.5, 1.0), 0.30, 0.60))
    base, h = fabric.creases(g, base, h, sag_m, stretch=(9.0, 6.0, 9.0), depth=0.0014, sharp=0.62, darker=0.06)
    # Back cushions: horizontal creases at the lumbar zone where people lean
    front = g.maprange(g.ny, -0.3, -0.7)
    lumbar = g.mul(g.mul(g.band(g.z, 0.47, 0.62, 0.07), front), g.maprange(g.y, 0.26, 0.18))
    lumbar = g.mul(lumbar, g.maprange(g.noise(3.0, 1.0), 0.35, 0.65))
    base, h = fabric.creases(g, base, h, g.mul(lumbar, 0.6), stretch=(4.0, 10.0, 16.0), depth=0.0008,
                         sharp=0.80)

    rub_seat = g.mul(rub_seat, breakup)
    base, rough = fabric.rub(g, base, rough, rub_seat, shinier=0.14, tint=0.05)
    # Arm tops: forearms rest on the inner half, the left arm most; oils darken them
    arm = g.mul(g.mul(g.band(absx, 0.885, 1.00, 0.035), g.maprange(g.z, 0.56, 0.615)),
                g.maprange(g.y, 0.30, -0.12))
    arm = g.mul(g.mul(arm, g.mixf(g.maprange(g.x, -0.1, 0.1), 1.0, 0.55)), breakup)
    base, rough = fabric.rub(g, base, rough, arm, shinier=0.22, tint=-0.07)
    base, h = fabric.pilling(g, base, h, g.add(rub_seat, g.mul(arm, 0.5)))
    # Head mark near the top of the favorite back cushion
    head = g.mul(g.mul(g.band(g.x, -0.80, -0.40, 0.08), g.band(g.z, 0.70, 0.82, 0.04)),
                 g.maprange(g.ny, -0.2, -0.6))
    base, rough = fabric.rub(g, base, rough, g.mul(g.mul(head, breakup), 0.8), shinier=0.10, tint=-0.06)

    # Dust on the back frame's top (behind the cushions), grime and scuffs low down
    dust = g.mul(g.mul(g.maprange(g.nz, 0.80, 0.95), g.band(g.z, 0.70, 0.74, 0.01)),
                 g.maprange(g.noise(12.0, 2.0), 0.2, 0.8))
    base = g.mixc(g.mul(dust, 0.035), base, (0.40, 0.39, 0.37))
    rough = g.add(rough, g.mul(dust, 0.04))
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.27, z_full=0.14, rougher=0.08, darker=0.10)
    base = wear.floor_grime(g, base, z0=0.13, z1=0.24, darkest=0.86)

    # A faint coffee spill on the middle seat and a smaller one on the right arm
    base, rough = fabric.stain(g, base, rough, (0.07, -0.26, 0.445), 0.038)
    base, rough = fabric.stain(g, base, rough, (0.975, -0.12, 0.625), 0.026, strength=0.08, ring=0.12)
    return fabric.fabric_finish(g, base, rough, h)


def mat_pillow_fabric():
    """Terracotta slub linen with a self welt; fine creases toward the corners."""
    g = Graph(new_mat("src_pillow_fabric"))
    base, rough, h = fabric.fabric_base(g, PILLOW_COLOR, rough=0.93, heather=0.06, slub=0.08, mottle=0.05,
                                    weave=0.00026, slub_height=0.0002)
    base, rough, h = fabric.welt(g, base, rough, h, cord=0.0063, groove=0.0035, bead=0.0006, darker=0.22)
    hx, hy = PILLOW_SIZE[0] / 2, PILLOW_SIZE[1] / 2
    dx = g.sub(hx, g.math("ABSOLUTE", g.x))
    dy = g.sub(hy, g.math("ABSOLUTE", g.y))
    dc = g.math("SQRT", g.add(g.mul(dx, dx), g.mul(dy, dy)))
    corner = g.maprange(dc, 0.16, 0.03)
    base, h = fabric.creases(g, base, h, corner, stretch=(16.0, 16.0, 16.0), depth=0.0010, darker=0.08)
    base, h = fabric.pilling(g, base, h, 0.35, lighter=0.05)
    return fabric.fabric_finish(g, base, rough, h)


def build_materials():
    return {
        "fabric": mat_sofa_fabric(),
        "pillow": mat_pillow_fabric(),
        "legs": materials.dark_plastic("legs", base=LEG_COLOR, rough=0.42),
    }


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def soft_object(name, bm, coll, mat):
    ob = new_object(name, bm, coll, material=mat)
    shade(ob, SOFT)
    return ob


def build_frame(coll, mats):
    fabric = mats["fabric"]
    parts = []
    # Track arms (welt around the outer and inner side panels)
    arm_w = ARM_X_OUT - ARM_X_IN
    for side, sx in (("L", -1.0), ("R", 1.0)):
        cx = sx * (ARM_X_IN + ARM_X_OUT) / 2
        outer = "+x" if sx > 0 else "-x"
        bm = soft.soft_box((cx, 0.0, (LEG_H + ARM_TOP) / 2), (arm_w, BACK_Y - FRONT_Y, ARM_TOP - LEG_H),
                         0.035, step=0.04, band_segments=3, panel_axis=0,
                         crown={outer: 0.008, "-y": 0.007, "+y": 0.004, "+z": 0.004}, open_faces=("-z",))
        # where the elbow rests (the left arm more)
        soft.press(bm, (cx - sx * 0.02, -0.08, ARM_TOP), (0.07, 0.17, 0.0), 0.007 if sx < 0 else 0.004,
                 thickness=0.12)
        soft.jitter(bm, 0.0015, 6.0, seed=3.0 + sx)
        parts.append(soft_object(f"Arm{side}", bm, coll, fabric))

    # Base (seat deck) between the arms; hidden top and bottom are single n-gons
    bm = soft.soft_box((0.0, (BASE_Y0 + BASE_Y1) / 2, (LEG_H + DECK_Z) / 2),
                     (2 * ARM_X_IN + 0.01, BASE_Y1 - BASE_Y0, DECK_Z - LEG_H),
                     0.015, step=(0.06, 0.06, 0.04), band_segments=2, panel_axis=2,
                     crown={"-y": 0.004}, open_faces=("-z", "+z"))
    parts.append(soft_object("Base", bm, coll, fabric))

    # Outside back (welt around the front and back panels)
    bm = soft.soft_box((0.0, (FRAME_Y0 + FRAME_Y1) / 2, (FRAME_Z0 + FRAME_Z1) / 2),
                     (2 * ARM_X_IN + 0.01, FRAME_Y1 - FRAME_Y0, FRAME_Z1 - FRAME_Z0),
                     0.03, step=(0.06, 0.04, 0.05), band_segments=2, panel_axis=1,
                     crown={"+y": 0.006, "+z": 0.005}, open_faces=("-z",))
    soft.jitter(bm, 0.0015, 4.0, seed=7.0)
    parts.append(soft_object("BackFrame", bm, coll, fabric))

    # Slim tapered steel legs (1 cm tucked into the base)
    bm = bmesh.new()
    depth = LEG_H + 0.01
    for x, y in LEGS:
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=LEG_R_BOTTOM,
                              radius2=LEG_R_TOP, depth=depth, matrix=Matrix.Translation((x, y, depth / 2)))
    legs = new_object("Legs", bm, coll, material=mats["legs"])
    finish(legs, 0.0015, 1)
    parts.append(legs)

    frame = geo.join(parts, "SofaFrame")
    tag(frame, "frame")
    return frame


def build_cushions(coll, mats):
    fabric = mats["fabric"]
    parts = []
    names = ("L", "M", "R")
    for i, cx in enumerate(SEAT_X):
        # Seat cushion: welted top and bottom panels, crowned, sagging where people sit
        bm = soft.soft_box((cx, (SEAT_Y0 + SEAT_Y1) / 2, (SEAT_Z0 + SEAT_Z1) / 2),
                         (SEAT_W, SEAT_Y1 - SEAT_Y0, SEAT_Z1 - SEAT_Z0),
                         0.03, step=0.035, band_segments=3, panel_axis=2,
                         crown={"+z": SEAT_CROWN, "-y": 0.012, "+y": 0.006, "-x": 0.005, "+x": 0.005},
                         open_faces=("-z",))
        soft.press(bm, (cx, SEAT_SAG_Y, SEAT_Z1 + SEAT_CROWN), (0.19, 0.16, 0.0), SEAT_SAG[i],
                 thickness=SEAT_Z1 + SEAT_CROWN - SEAT_Z0)
        # the front roll flattens a little under the thighs
        soft.press(bm, (cx, SEAT_Y0 + 0.03, SEAT_Z1), (0.18, 0.06, 0.0), SEAT_SAG[i] * 0.35,
                 thickness=SEAT_Z1 - SEAT_Z0)
        soft.jitter(bm, 0.002, 7.0, seed=float(i))
        soft.rotate_verts(bm, (cx, (SEAT_Y0 + SEAT_Y1) / 2, SEAT_Z0), SEAT_YAW[i], "Z")
        parts.append(soft_object(f"Seat{names[i]}", bm, coll, fabric))

        # Back cushion: built upright, pressed at the lumbar, leaned back onto the frame
        yc = BACK_PIVOT_Y - BACK_T / 2
        bm = soft.soft_box((cx, yc, BACK_PIVOT_Z + BACK_H / 2), (BACK_W, BACK_T, BACK_H),
                         0.035, step=0.038, band_segments=3, panel_axis=1,
                         crown={"-y": 0.024, "+y": 0.008, "+z": 0.008, "-x": 0.004, "+x": 0.004})
        soft.press(bm, (cx, BACK_PIVOT_Y - BACK_T - 0.024, BACK_PIVOT_Z + 0.20), (0.20, 0.0, 0.12),
                 [0.012, 0.006, 0.008][i], direction=(0.0, 1.0, 0.0), thickness=BACK_T + 0.03)
        soft.rotate_verts(bm, (0.0, BACK_PIVOT_Y, BACK_PIVOT_Z), -(BACK_TILT + BACK_LEAN[i]), "X")
        soft.rotate_verts(bm, (cx, BACK_PIVOT_Y, BACK_PIVOT_Z), BACK_YAW[i], "Z")
        soft.jitter(bm, 0.002, 6.0, seed=10.0 + i)
        parts.append(soft_object(f"Back{names[i]}", bm, coll, fabric))

    cushions = geo.join(parts, "SofaCushions")
    tag(cushions, "cushions")
    return cushions


def build_pillow(coll, mats):
    bm = soft.pillow(size=PILLOW_SIZE, thickness=PILLOW_T, res=30, folds=0.014, fold_count=5.0)
    soft.jitter(bm, 0.004, 3.5, seed=21.0)   # uneven fill
    soft.jitter(bm, 0.0012, 12.0, seed=5.0)  # small lumps
    ob = soft_object("SofaPillow", bm, coll, mats["pillow"])
    tag(ob, "pillow")
    return ob


def build_collision(coll):
    for name, (lo, hi) in COLLISION.items():
        tag(collision_box(name, lo, hi, coll), "sofa_col")


def main():
    clear_scene()
    mats = build_materials()
    build_frame(get_collection("Sofa"), mats)
    build_cushions(get_collection("Sofa"), mats)
    build_collision(get_collection("SofaCollision"))
    build_pillow(get_collection("SofaPillow"), mats)
    f, c, col, p = part_tris("frame"), part_tris("cushions"), part_tris("sofa_col"), part_tris("pillow")
    print(f"TRIS frame={f} cushions={c} sofa={f + c} collision={col} pillow={p}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
