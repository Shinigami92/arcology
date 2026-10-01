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

Windows (D-033) come from tools/props/windows/apartment.json, the spec shared with
Blender and tools/props/window.py: the openings are cut from it and the generated
window scenes are placed in them (WINDOWS below). Regenerate the window scenes with
python tools/props/window.py.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "zones" / "apartment" / "apartment.tscn"
sys.path.insert(0, str(ROOT / "tools" / "props"))
import window as window_specs  # noqa: E402  (tools/props/window.py)
from prop_scenes import glb_bounds  # noqa: E402
import skirting  # noqa: E402  (tools/blockout/skirting.py)

H = 2.6  # ceiling height
T = 0.2  # wall thickness
DOOR_H = 2.1
NORTH = -3.1  # window wall line (the facade faces -Z)

# Window placements: spec name -> node name, opening center x on the north wall, room
# spill light it dims (WindowLight). Opening size and sill come from the spec.
WINDOWS = [
    ("apartment_bedroom", "BedroomWindow", -5.0, "BedroomCitySpill"),
    ("apartment_living", "LivingWindow", 0.0, "LivingCitySpill"),
    ("apartment_kitchen", "KitchenWindow", 4.55, "KitchenCitySpill"),
]
WINDOW_LIGHT_SCRIPT = "res://core/interaction/window_light.gd"

MATS = {
    "vinyl": "vinyl_plank", "carpet": "carpet", "concrete": "polished_concrete",
    "wall": "wall_plaster", "ceiling": "ceiling_plaster",
    "gunmetal": "gunmetal", "steel": "brushed_steel", "dark": "furniture_dark",
    "sofa": "fabric_sofa", "magenta": "neon_magenta",
    "cyan": "neon_cyan", "lamp": "ceiling_lamp",
    "mirror": "mirror", "linen": "bed_linen", "wood": "wood_dark", "ceramic": "ceramic",
}
UNSHADOWED = {"magenta", "cyan", "lamp"}
SCENES = {
    "door": "res://assets/props/door_interior/door_interior.tscn",
    "door_bath": "res://assets/props/door_interior/door_interior_bath.tscn",
    "door_entrance": "res://assets/props/door_entrance/door_entrance.tscn",
    "ball": "res://assets/props/ball/ball.tscn",
    "can": "res://assets/props/beverage_can/beverage_can.tscn",
    "trash": "res://assets/props/trash_can/trash_can.tscn",
    "fridge": "res://assets/props/fridge/fridge.tscn",
    "sofa": "res://assets/props/sofa/sofa.tscn",
    "pillow": "res://assets/props/sofa/sofa_pillow.tscn",
    "bed": "res://assets/props/bed/bed.tscn",
    "wardrobe": "res://assets/props/wardrobe/wardrobe.tscn",
    "nightstand": "res://assets/props/nightstand/nightstand.tscn",
    "rain_debug": "res://core/debug/rain_debug_button.tscn",
}
SEAT_SCRIPT = "res://core/interaction/seat.gd"
AB_SCRIPT = "res://core/debug/ab_switch.gd"

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


def door_gap(s, e):
    return (s, e, 0.0, DOOR_H)


def window_gap(spec_name, x):
    """The wall cut for a window spec centered at x (along the wall)."""
    x0, x1, y0, y1 = window_specs.opening(*window_specs.spec(spec_name))
    return (x + x0, x + x1, y0, y1)


# --- Shell -----------------------------------------------------------------
# Floors split at the wall center lines: vinyl in the living room, kitchen and hallway,
# fitted carpet in the bedroom (edge under its door), polished concrete in the bathroom.
box("Shell", "Floor", (1.75, -0.1, 0.3), (9.7, 0.2, 7.0), "vinyl")
box("Shell", "HallWestFloor", (-5.05, -0.1, 2.95), (3.9, 0.2, 1.7), "vinyl")
box("Shell", "BedroomFloor", (-5.05, -0.1, -0.55), (3.9, 0.2, 5.3), "carpet")
box("Shell", "Ceiling", (-0.2, H + 0.1, 0.3), (13.6, 0.2, 7.0), "ceiling")
box("Shell", "BathFloor", (0.5, -0.1, 5.1), (3.4, 0.2, 2.6), "concrete")
box("Shell", "BathCeiling", (0.5, H + 0.1, 5.1), (3.4, 0.2, 2.6), "ceiling")

