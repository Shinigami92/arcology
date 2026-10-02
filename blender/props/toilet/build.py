"""Stage 1: build the toilet geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/toilet/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import toilet_common as C  # noqa: E402
from lib_candidates import (  # noqa: E402
    blend_ring, loft_rings, prism_y, rounded_rect_xz, wave_profile,
)
from arcology_blender import materials, metal, wear  # noqa: E402
from arcology_blender.curves import circle_profile, lathe, round_polyline, sweep  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    bm_box, bm_cyl, collision_box, cut, cyl_x, cyl_y, cyl_z, finish, instance, new_empty, new_object, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat, solid_mat  # noqa: E402


# ---------------------------------------------------------------------------
# Materials (contract: marble, porcelain, fixture metal; hotel-clean wear)
# ---------------------------------------------------------------------------
def mat_marble():
    """Honed white marble: soft cloudy body, medium-scale grey veins (no fine
    veining: it shimmers in VR), 0.22 on tops, 0.30 on faces, 0.35 on the edges."""
    g = Graph(new_mat("src_marble"))
    cloud = g.noise(1.4, 3.0, 0.55)
    base = g.mixc(g.maprange(cloud, 0.35, 0.70, 0.0, 0.35), C.MARBLE, (0.72, 0.69, 0.635))
    warm = g.noise(0.7, 2.0, 0.5, vector=g.offset((5.0, 2.0, 7.0)))
    base = g.mixc(g.maprange(warm, 0.45, 0.65, 0.0, 0.25), base, (0.80, 0.755, 0.68))
    # Main veins: thresholded triangle wave, strongly distorted, fading in and out.
    w1 = wave_profile(g.wave(0.50, 8.0, 3.0, "DIAGONAL"))
    fade1 = g.maprange(g.noise(0.9, 2.0, 0.5, vector=g.offset((1.3, 4.1, 2.2))), 0.30, 0.60, 0.15, 1.0)
    vein1 = g.mul(g.maprange(w1, 0.958, 0.994), fade1)
    halo1 = g.mul(g.maprange(w1, 0.84, 0.985), g.mul(fade1, 0.30))
    # Secondary veins: thinner, fainter, a different flow.
    w2 = wave_profile(g.wave(0.95, 10.0, 3.0, "Z", vector=g.offset((3.1, 1.7, 0.9))))
    fade2 = g.maprange(g.noise(1.1, 2.0, 0.5, vector=g.offset((7.0, 0.3, 5.5))), 0.40, 0.62)
    vein2 = g.mul(g.maprange(w2, 0.975, 0.996), g.mul(fade2, 0.40))
    # Grey clouds following the veins.
    cloud2 = g.mul(g.maprange(g.noise(2.6, 4.0, 0.6, vector=g.offset((2.0, 9.0, 4.0))), 0.52, 0.75), 0.22)
    base = g.mixc(cloud2, base, (0.56, 0.55, 0.53))
    base = g.mixc(halo1, base, (0.55, 0.54, 0.52))
    base = g.mixc(g.mul(vein1, 0.75), base, C.MARBLE_VEIN)
    base = g.mixc(vein2, base, C.MARBLE_VEIN)
    rough = g.mixf(g.maprange(g.nz, 0.6, 0.9), 0.30, 0.22)
    rough = g.add(rough, g.mul(g.sub(g.noise(9.0, 2.0), 0.5), 0.04))
    rough = g.add(rough, g.mul(g.add(vein1, vein2), 0.04))
    rough = g.mixf(wear.bevel_edges(g, 0.003), rough, 0.35)
    base, rough = wear.top_dust(g, base, rough, C.SHELF_TOP - 0.004, C.SHELF_TOP - 0.001,
                                color=(0.70, 0.68, 0.64), amount=0.05, rougher=0.10)
    height = g.mul(g.add(vein1, vein2), -0.00002)
    return g.finish_height(base, rough, 0.0, height)


def mat_porcelain():
    """Glossy sanitary ceramic: a faint limescale line at the water, the dark
    flush-water inlet slot under the back of the rimless rim."""
    g = Graph(new_mat("src_porcelain"))
    base = C.PORCELAIN
    rough = g.add(0.08, g.mul(g.sub(g.noise(16.0, 2.0), 0.5), 0.02))
    inside = g.mul(g.band(g.x, -0.13, 0.13, 0.01), g.band(g.y, -0.64, -0.30, 0.01))
    lime = g.mul(inside, g.band(g.z, C.WATER_Z + 0.0005, C.WATER_Z + 0.006, 0.004))
    lime = g.mul(lime, g.maprange(g.noise(30.0, 2.0), 0.35, 0.65, 0.4, 1.0))
    base = g.mixc(g.mul(lime, 0.30), base, (0.78, 0.74, 0.64))
    rough = g.add(rough, g.mul(lime, 0.18))
    # Water spots on the inner bowl above the water line (very faint).
    spots = g.mul(g.mul(inside, g.band(g.z, C.WATER_Z + 0.01, 0.37, 0.02)),
                  g.maprange(g.noise(55.0, 1.0), 0.70, 0.74))
    rough = g.add(rough, g.mul(spots, 0.10))
    slot = g.mul(g.mul(g.band(g.x, -0.034, 0.034, 0.002), g.band(g.z, 0.373, 0.382, 0.0015)),
                 g.mul(g.band(g.y, -0.335, -0.29, 0.005), g.maprange(g.ny, -0.15, -0.45)))
    base = g.mixc(slot, base, (0.035, 0.036, 0.04))
    rough = g.mixf(slot, rough, 0.5)
    return g.finish(base, rough, 0.0, None)


def mat_fixture():
    """Brushed gunmetal PVD (contract): horizontal brushing, faint fingerprints on
    and around the flush buttons, a few dried water spots."""
    g = Graph(new_mat("src_fixture"))
    rough, h = metal.brushed(g, 0.30, axis="X", streak=0.05)
    base = C.FIXTURE
    region = g.mul(g.band(g.z, 1.03, 1.17, 0.02), g.band(g.x, -0.12, 0.12, 0.02))
    base, rough = wear.smudges(g, base, rough, region, rougher=0.07, darker=0.0)
    spots = g.mul(g.maprange(g.noise(140.0, 1.0, 0.5, vector=g.offset((0.7, 0.2, 0.4))), 0.725, 0.75),
                  g.maprange(g.noise(4.0, 2.0), 0.50, 0.70))
    base = g.mixc(g.mul(spots, 0.30), base, (0.20, 0.20, 0.19))
    rough = g.add(rough, g.mul(spots, 0.15))
    metal_f = g.sub(1.0, g.mul(spots, 0.3))
    return g.finish_height(base, rough, metal_f, h)


def mat_seat():
    """Duroplast seat and lid: glossy white, slightly warmer and softer than the bowl."""
    g = Graph(new_mat("src_seat"))
    rough = g.add(0.12, g.mul(g.sub(g.noise(12.0, 2.0), 0.5), 0.03))
    n = g.bump(g.noise(90.0, 2.0), 1.0, 0.0003)
    return g.finish(C.SEAT_WHITE, rough, 0.0, n)


def mat_paper():
    """Soft 3-ply tissue: quilted embossing on the outside, faint layer rings on the ends."""
    g = Graph(new_mat("src_paper"))
    base = (0.86, 0.85, 0.82)
    r = g.math("SQRT", g.add(g.mul(g.x, g.x), g.mul(g.y, g.y)))
    ang = g.math("ARCTAN2", g.y, g.x)
    side = g.maprange(g.math("ABSOLUTE", g.nz), 0.5, 0.2)  # 1 on the outer cylinder
    # Quilted diamonds on the outside, ~8 mm pitch (45 per turn keeps the seam invisible).
    u = g.mul(ang, 45.0)
    v = g.mul(g.z, 2 * math.pi / 0.008)
    d1 = g.math("SINE", g.add(u, v))
    d2 = g.math("SINE", g.sub(u, v))
    quilt = g.mul(g.mul(g.add(d1, 1.0), g.add(d2, 1.0)), 0.25)
    # Three perforation lines around the outer sheet.
    perf = g.maprange(g.math("ABSOLUTE", g.math("SINE", g.mul(ang, 1.5))), 0.03, 0.0)
    ends = g.sub(1.0, side)
    rings = g.mul(ends, g.maprange(g.noise(1.0, 2.0, 0.5, vector=g.combine(g.mul(r, 600.0), 0.0, 0.0)), 0.4, 0.7))
    base = g.scale_color(base, g.sub(1.0, g.add(g.mul(rings, 0.05), g.mul(g.mul(perf, side), 0.04))))
    base = g.scale_color(base, g.add(0.97, g.mul(g.noise(25.0, 2.0), 0.05)))
    height = g.add(g.mul(g.mul(quilt, side), 0.00012), g.mul(g.mul(perf, side), -0.0001))
    return g.finish_height(base, 0.92, 0.0, height)


def mat_cardboard():
    g = Graph(new_mat("src_cardboard"))
    base = g.mixc(g.noise(40.0, 2.0), (0.34, 0.21, 0.11), (0.42, 0.28, 0.15))
    rough = g.add(0.85, g.mul(g.sub(g.noise(20.0), 0.5), 0.08))
    return g.finish(base, rough, 0.0, g.bump(g.noise(120.0, 2.0), 1.0, 0.0004))


def build_materials():
    return {
        "marble": mat_marble(),
        "recess": materials.dark_plastic("toilet_recess", base=(0.035, 0.034, 0.033), rough=0.6),
        "porcelain": mat_porcelain(),
        "fixture": mat_fixture(),
        "seat": mat_seat(),
        "rubber": materials.rubber("toilet_rubber", base=(0.75, 0.75, 0.73), rough=0.6),
        "paper": mat_paper(),
        "cardboard": mat_cardboard(),
        # Unbaked: still water, its own slot so Godot can swap in a water shader.
        "water": solid_mat(C.WATER_MAT, (0.62, 0.68, 0.70), 0.03),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def drop_faces(ob, test):
    """Delete faces whose (center, normal) pass `test` (hidden back/bottom faces)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if test(f.calc_center_median(), f.normal)], context="FACES")
    bm.to_mesh(ob.data)
    bm.free()


