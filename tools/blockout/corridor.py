"""Generates zones/corridor/corridor.tscn (blockout) from the layout below (D-059).

    python tools/blockout/corridor.py [--check]

Floor 44's corridors, the first zone outside the apartment, streamed in by ZoneStreamer
(zones/zone_graph.json). The zone scene is generated: edit this file, not the .tscn.
Written by tools/blockout/blockout.py (shell, occluders, window notifiers, bounds, props,
signs, lights, probes, entries, perf path).

Layout (x = east, z = south, the facade faces -Z), interior extents:
    side corridor  x  6.6..8.8   z -3.0..7.0   from the facade window (north) past our entrance
                                               (west wall, 4417) and two neighbors (east wall)
    main corridor  x -7.0..21.0  z  7.0..9.4   behind the units: four doors south, service north,
                                               stairs at the west end
    elevator lobby x 11.0..15.0  z  9.6..12.0  off the main corridor's south side, two elevators

The side corridor's west wall is the apartment's east wall (line x 6.5). The corridor has its
own copy of it (same line, same door gap), so it stays closed while the apartment isn't loaded;
both are world-mapped plaster (D-035), so where they overlap they look the same.

Elevators, call buttons and the stairs are static placeholders until the elevator step (M3).
Signs and unit numbers are Label3D placeholders until the world directory (roadmap).
"""

import math
import sys

import skirting  # noqa: E402  (tools/blockout/skirting.py)
from blockout import FLOOR_MATS, ROOT, T, Zone, door_gap
from prop_scenes import glb_bounds  # noqa: E402  (tools/props/prop_scenes.py, on the path via blockout)

H = 2.8  # ceiling height
NORTH = -3.1  # facade wall line (the apartment's window wall)
WEST = 6.5  # side corridor west wall line = the apartment's east wall
EAST = 8.9  # side corridor east wall line
MAIN_N, MAIN_S = 6.9, 9.5  # main corridor wall lines
MAIN_W, MAIN_E = -7.1, 21.1  # main corridor end wall lines
LOBBY_W, LOBBY_E, LOBBY_S = 10.9, 15.1, 12.1
SIDE_X = (WEST + EAST) / 2  # 7.7
MAIN_Z = (MAIN_N + MAIN_S) / 2  # 8.2
LOBBY_X = (LOBBY_W + LOBBY_E) / 2  # 13.0
ELEVATORS = [12.0, 14.0]  # door centers on the lobby's south wall
ELEVATOR_W, ELEVATOR_H = 1.1, 2.2

# Neighbor doors: name, wall ("x"/"z" axis), wall line, position along the wall, yaw (local +Z = the unit), label.
DOORS = [
    ("Door4418", "z", EAST, 0.0, 90, "4418"),
    ("Door4419", "z", EAST, 4.6, 90, "4419"),
    ("Door4420", "x", MAIN_S, 18.2, 0, "4420"),
    ("Door4421", "x", MAIN_S, 6.2, 0, "4421"),
    ("Door4422", "x", MAIN_S, 1.0, 0, "4422"),
    ("Door4423", "x", MAIN_S, -4.0, 0, "4423"),
    ("DoorService", "x", MAIN_N, 4.6, 180, "SERVICE"),
    ("DoorStairs", "z", MAIN_W, MAIN_Z, -90, "STAIRS"),
]
DOOR_HALF = 0.45
# Doors into units (zones in zones/zone_graph.json, D-062) work like ours (door_entrance: lever, lock,
# peephole); service and stairs stay shut (door_neighbor). Each shows its number (UnitPlate).
UNIT_DOORS = {"4418", "4419", "4420", "4421", "4422", "4423"}


# Wall trim (D-060): the wainscot swept along these runs by blender/architecture/corridor/ into TRIM_GLB
# (tools/blockout/corridor_kit.json has the profile). Same run format as the apartment's skirting (D-036).
TRIM_JSON = ROOT / "tools" / "blockout" / "corridor_trim.json"
TRIM_PROFILE = {"height": 1.05, "thickness": 0.035}
DOOR_FRAME_GLB = "assets/props/door_entrance/door_entrance_frame.glb"
# The apartment's entrance door (apartment.py INSTANCES): its frame cuts the trim on the corridor side.
ENTRANCE = ((WEST, 0, 2.9), -90)


KIT_DIR = "assets/architecture/corridor"


def kit(name):
    """The corridor kit glb's res:// path once the artist exported it, else None."""
    path = f"{KIT_DIR}/{name}.glb"
    return "res://" + path if (ROOT / path).exists() else None


