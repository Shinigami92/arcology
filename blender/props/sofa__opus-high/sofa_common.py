"""Sofa (A/B variant opus-high): dimensions, paths and parts. Built on blender/lib (D-028).

A compact modern three-seater: track arms, a tight upholstered base on six
slim steel legs, three loose seat cushions and three loose back cushions
leaning against a low back frame. Lived-in: the left seat is the favorite
(deepest sag, most wear), the left arm is where the elbow rests.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/sofa__opus-high/build.py
  blender -b --factory-startup blender/props/sofa__opus-high.blend --python blender/props/sofa__opus-high/bake.py
  blender -b --factory-startup blender/props/sofa__opus-high.blend --python blender/props/sofa__opus-high/export.py
  blender -b --factory-startup blender/props/sofa__opus-high.blend --python blender/props/sofa__opus-high/render.py -- [--quick]
  blender -b --factory-startup --python blender/props/sofa__opus-high/verify.py

Coordinates: Blender Z up, meters, the sofa's front faces -Y, origin at the
bottom center of the footprint. All objects are built in world coordinates
(identity transforms). The pillow is built lying flat, centered on the origin.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "sofa"
VARIANT = "opus-high"
BLEND = output_path("blender", "props", f"sofa__{VARIANT}.blend")
GLB_SOFA = output_path("assets", "props", "sofa", f"sofa__{VARIANT}.glb")
GLB_PILLOW = output_path("assets", "props", "sofa", f"sofa_pillow__{VARIANT}.glb")
SCRATCH = scratch_dir(NAME)  # set ARCOLOGY_RENDER_DIR to put thumbnails elsewhere

# --- Fixed contract (the Godot scene depends on these) ---------------------------
FRONT_Y, BACK_Y = -0.445, 0.445
SEAT_TOP = 0.44           # seat surface the game's sit point assumes (collision top)

# Legs and base
LEG_H = 0.13
LEG_R_TOP, LEG_R_BOTTOM = 0.017, 0.011
LEGS = [(-0.97, -0.36), (0.97, -0.36), (-0.97, 0.36), (0.97, 0.36), (0.0, -0.30), (0.0, 0.34)]
ARM_X_IN, ARM_X_OUT = 0.89, 1.05
ARM_TOP = 0.625
DECK_Z = 0.30             # top of the upholstered base (seat deck)
BASE_Y0, BASE_Y1 = -0.43, 0.44

# Seat cushions (three, pressed together between the arms)
SEAT_X = [-0.5933, 0.0, 0.5933]
SEAT_W = 0.60
SEAT_Y0, SEAT_Y1 = -0.445, 0.095  # 0.54 deep
SEAT_Z0, SEAT_Z1 = 0.295, 0.425   # box before crown and sag
SEAT_CROWN = 0.028
SEAT_SAG = [0.022, 0.008, 0.013]  # left (favorite), middle, right
SEAT_SAG_Y = -0.14                # where people sit
SIT_Y = -0.15                     # where the seat height is measured

# Back cushions (upright build, then leaned back about their bottom-back edge)
BACK_W, BACK_T, BACK_H = 0.60, 0.16, 0.53
BACK_PIVOT_Y, BACK_PIVOT_Z = 0.25, 0.30
BACK_TILT = 8.0
# Lived-in variation per cushion (left, middle, right): extra lean (deg), yaw (deg), seat yaw (deg)
BACK_LEAN = [1.8, 0.0, -0.8]
BACK_YAW = [1.2, -0.4, -1.0]
SEAT_YAW = [0.7, -0.3, 0.4]

# Back frame (outside back, between the arms)
FRAME_Y0, FRAME_Y1 = 0.30, 0.445
FRAME_Z0, FRAME_Z1 = 0.295, 0.72

# Collision boxes (Blender lo, hi); the back box starts where the seat block ends
COL_SPLIT_Y = 0.12
COLLISION = {
    "ColSeat": ((-ARM_X_IN, FRONT_Y, 0.0), (ARM_X_IN, COL_SPLIT_Y, SEAT_TOP)),
    "ColBack": ((-ARM_X_IN, COL_SPLIT_Y, 0.0), (ARM_X_IN, BACK_Y, 0.85)),
    "ColArmL": ((-ARM_X_OUT, FRONT_Y, 0.0), (-ARM_X_IN, BACK_Y, ARM_TOP)),
    "ColArmR": ((ARM_X_IN, FRONT_Y, 0.0), (ARM_X_OUT, BACK_Y, ARM_TOP)),
}

# Throw pillow
PILLOW_SIZE = (0.45, 0.45)
PILLOW_T = 0.16
PILLOW_MASS = 0.45  # kg, feather/fiber insert

# Colors (linear). Sofa: a deep, muted petrol that holds up under warm 2700 K light
# and echoes the cool city outside; pillows: the palette's rust, as terracotta linen.
SOFA_COLOR = (0.018, 0.044, 0.051)
PILLOW_COLOR = (0.22, 0.056, 0.024)
LEG_COLOR = (0.028, 0.031, 0.036)  # gunmetal powder coat

CUSHION_MAT = "SofaCushions"
FRAME_MAT = "SofaFrame"
PILLOW_MAT = "SofaPillow"
TEX_SIZE = 2048
PILLOW_TEX = 1024


# --- Parts (tagged in build.py) -------------------------------------------------
def cushion_objects():
    return part_objects("cushions", mesh_only=True)


def frame_objects():
    return part_objects("frame", mesh_only=True)


def sofa_objects():
    return frame_objects() + cushion_objects()


def collision_objects():
    return part_objects("sofa_col")


def pillow_objects():
    return part_objects("pillow", mesh_only=True)