def against_wall(c, n):
    return c.y > -0.001 and n.y > 0.9


def on_floor(c, n):
    return c.z < 0.001 and n.z < -0.9


# ---------------------------------------------------------------------------
# Body: installation box, bowl, water, hinge posts, flush plate, roll holder
# ---------------------------------------------------------------------------
def build_box(coll, mats):
    bm = bmesh.new()
    bm_box(bm, (-C.BOX_X, C.BOX_FACE, 0.0), (C.BOX_X, 0.0, C.CLAD_TOP))
    clad = new_object("Cladding", bm, coll, material=mats["marble"])
    finish(clad, 0.0025, 3)
    drop_faces(clad, lambda c, n: against_wall(c, n) or on_floor(c, n))
    tag(clad, "body")

    g = C.GAP_DEPTH
    bm = bmesh.new()
    bm_box(bm, (-C.BOX_X + g, C.BOX_FACE + g, C.CLAD_TOP - 0.002), (C.BOX_X - g, 0.0, C.CLAD_TOP + C.GAP_H + 0.002))
    recess = new_object("ShadowGap", bm, coll, material=mats["recess"])
    shade(recess)
    drop_faces(recess, against_wall)
    tag(recess, "body")

    bm = bmesh.new()
    bm_box(bm, (-C.BOX_X, C.BOX_FACE, C.SHELF_TOP - C.SHELF_T), (C.BOX_X, 0.0, C.SHELF_TOP))
    shelf = new_object("Shelf", bm, coll, material=mats["marble"])
    finish(shelf, 0.003, 3)
    drop_faces(shelf, against_wall)
    tag(shelf, "body")


