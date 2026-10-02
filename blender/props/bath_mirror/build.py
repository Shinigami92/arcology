"""Stage 1: build the bathroom mirror and the swing-arm magnifier with procedural source materials, save.

  blender -b --factory-startup --python blender/props/bath_mirror/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import lib_candidates as cand  # noqa: E402
from bath_mirror_common import (  # noqa: E402
    ALU_DARK, ARM_KNUCKLE, ARM_R, BACKING, BACKING_Y0, BACKING_Y1, BLEND, BRACKET_KNUCKLE, DIFFUSER, FIXTURE,
    FIXTURE_POLISH, FRONT_Y, GLASS_MAT, GLASS_R, GLASS_W, GLASS_Y, GRIP_LOCAL, H, HALO_IN, HALO_OUT, HALO_TEX,
    HALO_Y, HEAD_BACK, HEAD_R, HEAD_X, HX, KNUCKLE_R, LED_D, LED_INSET, LED_MAT, LED_STRENGTH, LED_W, LED_Y, LIP,
    MAG_POS, PIVOT_Y, ROSETTE_R, ROSETTE_T, STANDOFF, SWIVEL_X, TOUCH_MAT, TOUCH_R0, TOUCH_R1, TOUCH_STRENGTH,
    TOUCH_X, TOUCH_Y, TOUCH_Z, WALL_T, WARM_LED,
)
from arcology_blender import curves, materials, metal, wear  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    bm_box, bm_cyl, bm_merge, collision_box, cyl_y, finish, join, new_empty, new_object, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, emissive_image_mat, new_mat, solid_mat  # noqa: E402
from arcology_blender.trim import image_from_array, linear_to_srgb  # noqa: E402

ROT_TO_FRONT = Matrix.Rotation(math.radians(90.0), 4, "X")  # lathe axis +Z -> -Y (faces the room)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def fixture_finish(g, rough, h):
    """The set's brushed gunmetal PVD: polished a touch brighter on convex edges."""
    edge = wear.convex_edges(g, radius=0.0008, ao_distance=0.004)
    base = g.mixc(g.mul(edge, 0.45), FIXTURE, FIXTURE_POLISH)
    rough = g.sub(rough, g.mul(edge, 0.06))
    return base, rough, h


def mat_frame():
    """Mirror frame: brushed along each member (mitered at the corners), faint
    fingerprints at the bottom center (the touch sensor) and dried splashes
    on the bottom member, the side facing the basin."""
    g = Graph(new_mat("src_frame"))
    rx, hx = metal.brushed(g, 0.30, axis="X", streak=0.06)
    rz, hz = metal.brushed(g, 0.30, axis="Z", streak=0.06)
    dx = g.sub(HX, g.math("ABSOLUTE", g.x))
    dz = g.math("MINIMUM", g.z, g.sub(H, g.z))
    side = g.maprange(g.sub(dz, dx), -0.0003, 0.0003)          # 1 on the vertical members
    rough, h = g.mixf(side, rx, rz), g.mixf(side, hx, hz)
    base, rough, h = fixture_finish(g, rough, h)
    touch = g.mul(g.band(g.x, TOUCH_X - 0.10, TOUCH_X + 0.10, 0.06), g.maprange(g.z, 0.03, 0.0))
    base, rough = wear.smudges(g, base, rough, touch, rougher=0.10, darker=0.03)
    low = g.maprange(g.z, 0.03, 0.0)
    base, rough = cand.water_spots(g, base, rough, low, scale=60.0, density=0.30, amount=0.10, rougher=0.10)
    return g.finish(base, rough, 1.0, g.bump(h, 1.0, 1.0))


def mat_alu():
    """Hidden mount rails and LED channel: dark anodized aluminium."""
    g = Graph(new_mat("src_alu"))
    r = g.add(0.42, g.mul(g.sub(g.noise(25.0), 0.5), 0.08))
    return g.finish(ALU_DARK, r, 0.9, None)


def mat_backing():
    """Aluminium composite backing behind the glass, dark grey paint."""
    g = Graph(new_mat("src_backing"))
    return g.finish(BACKING, 0.55, 0.0, None)


