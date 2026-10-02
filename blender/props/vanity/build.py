"""Stage 1: build the vanity (body, basin, mixer, drawers, lever, LED, soap dispenser) with
procedural source materials and collision, save the .blend.

  blender -b --factory-startup --python blender/props/vanity/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

from vanity_common import (  # noqa: E402
    AERATOR, BACK_Y0, BASIN_C, BLEND, BOTTOM_BOX, BOTTOM_DRAWER_ORIGIN, BOTTOM_FH, BOTTOM_RUN_Z, BOTTOM_Z1,
    BOWL_FLANGE, BOWL_RINGS, BOWL_T, BOX_BACK, BOX_FLOOR, BOX_SIDE, BOX_X, CAP_TOP, CASE_FRONT, CASE_Z0, CASE_Z1,
    CERAMIC, CHANNEL_Y, CORNER_SEGS, CUT_H, CUT_R, CUT_W, DISPENSER_POS, DRAIN_Z, FIXTURE, FLANGE_Z0, FRONT_T,
    FRONT_X, FRONT_Y, HX, LED_MAT, LED_STRENGTH, LED_WARM, LED_X, LED_Y0, LED_Y1, LED_Z0, LEVER_GRIP_LOCAL,
    LEVER_LEN, LEVER_PIVOT, LEVER_TILT, LINER_T, MARBLE, MARBLE_VEIN, MID_CHANNEL, MIXER, MIXER_R, MIXER_TOP,
    PORCELAIN, PULL_BACK, PULL_LIP, PULL_T, RUN_BODY_X0, RUN_DRAWER_X1, RUN_H, SPLASH_T, SPLASH_Z1, SPOUT_END,
    SPOUT_Z, T, TOP_BOX, TOP_DRAWER_ORIGIN, TOP_EASE, TOP_FH, TOP_FRONT, TOP_RUN_Z, TOP_Z0, TOP_Z1, TRAP_R,
    TRAP_Y0, TRAP_Y1, TRAP_Z, WALNUT, X_IN, X_OUT,
)
from lib_candidates import (  # noqa: E402
    convex_collider, lathe_along, loft_loops, offset_rings, rect_loop_around, reorigin, rounded_rect_loop,
)
from arcology_blender import curves, fabric, metal, wear, wood  # noqa: E402
from arcology_blender.geo import bm_box, bm_cyl, collision_box, cyl_x, finish, join, new_empty, new_object, shade  # noqa: E402,E501
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat, solid_mat  # noqa: E402

WALNUT_MID = tuple(c * 0.80 for c in WALNUT)     # veneer_axis averages above `mid`: lands near #4A3326
WALNUT_LIGHT = tuple(c * 1.20 for c in WALNUT)
WALNUT_DARK = tuple(c * 0.38 for c in WALNUT)
WALNUT_WORN = tuple(c * 1.5 for c in WALNUT)
LIMESCALE = (0.80, 0.78, 0.73)
RUNNER = (0.05, 0.05, 0.055)
FELT = (0.060, 0.058, 0.056)


# ---------------------------------------------------------------------------
# Materials (src_*, baked later). Hotel-clean: soft edges, water spots, a hint of limescale.
# ---------------------------------------------------------------------------
def water_spots(g, base, rough, mask, scale=55.0, amount=0.5, rougher=0.14, lighter=0.05):
    """Dried water spots inside a 0..1 mask: small dull, slightly lighter dots."""
    dots = g.maprange(g.noise(scale, 2.0, 0.5), 0.63, 0.70)
    dots = g.mul(g.mul(dots, g.maprange(g.noise(6.0, 2.0), 0.35, 0.65)), g.mul(mask, amount))
    rough = g.add(rough, g.mul(dots, rougher))
    base = g.mixc(g.mul(dots, lighter * 4.0), base, LIMESCALE)
    return base, rough


def mat_walnut(name, axis, drawer=None):
    """Satin walnut veneer, straight grain along a world axis. Convex edges a touch
    lighter (soft, hotel-clean). drawer=(x half width, z of the pull) adds
    fingerprints and a rubbed finish where hands reach under the edge pull."""
    g = Graph(new_mat(f"src_{name}"))
    base, rough, h = wood.veneer_axis(g, axis, mid=WALNUT_MID, light=WALNUT_LIGHT, dark=WALNUT_DARK, rough=0.45,
                                      figure=0.030, bands=0.75, streak=0.45, seed=0.37 if axis == "Y" else 0.0)
    edge = wear.convex_edges(g, radius=0.002)
    base, rough = wear.edge_wear(g, base, rough, edge, 0.35, WALNUT_WORN, amount=0.35, rough_delta=0.05)
    if drawer is not None:
        hw, zp = drawer
        front = g.maprange(g.ny, -0.5, -0.9)
        region = g.mul(g.mul(front, g.band(g.x, -0.30, 0.30, 0.20)), g.band(g.z, zp - 0.05, zp, 0.03))
        base, rough = wear.smudges(g, base, rough, region, rougher=0.10, darker=0.03)
    return g.finish_height(base, rough, 0.0, h)


def mat_marble():
    """Honed white marble with soft grey veins at a medium scale (a few cm wide, long,
    meandering; no fine veining: it shimmers in VR). Roughness 0.22 on tops, 0.35 on
    edges; water spots around the mixer and the basin's back edge."""
    g = Graph(new_mat("src_marble"))
    warp = 0.16
    wx = g.mul(g.sub(g.noise(2.2, 3.0, 0.55), 0.5), warp)
    wy = g.mul(g.sub(g.noise(2.2, 3.0, 0.55, vector=g.offset((3.1, 1.7, 0.4))), 0.5), warp)
    wz = g.mul(g.sub(g.noise(2.2, 3.0, 0.55, vector=g.offset((7.3, 2.9, 5.1))), 0.5), warp)
    x, y, z = g.add(g.x, wx), g.add(g.y, wy), g.add(g.z, wz)
    # rotate the frame so the veins run diagonally across the top, stretched along u
    u = g.add(g.mul(x, 0.80), g.mul(y, 0.60))
    v = g.sub(g.mul(y, 0.80), g.mul(x, 0.60))
    frame = g.combine(g.mul(u, 0.55), g.mul(v, 1.6), g.mul(z, 1.2))

    def contour(n, width, soft):
        return g.maprange(g.math("ABSOLUTE", g.sub(n, 0.5)), width + soft, width)

    main_n = g.noise(1.4, 2.0, 0.45, vector=frame)
    main = contour(main_n, 0.006, 0.010)
    halo = contour(main_n, 0.02, 0.05)
    fade = g.maprange(g.noise(2.5, 2.0, 0.5, vector=g.offset((1.3, 4.4, 2.2))), 0.30, 0.62)
    sec_n = g.noise(3.2, 2.0, 0.5, vector=g.vscale(frame, 1.0, 1.0, 1.0, (5.0, 2.0, 9.0)))
    sec = g.mul(contour(sec_n, 0.004, 0.008), g.maprange(g.noise(4.0, 2.0), 0.45, 0.70))
    vein = g.math("MAXIMUM", g.mul(main, g.add(0.35, g.mul(fade, 0.65))), g.mul(sec, 0.45))
    vein = g.math("MAXIMUM", vein, g.mul(halo, g.mul(fade, 0.16)))
    cloud = g.noise(3.0, 3.0, 0.55, vector=g.offset((2.0, 8.0, 1.0)))
    base = g.scale_color(MARBLE, g.add(0.97, g.mul(cloud, 0.06)))
    base = g.mixc(g.mul(vein, 0.78), base, MARBLE_VEIN)
    top = g.maprange(g.nz, 0.85, 0.97)
    rough = g.add(g.mixf(top, 0.35, 0.22), g.mul(vein, 0.03))
    rough = g.add(rough, g.mul(g.sub(g.noise(18.0, 2.0), 0.5), 0.04))
    # water spots: around the mixer, the back edge of the cutout, a few near the front edge
    up = g.mul(top, g.band(g.z, TOP_Z1 - 0.002, TOP_Z1 + 0.002, 0.001))
    near_mixer = g.maprange(g.dist_xy(MIXER.x, MIXER.y), 0.10, 0.03)
    near_basin = g.mul(g.maprange(g.dist_xy(BASIN_C.x, BASIN_C.y), 0.34, 0.20), 0.6)
    base, rough = water_spots(g, base, rough, g.mul(up, g.math("MAXIMUM", near_mixer, near_basin)),
                              scale=48.0, amount=0.8)
    h = g.mul(g.noise(160.0, 2.0, 0.5), 0.000015)       # honed: almost flat
    return g.finish_height(base, rough, 0.0, h)


