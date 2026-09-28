"""Generates zones/apartment/apartment.tscn (blockout) from the layout below.

    python tools/blockout/apartment.py

The zone scene is generated: edit this file, not the .tscn. Walls are
declared as lines with openings (doors, windows, archways) and split into
boxes automatically. Replaced piece by piece by Blender geometry later.

Layout (x = east, z = south, window facade faces -Z), interior extents:
    bedroom  x -6.8..-3.2   z -3..2      window north
    living   x -3..3        z -3..2      window north, sofa seat
    kitchen  x  3.2..6.4    z -3..2      window north, archways to living and hallway, trash can
    hallway  x -6.8..6.4    z  2.2..3.6  connects everything, entrance at the east end
    bathroom x -1..2        z  3.8..6.2  no window
    vestibule x 6.6..8.2    z  2.2..3.6  dead end behind the entrance (building corridor in M3)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "zones" / "apartment" / "apartment.tscn"

H = 2.6  # ceiling height
T = 0.2  # wall thickness
DOOR_H = 2.1
SILL, HEAD = 0.4, 2.4  # window opening

MATS = {
    "floor": "blockout_floor", "wall": "blockout_wall", "ceiling": "blockout_ceiling",
    "gunmetal": "gunmetal", "steel": "brushed_steel", "dark": "furniture_dark",
    "sofa": "fabric_sofa", "glass": "window_glass", "magenta": "neon_magenta",
    "cyan": "neon_cyan", "lamp": "ceiling_lamp", "tile": "bathroom_tile",
    "mirror": "mirror", "linen": "bed_linen", "wood": "wood_dark", "ceramic": "ceramic",
}
UNSHADOWED = {"glass", "magenta", "cyan", "lamp"}
SCENES = {
    "door": "res://assets/props/door/door.tscn",
    "ball": "res://assets/props/ball/ball.tscn",
    "can": "res://assets/props/beverage_can/beverage_can.tscn",
    "trash": "res://assets/props/trash_can/trash_can.tscn",
    "fridge": "res://assets/props/fridge/fridge.tscn",
    # Sofa A/B (blind model comparison); keep one after the headset test.
    "sofa_a": "res://assets/props/sofa/sofa__opus-high.tscn",
    "sofa_b": "res://assets/props/sofa/sofa__fable-high.tscn",
    "pillow_a": "res://assets/props/sofa/sofa_pillow__opus-high.tscn",
    "pillow_b": "res://assets/props/sofa/sofa_pillow__fable-high.tscn",
}
SEAT_SCRIPT = "res://core/interaction/seat.gd"

boxes = []  # (group, name, center, size, material, collide)


def box(group, name, center, size, mat, collide=True):
    """collide: True (collision = visual box), False, or (center, size) for a
    different collision box. Use a solid volume for anything the player can
    stand on: XR Tools regrows the body downward after a jump or crouch and
    pushes it through thin plates."""
    if isinstance(collide, tuple):
        collide = (tuple(collide[0]), tuple(collide[1]))
    boxes.append((group, name, tuple(center), tuple(size), mat, collide))


def wall(group, name, axis, line, span, openings=(), mat="wall"):
    """Wall along `axis` ('x' or 'z') at the fixed other coordinate `line`,
    from span[0] to span[1]. openings: (start, end, bottom, top) along the wall."""
    a0, a1 = span
    cuts = sorted(openings)

    def put(n, s, e, y0, y1):
        if e - s < 1e-3 or y1 - y0 < 1e-3:
            return
        mid, length = (s + e) / 2, e - s
        cy, hy = (y0 + y1) / 2, y1 - y0
        if axis == "x":
            box(group, n, (mid, cy, line), (length, hy, T), mat)
        else:
            box(group, n, (line, cy, mid), (T, hy, length), mat)

    cursor, i = a0, 0
    for s, e, bottom, top in cuts:
        put(f"{name}{i}", cursor, s, 0, H)
        put(f"{name}{i}Below", s, e, 0, bottom)
        put(f"{name}{i}Above", s, e, top, H)
        cursor, i = e, i + 1
    put(f"{name}{i}", cursor, a1, 0, H)


def window(group, name, axis, line, s, e, mullion=False, inward=1):
    """Glass pane and interior ledge for a window opening. inward: +1 if the
    room is on the +axis side of the wall line (in the other axis)."""
    mid, w = (s + e) / 2, e - s
    cy, hy = (SILL + HEAD) / 2, HEAD - SILL
    ledge_off = inward * (T / 2 + 0.06)
    if axis == "x":
        box(group, f"{name}Glass", (mid, cy, line), (w, hy, 0.02), "glass")
        box(group, f"{name}Ledge", (mid, SILL + 0.02, line + ledge_off), (w + 0.2, 0.04, 0.14), "gunmetal")
        if mullion:
            box(group, f"{name}Mullion", (mid, cy, line + inward * 0.08), (0.05, hy, 0.05), "gunmetal")
    else:
        box(group, f"{name}Glass", (line, cy, mid), (0.02, hy, w), "glass")
        box(group, f"{name}Ledge", (line + ledge_off, SILL + 0.02, mid), (0.14, 0.04, w + 0.2), "gunmetal")


def door_gap(s, e):
    return (s, e, 0.0, DOOR_H)


def window_gap(s, e):
    return (s, e, SILL, HEAD)


# --- Shell -----------------------------------------------------------------
box("Shell", "Floor", (-0.2, -0.1, 0.3), (13.6, 0.2, 7.0), "floor")
box("Shell", "Ceiling", (-0.2, H + 0.1, 0.3), (13.6, 0.2, 7.0), "ceiling")
box("Shell", "BathFloor", (0.5, -0.1, 5.1), (3.4, 0.2, 2.6), "tile")
box("Shell", "BathCeiling", (0.5, H + 0.1, 5.1), (3.4, 0.2, 2.6), "ceiling")

wall("Shell", "North", "x", -3.1, (-7.0, 6.6), [
    window_gap(-6.3, -3.7), window_gap(-2.5, 2.5), window_gap(3.6, 5.5)])
window("Shell", "BedroomWindow", "x", -3.1, -6.3, -3.7)
window("Shell", "LivingWindow", "x", -3.1, -2.5, 2.5, mullion=True)
window("Shell", "KitchenWindow", "x", -3.1, 3.6, 5.5)
wall("Shell", "West", "z", -6.9, (-3.2, 3.8))
wall("Shell", "East", "z", 6.5, (-3.2, 3.8), [door_gap(2.45, 3.35)])
wall("Shell", "BedroomLiving", "z", -3.1, (-3.0, 2.0))
wall("Shell", "LivingKitchen", "z", 3.1, (-3.0, 2.0), [door_gap(-1.2, 0.6)])
wall("Shell", "HallNorth", "x", 2.1, (-7.0, 6.6), [
    door_gap(-4.4, -3.5), door_gap(1.6, 2.5), door_gap(4.2, 5.2)])
wall("Shell", "HallSouth", "x", 3.7, (-7.0, 6.6), [door_gap(0.1, 1.0)])
wall("Shell", "BathWest", "z", -1.1, (3.8, 6.2))
wall("Shell", "BathEast", "z", 2.1, (3.8, 6.2))
wall("Shell", "BathSouth", "x", 6.3, (-1.2, 2.2))

# Vestibule behind the entrance (placeholder for the M3 building corridor).
box("Vestibule", "VestFloor", (7.4, -0.1, 2.9), (1.8, 0.2, 1.6), "floor")
box("Vestibule", "VestCeiling", (7.4, H + 0.1, 2.9), (1.8, 0.2, 1.6), "ceiling")
wall("Vestibule", "VestNorth", "x", 2.1, (6.6, 8.4))
wall("Vestibule", "VestSouth", "x", 3.7, (6.6, 8.4))
wall("Vestibule", "VestEnd", "z", 8.3, (2.2, 3.6))
box("Vestibule", "VestSign", (8.19, 2.2, 2.9), (0.02, 0.12, 0.6), "cyan", False)

# --- Living room -----------------------------------------------------------
box("Living", "TableTop", (1.1, 0.73, -1.3), (1.0, 0.04, 0.6), "dark", ((1.1, 0.375, -1.3), (1.0, 0.75, 0.6)))
box("Living", "TablePedestal", (1.1, 0.36, -1.3), (0.1, 0.7, 0.1), "steel", False)
box("Living", "TableBase", (1.1, 0.01, -1.3), (0.5, 0.02, 0.4), "steel", False)
box("Living", "Shelf", (-2.86, 1.1, -1.5), (0.28, 0.03, 1.2), "gunmetal")
box("Living", "ShelfLip", (-2.73, 1.14, -1.5), (0.02, 0.05, 1.2), "gunmetal")
box("Living", "NeonStrip", (-2.99, 2.2, -0.2), (0.02, 0.03, 1.6), "magenta", False)
box("Living", "LampDisc", (0, 2.585, -0.5), (0.6, 0.03, 0.6), "lamp", False)

# --- Kitchen ---------------------------------------------------------------
box("Kitchen", "CounterBody", (6.1, 0.44, -0.5), (0.6, 0.88, 3.4), "dark")
box("Kitchen", "CounterTop", (6.08, 0.9, -0.5), (0.64, 0.04, 3.44), "steel")
box("Kitchen", "Backsplash", (6.39, 1.25, -0.5), (0.02, 0.6, 3.4), "ceramic", False)
box("Kitchen", "CounterNeon", (6.37, 1.56, -0.5), (0.02, 0.02, 3.2), "cyan", False)
box("Kitchen", "TableTop", (4.4, 0.73, -1.0), (0.9, 0.04, 0.9), "wood", ((4.4, 0.375, -1.0), (0.9, 0.75, 0.9)))
box("Kitchen", "TablePedestal", (4.4, 0.36, -1.0), (0.1, 0.7, 0.1), "steel", False)
box("Kitchen", "TableBase", (4.4, 0.01, -1.0), (0.5, 0.02, 0.5), "steel", False)
box("Kitchen", "LampDisc", (4.8, 2.585, -0.5), (0.5, 0.03, 0.5), "lamp", False)

# --- Bedroom ---------------------------------------------------------------
box("Bedroom", "BedFrame", (-5.75, 0.15, -0.9), (2.1, 0.3, 1.6), "wood")
box("Bedroom", "Mattress", (-5.7, 0.4, -0.9), (2.0, 0.2, 1.5), "linen")
box("Bedroom", "Pillow", (-6.5, 0.56, -0.9), (0.35, 0.12, 1.2), "linen")
box("Bedroom", "Headboard", (-6.76, 0.55, -0.9), (0.08, 1.1, 1.6), "wood")
box("Bedroom", "Nightstand", (-6.5, 0.25, 0.35), (0.45, 0.5, 0.4), "wood")
box("Bedroom", "Wardrobe", (-5.9, 1.05, 1.68), (1.5, 2.1, 0.6), "dark")
box("Bedroom", "BedNeon", (-6.79, 1.7, -0.9), (0.02, 0.03, 1.4), "cyan", False)
box("Bedroom", "LampDisc", (-5.0, 2.585, -0.5), (0.5, 0.03, 0.5), "lamp", False)

# --- Bathroom --------------------------------------------------------------
box("Bathroom", "SinkCabinet", (1.75, 0.425, 5.0), (0.5, 0.85, 0.8), "ceramic")
box("Bathroom", "Mirror", (1.99, 1.45, 5.0), (0.02, 0.7, 0.6), "mirror", False)
box("Bathroom", "ToiletBase", (-0.75, 0.21, 5.85), (0.4, 0.42, 0.55), "ceramic")
box("Bathroom", "ToiletTank", (-0.75, 0.62, 6.1), (0.4, 0.4, 0.18), "ceramic")
box("Bathroom", "ShowerTray", (-0.55, 0.03, 4.3), (0.9, 0.06, 0.9), "ceramic")
box("Bathroom", "ShowerHead", (-0.55, 2.2, 4.0), (0.15, 0.03, 0.15), "steel", False)
box("Bathroom", "LampDisc", (0.5, 2.585, 5.0), (0.4, 0.03, 0.4), "lamp", False)

# --- Hallway ---------------------------------------------------------------
box("Hallway", "ShoeBench", (4.6, 0.225, 3.4), (0.9, 0.45, 0.35), "wood")
for i, x in enumerate((-4.5, 0.0, 4.5)):
    box("Hallway", f"LampDisc{i}", (x, 2.585, 2.9), (0.3, 0.03, 0.3), "lamp", False)

# --- Instances -------------------------------------------------------------
# Doors: origin at the hinge; leaf extends along local +X and opens toward local -Z.
INSTANCES = [
    ("DoorLiving", "door", (1.62, 0, 1.98), (0, 0, 0)),
    ("DoorBedroom", "door", (-4.38, 0, 1.98), (0, 0, 0)),
    ("DoorBathroom", "door", (0.98, 0, 3.82), (0, 180, 0)),
    ("DoorEntrance", "door", (6.38, 0, 3.33), (0, 90, 0)),
    ("TrashCan", "trash", (6.15, 0, 1.6), (0, 0, 0)),
    # Origin bottom center of the cabinet, front +Z, hinge on local -X: NE corner, faces west, hinge north.
    ("Fridge", "fridge", (6.055, 0, -2.53), (0, -90, 0)),
    # Sofas: origin bottom center, front +Z. A: living room, faces the window. B: west wall, faces east.
    ("SofaA", "sofa_a", (-1.6, 0, 0.9), (0, 180, 0)),
    ("SofaB", "sofa_b", (-2.54, 0, -1.15), (0, 90, 0)),
    # Throw pillows leaning on the back cushions (pickable; they settle when the game starts).
    ("PillowA1", "pillow_a", (-0.88, 0.68, 0.9), (74, 170, 0)),
    ("PillowA2", "pillow_a", (-2.30, 0.68, 0.9), (74, 190, 0)),
    ("PillowB1", "pillow_b", (-2.54, 0.68, -0.43), (74, 80, 0)),
    ("PillowB2", "pillow_b", (-2.54, 0.68, -1.85), (74, 100, 0)),
    ("Ball", "ball", (-2.84, 1.22, -1.8), (0, 0, 0)),
    ("CanLivingTable", "can", (1.25, 0.812, -1.25), (0, 0, 0)),
    ("CanWindowLedge", "can", (-1.2, 0.502, -2.94), (0, 0, 0)),
    ("CanCounter", "can", (6.0, 0.982, 0.3), (0, 0, 0)),
    ("CanKitchenTable", "can", (4.3, 0.812, -1.1), (0, 0, 0)),
    ("CanNightstand", "can", (-6.5, 0.562, 0.35), (0, 0, 0)),
    ("CanSink", "can", (1.7, 0.912, 4.75), (0, 0, 0)),
]

# Seats: name, area center, area size, sit eye point, sit yaw, stand point, stand yaw, prompt pos
SEATS = [
    ("SofaSeat", (-1.6, 1.0, 0.15), (2.2, 2.0, 1.2), (-1.6, 1.15, 0.85), 0, (-1.6, 0, 0.1), 0, (-1.6, 0.9, 0.9)),
    ("SofaBSeat", (-1.75, 1.0, -1.15), (1.2, 2.0, 1.4), (-2.39, 1.15, -1.15), -90, (-1.79, 0, -1.15), -90, (-2.24, 0.9, -1.15)),
    ("BedSeat", (-5.3, 1.0, -2.25), (1.6, 2.0, 1.3), (-5.3, 1.2, -1.5), 0, (-5.3, 0, -2.3), 0, (-5.3, 0.85, -1.6)),
]

LIGHTS = [
    # name, type, position, rotation, color, energy, range, shadow, extra
    ("LivingCeiling", "Omni", (0, 2.45, -0.5), None, (1, 0.77, 0.56), 1.4, 6.5, True, "omni_attenuation = 1.2\n"),
    ("LivingNeonSpill", "Omni", (-2.8, 2.1, -0.2), None, (1, 0.165, 0.427), 0.35, 2.5, False, ""),
    ("LivingCitySpill", "Spot", (0, 2.2, -5.5), (-12, 180, 0), (0.45, 0.55, 1), 1.6, 12, False, "spot_angle = 55.0\nspot_angle_attenuation = 1.5\n"),
    ("KitchenCeiling", "Omni", (4.8, 2.45, -0.5), None, (1, 0.88, 0.75), 1.0, 4.5, False, ""),
    ("KitchenCounter", "Omni", (6.0, 1.5, -0.5), None, (0.6, 0.9, 1), 0.35, 2.0, False, ""),
    ("KitchenCitySpill", "Spot", (4.55, 2.2, -5.0), (-12, 180, 0), (0.45, 0.55, 1), 1.0, 10, False, "spot_angle = 45.0\nspot_angle_attenuation = 1.5\n"),
    ("BedroomCeiling", "Omni", (-5.0, 2.45, -0.5), None, (1, 0.72, 0.5), 0.7, 4.5, False, ""),
    ("BedroomLamp", "Omni", (-6.45, 0.85, 0.35), None, (1, 0.65, 0.4), 0.4, 1.8, False, ""),
    ("BedroomCitySpill", "Spot", (-5.0, 2.2, -5.0), (-12, 180, 0), (0.55, 0.45, 1), 1.0, 10, False, "spot_angle = 45.0\nspot_angle_attenuation = 1.5\n"),
    ("Hall0", "Omni", (-4.5, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("Hall1", "Omni", (0.0, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("Hall2", "Omni", (4.5, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("BathCeiling", "Omni", (0.5, 2.4, 5.0), None, (0.9, 0.95, 1), 0.9, 3.5, False, ""),
    ("VestibuleLight", "Omni", (7.4, 2.35, 2.9), None, (0.6, 0.85, 1), 0.4, 2.2, False, ""),
]

PROBES = [
    # name, center, size
    ("LivingProbe", (0, 1.3, -0.5), (6.2, 2.7, 5.2)),
    ("KitchenProbe", (4.8, 1.3, -0.5), (3.4, 2.7, 5.2)),
    ("BedroomProbe", (-5.0, 1.3, -0.5), (3.8, 2.7, 5.2)),
    ("HallwayProbe", (-0.2, 1.3, 2.9), (13.4, 2.7, 1.6)),
    ("BathroomProbe", (0.5, 1.3, 5.0), (3.2, 2.7, 2.6)),
]

ENTRIES = [
    ("Default", (0.4, 0, -0.4), 0),
    ("Entrance", (7.4, 0, 2.9), 90),
]

# Perf flythrough through every room (eye height 1.7, yaw 0 = -Z, 90 = -X, 180 = +Z, -90 = +X).
PERF_PATH = [
    ((0.4, 1.7, -0.4), (0, 0, 0)),
    ((0.0, 1.7, -2.3), (-12, 0, 0)),
    ((2.3, 1.7, -0.3), (0, -90, 0)),
    ((4.6, 1.7, -1.0), (-5, -30, 0)),
    ((4.7, 1.7, 1.4), (0, 180, 0)),
    ((4.7, 1.7, 2.9), (0, 90, 0)),
    ((0.55, 1.7, 2.9), (0, 180, 0)),
    ((0.5, 1.7, 4.8), (-10, 200, 0)),
    ((0.55, 1.7, 2.9), (0, 90, 0)),
    ((-3.95, 1.7, 2.9), (0, 0, 0)),
    ((-3.95, 1.7, 1.5), (0, 20, 0)),
    ((-5.0, 1.7, -1.8), (-5, 30, 0)),
]


# --- Writer ----------------------------------------------------------------
def v3(t):
    return "Vector3(%s)" % ", ".join(f"{c:g}" for c in t)


def color(t):
    return "Color(%s, 1)" % ", ".join(f"{c:g}" for c in t)


def main():
    ext, subs, nodes, ids = [], [], [], {}

    def add_ext(key, typ, path):
        ids[key] = f"{len(ids) + 1}_{key}"
        ext.append(f'[ext_resource type="{typ}" path="{path}" id="{ids[key]}"]')

    for key, name in MATS.items():
        add_ext(key, "Material", f"res://assets/materials/{name}.tres")
    for key, path in SCENES.items():
        add_ext(key, "PackedScene", path)
    add_ext("seat", "Script", SEAT_SCRIPT)

    sizes = {}
    all_sizes = [b[3] for b in boxes] + [b[5][1] for b in boxes if isinstance(b[5], tuple)]
    for size in all_sizes:
        if size not in sizes:
            sid = f"s{len(sizes)}"
            sizes[size] = sid
            subs.append(f'[sub_resource type="BoxMesh" id="BoxMesh_{sid}"]\nsize = {v3(size)}\n')
            subs.append(f'[sub_resource type="BoxShape3D" id="BoxShape3D_{sid}"]\nsize = {v3(size)}\n')
    seat_shapes = {}
    for seat in SEATS:
        sid = f"seat{len(seat_shapes)}"
        seat_shapes[seat[0]] = sid
        subs.append(f'[sub_resource type="BoxShape3D" id="BoxShape3D_{sid}"]\nsize = {v3(seat[2])}\n')

    nodes.append('[node name="Apartment" type="Node3D"]\n'
                 'metadata/_doc = "Zone: apartment (bedroom, living room, kitchen, hallway, bathroom). '
                 'GENERATED by tools/blockout/apartment.py; edit that, not this file. Floor y 0, ceiling 2.6 m, '
                 'window facade faces -Z."\n')

    groups = list(dict.fromkeys(g for g, *_ in boxes))
    for g in groups:
        nodes.append(f'[node name="{g}" type="StaticBody3D" parent="."]\n')
        for gg, name, center, size, mat, collide in boxes:
            if gg != g:
                continue
            sid = sizes[size]
            shadow = "cast_shadow = 0\n" if mat in UNSHADOWED else ""
            nodes.append(
                f'[node name="{name}" type="MeshInstance3D" parent="{g}"]\n'
                f"position = {v3(center)}\n{shadow}"
                f'mesh = SubResource("BoxMesh_{sid}")\n'
                f'surface_material_override/0 = ExtResource("{ids[mat]}")\n')
            if collide:
                col_center, col_size = collide if isinstance(collide, tuple) else (center, size)
                nodes.append(
                    f'[node name="{name}Collision" type="CollisionShape3D" parent="{g}"]\n'
                    f"position = {v3(col_center)}\n"
                    f'shape = SubResource("BoxShape3D_{sizes[col_size]}")\n')

    nodes.append('[node name="Props" type="Node3D" parent="."]\n')
    for name, key, pos, rot in INSTANCES:
        rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
        nodes.append(f'[node name="{name}" parent="Props" instance=ExtResource("{ids[key]}")]\n'
                     f"position = {v3(pos)}\n{rot_line}")

    nodes.append('[node name="Seats" type="Node3D" parent="."]\n')
    for name, center, size, sit, sit_yaw, stand, stand_yaw, prompt in SEATS:
        nodes.append(
            f'[node name="{name}" type="Area3D" parent="Seats" node_paths=PackedStringArray("sit_point", "stand_point", "prompt")]\n'
            f"collision_layer = 0\ncollision_mask = 524288\nmonitorable = false\n"
            f'script = ExtResource("{ids["seat"]}")\n'
            f'sit_point = NodePath("../{name}Sit")\nstand_point = NodePath("../{name}Stand")\nprompt = NodePath("../{name}Prompt")\n')
        nodes.append(f'[node name="CollisionShape3D" type="CollisionShape3D" parent="Seats/{name}"]\n'
                     f"position = {v3(center)}\n"
                     f'shape = SubResource("BoxShape3D_{seat_shapes[name]}")\n')
        nodes.append(f'[node name="{name}Sit" type="Marker3D" parent="Seats"]\nposition = {v3(sit)}\n'
                     + (f"rotation_degrees = Vector3(0, {sit_yaw}, 0)\n" if sit_yaw else ""))
        nodes.append(f'[node name="{name}Stand" type="Marker3D" parent="Seats"]\nposition = {v3(stand)}\n'
                     + (f"rotation_degrees = Vector3(0, {stand_yaw}, 0)\n" if stand_yaw else ""))
        nodes.append(f'[node name="{name}Prompt" type="Label3D" parent="Seats"]\nposition = {v3(prompt)}\n'
                     'pixel_size = 0.0015\nbillboard = 1\nmodulate = Color(0.02, 0.85, 0.91, 1)\n'
                     'outline_modulate = Color(0, 0, 0, 0.6)\nfont_size = 48\n'
                     'text = "X  ·  sit"\n')

    nodes.append('[node name="Lighting" type="Node3D" parent="."]\n')
    for name, kind, pos, rot, col, energy, rng, shadow, extra in LIGHTS:
        typ = "OmniLight3D" if kind == "Omni" else "SpotLight3D"
        range_key = "omni_range" if kind == "Omni" else "spot_range"
        rot_line = f"rotation_degrees = {v3(rot)}\n" if rot else ""
        shadow_line = "shadow_enabled = true\n" if shadow else ""
        nodes.append(f'[node name="{name}" type="{typ}" parent="Lighting"]\nposition = {v3(pos)}\n{rot_line}'
                     f"light_color = {color(col)}\nlight_energy = {energy:g}\n{shadow_line}"
                     f"{range_key} = {rng:g}\n{extra}")
    for name, center, size in PROBES:
        nodes.append(f'[node name="{name}" type="ReflectionProbe" parent="Lighting"]\nposition = {v3(center)}\n'
                     f"size = {v3(size)}\nbox_projection = true\ninterior = true\nambient_mode = 0\n")

    nodes.append('[node name="Entries" type="Node3D" parent="."]\n')
    for name, pos, yaw in ENTRIES:
        nodes.append(f'[node name="{name}" type="Marker3D" parent="Entries"]\nposition = {v3(pos)}\n'
                     + (f"rotation_degrees = Vector3(0, {yaw}, 0)\n" if yaw else ""))

    nodes.append('[node name="PerfPath" type="Node3D" parent="."]\n'
                 'metadata/_doc = "Perf flythrough waypoints at eye height, visited in order; -Z is the view direction. See tools/perf."\n')
    for i, (pos, rot) in enumerate(PERF_PATH):
        rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
        nodes.append(f'[node name="P{i}" type="Marker3D" parent="PerfPath"]\nposition = {v3(pos)}\n{rot_line}')

    text = "[gd_scene format=3]\n\n" + "\n".join(ext) + "\n\n" + "\n".join(subs) + "\n" + "\n".join(nodes)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(boxes)} boxes, {len(sizes)} sizes, "
          f"{len(LIGHTS)} lights, {len(PROBES)} probes, {len(SEATS)} seats")


if __name__ == "__main__":
    main()
