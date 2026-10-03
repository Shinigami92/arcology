"""Silena Vesper, the player avatar (D-037, docs/characters/silena_vesper.md): body
proportions, glove and sleeve contracts, paths and parts. Built on blender/lib
(D-028); quick reference: blender/lib/README.md.

Stage 1 = the gloved hands (glove.py, leather.py, filigree.py, poses.py); stage 2
= the coat sleeves over them (sleeve.py, coat_leather.py, embroidery.py): each
arm is one glb, glove + sleeve from the shoulder to the fingertips on the
`<Side>UpperArm` subtree plus a `<Side>LowerArmTwist` bone. The full MPFB body
(`Body`) and its humanoid skeleton (`Armature`) are built once and kept in the
.blend; every exported part is cut from or fitted over them (later stages: body,
head). Render-only test poses: test_poses.py.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/characters/silena_vesper/build.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/bake.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/export.py
  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/render.py -- [--quick] [--out DIR] [--shots ...] [--sides ...]
  blender -b --factory-startup --python blender/characters/silena_vesper/verify.py

ARCOLOGY_OUT_DIR=<folder> sends the .blend and the glbs there instead of the repo.

Coordinates: Blender Z up, meters, the character faces -Y with her feet at the
origin; her left side is +X. The glbs stay in body coordinates (nothing is
moved to the origin): Godot places the hand bone at the controller and solves
the shoulder and elbow.
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
GLB = {side: os.path.join(GLB_DIR, f"{NAME}_arm_{side.lower()}.glb") for side in ("Left", "Right")}
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

# --- Coat sleeve contract (stage 2; t = distance along the sleeve's centerline from the
# wrist joint: up the forearm, around the elbow fillet, up the upper arm) ---------------
SLEEVE_COLUMNS = 40          # vertices around the sleeve
ELBOW_FILLET = 0.08          # centerline fillet radius at the elbow (rest bend ~39 degrees)
PAST_SHOULDER = 0.08         # centerline continues this far beyond the shoulder joint
SLEEVE_OPEN_T = 0.050        # the opening's fold (turned-back cuff): the glove shows below it
CUFF_TOP_T = 0.115           # the turned-back cuff's free top edge
FOLD_R = 0.0016              # fold radius at the opening (two layers of coat leather)
LIP_R = 0.0013               # the cuff's rolled top edge
CUFF_GAP = 0.0040            # opening clears the glove's gauntlet by this much
CUFF_STANDOFF = 0.0060       # the cuff's top edge stands off the sleeve
SLEEVE_LINING_TOP_T = 0.090  # the inside of the sleeve seen in the opening ends here (hidden)
GLOVE_HIDE_T = 0.076         # glove geometry above this is inside the sleeve: deleted
ARMHOLE_C0 = -0.012          # armhole seam: t_top = t_shoulder + C0 + C1 * cos(angle from the top)
ARMHOLE_C1 = 0.045
CAP_DOME = 0.020             # the dome closing the sleeve inside the armhole (bulges toward the body)
# LowerArmTwist (rig.add_twist_bone, Godot turns it by ~70 % of the hand's roll): the
# LowerArm weight of sleeve and glove moves to it fully below TWIST_T[0] (the whole cuff
# rolls rigidly, so neither cuff pinches), not above TWIST_T[1] (below the elbow).
TWIST_AT = 0.5
TWIST_T = (0.118, 0.212)
TWIST_SHARE = 0.7
# Linear blend skinning pulls a twisting blend toward the axis (by cos(a/2) at an even
# blend); the sleeve is that much fuller there for a roll of TWIST_FULL degrees, so the
# pinch at a full +-90 degree wrist roll halves (and a straight sleeve bulges ~3 mm).
TWIST_FULL = 45.0

COAT_LINING = (0.026, 0.016, 0.048)       # violet lining seen in the cuff's opening
COAT_MAT = "SilenaCoat"      # final baked material of the sleeve


def twist_factor(t):
    """Share of a vertex's LowerArm weight that moves to LowerArmTwist at t."""
    lo, hi = TWIST_T
    x = min(max((t - lo) / (hi - lo), 0.0), 1.0)
    return 1.0 - x * x * (3.0 - 2.0 * x)


def twist_inflation(t):
    """Radius factor that pre-compensates the twist blend's pinch (see TWIST_FULL)."""
    import math
    f = twist_factor(t)
    a = math.radians(TWIST_FULL)
    return 1.0 / math.hypot(1.0 - f + f * math.cos(a), f * math.sin(a))

# Poses (glTF animation names; Godot's hand blend tree mixes them per finger)
POSES = ("Open", "Grip")
GRIP_DIAMETER = 0.038        # controller handle


# --- Parts (tagged in build.py) ------------------------------------------------------
def glove(side):
    obs = part_objects(f"glove_{side.lower()}", mesh_only=True)
    return obs[0] if obs else None


def sleeve(side):
    obs = part_objects(f"sleeve_{side.lower()}", mesh_only=True)
    return obs[0] if obs else None


def arm_mesh(side):
    """The exported mesh (glove + sleeve joined by bake.py)."""
    obs = part_objects(f"arm_{side.lower()}", mesh_only=True)
    return obs[0] if obs else None


def body():
    return part_objects("body", mesh_only=True)[0]


def armature():
    import bpy
    return bpy.data.objects["Armature"]