def mat_porcelain():
    """Glossy sanitary porcelain; a faint limescale ring at the drain, water spots on the floor."""
    g = Graph(new_mat("src_porcelain"))
    rough = g.add(0.08, g.mul(g.sub(g.noise(12.0, 2.0), 0.5), 0.03))
    base = PORCELAIN
    d = g.dist_xy(BASIN_C.x, BASIN_C.y)
    floor = g.maprange(g.z, DRAIN_Z + 0.03, DRAIN_Z + 0.012)
    ring = g.mul(g.band(d, 0.036, 0.050, 0.010), g.maprange(g.noise(40.0, 2.0), 0.30, 0.65))
    ring = g.mul(ring, floor)
    base = g.mixc(g.mul(ring, 0.30), base, LIMESCALE)
    rough = g.add(rough, g.mul(ring, 0.18))
    spots = g.mul(floor, g.maprange(d, 0.16, 0.06))
    base, rough = water_spots(g, base, rough, spots, scale=65.0, amount=0.7, rougher=0.12, lighter=0.03)
    return g.finish(base, rough, 0.0, g.bump(g.noise(90.0, 2.0), 1.0, 0.00002))


def mat_fixture(name, axis="Z", center=None, spots=None, prints=None, aerator=False):
    """Brushed gunmetal PVD (#3B3E44): brushed streaks along `axis` (or spun around
    `center`), polished convex edges, dried water spots in `spots` = (x, y, z, radius),
    fingerprints in `prints` = (x, y, z, radius), a dark aerator insert."""
    g = Graph(new_mat(f"src_{name}"))
    rough, h = metal.brushed(g, 0.30, axis=axis, center=center, streak=0.05)
    base = FIXTURE
    edge = wear.convex_edges(g, radius=0.0012)
    rough = g.sub(rough, g.mul(edge, 0.06))
    base = g.scale_color(base, g.add(1.0, g.mul(edge, 0.25)))

    def sphere(p):
        dx, dy, dz = g.sub(g.x, p[0]), g.sub(g.y, p[1]), g.sub(g.z, p[2])
        dist = g.math("SQRT", g.add(g.add(g.mul(dx, dx), g.mul(dy, dy)), g.mul(dz, dz)))
        return g.maprange(dist, p[3], p[3] * 0.4)

    if spots is not None:
        base, rough = water_spots(g, base, rough, sphere(spots), scale=150.0, amount=0.6, rougher=0.16,
                                  lighter=0.012)
    if prints is not None:
        base, rough = wear.smudges(g, base, rough, sphere(prints), rougher=0.18, darker=0.0)
    metal_v = 1.0
    if aerator:
        m = g.mul(g.maprange(g.dist_xy(AERATOR.x, AERATOR.y), 0.0075, 0.0065),
                  g.maprange(g.z, AERATOR.z + 0.0012, AERATOR.z + 0.0004))
        base = g.mixc(m, base, (0.03, 0.03, 0.032))
        rough = g.mixf(m, rough, 0.55)
        metal_v = g.sub(1.0, g.mul(m, 0.8))
    return g.finish_height(base, rough, metal_v, h)


