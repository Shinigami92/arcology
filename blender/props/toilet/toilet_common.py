"""Toilet (bathroom set): concealed-cistern box in honed marble, rimless wall-hung bowl,
soft-close seat and lid, dual-flush plate, roll holder with a pickable roll.
Built on blender/lib (D-028); shared bathroom contract: marble, porcelain, fixture metal.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/toilet/build.py
  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/bake.py
  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/export.py
  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/toilet/verify.py

Coordinates: Blender Z up, meters. The wall plane is Y = 0, the toilet sits in
front of it (Y <= 0), front = -Y (Godot +Z). Origin on the floor at the wall
plane on the bowl's center axis. Seat and lid are built around root objects on
the shared hinge axis (along X); opening is a negative rotation about +X.
The flush buttons have their roots at their face centers (press +Y); the roll
is built upright with its root at its bottom center, and an unexported linked
instance hangs on the holder for renders and the clearance check.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402
from lib_candidates import egg_outline  # noqa: E402

NAME = "toilet"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB_BODY = output_path("assets", "props", NAME, f"{NAME}_body.glb")
GLB_SEAT = output_path("assets", "props", NAME, f"{NAME}_seat.glb")
GLB_LID = output_path("assets", "props", NAME, f"{NAME}_lid.glb")
GLB_FLUSH_SMALL = output_path("assets", "props", NAME, f"{NAME}_flush_small.glb")
GLB_FLUSH_LARGE = output_path("assets", "props", NAME, f"{NAME}_flush_large.glb")
GLB_ROLL = output_path("assets", "props", NAME, f"{NAME}_roll.glb")
SCRATCH = scratch_dir(NAME)

# --- Fixed contract (the Godot scene depends on these) ---------------------------
# Installation box (concealed cistern) clad in honed marble
BOX_X = 0.60                  # X -0.60 .. 0.60
BOX_D = 0.20                  # Y -0.20 .. 0
BOX_FACE = -BOX_D
SHELF_TOP = 1.25              # marble shelf top: small things stand here
SHELF_T = 0.028               # shelf slab thickness
GAP_H = 0.007                 # shadow gap under the shelf
GAP_DEPTH = 0.008
CLAD_TOP = SHELF_TOP - SHELF_T - GAP_H  # 1.215
LIMIT_LO = Vector((-BOX_X, -0.80, 0.0))
LIMIT_HI = Vector((BOX_X, 0.0, SHELF_TOP))

# Bowl (rimless, wall-hung)
RIM_Z = 0.400                 # rim top; the seat adds 20 mm -> seat height 0.42
BOWL_BACK = -0.185            # outer shell's back, 15 mm inside the box (clean contact line)
BOWL_FRONT = -0.750           # 0.55 m projection from the box face
BOWL_HALF_W = 0.180
BOWL_BOTTOM = 0.060
WATER_Z = 0.236
N_OUTLINE = 80                # points per ring (bowl, seat, lid)

# Hinge (seat and lid share it): axis along X
HINGE = Vector((0.0, -0.275, 0.425))
HINGE_R = 0.0095              # knuckle radius
SEAT_KNUCKLE = (0.060, 0.088)  # |x| ranges
POST = (0.091, 0.103)
LID_KNUCKLE = (0.106, 0.134)
PIN_X = 0.137
LID_OPEN_DEG = 97.0           # lid rests against the box face (checked in verify.py)
SEAT_OPEN_DEG = 97.0          # seat rests against the open lid (1.5 mm apart)

# Seat ring and lid
SEAT_Z0, SEAT_Z1 = 0.4035, 0.420   # ring body; bumpers below down to the rim
BUMPER_Z0 = RIM_Z
LID_Z0, LID_Z1 = 0.4215, 0.4405    # lid edge; the top crowns 2 mm higher
LID_CROWN = 0.002

# Flush plate (fixture metal), center 1.10 m
PLATE_C = Vector((0.0, BOX_FACE, 1.10))
PLATE_W, PLATE_H, PLATE_R = 0.250, 0.165, 0.010
PLATE_T = 0.009               # plate face at y = -0.209
POCKET_W, POCKET_H, POCKET_FLOOR = 0.221, 0.133, -0.2015
BTN_H, BTN_R, BTN_T = 0.130, 0.004, 0.005
BTN_FACE_Y = -0.2105          # 1.5 mm proud of the plate face
BTN_TRAVEL = 0.004
BTN_SMALL_W, BTN_LARGE_W, BTN_GAP = 0.070, 0.145, 0.003
BTN_SMALL_X = -POCKET_W / 2 + 0.0015 + BTN_SMALL_W / 2              # -0.074
BTN_LARGE_X = BTN_SMALL_X + BTN_SMALL_W / 2 + BTN_GAP + BTN_LARGE_W / 2  # 0.0365

# Roll holder (+X side of the bowl) and roll
HOLDER_X, HOLDER_Z = 0.300, 0.700
ROSE_R, ROSE_T = 0.024, 0.0085
BAR_R, BAR_Y, BAR_X1 = 0.0055, -0.272, 0.446
ROLL_R_IN, ROLL_R_CORE, ROLL_R, ROLL_W = 0.0215, 0.0228, 0.057, 0.098
ROLL_MASS = 0.13              # kg, a 3-ply roll
# Hanging: the roll's axis along X, its core resting on the bar
ROLL_HANG_CENTER = Vector((0.372, BAR_Y, HOLDER_Z + BAR_R - ROLL_R_IN + 0.0006))  # 0.6 mm above the bar

# Colors (linear, from the contract's sRGB values)
MARBLE = (0.791, 0.761, 0.701)       # #E6E2DA
MARBLE_VEIN = (0.262, 0.254, 0.238)  # #8C8A86
PORCELAIN = (0.888, 0.879, 0.855)    # #F2F1EE
FIXTURE = (0.0437, 0.0482, 0.0578)   # #3B3E44
SEAT_WHITE = (0.871, 0.863, 0.838)

BODY_MAT = "ToiletBody"
SEAT_MAT = "ToiletSeat"
LID_MAT = "ToiletLid"
FLUSH_SMALL_MAT = "ToiletFlushSmall"
FLUSH_LARGE_MAT = "ToiletFlushLarge"
ROLL_MAT = "ToiletRoll"
WATER_MAT = "ToiletWater"            # unbaked, own slot: Godot may swap in a water shader

BODY_TEX = 2048
SEAT_TEX = LID_TEX = 1024
BTN_TEX = 256
ROLL_TEX = 512


# --- Plan outlines (shared by bowl, seat and lid) -----------------------------------
def bowl_outer(L, b, z):
    """Bowl shell plan at height z: back fixed at BOWL_BACK, length L, half width b."""
    a_b = 0.42 * L
    return egg_outline(BOWL_BACK - a_b, 0.58 * L, a_b, b, N_OUTLINE, z, p_front=2.35, p_back=7.0)


def bowl_opening(grow=0.0, z=RIM_Z, s=0.0):
    """Inner rim edge (s = 0) narrowing toward the water section (s = 1), grown by `grow`."""
    yc = -0.460 + 0.012 * s
    af = 0.245 + (0.118 - 0.245) * s
    ab = 0.150 + (0.078 - 0.150) * s
    b = 0.140 + (0.086 - 0.140) * s
    return egg_outline(yc, af + grow, ab + grow, b + grow, N_OUTLINE, z, p_front=2.2, p_back=2.6)


def seat_outer(z=0.0):
    return egg_outline(-0.432, 0.314, 0.145, 0.177, N_OUTLINE, z, p_front=2.35, p_back=3.2)


def seat_inner(z=0.0):
    return egg_outline(-0.468, 0.217, 0.128, 0.119, N_OUTLINE, z, p_front=2.2, p_back=2.4)


def lid_outer(z=0.0):
    return egg_outline(-0.432, 0.316, 0.142, 0.178, N_OUTLINE, z, p_front=2.35, p_back=3.4)


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    return part_objects("body", mesh_only=True)


def body_collision_objects():
    return part_objects("body_col")


def seat_objects():
    return part_objects("seat")


def lid_objects():
    return part_objects("lid")


def flush_small_objects():
    return part_objects("flush_small")


def flush_large_objects():
    return part_objects("flush_large")


def roll_objects():
    return part_objects("roll")


def meshes(objs):
    return [o for o in objs if o.type == "MESH"]
