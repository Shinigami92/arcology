"""Apartment front door (steel security frame + hinged leaf): contract dimensions, paths and parts.
Built on blender/lib (D-028); quick reference: blender/lib/README.md. Body + hinged door pattern
from the fridge.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/door_entrance/build.py
  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/bake.py
  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/export.py
  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/door_entrance/verify.py

Coordinates: Blender Z up, meters. Origin = bottom center of the rough wall opening on the
wall's center plane. -Y (Godot +Z) is the apartment side, the side the leaf swings toward;
+Y is the building corridor. The hinge is on the -X side.

Frame objects are built in world coordinates. The leaf is built around its root object
`Leaf` on the hinge axis (HINGE), so its glb origin is the hinge axis at the floor; it
opens with a negative rotation about Z (toward -Y). Lever and thumb-turn objects are not
parented (they export with their own origin on the spindle / deadbolt axis); verify.py and
render.py parent them to the leaf at runtime.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "door_entrance"
BLEND = output_path("blender", "props", f"{NAME}.blend")
ASSET_DIR = ("assets", "props", NAME)
GLB_FRAME = output_path(*ASSET_DIR, f"{NAME}_frame.glb")
GLB_LEAF = output_path(*ASSET_DIR, f"{NAME}_leaf.glb")
GLB_LEVER_APT = output_path(*ASSET_DIR, f"{NAME}_lever_apartment.glb")
GLB_LEVER_COR = output_path(*ASSET_DIR, f"{NAME}_lever_corridor.glb")
GLB_THUMBTURN = output_path(*ASSET_DIR, f"{NAME}_thumbturn.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails (render.py --out overrides)

# --- Fixed contract (the apartment generator cuts this opening) -------------------
OPEN_W, OPEN_H = 0.90, 2.10    # rough opening
WALL_Y = 0.10                  # wall faces at +-WALL_Y
OX = OPEN_W / 2                # 0.45

# --- Frame: pressed-steel wrap-around profile ------------------------------------
CASING_OUT = 0.05              # casing reaches 50 mm past the opening edge on both faces
CASING_T = 0.012               # casing face 12 mm proud of the wall
Y_APT = -(WALL_Y + CASING_T)   # -0.112 apartment casing face
Y_COR = WALL_Y + CASING_T      # +0.112 corridor casing face
REBATE_IN = 0.025              # rebate soffit 25 mm inside the rough opening (apartment part)
STOP_IN = 0.045                # stop 45 mm inside (corridor part)
STOP_Y = -0.040                # stop face (the leaf's corridor face closes against its seal)
SOFFIT_X = OX - REBATE_IN      # 0.425
STOP_X = OX - STOP_IN          # 0.405
HEAD_SOFFIT_Z = OPEN_H - REBATE_IN  # 2.075
HEAD_STOP_Z = OPEN_H - STOP_IN      # 2.055
SEAL_Y0, SEAL_Y1 = -0.044, STOP_Y   # rubber seal on the stop face, 1 mm off the closed leaf
THRESHOLD_H = 0.010            # beveled threshold peak (<= 15 mm)
THRESHOLD_Y = 0.125            # threshold runs y -0.125..0.125, ramps 40 mm

# --- Leaf ------------------------------------------------------------------------
LEAF_T = 0.065
LEAF_Y0 = -0.110               # apartment face (2 mm behind the casing face)
LEAF_Y1 = LEAF_Y0 + LEAF_T     # -0.045 corridor face
LEAF_X0 = -SOFFIT_X + 0.003    # hinge edge, 3 mm gap
LEAF_X1 = SOFFIT_X - 0.004     # latch edge at the apartment face, 4 mm gap
LATCH_BEVEL = 0.0524           # tan(3 deg): latch edge leans back toward the corridor face
LEAF_Z0 = 0.016                # slab bottom; the drop seal reaches 0.0125
SEAL_Z0 = 0.0125
LEAF_Z1 = HEAD_SOFFIT_Z - 0.003  # 2.072
LEAF_CX = (LEAF_X0 + LEAF_X1) / 2

# Hinges: weld-on barrel hinges (frame knuckle below, leaf knuckle above), barrel proud of the
# apartment face so the leaf clears the casing through the full swing.
BARREL_R = 0.0095
HINGE = Vector((-SOFFIT_X + 0.0015, -0.124, 0.0))  # hinge axis at the floor
HINGE_ZS = (0.25, 1.10, 1.85)  # hinge centers (knuckle split)
KNUCKLE = 0.065
OPEN_DEG = 100.0

# Hardware (all on the latch side, backset 60 mm)
BACKSET = 0.060
LX = LEAF_X1 - BACKSET         # 0.361 spindle / deadbolt x
LEVER_Z = 1.10                 # handle height (seated reach)
BOLT_Z = 1.30                  # deadbolt (thumb-turn, smart lock, key cylinder)
ROSE_PROUD = 0.009
LEVER_REACH = 0.062            # arm center from the leaf face
LEVER_LEN = 0.135              # spindle to tip
LOCK_W, LOCK_D = 0.062, 0.026  # smart-lock housing (apartment face)
LOCK_Z0, LOCK_Z1 = 1.232, 1.392  # thumb-turn at BOLT_Z, a fingerprint pad above it
LOCK_FRONT_Y = LEAF_Y0 - LOCK_D  # -0.136, thumb-turn origin plane
LED_R0, LED_R1 = 0.0178, 0.0205  # status ring around the thumb-turn
PEEP_Z = 1.55
PLATE_Z = 1.73                 # unit number plate center (corridor face)
UNIT_NUMBER = "4417"

# Grip points (world, closed), exported as HandleGrip* empties under the leaf
GRIP_APT = Vector((LX - 0.075, LEAF_Y0 - LEVER_REACH, LEVER_Z))
GRIP_COR = Vector((LX - 0.075, LEAF_Y1 + LEVER_REACH, LEVER_Z))

# --- Colors (linear) --------------------------------------------------------------
GUNMETAL = (0.0273, 0.0319, 0.0395)       # #2E3238 powder coat
GUNMETAL_WORN = (0.20, 0.205, 0.215)      # coat chipped to bare steel
APT_PAINT = (0.184, 0.171, 0.147)         # #77736B warm greige satin
STEEL = (0.50, 0.51, 0.53)                # brushed stainless (#8A9099 reads darker as metal)
GRIME = (0.035, 0.030, 0.024)
LED_CYAN = (0.0015, 0.693, 0.807)         # #05D9E8

FRAME_MAT = "DoorEntranceFrame"
LEAF_MAT = "DoorEntranceLeaf"
HW_MAT = "DoorEntranceHardware"           # levers + thumb-turn share one atlas
LED_MAT = "door_entrance_lock_led"        # unbaked, Godot switches it (cyan / red / green)
LED_STRENGTH = 4.0                        # like the fridge's switchable light
FRAME_TEX, LEAF_TEX, HW_TEX = 2048, 2048, 1024


# --- Parts (tagged in build.py) -------------------------------------------------
def frame_objects():
    """Render meshes of the frame glb (no collision)."""
    return part_objects("body", mesh_only=True)


def frame_collision_objects():
    return part_objects("body_col")


def leaf_objects():
    """Leaf root, its meshes (slab, LED) and the HandleGrip empties."""
    return part_objects("door")


def leaf_meshes():
    return part_objects("door", mesh_only=True)


def lever_apartment():
    return part_objects("lever_apartment", mesh_only=True)


def lever_corridor():
    return part_objects("lever_corridor", mesh_only=True)


def thumbturn():
    return part_objects("thumbturn", mesh_only=True)


def hardware_objects():
    return lever_apartment() + lever_corridor() + thumbturn()
