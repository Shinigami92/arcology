"""Silena Vesper, the player avatar (D-037, docs/characters/silena_vesper.md): body
proportions, glove contract, paths and parts. Built on blender/lib (D-028);
quick reference: blender/lib/README.md.

Stage 1 = the gloved hands. The full MPFB body (`Body`) and its humanoid
skeleton (`Armature`) are built once and kept in the .blend; every exported
part is cut from them (later stages: sleeves, body, head).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/characters/silena_vesper/build.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/bake.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/export.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/characters/silena_vesper/verify.py

ARCOLOGY_OUT_DIR=<folder> sends the .blend and the glbs there instead of the repo.

Coordinates: Blender Z up, meters, the character faces -Y with her feet at the
origin; her left side is +X. The glbs stay in body coordinates (the hand is
not moved to the origin): Godot aligns the hand bone to the controller.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "silena_vesper"
BLEND = output_path("blender", "characters", f"{NAME}.blend")
GLB_DIR = output_path("assets", "characters", NAME)
GLB = {side: os.path.join(GLB_DIR, f"{NAME}_hand_{side.lower()}.glb") for side in ("Left", "Right")}
SCRATCH = scratch_dir(NAME)

# --- Body (MPFB macros, 0..1) --------------------------------------------------------
# Tall slender elf: 1.91 m (eyes at ~1.80 m = XR Tools' standard_height), low weight,
# low-moderate muscle, idealized proportions, pale. Measured by build.py.
MACROS = dict(gender=0.0, age=0.5, muscle=0.3, weight=0.22, proportions=1.0, height=0.716,
              cupsize=0.45, firmness=0.6)
RACE = {"caucasian": 1.0}
# Long, slender fingers (MPFB hand targets), both sides so the body stays symmetric.
TARGETS = {}
for _s in ("l", "r"):
    TARGETS[f"hands/{_s}-hand-fingers-length-incr"] = 0.28
    TARGETS[f"hands/{_s}-hand-fingers-diameter-decr"] = 0.35
SKIN = "young_caucasian_female"  # MakeHuman system asset (CC0); pale, cool undertone
HEIGHT_TARGET = 1.91
HAND_LENGTH_RANGE = (0.19, 0.20)  # wrist crease to middle fingertip

# --- Glove contract (meters; t = distance from the wrist joint up the forearm) -------
GLOVE_OFFSET = 0.0010        # leather shell over the skin (hand and fingers)
PALM_OFFSET = 0.0012         # a little thicker on the palm
TIP_SLACK = 0.0014           # extra length at the fingertips (gloves are never skin tight there)
STRAP_T = 0.016              # wrist strap center (the wrist is narrowest at t = 0..12 mm)
STRAP_W = 0.015              # strap width
STRAP_THICK = 0.0017
JUNCTION_T = STRAP_T         # hand shell ends here, hidden under the strap
CUFF_START_T = STRAP_T - 0.005
CUFF_TOP_T = 0.096           # gauntlet cuff top on the back of the forearm (~1/3 of 0.26 m)
CUFF_SLANT = 0.010           # top edge is that much shorter on the palm side
CUFF_OFFSET = 0.0016         # cuff over the skin where it starts
CUFF_FLARE = 0.0105          # extra radius at the cuff top
CUFF_SEGMENTS = 36
CUFF_RING_STEP = 0.0045
FOLD_AMP = 0.0007            # soft horizontal bunching of the cuff
FOLD_PERIOD = 0.019
HEM = 0.0016                 # rolled cuff edge thickness
LINING_DEPTH = 0.013         # visible lining inside the cuff before it closes
SNAP_R = 0.0052

# Colors (linear) from the spec's palette
LEATHER = (0.0070, 0.0060, 0.0080)        # #141216
LEATHER_WORN = (0.030, 0.026, 0.028)
LINING = (0.030, 0.018, 0.055)          # deep violet suede lining (the underlayer violet)
FILIGREE = (0.105, 0.051, 0.238)          # #5B3F86
THREAD = (0.020, 0.018, 0.022)
GUNMETAL = (0.085, 0.090, 0.100)
GUNMETAL_DARK = (0.040, 0.042, 0.047)

GLOVE_MAT = "SilenaGlove"    # final baked material (leather + gunmetal snap)
TEX_SIZE = 2048

# Poses (glTF animation names; Godot's hand blend tree mixes them per finger)
POSES = ("Open", "Grip")
GRIP_DIAMETER = 0.038        # controller handle


# --- Parts (tagged in build.py) ------------------------------------------------------
def glove(side):
    obs = part_objects(f"glove_{side.lower()}", mesh_only=True)
    return obs[0] if obs else None


def body():
    return part_objects("body", mesh_only=True)[0]


def armature():
    import bpy
    return bpy.data.objects["Armature"]
