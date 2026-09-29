"""Bed (A/B variant opus-high): dimensions, paths and parts. Built on blender/lib (D-028).

A modern low platform double bed: a floating dark walnut platform on six
brushed gunmetal legs, a plain walnut headboard with a gunmetal inlay bar,
a mattress in a fitted sheet, a thick linen duvet (cloth-simulated) turned
down at the head end, two pillows leaning against the headboard and a
slate-blue wool throw across the foot. Lived-in: the left side (-X) was
slept in (mattress dent, dented pillow, duvet corner pulled back a little).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/bed__opus-high/build.py
  blender -b --factory-startup blender/props/bed__opus-high.blend --python blender/props/bed__opus-high/bake.py
  blender -b --factory-startup blender/props/bed__opus-high.blend --python blender/props/bed__opus-high/export.py
  blender -b --factory-startup blender/props/bed__opus-high.blend --python blender/props/bed__opus-high/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/bed__opus-high/verify.py

Coordinates: Blender Z up, meters, origin at the bottom center of the
footprint, the head end at +Y (against the wall), the foot end at -Y. All
objects are built in world coordinates (identity transforms).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "bed__opus-high"
TAG = "opus-high"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB = output_path("assets", "props", "bed", f"{NAME}.glb")
SCRATCH = scratch_dir("bed__opus-high")  # render.py --out overrides

# --- Fixed contract (the Godot scene depends on these) ---------------------------
HALF_W = 0.85             # frame x = +-0.85 (1.70 wide)
FOOT_Y, HEAD_Y = -1.08, 1.07  # 2.15 long
SLEEP_TOP = 0.50          # duvet top over the seating area (+- 0.03)

# Platform (floating walnut slab) and legs
PLAT_Z0, PLAT_Z1 = 0.14, 0.26
PLAT_Y1 = 1.01            # meets the headboard front
LEG_H = PLAT_Z0
LEG_SIZE = 0.045
LEGS = [(sx * 0.70, y) for sx in (-1.0, 1.0) for y in (-0.93, -0.03, 0.86)]

# Headboard (walnut panel, gunmetal inlay bar)
HB_Y0, HB_Y1 = PLAT_Y1, HEAD_Y
HB_Z0, HB_Z1 = 0.08, 1.02
INLAY_Z = 0.885           # center of the inlay bar
INLAY_H, INLAY_D = 0.016, 0.008

# Mattress (fitted sheet)
MAT_HALF_W = 0.80
MAT_Y0, MAT_Y1 = -1.01, 0.99
MAT_Z0, MAT_Z1 = PLAT_Z1, 0.447
MAT_R = 0.035
DENT = ((-0.30, -0.05), (0.28, 0.62), 0.018)  # where someone slept: center xy, radii, depth

# Duvet (simulated): flat size, thickness, turn-down fold at the head end
DUVET_W = 2.02
DUVET_T = 0.034
DUVET_FOOT_Y = MAT_Y0 - 0.22     # hem of the flat sheet before it drapes over the foot
FOLD_Y = 0.40                    # fold line at x = 0 (slightly diagonal, see build.py)
FOLD_SKEW = 0.09                 # fold line y change per meter of x
# slack patches (x, y, radius x, radius y, weight): the slept-in left half, a kicked foot area
DUVET_SLACK = [(-0.27, -0.12, 0.24, 0.52, 1.0), (0.25, -0.55, 0.26, 0.22, 0.6), (0.30, 0.12, 0.22, 0.20, 0.45)]
FOLD_BACK = 0.34                 # turned-down length
DUVET_SPACING = 0.034

# Pillows (two, leaning against the headboard)
PILLOW_SIZE = (0.72, 0.50)
PILLOW_T = 0.20
PILLOW_TILT = 34.0               # degrees from horizontal
PILLOWS = [  # x center, yaw (deg), head dent depth
    (-0.385, 2.5, 0.030),
    (0.375, -1.8, 0.010),
]

# Throw (slate-blue wool runner across the foot)
THROW_SIZE = (1.80, 0.62)        # x, y flat
THROW_T = 0.008
THROW_CENTER = (0.02, -0.68)
THROW_YAW = 4.0
THROW_SPACING = 0.030

# Collision boxes (Blender lo, hi)
COLLISION = {
    "BedBlock": ((-HALF_W, FOOT_Y, 0.0), (HALF_W, HB_Y0, SLEEP_TOP)),
    "Headboard": ((-HALF_W, HB_Y0, 0.0), (HALF_W, HEAD_Y, HB_Z1)),
}

# Colors (linear)
WALNUT_DARK = (0.011, 0.0048, 0.0022)
WALNUT_MID = (0.033, 0.0140, 0.0060)
WALNUT_LIGHT = (0.060, 0.027, 0.0120)
GUNMETAL = (0.070, 0.078, 0.090)       # style guide #2E3238, lifted to a metal F0
DUVET_COLOR = (0.60, 0.565, 0.49)      # warm off-white #D8D2C4, slightly darker for fabric
PILLOW_COLOR = (0.63, 0.595, 0.52)
SHEET_COLOR = (0.53, 0.515, 0.475)     # a touch greyer than the duvet
THROW_COLOR = (0.040, 0.058, 0.080)    # muted slate blue

FRAME_MAT = "BedFrame"
LINEN_MAT = "BedLinen"
THROW_MAT = "BedThrow"
FRAME_TEX = 2048
LINEN_TEX = 2048
THROW_TEX = 1024


# --- Parts (tagged in build.py) -------------------------------------------------
def frame_objects():
    return part_objects("frame", mesh_only=True)


def linen_objects():
    return part_objects("linen", mesh_only=True)


def throw_objects():
    return part_objects("throw", mesh_only=True)


def bed_objects():
    return frame_objects() + linen_objects() + throw_objects()


def collision_objects():
    return part_objects("bed_col")