def bowl_rings():
    """Rings of the bowl from the outer bottom, up the shell, over the rim and down
    the basin to below the water line (one closed surface)."""
    L0 = C.BOWL_BACK - C.BOWL_FRONT
    b0 = C.BOWL_HALF_W
    rings = []
    # Lower shell: a quarter ellipse from the flat underside to the vertical sides.
    dl, dw, zc = 0.255, 0.075, 0.300
    hh = zc - C.BOWL_BOTTOM
    for psi in (0, 7, 14, 22, 31, 41, 52, 64, 77, 90):
        s = math.sin(math.radians(psi))
        rings.append(C.bowl_outer(L0 - dl * (1 - s), b0 - dw * (1 - s), zc - hh * math.cos(math.radians(psi))))
    rings.append(C.bowl_outer(L0, b0, 0.350))
    # Rounded outer rim edge (r 10 mm).
    r = 0.010
    for phi in (0.0, 22.5, 45.0, 67.5, 90.0):
        a = math.radians(phi)
        inset = r * (1 - math.cos(a))
        rings.append(C.bowl_outer(L0 - inset, b0 - inset, C.RIM_Z - r + r * math.sin(a)))
    # Flat rim top to the rounded inner lip (r 6 mm), then the rimless basin wall.
    lip = 0.006
    for phi in (90.0, 67.5, 45.0, 22.5, 0.0):
        a = math.radians(phi)
        rings.append(C.bowl_opening(lip * (1 - math.cos(a)), C.RIM_Z - lip + lip * math.sin(a)))
    z_top = C.RIM_Z - lip
    for q in (0.86, 0.72, 0.58, 0.45, 0.33, 0.23, 0.14, 0.07, 0.025, 0.0):
        rings.append(C.bowl_opening(0.0, C.WATER_Z + q * (z_top - C.WATER_Z), 1.0 - math.sqrt(q)))
    rings.append(C.bowl_opening(0.0, C.WATER_Z - 0.02, 1.22))
    rings.append(C.bowl_opening(0.0, C.WATER_Z - 0.04, 1.40))
    return rings


