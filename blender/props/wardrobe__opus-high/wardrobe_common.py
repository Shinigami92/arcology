"""Wardrobe (A/B variant opus-high): dimensions, paths and parts. Built on blender/lib (D-028).

A slim modern two-door wardrobe in dark walnut veneer on six brushed gunmetal
legs, part of the bedroom set (bed, nightstand). Full-overlay slab doors meet
in the middle, with vertical gunmetal bar pulls near the meeting edges.
Inside: a top shelf with folded linen, an LED strip under it, a hanging rail
with six walnut hangers (two linen shirts), a bottom shelf over two static
drawers, and a linen-textured back panel. Lived-in: worn and polished door
edges and fingerprints around the pulls, a small scratch on the right door,
faint kick scuffs, light dust on top.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/wardrobe__opus-high/build.py
  blender -b --factory-startup blender/props/wardrobe__opus-high.blend --python blender/props/wardrobe__opus-high/bake.py
  blender -b --factory-startup blender/props/wardrobe__opus-high.blend --python blender/props/wardrobe__opus-high/export.py
  blender -b --factory-startup blender/props/wardrobe__opus-high.blend --python blender/props/wardrobe__opus-high/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/wardrobe__opus-high/verify.py

Coordinates: Blender Z up, meters, front faces -Y, origin at the bottom
center of the footprint. Body objects are built in world coordinates
(identity transforms). Each door is built in door-local coordinates (hinge
axis at the local origin, floor height; the left door extends along +X, the
right door along -X; front face toward -Y) and its root object sits on the
hinge: left (-0.75, -0.30, 0), right (+0.75, -0.30, 0). The left door opens
with a negative rotation about +Z, the right door with a positive one.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

TAG = "opus-high"
NAME = "wardrobe"
BLEND = output_path("blender", "props", f"wardrobe__{TAG}.blend")
GLB_BODY = output_path("assets", "props", "wardrobe", f"wardrobe_body__{TAG}.glb")
GLB_DOOR_L = output_path("assets", "props", "wardrobe", f"wardrobe_door_left__{TAG}.glb")
GLB_DOOR_R = output_path("assets", "props", "wardrobe", f"wardrobe_door_right__{TAG}.glb")
GLB_DRAWER = output_path("assets", "props", "wardrobe", f"wardrobe_drawer__{TAG}.glb")  # instanced twice
GLB_BOX = output_path("assets", "props", "wardrobe", f"wardrobe_box__{TAG}.glb")
GLB_LID = output_path("assets", "props", "wardrobe", f"wardrobe_box_lid__{TAG}.glb")
GLB_HANGER = output_path("assets", "props", "wardrobe", f"wardrobe_hanger__{TAG}.glb")  # bare, instanced
GLB_HANGER_A = output_path("assets", "props", "wardrobe", f"wardrobe_hanger_shirt_a__{TAG}.glb")
GLB_HANGER_B = output_path("assets", "props", "wardrobe", f"wardrobe_hanger_shirt_b__{TAG}.glb")
SCRATCH = scratch_dir(f"{NAME}__{TAG}")  # default thumbnail folder (render.py --out overrides)

# --- Fixed contract (the Godot scene depends on these) ---------------------------
BODY_W, BODY_D, BODY_H = 1.50, 0.60, 2.10
BX = BODY_W / 2   # 0.75
BY = BODY_D / 2   # 0.30
HINGE_L = Vector((-BX, -BY, 0.0))
HINGE_R = Vector((BX, -BY, 0.0))
OPEN_DEG = 110.0    # swing checked in Blender (sign -1 left, +1 right)
RENDER_DEG = 100.0  # open thumbnail

# --- Carcass (19 mm veneered board) ------------------------------------------------
BOARD = 0.019
LEG_H = 0.10                   # carcass underside
CARCASS_Z0 = LEG_H
IN_X = BX - BOARD              # 0.731 inner face of the sides
IN_Z0 = CARCASS_Z0 + BOARD     # 0.119 top of the bottom panel
IN_Z1 = BODY_H - BOARD         # 2.081 underside of the top panel
BACK_Y0, BACK_Y1 = 0.282, 0.290  # 8 mm back panel, inset 10 mm into the sides
FRONT_Y = -BY                  # carcass front edges

# Shelves (18 mm, front edge 15 mm behind the carcass front)
SHELF_T = 0.019
SHELF_Y0 = -0.285
TOP_SHELF_Z = 1.800            # underside; top surface 1.819
BOTTOM_SHELF_Z = 0.360         # underside; top surface 0.379 (drawer unit lid)

# Drawer unit under the bottom shelf: center divider, two compartments with
# gunmetal runners on the sides and the divider, two identical sliding drawers
DIVIDER_T = 0.019
DRAWER_Y0, DRAWER_Y1 = -0.262, -0.244  # front face, back face of the drawer fronts (closed, world)
DRAWER_GAP = 0.003
DRAWER_Z0, DRAWER_Z1 = IN_Z0 + DRAWER_GAP, BOTTOM_SHELF_Z - DRAWER_GAP
BOTTOM_SHELF_Y0 = DRAWER_Y0   # the drawer unit lid is flush with the drawer fronts
DRAWER_CX = (IN_X + DIVIDER_T / 2) / 2          # 0.37025, drawer center |x|
DRAWER_ORIGINS = (Vector((-DRAWER_CX, DRAWER_Y0, DRAWER_Z0)), Vector((DRAWER_CX, DRAWER_Y0, DRAWER_Z0)))
DRAWER_TRAVEL = 0.40           # checked in verify.py (slides along -Y)
RENDER_DRAWER_OUT = 0.25       # open thumbnail
# Drawer-local (origin at the front's outer face, bottom edge, centered; the box extends +Y)
DR_FRONT_HW = (IN_X - DRAWER_GAP - (DIVIDER_T / 2 + DRAWER_GAP)) / 2   # 0.35775
DR_FRONT_T = DRAWER_Y1 - DRAWER_Y0                                   # 0.018
DR_FRONT_H = DRAWER_Z1 - DRAWER_Z0                                   # 0.235
RUNNER_T = 0.006               # carcass runner rail (on the side panel and the divider)
RUNNER_Z0, RUNNER_Z1 = 0.200, 0.235                                  # world
RUNNER_Y0, RUNNER_Y1 = -0.240, 0.260                                 # world
DR_BOX_HW = IN_X - DRAWER_CX - RUNNER_T - 0.001 - 0.0055             # 0.34825 outer half width of the box
DR_MEMBER_T = 0.0055           # drawer-side slide member
DR_WALL = 0.012
DR_FLOOR = 0.008
DR_BOX_Z0, DR_BOX_Z1 = 0.010, 0.203                                  # local
DR_BOX_Y0, DR_BOX_Y1 = DR_FRONT_T, 0.522                             # local (back wall at world y 0.260)
PULL_LEN = 0.16
PULL_R = 0.0045
PULL_Y = DRAWER_Y0 - 0.018     # bar axis (world, closed); bar front at -0.2845 (door back at -0.301)
PULL_Z = DRAWER_Z1 - 0.045

# Shelf pin holes (32 mm system) on the inner sides around the top shelf, and its pins
PIN_Y = (-0.255, 0.250)
PIN_R = 0.0025
PIN_Z = TOP_SHELF_Z - PIN_R    # pin axis under the top shelf
PIN_PITCH = 0.032
PIN_HOLES_Z = (1.50, 2.04)     # the row of holes spans this range, one hole on PIN_Z

# Hanging rail
RAIL_R = 0.0125
RAIL_Y = -0.010
RAIL_Z = 1.735
HANGERS_X = (-0.575, -0.505, -0.215, -0.135, 0.285, 0.360)
SHIRTS = (2, 3)                # indices into HANGERS_X that carry a shirt
HOOK_WIRE = 0.0025             # hook wire radius
HOOK_R = 0.0195                # hook centerline radius (inside 17 mm, a little wider than the rail)
HOOK_CENTER_Z = -(HOOK_R - HOOK_WIRE)  # hanger-local: the hook's inside touches the rail top at the origin
HANGER_W = 0.43                # tip to tip
# Hanger-local frame: origin at the hook's resting point (top of the rail), shoulders
# along local X, garment hanging down -Z, garment front toward local -Y. In the
# wardrobe each hanger sits at (x, RAIL_Y, RAIL_Z + RAIL_R) rotated +90 deg about Z.
HANGER_ROT_Z = 90.0
HANGER_ARM_TOP = -0.0875       # local z of the arms' top at the center

# Fabric storage box on the bottom shelf (pickable, lid separate)
BOX_ORIGIN = Vector((0.41, 0.0, BOTTOM_SHELF_Z + SHELF_T))   # bottom center, on the shelf
BOX_SIZE = (0.38, 0.32, 0.175)
BOX_WALL = 0.005
LID_SIZE = (0.389, 0.329, 0.035)
LID_WALL, LID_TOP = 0.004, 0.005
LID_ORIGIN = BOX_ORIGIN + Vector((0.0, 0.0, BOX_SIZE[2] - (LID_SIZE[2] - LID_TOP)))  # skirt 3 cm over the box

# LED strip under the top shelf (unbaked emissive, Godot's HingeLight can switch it)
LED_Y0, LED_Y1 = -0.272, -0.254

# Legs (tapered square gunmetal tube, 6 pcs)
LEG_TOP, LEG_BOTTOM = 0.034, 0.024
LEGS = [(x, y) for x in (-0.70, 0.0, 0.70) for y in (-0.255, 0.255)]

# --- Doors (door-local coordinates; hinge axis at the origin) -----------------------
DOOR_GAP = 0.003               # between the doors in the middle
DOOR_W = BX - DOOR_GAP / 2     # 0.7485
DOOR_T = 0.020
DOOR_Y1 = -0.001               # back face: 1 mm in front of the carcass
DOOR_Y0 = DOOR_Y1 - DOOR_T     # front face (-0.021)
DOOR_Z0, DOOR_Z1 = 0.102, 2.098

# Door pulls: vertical round bar on two standoffs, near the meeting edge
HANDLE_INSET = 0.055           # bar axis from the meeting edge
HANDLE_R = 0.007
HANDLE_OUT = 0.032             # bar axis in front of the door face
HANDLE_Z0, HANDLE_Z1 = 0.95, 1.45
HANDLE_POSTS = (0.99, 1.41)
GRIP_Z = 1.20
HANDLE_LOCAL_X = DOOR_W - HANDLE_INSET          # left door; the right door mirrors it
HANDLE_LOCAL_Y = DOOR_Y0 - HANDLE_OUT           # -0.053

# --- Materials and textures --------------------------------------------------------
BODY_MAT = "WardrobeBody"          # carcass, shelves, runners, legs, back panel, rail, linen stacks
PROPS_MAT = "WardrobeProps"        # the moving parts: drawer, box, lid, hangers, shirts (one shared atlas)
LIGHT_MAT = "WardrobeLight"        # LED diffuser (unbaked emissive)
DOOR_L_MAT = "WardrobeDoorLeft"
DOOR_R_MAT = "WardrobeDoorRight"
BODY_TEX = 2048
PROPS_TEX = 1024
DOOR_TEX = 1024

# Palette (linear). Gunmetal is style guide #2E3238, lifted a little for metal F0.
WALNUT_MID = (0.036, 0.019, 0.011)
WALNUT_LIGHT = (0.072, 0.039, 0.021)
WALNUT_DARK = (0.014, 0.007, 0.004)
GUNMETAL = (0.052, 0.060, 0.072)
OFF_WHITE = (0.687, 0.644, 0.552)   # #D8D2C4
SAND = (0.300, 0.250, 0.180)

# --- Collision boxes (Blender lo, hi) ------------------------------------------------
COLLISION = {
    "ColSideLeft": ((-BX, -BY, CARCASS_Z0), (-IN_X, BY, BODY_H)),
    "ColSideRight": ((IN_X, -BY, CARCASS_Z0), (BX, BY, BODY_H)),
    "ColTop": ((-IN_X, -BY, IN_Z1), (IN_X, BY, BODY_H)),
    "ColBack": ((-IN_X, BACK_Y0, IN_Z0), (IN_X, BY, IN_Z1)),
    # Down to the floor, so nothing rolls under the wardrobe between the legs.
    "ColBottom": ((-BX, -BY, 0.0), (BX, BY, IN_Z0)),
    # Drawer compartments: floor = ColBottom, lid = ColShelfBottom, sides + this divider
    "ColDivider": ((-DIVIDER_T / 2, DRAWER_Y0, IN_Z0), (DIVIDER_T / 2, BACK_Y0, BOTTOM_SHELF_Z)),
    "ColShelfBottom": ((-IN_X, BOTTOM_SHELF_Y0, BOTTOM_SHELF_Z), (IN_X, BACK_Y0, BOTTOM_SHELF_Z + SHELF_T)),
    "ColShelfTop": ((-IN_X, SHELF_Y0, TOP_SHELF_Z), (IN_X, BACK_Y0, TOP_SHELF_Z + SHELF_T)),
}


# --- Parts (tagged in build.py) ------------------------------------------------------
def body_objects():
    """Render meshes of the body glb (no collision)."""
    return part_objects("body", mesh_only=True)


def interior_objects():
    """Kept for older scripts; the static interior is part of "body" now."""
    return part_objects("interior", mesh_only=True)


# Moving parts: part tag -> (root object name, glb path)
PROPS = {
    "drawer": ("Drawer", GLB_DRAWER),
    "box": ("Box", GLB_BOX),
    "lid": ("Lid", GLB_LID),
    "hanger": ("Hanger", GLB_HANGER),
    "hanger_a": ("HangerShirtA", GLB_HANGER_A),
    "hanger_b": ("HangerShirtB", GLB_HANGER_B),
}
BARE_HANGERS = [i for i in range(len(HANGERS_X)) if i not in SHIRTS]  # the first one is the built one


def prop_objects(part=None):
    parts = [part] if part else list(PROPS)
    return [o for p in parts for o in part_objects(p)]


def body_collision_objects():
    return part_objects("body_col")


def door_left_objects():
    return part_objects("door_left")


def door_right_objects():
    return part_objects("door_right")
