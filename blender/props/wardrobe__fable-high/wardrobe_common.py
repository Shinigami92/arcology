"""Wardrobe dimensions, paths and parts (A/B variant `fable-high`). Built on blender/lib (D-028).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/wardrobe__fable-high/build.py
  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/bake.py
  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/export.py
  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/wardrobe__fable-high/verify.py

Coordinates: Blender Z up, meters, the wardrobe front faces -Y. Body objects
are built in world coordinates (identity transforms). Each door is built in
door-local coordinates (hinge axis at the local origin at floor height, front
face toward -Y) and parented to its root object `DoorLeft` (at the hinge
(-0.75, -0.30, 0), extends along +X, opens by a negative Z rotation) or
`DoorRight` (at (+0.75, -0.30, 0), extends along -X, opens by a positive one).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

TAG = "fable-high"
NAME = f"wardrobe__{TAG}"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB_BODY = output_path("assets", "props", "wardrobe", f"wardrobe_body__{TAG}.glb")
GLB_DOOR_LEFT = output_path("assets", "props", "wardrobe", f"wardrobe_door_left__{TAG}.glb")
GLB_DOOR_RIGHT = output_path("assets", "props", "wardrobe", f"wardrobe_door_right__{TAG}.glb")
SCRATCH = scratch_dir(NAME)  # default thumbnail folder; render.py takes --out

# --- Fixed contract (the Godot scene depends on these) ---------------------------
BODY_W, BODY_D, BODY_H = 1.50, 0.60, 2.10
BODY_X = BODY_W / 2  # 0.75
BODY_Y = BODY_D / 2  # 0.30
HINGE_LEFT = Vector((-BODY_X, -BODY_Y, 0.0))
HINGE_RIGHT = Vector((BODY_X, -BODY_Y, 0.0))
OPEN_DEG = 110.0  # swing checked in Blender (verify.py)

# Carcass (18 mm panels on 80 mm legs)
LEG_H = 0.08
PANEL = 0.018
BACK_T = 0.020
CAV_X = BODY_X - PANEL           # 0.732
CAV_Y_BACK = BODY_Y - BACK_T     # 0.28
CAV_Z0 = LEG_H + PANEL           # 0.098
CAV_Z1 = BODY_H - PANEL          # 2.082
LEG_R_TOP, LEG_R_BOT = 0.017, 0.012
LEGS = [(x, y) for x in (-0.66, 0.0, 0.66) for y in (-0.22, 0.22)]

# Interior layout: hanging space on the left, shelves and drawers on the right
DIVIDER_X = 0.25                 # center of the 18 mm vertical divider
DIV_X0, DIV_X1 = DIVIDER_X - PANEL / 2, DIVIDER_X + PANEL / 2
TOP_SHELF = 1.75                 # top surface z, full width
SHELF_Y0 = -0.27                 # shelves set back 30 mm from the carcass front
RIGHT_SHELVES = [0.598, 0.98, 1.36]  # top surface z (the first is the drawer unit top)
DRAWERS = [(0.101, 0.335), (0.341, 0.575)]  # front z0, z1
DRAWER_Y0, DRAWER_Y1 = -0.23, -0.212        # front slab (18 mm), 70 mm behind the carcass front: clears the hinge arms
DRAWER_X0, DRAWER_X1 = DIV_X1 + 0.003, CAV_X - 0.003
RAIL_Z, RAIL_Y, RAIL_R = 1.66, 0.0, 0.0125
RAIL_X0, RAIL_X1 = -CAV_X + 0.004, DIV_X0 - 0.004
HANGERS = [(-0.56, "linen"), (-0.46, "charcoal"), (-0.34, None), (-0.22, None)]  # x, garment

# Doors (local coordinates: u along the door from the hinge, y depth, z height)
DOOR_W = 0.747                   # 6 mm meeting gap between the two doors
DOOR_T = 0.020
DOOR_GAP = 0.0015                # to the carcass front
DOOR_Y1 = -DOOR_GAP              # back face
DOOR_Y0 = DOOR_Y1 - DOOR_T       # front face (-0.0215)
DOOR_Z0, DOOR_Z1 = 0.082, 2.098
HINGE_ZS = [0.20, 0.80, 1.40, 1.98]
CUP_U, CUP_R = 0.0225, 0.0175    # concealed hinge cup center from the hinge edge, radius

# Handle: slim square bar on two standoffs near the meeting edge
HANDLE_U = DOOR_W - 0.045        # 0.702
HANDLE_HALF = 0.006              # 12 mm bar
HANDLE_Z0, HANDLE_Z1 = 0.95, 1.45
HANDLE_STAND = 0.034             # front face to bar
HANDLE_Y = DOOR_Y0 - HANDLE_STAND - HANDLE_HALF  # bar center y (-0.0615)
HANDLE_GRIP_Z = 1.20

BODY_MAT = "WardrobeBody"
DOOR_LEFT_MAT = "WardrobeDoorLeft"
DOOR_RIGHT_MAT = "WardrobeDoorRight"

TEX_SIZE_BODY = 2048
TEX_SIZE_DOOR = 1536


def handle_grip(sign):
    """Grip center in door-local coordinates (sign +1 left door, -1 right door)."""
    return Vector((sign * HANDLE_U, HANDLE_Y, HANDLE_GRIP_Z))


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Render meshes of the body glb (no collision)."""
    return part_objects("body", mesh_only=True)


def body_collision_objects():
    return part_objects("body_col")


def door_objects(side):
    """All objects of one door ("left" or "right"), including the HandleGrip empty."""
    return part_objects(f"door_{side}")


def door_meshes(side):
    return part_objects(f"door_{side}", mesh_only=True)