def build_bowl(coll, mats):
    bm = bmesh.new()
    loft_rings(bm, bowl_rings(), cap_start=True, cap_end=True)
    bowl = new_object("Bowl", bm, coll, material=mats["porcelain"])
    shade(bowl, 40.0)
    tag(bowl, "body")

    bm = bmesh.new()
    bm.faces.new([bm.verts.new(p) for p in C.bowl_opening(0.004, C.WATER_Z + 0.0005, 1.0)])
    water = new_object("Water", bm, coll, material=mats["water"])
    shade(water, 89.0)
    tag(water, "body")

    # Hinge posts on the rim and the axle pin (static; seat and lid turn around it).
    bm = bmesh.new()
    hy, hz = C.HINGE.y, C.HINGE.z
    for sx in (-1, 1):
        x0, x1 = sorted((sx * C.POST[0], sx * C.POST[1]))
        bm_box(bm, (x0, hy - 0.0095, C.RIM_Z - 0.002), (x1, hy + 0.0095, hz))
        bm_cyl(bm, 0.0095, x1 - x0, cyl_x(((x0 + x1) / 2, hy, hz)), 20)
        bm_box(bm, (x0 - 0.004, hy - 0.016, C.RIM_Z - 0.002), (x1 + 0.004, hy + 0.016, C.RIM_Z + 0.0035))
    posts = new_object("HingePosts", bm, coll, material=mats["fixture"])
    finish(posts, 0.0012, 1)
    tag(posts, "body")
    bm = bmesh.new()
    bm_cyl(bm, 0.0042, 2 * C.PIN_X, cyl_x(C.HINGE), 16)
    for sx in (-1, 1):
        bm_cyl(bm, 0.0078, 0.004, cyl_x((sx * (C.PIN_X - 0.0005), hy, hz)), 20)
    pin = new_object("HingePin", bm, coll, material=mats["fixture"])
    finish(pin, 0.0010, 1)
    tag(pin, "body")


def build_flush_plate(coll, mats):
    c = C.PLATE_C
    y_front = C.BOX_FACE - C.PLATE_T
    bm = bmesh.new()
    prism_y(bm, rounded_rect_xz(c.x, c.z, C.PLATE_W, C.PLATE_H, C.PLATE_R, 6), y_front, C.BOX_FACE + 0.001)
    plate = new_object("FlushPlate", bm, coll, material=mats["fixture"])
    bm = bmesh.new()
    prism_y(bm, rounded_rect_xz(c.x, c.z, C.POCKET_W, C.POCKET_H, 0.0055, 4), y_front - 0.01, C.POCKET_FLOOR)
    cut(plate, bm, coll)
    finish(plate, 0.0015, 2)
    drop_faces(plate, lambda cc, n: n.y > 0.9 and cc.y > C.BOX_FACE)
    tag(plate, "body")