def mat_mag_metal(name, radial_center, radial_mask, barrels):
    """Magnifier fixture metal: brushed along the arm (X), along Z on the
    knuckle barrels (vertical axes through `barrels`: [(x, y, radius)]), spun
    around the head's / rosette's axis inside `radial_mask(g)`; fingerprints
    and a few water spots there."""
    g = Graph(new_mat(f"src_{name}"))
    rx, hx = metal.brushed(g, 0.30, axis="X", streak=0.06)
    rz, hz = metal.brushed(g, 0.30, axis="Z", streak=0.06)
    rr, hr = cand.brushed_radial(g, 0.30, radial_center, axis="Y", streak=0.06)
    vertical = 0.0
    for bx, by, br in barrels:
        vertical = g.add(vertical, g.maprange(g.dist_xy(bx, by), br + 0.0015, br + 0.0005))
    vertical = g.math("MINIMUM", vertical, 1.0)
    rough, h = g.mixf(vertical, rx, rz), g.mixf(vertical, hx, hz)
    m = radial_mask(g)
    rough, h = g.mixf(m, rough, rr), g.mixf(m, h, hr)
    base, rough, h = fixture_finish(g, rough, h)
    base, rough = wear.smudges(g, base, rough, m, rougher=0.08, darker=0.03)
    base, rough = cand.water_spots(g, base, rough, g.mul(m, 0.6), scale=70.0, density=0.20, amount=0.08,
                                   rougher=0.08)
    return g.finish(base, rough, 1.0, g.bump(h, 1.0, 1.0))


def halo_image():
    """Emission texture of the wall glow (warm 3000 K), covering the halo quad."""
    ext = (-HX - HALO_OUT[0], -HALO_OUT[1], HX + HALO_OUT[0], H + HALO_OUT[1])
    loop = (-HX + LED_INSET, LED_INSET, HX - LED_INSET, H - LED_INSET)
    k = cand.backlight_halo(ext, loop, height=-LED_Y, size=HALO_TEX, inner=(-HX, 0.0, HX, H))
    rgb = linear_to_srgb(k[..., None] * cand.np.asarray(WARM_LED, dtype=cand.np.float32))
    return image_from_array("bath_mirror_halo", rgb, "sRGB"), ext


def build_materials():
    head_c = MAG_POS + Vector((HEAD_X, PIVOT_Y, 0.0))
    px, py = MAG_POS.x, MAG_POS.y + PIVOT_Y
    halo, ext = halo_image()
    led = emissive_image_mat(LED_MAT, halo, base=(0.0, 0.0, 0.0), rough=1.0, strength=LED_STRENGTH)
    return {
        "frame": mat_frame(),
        "alu": mat_alu(),
        "backing": mat_backing(),
        "rubber": materials.rubber("bumper", base=(0.03, 0.03, 0.03), rough=0.75),
        "glass": solid_mat(GLASS_MAT, (0.92, 0.93, 0.93), 0.03, 1.0),
        "led": led,
        "halo_extent": ext,
        "touch": solid_mat(TOUCH_MAT, (0.70, 0.70, 0.68), 0.45, 0.0, emission=WARM_LED,
                           emission_strength=TOUCH_STRENGTH),
        "arm": mat_mag_metal("mag_arm", head_c,
                             lambda g: g.maprange(g.x, MAG_POS.x + SWIVEL_X + 0.006, MAG_POS.x + SWIVEL_X + 0.009),
                             [(px, py, KNUCKLE_R), (px + SWIVEL_X, py, 0.0085)]),
        "bracket": mat_mag_metal("mag_bracket", MAG_POS,
                                 lambda g: g.maprange(g.y, -ROSETTE_T - 0.001, -ROSETTE_T + 0.0005),
                                 [(px, py, KNUCKLE_R)]),
    }


def frame_member(bm, p0, p1, u, v, profile):
    """One straight frame member from corner p0 to corner p1 (x, z) with 45-degree
    miters: `profile` [(inset a, y)] closed, u along the member, v inward.
    A point at inset a sits at p0 + (u + v) * a and p1 + (v - u) * a."""
    left, right = [], []
    for a, y in profile:
        left.append(bm.verts.new((p0[0] + (u[0] + v[0]) * a, y, p0[1] + (u[1] + v[1]) * a)))
        right.append(bm.verts.new((p1[0] + (v[0] - u[0]) * a, y, p1[1] + (v[1] - u[1]) * a)))
    n = len(profile)
    faces = [bm.faces.new((left[i], left[(i + 1) % n], right[(i + 1) % n], right[i])) for i in range(n)]
    faces += [bm.faces.new(left), bm.faces.new(list(reversed(right)))]
    bmesh.ops.recalc_face_normals(bm, faces=faces)


