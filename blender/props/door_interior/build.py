"""Stage 1: build the interior door (frame, leaf, lever, thumb-turn) and its source materials, save.

  blender -b --factory-startup --python blender/props/door_interior/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from door_interior_common import (  # noqa: E402
    BLEND, BOLT_HOLE, CASING_T, CASING_W, CASING_X0, CASING_Z0, FACEPLATE_Y, FACEPLATE_Z, FRAME_PAINT,
    GAP, GRIP_DX, HEAD_Z, HINGE, HINGE_H, HINGE_ZS, JAMB_X, KNUCKLE_GAP, KNUCKLE_R, LATCH_HOLE,
    LEAF_PAINT, LEAF_X0, LEAF_X1, LEAF_Y0, LEAF_Y1, LEAF_Z0, LEAF_Z1, LEAF_T, LEVER_LEN, LEVER_OUT,
    LEVER_R, LINING_T, OPEN_H, OPEN_X, PLATE_T, PLATE_W, PRIMER, ROSE_H, ROSE_R, SPINDLE_X, SPINDLE_Z,
    STEEL, STOP_T, STOP_X, STOP_Y0, STOP_Y1, STOP_Z, STRIKE_Y, STRIKE_Z, TURN_Z, WALL_Y, to_leaf,
)
from lib_candidates import facing, lathe_axis, mitered_sweep, rounded_polygon, spun  # noqa: E402
from arcology_blender import metal, wear  # noqa: E402
from arcology_blender.curves import circle_profile, round_polyline, rounded_rect_profile, sweep  # noqa: E402
from arcology_blender.geo import bm_box, bm_cyl, collision_box, cut, cyl_z, finish, new_empty, new_object, shade  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

PLATE_Y = 0.0085  # hinge plates start this far behind the axis (clear of the knuckles and the eased edges)


# ---------------------------------------------------------------------------
# Materials: `src_*` graphs in world coordinates (the leaf is closed while baking).
# Wear at medium scale and low contrast (VR shimmer).
# ---------------------------------------------------------------------------
def _faces(g):
    """Masks: front (-Y) and back (+Y) faces."""
    return g.maprange(g.ny, -0.5, -0.8), g.maprange(g.ny, 0.5, 0.8)


def mat_leaf_paint():
    """Satin warm grey paint on the leaf: orange peel, worn edges (more at the latch edge
    and the bottom), rubbed and fingerprinted around the levers on both faces and on the
    latch edge, kick scuffs on the bottom rail."""
    g = Graph(new_mat("src_leaf_paint"))
    base = LEAF_PAINT
    rough = g.add(0.42, g.mul(g.sub(g.noise(3.0, 2.0), 0.5), 0.06))
    h = g.mul(g.noise(240.0, 2.0, 0.5), 0.000012)  # roller orange peel
    front, back = _faces(g)
    edge = wear.convex_edges(g, radius=0.003, lo=0.04, hi=0.22)
    latch = g.maprange(g.x, 0.30, 0.42)
    low = g.maprange(g.z, 0.35, 0.05)
    mask = g.add(0.30, g.mul(g.math("MAXIMUM", latch, low), 0.70))
    base, rough = wear.edge_wear(g, base, rough, edge, mask, PRIMER, amount=0.40, rough_delta=0.10)
    pts = [(SPINDLE_X, SPINDLE_Z)]
    for face in (front, back):  # satin rubbed glossy and a little grubby around the rose
        base, rough = wear.fixture_wear(g, base, rough, pts, r_in=0.030, r_out=0.100, rougher=-0.15,
                                        lighter=-0.09, facing=face)
    faces = g.math("MAXIMUM", front, back)
    hand = g.mul(g.rect_xz((SPINDLE_X - 0.21, 0.93), (LEAF_X1 + 0.01, 1.30), 0.05), faces)
    base, rough = wear.smudges(g, base, rough, hand, rougher=0.20, darker=0.09)
    edge_face = g.mul(g.maprange(g.nx, 0.6, 0.9), g.band(g.z, 0.85, 1.45, 0.12))
    base, rough = wear.smudges(g, base, rough, edge_face, rougher=0.15, darker=0.10)
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.24, z_full=0.04, rougher=0.02, darker=0.25,
                                     mask=faces)
    base = wear.floor_grime(g, base, LEAF_Z0, 0.05, 0.85)
    return g.finish_height(base, rough, 0.0, h)


def mat_frame_paint():
    """Semi-gloss frame paint, a step darker than the leaf: crisp edges worn at the
    bottom (vacuum, shoes) and where hands grab the latch-side jamb, dust on the head
    casing, floor grime."""
    g = Graph(new_mat("src_frame_paint"))
    base = FRAME_PAINT
    rough = g.add(0.34, g.mul(g.sub(g.noise(3.5, 2.0), 0.5), 0.05))
    h = g.mul(g.noise(260.0, 2.0, 0.5), 0.000010)
    edge = wear.convex_edges(g, radius=0.002, lo=0.04, hi=0.22)
    low = g.maprange(g.z, 0.40, 0.04)
    hand_zone = g.mul(g.maprange(g.x, 0.38, 0.44), g.band(g.z, 0.85, 1.50, 0.15))
    mask = g.add(0.25, g.mul(g.math("MAXIMUM", low, hand_zone), 0.75))
    base, rough = wear.edge_wear(g, base, rough, edge, mask, PRIMER, amount=0.55, rough_delta=0.10)
    base, rough = wear.smudges(g, base, rough, hand_zone, rougher=0.14, darker=0.06)
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.22, z_full=0.03, rougher=0.03, darker=0.28)
    base = wear.floor_grime(g, base, 0.0, 0.05, 0.82)
    base, rough = wear.top_dust(g, base, rough, CASING_Z0 + CASING_W - 0.012, CASING_Z0 + CASING_W - 0.002,
                                amount=0.22)
    return g.finish_height(base, rough, 0.0, h)


def _holes(g, holes, center_x):
    """Dark latch/bolt openings on faces facing +-X near |x| = center_x: list of ((y0, y1), (z0, z1))."""
    side = g.mul(g.maprange(g.math("ABSOLUTE", g.nx), 0.6, 0.9),
                 g.band(g.x, center_x - 0.002, center_x + 0.002, 0.0005))  # latch side only (+X)
    m = 0.0
    for (y0, y1), (z0, z1) in holes:
        m = g.add(m, g.mul(g.band(g.y, y0, y1, 0.0006), g.band(g.z, z0, z1, 0.0006)))
    return g.mul(g.math("MINIMUM", m, 1.0), side)


def mat_steel(name, holes=(), hole_x=0.0, screws=()):
    """Brushed stainless (hinges, strike, faceplate): dark openings for latch and bolt,
    screw heads as dark rings at world (y, z) on the +-X faces."""
    g = Graph(new_mat(name))
    rough, h = metal.brushed(g, 0.30, axis="Z")
    base = STEEL
    metal_v = 1.0
    if holes:
        hole = _holes(g, holes, hole_x)
        base = g.mixc(hole, base, (0.025, 0.025, 0.027))
        rough = g.mixf(hole, rough, 0.6)
        metal_v = g.sub(1.0, g.mul(hole, 0.7))
    for (sy, sz) in screws:
        dy, dz = g.sub(g.y, sy), g.sub(g.z, sz)
        d = g.math("SQRT", g.add(g.mul(dy, dy), g.mul(dz, dz)))
        ring = g.mul(g.band(d, 0.0034, 0.0040, 0.0003), g.mul(g.maprange(g.math("ABSOLUTE", g.nx), 0.6, 0.9),
                                                              g.maprange(g.x, 0.40, 0.42)))
        slot = g.mul(g.mul(g.band(dy, -0.0030, 0.0030, 0.0002), g.band(dz, -0.0005, 0.0005, 0.0002)),
                     g.mul(g.maprange(d, 0.0036, 0.0030), g.maprange(g.x, 0.40, 0.42)))
        dark = g.math("MAXIMUM", ring, slot)
        base = g.mixc(g.mul(dark, 0.75), base, (0.06, 0.06, 0.065))
    base = wear.floor_grime(g, base, 0.0, 0.30, 0.80)
    return g.finish_height(base, rough, metal_v, h)


def mat_spun(name, center, fingerprints=0.6):
    """Spun stainless about the spindle (roses, coin-release disc) with light fingerprints."""
    g = Graph(new_mat(name))
    rough, h = spun(g, 0.27, "Y", center)
    base = STEEL
    base, rough = wear.smudges(g, base, rough, fingerprints, rougher=0.16, darker=0.05)
    return g.finish_height(base, rough, 1.0, h)


def mat_lever():
    """Brushed lever bar, polished a little by hands on the grip, fingerprints."""
    g = Graph(new_mat("src_lever_steel"))
    rough, h = metal.brushed(g, 0.28, axis="X")
    base = STEEL
    grip = g.band(g.x, SPINDLE_X - LEVER_LEN - 0.02, SPINDLE_X - 0.02, 0.03)
    rough = g.sub(rough, g.mul(grip, 0.06))
    base, rough = wear.smudges(g, base, rough, g.add(0.3, g.mul(grip, 0.5)), rougher=0.10, darker=0.03)
    return g.finish_height(base, rough, 1.0, h)


def mat_knob():
    g = Graph(new_mat("src_knob_steel"))
    rough, h = metal.brushed(g, 0.28, axis="Z")
    base, rough = wear.smudges(g, STEEL, rough, 0.8, rougher=0.18, darker=0.06)
    return g.finish_height(base, rough, 1.0, h)


def build_materials():
    strike_screws = [(sum(STRIKE_Y) / 2, STRIKE_Z[0] + 0.012), (sum(STRIKE_Y) / 2, STRIKE_Z[1] - 0.012)]
    face_screws = [(sum(FACEPLATE_Y) / 2, FACEPLATE_Z[0] + 0.012), (sum(FACEPLATE_Y) / 2, FACEPLATE_Z[1] - 0.012)]
    return {
        "leaf": mat_leaf_paint(),
        "frame": mat_frame_paint(),
        "steel_frame": mat_steel("src_steel_frame", (LATCH_HOLE, BOLT_HOLE), JAMB_X, strike_screws),
        "steel_leaf": mat_steel("src_steel_leaf", (LATCH_HOLE, BOLT_HOLE), LEAF_X1, face_screws),
        "rose": mat_spun("src_rose_steel", (SPINDLE_X, 0.0, SPINDLE_Z)),
        "lever": mat_lever(),
        "tt_rose": mat_spun("src_thumbturn_steel", (SPINDLE_X, 0.0, TURN_Z), 0.4),
        "knob": mat_knob(),
    }


# ---------------------------------------------------------------------------
# Profiles (u: away from the opening, v: along +Y or the casing thickness)
# ---------------------------------------------------------------------------
def u_path(x, z_top, y=0.0):
    """Left jamb up, across the head, right jamb down (u of `mitered_sweep` points outward)."""
    return [(-x, y, 0.0), (-x, y, z_top), (x, y, z_top), (x, y, 0.0)]


def lining_profile():
    y = WALL_Y
    return rounded_polygon([(0.0, -y), (LINING_T, -y), (LINING_T, y), (0.0, y)], [0.0012, 0, 0, 0.0012], 3)


def stop_profile():
    return rounded_polygon([(0.0, STOP_Y0), (STOP_T + 0.001, STOP_Y0), (STOP_T + 0.001, STOP_Y1), (0.0, STOP_Y1)],
                           [0.0015, 0, 0, 0.0015], 3)


def casing_profile(sign):
    """Flat casing, thicker at the opening (13 mm) than at the wall (9.5 mm), with a small
    step 9 mm from the inner edge; eased front edges, sharp back. sign -1: front wall face."""
    pts = [(0.0, 0.0), (CASING_W, 0.0), (CASING_W, 0.0095), (0.011, 0.0118), (0.009, CASING_T), (0.0, CASING_T)]
    radii = [0.0, 0.0, 0.0015, 0.0008, 0.0006, 0.0015]
    prof = rounded_polygon(pts, radii, 3)
    return [(u, sign * v) for u, v in prof]


# ---------------------------------------------------------------------------
# Frame (world coordinates)
# ---------------------------------------------------------------------------
def knuckle_ranges(zc):
    k = (HINGE_H - 2 * KNUCKLE_GAP) / 3
    z0 = zc - HINGE_H / 2
    return (z0, z0 + k), (z0 + k + KNUCKLE_GAP, z0 + 2 * k + KNUCKLE_GAP), (zc + HINGE_H / 2 - k, zc + HINGE_H / 2)


def knuckle(bm, x, y, z0, z1):
    bm_cyl(bm, KNUCKLE_R, z1 - z0, Matrix.Translation((x, y, (z0 + z1) / 2)), 24)


def finial(bm, x, y, z, up):
    """Pin cap: a low dome on the end of a frame knuckle."""
    prof = [(KNUCKLE_R * 0.92, 0.0)] + [(KNUCKLE_R * 0.92 * math.cos(a), 0.0035 * math.sin(a))
                                        for a in [math.radians(d) for d in (25, 50, 70, 90)]]
    prof[-1] = (0.0, 0.0035)
    m = Matrix.Translation((x, y, z)) @ (Matrix.Identity(4) if up else Matrix.Rotation(math.pi, 4, "X"))
    lathe_axis(bm, [(0.0, -0.0005)] + [(r, zz) for r, zz in prof], m, segments=24)


def build_frame(coll, col_coll, mats):
    paint = mats["frame"]
    parts = []

    bm = bmesh.new()
    mitered_sweep(bm, u_path(JAMB_X, HEAD_Z), lining_profile(), (0, 1, 0))
    parts.append(new_object("Lining", bm, coll, material=paint))

    bm = bmesh.new()
    mitered_sweep(bm, u_path(STOP_X, STOP_Z), stop_profile(), (0, 1, 0))
    parts.append(new_object("Stop", bm, coll, material=paint))

    for name, sign in (("CasingFront", -1.0), ("CasingBack", 1.0)):
        bm = bmesh.new()
        mitered_sweep(bm, u_path(CASING_X0, CASING_Z0, sign * WALL_Y), casing_profile(sign), (0, 1, 0))
        parts.append(new_object(name, bm, coll, material=paint))
    for ob in parts:
        shade(ob, 40.0)

    # Hinges: jamb plates and the two outer knuckles with pin caps
    bm = bmesh.new()
    hx, hy = HINGE.x, HINGE.y
    for zc in HINGE_ZS:
        lo, _, hi = knuckle_ranges(zc)
        for z0, z1 in (lo, hi):
            knuckle(bm, hx, hy, z0, z1)
            bm_box(bm, (-JAMB_X - 0.0003, hy, z0), (-JAMB_X + PLATE_T, hy + PLATE_Y + 0.0005, z1))  # tab
        finial(bm, hx, hy, hi[1], True)
        finial(bm, hx, hy, lo[0], False)
        bm_box(bm, (-JAMB_X - 0.0003, hy + PLATE_Y, zc - HINGE_H / 2), (-JAMB_X + PLATE_T, hy + PLATE_Y + PLATE_W,
                                                                       zc + HINGE_H / 2))
    hinges = new_object("FrameHinges", bm, coll, material=mats["steel_frame"])
    finish(hinges, 0.0004, 1, sharp_angle=40.0)
    parts.append(hinges)

    # Strike plate on the latch jamb (0.6 mm proud), latch and bolt openings in the material
    bm = bmesh.new()
    bm_box(bm, (JAMB_X - 0.0006, STRIKE_Y[0], STRIKE_Z[0]), (JAMB_X + 0.0003, STRIKE_Y[1], STRIKE_Z[1]))
    strike = new_object("Strike", bm, coll, material=mats["steel_frame"])
    finish(strike, 0.0003, 1)
    parts.append(strike)

    for ob in parts:
        tag(ob, "body")

    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColJambLeft", (-OPEN_X, -WALL_Y, 0.0), (-JAMB_X, WALL_Y, OPEN_H))
    col("ColJambRight", (JAMB_X, -WALL_Y, 0.0), (OPEN_X, WALL_Y, OPEN_H))
    col("ColHead", (-JAMB_X, -WALL_Y, HEAD_Z), (JAMB_X, WALL_Y, OPEN_H))
    return parts


# ---------------------------------------------------------------------------
# Leaf (leaf-local coordinates: hinge axis at the origin, floor level)
# ---------------------------------------------------------------------------
def rose_profile(height):
    r, e = ROSE_R, 0.0035
    prof = [(0.0, -0.0005), (r, -0.0005), (r, height - e)]
    prof += [(r - e + e * math.cos(math.radians(a)), height - e + e * math.sin(math.radians(a))) for a in (30, 60, 90)]
    prof += [(0.012, height + 0.0003), (0.0, height + 0.0004)]
    return prof


def build_leaf(coll, mats):
    lo, hi = to_leaf((LEAF_X0, LEAF_Y0, LEAF_Z0)), to_leaf((LEAF_X1, LEAF_Y1, LEAF_Z1))
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    leaf = new_object("Leaf", bm, coll, origin=HINGE, material=mats["leaf"])
    finish(leaf, 0.0025, 3, sharp_angle=40.0)
    tag(leaf, "door")

    def child(name, bm, material, bevel=None, segs=1):
        ob = new_object(name, bm, coll, material=material, parent=leaf)
        finish(ob, bevel, segs, sharp_angle=40.0)
        tag(ob, "door")
        return ob

    # Hinge knuckle (middle) with its plate on the leaf edge
    bm = bmesh.new()
    edge_x = lo.x  # leaf edge, 1.5 mm from the axis
    for zc in HINGE_ZS:
        _, (z0, z1), _ = knuckle_ranges(zc)
        knuckle(bm, 0.0, 0.0, z0, z1)
        bm_box(bm, (edge_x - PLATE_T, 0.0, z0), (edge_x + 0.0003, PLATE_Y + 0.0005, z1))
        bm_box(bm, (edge_x - PLATE_T, PLATE_Y, zc - HINGE_H / 2), (edge_x + 0.0003, PLATE_Y + PLATE_W, zc + HINGE_H / 2))
    child("LeafHinges", bm, mats["steel_leaf"], 0.0004)

    # Lock faceplate on the latch edge (0.5 mm proud)
    bm = bmesh.new()
    f0 = to_leaf((LEAF_X1 - 0.0003, FACEPLATE_Y[0], FACEPLATE_Z[0]))
    f1 = to_leaf((LEAF_X1 + 0.0005, FACEPLATE_Y[1], FACEPLATE_Z[1]))
    bm_box(bm, f0, f1)
    child("Faceplate", bm, mats["steel_leaf"], 0.0003)

    # Lever roses on both faces
    bm = bmesh.new()
    lathe_axis(bm, rose_profile(ROSE_H), Matrix.Translation(to_leaf((SPINDLE_X, LEAF_Y0, SPINDLE_Z))) @ facing("-Y"), 48)
    lathe_axis(bm, rose_profile(ROSE_H), Matrix.Translation(to_leaf((SPINDLE_X, LEAF_Y1, SPINDLE_Z))) @ facing("+Y"), 48)
    child("Roses", bm, mats["rose"])

    # Grip points and sockets for the separate lever / thumb-turn glbs
    grips = {
        "HandleGripFront": (SPINDLE_X + GRIP_DX, LEAF_Y0 - LEVER_OUT, SPINDLE_Z),
        "HandleGripBack": (SPINDLE_X + GRIP_DX, LEAF_Y1 + LEVER_OUT, SPINDLE_Z),
        "LeverSocketFront": (SPINDLE_X, LEAF_Y0, SPINDLE_Z),
        "LeverSocketBack": (SPINDLE_X, LEAF_Y1, SPINDLE_Z),
        "ThumbturnSocket": (SPINDLE_X, LEAF_Y0, TURN_Z),
    }
    for name, p in grips.items():
        e = new_empty(name, coll, to_leaf(p), parent=leaf, display="PLAIN_AXES" if "Socket" in name else "SPHERE")
        if name == "LeverSocketBack":
            e.rotation_euler = (math.pi, 0.0, 0.0)  # the lever glb turned to the back face
        tag(e, "door")
    return leaf


# ---------------------------------------------------------------------------
# Lever (origin on the spindle at the leaf's front face; bar toward the hinge, -X)
# ---------------------------------------------------------------------------
def build_lever(coll, mats):
    bm = bmesh.new()
    # Hub on the rose
    z0, z1 = ROSE_H - 0.001, ROSE_H + 0.0065
    hub = [(0.0, z0), (0.0118, z0), (0.0118, z1 - 0.002)]
    hub += [(0.0118 - 0.002 + 0.002 * math.cos(math.radians(a)), z1 - 0.002 + 0.002 * math.sin(math.radians(a)))
            for a in (30, 60, 90)]
    hub += [(0.0, z1)]
    lathe_axis(bm, hub, facing("-Y"), 32)
    # Bar: neck out from the hub, a 20 mm bend, the grip toward the hinge, a domed end
    path = round_polyline([(0.0, -(ROSE_H + 0.003), 0.0), (0.0, -LEVER_OUT, 0.0), (-LEVER_LEN, -LEVER_OUT, 0.0)],
                          0.020, steps=10)
    dense = [path[0]]
    for a, b in zip(path[:-1], path[1:]):
        n = max(1, int((b - a).length / 0.012))
        dense += [a.lerp(b, k / n) for k in range(1, n + 1)]
    taper = []
    for p in dense:
        t = max(0.0, min(1.0, (-p.x - 0.02) / (LEVER_LEN - 0.02)))
        taper.append((1.0 - 0.07 * t, 1.0 - 0.07 * t))
    segs = 32
    sweep(bm, dense, circle_profile(LEVER_R, segs), up=(0, 0, 1), scales=taper, caps=False)
    r_end = LEVER_R * taper[-1][0]
    dome = [(r_end * math.cos(math.radians(a)), 0.85 * r_end * math.sin(math.radians(a))) for a in range(0, 90, 15)]
    dome.append((0.0, 0.85 * r_end))
    lathe_axis(bm, dome, Matrix.Translation(dense[-1]) @ facing("-X"), segs)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    lever = new_object("Lever", bm, coll, origin=(SPINDLE_X, LEAF_Y0, SPINDLE_Z), material=mats["lever"])
    shade(lever, 40.0)
    tag(lever, "lever")
    return lever


# ---------------------------------------------------------------------------
# Bathroom privacy set: back thumb-turn + front coin release, both escutcheons
# ---------------------------------------------------------------------------
def build_thumbturn(coll, mats):
    root = new_empty("Thumbturn", coll, (SPINDLE_X, LEAF_Y0, TURN_Z), display="PLAIN_AXES")
    tag(root, "thumbturn")

    bm = bmesh.new()
    lathe_axis(bm, rose_profile(0.008), facing("-Y"), 48)
    lathe_axis(bm, rose_profile(0.008), Matrix.Translation((0.0, LEAF_T, 0.0)) @ facing("+Y"), 48)
    roses = new_object("ThumbturnRoses", bm, coll, material=mats["tt_rose"], parent=root)
    shade(roses, 40.0)
    tag(roses, "thumbturn")

    # Coin release: a raised disc with a vertical slot (vertical = unlocked)
    bm = bmesh.new()
    disc = [(0.0, 0.007), (0.0105, 0.007), (0.0105, 0.0098), (0.0098, 0.0106), (0.0088, 0.0108), (0.0, 0.0108)]
    lathe_axis(bm, disc, facing("-Y"), 40)
    coin = new_object("CoinRelease", bm, coll, material=mats["tt_rose"], parent=root)
    bm = bmesh.new()
    bm_box(bm, (-0.0009, -0.0125, -0.0065), (0.0009, -0.0096, 0.0065))
    cut(coin, bm, coll)
    shade(coin, 25.0)
    tag(coin, "thumbturn")

    # Thumb-turn on the back: hub + rounded blade (vertical = unlocked); origin on the axis at the back face
    bm = bmesh.new()
    hub = [(0.0, 0.0065), (0.0090, 0.0065), (0.0090, 0.0115), (0.0080, 0.0125), (0.0, 0.0125)]
    lathe_axis(bm, hub, facing("+Y"), 32)
    blade = [Vector((0.0, y, 0.0)) for y in (0.010, 0.016, 0.0205, 0.0230, 0.0245)]
    scales = [(1.0, 1.0), (0.93, 1.0), (0.95, 1.0), (0.80, 0.94), (0.45, 0.82)]
    sweep(bm, blade, rounded_rect_profile(0.0105, 0.038, 0.0048, 3), up=(0, 0, 1), scales=scales)
    knob = new_object("ThumbTurn", bm, coll, origin=(0.0, LEAF_T, 0.0), material=mats["knob"], parent=root)
    shade(knob, 40.0)
    tag(knob, "thumbturn")
    return root


def main():
    clear_scene()
    mats = build_materials()
    build_frame(get_collection("Frame"), get_collection("FrameCollision"), mats)
    build_leaf(get_collection("Leaf"), mats)
    build_lever(get_collection("Lever"), mats)
    build_thumbturn(get_collection("Thumbturn"), mats)
    tris = {p: part_tris(p) for p in ("body", "body_col", "door", "lever", "thumbturn")}
    print("TRIS " + " ".join(f"{k}={v}" for k, v in tris.items()) + f" total={sum(tris.values())}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