def build_holder(coll, mats):
    y0 = C.BOX_FACE
    bm = bmesh.new()
    bm_cyl(bm, C.ROSE_R, C.ROSE_T, cyl_y((C.HOLDER_X, y0 - C.ROSE_T / 2 + 0.0005, C.HOLDER_Z)), 32)
    rose = new_object("HolderRose", bm, coll, material=mats["fixture"])
    finish(rose, 0.002, 2)
    tag(rose, "body")
    bm = bmesh.new()
    path = round_polyline([(C.HOLDER_X, y0 - C.ROSE_T + 0.002, C.HOLDER_Z), (C.HOLDER_X, C.BAR_Y, C.HOLDER_Z),
                           (C.BAR_X1, C.BAR_Y, C.HOLDER_Z)], 0.016, steps=6)
    sweep(bm, path, circle_profile(C.BAR_R, 16), up=(0.0, 0.0, 1.0))
    bar = new_object("HolderBar", bm, coll, material=mats["fixture"])
    shade(bar, 50.0)
    tag(bar, "body")
    bm = bmesh.new()
    bm_cyl(bm, 0.0068, 0.007, cyl_x((C.BAR_X1 + 0.0015, C.BAR_Y, C.HOLDER_Z)), 20)
    tip = new_object("HolderTip", bm, coll, material=mats["fixture"])
    finish(tip, 0.0022, 2)
    tag(tip, "body")


def build_collision(col_coll):
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColBox", (-C.BOX_X, C.BOX_FACE, 0.0), (C.BOX_X, 0.0, C.SHELF_TOP))
    # Bowl: a hollow ring above the water so things can drop in, a solid base below.
    col("ColBowlBase", (-0.120, -0.585, 0.070), (0.120, C.BOX_FACE, 0.160))
    col("ColBowlBasin", (-0.150, -0.700, 0.160), (0.150, C.BOX_FACE, C.WATER_Z))
    col("ColRimBack", (-0.175, -0.315, C.WATER_Z), (0.175, C.BOX_FACE, C.RIM_Z))
    col("ColRimFront", (-0.110, -0.748, C.WATER_Z), (0.110, -0.700, C.RIM_Z))
    for sx, side in ((-1, "L"), (1, "R")):
        x0, x1 = sorted((sx * 0.135, sx * 0.178))
        col(f"ColRimSide{side}", (x0, -0.660, C.WATER_Z), (x1, -0.315, C.RIM_Z))
        x0, x1 = sorted((sx * 0.105, sx * 0.160))
        col(f"ColRimCorner{side}", (x0, -0.715, C.WATER_Z), (x1, -0.660, C.RIM_Z))


# ---------------------------------------------------------------------------
# Seat and lid (roots on the hinge axis, closed)
# ---------------------------------------------------------------------------
SEAT_PROFILE = [
    (0.0, 0.0070, C.SEAT_Z0), (0.0, 0.0025, C.SEAT_Z0 + 0.0006), (0.0, 0.0004, C.SEAT_Z0 + 0.0030),
    (0.0, 0.0, C.SEAT_Z0 + 0.0065), (0.0, 0.0006, 0.4135), (0.0, 0.0022, 0.4165), (0.0, 0.0050, 0.4187),
    (0.0, 0.0095, 0.4198), (0.30, 0.0, C.SEAT_Z1), (0.70, 0.0, C.SEAT_Z1),
    (1.0, -0.0095, 0.4197), (1.0, -0.0050, 0.4184), (1.0, -0.0022, 0.4160), (1.0, -0.0006, 0.4125),
    (1.0, 0.0, 0.4085), (1.0, -0.0006, 0.4055), (1.0, -0.0025, C.SEAT_Z0 + 0.0006), (1.0, -0.0070, C.SEAT_Z0),
    (0.5, 0.0, C.SEAT_Z0),
]

LID_PROFILE = [
    (1.0, 0.0, C.LID_Z0), (0.5, 0.0, C.LID_Z0), (0.0, 0.010, C.LID_Z0), (0.0, 0.004, C.LID_Z0 + 0.0008),
    (0.0, 0.001, C.LID_Z0 + 0.003), (0.0, 0.0, C.LID_Z0 + 0.007), (0.0, 0.0005, C.LID_Z0 + 0.011),
    (0.0, 0.0025, C.LID_Z0 + 0.0155), (0.0, 0.0060, C.LID_Z1 - 0.0015), (0.0, 0.0110, C.LID_Z1),
    (0.0, 0.0250, C.LID_Z1 + 0.0007), (0.5, 0.0, C.LID_Z1 + 0.0017), (1.0, 0.0, C.LID_Z1 + C.LID_CROWN),
]