# ---------------------------------------------------------------------------
# Main mirror (world coordinates = mirror-local: origin bottom center of the back, wall plane)
# ---------------------------------------------------------------------------
def build_mirror(coll, col_coll, mats):
    # Frame: four mitered L-section members (8 mm face, 22 mm skirt, 1.5 mm walls).
    # Separate members also unwrap as strips instead of one ring island.
    profile = [(0.0, FRONT_Y), (LIP, FRONT_Y), (LIP, FRONT_Y + WALL_T), (WALL_T, FRONT_Y + WALL_T),
               (WALL_T, -STANDOFF), (0.0, -STANDOFF)]       # (inset from the outer edge, y)
    bm = bmesh.new()
    for p0, p1, u, v in (((-HX, 0.0), (HX, 0.0), (1, 0), (0, 1)), ((HX, 0.0), (HX, H), (0, 1), (-1, 0)),
                         ((HX, H), (-HX, H), (-1, 0), (0, -1)), ((-HX, H), (-HX, 0.0), (0, -1), (1, 0))):
        frame_member(bm, p0, p1, u, v, profile)
    frame = new_object("Frame", bm, coll, material=mats["frame"])
    finish(frame, 0.0005, 2, angle=30.0, sharp_angle=40.0)
    parts = [frame]

    # Backing panel behind the glass
    bm = bmesh.new()
    g = WALL_T + 0.0005
    bm_box(bm, (-HX + g, BACKING_Y0, g), (HX - g, BACKING_Y1, H - g))
    backing = new_object("Backing", bm, coll, material=mats["backing"])
    finish(backing, None)
    parts.append(backing)

    # LED channel loop on the back (strip faces the wall), and the hidden mount
    bm = bmesh.new()
    lx, lz0, lz1 = HX - LED_INSET, LED_INSET, H - LED_INSET
    hw = LED_W / 2
    y0, y1 = BACKING_Y1, LED_Y
    bm_box(bm, (-lx - hw, y0, lz0 - hw), (lx + hw, y1, lz0 + hw))
    bm_box(bm, (-lx - hw, y0, lz1 - hw), (lx + hw, y1, lz1 + hw))
    bm_box(bm, (-lx - hw, y0, lz0 + hw), (-lx + hw, y1, lz1 - hw))
    bm_box(bm, (lx - hw, y0, lz0 + hw), (lx + hw, y1, lz1 - hw))
    # French cleat: wall rail and the mirror's rail hooked over it
    bm_box(bm, (-0.30, -0.010, 0.56), (0.30, 0.0, 0.66))
    bm_box(bm, (-0.30, BACKING_Y1, 0.60), (0.30, -0.0105, 0.70))
    bm_box(bm, (-0.30, -0.0215, 0.645), (0.30, -0.0105, 0.70))
    mount = new_object("Mount", bm, coll, material=mats["alu"])
    finish(mount, 0.0008, 1)
    parts.append(mount)
    bm = bmesh.new()
    for sx in (-1, 1):  # bottom bumpers keep the mirror parallel to the wall
        bm_cyl(bm, 0.012, -BACKING_Y1 - 0.001, cyl_y((sx * 0.42, (BACKING_Y1 - 0.001) / 2, 0.12)), 16)
    bumpers = new_object("Bumpers", bm, coll, material=mats["rubber"])
    finish(bumpers, 0.001, 1)
    parts.append(bumpers)
    body = join(parts, "BathMirror")
    tag(body, "body")

    # Mirror glass: its own object and slot (Godot assigns the reflective material)
    bm = bmesh.new()
    gx0, gx1, gz0, gz1 = -HX + LIP - 0.003, HX - LIP + 0.003, LIP - 0.003, H - LIP + 0.003
    cand._face_minus_y(bm, [bm.verts.new(p) for p in ((gx0, GLASS_Y, gz0), (gx1, GLASS_Y, gz0),
                                                      (gx1, GLASS_Y, gz1), (gx0, GLASS_Y, gz1))])
    glass = new_object("MirrorGlass", bm, coll, material=mats["glass"])
    cand.planar_uvs(glass, lambda p: ((p.x - gx0) / (gx1 - gx0), (p.z - gz0) / (gz1 - gz0)))
    tag(glass, "mirror_fx")

    # Light: halo ring quad on the wall + the LED diffuser faces (one switchable slot)
    x0, z0, x1, z1 = mats["halo_extent"]
    bm = bmesh.new()
    cand.rect_ring_quads(bm, (x0, z0, x1, z1), (-HX + HALO_IN, HALO_IN, HX - HALO_IN, H - HALO_IN), HALO_Y)
    dw = 0.0045
    yd = LED_Y + 0.0002
    for lo, hi in (((-lx - dw, lz0 - dw), (lx + dw, lz0 + dw)), ((-lx - dw, lz1 - dw), (lx + dw, lz1 + dw)),
                   ((-lx - dw, lz0 + dw), (-lx + dw, lz1 - dw)), ((lx - dw, lz0 + dw), (lx + dw, lz1 - dw))):
        f = bm.faces.new([bm.verts.new(p) for p in ((lo[0], yd, lo[1]), (lo[0], yd, hi[1]),
                                                     (hi[0], yd, hi[1]), (hi[0], yd, lo[1]))])
        f.normal_update()
        if f.normal.y < 0.0:   # the diffuser faces the wall (+Y)
            f.normal_flip()
    light = new_object("MirrorLight", bm, coll, material=mats["led"])

    def halo_uv(p):
        if p.y > HALO_Y + 0.001:                 # diffuser: the bright texels behind the mirror
            return (0.5, 0.5)
        return ((p.x - x0) / (x1 - x0), (p.z - z0) / (z1 - z0))
    cand.planar_uvs(light, halo_uv)
    tag(light, "mirror_fx")

    # Touch sensor: etched sun icon and a thin ring light on the glass, bottom center
    bm = bmesh.new()
    c = Vector((TOUCH_X, TOUCH_Y, TOUCH_Z))
    cand.annulus_y(bm, c, TOUCH_R0, TOUCH_R1, 48)
    cand.disc_y(bm, c, 0.0032, 20)
    for i in range(8):
        a = math.radians(22.5 + 45.0 * i)
        d, t = Vector((math.cos(a), 0.0, math.sin(a))), Vector((-math.sin(a), 0.0, math.cos(a)))
        r0, r1, w = 0.0050, 0.0074, 0.0006
        cand._face_minus_y(bm, [bm.verts.new(c + d * r0 - t * w), bm.verts.new(c + d * r1 - t * w),
                                bm.verts.new(c + d * r1 + t * w), bm.verts.new(c + d * r0 + t * w)])
    touch = new_object("TouchSensor", bm, coll, material=mats["touch"])
    cand.planar_uvs(touch, lambda p: ((p.x - c.x) / 0.03 + 0.5, (p.z - c.z) / 0.03 + 0.5))
    tag(touch, "mirror_fx")

    # Collision for Godot: one box from the wall to the frame's front
    tag(collision_box("ColMirror", (-HX, FRONT_Y, 0.0), (HX, 0.0, H), col_coll), "body_col")
    return body


