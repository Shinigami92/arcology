"""Stage 1: build the fridge geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/fridge/build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from fridge_common import (  # noqa: E402
    BINS, BIN_Y1, BLEND, CAB_H, CAB_X, CAB_Y, CAV_X, CAV_Y_BACK, CAV_Z0, CAV_Z1, CRISPER_COVER_TOP,
    CRISPER_D, CRISPER_H, CRISPER_W, CRISPER_Y0, DISPLAY_MAT, DOOR_LINER_Y0, DOOR_LINER_Y1,
    DOOR_SKIN_Y0, DOOR_SKIN_Y1, DOOR_W, DOOR_Z0, DOOR_Z1, GASKET_Y0, GASKET_Y1, GLASS_MAT, GLASS_T,
    HANDLE_GRIP, HANDLE_R, HANDLE_X, HANDLE_Y, HANDLE_Z0, HANDLE_Z1, HINGE, LIGHT_MAT, PLINTH_DEPTH,
    PLINTH_Z, SHELF_TOPS, SHELF_Y0,
)
from arcology_blender import materials, wear  # noqa: E402
from arcology_blender.geo import (  # noqa: E402
    assign_by_region, bm_box, bm_cyl, bm_quad, collision_box, cut, cyl_y, finish, new_empty,
    new_object, set_uvs, shade,
)
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import (  # noqa: E402
    Graph, canvas_image, draw_text, emissive_image_mat, fill_rect, new_mat, pixel_canvas, solid_mat,
)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def mat_steel():
    """Brushed stainless: sheet waviness, worn edges, fingerprints around the
    handle, kick scuffs, dust on top, a parcel sticker on the door."""
    g = Graph(new_mat("src_steel"))
    base = (0.42, 0.43, 0.45)
    rough = g.add(0.34, g.mul(g.sub(g.noise(6.0, 2.0), 0.5), 0.10))
    # Sheet metal waviness (large scale only; fine grain shimmers in VR).
    n = g.bump(g.noise(2.5, 1.0), 1.0, 0.02)
    base, rough = wear.edge_highlight(g, base, rough)
    # Fingerprints around the handle (door front and handle bar, world coordinates).
    front = g.maprange(g.y, -0.365, -0.372)
    region = g.mul(g.mul(g.band(g.x, 0.10, 0.29, 0.05), g.band(g.z, 0.90, 1.60, 0.10)), front)
    base, rough = wear.smudges(g, base, rough, region)
    base, rough = wear.bottom_scuffs(g, base, rough)
    base = wear.floor_grime(g, base)
    base, rough = wear.top_dust(g, base, rough, 1.78, 1.84)
    # A parcel sticker on the door front (world x -0.22..-0.13, z 0.98..1.05).
    st = g.mul(g.rect_xz((-0.22, 0.98), (-0.13, 1.05)), front)
    stripe = g.band(g.z, 1.034, 1.05, 0.001)
    line1 = g.mul(g.band(g.z, 1.000, 1.007, 0.001), g.band(g.x, -0.210, -0.160, 0.001))
    line2 = g.mul(g.band(g.z, 1.014, 1.021, 0.001), g.band(g.x, -0.210, -0.140, 0.001))
    st_col = g.mixc(stripe, (0.90, 0.90, 0.88), (0.85, 0.08, 0.30))
    st_col = g.mixc(g.add(line1, line2), st_col, (0.10, 0.10, 0.11))
    base = g.mixc(st, base, st_col)
    rough = g.mixf(st, rough, 0.55)
    metal = g.sub(1.0, st)
    return g.finish(base, rough, metal, n)


def display_texture():
    """Cyan status readout: fridge and freezer temperature, eco mode, level bar."""
    w, h = 512, 256
    img = pixel_canvas(w, h, (0.012, 0.02, 0.028))
    cyan = (0.02, 0.85, 0.91)
    dim = (0.02, 0.36, 0.40)
    draw_text(img, "4°C", 40, 60, 12, cyan)
    draw_text(img, "-18°C", 290, 78, 7, dim)
    draw_text(img, "ECO", 290, 140, 7, dim)
    fill_rect(img, 40, 47, 472, 50, dim)
    for i in range(8):
        x = 40 + i * 32
        fill_rect(img, x, 176, x + 24, 190, cyan if i < 5 else (0.03, 0.10, 0.12))
    return canvas_image("fridge_display_emissive", img)


def build_materials():
    return {
        "steel": mat_steel(),
        "liner": materials.white_plastic("liner"),
        "dark": materials.dark_plastic("dark"),
        "frosted": materials.frosted_plastic("frosted"),
        "rubber": materials.rubber("rubber"),
        "paper": materials.note_paper("paper", (-0.19, 1.405), (-0.135, 1.465)),
        "magnet": materials.gloss_paint("magnet", (0.85, 0.10, 0.32)),
        # Opaque frosted glass: no stacked transparent surfaces in VR.
        "glass": solid_mat(GLASS_MAT, (0.80, 0.86, 0.84), 0.05),
        "light": solid_mat(LIGHT_MAT, (0.90, 0.90, 0.90), 0.5, emission=(1.0, 0.96, 0.90), emission_strength=4.0),
        "display": emissive_image_mat(DISPLAY_MAT, display_texture()),
    }


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def build_body(coll, col_coll, mats):
    steel, liner, dark, frosted = mats["steel"], mats["liner"], mats["dark"], mats["frosted"]
    glass, light = mats["glass"], mats["light"]

    # Cabinet shell: outer box minus cavity and plinth recess
    bm = bmesh.new()
    bm_box(bm, (-CAB_X, -CAB_Y, 0.0), (CAB_X, CAB_Y, CAB_H))
    cab = new_object("Cabinet", bm, coll, material=steel)
    bm = bmesh.new()
    bm_box(bm, (-CAV_X, -0.40, CAV_Z0), (CAV_X, CAV_Y_BACK, CAV_Z1))
    bm_box(bm, (-0.31, -0.40, -0.01), (0.31, -CAB_Y + PLINTH_DEPTH, PLINTH_Z))
    cut(cab, bm, coll)
    finish(cab, 0.006, 2)
    assign_by_region(cab, [
        (((-CAV_X - 0.012, -0.34, CAV_Z0 - 0.012), (CAV_X + 0.012, CAV_Y_BACK + 0.012, CAV_Z1 + 0.012)), liner),
        (((-0.31, -0.34, -0.01), (0.31, -CAB_Y + PLINTH_DEPTH + 0.012, PLINTH_Z + 0.012)), dark),
    ], steel)
    tag(cab, "body")

    # Top hinge bracket
    bm = bmesh.new()
    bm_box(bm, (-CAB_X, -0.39, CAB_H), (-CAB_X + 0.075, -0.255, CAB_H + 0.006))
    bm_cyl(bm, 0.012, 0.006, Matrix.Translation((HINGE.x, HINGE.y, CAB_H + 0.009)), 16)
    ob = new_object("HingeTop", bm, coll, material=steel)
    finish(ob, 0.0015, 1)
    tag(ob, "body")

    # Kick grille in the plinth recess
    bm = bmesh.new()
    yb = -CAB_Y + PLINTH_DEPTH
    bm_box(bm, (-0.285, yb - 0.006, 0.004), (0.285, yb, PLINTH_Z - 0.004))
    for i in range(5):
        z = 0.012 + i * 0.014
        bm_box(bm, (-0.28, yb - 0.012, z), (0.28, yb - 0.006, z + 0.006))
    ob = new_object("KickGrille", bm, coll, material=dark)
    finish(ob, 0.0012, 1)
    tag(ob, "body")

    # Shelf support ribs on the liner walls
    bm = bmesh.new()
    for t in SHELF_TOPS + [CRISPER_COVER_TOP]:
        y0 = SHELF_Y0 + 0.015 if t in SHELF_TOPS else CRISPER_Y0 + 0.015
        for s in (-1, 1):
            xa, xb = sorted((s * (CAV_X - 0.012), s * (CAV_X + 0.002)))
            bm_box(bm, (xa, y0, t - 0.026), (xb, CAV_Y_BACK + 0.002, t - 0.014))
    ob = new_object("ShelfRibs", bm, coll, material=liner)
    finish(ob, 0.002, 1)
    tag(ob, "body")

    # Cold air duct on the back wall, with vents and a thermostat dial
    bm = bmesh.new()
    bm_box(bm, (-0.10, CAV_Y_BACK - 0.02, 1.40), (0.10, CAV_Y_BACK + 0.002, 1.72))
    ob = new_object("BackDuct", bm, coll, material=liner)
    finish(ob, 0.004, 2)
    tag(ob, "body")
    bm = bmesh.new()
    for i in range(4):
        z = 1.43 + i * 0.05
        bm_box(bm, (-0.08, CAV_Y_BACK - 0.024, z), (0.08, CAV_Y_BACK - 0.019, z + 0.02))
    bm_cyl(bm, 0.02, 0.012, cyl_y((0.0, CAV_Y_BACK - 0.026, 1.665)), 24)
    bm_box(bm, (-0.002, CAV_Y_BACK - 0.034, 1.665), (0.002, CAV_Y_BACK - 0.03, 1.683))
    ob = new_object("DuctVents", bm, coll, material=dark)
    finish(ob, 0.001, 1)
    tag(ob, "body")

    # Interior light: frame with a recessed diffuser panel
    bm = bmesh.new()
    bm_box(bm, (-0.16, -0.21, CAV_Z1 - 0.025), (0.16, -0.05, CAV_Z1 + 0.002))
    frame = new_object("LightFrame", bm, coll, material=liner)
    bm = bmesh.new()
    bm_box(bm, (-0.14, -0.19, CAV_Z1 - 0.03), (0.14, -0.07, CAV_Z1 - 0.008))
    cut(frame, bm, coll)
    finish(frame, 0.003, 2)
    tag(frame, "body")
    bm = bmesh.new()
    z = CAV_Z1 - 0.012
    bm_quad(bm, ((-0.14, -0.19, z), (-0.14, -0.07, z), (0.14, -0.07, z), (0.14, -0.19, z)))
    ob = new_object("LightPanel", bm, coll, material=light)
    set_uvs(ob, ((0, 0), (0, 1), (1, 1), (1, 0)))
    tag(ob, "body")

    # Shelves: opaque frosted-glass panes in a dark trim frame
    def shelf(name, top, y0):
        bm = bmesh.new()
        bm_box(bm, (-CAV_X + 0.0025, y0, top - GLASS_T), (CAV_X - 0.0025, CAV_Y_BACK - 0.004, top))
        g = new_object(f"{name}Glass", bm, coll, material=glass)
        shade(g, 89.0)
        tag(g, "body")
        bm = bmesh.new()
        bm_box(bm, (-CAV_X + 0.0025, y0 - 0.015, top - 0.016), (CAV_X - 0.0025, y0, top + 0.006))
        for s in (-1, 1):
            xa, xb = sorted((s * (CAV_X - 0.0025), s * (CAV_X - 0.0145)))
            bm_box(bm, (xa, y0, top - 0.014), (xb, CAV_Y_BACK - 0.004, top + 0.002))
        bm_box(bm, (-CAV_X + 0.0025, CAV_Y_BACK - 0.012, top - 0.014), (CAV_X - 0.0025, CAV_Y_BACK - 0.004, top + 0.002))
        f = new_object(f"{name}Frame", bm, coll, material=dark)
        finish(f, 0.002, 1)
        tag(f, "body")

    for i, t in enumerate(SHELF_TOPS):
        shelf(f"Shelf{i + 1}", t, SHELF_Y0)
    shelf("CrisperCover", CRISPER_COVER_TOP, CRISPER_Y0)

    # Crisper drawer: origin at front-bottom-center (world 0, CRISPER_Y0, CAV_Z0)
    hw = CRISPER_W / 2
    bm = bmesh.new()
    bm_box(bm, (-hw, 0.0, 0.0), (hw, CRISPER_D, CRISPER_H))
    bm_box(bm, (-hw - 0.0075, -0.012, 0.0), (hw + 0.0075, 0.0, CRISPER_H + 0.02))  # front panel
    bm_box(bm, (-0.08, -0.030, CRISPER_H - 0.01), (0.08, -0.012, CRISPER_H + 0.02))  # grip lip
    drawer = new_object("CrisperDrawer", bm, coll, origin=(0.0, CRISPER_Y0, CAV_Z0), material=frosted)
    bm = bmesh.new()
    bm_box(bm, (-hw + 0.008, 0.008, 0.008), (hw - 0.008, CRISPER_D - 0.008, CRISPER_H + 0.05))
    bm_box(bm, (-0.06, -0.031, CRISPER_H - 0.002), (0.06, -0.02, CRISPER_H + 0.012))  # finger recess
    cut(drawer, bm, coll)
    finish(drawer, 0.003, 2)
    assign_by_region(drawer, [
        (((-0.081, -0.031, CRISPER_H - 0.011), (0.081, -0.0115, CRISPER_H + 0.021)), dark),
    ], frosted)
    tag(drawer, "body")

    # Collision boxes for Godot, one per piece, so cans stand on the shelves
    def col(name, lo, hi):
        tag(collision_box(name, lo, hi, col_coll), "body_col")

    col("ColFloor", (-CAB_X, -CAB_Y, 0.0), (CAB_X, CAB_Y, CAV_Z0))
    col("ColWallLeft", (-CAB_X, -CAB_Y, CAV_Z0), (-CAV_X, CAB_Y, CAV_Z1))
    col("ColWallRight", (CAV_X, -CAB_Y, CAV_Z0), (CAB_X, CAB_Y, CAV_Z1))
    col("ColTop", (-CAB_X, -CAB_Y, CAV_Z1), (CAB_X, CAB_Y, CAB_H))
    col("ColBack", (-CAV_X, CAV_Y_BACK, CAV_Z0), (CAV_X, CAB_Y, CAV_Z1))
    for i, t in enumerate(SHELF_TOPS):
        col(f"ColShelf{i + 1}", (-CAV_X, SHELF_Y0 - 0.015, t - 0.016), (CAV_X, CAV_Y_BACK, t))
    col("ColCrisperCover", (-CAV_X, CRISPER_Y0 - 0.015, CRISPER_COVER_TOP - 0.016),
        (CAV_X, CAV_Y_BACK, CRISPER_COVER_TOP))


def build_door(coll, mats):
    steel, liner, dark, frosted = mats["steel"], mats["liner"], mats["dark"], mats["frosted"]
    rubber, paper, magnet, display = mats["rubber"], mats["paper"], mats["magnet"], mats["display"]

    # Door skin (root of the door hierarchy, origin on the hinge axis)
    bm = bmesh.new()
    bm_box(bm, (0.0, DOOR_SKIN_Y0, DOOR_Z0), (DOOR_W, DOOR_SKIN_Y1, DOOR_Z1))
    door = new_object("Door", bm, coll, origin=HINGE, material=steel)
    finish(door, 0.010, 3)
    tag(door, "door")

    def child(name, bm, material, bevel_w=None, segs=1):
        ob = new_object(name, bm, coll, material=material, parent=door)
        if bevel_w:
            finish(ob, bevel_w, segs)
        else:
            shade(ob)
        tag(ob, "door")
        return ob

    # Inner liner panel
    bm = bmesh.new()
    bm_box(bm, (0.031, DOOR_LINER_Y0, 0.118), (DOOR_W - 0.031, DOOR_LINER_Y1, DOOR_Z1 - 0.028))
    child("DoorLiner", bm, liner, 0.003, 2)

    # Gasket ring
    bm = bmesh.new()
    bm_box(bm, (0.010, GASKET_Y0, 0.098), (DOOR_W - 0.010, GASKET_Y1, DOOR_Z1 - 0.008))
    gasket = new_object("DoorGasket", bm, coll, material=rubber, parent=door)
    bm = bmesh.new()
    bm_box(bm, (0.030, GASKET_Y0 - 0.01, 0.118), (DOOR_W - 0.030, GASKET_Y1 + 0.01, DOOR_Z1 - 0.028))
    cut(gasket, bm, coll)
    finish(gasket, 0.003, 2)
    tag(gasket, "door")

    # Door bins (walls 6 mm; Godot's fridge.tscn has matching collision boxes)
    for i, (zb, hgt) in enumerate(BINS):
        x0, x1 = 0.06, DOOR_W - 0.06
        y0, y1 = DOOR_LINER_Y1, BIN_Y1
        w = 0.006
        bm = bmesh.new()
        bm_box(bm, (x0, y0, zb), (x1, y1, zb + w))                       # bottom
        bm_box(bm, (x0, y0, zb + w), (x0 + w, y1, zb + hgt))             # left wall
        bm_box(bm, (x1 - w, y0, zb + w), (x1, y1, zb + hgt))             # right wall
        bm_box(bm, (x0 + w, y1 - w, zb + w), (x1 - w, y1, zb + hgt))     # front wall
        bm_box(bm, (x0, y1 - 0.012, zb + hgt - 0.006), (x1, y1, zb + hgt + 0.002))  # top rim
        child(f"DoorBin{i + 1}", bm, frosted, 0.0015, 1)

    # Handle: vertical bar on two standoffs
    bm = bmesh.new()
    zc = (HANDLE_Z0 + HANDLE_Z1) / 2
    bm_cyl(bm, HANDLE_R, HANDLE_Z1 - HANDLE_Z0, Matrix.Translation((HANDLE_X, HANDLE_Y, zc)), 24)
    for z in (HANDLE_Z0 + 0.05, HANDLE_Z1 - 0.05):
        yc = (DOOR_SKIN_Y0 + HANDLE_Y) / 2
        bm_cyl(bm, 0.009, abs(HANDLE_Y - DOOR_SKIN_Y0) + 0.004, cyl_y((HANDLE_X, yc + 0.002, z)), 16)
    child("Handle", bm, steel, 0.004, 2)

    # Status display: bezel + emissive screen
    bm = bmesh.new()
    bm_box(bm, (0.43, DOOR_SKIN_Y0 - 0.003, 1.60), (0.56, DOOR_SKIN_Y0 + 0.004, 1.66))
    child("DisplayBezel", bm, dark, 0.0015, 2)
    bm = bmesh.new()
    y = DOOR_SKIN_Y0 - 0.0032
    bm_quad(bm, ((0.44, y, 1.61), (0.55, y, 1.61), (0.55, y, 1.65), (0.44, y, 1.65)))
    screen = child("DisplayScreen", bm, display)
    set_uvs(screen, ((0, 0), (1, 0), (1, 1), (0, 1)))

    # A note held by a magnet
    bm = bmesh.new()
    y = DOOR_SKIN_Y0 - 0.0006
    rot = Matrix.Rotation(math.radians(-4.0), 4, "Y")
    center = Vector((0.1375, y, 1.45))
    bm_quad(bm, [center + rot @ Vector((dx, 0.0, dz))
                 for dx, dz in ((-0.0375, -0.05), (0.0375, -0.05), (0.0375, 0.05), (-0.0375, 0.05))])
    child("Note", bm, paper)
    bm = bmesh.new()
    bm_cyl(bm, 0.013, 0.006, cyl_y((0.1375, y - 0.003, 1.49)), 24)
    child("Magnet", bm, magnet, 0.0015, 2)

    # Grip point for the Godot handle
    tag(new_empty("HandleGrip", coll, HANDLE_GRIP, parent=door), "door")
    return door


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("FridgeBody"), get_collection("FridgeBodyCollision"), mats)
    build_door(get_collection("FridgeDoor"), mats)
    body, col, door = part_tris("body"), part_tris("body_col"), part_tris("door")
    print(f"TRIS body={body} collision={col} door={door} total={body + col + door}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