def to_local(bm):
    bmesh.ops.translate(bm, vec=-C.HINGE, verts=bm.verts)
    return bm


def build_seat(coll, mats):
    outer, inner = C.seat_outer(), C.seat_inner()
    bm = bmesh.new()
    loft_rings(bm, [blend_ring(outer, inner, f, d, z) for f, d, z in SEAT_PROFILE], closed=True)
    seat = new_object("Seat", to_local(bm), coll, origin=C.HINGE, material=mats["seat"])
    shade(seat, 40.0)
    tag(seat, "seat")

    hy, hz = C.HINGE.y, C.HINGE.z
    bm = bmesh.new()
    for sx in (-1, 1):
        x0, x1 = sorted((sx * C.SEAT_KNUCKLE[0], sx * C.SEAT_KNUCKLE[1]))
        bm_box(bm, (x0, hy - 0.027, C.SEAT_Z0 + 0.002), (x1, hy, C.SEAT_Z1 - 0.0005))
    arms = new_object("SeatHingeArms", to_local(bm), coll, material=mats["seat"], parent=seat)
    finish(arms, 0.003, 2)
    tag(arms, "seat")
    bm = bmesh.new()
    for sx in (-1, 1):
        x0, x1 = sorted((sx * C.SEAT_KNUCKLE[0], sx * C.SEAT_KNUCKLE[1]))
        bm_cyl(bm, C.HINGE_R, x1 - x0, cyl_x(((x0 + x1) / 2, hy, hz)), 24)
    knuckles = new_object("SeatKnuckles", to_local(bm), coll, material=mats["fixture"], parent=seat)
    finish(knuckles, 0.0012, 2)
    tag(knuckles, "seat")

    # Rubber bumpers under the ring, over the rim.
    bm = bmesh.new()
    n = C.N_OUTLINE
    assert n == 80, "bumper indices assume 80 outline points"
    for i, f in ((14, 0.25), (26, 0.25), (51, 0.35), (69, 0.35)):  # over the rim, symmetric
        p = outer[i].lerp(inner[i], f)
        bm_cyl(bm, 0.009, C.SEAT_Z0 - C.BUMPER_Z0 + 0.001, cyl_z((p.x, p.y, (C.BUMPER_Z0 + C.SEAT_Z0 + 0.001) / 2)), 16)
    bumpers = new_object("SeatBumpers", to_local(bm), coll, material=mats["rubber"], parent=seat)
    finish(bumpers, 0.0008, 1)
    tag(bumpers, "seat")

    front = outer[3 * n // 4]
    tag(new_empty("HandleGrip", coll, Vector((0.0, front.y + 0.004, (C.SEAT_Z0 + C.SEAT_Z1) / 2)) - C.HINGE,
                  parent=seat), "seat")
    return seat


def build_lid(coll, mats):
    outer = C.lid_outer()
    cen = Vector((0.0, -0.47, 0.0))
    inner = [cen + (p - cen) * 0.35 for p in outer]
    bm = bmesh.new()
    loft_rings(bm, [blend_ring(outer, inner, f, d, z) for f, d, z in LID_PROFILE], cap_start=True, cap_end=True)
    lid = new_object("Lid", to_local(bm), coll, origin=C.HINGE, material=mats["seat"])
    shade(lid, 40.0)
    tag(lid, "lid")

    hy, hz = C.HINGE.y, C.HINGE.z
    bm = bmesh.new()
    for sx in (-1, 1):
        x0, x1 = sorted((sx * C.LID_KNUCKLE[0], sx * C.LID_KNUCKLE[1]))
        bm_box(bm, (x0, hy - 0.030, C.LID_Z0 + 0.0005), (x1, hy, C.LID_Z1 - 0.004))
    arms = new_object("LidHingeArms", to_local(bm), coll, material=mats["seat"], parent=lid)
    finish(arms, 0.003, 2)
    tag(arms, "lid")
    bm = bmesh.new()
    for sx in (-1, 1):
        x0, x1 = sorted((sx * C.LID_KNUCKLE[0], sx * C.LID_KNUCKLE[1]))
        bm_cyl(bm, C.HINGE_R, x1 - x0, cyl_x(((x0 + x1) / 2, hy, hz)), 24)
    knuckles = new_object("LidKnuckles", to_local(bm), coll, material=mats["fixture"], parent=lid)
    finish(knuckles, 0.0012, 2)
    tag(knuckles, "lid")

    front = outer[3 * C.N_OUTLINE // 4]
    tag(new_empty("HandleGrip", coll, Vector((0.0, front.y + 0.004, (C.LID_Z0 + C.LID_Z1) / 2)) - C.HINGE,
                  parent=lid), "lid")
    return lid


# ---------------------------------------------------------------------------
# Flush buttons (roots at their face centers) and the roll
# ---------------------------------------------------------------------------
def build_button(name, part, width, x, coll, mats):
    bm = bmesh.new()
    prism_y(bm, rounded_rect_xz(0.0, 0.0, width, C.BTN_H, C.BTN_R, 4), 0.0, C.BTN_T)
    ob = new_object(name, bm, coll, origin=(x, C.BTN_FACE_Y, C.PLATE_C.z), material=mats["fixture"])
    finish(ob, 0.0012, 2)
    tag(ob, part)
    return ob


def roll_profile():
    """Closed (r, z) cross-section of the upright roll: core tube and soft paper body."""
    ri, rc, ro, w = C.ROLL_R_IN, C.ROLL_R_CORE, C.ROLL_R, C.ROLL_W
    return [
        (ri, 0.0015), (ri + 0.0004, 0.0002), (rc, 0.0), (rc + 0.0008, 0.0012),
        (0.034, 0.0013), (0.046, 0.0012), (ro - 0.003, 0.0010), (ro - 0.0012, 0.0024), (ro - 0.0002, 0.0055),
        (ro, 0.012), (ro + 0.0003, w / 2), (ro, w - 0.012),
        (ro - 0.0002, w - 0.0055), (ro - 0.0012, w - 0.0024), (ro - 0.003, w - 0.0010), (0.046, w - 0.0012),
        (0.034, w - 0.0013), (rc + 0.0008, w - 0.0012), (rc, w), (ri + 0.0004, w - 0.0002), (ri, w - 0.0015),
        (ri, w / 2),
    ]


def build_roll(coll, mats):
    bm = bmesh.new()
    lathe(bm, roll_profile(), segments=40, closed=True)
    roll = new_object("Roll", bm, coll, material=mats["paper"])
    roll.data.materials.append(mats["cardboard"])
    for p in roll.data.polygons:
        c = p.center
        if math.hypot(c.x, c.y) < C.ROLL_R_CORE + 0.0006:
            p.material_index = 1
    shade(roll, 40.0)
    tag(roll, "roll")
    # Linked copy hanging on the holder for renders and clearance checks (not exported).
    hang = C.ROLL_HANG_CENTER - Vector((C.ROLL_W / 2, 0.0, 0.0))
    instance(roll, "RollHanging", hang, rotation=(0.0, math.radians(90.0), 0.0), part="instance")
    return roll


def main():
    clear_scene()
    mats = build_materials()
    body = get_collection("ToiletBody")
    build_box(body, mats)
    build_bowl(body, mats)
    build_flush_plate(body, mats)
    build_holder(body, mats)
    build_collision(get_collection("ToiletBodyCollision"))
    build_seat(get_collection("ToiletSeat"), mats)
    build_lid(get_collection("ToiletLid"), mats)
    buttons = get_collection("ToiletFlush")
    build_button("FlushSmall", "flush_small", C.BTN_SMALL_W, C.BTN_SMALL_X, buttons, mats)
    build_button("FlushLarge", "flush_large", C.BTN_LARGE_W, C.BTN_LARGE_X, buttons, mats)
    build_roll(get_collection("ToiletRoll"), mats)
    parts = ("body", "body_col", "seat", "lid", "flush_small", "flush_large", "roll")
    print("TRIS " + " ".join(f"{p}={part_tris(p)}" for p in parts))
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
