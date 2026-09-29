"""Stage 1: build the bed (frame, mattress, pillows, simulated duvet and throw), the
procedural source materials and the collision (collision.py); save the .blend.

  blender -b --factory-startup --python blender/props/bed/build.py
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bed_common as C  # noqa: E402
import collision  # noqa: E402
import lib_candidates as L  # noqa: E402
from arcology_blender import cloth, fabric, geo, soft, wear  # noqa: E402
from arcology_blender.cloth import S_ATTR, U_ATTR  # noqa: E402
from arcology_blender.geo import bm_box, bvh, finish, new_object, set_float_attr, shade, trim_hidden  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402

SOFT = 80.0  # shade angle for soft goods: smooth everywhere


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_walnut():
    """Dark walnut veneer, satin lacquer. Grain runs horizontally on every
    vertical face (along the rails and the headboard) and along the ledges
    on top. Lighter worn edges, a faint hair-oil mark on the headboard where
    the left sleeper leans, dust on the headboard top, kick scuffs low."""
    g = Graph(new_mat("src_walnut"))
    horiz = g.maprange(g.math("ABSOLUTE", g.nz), 0.5, 0.7)
    side = g.maprange(g.math("ABSOLUTE", g.x), 0.76, 0.79)
    across = g.mixf(horiz, g.z, g.mixf(side, g.y, g.x))
    base, rough, h = L.wood_veneer(g, across, g.vec(0.9, 0.9, 3.5), C.WALNUT_DARK, C.WALNUT_MID, C.WALNUT_LIGHT,
                                   lines_per_m=22.0, figure=3.0, rough=0.44, pore_vec=g.vec(0.1, 0.1, 1.0),
                                   streak_vec=g.vec(0.35, 0.35, 9.0), line_contrast=0.70)
    base, rough = wear.edge_highlight(g, base, rough, lo=0.53, hi=0.62, smoother=0.06, brighter=0.22)
    # where the left sleeper sits up against the headboard: skin oils darken and polish it
    lean = g.mul(g.mul(g.band(g.x, -0.62, -0.18, 0.10), g.band(g.z, 0.70, 0.86, 0.06)),
                 g.maprange(g.ny, -0.3, -0.7))
    lean = g.mul(lean, g.maprange(g.noise(4.0, 2.0), 0.25, 0.75))
    base, rough = fabric.rub(g, base, rough, g.mul(lean, 0.7), shinier=0.10, tint=-0.10)
    base, rough = wear.top_dust(g, base, rough, 0.99, 1.015, color=(0.36, 0.34, 0.31), amount=0.18, rougher=0.12)
    base, rough = wear.bottom_scuffs(g, base, rough, z_clean=0.24, z_full=0.15, rougher=0.10, darker=0.12)
    return g.finish(base, rough, 0.0, g.bump(h, 1.0, 1.0))


def mat_gunmetal():
    """Brushed gunmetal steel: legs brushed vertically, the headboard inlay
    bar along its length. Brighter worn edges, grime at the floor."""
    g = Graph(new_mat("src_gunmetal"))
    high = g.maprange(g.z, 0.4, 0.5)
    b1, r1, h1 = L.brushed_metal(g, C.GUNMETAL, 0.34, g.vec(120.0, 120.0, 3.0))
    b2, r2, h2 = L.brushed_metal(g, C.GUNMETAL, 0.30, g.vec(3.0, 120.0, 120.0))
    base, rough, h = g.mixc(high, b1, b2), g.mixf(high, r1, r2), g.mixf(high, h1, h2)
    base, rough = wear.edge_highlight(g, base, rough, lo=0.53, hi=0.62, smoother=0.08, brighter=0.35)
    base = wear.floor_grime(g, base, 0.0, 0.03, 0.7)
    return g.finish(base, rough, 1.0, g.bump(h, 1.0, 1.0))


def _linen(g, color):
    return fabric.fabric_base(g, color, rough=0.92, heather=0.04, slub=0.06, mottle=0.035, weave=0.00016,
                              slub_height=0.00016, mottle_height=0.00005)


def mat_duvet():
    """Washed linen duvet cover: soft crumple everywhere, deeper creases on
    the slept-in left half, a narrow hem."""
    g = Graph(new_mat("src_duvet"))
    base, rough, h = _linen(g, C.DUVET_COLOR)
    base, rough, h = fabric.welt(g, base, rough, h, cord=0.005, groove=0.003, bead=0.0008, darker=0.12,
                                 lighter=0.02, shinier=0.02)
    crumple = g.maprange(g.noise(3.0, 2.0), 0.25, 0.75)
    base, h = fabric.creases(g, base, h, crumple, stretch=(10.0, 10.0, 10.0), depth=0.0028, sharp=0.74,
                             darker=0.06)
    slept = g.mul(g.band(g.x, -0.85, 0.05, 0.25), g.band(g.y, -0.60, 0.45, 0.25))
    base, h = fabric.creases(g, base, h, g.mul(slept, g.maprange(g.noise(2.0, 1.0), 0.3, 0.7)),
                             stretch=(18.0, 7.0, 12.0), depth=0.0024, sharp=0.78, darker=0.06)
    return fabric.fabric_finish(g, base, rough, h)


def mat_sheet():
    """Fitted cotton-linen sheet: creases around the pillows and the dent,
    gathered at the corners by the elastic."""
    g = Graph(new_mat("src_sheet"))
    base, rough, h = _linen(g, C.SHEET_COLOR)
    head = g.mul(g.maprange(g.y, 0.25, 0.55), g.maprange(g.noise(3.0, 1.0), 0.3, 0.7))
    base, h = fabric.creases(g, base, h, head, stretch=(14.0, 6.0, 10.0), depth=0.0022, sharp=0.74, darker=0.07)
    sidem = g.maprange(g.math("ABSOLUTE", g.nz), 0.6, 0.3)
    base, h = fabric.creases(g, base, h, g.mul(sidem, 0.8), stretch=(30.0, 30.0, 4.0), depth=0.0010,
                             sharp=0.70, darker=0.08)
    base = wear.floor_grime(g, base, C.MAT_Z0, C.MAT_Z0 + 0.04, 0.85)
    return fabric.fabric_finish(g, base, rough, h)


def mat_pillow():
    """Linen pillowcases: creases toward the corners and around the head dent."""
    g = Graph(new_mat("src_pillow"))
    base, rough, h = _linen(g, C.PILLOW_COLOR)
    base, rough, h = fabric.welt(g, base, rough, h, cord=0.006, groove=0.003, bead=0.0008, darker=0.12,
                                 lighter=0.02, shinier=0.02)
    crumple = g.maprange(g.noise(4.0, 2.0), 0.2, 0.7)
    base, h = fabric.creases(g, base, h, crumple, stretch=(16.0, 16.0, 16.0), depth=0.0024, sharp=0.72,
                             darker=0.07)
    return fabric.fabric_finish(g, base, rough, h)


def mat_throw():
    """Slate-blue wool throw: heathered, a folded 12 mm hem, light pilling."""
    g = Graph(new_mat("src_throw"))
    base, rough, h = fabric.fabric_base(g, C.THROW_COLOR, rough=0.95, heather=0.08, slub=0.03, mottle=0.08,
                                        weave=0.00030, slub_height=0.00010, mottle_height=0.00010)
    base, rough, h = fabric.welt(g, base, rough, h, cord=0.012, groove=0.003, bead=0.0012, darker=0.20,
                                 lighter=0.03, shinier=0.02)
    base, h = fabric.creases(g, base, h, g.maprange(g.noise(3.0, 1.0), 0.3, 0.7), stretch=(8.0, 14.0, 10.0),
                             depth=0.0018, sharp=0.72, darker=0.10)
    base, h = fabric.pilling(g, base, h, 0.4, scale=110.0, amount=0.00025, lighter=0.04)
    return fabric.fabric_finish(g, base, rough, h)


def build_materials():
    return {"walnut": mat_walnut(), "gunmetal": mat_gunmetal(), "duvet": mat_duvet(), "sheet": mat_sheet(),
            "pillow": mat_pillow(), "throw": mat_throw()}


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------
def build_frame(coll, mats):
    parts = []
    # Platform slab; its top is open where the mattress covers it
    bm = bmesh.new()
    bm_box(bm, (-C.HALF_W, C.FOOT_Y, C.PLAT_Z0), (C.HALF_W, C.PLAT_Y1, C.PLAT_Z1))
    plat = new_object("Platform", bm, coll, material=mats["walnut"])
    finish(plat, 0.004, 2)
    bm = bmesh.new()
    bm.from_mesh(plat.data)
    top = [f for f in bm.faces if f.normal.z > 0.99 and f.calc_center_median().z > C.PLAT_Z1 - 1e-4
           and f.calc_area() > 1.0]
    inner = bmesh.ops.inset_individual(bm, faces=top, thickness=0.066)
    bmesh.ops.delete(bm, geom=top, context="FACES")
    bm.to_mesh(plat.data)
    bm.free()
    shade(plat, 30.0)
    parts.append(plat)

    # Headboard with a groove for the inlay bar
    bm = bmesh.new()
    bm_box(bm, (-C.HALF_W, C.HB_Y0, C.HB_Z0), (C.HALF_W, C.HB_Y1, C.HB_Z1))
    hb = new_object("Headboard", bm, coll, material=mats["walnut"])
    cut = bmesh.new()
    gz0, gz1 = C.INLAY_Z - C.INLAY_H / 2 - 0.002, C.INLAY_Z + C.INLAY_H / 2 + 0.002
    bm_box(cut, (-C.HALF_W + 0.05, C.HB_Y0 - 0.01, gz0), (C.HALF_W - 0.05, C.HB_Y0 + 0.012, gz1))
    geo.cut(hb, cut, coll)
    finish(hb, 0.006, 3)
    parts.append(hb)

    bm = bmesh.new()
    bm_box(bm, (-C.HALF_W + 0.052, C.HB_Y0 + 0.003, C.INLAY_Z - C.INLAY_H / 2),
           (C.HALF_W - 0.052, C.HB_Y0 + 0.012, C.INLAY_Z + C.INLAY_H / 2))
    inlay = new_object("Inlay", bm, coll, material=mats["gunmetal"])
    finish(inlay, 0.0015, 2)
    parts.append(inlay)

    # Square steel legs, 1 cm tucked into the platform
    bm = bmesh.new()
    h = C.LEG_SIZE / 2
    for x, y in C.LEGS:
        bm_box(bm, (x - h, y - h, 0.0), (x + h, y + h, C.LEG_H + 0.01))
    legs = new_object("Legs", bm, coll, material=mats["gunmetal"])
    finish(legs, 0.003, 2)
    parts.append(legs)

    frame = geo.join(parts, "BedFrame")
    tag(frame, "frame")
    return frame


# ---------------------------------------------------------------------------
# Soft goods
# ---------------------------------------------------------------------------
def build_mattress(coll, mats):
    size = (2 * C.MAT_HALF_W, C.MAT_Y1 - C.MAT_Y0, C.MAT_Z1 - C.MAT_Z0)
    center = (0.0, (C.MAT_Y0 + C.MAT_Y1) / 2, (C.MAT_Z0 + C.MAT_Z1) / 2)
    bm = soft.soft_box(center, size, C.MAT_R, step=0.06, band_segments=2, panel_axis=None,
                       crown={"+z": 0.008, "-x": 0.004, "+x": 0.004, "-y": 0.004}, crown_power=4.0,
                       open_faces=("-z",))
    (dx, dy), (rx, ry), depth = C.DENT
    soft.press(bm, (dx, dy, C.MAT_Z1 + 0.01), (rx, ry, 0.0), depth, thickness=size[2] + 0.01, power=2.0)
    soft.jitter(bm, 0.002, 4.0, seed=2.0)
    # the bottom n-gon sits on the platform: never visible
    bottom = [f for f in bm.faces if f.normal.z < -0.99 and len(f.verts) > 4]
    bmesh.ops.delete(bm, geom=bottom, context="FACES")
    ob = new_object("Mattress", bm, coll, material=mats["sheet"])
    shade(ob, SOFT)
    return ob


def build_pillows(coll, mats, mattress):
    tree = bvh([mattress])
    out = []
    for i, (px, yaw, dent) in enumerate(C.PILLOWS):
        bm = soft.pillow(size=C.PILLOW_SIZE, thickness=C.PILLOW_T, res=22, cord=0.004, pinch=0.08,
                         fullness=0.75, folds=0.016, fold_count=5.0, edge_ripple=0.004, seed=3.0 + i)
        soft.jitter(bm, 0.005, 3.0, seed=11.0 + i)
        soft.jitter(bm, 0.0012, 11.0, seed=4.0 + i)
        # head dent (upper panel, a little below the middle once leaned)
        soft.press(bm, (0.03 - 0.06 * i, -0.02, C.PILLOW_T / 2), (0.17, 0.13, 0.0), dent,
                   thickness=C.PILLOW_T, power=1.5)
        soft.rotate_verts(bm, (0.0, 0.0, 0.0), C.PILLOW_TILT, "X")
        soft.rotate_verts(bm, (0.0, 0.0, 0.0), yaw, "Z")
        hit = tree.ray_cast(Vector((px, 0.78, 1.0)), Vector((0, 0, -1)))
        mtop = hit[0].z
        maxy = max(v.co.y for v in bm.verts)
        minz = min(v.co.z for v in bm.verts)
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((px, C.HB_Y0 + 0.014 - maxy, mtop - 0.030 - minz)))
        soft.flatten_against(bm, (0, 0, mtop), (0, 0, 1), falloff=0.018,
                             region=lambda co: co.y < C.MAT_Y1 - 0.02)
        soft.flatten_against(bm, (0, C.HB_Y0, 0), (0, -1, 0), falloff=0.016)
        ob = new_object(f"Pillow{i}", bm, coll, material=mats["pillow"])
        shade(ob, SOFT)
        out.append(ob)
    return out


def duvet_place():
    """Start pose: flat above the mattress, turned down at the head end along
    a slightly diagonal line, with low bumps so it settles rumpled."""
    r = 0.025
    z0 = C.MAT_Z1 + 0.008 + C.DUVET_T + 0.010
    path = cloth.fold_path(C.DUVET_FOOT_Y, z0, C.FOLD_Y, r)
    rot = Matrix.Rotation(math.radians(1.2), 3, "Z")

    def place(u, s):
        fy = C.FOLD_Y + C.FOLD_SKEW * u
        y, z, layer = path(s, fy)
        if layer == 0:
            z += cloth.bumps(u, y, 0.035, 1.9, seed=1.0)
        elif layer == 2:
            z += cloth.bumps(u, y, 0.02, 2.5, seed=2.0)
        p = rot @ Vector((u, y, 0.0))
        return (p.x - 0.006, p.y, z)

    length = (C.FOLD_Y - C.DUVET_FOOT_Y) + math.pi * r + C.FOLD_BACK
    return place, length, r


def build_duvet(coll, mats, colliders):
    place, length, r = duvet_place()
    bm = cloth.cloth_grid(C.DUVET_W, length, C.DUVET_SPACING, place, corner_radius=0.40)
    ob = new_object("Duvet", bm, coll, material=mats["duvet"])
    # slack where it was slept in and kicked about: buckles into wrinkles in place
    def slack(co, a):
        w = 0.0
        for (cx, cy, rx, ry, amt) in C.DUVET_SLACK:
            w += amt * math.exp(-(((co.x - cx) / rx) ** 2 + ((co.y - cy) / ry) ** 2))
        # the hanging sides and foot get a little slack too: soft vertical ripples
        u, s_ = abs(a[U_ATTR]), a[S_ATTR]
        w += 0.32 * max(min(1.0, (u - 0.78) / 0.12), min(1.0, (0.24 - s_) / 0.12), 0.0)
        return min(1.0, w) if s_ < C.FOLD_Y - C.DUVET_FOOT_Y + C.FOLD_SKEW * a[U_ATTR] else 0.0

    set_float_attr(ob, "_slack", slack)
    t0 = time.time()
    cloth.cloth_settle(ob, colliders, frames=130, quality=10, mass=0.02, tension=40.0, compression=40.0, shear=10.0,
                   bending=0.5, air_damping=2.0, friction=10.0, distance=0.004, collision_quality=4,
                   self_collision=True, self_distance=0.004, self_friction=8.0, shrink=-0.015,
                   shrink_attr="_slack", shrink_max=-0.12)
    print(f"SIM duvet {time.time() - t0:.1f}s")
    s_fold = C.FOLD_Y - C.DUVET_FOOT_Y

    def keep(co, a):
        s_f = s_fold + C.FOLD_SKEW * a[U_ATTR]
        hanging = abs(a[U_ATTR]) > C.DUVET_W / 2 - 0.30 or a[S_ATTR] < 0.30
        return 1.0 if (a[S_ATTR] > s_f - 0.06 or a[soft.SEAM_ATTR] < 0.075 or hanging) else 0.0

    def drop(co, a):
        s_f = s_fold + C.FOLD_SKEW * a[U_ATTR]
        return 1.0 if a[S_ATTR] > s_f + math.pi * r + 0.05 else 0.0

    set_float_attr(ob, "_keep", keep)
    set_float_attr(ob, "_drop", drop)
    # loft thins out toward the hem seam
    set_float_attr(ob, "_taper", lambda co, a: min(1.0, a[soft.SEAM_ATTR] / 0.09) ** 0.6)
    lumps(ob, 0.008, 2.6, seed=8.0)
    cloth.thicken(ob, C.DUVET_T, keep_under_attr="_keep", drop_front_attr="_drop", taper_attr="_taper",
              taper_min=0.25)
    for a in ("_keep", "_drop", "_taper", "_slack", U_ATTR, S_ATTR):
        geo.remove_attribute(ob, a)
    shade(ob, SOFT)
    return ob


def build_throw(coll, mats, colliders):
    w, d = C.THROW_SIZE
    cx, cy = C.THROW_CENTER
    rot = Matrix.Rotation(math.radians(C.THROW_YAW), 3, "Z")
    z0 = 0.555

    def place(u, s):
        p = rot @ Vector((u, s - d / 2, 0.0))
        x, y = p.x + cx, p.y + cy
        return (x, y, z0 + cloth.bumps(x, y, 0.05, 3.2, seed=5.0))

    bm = cloth.cloth_grid(w, d, C.THROW_SPACING, place, corner_radius=0.03)
    ob = new_object("Throw", bm, coll, material=mats["throw"])
    t0 = time.time()
    cloth.cloth_settle(ob, colliders, frames=90, quality=6, mass=0.15, tension=10.0, compression=4.0, shear=5.0,
                   bending=0.6, air_damping=2.0, friction=12.0, distance=0.003, collision_quality=3,
                   shrink=-0.03)
    print(f"SIM throw {time.time() - t0:.1f}s")
    set_float_attr(ob, "_keep", lambda co, a: 1.0 if a[soft.SEAM_ATTR] < 0.05 else 0.0)
    cloth.thicken(ob, C.THROW_T, keep_under_attr="_keep")
    for a in ("_keep", U_ATTR, S_ATTR):
        geo.remove_attribute(ob, a)
    shade(ob, SOFT)
    return ob


def lumps(ob, amount, scale, seed):
    """Uneven fill: soft bulges along the normals of the upward-facing parts
    (the hanging sides stay put, so the footprint doesn't grow)."""
    from mathutils import noise
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    off = Vector((seed * 13.7, seed * 7.3, seed * 3.1))
    moves = []
    for v in bm.verts:
        w = min(1.0, max(0.0, (v.normal.z - 0.5) / 0.4))
        moves.append(v.normal * (amount * w * noise.noise(v.co * scale + off)))
    for v, m in zip(bm.verts, moves):
        v.co += m
    bm.to_mesh(ob.data)
    bm.free()


def main():
    t0 = time.time()
    clear_scene()
    mats = build_materials()
    coll = get_collection("Bed")
    frame = build_frame(coll, mats)
    mattress = build_mattress(coll, mats)
    pillows = build_pillows(coll, mats, mattress)
    duvet = build_duvet(coll, mats, [(mattress, C.DUVET_T), (frame, C.DUVET_T)] + [(p, 0.006) for p in pillows])
    throw = build_throw(coll, mats, [(duvet, C.THROW_T + 0.002, 20.0), (mattress, C.THROW_T), (frame, C.THROW_T)])
    # hanging hems and corners flare a little: keep them inside the footprint
    cloth.soft_bounds([duvet, throw], lo=(-C.HALF_W - 0.005, C.FOOT_Y + 0.004, None),
                  hi=(C.HALF_W + 0.005, None, None), knee=0.022)
    trim_hidden(mattress, [duvet])
    linen = geo.join([mattress, duvet] + pillows, "BedLinen")
    tag(linen, "linen")
    tag(throw, "throw")
    throw.name = throw.data.name = "BedThrow"
    collision.build_collision()
    f, li, th = part_tris("frame"), part_tris("linen"), part_tris("throw")
    print(f"TRIS frame={f} linen={li} throw={th} total={f + li + th} collision={part_tris('bed_col')}")
    save_blend(C.BLEND)
    print(f"BUILD {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