# ---------------------------------------------------------------------------
# Magnifier (built at MAG_POS; bracket-local and arm-local geometry)
# ---------------------------------------------------------------------------
def lathe_front(bm, profile, segments, center):
    """Revolve a (r, w) profile about an axis through `center` pointing to -Y (w > 0 toward the room)."""
    tmp = bmesh.new()
    curves.lathe(tmp, profile, segments)
    bmesh.ops.transform(tmp, verts=tmp.verts, matrix=Matrix.Translation(center) @ ROT_TO_FRONT)
    bm_merge(bm, tmp)


def knuckle(bm, center, r, z0, z1, segs=24):
    """Vertical barrel with chamfered ends (lathe)."""
    c = 0.0008
    curves.lathe(bm, [(0.0, z0), (r - c, z0), (r, z0 + c), (r, z1 - c), (r - c, z1), (0.0, z1)], segs, center=center)


def build_magnifier(coll, mats):
    # Bracket: wall rosette, two lugs, top and bottom knuckles with pin caps
    bm = bmesh.new()
    R, T = ROSETTE_R, ROSETTE_T
    lathe_front(bm, [(0.0, 0.0), (R, 0.0), (R, T - 0.0025), (R - 0.0008, T - 0.0010), (R - 0.0025, T - 0.0001),
                     (R - 0.006, T), (0.0, T + 0.0003)], 48, Vector((0.0, 0.0, 0.0)))
    bracket = new_object("MagnifierBracket", bm, coll, origin=MAG_POS, material=mats["bracket"])
    shade(bracket, 35.0)
    zc = sum(BRACKET_KNUCKLE) / 2
    bm = bmesh.new()
    for s in (-1, 1):
        bm_cyl(bm, 0.0075, -PIVOT_Y - T + 0.002, cyl_y((0.0, (PIVOT_Y - T + 0.002) / 2, s * zc)), 20)
    lugs = new_object("Lugs", bm, coll, origin=MAG_POS, material=mats["bracket"])
    finish(lugs, 0.0008, 2, sharp_angle=40.0)
    bm = bmesh.new()
    k0, k1 = BRACKET_KNUCKLE
    knuckle(bm, (0.0, PIVOT_Y, 0.0), KNUCKLE_R, k0, k1)
    knuckle(bm, (0.0, PIVOT_Y, 0.0), KNUCKLE_R, -k1, -k0)
    for s in (-1, 1):  # pin caps
        prof = [(0.0, 0.0), (0.0062, 0.0), (0.0060, 0.0010), (0.0050, 0.0020), (0.0028, 0.0027), (0.0, 0.0029)]
        if s < 0:
            prof = [(r, -z) for r, z in prof]
        curves.lathe(bm, prof, 20, center=(0.0, PIVOT_Y, s * k1))
    knuckles = new_object("Knuckles", bm, coll, origin=MAG_POS, material=mats["bracket"])
    shade(knuckles, 40.0)
    bracket = join([bracket, lugs, knuckles], "MagnifierBracket")
    tag(bracket, "mag_bracket")
    col = collision_box("ColMagBracket", (-ROSETTE_R, PIVOT_Y - KNUCKLE_R, -k1 - 0.003),
                        (ROSETTE_R, 0.0, k1 + 0.003), coll)
    col.parent = bracket
    tag(col, "mag_bracket_col")

    # Arm (origin on the pivot axis): knuckle, tapered bar, swivel knuckle, head bezel and back
    root_pos = MAG_POS + Vector((0.0, PIVOT_Y, 0.0))
    bm = bmesh.new()
    knuckle(bm, (0.0, 0.0, 0.0), KNUCKLE_R, -ARM_KNUCKLE, ARM_KNUCKLE, 24)
    arm = new_object("MagnifierArm", bm, coll, origin=root_pos, material=mats["arm"])
    shade(arm, 40.0)
    bm = bmesh.new()
    path = [(KNUCKLE_R - 0.003 + (SWIVEL_X - KNUCKLE_R) * i / 6.0, 0.0, 0.0) for i in range(7)]
    scales = [(1.0 - 0.18 * i / 6.0,) * 2 for i in range(7)]
    curves.sweep(bm, path, curves.circle_profile(ARM_R, 16), up=(0.0, 0.0, 1.0), scales=scales)
    bar = new_object("ArmBar", bm, coll, origin=root_pos, material=mats["arm"])
    shade(bar, 50.0)
    bm = bmesh.new()
    knuckle(bm, (SWIVEL_X, 0.0, 0.0), 0.0085, -0.016, 0.016, 20)
    bm_box(bm, (SWIVEL_X + 0.004, -0.0035, -0.010), (HEAD_X - HEAD_R + 0.004, 0.0035, 0.010))
    swivel = new_object("Swivel", bm, coll, origin=root_pos, material=mats["arm"])
    finish(swivel, 0.0007, 2, sharp_angle=40.0)
    bm = bmesh.new()
    gw = GLASS_W
    prof = [(0.0935, gw - 0.0010), (0.0950, gw + 0.0012), (0.0962, 0.0086), (0.0985, 0.0090),
            (0.1006, 0.0081), (0.1017, 0.0062), (HEAD_R, 0.0035), (HEAD_R, -0.0050), (0.1012, -0.0082),
            (0.0990, -0.0102), (0.0950, -0.0117), (0.0800, -0.0136), (0.0500, -0.0152), (0.0200, -0.0159),
            (0.0, HEAD_BACK)]
    lathe_front(bm, prof, 72, Vector((HEAD_X, 0.0, 0.0)))
    head = new_object("Head", bm, coll, origin=root_pos, material=mats["arm"])
    shade(head, 40.0)
    arm = join([arm, bar, swivel, head], "MagnifierArm")
    tag(arm, "mag_arm")

    bm = bmesh.new()
    cand.disc_y(bm, (HEAD_X, -gw, 0.0), GLASS_R, 72)
    mglass = new_object("MagnifierGlass", bm, coll, material=mats["glass"], parent=arm)
    cand.planar_uvs(mglass, lambda p: ((p.x - HEAD_X) / (2 * GLASS_R) + 0.5, p.z / (2 * GLASS_R) + 0.5))
    tag(mglass, "mag_arm")
    tag(new_empty("HandleGrip", coll, GRIP_LOCAL, parent=arm, size=0.02), "mag_arm")
    return bracket, arm


def main():
    clear_scene()
    mats = build_materials()
    build_mirror(get_collection("Mirror"), get_collection("MirrorCollision"), mats)
    build_magnifier(get_collection("Magnifier"), mats)
    print(f"TRIS body={part_tris('body')} mirror_fx={part_tris('mirror_fx')} collision={part_tris('body_col')} "
          f"bracket={part_tris('mag_bracket')} arm={part_tris('mag_arm')}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