def placed_bounds(glb, pos, yaw, pad=0.0):
    """World (x0, z0, x1, z1) of a glb's bounds placed at pos with a yaw (multiples of 90)."""
    lo, hi = glb_bounds(glb)
    c, s = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
    xs, zs = [], []
    for x in (lo[0], hi[0]):
        for z in (lo[2], hi[2]):
            xs.append(pos[0] + x * c + z * s)
            zs.append(pos[2] - x * s + z * c)
    return (min(xs) - pad, min(zs) - pad, max(xs) + pad, max(zs) + pad)


def trim_runs(z: Zone) -> list[dict]:
    """Runs along the foot of every corridor wall, cut at door frames, the window and the elevators."""
    def footprint(center, size):
        return (center[0] - size[0] / 2, center[2] - size[2] / 2, center[0] + size[0] / 2, center[2] + size[2] / 2)

    floors = [footprint(c, sz) for _, _, c, sz, mat, _ in z.boxes if mat in FLOOR_MATS]
    blocked = [footprint(c, sz) for _, _, c, sz, mat, _ in z.boxes if mat == "wall" and c[1] - sz[1] / 2 < 1e-6]
    cuts = []
    x0, x1, _, _ = z.window_gap("corridor_end", SIDE_X)
    blocked.append((x0, NORTH - T / 2, x1, NORTH + T / 2))  # glass, not a doorway
    cuts.append((x0, NORTH - T / 2, x1, NORTH + T / 2 + 0.05))  # the floor-level frame
    for x in ELEVATORS:  # the car doors fill the openings
        blocked.append((x - ELEVATOR_W / 2, LOBBY_S - T / 2, x + ELEVATOR_W / 2, LOBBY_S + T / 2))
        cuts.append((x - ELEVATOR_W / 2 - 0.07, LOBBY_S - T / 2 - 0.03, x + ELEVATOR_W / 2 + 0.07, LOBBY_S))
    for _, axis, line, at, yaw, _ in DOORS:
        pos = (line, 0, at) if axis == "z" else (at, 0, line)
        cuts.append(placed_bounds(DOOR_FRAME_GLB, pos, yaw))
    cuts.append(placed_bounds(DOOR_FRAME_GLB, *ENTRANCE))
    return skirting.runs(floors, blocked, cuts)


