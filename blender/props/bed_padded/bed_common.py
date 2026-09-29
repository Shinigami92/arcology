"""Padded-headboard bed (Fable 5.1, runner-up of the bedroom A/B, kept for other apartments, D-032): dimensions, paths and parts. Built on blender/lib (D-028).

A modern low platform double bed for the apartment bedroom: dark walnut
veneer platform and headboard, brushed gunmetal legs and headboard cap, a
padded linen headboard panel, a mattress in a stone-grey fitted sheet, an
off-white linen duvet turned down at the head end and hanging over the sides
and foot, two pillows leaning on the headboard, and a muted clay wool throw
folded across the foot. Made but lived-in: somebody sat on the left edge,
the duvet has been pulled up and left rumpled.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/bed_padded/build.py
  blender -b --factory-startup blender/props/bed_padded.blend --python blender/props/bed_padded/bake.py
  blender -b --factory-startup blender/props/bed_padded.blend --python blender/props/bed_padded/export.py
  blender -b --factory-startup blender/props/bed_padded.blend --python blender/props/bed_padded/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/bed_padded/verify.py

Coordinates: Blender Z up, meters, origin at the bottom center of the
footprint, the head end at +Y (against the wall), the foot at -Y. All objects
are built in world coordinates (identity transforms).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "bed_padded"
RENDER_NAME = "bed_padded"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB = output_path("assets", "props", "bed", f"{NAME}.glb")
SCRATCH = scratch_dir(NAME)  # set ARCOLOGY_RENDER_DIR to put thumbnails elsewhere

# --- Fixed contract (the Godot scene depends on these) ---------------------------
LIMIT_X, LIMIT_Y = 0.86, 1.08
SLEEP_TOP = 0.50            # duvet surface over the seating area (collision top), +-0.03
SIT_POINTS = [(-0.66, -0.50), (-0.66, -0.20), (-0.66, 0.05), (0.66, -0.50), (0.66, -0.20), (0.66, 0.05), (0.0, -0.30)]

# Platform (walnut box with a recess for the mattress) and legs
FRAME_X = 0.85
FRAME_Y0, FRAME_Y1 = -1.06, 1.00
FRAME_Z0, FRAME_Z1 = 0.12, 0.27
RECESS_X, RECESS_Y0, RECESS_Y1, RECESS_Z = 0.795, -1.01, 0.96, 0.22
LEG_SIZE, LEG_H = 0.06, FRAME_Z0
LEGS = [(-0.73, -0.93), (0.73, -0.93), (-0.73, 0.86), (0.73, 0.86)]

# Headboard: walnut panel, gunmetal cap, padded linen panel on its front
HEAD_Y0, HEAD_Y1 = 1.00, 1.06
HEAD_Z0, HEAD_Z1 = 0.10, 1.02
CAP_T, CAP_LIP = 0.015, 0.005
PAD_X, PAD_Y0, PAD_Y1, PAD_Z0, PAD_Z1 = 0.75, 0.96, 1.005, 0.42, 0.88

# Mattress (in a fitted sheet), sits in the recess
MAT_X, MAT_Y0, MAT_Y1 = 0.78, -1.00, 0.95
MAT_Z0, MAT_Z1 = RECESS_Z, 0.46
MAT_R, MAT_CROWN = 0.035, 0.012

# Duvet: lies on the mattress from the foot to the fold line, turned down toward the foot
DUVET_T = 0.036             # filled thickness on the mattress
DUVET_FOLD_Y = 0.36         # fold line (top edge of the turned-down duvet)
DUVET_HEM_Y = 0.13          # where the turned-down layer's hem lies on top (clear of the sit points)
DUVET_LAYER2 = 0.035        # extra height of the turned-down layer
DUVET_OVERHANG = {"-x": 0.215, "+x": 0.24, "-y": 0.225, "+y": 0.104}
DUVET_RADIUS = {"-x": 0.035, "+x": 0.035, "-y": 0.035, "+y": 0.05}
SIT_DENT = ((-0.62, -0.18), (0.24, 0.20), 0.020)   # center, radii, depth: someone sat on the left edge

# Pillows: lean on the headboard pad
PILLOW_SIZE, PILLOW_T = (0.70, 0.48), 0.15
PILLOW_X = [-0.37, 0.37]
PILLOW_Y, PILLOW_TILT = 0.69, 22.0
PILLOW_YAW = [2.5, -1.5]

# Throw: folded wool blanket across the foot, tipped over the +x side
THROW_RECT = (-0.62, -0.93, 0.80, -0.50)
THROW_T = 0.028
THROW_OVERHANG = {"+x": 0.16}

# Collision boxes (Blender lo, hi)
COLLISION = {
    "ColBed": ((-FRAME_X, FRAME_Y0, 0.0), (FRAME_X, HEAD_Y0, SLEEP_TOP)),
    "ColHeadboard": ((-FRAME_X, PAD_Y0, 0.0), (FRAME_X, HEAD_Y1 + CAP_LIP, HEAD_Z1 + CAP_T)),
}

# Colors (linear). Walnut from a dark #4E3323; gunmetal #2E3238; linen from the palette's
# warm off-white #D8D2C4; the sheet a stone grey; the throw a muted clay (the palette's rust, dusty).
WALNUT = (0.052, 0.025, 0.013)
GUNMETAL = (0.028, 0.033, 0.040)
LINEN = (0.68, 0.64, 0.55)
SHEET = (0.46, 0.44, 0.39)
PAD = (0.40, 0.38, 0.34)
THROW = (0.12, 0.058, 0.038)

FRAME_MAT = "BedFrame"
BEDDING_MAT = "BedBedding"
TEX_SIZE = 2048


# --- Parts (tagged in build.py) -------------------------------------------------
def frame_objects():
    return part_objects("frame", mesh_only=True)


def bedding_objects():
    return part_objects("bedding", mesh_only=True)


def bed_objects():
    return frame_objects() + bedding_objects()


def collision_objects():
    return part_objects("bed_col")