def mat_runner():
    g = Graph(new_mat("src_runner"))
    r = g.add(0.38, g.mul(g.sub(g.noise(30.0), 0.5), 0.1))
    return g.finish(RUNNER, r, 0.85, None)


def mat_felt():
    """Charcoal felt liner in the drawers (soft landing for whatever gets put in)."""
    g = Graph(new_mat("src_felt"))
    base, rough, h = fabric.fabric_base(g, FELT, rough=0.93, heather=0.05, slub=0.02, mottle=0.05,
                                        weave=0.00012)
    return fabric.fabric_finish(g, base, rough, h)


def mat_ceramic():
    """Matte charcoal glazed ceramic with faint lighter speckles; unglazed foot ring."""
    g = Graph(new_mat("src_ceramic"))
    speck = g.maprange(g.noise(220.0, 1.0, 0.5), 0.72, 0.76)
    base = g.mixc(g.mul(speck, 0.12), CERAMIC, (0.12, 0.11, 0.10))
    base = g.scale_color(base, g.add(0.96, g.mul(g.noise(14.0, 2.0), 0.08)))
    rough = g.add(0.55, g.mul(g.sub(g.noise(25.0, 2.0), 0.5), 0.06))
    foot = g.maprange(g.z, DISPENSER_POS.z + 0.0045, DISPENSER_POS.z + 0.0025)
    base = g.mixc(foot, base, (0.30, 0.27, 0.24))
    rough = g.mixf(foot, rough, 0.85)
    side = g.mul(g.band(g.z, DISPENSER_POS.z + 0.03, DISPENSER_POS.z + 0.12, 0.02), 1.0)
    base, rough = wear.smudges(g, base, rough, side, rougher=-0.10, darker=-0.03)
    h = g.mul(g.noise(140.0, 2.0, 0.5), 0.00002)
    return g.finish_height(base, rough, 0.0, h)