def build() -> Zone:
    z = Zone("Corridor", "zones/corridor/corridor.tscn", height=H, doc=(
        "Zone: corridor, floor 44 (side corridor with the facade window and our entrance, main corridor, elevator "
        "lobby). GENERATED by tools/blockout/corridor.py; edit that, not this file. Floor y 0, ceiling 2.8 m. "
        "Streamed in by ZoneStreamer (D-059)."))

    # --- Shell: floors and ceilings on the wall center lines -----------------------------------------
    # Hotel carpet tiles (D-060) once the surface set exists.
    floor = "carpet_tiles" if (ROOT / "assets" / "materials" / "carpet_tiles.tres").exists() else "concrete"
    for name, x0, x1, z0, z1, mat in [
        ("Side", WEST, EAST, NORTH, MAIN_N, floor),
        ("Main", MAIN_W, MAIN_E, MAIN_N, MAIN_S, floor),
        ("Lobby", LOBBY_W, LOBBY_E, MAIN_S, LOBBY_S, floor),
    ]:
        center, size = ((x0 + x1) / 2, (z0 + z1) / 2), (x1 - x0, z1 - z0)
        z.box("Shell", f"{name}Floor", (center[0], -0.1, center[1]), (size[0], 0.2, size[1]), mat)
        z.box("Shell", f"{name}Ceiling", (center[0], H + 0.1, center[1]), (size[0], 0.2, size[1]), "ceiling")

    gaps = {}
    for name, axis, line, at, yaw, _ in DOORS:
        gaps.setdefault((axis, line), []).append(door_gap(at - DOOR_HALF, at + DOOR_HALF))

    # Side corridor. West: the apartment's east wall line with its entrance gap (apartment.py: East).
    z.wall("Shell", "SideWest", "z", WEST, (NORTH - T / 2, MAIN_N - T / 2), [door_gap(2.45, 3.35)])
    z.wall("Shell", "SideEast", "z", EAST, (NORTH - T / 2, MAIN_N - T / 2), gaps[("z", EAST)])
    z.wall("Shell", "Facade", "x", NORTH, (WEST + T / 2, EAST + T / 2), [z.window_gap("corridor_end", SIDE_X)])
    z.window("corridor_end", "EndWindow", (SIDE_X, 0, NORTH))
    # Main corridor: north wall on both sides of the side corridor, south wall with the lobby opening.
    service = gaps[("x", MAIN_N)]
    z.wall("Shell", "MainNorthWest", "x", MAIN_N, (MAIN_W - T / 2, WEST + T / 2), service)
    z.wall("Shell", "MainNorthEast", "x", MAIN_N, (EAST - T / 2, MAIN_E + T / 2))
    z.wall("Shell", "MainSouth", "x", MAIN_S, (MAIN_W - T / 2, MAIN_E + T / 2),
           gaps[("x", MAIN_S)] + [(LOBBY_W + T / 2, LOBBY_E - T / 2, 0.0, 2.4)])
    z.wall("Shell", "MainWestEnd", "z", MAIN_W, (MAIN_N - T / 2, MAIN_S + T / 2), gaps[("z", MAIN_W)])
    z.wall("Shell", "MainEastEnd", "z", MAIN_E, (MAIN_N - T / 2, MAIN_S + T / 2))
    # Elevator lobby.
    z.wall("Shell", "LobbyWest", "z", LOBBY_W, (MAIN_S + T / 2, LOBBY_S + T / 2))
    z.wall("Shell", "LobbyEast", "z", LOBBY_E, (MAIN_S + T / 2, LOBBY_S + T / 2))
    z.wall("Shell", "LobbySouth", "x", LOBBY_S, (LOBBY_W - T / 2, LOBBY_E + T / 2),
           [(x - ELEVATOR_W / 2, x + ELEVATOR_W / 2, 0.0, ELEVATOR_H) for x in ELEVATORS])

    # --- Elevators (placeholders): steel leaves in the openings, gunmetal trim, a call panel -----------
    face = LOBBY_S - T / 2  # the lobby side of the south wall
    for i, x in enumerate(ELEVATORS):
        half = ELEVATOR_W / 2
        z.box("Elevators", f"Car{i}DoorLeft", (x - half / 2, ELEVATOR_H / 2, LOBBY_S), (half - 0.005, ELEVATOR_H, 0.04), "steel")
        z.box("Elevators", f"Car{i}DoorRight", (x + half / 2, ELEVATOR_H / 2, LOBBY_S), (half - 0.005, ELEVATOR_H, 0.04), "steel")
        z.box("Elevators", f"Car{i}TrimLeft", (x - half - 0.03, ELEVATOR_H / 2, face - 0.01), (0.06, ELEVATOR_H, 0.02), "gunmetal", False)
        z.box("Elevators", f"Car{i}TrimRight", (x + half + 0.03, ELEVATOR_H / 2, face - 0.01), (0.06, ELEVATOR_H, 0.02), "gunmetal", False)
        z.box("Elevators", f"Car{i}TrimTop", (x, ELEVATOR_H + 0.03, face - 0.01), (ELEVATOR_W + 0.12, 0.06, 0.02), "gunmetal", False)
        z.sign(f"Car{i}Floor", (x, ELEVATOR_H + 0.22, face - 0.005), 180, "44", font_size=96, pixel_size=0.0012,
               col=(0.3, 0.95, 1.0))
    z.box("Elevators", "CallPanel", (LOBBY_X, 1.2, face - 0.01), (0.12, 0.26, 0.02), "gunmetal", False)
    z.box("Elevators", "CallUp", (LOBBY_X, 1.25, face - 0.022), (0.03, 0.03, 0.006), "cyan", False)
    z.box("Elevators", "CallDown", (LOBBY_X, 1.15, face - 0.022), (0.03, 0.03, 0.006), "cyan", False)

    # --- Neighbor doors and their numbers ---------------------------------------------------------------
    for name, axis, line, at, yaw, label in DOORS:
        pos = (line, 0, at) if axis == "z" else (at, 0, line)
        z.instance(name, "door_entrance" if label in UNIT_DOORS else "door_neighbor", pos, (0, yaw, 0),
                   meta={"unit_number": label})

    # --- Kit (D-060, tools/blockout/corridor_kit.json): the artist's glbs once they exist, stand-ins until then ---
    trim = kit("corridor_trim")
    if trim:
        z.instance("Trim", trim, (0, 0, 0))
    else:
        # A cyan cove along the side corridor's east wall until the wainscot brings its LED reveal.
        z.box("Fixtures", "SideCove", (EAST - T / 2 - 0.01, 2.55, (NORTH + MAIN_N) / 2 + 0.1), (0.02, 0.025, 9.6), "cyan", False)
    z.box("Fixtures", "LobbyBand", (LOBBY_X, 2.42, MAIN_S - T / 2 - 0.01), (4.0, 0.025, 0.02), "magenta", False)

    side_lights = [-1.5, 2.0, 5.2]
    main_lights = [-5.0, 0.0, 4.5, 9.5, 17.5]
    fixtures = ([(f"SideLamp{i}", SIDE_X, zz, 90) for i, zz in enumerate(side_lights)]
                + [(f"MainLamp{i}", x, MAIN_Z, 0) for i, x in enumerate(main_lights)]
                + [("LobbyLamp", LOBBY_X, 10.8, 0)])
    light_glb = kit("corridor_light")
    for name, x, zz, yaw in fixtures:
        if light_glb:
            z.instance(name, light_glb, (x, H, zz), (0, yaw, 0))
        else:
            z.box("Fixtures", name, (x, H - 0.015, zz), (0.3, 0.03, 0.9) if yaw else (0.9, 0.03, 0.3), "lamp", False)
    vent_glb = kit("corridor_vent")
    if vent_glb:
        for i, (x, zz, yaw) in enumerate([(SIDE_X, 0.3, 90), (SIDE_X, 3.6, 90), (-2.5, MAIN_Z, 0), (2.2, MAIN_Z, 0),
                                          (7.0, MAIN_Z, 0), (15.5, MAIN_Z, 0), (19.5, MAIN_Z, 0)]):
            z.instance(f"Vent{i}", vent_glb, (x, H, zz), (0, yaw, 0))

    # Emergency exit over the stairs door (physical, back-lit).
    exit_at = (MAIN_W + T / 2, 2.35, MAIN_Z)
    exit_glb = kit("exit_sign")
    if exit_glb:
        z.instance("ExitSign", exit_glb, exit_at, (0, 90, 0))
    else:
        z.box("Fixtures", "ExitSign", (exit_at[0] + 0.025, exit_at[1], exit_at[2]), (0.05, 0.16, 0.36), "dark", False)
        z.sign("ExitSignFace", (exit_at[0] + 0.052, exit_at[1], exit_at[2]), 90, "EXIT", font_size=96,
               pixel_size=0.0009, col=(0.17, 0.88, 0.48))

    # --- Holographic wayfinding (HoloSign) on the walls, each under a ceiling emitter -------------------------
    south = MAIN_S - T / 2 - 0.03
    north = MAIN_N + T / 2 + 0.03
    magenta = (1.0, 0.16, 0.43)
    holos = [
        # name, position, yaw (the reader faces it), text, size, arrow (as read), extra
        ("JunctionElevators", (SIDE_X, 1.92, south), 180, "ELEVATORS  ·  4420", (1.4, 0.2), "left", {}),
        ("JunctionStairs", (SIDE_X, 1.64, south), 180, "4421 – 4423  ·  STAIRS", (1.4, 0.2), "right", {}),
        ("SideToElevators", (EAST - T / 2 - 0.03, 1.7, 6.1), -90, "ELEVATORS", (0.9, 0.2), "right", {}),
        ("WestToElevators", (1.5, 1.7, north), 0, "ELEVATORS  ·  4420", (1.4, 0.2), "right", {}),
        ("EastToElevators", (17.0, 1.7, north), 0, "ELEVATORS", (0.9, 0.2), "left", {}),
        ("FromElevatorsEast", (LOBBY_X, 1.92, north), 0, "4420", (0.8, 0.2), "right", {}),
        ("FromElevatorsWest", (LOBBY_X, 1.64, north), 0, "4417 – 4419  ·  4421 – 4423  ·  STAIRS", (2.1, 0.2),
         "left", {}),
        ("LobbyHeader", (LOBBY_X, 2.6, MAIN_S - T / 2 - 0.02), 180, "ELEVATORS", (1.8, 0.3), "",
         {"tint": magenta, "line_height": 0.13}),
        ("Directory", (LOBBY_W + T / 2 + 0.03, 1.5, 10.8), 90,
         "FLOOR 44\n4417 – 4419  ·  north wing\n4420 – 4423  ·  main corridor\nSTAIRS  ·  SERVICE  ·  west",
         (1.1, 0.5), "", {"align": "left", "line_height": 0.06}),
    ]
    emitter = kit("holo_emitter")
    for name, pos, yaw, text, size, arrow, extra in holos:
        z.holo(name, pos, yaw, text, size, arrow=arrow, **extra)
        if emitter:
            # On the ceiling 12 cm out from the wall, over the sign.
            nx, nz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
            z.instance(f"{name}Emitter", emitter, (round(pos[0] + nx * 0.12, 4), H, round(pos[2] + nz * 0.12, 4)))

    # --- Floor guide lights: two lines along the walls, pulses running toward the elevators -----------------
    off = T / 2 + 0.035 + 0.12  # from the wall line: past the wainscot, then 12 cm
    side_z = (NORTH + T / 2 + 0.3, MAIN_N + T / 2)
    z.guide_strip("SideWest", (WEST + off, side_z[0]), (WEST + off, side_z[1]), (0, 1))
    z.guide_strip("SideEast", (EAST - off, side_z[0]), (EAST - off, side_z[1]), (0, 1))
    west_end, east_end = MAIN_W + off, MAIN_E - off
    for name, x0, x1, zz, flow in [
        ("NorthWest", west_end, WEST + T / 2, MAIN_N + off, 1), ("NorthMiddle", EAST - T / 2, LOBBY_X, MAIN_N + off, 1),
        ("NorthEast", LOBBY_X, east_end, MAIN_N + off, -1),
        ("SouthWest", west_end, LOBBY_W + T / 2, MAIN_S - off, 1), ("SouthEast", LOBBY_E - T / 2, east_end, MAIN_S - off, -1),
    ]:
        z.guide_strip(name, (round(x0, 4), round(zz, 4)), (round(x1, 4), round(zz, 4)), (flow, 0))

    # --- Lighting -----------------------------------------------------------------------------------------------
    cool = (0.8, 0.9, 1.0)
    for i, zz in enumerate(side_lights):
        z.light(f"Side{i}", "Omni", (SIDE_X, H - 0.15, zz), color=cool, energy=0.55, range=3.6)
    for i, x in enumerate(main_lights):
        z.light(f"Main{i}", "Omni", (x, H - 0.15, MAIN_Z), color=cool, energy=0.55, range=3.8)
    z.light("Lobby", "Omni", (LOBBY_X, H - 0.15, 10.8), color=(1.0, 0.86, 0.95), energy=0.7, range=4.0)
    z.probe("SideProbe", (SIDE_X, 1.4, (NORTH + MAIN_N) / 2), (EAST - WEST - T, H, MAIN_N - NORTH), daylight=True)
    z.probe("MainProbe", ((MAIN_W + MAIN_E) / 2, 1.4, MAIN_Z), (MAIN_E - MAIN_W - T, H, MAIN_S - MAIN_N - T))
    z.probe("LobbyProbe", (LOBBY_X, 1.4, (MAIN_S + LOBBY_S) / 2), (LOBBY_E - LOBBY_W - T, H, LOBBY_S - MAIN_S))

    # --- Entries and the perf path (eye height 1.7, yaw 0 = -Z, 90 = -X, 180 = +Z, -90 = +X) -------------------
    z.entry("ApartmentDoor", (7.4, 0, 2.9), 90)
    z.entry("Elevator", (LOBBY_X, 0, 11.2), 0)
    for pos, rot in [
        ((SIDE_X, 1.7, 6.0), (0, 0, 0)),
        ((SIDE_X, 1.7, 0.0), (0, 0, 0)),
        ((SIDE_X, 1.7, -2.0), (-5, 0, 0)),
        ((SIDE_X, 1.7, 2.9), (0, 90, 0)),
        ((SIDE_X, 1.7, MAIN_Z), (0, 180, 0)),
        ((1.0, 1.7, MAIN_Z), (0, 90, 0)),
        ((LOBBY_X, 1.7, MAIN_Z), (0, -90, 0)),
        ((LOBBY_X, 1.7, 10.8), (0, 180, 0)),
        ((18.0, 1.7, MAIN_Z), (0, -90, 0)),
    ]:
        z.perf_marker(pos, rot)
    return z


if __name__ == "__main__":
    zone = build()
    check = "--check" in sys.argv
    runs = trim_runs(zone)
    if not check:
        skirting.write(TRIM_JSON, TRIM_PROFILE, runs,
                       "GENERATED by tools/blockout/corridor.py: the corridor's wall trim runs (D-060; format: "
                       "tools/blockout/skirting.py).")
        print(f"wrote {TRIM_JSON.relative_to(ROOT)}: {len(runs)} runs")
    sys.exit(zone.save(check=check))
