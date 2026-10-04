"""Stage 1: build the five brutalist towers (geometry with UVs into the shared
texture layouts, placeholder materials named as in Godot), save the .blend.

  blender -b --factory-startup --python blender/architecture/city/brutalist/build.py

Every tower is built at the origin (base center on the street, front -Y), so
the five overlap in the .blend; render.py places them per the JSON for the
night view. Each tower = one mesh `<name>` plus `<name>_blink` (pad and
aircraft warning lights that Godot may animate), tagged with the tower name.

Detail goes where the apartment sees it: fronts and the eye-side faces get
balconies, pods, signs; backs are ribbon facades; roofs below eye level
(deck, stacked's setbacks, terrace steps, ziggurat tiers) get plant and
planting; the lowest floors are a plain podium (dark and fogged in Godot).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from brutalist_common import BLEND, FH, MATERIALS, towers  # noqa: E402
from brutalist_kit import EDGES, Tower  # noqa: E402
from brutalist_textures import concrete_sheet, decal_rect, lit_cells, metal_sheet, window_plan  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag  # noqa: E402

BAL3 = dict(style="balcony", run_bays=3)
BAL2 = dict(style="balcony", run_bays=2)
BAL4 = dict(style="balcony", run_bays=4)
RIB = dict(style="ribbon")
SLOT = dict(style="blank", slot=True)
BLANK = dict(style="blank")
BLADE = (4.0, 4.0 * 16.0 / 3.0)        # flat vertical sign on a pier (atlas blades are 3 x 16)
BLADE_FAR = (5.0, 5.0 * 16.0 / 3.0)    # the same for towers 300+ m away
SMALL = (14.0, 6.0)                    # small signs (atlas 7 x 3) at twice the size


def z_ref_for(height):
    """Ground floor height so the top floor ends at the roof slab (4.0-7.2 m)."""
    n = math.floor((height - 4.0) / FH)
    return height - n * FH


def grid(T, k):
    return T.z_ref + k * FH


def cp_of(length, run_bays):
    return Tower.layout(length, 4.0, run_bays)[0]


def with_(base, **kw):
    d = dict(base)
    d.update(kw)
    return d


def podium(T, W, D, top, parapet=False):
    faces = {e: dict(style="ribbon", band="wall_c") for e in EDGES}
    return T.block(-W / 2, W / 2, -D / 2, D / 2, 0.0, top, faces, parapet=parapet)


def front_sign(T, x, y_face, zc, rect, size, depth=0.45):
    """Flat sign facing -Y (front) on a pier at x, its face 0.5 m in front of y_face."""
    T.sign_panel((x, y_face - 0.5, zc), (1, 0, 0), size[0], size[1], rect, depth=depth, mount=0.05)


def standing_sign(T, x, y, z_base, rect, size, legs=2):
    """Sign standing on a roof edge on steel legs, facing -Y."""
    zc = z_base + 1.6 + size[1] / 2
    T.sign_panel((x, y, zc), (1, 0, 0), size[0], size[1], rect, depth=0.45)
    for k in range(legs):
        dx = (k / max(legs - 1, 1) - 0.5) * size[0] * 0.7
        T.m.tube([Vector((x + dx, y + 0.25, z_base)), Vector((x + dx, y + 0.25, zc - size[1] / 2))], 0.18, T.M,
                 "dark", 4)


def terrace_planting(T, rect, edges=("front",), shrubs=0, hvac=0, tanks=0, depth_max=5.0):
    """Hedges along the parapet of a roof terrace, a few shrubs and plant."""
    x0, x1, y0, y1, z = rect
    for e in edges:
        if e == "front":
            T.hedge(Vector((x0 + 0.5, y0 + 0.1, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), x1 - x0 - 1.0, z, 1.0, 0.9)
        elif e == "left":
            T.hedge(Vector((x0 + 0.1, y1 - 0.5, 0)), Vector((0, -1, 0)), Vector((1, 0, 0)), y1 - y0 - 1.0, z, 1.0,
                    0.9)
        elif e == "right":
            T.hedge(Vector((x1 - 0.1, y0 + 0.5, 0)), Vector((0, 1, 0)), Vector((-1, 0, 0)), y1 - y0 - 1.0, z, 1.0,
                    0.9)
    for _ in range(shrubs):
        x = T.rng.uniform(x0 + 2.5, x1 - 2.5)
        lo = y0 + 1.6
        y = T.rng.uniform(lo, max(lo + 0.1, min(y1 - 1.5, y0 + depth_max)))
        T.shrub(x, y, z, T.rng.uniform(1.2, 2.2), T.rng.uniform(2.5, 5.0))
    for _ in range(hvac):
        x = T.rng.uniform(x0 + 4, x1 - 4)
        y = (y0 + y1) / 2 + T.rng.uniform(-1, 1)
        T.hvac(x, y, z, 4.0, 2.4, 1.8, fans=2)
    for _ in range(tanks):
        T.tank(T.rng.uniform(x0 + 3, x1 - 3), y1 - 3.0, z, 1.6, 2.8, legs=1.5, band="panel")


def lamp_post(T, x, y, z, h, color, r=3.2):
    """A steel pole with a lamp head and its pool of light on the roof."""
    T.m.tube([Vector((x, y, z)), Vector((x, y, z + h))], 0.1, T.M, "dark", 4)
    T.light(Vector((x, y, z + h + 0.15)), 0.5, color, blink=False)
    T.pool(Vector((x, y, z + 0.03)), r, color)


def core(T, x0, x1, y0, y1, z0, z1, slot_edge=None):
    """A concrete service shaft (stairs, lifts): blank, one slot window column."""
    faces = {e: (SLOT if e == slot_edge else BLANK) for e in EDGES}
    return T.block(x0, x1, y0, y1, z0, z1, faces, roof_band="top")


def link(T, x0, x1, y0, y1, z0):
    """A one-floor glazed link between two volumes (along X)."""
    T.bridge(x0, x1, y0, y1, z0, z0 + FH, truss=False)


# =============================================================================================
def build_deck(T, t):
    """64 x 44 m, roof at 145 m (35 m below the window): the roof is the hero."""
    W, D, H = t["W"], t["D"], t["height"]
    top_p = grid(T, 1)
    podium(T, W, D, top_p)
    mech = [grid(T, 22)]
    roof = T.block(-W / 2, W / 2, -D / 2, D / 2, top_p, H,
                   {"front": with_(BAL3, mech=mech), "right": with_(BAL2, mech=mech), "back": with_(RIB, mech=mech),
                    "left": with_(SLOT, mech=mech)})
    x0, x1, y0, y1, z = roof
    # stair and lift core at the back right, rising above the roof
    core(T, 17.0, 27.0, 11.5, 21.5, 0.0, H + 7.0, slot_edge="right")
    T.mast(24.0, 18.0, H + 7.0, 16.0, dishes=2)
    # cantilevered pods on the front
    fa, fb = (-W / 2, -D / 2), (W / 2, -D / 2)
    cp = cp_of(W, 3)
    T.pod(fa, fb, cp + 9.45, 3, grid(T, 27), 2)
    T.pod(fa, fb, cp + 3 * 9.45, 3, grid(T, 11), 3)
    # landing pad (front-left) with a parked aircar and a control booth
    T.landing_pad(-15.0, -4.0, z, size=22.0, height=1.8, lights=12)
    T.aircar(-12.5, -2.0, z + 1.8, math.radians(25.0))
    T.penthouse(-28.0, -23.0, 11.0, 17.0, z, 3.2, door_side="right", lit_cell=T.cells_cold[0])
    T.m.box((-23.0, 12.5, z), (-20.5, 15.5, z + 1.2), T.M, "panel", top="grating", strip=3.2, z_ref=z)
    # lift motor room / stair house with a lit door
    T.penthouse(2.0, 12.0, 6.0, 15.0, z, 4.6, door_side="front", lit_cell=T.cells_warm[0])
    # plant: HVAC row, cooling tower, tanks, pipes, a dish
    for yy in (-13.0, -5.5, 2.0):
        T.hvac(23.0, yy, z, 3.4, 6.2, 2.2, fans=2, along_x=False)
    T.m.cylinder((6.0, -12.0), 2.8, z, z + 2.4, T.M, "louver", segs=14)
    T.m.cylinder((6.0, -12.0), 2.8, z + 2.4, z + 2.9, T.M, "panel", segs=14, top_uv=T.fan_uv)
    T.tank(14.0, -15.5, z, 1.6, 2.6, band="panel")
    T.tank(28.0, 9.0, z, 1.5, 2.4)
    T.pipe([(19.6, -9.0, z + 1.2), (16.5, -9.0, z + 1.2), (16.5, 9.0, z + 1.2), (12.2, 9.0, z + 1.2)], 0.32)
    T.pipe([(19.6, 0.0, z + 0.9), (15.0, 0.0, z + 0.9), (15.0, -14.0, z + 0.9), (12.0, -14.0, z + 0.9)], 0.25, "panel")
    T.dish(Vector((-4.0, 16.0, z + 1.6)), Vector((-0.5, -0.6, 0.6)), 1.4)
    T.m.box((-4.3, 15.7, z), (-3.7, 16.3, z + 1.2), T.M, "dark", strip=1.0, z_ref=z)
    # solar array tilted toward the front (catches the sky and the signs as reflections)
    for row, yy in enumerate((-8.0, -4.6)):
        for i in range(4):
            xx = -1.0 + i * 2.7
            a, b = Vector((xx - 1.25, yy - 0.6, z + 0.5)), Vector((xx + 1.25, yy - 0.6, z + 0.5))
            c, d = b + Vector((0, 1.2, 0.75)), a + Vector((0, 1.2, 0.75))
            T.m.band_face([a, b, c, d], T.M, "dark", (1, 0, 0), (0, -0.53, 0.85), stretch=True)
            T.m.band_face([b, a, d, c], T.M, "panel", (-1, 0, 0), (0, 0.53, -0.85), stretch=True)
            T.m.box((xx - 0.1, yy + 0.4, z), (xx + 0.1, yy + 0.6, z + 1.2), T.M, "dark", strip=1.0, z_ref=z)
    # grating walkway from the pad to the lift room door
    T.m.box((-4.5, 2.0, z), (6.5, 3.4, z + 0.3), T.M, "dark", top="grating", strip=1.0, z_ref=z)
    T.m.box((5.1, 3.4, z), (6.5, 6.0, z + 0.3), T.M, "dark", top="grating", strip=1.0, z_ref=z)
    # roof garden strip along the back parapet
    T.hedge(Vector((-17.0, y1 - 0.2, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)), 14.0, z, 1.2, 0.8)
    for sx in (-14.0, -9.0):
        T.shrub(sx, y1 - 2.4, z, 1.4, 3.0)
    # warm skylights over the top floor (lit window cells)
    for i, (sx, sy) in enumerate(((-6.0, 11.0), (-1.0, 11.0), (-6.0, 4.5))):
        T.m.box((sx - 1.6, sy - 1.1, z), (sx + 1.6, sy + 1.1, z + 0.45), T.M, "dark", strip=1.0, z_ref=z)
        p = Vector((sx - 1.5, sy - 1.0, z + 0.47))
        T.window_cell_quad([p, p + Vector((3.0, 0, 0)), p + Vector((3.0, 2.0, 0)), p + Vector((0, 2.0, 0))],
                           T.cells_warm[1 + i], Vector((0, 0, 1)))
    # roof-edge sign hanging off the front fascia, facing the apartment (the roof stays open)
    T.sign_panel((12.0, -D / 2 - 0.9, H - 2.4), (1, 0, 0), 30.0, 5.625, "roof_sign", depth=0.5, mount=0.4)
    # vertical sign on the front-left pier
    front_sign(T, -W / 2 + cp / 2, -D / 2, grid(T, 37), "blade_1", BLADE)
    # maintenance lights on poles: pools of light between the plant
    for (lx, ly, col) in ((19.5, -9.2, "coolwhite"), (8.5, -16.0, "warmwhite"), (19.0, 11.5, "warmwhite"),
                          (-24.0, 6.0, "amber")):
        lamp_post(T, lx, ly, z, 3.2, col)


def build_stacked(T, t):
    """90 x 36 m, roof at 225 m: three stacked slabs, galleries on the front."""
    W, D, H = t["W"], t["D"], t["height"]
    top_p = grid(T, 1)
    podium(T, W, D, top_p)
    zA, zB = grid(T, 32), grid(T, 50)
    gal_A = [grid(T, k) for k in (8, 16, 24)]
    gal_B = [grid(T, 41)]
    mechA = [grid(T, 12), grid(T, 28)]
    mechB = [grid(T, 46)]
    roofA = T.block(-45.0, 45.0, -18.0, 18.0, top_p, zA,
                    {"front": with_(BAL4, skip_floors=gal_A, mech=mechA), "right": with_(SLOT, mech=mechA),
                     "back": with_(RIB, mech=mechA), "left": with_(SLOT, mech=mechA)})
    for k, zf in enumerate(gal_A):
        T.gallery((-45.0, -18.0), (45.0, -18.0), zf, light="amber" if k == 1 else "coolwhite")
    roofB = T.block(-40.0, 40.0, -12.0, 18.0, zA, zB,
                    {"front": with_(BAL3, skip_floors=gal_B, mech=mechB), "right": with_(BAL2, mech=mechB),
                     "back": with_(RIB, mech=mechB), "left": BLANK})
    for zf in gal_B:
        T.gallery((-40.0, -12.0), (40.0, -12.0), zf, light="cyan")
    roofC = T.block(-34.0, 26.0, -6.0, 18.0, zB, H,
                    {"front": BAL2, "right": RIB, "back": RIB, "left": SLOT})
    # pods on A's front
    fa, fb = (-45.0, -18.0), (45.0, -18.0)
    cpA = cp_of(90.0, 4)
    T.pod(fa, fb, cpA + 1 * 12.45, 4, grid(T, 18), 3)
    T.pod(fa, fb, cpA + 4 * 12.45, 4, grid(T, 3), 3)
    T.pod(fa, fb, cpA + 2 * 12.45, 3, grid(T, 25), 2)
    # lift shaft on the right, free above B, linked to C
    core(T, 38.5, 44.5, -3.0, 7.0, 0.0, H + 8.0, slot_edge="right")
    for k in (55, 63):
        link(T, 26.0, 38.5, 0.0, 4.0, grid(T, k))
    T.mast(41.5, 2.0, H + 8.0, 14.0, dishes=1)
    # setback terraces
    terrace_planting(T, (roofA[0], roofA[1], roofA[2], -12.0, roofA[4]), ("front",), shrubs=7)
    T.hvac(-36.0, 0.0, roofA[4], 3.0, 7.0, 2.2, fans=2, along_x=False)
    terrace_planting(T, (roofB[0], roofB[1], roofB[2], -6.0, roofB[4]), ("front",), shrubs=4)
    T.hvac(34.0, 4.0, roofB[4], 3.0, 8.0, 2.2, fans=2, along_x=False)
    T.tank(-30.0, 10.0, roofB[4], 1.8, 3.0)
    # top roof
    x0, x1, y0, y1, z = roofC
    T.penthouse(-22.0, -10.0, 6.0, 15.0, z, 5.0, lit_cell=T.cells_warm[2])
    T.mast(-15.0, 11.0, z + 5.0, 22.0, dishes=2)
    for xx in (2.0, 9.0, 16.0):
        T.hvac(xx, -0.5, z, 4.6, 3.0, 2.2, fans=2)
    T.tank(18.0, 12.0, z, 2.0, 3.0)
    T.tank(5.0, 12.5, z, 1.6, 2.6, band="panel")
    T.pipe([(9.0, 1.1, z + 1.0), (9.0, 6.0, z + 1.0), (-10.0, 6.0, z + 1.0)], 0.3)
    lamp_post(T, -4.0, 2.0, z, 3.0, "warmwhite")
    lamp_post(T, -28.0, -12.0, roofA[4], 3.0, "warmwhite")
    lamp_post(T, 10.0, -8.0, roofB[4], 3.0, "coolwhite")
    # signs: flat verticals on A's front-right and B's front-left piers, one on A's right face,
    # RAMEN standing on A's terrace edge
    front_sign(T, 45.0 - cpA / 2, -18.0, grid(T, 22), "blade_0", BLADE)
    cpB = cp_of(80.0, 3)
    front_sign(T, -40.0 + cpB / 2, -12.0, grid(T, 43), "blade_3", BLADE)
    T.sign_panel((45.0 + 0.55, -12.0, grid(T, 14)), (0, 1, 0), BLADE[0], BLADE[1], "blade_5", depth=0.45)
    standing_sign(T, -22.0, -16.4, zA, "small_0", SMALL)


def build_terrace(T, t):
    """72 x 38 m, roof at 195 m: front steps back toward the top, planted."""
    W, D, H = t["W"], t["D"], t["height"]
    top_p = grid(T, 1)
    podium(T, W, D, top_p)
    zA = grid(T, 40)
    x0, x1 = -W / 2, W / 2
    yb = D / 2
    mech = [grid(T, 14), grid(T, 29)]
    roof = T.block(x0, x1, -D / 2, yb, top_p, zA,
                   {"front": with_(BAL3, plants=0.1, mech=mech), "left": with_(BAL2, plants=0.08, mech=mech),
                    "back": with_(RIB, mech=mech), "right": with_(SLOT, mech=mech)})
    rects = [roof]
    steps = [(3, -D / 2 + 3.8), (3, -D / 2 + 7.6), (3, -D / 2 + 11.4), (3, -D / 2 + 15.2), (3, -D / 2 + 19.0),
             (4, -D / 2 + 22.8)]
    z = zA
    for nfl, y0 in steps:
        z1 = z + nfl * FH
        r = T.block(x0, x1, y0, yb, z, z1,
                    {"front": dict(BAL3, plants=0.45), "left": dict(BAL2, plants=0.25), "back": RIB, "right": SLOT})
        rects.append(r)
        z = z1
    # planted terraces: hedge on every step's front parapet, shrubs between
    for (r, nxt) in zip(rects[:-1], steps):
        terrace_planting(T, (r[0], r[1], r[2], nxt[1] - 0.2, r[4]), ("front",), shrubs=5)
    # roof (just above eye level): a core, plant, a mast, a sign standing on the front edge
    x0r, x1r, y0r, y1r, zr = rects[-1]
    core(T, -36.0, -28.0, 10.0, 19.0, zr - 2 * FH, zr + 8.0, slot_edge="left")
    T.penthouse(-6.0, 6.0, 9.0, 16.0, zr, 4.6, lit_cell=T.cells_warm[3])
    T.mast(3.5, 12.5, zr + 4.6, 14.0, dishes=1)
    for xx in (-19.0, 18.0, 25.0):
        T.hvac(xx, 12.0, zr, 4.4, 3.0, 2.2, fans=2)
    T.tank(31.0, 8.0, zr, 1.8, 3.0)
    lamp_post(T, 12.0, 8.0, zr, 3.0, "warmwhite")
    standing_sign(T, -12.0, y0r + 0.8, zr, "small_2", SMALL)
    # facade signs toward the apartment (front-left)
    cpF = cp_of(W, 3)
    front_sign(T, x0 + cpF / 2, -D / 2, grid(T, 26), "blade_2", BLADE)
    cpL = cp_of(D, 2)
    T.sign_panel((x0 - 0.55, -D / 2 + cpL / 2, grid(T, 9)), (0, -1, 0), cpL - 0.6, (cpL - 0.6) * 3 / 7, "small_3",
                 depth=0.45)


def build_bridge(T, t):
    """110 x 42 m: two slabs (275 / 249 m) joined by a sky bridge at eye level."""
    W, D, H = t["W"], t["D"], t["height"]
    top_p = grid(T, 3)
    podium(T, W, D, top_p, parapet=True)
    hR = grid(T, 76)
    mech = [grid(T, 30), grid(T, 66)]
    roofL = T.block(-55.0, -17.0, -D / 2, D / 2, top_p, H,
                    {"front": with_(BAL3, skip_floors=[grid(T, 50)], mech=mech), "right": with_(BAL2, mech=mech),
                     "back": with_(RIB, mech=mech), "left": with_(SLOT, mech=mech)})
    roofR = T.block(17.0, 55.0, -D / 2, D / 2, top_p, hR,
                    {"front": with_(BAL3, mech=mech), "left": with_(BAL2, mech=mech), "back": with_(RIB, mech=mech),
                     "right": with_(SLOT, mech=mech)})
    T.gallery((-55.0, -D / 2), (-17.0, -D / 2), grid(T, 50), light="amber")
    # sky bridge at eye level (Godot y = 0..15) and a lower link
    T.bridge(-17.0, 17.0, -8.0, 8.0, grid(T, 54), grid(T, 59))
    T.bridge(-17.0, 17.0, -3.0, 3.0, grid(T, 35), grid(T, 36), truss=False)
    T.sign_panel((0.0, -8.0 - 1.0, grid(T, 54) - 3.4), (1, 0, 0), 12.0, 12.0 * 3 / 7, "small_6", depth=0.4,
                 mount=0.4)
    # pods
    fa, fb = (-55.0, -D / 2), (-17.0, -D / 2)
    cpF = cp_of(38.0, 3)
    T.pod(fa, fb, cpF + 9.45, 3, grid(T, 20), 3)
    T.pod((17.0, -D / 2), (55.0, -D / 2), cpF, 3, grid(T, 44), 2)
    # left roof: plant and masts
    x0, x1, y0, y1, z = roofL
    T.penthouse(-48.0, -38.0, 4.0, 14.0, z, 5.0, lit_cell=T.cells_cold[1])
    T.mast(-43.0, 9.0, z + 5.0, 26.0, dishes=3)
    T.mast(-25.0, 14.0, z, 12.0, r=0.25, dishes=0)
    for yy in (-12.0, -4.0):
        T.hvac(-27.0, yy, z, 6.0, 3.2, 2.2, fans=2)
    T.tank(-48.0, -12.0, z, 2.2, 3.0)
    lamp_post(T, -36.0, -8.0, z, 3.0, "coolwhite")
    # right roof: billboard facing the apartment, plant, a small pad
    x0, x1, y0, y1, z = roofR
    T.sign_panel((36.0, y0 + 2.0, z + 3.0 + 5.0), (1, 0, 0), 20.0, 10.0, "billboard", depth=0.6)
    for dx in (-7.0, 0.0, 7.0):
        T.m.box((36.0 + dx - 0.25, y0 + 2.2, z), (36.0 + dx + 0.25, y0 + 2.9, z + 3.2), T.M, "dark", strip=1.0,
                z_ref=z)
    T.landing_pad(40.0, 9.0, z, size=14.0, height=1.2, lights=8)
    T.hvac(23.0, 10.0, z, 3.2, 6.0, 2.2, fans=2, along_x=False)
    T.mast(51.0, 16.0, z, 10.0, r=0.25, dishes=0)
    # flat verticals on the inner front piers
    front_sign(T, -17.0 - cpF / 2, -D / 2, grid(T, 40), "blade_4", BLADE_FAR)
    front_sign(T, 17.0 + cpF / 2, -D / 2, grid(T, 64), "blade_0", BLADE_FAR)


def build_ziggurat(T, t):
    """96 x 48 m, roof at 250 m: five tiers stepping back more on the front."""
    W, D, H = t["W"], t["D"], t["height"]
    top_p = grid(T, 1)
    podium(T, W, D, top_p)
    tiers = [(16, 0.0, 0.0, 0.0), (14, 6.0, 5.0, 1.0), (17, 11.0, 10.0, 3.0), (13, 17.0, 15.0, 5.0),
             (15, 23.0, 19.0, 7.0)]
    z = top_p
    k = 1
    rects, outlines = [], []
    for i, (nfl, ix, fy, by) in enumerate(tiers):
        x0, x1, y0, y1 = -W / 2 + ix, W / 2 - ix, -D / 2 + fy, D / 2 - by
        z1 = z + nfl * FH
        mech = [grid(T, k + nfl // 2)] if nfl >= 14 else []
        faces = {"front": with_(BAL3, plants=0.06 * i, mech=mech), "right": with_(BAL2, plants=0.05 * i, mech=mech),
                 "back": with_(RIB, mech=mech), "left": with_(RIB, mech=mech)}
        rects.append(T.block(x0, x1, y0, y1, z, z1, faces))
        outlines.append((x0, x1, y0, y1, z, z1))
        z, k = z1, k + nfl
    for i, r in enumerate(rects[:-1]):
        nx0, nx1, ny0, ny1 = outlines[i + 1][:4]
        x0, x1, y0, y1, zz = r
        T.hedge(Vector((x0 + 0.5, y0 + 0.1, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), x1 - x0 - 1.0, zz, 1.0, 0.9)
        T.hedge(Vector((x1 - 0.1, y0 + 0.5, 0)), Vector((0, 1, 0)), Vector((-1, 0, 0)), y1 - y0 - 1.0, zz, 1.0, 0.9)
        if ny0 - y0 > 4.0:
            for _ in range(3):
                T.shrub(T.rng.uniform(x0 + 3, x1 - 3), (y0 + ny0) / 2, zz, T.rng.uniform(1.0, 1.8), 3.0)
        if x1 - nx1 > 3.0:
            T.hvac((x1 + nx1) / 2, T.rng.uniform(ny0 + 4, ny1 - 4), zz, 2.4, 4.0, 1.8, fans=1, along_x=False)
    # pods on the front of tiers 0 and 2
    for (ti, run, kk, nfl) in ((0, 2, 6, 3), (0, 6, 12, 2), (2, 1, 40, 3)):
        x0, x1, y0, y1, za, zb = outlines[ti]
        cp = cp_of(x1 - x0, 3)
        T.pod((x0, y0), (x1, y0), cp + run * 9.45, 3, grid(T, kk), nfl)
    # service shaft on the right side (toward the apartment)
    x0, x1, y0, y1, za, zb = outlines[2]
    core(T, W / 2 - 12.0, W / 2 - 0.5, -6.0, 6.0, 0.0, zb + 6.0, slot_edge="right")
    T.sign_panel((W / 2 - 0.5 + 0.55, 0.0, grid(T, 34)), (0, 1, 0), BLADE_FAR[0], BLADE_FAR[1], "blade_3", depth=0.45)
    # crown
    x0, x1, y0, y1, zz = rects[-1]
    T.penthouse(-10.0, 10.0, 0.0, 12.0, zz, 6.4, lit_cell=T.cells_warm[4])
    T.mast(0.0, 6.0, zz + 6.4, 30.0, r=0.5, dishes=3)
    for sx in (-19.0, 19.0):
        T.hvac(sx, 4.0, zz, 3.2, 8.0, 2.2, fans=2, along_x=False)
    T.tank(-19.0, 13.0, zz, 1.6, 2.6)
    T.tank(19.0, 13.0, zz, 1.6, 2.6)
    # signs: a vertical on the right face of tier 1, a pharmacy cross and glyphs on the front
    x0, x1, y0, y1, za, zb = outlines[1]
    cpR = cp_of(y1 - y0, 2)
    T.sign_panel((x1 + 0.55, y0 + cpR / 2, grid(T, 23)), (0, 1, 0), BLADE_FAR[0], BLADE_FAR[1], "blade_5",
                 depth=0.45)
    x0, x1, y0, y1, za, zb = outlines[0]
    cp0 = cp_of(x1 - x0, 3)
    T.sign_panel((x0 + cp0 / 2, y0 - 0.55, grid(T, 9)), (1, 0, 0), cp0 - 1.0, cp0 - 1.0, "small_4", depth=0.45)
    x0, x1, y0, y1, za, zb = outlines[3]
    standing_sign(T, 6.0, y0 + 1.0, za, "small_5", SMALL)


BUILDERS = {"city_brutal_stacked": build_stacked, "city_brutal_deck": build_deck,
            "city_brutal_terrace": build_terrace, "city_brutal_bridge": build_bridge,
            "city_brutal_ziggurat": build_ziggurat}


def placeholder_materials():
    out = {}
    colors = {MATERIALS[0]: (0.1, 0.1, 0.11, 1), MATERIALS[1]: (0.02, 0.02, 0.03, 1),
              MATERIALS[2]: (0.03, 0.035, 0.04, 1), MATERIALS[3]: (0.5, 0.05, 0.3, 1)}
    for name in MATERIALS:
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = colors[name]
        out[name] = m
    return out


def main():
    clear_scene()
    mats = placeholder_materials()
    conc, metal = concrete_sheet(), metal_sheet()
    plan = window_plan()
    warm, cold = lit_cells(plan, warm=True), lit_cells(plan, warm=False)
    for i, t in enumerate(towers()):
        name = t["name"]
        T = Tower(name, conc, metal, plan, seed=100 + 17 * i, z_ref=z_ref_for(t["height"]))
        T.M = MATERIALS[2]
        T.cells_warm = [warm[(7 * i + k * 13) % len(warm)] for k in range(8)]
        T.cells_cold = [cold[(5 * i + k * 7) % len(cold)] for k in range(4)]
        T.fan_uv = decal_rect(metal, "fan")
        BUILDERS[name](T, t)
        coll = get_collection(name)
        ob = T.m.to_object(name, coll, mats)
        tag(ob, name)
        if T.blink.faces:
            tag(T.blink.to_object(f"{name}_blink", coll, mats), name)
        print(f"TOWER {name} z_ref={T.z_ref:.2f} tris={T.m.tris()} blink_tris={T.blink.tris()}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