def build_materials():
    spout_tip = (AERATOR.x, AERATOR.y, AERATOR.z, 0.035)
    deck = (MIXER.x, MIXER.y, TOP_Z1, 0.045)
    pull_top = TOP_DRAWER_ORIGIN.z + TOP_FH
    pull_bot = BOTTOM_DRAWER_ORIGIN.z + BOTTOM_FH
    return {
        "walnut_x": mat_walnut("walnut_x", "X"),
        "walnut_y": mat_walnut("walnut_y", "Y"),
        "drawer_top_x": mat_walnut("drawer_top_x", "X", drawer=(FRONT_X, pull_top)),
        "drawer_top_y": mat_walnut("drawer_top_y", "Y"),
        "drawer_bottom_x": mat_walnut("drawer_bottom_x", "X", drawer=(FRONT_X, pull_bot)),
        "drawer_bottom_y": mat_walnut("drawer_bottom_y", "Y"),
        "marble": mat_marble(),
        "porcelain": mat_porcelain(),
        "channel": mat_fixture("channel", axis="X"),
        "plumbing": mat_fixture("plumbing", axis="Y"),
        "pull_top": mat_fixture("pull_top", axis="X", prints=(0.0, FRONT_Y, pull_top, 0.12)),
        "pull_bottom": mat_fixture("pull_bottom", axis="X", prints=(0.0, FRONT_Y, pull_bot, 0.12)),
        "mixer": mat_fixture("mixer", axis="Z", spots=deck),
        "spout": mat_fixture("spout", axis="Y", spots=spout_tip, aerator=True),
        "drain": mat_fixture("drain", center=(BASIN_C.x, BASIN_C.y), spots=(BASIN_C.x, BASIN_C.y, DRAIN_Z, 0.022)),
        "lever": mat_fixture("lever", axis="Y",
                             prints=(LEVER_PIVOT.x, LEVER_PIVOT.y - 0.085, LEVER_PIVOT.z + 0.01, 0.04)),
        "pump": mat_fixture("pump", axis="Z"),
        "runner": mat_runner(),
        "felt": mat_felt(),
        "ceramic": mat_ceramic(),
        "led": solid_mat(LED_MAT, (0.80, 0.78, 0.74), 0.4, emission=LED_WARM, emission_strength=LED_STRENGTH),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def box(name, lo, hi, coll, mat, bevel=0.0015, segs=2):
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    ob = new_object(name, bm, coll, material=mat)
    finish(ob, bevel, segs)
    return ob


def mesh(name, bm, coll, mat, bevel=None, segs=2, sharp=35.0, angle=30.0):
    ob = new_object(name, bm, coll, material=mat)
    if bevel:
        finish(ob, bevel, segs, angle=angle, sharp_angle=sharp)
    else:
        shade(ob, sharp)
    return ob


def ring_loop(ring, z=None):
    zz, w, d, r = ring
    return rounded_rect_loop(BASIN_C, w, d, r, zz if z is None else z, CORNER_SEGS)


# ---------------------------------------------------------------------------
# Body: carcass, finger channels, runners, marble top, basin, plumbing, LED
# ---------------------------------------------------------------------------
def build_carcass(coll, mats):
    wx, wy = mats["walnut_x"], mats["walnut_y"]
    parts = [
        box("SideL", (-X_OUT, CASE_FRONT, CASE_Z0), (-X_IN, 0.0, CASE_Z1), coll, wy),
        box("SideR", (X_IN, CASE_FRONT, CASE_Z0), (X_OUT, 0.0, CASE_Z1), coll, wy),
        box("Bottom", (-X_IN, CASE_FRONT, CASE_Z0), (X_IN, BACK_Y0, BOTTOM_Z1), coll, wx),
        box("Back", (-X_IN, BACK_Y0, CASE_Z0), (X_IN, 0.0, CASE_Z1), coll, wx, bevel=0.001),
    ]
    # Handleless finger channels (gunmetal): an L under the top (its web stays in
    # front of the basin), a C between the drawers.
    bm = bmesh.new()
    bm_box(bm, (-X_IN, CHANNEL_Y, 0.783), (X_IN, CHANNEL_Y + 0.003, TOP_Z0))
    bm_box(bm, (-X_IN, CASE_FRONT, TOP_Z0 - 0.003), (X_IN, CHANNEL_Y + 0.003, TOP_Z0))
    m0, m1 = MID_CHANNEL
    web = -0.462
    bm_box(bm, (-X_IN, web, m0), (X_IN, web + 0.003, m1))
    bm_box(bm, (-X_IN, CASE_FRONT, m1 - 0.003), (X_IN, web + 0.003, m1))
    bm_box(bm, (-X_IN, CASE_FRONT, m0), (X_IN, web + 0.003, m0 + 0.003))
    parts.append(mesh("Channels", bm, coll, mats["channel"], 0.0006, 1))
    # Fixed runner members on the side walls
    bm = bmesh.new()
    for origin, rz in ((TOP_DRAWER_ORIGIN, TOP_RUN_Z), (BOTTOM_DRAWER_ORIGIN, BOTTOM_RUN_Z)):
        z0, z1 = origin.z + rz - 0.003, origin.z + rz + RUN_H + 0.003
        for s in (-1, 1):
            xa, xb = sorted((s * RUN_BODY_X0, s * X_IN))
            bm_box(bm, (xa, CASE_FRONT + 0.004, z0), (xb, BACK_Y0 - 0.010, z1))
    parts.append(mesh("Runners", bm, coll, mats["runner"], 0.0008, 1))
    # LED channel under the bottom panel (the diffuser is its own object/material)
    bm = bmesh.new()
    bm_box(bm, (-LED_X - 0.004, LED_Y0, LED_Z0), (LED_X + 0.004, LED_Y1, CASE_Z0))
    parts.append(mesh("LEDChannel", bm, coll, mats["channel"], 0.0006, 1))
    return parts


def build_top(coll, mats):
    """Marble slab with the rounded basin cutout (eased edge) in clean quads, plus the upstand."""
    cs = CORNER_SEGS
    c = BASIN_C
    lo, hi = (-HX, TOP_FRONT), (HX, 0.0)
    e = TOP_EASE
    loops = [rect_loop_around(c, CUT_W + 2 * e, CUT_H + 2 * e, CUT_R + e, TOP_Z1, lo, hi, cs)]
    for i in range(5):
        th = math.radians(90.0 + 22.5 * i)
        d = e + e * math.cos(th)
        z = TOP_Z1 - e + e * math.sin(th)
        loops.append(rounded_rect_loop(c, CUT_W + 2 * d, CUT_H + 2 * d, CUT_R + d, z, cs))
    loops.append(rounded_rect_loop(c, CUT_W, CUT_H, CUT_R, TOP_Z0, cs))
    loops.append(rect_loop_around(c, CUT_W, CUT_H, CUT_R, TOP_Z0, lo, hi, cs))
    bm = bmesh.new()
    loft_loops(bm, loops, close=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    slab = mesh("Top", bm, coll, mats["marble"], 0.0025, 2, sharp=30.0, angle=40.0)
    splash = box("Upstand", (-HX, -SPLASH_T, TOP_Z1), (HX, 0.0, SPLASH_Z1), coll, mats["marble"], bevel=0.0025)
    return [slab, splash]


def build_basin(coll, mats):
    """Undermount porcelain bowl: inner surface, flange under the marble, outer
    surface, drain hole, as one closed loft."""
    inner = list(BOWL_RINGS)
    outer = offset_rings(inner, BOWL_T)
    z0, w0, d0, r0 = inner[0]
    grow = BOWL_T + BOWL_FLANGE
    loops = [ring_loop(rg) for rg in reversed(inner)]
    loops[-1] = ring_loop(inner[0], z0 - 0.0005)
    loops.append(rounded_rect_loop(BASIN_C, w0 + 2 * grow, d0 + 2 * grow, r0 + grow, z0 - 0.0005, CORNER_SEGS))
    loops.append(rounded_rect_loop(BASIN_C, w0 + 2 * grow, d0 + 2 * grow, r0 + grow, FLANGE_Z0, CORNER_SEGS))
    loops.append(rounded_rect_loop(BASIN_C, w0 + 2 * BOWL_T, d0 + 2 * BOWL_T, r0 + BOWL_T, FLANGE_Z0, CORNER_SEGS))
    loops += [ring_loop(rg) for rg in outer[1:]]
    bm = bmesh.new()
    loft_loops(bm, loops, close=True)
    return mesh("Basin", bm, coll, mats["porcelain"], sharp=50.0)


def build_plumbing(coll, mats):
    """Waste under the basin: nut, tailpiece bending back to the wall, an in-line
    compact trap, a wall rose. Visible with the top drawer open."""
    cx, cy = BASIN_C.x, BASIN_C.y
    bm = bmesh.new()
    curves.lathe(bm, [(0.0160, 0.684), (0.0228, 0.684), (0.0240, 0.6855), (0.0240, 0.6985), (0.0228, 0.700),
                      (0.0160, 0.700)], 24, center=(cx, cy, 0.0))
    path = curves.round_polyline([(cx, cy, 0.700), (cx, cy, TRAP_Z), (cx, BACK_Y0 + 0.002, TRAP_Z)], 0.028, steps=6)
    curves.tube(bm, path, 0.016, 16, along_attr=None, around_attrs=None)
    ln = TRAP_Y1 - TRAP_Y0
    lathe_along(bm, [(0.0166, 0.0), (0.0166, 0.004), (0.0255, 0.0065), (0.0280, 0.011), (0.0280, ln - 0.011),
                     (0.0255, ln - 0.0065), (0.0166, ln - 0.004), (0.0166, ln)], (cx, TRAP_Y0, TRAP_Z),
                (0.0, 1.0, 0.0), 24)
    lathe_along(bm, [(0.0166, 0.007), (0.0270, 0.007), (0.0300, 0.005), (0.0312, 0.002), (0.0312, 0.0)],
                (cx, BACK_Y0, TRAP_Z), (0.0, -1.0, 0.0), 24)
    return mesh("Plumbing", bm, coll, mats["plumbing"], sharp=40.0)


def build_led(coll, mats):
    bm = bmesh.new()
    bm_box(bm, (-LED_X, LED_Y0 + 0.0025, LED_Z0 - 0.0006), (LED_X, LED_Y1 - 0.0025, LED_Z0 + 0.002))
    ob = new_object("LEDStrip", bm, coll, material=mats["led"])
    shade(ob, 30.0)
    return ob


def build_body(coll, mats):
    parts = build_carcass(coll, mats) + build_top(coll, mats)
    parts += [build_basin(coll, mats), build_plumbing(coll, mats)]
    body = join(parts, "Vanity")
    tag(body, "body")
    tag(build_led(coll, mats), "body")
    return body


# ---------------------------------------------------------------------------
# Fixtures: mixer body + spout, pop-up drain (static, own atlas)
# ---------------------------------------------------------------------------
def build_fixture(coll, mats):
    r = MIXER_R
    z0 = TOP_Z1
    prof = [(0.0, z0), (0.0265, z0), (0.0272, z0 + 0.0008), (0.0275, z0 + 0.0025), (0.0275, z0 + 0.0050),
            (0.0268, z0 + 0.0062), (0.0250, z0 + 0.0068), (r + 0.0004, z0 + 0.0070), (r, z0 + 0.0080),
            (r, MIXER_TOP - 0.0020), (r - 0.0006, MIXER_TOP - 0.0005), (r - 0.0022, MIXER_TOP),
            (0.0165, MIXER_TOP), (0.0160, MIXER_TOP + 0.0006), (0.0160, CAP_TOP - 0.0012),
            (0.0154, CAP_TOP - 0.0003), (0.0142, CAP_TOP), (0.0, CAP_TOP)]
    bm = bmesh.new()
    curves.lathe(bm, prof, 40, center=(MIXER.x, MIXER.y, 0.0))
    mixer = mesh("Mixer", bm, coll, mats["mixer"], sharp=40.0)
    # Spout: rounded-rectangle section, flat beveled tip, aerator underneath
    bm = bmesh.new()
    prof2 = curves.rounded_rect_profile(0.026, 0.018, 0.0075, 3)
    curves.sweep(bm, [Vector((MIXER.x, MIXER.y - 0.012, SPOUT_Z)), Vector((MIXER.x, SPOUT_END, SPOUT_Z))],
                 prof2, up=(0.0, 0.0, 1.0))
    curves.lathe(bm, [(0.0, AERATOR.z - 0.0006), (0.0074, AERATOR.z - 0.0006), (0.0084, AERATOR.z - 0.0003),
                      (0.0088, AERATOR.z + 0.0004), (0.0088, AERATOR.z + 0.003)], 24,
                 center=(AERATOR.x, AERATOR.y, 0.0))
    spout = mesh("Spout", bm, coll, mats["spout"], 0.0016, 2, sharp=40.0, angle=50.0)
    # Pop-up drain: domed cap in a thin flange ring
    zd = DRAIN_Z
    bm = bmesh.new()
    curves.lathe(bm, [(0.0, zd + 0.0085), (0.010, zd + 0.0081), (0.019, zd + 0.0068), (0.026, zd + 0.0046),
                      (0.0300, zd + 0.0026), (0.0310, zd + 0.0012), (0.0310, zd + 0.0002), (0.0, zd + 0.0002)],
                 48, center=(BASIN_C.x, BASIN_C.y, 0.0))
    curves.lathe(bm, [(0.0318, zd - 0.0015), (0.0318, zd + 0.0016), (0.0340, zd + 0.0022), (0.0368, zd + 0.0018),
                      (0.0384, zd + 0.0008), (0.0388, zd - 0.0005)], 48, center=(BASIN_C.x, BASIN_C.y, 0.0))
    drain = mesh("Drain", bm, coll, mats["drain"], sharp=40.0)
    fixture = join([mixer, spout, drain], "VanityFixture")
    tag(fixture, "fixture")
    return fixture


# ---------------------------------------------------------------------------
# Lever (moving part: origin on its pivot)
# ---------------------------------------------------------------------------
def build_lever(coll, mats):
    p = LEVER_PIVOT
    bm = bmesh.new()
    bm_cyl(bm, 0.0065, 0.020, cyl_x(p), 24)
    knuckle = mesh("LeverKnuckle", bm, coll, mats["lever"], 0.0012, 2, sharp=40.0)
    tilt = math.radians(LEVER_TILT)
    d = Vector((0.0, -math.cos(tilt), math.sin(tilt)))
    path, scales = [], []
    for s, sc in ((0.0, (1.05, 1.0)), (0.03, (1.0, 0.95)), (0.07, (0.92, 0.88)), (LEVER_LEN - 0.006, (0.86, 0.84)),
                  (LEVER_LEN - 0.0025, (0.74, 0.70)), (LEVER_LEN - 0.0006, (0.50, 0.46)), (LEVER_LEN, (0.18, 0.2))):
        path.append(p + d * s)
        scales.append(sc)
    bm = bmesh.new()
    curves.sweep(bm, path, curves.rounded_rect_profile(0.016, 0.008, 0.0036, 3), up=(0.0, 0.0, 1.0), scales=scales)
    blade = mesh("LeverBlade", bm, coll, mats["lever"], sharp=45.0)
    lever = join([knuckle, blade], "Lever")
    reorigin(lever, p)
    tag(lever, "lever")
    tag(new_empty("HandleGripLever", coll, LEVER_GRIP_LOCAL, parent=lever, size=0.01), "lever")
    return lever


# ---------------------------------------------------------------------------
# Drawers (built in world coordinates at the closed position, then re-origined)
# ---------------------------------------------------------------------------
def edge_pull(name, origin, fh, coll, mat):
    """Slim gunmetal edge pull capping the front's top edge: a 10 mm lip down the
    face, the cap, and a rear lip the fingers hook behind from the channel."""
    z = origin.z + fh
    prof = [(-0.0015, -PULL_LIP), (-0.0015, -0.0006), (-0.0009, 0.0), (FRONT_T, 0.0),
            (FRONT_T, -PULL_T), (0.0, -PULL_T), (0.0, -PULL_LIP)]
    # sweep along +X: the profile's u runs along -Y, v along +Z
    prof = [(-y, v) for y, v in prof]
    bm = bmesh.new()
    curves.sweep(bm, [Vector((-FRONT_X, origin.y, z)), Vector((FRONT_X, origin.y, z))], prof, up=(0.0, 0.0, 1.0))
    # rear lip between the carcass sides (the fronts overlay the side edges)
    x = X_IN - 0.003
    bm_box(bm, (-x, origin.y + FRONT_T, z - PULL_BACK), (x, origin.y + FRONT_T + 0.0012, z - PULL_T + 0.0002))
    return mesh(name, bm, coll, mat, sharp=35.0)


def drawer_common(prefix, origin, fh, box_z0, box_z1, run_z, coll, mats, which):
    """Front, edge pull, side walls, runners. Returns (parts, local->world helpers)."""
    ox, oy, oz = origin

    def W(x, y, z):
        return (ox + x, oy + y, oz + z)

    wx, wy = mats[f"drawer_{which}_x"], mats[f"drawer_{which}_y"]
    parts = [
        box(f"{prefix}Front", W(-FRONT_X, 0.0, 0.0), W(FRONT_X, FRONT_T, fh - PULL_T), coll, wx),
        edge_pull(f"{prefix}Pull", origin, fh, coll, mats[f"pull_{which}"]),
    ]
    for s, n in ((-1, "L"), (1, "R")):
        xa, xb = sorted((s * (BOX_X - BOX_SIDE), s * BOX_X))
        parts.append(box(f"{prefix}Side{n}", W(xa, FRONT_T, box_z0), W(xb, BOX_BACK, box_z1), coll, wy))
    bm = bmesh.new()
    for s in (-1, 1):
        xa, xb = sorted((s * BOX_X, s * RUN_DRAWER_X1))
        bm_box(bm, W(xa, FRONT_T + 0.006, run_z), W(xb, BOX_BACK - 0.006, run_z + RUN_H))
    parts.append(mesh(f"{prefix}Runners", bm, coll, mats["runner"], 0.0008, 1))
    return parts, W


def build_drawer_top(coll, col_coll, mats):
    o, fh = TOP_DRAWER_ORIGIN, TOP_FH
    b = TOP_BOX
    z0, z1, low = b["z0"], b["z1"], b["low"]
    fz = z0 + BOX_FLOOR
    ix = BOX_X - BOX_SIDE
    dv, nt, nf = b["divider"], b["notch"], b["notch_front"]
    parts, W = drawer_common("Top", o, fh, z0, z1, TOP_RUN_Z, coll, mats, "top")
    wx, wy = mats["drawer_top_x"], mats["drawer_top_y"]
    back0 = BOX_BACK - BOX_SIDE
    # U-shaped floor: a strip in front of the drain notch and two arms beside it
    floors = [((-ix, FRONT_T, z0), (ix, nf - BOX_SIDE, fz))]
    for s in (-1, 1):
        xa, xb = sorted((s * (nt + BOX_SIDE), s * ix))
        floors.append(((xa, nf - BOX_SIDE, z0), (xb, back0, fz)))
    for i, (lo, hi) in enumerate(floors):
        parts.append(box(f"TopFloor{i}", W(*lo), W(*hi), coll, wx, bevel=0.0008, segs=1))
        liner_lo = (lo[0] + (0.001 if lo[0] > -ix + 1e-4 else 0.0), lo[1], fz)
        liner_hi = (hi[0] - (0.001 if hi[0] < ix - 1e-4 else 0.0), hi[1], fz + LINER_T)
        bm = bmesh.new()
        bm_box(bm, W(*liner_lo), W(*liner_hi))
        parts.append(mesh(f"TopLiner{i}", bm, coll, mats["felt"], sharp=30.0))
    for s, n in ((-1, "L"), (1, "R")):
        # back wall: tall behind the side compartment, low behind the shallow center tray
        xa, xb = sorted((s * dv, s * ix))
        parts.append(box(f"TopBack{n}", W(xa, back0, fz), W(xb, BOX_BACK, z1), coll, wx))
        xa, xb = sorted((s * (nt + BOX_SIDE), s * dv))
        parts.append(box(f"TopBackLow{n}", W(xa, back0, fz), W(xb, BOX_BACK, low), coll, wx))
        # divider between the tall side compartment and the center tray under the basin
        xa, xb = sorted((s * dv, s * (dv + BOX_SIDE)))
        parts.append(box(f"TopDivider{n}", W(xa, FRONT_T, fz), W(xb, back0, z1), coll, wy))
        # drain notch walls
        xa, xb = sorted((s * nt, s * (nt + BOX_SIDE)))
        parts.append(box(f"TopNotch{n}", W(xa, nf - BOX_SIDE, z0), W(xb, BOX_BACK, low), coll, wy))
    parts.append(box("TopNotchFront", W(-nt, nf - BOX_SIDE, z0), W(nt, nf, low), coll, wx))
    drawer = join(parts, "DrawerTop")
    reorigin(drawer, o)
    tag(drawer, "drawer_top")
    tag(new_empty("HandleGripDrawerTop", coll, (0.0, 0.010, fh - 0.006), parent=drawer, size=0.02), "drawer_top")

    def col(name, lo, hi):
        tag(collision_box(name, W(*lo), W(*hi), col_coll), "drawer_top_col")

    col("DTFront", (-FRONT_X, 0.0, 0.0), (FRONT_X, FRONT_T, fh))
    col("DTFloorFront", (-ix, FRONT_T, z0), (ix, nf - BOX_SIDE, fz + LINER_T))
    for s, n in ((-1, "L"), (1, "R")):
        lo_hi = lambda a, b: sorted((s * a, s * b))  # noqa: E731
        xa, xb = lo_hi(nt + BOX_SIDE, ix)
        col(f"DTFloor{n}", (xa, nf - BOX_SIDE, z0), (xb, back0, fz + LINER_T))
        xa, xb = lo_hi(ix, BOX_X)
        col(f"DTSide{n}", (xa, FRONT_T, z0), (xb, BOX_BACK, z1))
        xa, xb = lo_hi(dv, ix)
        col(f"DTBack{n}", (xa, back0, z0), (xb, BOX_BACK, z1))
        xa, xb = lo_hi(nt + BOX_SIDE, dv)
        col(f"DTBackLow{n}", (xa, back0, z0), (xb, BOX_BACK, low))
        xa, xb = lo_hi(dv, dv + BOX_SIDE)
        col(f"DTDivider{n}", (xa, FRONT_T, z0), (xb, back0, z1))
        xa, xb = lo_hi(nt, nt + BOX_SIDE)
        col(f"DTNotch{n}", (xa, nf - BOX_SIDE, z0), (xb, BOX_BACK, low))
    col("DTNotchFront", (-nt, nf - BOX_SIDE, z0), (nt, nf, low))
    return drawer


def build_drawer_bottom(coll, col_coll, mats):
    o, fh = BOTTOM_DRAWER_ORIGIN, BOTTOM_FH
    z0, z1 = BOTTOM_BOX["z0"], BOTTOM_BOX["z1"]
    fz = z0 + BOX_FLOOR
    ix = BOX_X - BOX_SIDE
    back0 = BOX_BACK - BOX_SIDE
    parts, W = drawer_common("Bottom", o, fh, z0, z1, BOTTOM_RUN_Z, coll, mats, "bottom")
    wx = mats["drawer_bottom_x"]
    parts.append(box("BottomFloor", W(-ix, FRONT_T, z0), W(ix, back0, fz), coll, wx, bevel=0.0008, segs=1))
    parts.append(box("BottomBack", W(-ix, back0, fz), W(ix, BOX_BACK, z1), coll, wx))
    bm = bmesh.new()
    bm_box(bm, W(-ix, FRONT_T, fz), W(ix, back0, fz + LINER_T))
    parts.append(mesh("BottomLiner", bm, coll, mats["felt"], sharp=30.0))
    drawer = join(parts, "DrawerBottom")
    reorigin(drawer, o)
    tag(drawer, "drawer_bottom")
    tag(new_empty("HandleGripDrawerBottom", coll, (0.0, 0.010, fh - 0.006), parent=drawer, size=0.02), "drawer_bottom")

    def col(name, lo, hi):
        tag(collision_box(name, W(*lo), W(*hi), col_coll), "drawer_bottom_col")

    col("DBFront", (-FRONT_X, 0.0, 0.0), (FRONT_X, FRONT_T, fh))
    col("DBFloor", (-ix, FRONT_T, z0), (ix, back0, fz + LINER_T))
    col("DBSideL", (-BOX_X, FRONT_T, z0), (-ix, BOX_BACK, z1))
    col("DBSideR", (ix, FRONT_T, z0), (BOX_X, BOX_BACK, z1))
    col("DBBack", (-ix, back0, z0), (ix, BOX_BACK, z1))
    return drawer


# ---------------------------------------------------------------------------
# Soap dispenser (pickable; origin at its bottom center)
# ---------------------------------------------------------------------------
def build_dispenser(coll, mats):
    p = DISPENSER_POS
    c = (p.x, p.y, 0.0)
    z = p.z
    body = [(0.0, 0.0012), (0.0280, 0.0012), (0.0300, 0.0), (0.0335, 0.0004), (0.0352, 0.0025), (0.0359, 0.006),
            (0.0360, 0.012), (0.0360, 0.118), (0.0355, 0.127), (0.0338, 0.135), (0.0305, 0.1415), (0.0258, 0.1465),
            (0.0205, 0.1497), (0.0158, 0.1512), (0.0150, 0.1530), (0.0, 0.1530)]
    bm = bmesh.new()
    curves.lathe(bm, [(r, z + h) for r, h in body], 40, center=c)
    bottle = mesh("DispenserBottle", bm, coll, mats["ceramic"], sharp=40.0)
    pump = [(0.0, 0.1520), (0.0172, 0.1520), (0.0179, 0.1532), (0.0180, 0.1645), (0.0173, 0.1662),
            (0.0150, 0.1668), (0.0060, 0.1672), (0.0046, 0.1680), (0.0046, 0.1775), (0.0128, 0.1778),
            (0.0140, 0.1788), (0.0144, 0.1805), (0.0144, 0.1905), (0.0139, 0.1935), (0.0124, 0.1953),
            (0.0080, 0.1960), (0.0, 0.1961)]
    bm = bmesh.new()
    curves.lathe(bm, [(r, z + h) for r, h in pump], 32, center=c)
    path = [Vector((p.x, p.y - 0.010, z + 0.1872)), Vector((p.x, p.y - 0.027, z + 0.1872)),
            Vector((p.x, p.y - 0.034, z + 0.1862)), Vector((p.x, p.y - 0.0375, z + 0.1840))]
    curves.tube(bm, path, 0.0042, 14, along_attr=None, around_attrs=None)
    pump_ob = mesh("DispenserPump", bm, coll, mats["pump"], sharp=40.0)
    disp = join([bottle, pump_ob], "SoapDispenser")
    reorigin(disp, p)
    tag(disp, "dispenser")
    return disp


# ---------------------------------------------------------------------------
# Body collision: hollow carcass, top around the cutout, upstand, mixer, basin hulls
# ---------------------------------------------------------------------------
def build_collision(col_coll):
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColSideL", (-X_OUT, CASE_FRONT, CASE_Z0), (-X_IN, 0.0, TOP_Z0))
    col("ColSideR", (X_IN, CASE_FRONT, CASE_Z0), (X_OUT, 0.0, TOP_Z0))
    col("ColBack", (-X_IN, BACK_Y0, CASE_Z0), (X_IN, 0.0, TOP_Z0))
    col("ColBottom", (-X_IN, CASE_FRONT, CASE_Z0), (X_IN, BACK_Y0, BOTTOM_Z1))
    cy0, cy1 = BASIN_C.y - CUT_H / 2, BASIN_C.y + CUT_H / 2
    cx0, cx1 = BASIN_C.x - CUT_W / 2, BASIN_C.x + CUT_W / 2
    col("ColTopFront", (-HX, TOP_FRONT, TOP_Z0), (HX, cy0, TOP_Z1))
    col("ColTopBack", (-HX, cy1, TOP_Z0), (HX, -SPLASH_T, TOP_Z1))
    col("ColTopLeft", (-HX, cy0, TOP_Z0), (cx0, cy1, TOP_Z1))
    col("ColTopRight", (cx1, cy0, TOP_Z0), (HX, cy1, TOP_Z1))
    col("ColUpstand", (-HX, -SPLASH_T, TOP_Z0), (HX, 0.0, SPLASH_Z1))
    col("ColMixer", (MIXER.x - MIXER_R, MIXER.y - MIXER_R, TOP_Z1), (MIXER.x + MIXER_R, MIXER.y + MIXER_R, CAP_TOP))
    col("ColSpout", (MIXER.x - 0.013, SPOUT_END, SPOUT_Z - 0.009), (MIXER.x + 0.013, MIXER.y - MIXER_R, SPOUT_Z + 0.009))
    # Basin: convex slabs following the bowl (4 bands x 8 sectors: straight sides and
    # corners), so a can slides down the walls into the bowl; a flat floor at the drain.
    rings = list(BOWL_RINGS)
    outer = offset_rings(rings, 0.015)
    k = CORNER_SEGS + 1
    n = 4 * k
    sectors = []
    for cidx in range(4):
        sectors.append(list(range(cidx * k, cidx * k + k)))                 # corner arc
        sectors.append([cidx * k + k - 1, ((cidx + 1) * k) % n])            # straight side
    for bi, (i, j) in enumerate(((0, 2), (2, 3), (3, 4), (4, 5))):
        li, lj = ring_loop(rings[i]), ring_loop(rings[j])
        oi, oj = ring_loop(outer[i]), ring_loop(outer[j])
        for si, idx in enumerate(sectors):
            pts = [lp[q] for lp in (li, lj, oi, oj) for q in idx]
            tag(convex_collider(f"ColBowl{bi}{si}", pts, col_coll), "body_col")
    z5, w5, d5, _ = rings[5]
    col("ColBowlFloor", (BASIN_C.x - w5 / 2, BASIN_C.y - d5 / 2, DRAIN_Z - 0.012),
        (BASIN_C.x + w5 / 2, BASIN_C.y + d5 / 2, DRAIN_Z + 0.007))


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("VanityBody"), mats)
    build_fixture(get_collection("VanityFixture"), mats)
    build_lever(get_collection("VanityLever"), mats)
    dcol = get_collection("DrawerCollisionReference")
    build_drawer_top(get_collection("VanityDrawerTop"), dcol, mats)
    build_drawer_bottom(get_collection("VanityDrawerBottom"), dcol, mats)
    build_dispenser(get_collection("SoapDispenser"), mats)
    build_collision(get_collection("VanityCollision"))
    dcol.hide_render = True
    tris = {p: part_tris(p) for p in ("body", "fixture", "lever", "drawer_top", "drawer_bottom", "dispenser",
                                      "body_col")}
    total = sum(v for k, v in tris.items() if k not in ("body_col", "dispenser"))
    print("TRIS " + " ".join(f"{k}={v}" for k, v in tris.items()) + f" vanity_total={total}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
