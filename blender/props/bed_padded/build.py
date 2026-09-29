"""Stage 1: build the bed (frame, bedding, collision) and its procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/bed_padded/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Vector, noise  # noqa: E402

from bed_common import (  # noqa: E402
    BLEND, CAP_LIP, CAP_T, COLLISION, DUVET_FOLD_Y, DUVET_HEM_Y, DUVET_LAYER2, DUVET_OVERHANG, DUVET_RADIUS,
    DUVET_T, FRAME_X, FRAME_Y0, FRAME_Y1, FRAME_Z0, FRAME_Z1, GUNMETAL, HEAD_Y0, HEAD_Y1, HEAD_Z0, HEAD_Z1,
    LEG_H, LEG_SIZE, LEGS, LINEN, MAT_CROWN, MAT_R, MAT_X, MAT_Y0, MAT_Y1, MAT_Z0, MAT_Z1, PAD, PAD_X, PAD_Y0,
    PAD_Y1, PAD_Z0, PAD_Z1, PILLOW_SIZE, PILLOW_T, PILLOW_TILT, PILLOW_X, PILLOW_Y, PILLOW_YAW, RECESS_X,
    RECESS_Y0, RECESS_Y1, RECESS_Z, SHEET, SIT_DENT, THROW, THROW_OVERHANG, THROW_RECT, THROW_T, WALNUT,
)
from lib_candidates import brushed_metal, wood_veneer  # noqa: E402
from arcology_blender import fabric, geo, soft, wear  # noqa: E402
from arcology_blender.cloth import drape, lumps, ridge, smoothstep  # noqa: E402
from arcology_blender.fabric import quilting, wool_knit  # noqa: E402
from arcology_blender.geo import assign_by_region, bm_box, collision_box, cut, finish, new_object, shade  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

SOFT = 80.0  # shade angle for soft goods: smooth everywhere


# ---------------------------------------------------------------------------
# Surfaces (analytic, so the duvet knows the mattress and the throw knows the duvet)
# ---------------------------------------------------------------------------
def mattress_top(x, y):
    """Top of the mattress (crowned, rounded edges) at world x, y."""
    hx, hy = MAT_X, (MAT_Y1 - MAT_Y0) / 2
    px, py = x, y - (MAT_Y0 + MAT_Y1) / 2
    f = max(0.0, 1.0 - (abs(px) / hx) ** 3) * max(0.0, 1.0 - (abs(py) / hy) ** 3)

    def edge_drop(p, h):
        e = abs(p) - (h - MAT_R)
        if e <= 0.0:
            return 0.0
        e = min(e, MAT_R)
        return MAT_R - math.sqrt(max(0.0, MAT_R * MAT_R - e * e))

    return MAT_Z1 + MAT_CROWN * f - max(edge_drop(px, hx), edge_drop(py, hy))


def duvet_top(x, y):
    """Top of the duvet over the mattress: filled thickness, the turned-down
    layer from its hem to the fold line, lumps, three fold ridges and the
    dent where someone sat on the edge."""
    z = mattress_top(x, y) + DUVET_T
    hem = DUVET_HEM_Y + 0.03 * noise.noise(Vector((x * 1.4, 2.0, 0.0)))  # the hem lies in a lazy wave
    z += DUVET_LAYER2 * smoothstep(y, hem - 0.025, hem + 0.015)
    z += lumps(x, y, 0.010, 2.2, seed=4.0) + lumps(x, y, 0.0035, 6.0, seed=9.0)
    z += ridge(x, y, (0.05, -0.80), (0.55, -0.22), 0.018, 0.045)
    z += ridge(x, y, (-0.32, -0.55), (0.30, -0.42), 0.011, 0.05)
    z += ridge(x, y, (0.18, 0.16), (0.60, 0.30), 0.008, 0.04)
    z += ridge(x, y, (-0.70, -0.95), (-0.35, -0.62), -0.008, 0.06)
    (cx, cy), (rx, ry), depth = SIT_DENT
    z -= depth * math.exp(-((x - cx) / rx) ** 2 - ((y - cy) / ry) ** 2)
    return z


def throw_top(x, y):
    """Top of the folded throw lying on the duvet (a fold ridge along its length)."""
    z = duvet_top(min(x, MAT_X - 0.01), y) + THROW_T
    z += lumps(x, y, 0.006, 5.0, seed=21.0)
    z += ridge(x, y, (THROW_RECT[0] + 0.05, -0.70), (THROW_RECT[2], -0.73), 0.010, 0.07, taper=0.25)
    return z


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_walnut(name, grain, axis_offset):
    """Walnut veneer with dust on the platform lip, kick scuffs and grime low down."""
    g, base, rough, h = wood_veneer(name, WALNUT, grain=grain, axis_offset=axis_offset)
    base, rough = wear.top_dust(g, base, rough, FRAME_Z1 - 0.02, FRAME_Z1 - 0.004, amount=0.10, rougher=0.12)
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.22, z_full=0.13, rougher=0.12, darker=0.10)
    base = wear.floor_grime(g, base, z0=FRAME_Z0, z1=0.21, darkest=0.90)
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_sheet():
    """Stone-grey fitted sheet: taut, pulled toward the mattress corners,
    slack creases and a soft shine where someone sat."""
    g = Graph(new_mat("src_sheet"))
    base, rough, h = fabric.fabric_base(g, SHEET, rough=0.88, heather=0.03, slub=0.05, mottle=0.03,
                                        weave=0.00010, slub_height=0.00008)
    top = g.maprange(g.nz, 0.5, 0.85)
    corner = 0.0
    for sx in (-1.0, 1.0):
        for cy in (MAT_Y0, MAT_Y1):
            corner = g.add(corner, g.maprange(g.dist_xy(sx * MAT_X, cy), 0.40, 0.08))
    base, h = fabric.creases(g, base, h, g.mul(corner, top), stretch=(9.0, 9.0, 9.0), depth=0.0007, sharp=0.78)
    (cx, cy), (rx, ry), _ = SIT_DENT
    sat = g.mul(g.maprange(g.dist_xy(cx, cy), rx + 0.05, rx * 0.4), top)
    base, h = fabric.creases(g, base, h, sat, stretch=(8.0, 6.0, 8.0), depth=0.0010, sharp=0.66)
    base, rough = fabric.rub(g, base, rough, g.mul(sat, 0.6), shinier=0.06, tint=-0.03)
    return fabric.fabric_finish(g, base, rough, h)


def mat_duvet():
    """Off-white linen duvet cover: baffle-box quilting on the top, broad
    slept-in creases, vertical creases down the hanging sides, light pilling
    and a rubbed patch where someone sat."""
    g = Graph(new_mat("src_duvet"))
    base, rough, h = fabric.fabric_base(g, LINEN, rough=0.86, heather=0.035, slub=0.06, mottle=0.035,
                                        weave=0.00012, slub_height=0.00009)
    top = g.maprange(g.nz, 0.45, 0.85)
    side = g.maprange(g.nz, 0.55, 0.20)
    base, h = quilting(g, base, h, 0.31, top, width=0.016, depth=0.0008, darker=0.025, puff=0.003)
    slept = g.mul(top, g.maprange(g.noise(1.8, 1.0), 0.32, 0.68))
    base, h = fabric.creases(g, base, h, slept, stretch=(6.0, 8.0, 6.0), depth=0.0013, sharp=0.70, darker=0.07)
    base, h = fabric.creases(g, base, h, g.mul(side, 0.8), stretch=(12.0, 12.0, 2.5), depth=0.0010, sharp=0.74,
                             darker=0.06)
    (cx, cy), (rx, ry), _ = SIT_DENT
    sat = g.mul(g.maprange(g.dist_xy(cx, cy), rx + 0.08, rx * 0.5), top)
    base, h = fabric.creases(g, base, h, sat, stretch=(9.0, 5.0, 9.0), depth=0.0012, sharp=0.64, darker=0.06)
    base, rough = fabric.rub(g, base, rough, g.mul(sat, 0.5), shinier=0.05, tint=-0.03)
    base, h = fabric.pilling(g, base, h, 0.25, scale=120.0, amount=0.0004, lighter=0.04)
    return fabric.fabric_finish(g, base, rough, h)


def mat_pillow():
    """Linen pillowcases: creases radiating from the corners, a rubbed, slightly
    darker patch where the head lies, fine pilling."""
    g = Graph(new_mat("src_pillow"))
    base, rough, h = fabric.fabric_base(g, LINEN, rough=0.86, heather=0.04, slub=0.06, mottle=0.04,
                                        weave=0.00012, slub_height=0.00009)
    corner = 0.0
    for px in PILLOW_X:
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                corner = g.add(corner, g.maprange(g.dist_xy(px + sx * PILLOW_SIZE[0] / 2, PILLOW_Y + sy * 0.23),
                                                  0.22, 0.04))
    base, h = fabric.creases(g, base, h, g.maprange(corner, 0.0, 1.0), stretch=(14.0, 14.0, 14.0), depth=0.0009,
                             sharp=0.74, darker=0.08)
    head = 0.0
    for px in PILLOW_X:
        head = g.add(head, g.maprange(g.dist_xy(px, PILLOW_Y + 0.02), 0.20, 0.06))
    head = g.mul(head, g.maprange(g.noise(4.0, 2.0), 0.35, 0.65))
    base, h = fabric.creases(g, base, h, head, stretch=(10.0, 10.0, 10.0), depth=0.0008, sharp=0.70)
    base, rough = fabric.rub(g, base, rough, g.mul(head, 0.6), shinier=0.05, tint=-0.04)
    base, h = fabric.pilling(g, base, h, 0.2, scale=120.0, amount=0.0004, lighter=0.04)
    return fabric.fabric_finish(g, base, rough, h)


def mat_throw():
    """Muted clay wool throw: chunky knit, heathered, fuzzy."""
    g, base, rough, h = wool_knit("throw", THROW, rib_period=0.014, rib_height=0.0005, rib_direction="Y")
    return fabric.fabric_finish(g, base, rough, h)


def mat_pad():
    """Padded linen headboard panel with a welt, rubbed where heads lean."""
    g = Graph(new_mat("src_pad"))
    base, rough, h = fabric.fabric_base(g, PAD, rough=0.90, heather=0.04, slub=0.05, mottle=0.04, weave=0.00012)
    base, rough, h = fabric.welt(g, base, rough, h, cord=0.005, groove=0.003, bead=0.0018, darker=0.22)
    lean = 0.0
    for px in PILLOW_X:
        lean = g.add(lean, g.mul(g.band(g.x, px - 0.18, px + 0.18, 0.10), g.band(g.z, 0.62, 0.84, 0.06)))
    lean = g.mul(lean, g.maprange(g.noise(5.0, 2.0), 0.35, 0.65))
    base, rough = fabric.rub(g, base, rough, lean, shinier=0.10, tint=-0.05)
    base, rough = wear.top_dust(g, base, rough, PAD_Z1 - 0.03, PAD_Z1 - 0.005, amount=0.12, rougher=0.10)
    return fabric.fabric_finish(g, base, rough, h)


def build_materials():
    return {
        # Ring axes run along the grain, above the bed's center line, so the radius (and with it the
        # ring lines) changes with height on the rails' faces and the headboard, and with x/y on the lip.
        "walnut_x": mat_walnut("walnut_x", "X", (0.0, 0.0, -1.9)),   # head/foot rails, headboard: grain along X
        "walnut_y": mat_walnut("walnut_y", "Y", (0.0, 0.0, -1.07)),  # side rails: grain along Y
        "metal_z": brushed_metal("gunmetal_z", GUNMETAL, along="Z"),
        "metal_x": brushed_metal("gunmetal_x", GUNMETAL, along="X"),
        "sheet": mat_sheet(),
        "duvet": mat_duvet(),
        "pillow": mat_pillow(),
        "throw": mat_throw(),
        "pad": mat_pad(),
    }


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def soft_object(name, bm, coll, mat):
    ob = new_object(name, bm, coll, material=mat)
    shade(ob, SOFT)
    return ob


def build_frame(coll, mats):
    parts = []
    # Platform with the mattress recess; side rails get the lengthwise grain
    bm = bmesh.new()
    bm_box(bm, (-FRAME_X, FRAME_Y0, FRAME_Z0), (FRAME_X, FRAME_Y1, FRAME_Z1))
    platform = new_object("Platform", bm, coll, material=mats["walnut_x"])
    bm = bmesh.new()
    bm_box(bm, (-RECESS_X, RECESS_Y0, RECESS_Z), (RECESS_X, RECESS_Y1, FRAME_Z1 + 0.02))
    cut(platform, bm, coll)
    finish(platform, 0.004, 2)
    assign_by_region(platform, [
        (((-2.0, -2.0, -1.0), (-0.77, 2.0, 1.0)), mats["walnut_y"]),
        (((0.77, -2.0, -1.0), (2.0, 2.0, 1.0)), mats["walnut_y"]),
    ], mats["walnut_x"])
    parts.append(platform)

    # Headboard panel and its gunmetal cap
    bm = bmesh.new()
    bm_box(bm, (-FRAME_X, HEAD_Y0, HEAD_Z0), (FRAME_X, HEAD_Y1, HEAD_Z1))
    head = new_object("Headboard", bm, coll, material=mats["walnut_x"])
    finish(head, 0.004, 2)
    parts.append(head)
    bm = bmesh.new()
    bm_box(bm, (-FRAME_X - CAP_LIP, HEAD_Y0 - CAP_LIP, HEAD_Z1), (FRAME_X + CAP_LIP, HEAD_Y1 + CAP_LIP, HEAD_Z1 + CAP_T))
    cap = new_object("HeadboardCap", bm, coll, material=mats["metal_x"])
    finish(cap, 0.002, 2)
    parts.append(cap)

    # Legs: square gunmetal tubes, inset (the platform floats)
    bm = bmesh.new()
    s = LEG_SIZE / 2
    for x, y in LEGS:
        bm_box(bm, (x - s, y - s, 0.0), (x + s, y + s, LEG_H + 0.01))
    legs = new_object("Legs", bm, coll, material=mats["metal_z"])
    finish(legs, 0.002, 2)
    parts.append(legs)

    frame = geo.join(parts, "BedFrame")
    tag(frame, "frame")

    # Padded headboard panel (welted, crowned, pressed where heads lean)
    bm = soft.soft_box((0.0, (PAD_Y0 + PAD_Y1) / 2, (PAD_Z0 + PAD_Z1) / 2),
                       (2 * PAD_X, PAD_Y1 - PAD_Y0, PAD_Z1 - PAD_Z0), 0.015, step=0.05, band_segments=2,
                       panel_axis=1, crown={"-y": 0.008}, open_faces=("+y",))
    for px in PILLOW_X:
        soft.press(bm, (px, PAD_Y0 - 0.008, 0.74), (0.16, 0.0, 0.10), 0.004, direction=(0.0, 1.0, 0.0),
                   thickness=PAD_Y1 - PAD_Y0 + 0.01)
    soft.jitter(bm, 0.0008, 5.0, seed=31.0)
    pad = soft_object("HeadPad", bm, coll, mats["pad"])
    tag(pad, "frame")
    return frame, pad


def build_bedding(coll, mats):
    parts = []
    # Mattress in its fitted sheet; the top under the duvet and the bottom are removed (hidden)
    bm = soft.soft_box((0.0, (MAT_Y0 + MAT_Y1) / 2, (MAT_Z0 + MAT_Z1) / 2),
                       (2 * MAT_X, MAT_Y1 - MAT_Y0, MAT_Z1 - MAT_Z0), MAT_R, step=0.06, band_segments=2,
                       panel_axis=2, crown={"+z": MAT_CROWN}, open_faces=("-z",))
    (cx, cy), (rx, ry), depth = SIT_DENT
    soft.press(bm, (cx, cy, MAT_Z1 + MAT_CROWN), (rx, ry, 0.0), depth * 0.5, thickness=MAT_Z1 - MAT_Z0)
    soft.jitter(bm, 0.0012, 5.0, seed=12.0)
    hidden = [f for f in bm.faces
              if (f.calc_center_median().z > MAT_Z1 - 0.012 and f.calc_center_median().y < 0.20)
              or f.calc_center_median().z < MAT_Z0 + 0.002]
    bmesh.ops.delete(bm, geom=hidden, context="FACES")
    parts.append(soft_object("Mattress", bm, coll, mats["sheet"]))

    # Duvet: draped over the mattress, hanging over the sides and foot, turned down at the head
    bm = drape((-MAT_X, MAT_Y0, MAT_X, DUVET_FOLD_Y), duvet_top, DUVET_OVERHANG, 0.035, res=0.032,
               radius=DUVET_RADIUS, corner_radius=0.08, fold_amp=0.010, fold_period=0.17, hem_wave=0.008,
               flare=0.05, seed=3.0)
    parts.append(soft_object("Duvet", bm, coll, mats["duvet"]))

    # Pillows: built flat on the origin, pressed by a head, tilted against the headboard pad
    for i, (px, yaw) in enumerate(zip(PILLOW_X, PILLOW_YAW)):
        bm = soft.pillow(size=PILLOW_SIZE, thickness=PILLOW_T, res=20, cord=0.003, pinch=0.05, fullness=0.9,
                         folds=0.012, fold_count=5.0, edge_ripple=0.003, seed=1.0 + i)
        soft.press(bm, (0.0, 0.02, PILLOW_T / 2), (0.15, 0.12, 0.0), 0.030 if i == 0 else 0.018,
                   thickness=PILLOW_T)
        soft.jitter(bm, 0.003, 3.5, seed=41.0 + i)
        soft.jitter(bm, 0.0010, 12.0, seed=45.0 + i)
        soft.rotate_verts(bm, (0.0, 0.0, 0.0), PILLOW_TILT, "X")
        soft.rotate_verts(bm, (0.0, 0.0, 0.0), yaw, "Z")
        low = min(bm.verts, key=lambda v: v.co.z)
        rest = mattress_top(px + low.co.x, PILLOW_Y + low.co.y) + 0.002
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((px, PILLOW_Y, rest - low.co.z)))
        parts.append(soft_object(f"Pillow{'LR'[i]}", bm, coll, mats["pillow"]))

    # Throw: folded across the foot, tipped over the +x edge
    bm = drape(THROW_RECT, throw_top, THROW_OVERHANG, THROW_T, res=0.03, radius=0.045, corner_radius=0.03,
               fold_amp=0.006, fold_period=0.14, hem_wave=0.006, flare=0.02, seed=7.0)
    parts.append(soft_object("Throw", bm, coll, mats["throw"]))

    bedding = geo.join(parts, "BedBedding")
    tag(bedding, "bedding")
    return bedding


def build_collision(coll):
    for name, (lo, hi) in COLLISION.items():
        tag(collision_box(name, lo, hi, coll), "bed_col")


def main():
    clear_scene()
    mats = build_materials()
    build_frame(get_collection("Bed"), mats)
    build_bedding(get_collection("Bed"), mats)
    build_collision(get_collection("BedCollision"))
    f, b, c = part_tris("frame"), part_tris("bedding"), part_tris("bed_col")
    print(f"TRIS frame={f} bedding={b} bed={f + b} collision={c}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
