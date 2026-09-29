"""Wardrobe dimensions, paths and parts (Fable 5.1 won the A/B). Built on blender/lib (D-028).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/wardrobe/build.py
  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/bake.py
  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/export.py
  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/wardrobe/verify.py

Coordinates: Blender Z up, meters, the wardrobe front faces -Y. Body objects
are built in world coordinates (identity transforms). Moving parts are built
in part-local coordinates around a root object placed at the part's closed or
resting position, and exported with the root at the origin:

  DoorLeft / DoorRight  hinge axis at the local origin at floor height, front toward -Y;
                        left extends along +X and opens by a negative Z rotation, right mirrored
  DrawerLower / Upper   drawer front's bottom center, slides along -Y (one glb: both identical)
  StorageBox, BoxLid    bottom center of the box / bottom of the lid's skirt
  Hanger1..4            the hook's resting point (inside of the hook on the rail top);
                        shoulders along local X, garment down -Z; roots rotated 90 deg
                        about Z in the scene so the shoulders run across the rail
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "wardrobe"
BLEND = output_path("blender", "props", f"{NAME}.blend")
ASSET_DIR = ("assets", "props", "wardrobe")
GLB_BODY = output_path(*ASSET_DIR, "wardrobe_body.glb")
GLB_DOOR_LEFT = output_path(*ASSET_DIR, "wardrobe_door_left.glb")
GLB_DOOR_RIGHT = output_path(*ASSET_DIR, "wardrobe_door_right.glb")
GLB_DRAWER = output_path(*ASSET_DIR, "wardrobe_drawer.glb")
GLB_BOX = output_path(*ASSET_DIR, "wardrobe_box.glb")
GLB_BOX_LID = output_path(*ASSET_DIR, "wardrobe_box_lid.glb")
GLB_HANGER = output_path(*ASSET_DIR, "wardrobe_hanger.glb")
GLB_HANGER_SHIRT_A = output_path(*ASSET_DIR, "wardrobe_hanger_shirt_a.glb")  # linen
GLB_HANGER_SHIRT_B = output_path(*ASSET_DIR, "wardrobe_hanger_shirt_b.glb")  # charcoal
SCRATCH = scratch_dir(NAME)  # default thumbnail folder; render.py takes --out

# --- Fixed contract (the Godot scene depends on these) ---------------------------
BODY_W, BODY_D, BODY_H = 1.50, 0.60, 2.10
BODY_X = BODY_W / 2  # 0.75
BODY_Y = BODY_D / 2  # 0.30
HINGE_LEFT = Vector((-BODY_X, -BODY_Y, 0.0))
HINGE_RIGHT = Vector((BODY_X, -BODY_Y, 0.0))
OPEN_DEG = 110.0          # swing checked in Blender (verify.py)
DRAWER_CHECK_DEG = 95.0   # doors open this far while the drawer travel is checked

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

# Interior layout: hanging space on the left, drawers and shelves on the right
DIVIDER_X = 0.25                 # center of the 18 mm vertical divider
DIV_X0, DIV_X1 = DIVIDER_X - PANEL / 2, DIVIDER_X + PANEL / 2
BAY_X0, BAY_X1 = DIV_X1, CAV_X   # right bay, 0.473 wide
BAY_XC = (BAY_X0 + BAY_X1) / 2   # 0.4955
TOP_SHELF = 1.75                 # top surface z, full width
SHELF_Y0 = -0.27                 # shelves set back 30 mm from the carcass front
RIGHT_SHELVES = [0.782, 1.10, 1.36]  # top surface z: drawer unit top, folded clothes, storage box
# Shelves and drawers avoid the door hinge arms (z +-7 mm around HINGE_ZS, 62 mm behind the door).

# Drawers (local: origin at the front's bottom center, front face at y = 0, slides along -Y)
DRAWER_FRONT_Y = -0.23           # front face, 70 mm behind the carcass front: clears the hinge arms
DRAWER_Z0S = [0.240, 0.503]      # front bottom z of the lower and upper drawer (6 mm gaps)
DRAWER_W, DRAWER_H, DRAWER_FRONT_T = 0.467, 0.257, PANEL
DRAWER_BOX_HW = 0.222            # box outer half width (12.5 mm runner space each side)
DRAWER_WALL = 0.010
DRAWER_BOX_Y0, DRAWER_BOX_Y1 = DRAWER_FRONT_T, 0.478   # box behind the front (0.46 long)
DRAWER_FLOOR_Z0, DRAWER_FLOOR_Z1 = 0.015, 0.025
DRAWER_BOX_Z1 = 0.200            # wall top
DRAWER_RUNNER_Z0, DRAWER_RUNNER_Z1 = 0.028, 0.040      # drawer-side runner (on the box walls)
DRAWER_RUNNER_HX = 0.235         # its outer half width
BODY_RUNNER_Z0, BODY_RUNNER_Z1 = 0.012, 0.027          # body-side runner, relative to the drawer z0
BODY_RUNNER_T = 0.0125           # its thickness from the bay wall
BODY_RUNNER_Y0, BODY_RUNNER_Y1 = -0.20, 0.25
DRAWER_TRAVEL = 0.40             # checked in verify.py with the doors at DRAWER_CHECK_DEG
DRAWER_GRIP = Vector((0.0, -0.004, 0.245))
CUBBY_Z1 = DRAWER_Z0S[0]         # open space under the drawers (z 0.098..0.24)

# Hanging rail and hangers
RAIL_Z, RAIL_Y, RAIL_R = 1.66, 0.0, 0.0125
RAIL_X0, RAIL_X1 = -CAV_X + 0.004, DIV_X0 - 0.004
HANGER_WIRE = 0.0021
HANGER_REST_Z = RAIL_Z + RAIL_R  # hanger origin z (hook resting on the rail top)
HANGERS = [(-0.56, "linen"), (-0.46, "charcoal"), (-0.34, None), (-0.22, None)]  # x slot, garment

# Fabric storage box with a lift-off lid on the 1.36 shelf (local: bottom center / skirt bottom)
BOX_HW, BOX_HD, BOX_H = 0.150, 0.180, 0.220
BOX_WALL = 0.008
LID_HW, LID_HD = BOX_HW + 0.010, BOX_HD + 0.010    # 2 mm clearance around the box
LID_SKIRT, LID_TOP = 0.030, 0.010
BOX_POS = Vector((BAY_XC, 0.0, RIGHT_SHELVES[2]))
LID_POS = Vector((BAY_XC, 0.0, RIGHT_SHELVES[2] + BOX_H - LID_SKIRT))

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
PROPS_MAT = "WardrobeProps"      # drawer, box, lid, hangers: one shared atlas

TEX_SIZE_BODY = 2048
TEX_SIZE_DOOR = 1536
TEX_SIZE_PROPS = 2048


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


MOVING_PARTS = ["drawer_lower", "drawer_upper", "box", "lid", "hanger1", "hanger2", "hanger3", "hanger4"]


def prop_meshes(part):
    return part_objects(part, mesh_only=True)


def all_prop_meshes():
    """Every moving part's meshes (the props atlas plus the instanced duplicates)."""
    return [o for p in MOVING_PARTS for o in prop_meshes(p)]


def prop_root(part):
    return [o for o in part_objects(part) if o.parent is None][0]