wall("Shell", "North", "x", NORTH, (-7.0, 6.6), [window_gap(spec, x) for spec, _, x, _ in WINDOWS])
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
box("Vestibule", "VestFloor", (7.4, -0.1, 2.9), (1.8, 0.2, 1.6), "vinyl")
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
# Doors (frame + leaf): origin at the opening's bottom center on the wall's center plane, the leaf opens toward
# local +Z (into the room), hinge on the local -X jamb.
INSTANCES = [
    ("DoorLiving", "door", (2.05, 0, 2.1), (0, 180, 0)),
    ("DoorBedroom", "door", (-3.95, 0, 2.1), (0, 180, 0)),
    ("DoorBathroom", "door_bath", (0.55, 0, 3.7), (0, 0, 0)),
    ("DoorEntrance", "door_entrance", (6.5, 0, 2.9), (0, -90, 0)),
    ("TrashCan", "trash", (6.15, 0, 1.6), (0, 0, 0)),
    # Origin bottom center of the cabinet, front +Z, hinge on local -X: NE corner, faces west, hinge north.
    ("Fridge", "fridge", (6.055, 0, -2.53), (0, -90, 0)),
    # Sofa: origin bottom center, front +Z; faces the window.
    ("Sofa", "sofa", (-1.6, 0, 0.9), (0, 180, 0)),
    # Throw pillows leaning on the back cushions (pickable; they settle when the game starts).
    ("SofaPillow1", "pillow", (-0.88, 0.68, 0.9), (74, 170, 0)),
    ("SofaPillow2", "pillow", (-2.30, 0.68, 0.9), (74, 190, 0)),
    ("Ball", "ball", (-2.84, 1.22, -1.8), (0, 0, 0)),
    ("CanLivingTable", "can", (1.25, 0.812, -1.25), (0, 0, 0)),
    ("CanWindowLedge", "can", (-5.6, 0.465, -3.02), (0, 0, 0)),
    ("CanCounter", "can", (6.0, 0.982, 0.3), (0, 0, 0)),
    ("CanKitchenTable", "can", (4.3, 0.812, -1.1), (0, 0, 0)),
    ("CanNightstand", "can", (-6.5, 0.612, 0.45), (0, 0, 0)),
    # Bedroom: bed head (-Z) against the west wall; wardrobe against the hallway wall, facing north;
    # nightstand on the west wall next to the bed head, facing east (it carries its lamp and light).
    ("Bed", "bed", (-5.70, 0, -0.9), (0, 90, 0)),
    ("Wardrobe", "wardrobe", (-5.9, 0, 1.70), (0, 180, 0)),
    ("Nightstand", "nightstand", (-6.60, 0, 0.35), (0, 90, 0)),
    ("CanSink", "can", (1.7, 0.912, 4.75), (0, 0, 0)),
    # Temporary rain debug button (D-034), on the wall west of the living room window panel.
    ("RainDebugButton", "rain_debug", (-2.74, 1.2, -3.0), (0, 0, 0)),
]

# Blind A/B pairs (core/debug/ab_switch.gd): name, scene A, scene B, position, rotation.
# Add an ABPanel (assets/props/ab_panel) to INSTANCES to flip them. Empty outside an A/B test (D-030, D-032).
AB_INSTANCES = []

# Seats: name, area center, area size, sit eye point, sit yaw, stand point, stand yaw, prompt pos
SEATS = [
    ("SofaSeat", (-1.6, 1.0, 0.15), (2.2, 2.0, 1.2), (-1.6, 1.15, 0.85), 0, (-1.6, 0, 0.1), 0, (-1.6, 0.9, 0.9)),
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
    ("BedroomCitySpill", "Spot", (-5.0, 2.2, -5.0), (-12, 180, 0), (0.55, 0.45, 1), 1.0, 10, False, "spot_angle = 45.0\nspot_angle_attenuation = 1.5\n"),
    ("Hall0", "Omni", (-4.5, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("Hall1", "Omni", (0.0, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("Hall2", "Omni", (4.5, 2.4, 2.9), None, (0.75, 0.88, 1), 0.45, 3.0, False, ""),
    ("BathCeiling", "Omni", (0.5, 2.4, 5.0), None, (0.9, 0.95, 1), 0.9, 3.5, False, ""),
    ("VestibuleLight", "Omni", (7.4, 2.35, 2.9), None, (0.6, 0.85, 1), 0.4, 2.2, False, ""),
]

PROBES = [
    # name, center, size
    # Room probes reach 1.2 m past the window wall: the glass (z -3.15) is inside their 1 m
    # blend distance and reflects the room at full weight.
    ("LivingProbe", (0, 1.3, -1.1), (6.2, 2.7, 6.4)),
    ("KitchenProbe", (4.8, 1.3, -1.1), (3.4, 2.7, 6.4)),
    ("BedroomProbe", (-5.0, 1.3, -1.1), (3.8, 2.7, 6.4)),
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


# --- Skirting (D-036) -------------------------------------------------------
# Runs along the foot of every wall, written to SKIRTING_JSON for the Blender build
# (blender/architecture/skirting/), which sweeps the profile along them into SKIRTING_GLB.
# They stop at door frames and floor-level window frames; archway reveals keep them.
SKIRTING_JSON = ROOT / "tools" / "blockout" / "apartment_skirting.json"
SKIRTING_GLB = "assets/architecture/skirting/apartment_skirting.glb"
SKIRTING_PROFILE = {"height": 0.08, "thickness": 0.01}
SKIRTING_SKIP = [
    (-1.0, 3.8, 2.0, 6.2),   # bathroom: wet room, gets its own wall finish later
    (6.6, 2.0, 8.5, 3.8),    # vestibule: building corridor placeholder (M3)
]
# Instance keys whose frame glb cuts the skirting (frame origin = the instance origin).
FRAMES = {
    "door": "assets/props/door_interior/door_interior_frame.glb",
    "door_bath": "assets/props/door_interior/door_interior_frame.glb",
    "door_entrance": "assets/props/door_entrance/door_entrance_frame.glb",
}


def _footprint(center, size):
    return (center[0] - size[0] / 2, center[2] - size[2] / 2, center[0] + size[0] / 2, center[2] + size[2] / 2)


def _placed_bounds(glb, pos, yaw, pad=0.0):
    """World (x0, z0, x1, z1) of a glb's bounds placed at pos with a yaw (multiples of 90)."""
    lo, hi = glb_bounds(glb)
    c, s = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
    xs, zs = [], []
    for x in (lo[0], hi[0]):
        for z in (lo[2], hi[2]):
            xs.append(pos[0] + x * c + z * s)
            zs.append(pos[2] - x * s + z * c)
    return (min(xs) - pad, min(zs) - pad, max(xs) + pad, max(zs) + pad)


def skirting_runs():
    floors = [_footprint(c, sz) for _, _, c, sz, mat, _ in boxes if mat in ("vinyl", "carpet", "concrete")]
    blocked = [_footprint(c, sz) for _, _, c, sz, mat, _ in boxes if mat == "wall" and c[1] - sz[1] / 2 < 1e-6]
    cuts = []
    for spec, _, x, _ in WINDOWS:
        x0, x1, bottom, _ = window_gap(spec, x)
        blocked.append((x0, NORTH - T / 2, x1, NORTH + T / 2))  # glass, not a doorway
        if bottom < 1e-6:
            # Floor-level window: the frame is flush with the wall face at the opening edges (its
            # flange beyond them sits in the wall), so the boards end at the opening.
            cuts.append((x0, NORTH - T / 2, x1, NORTH + T / 2 + 0.05))
    for _, key, pos, rot in INSTANCES:
        if key in FRAMES:
            cuts.append(_placed_bounds(FRAMES[key], pos, rot[1]))
    return skirting.runs(floors, blocked + SKIRTING_SKIP, cuts)


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
    for spec, _, _, _ in WINDOWS:
        add_ext(spec, "PackedScene", "res://" + window_specs.paths(spec)["tscn"])
    add_ext("window_light", "Script", WINDOW_LIGHT_SCRIPT)
    if (ROOT / SKIRTING_GLB).exists():
        add_ext("skirting", "PackedScene", "res://" + SKIRTING_GLB)
    if AB_INSTANCES:
        add_ext("ab", "Script", AB_SCRIPT)

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

    nodes.append('[node name="Windows" type="Node3D" parent="."]\n'
                 'metadata/_doc = "Generated window scenes (tools/props/window.py) in the north wall openings."\n')
    for spec, name, x, _ in WINDOWS:
        nodes.append(f'[node name="{name}" parent="Windows" instance=ExtResource("{ids[spec]}")]\n'
                     f"position = {v3((x, 0, NORTH))}\n")

    if (ROOT / SKIRTING_GLB).exists():
        nodes.append('[node name="Trim" type="Node3D" parent="."]\n'
                     'metadata/_doc = "Skirting boards along the walls (D-036), swept in Blender along '
                     'tools/blockout/apartment_skirting.json."\n')
        nodes.append(f'[node name="Skirting" parent="Trim" instance=ExtResource("{ids["skirting"]}")]\n')

    nodes.append('[node name="Props" type="Node3D" parent="."]\n')
    for name, key, pos, rot in INSTANCES:
        rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
        nodes.append(f'[node name="{name}" parent="Props" instance=ExtResource("{ids[key]}")]\n'
                     f"position = {v3(pos)}\n{rot_line}")
    for name, key_a, key_b, pos, rot in AB_INSTANCES:
        rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
        nodes.append(f'[node name="{name}" type="Node3D" parent="Props"]\nposition = {v3(pos)}\n{rot_line}'
                     f'script = ExtResource("{ids["ab"]}")\n')
        for variant, key in (("A", key_a), ("B", key_b)):
            nodes.append(f'[node name="{variant}" parent="Props/{name}" instance=ExtResource("{ids[key]}")]\n')

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
    for _, name, _, light in WINDOWS:
        room = name.removesuffix("Window")
        nodes.append(f'[node name="{room}WindowLight" type="Node" parent="Lighting" '
                     'node_paths=PackedStringArray("light", "glass", "shade")]\n'
                     f'script = ExtResource("{ids["window_light"]}")\n'
                     f'light = NodePath("../{light}")\n'
                     f'glass = NodePath("../../Windows/{name}/SmartGlass")\n'
                     f'shade = NodePath("../../Windows/{name}/Shade")\n')
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

    run_list = skirting_runs()
    skirting.write(SKIRTING_JSON, SKIRTING_PROFILE, run_list,
                   "GENERATED by tools/blockout/apartment.py (see tools/blockout/skirting.py for the format).")

    text = "[gd_scene format=3]\n\n" + "\n".join(ext) + "\n\n" + "\n".join(subs) + "\n" + "\n".join(nodes)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(boxes)} boxes, {len(sizes)} sizes, "
          f"{len(LIGHTS)} lights, {len(PROBES)} probes, {len(SEATS)} seats, {len(run_list)} skirting runs")


if __name__ == "__main__":
    main()
