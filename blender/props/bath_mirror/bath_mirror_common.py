"""Bathroom mirror set (luxury hotel bathroom): dimensions, paths and parts. Built on blender/lib (D-028).

Two assets from one source file:

- bath_mirror: a 1.20 x 0.90 m mirror floating 35 mm off the wall on a hidden
  cleat, in a slim brushed-gunmetal frame (the set's fixture metal). A warm
  LED strip on the back lights the wall: the halo is an emission-only ring quad
  on the wall (`mirror_led`, additive in Godot). A capacitive touch sensor
  (etched sun icon + ring, `mirror_touch_led`) sits on the glass, bottom center.
- bath_mirror_magnifier: a round 5x cosmetic mirror on a swing arm. Two glbs:
  the wall bracket (static) and the arm + head (swings about a vertical pivot).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/bath_mirror/build.py
  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/bake.py
  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/export.py
  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/bath_mirror/verify.py

Coordinates: Blender Z up, meters, the wall plane is Y = 0 and everything sits
at Y <= 0 (front -Y, Godot +Z). The main mirror's origin is the bottom center
of its back on the wall plane. The magnifier is built in the same file at its
intended spot (MAG_POS, 0.9 m to the mirror's +X side, 1.45 m in the room) so
verify.py can check the swing against the mirror; it exports at its own
origins: the bracket's on the wall plane behind the pivot axis, the arm's on
the pivot axis (PIVOT_Y in front of the wall), both at the pivot height.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "bath_mirror"
MAG_NAME = "bath_mirror_magnifier"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB = output_path("assets", "props", NAME, f"{NAME}.glb")
GLB_BRACKET = output_path("assets", "props", MAG_NAME, f"{MAG_NAME}_bracket.glb")
GLB_ARM = output_path("assets", "props", MAG_NAME, f"{MAG_NAME}_arm.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails (render.py --out overrides)

# --- Fixed contract: main mirror (the Godot scene depends on these) --------------
W, H = 1.20, 0.90              # outer size of the frame
HX = W / 2
STANDOFF = 0.035               # wall to the frame's back edge (hidden mount)
FRAME_DEPTH = 0.022            # frame skirt, front to back
FRONT_Y = -(STANDOFF + FRAME_DEPTH)   # -0.057: the frame's front face
LIP = 0.008                    # visible frame face around the glass
WALL_T = 0.0015                # frame wall thickness (lip and skirt)
GLASS_Y = FRONT_Y + WALL_T + 0.0002   # -0.0553: mirror surface (just behind the lip)
GLASS_T = 0.005
BACKING_Y0, BACKING_Y1 = -0.0505, -0.0465  # aluminium composite backing behind the glass

# LED strip on the back, shining at the wall (inset from the outer edge)
LED_INSET = 0.030
LED_W, LED_D = 0.012, 0.007    # channel width, depth (toward the wall)
LED_Y = BACKING_Y1 + LED_D     # -0.0395: channel face toward the wall
LED_STRENGTH = 3.0             # glb emission strength of mirror_led (halo on)

# Halo on the wall (emission-only ring quad, additive in Godot)
HALO_Y = -0.002
HALO_OUT = (0.22, 0.20)        # how far the quad reaches past the frame: x sides, z top/bottom
HALO_IN = 0.020                # ring's inner edge, hidden behind the frame
HALO_TEX = 512

# Touch sensor (etched icon + ring light), bottom center on the glass
TOUCH_X, TOUCH_Z = 0.0, 0.070  # center above the frame's bottom edge (room: 1.18 + 0.07 = 1.25 m)
TOUCH_R0, TOUCH_R1 = 0.0105, 0.0125   # ring light
TOUCH_Y = GLASS_Y - 0.0003     # decal plane just in front of the glass
TOUCH_STRENGTH = 2.0
TOUCH_AREA = (0.050, 0.050, 0.030)    # suggested press Area3D box (Godot x, y, z)

LIMIT_LO = Vector((-HX - HALO_OUT[0], FRONT_Y, -HALO_OUT[1]))
LIMIT_HI = Vector((HX + HALO_OUT[0], 0.0, H + HALO_OUT[1]))

# --- Magnifier (local to its bracket origin: wall plane, pivot height) -----------
MAG_POS = Vector((0.90, 0.0, 0.27))   # in the main mirror's frame (room: x 0.5, y 1.45 at yaw 180)
PIVOT_Y = -0.040               # vertical pivot axis in front of the wall
ROSETTE_R, ROSETTE_T = 0.032, 0.008
KNUCKLE_R = 0.011
BRACKET_KNUCKLE = (0.0125, 0.034)     # |z| range of the bracket's top and bottom knuckles
ARM_KNUCKLE = 0.0115           # arm knuckle z +-
ARM_R = 0.0065
HEAD_X = 0.315                 # pivot to head center along the folded arm (+X)
HEAD_R = 0.102                 # bezel outer radius (head 0.204 m across)
GLASS_R = 0.0945
HEAD_FRONT, HEAD_BACK = 0.009, -0.016  # head thickness along its front normal (-Y when folded)
GLASS_W = 0.0062               # glass plane along the front normal
SWIVEL_X = HEAD_X - HEAD_R - 0.004    # head swivel knuckle on the near rim
SWING_MAX = 170.0              # degrees, opening = negative rotation about Blender Z (Godot Y)
GRIP_LOCAL = Vector((HEAD_X + HEAD_R - 0.003, 0.0, 0.0))   # far rim, arm-local

# Colors (linear)
FIXTURE = (0.0437, 0.0482, 0.0578)     # #3B3E44 gunmetal PVD
FIXTURE_POLISH = (0.075, 0.080, 0.090)
ALU_DARK = (0.030, 0.031, 0.034)       # hidden anodized mount, LED channel
BACKING = (0.020, 0.020, 0.021)
DIFFUSER = (0.80, 0.80, 0.78)
WARM_LED = (1.0, 0.558, 0.275)         # #FFC58F, 3000 K
WALL_PLASTER = (0.686, 0.644, 0.552)   # render only

# --- Materials --------------------------------------------------------------------
BODY_MAT = "BathMirror"                 # baked frame + mount
GLASS_MAT = "mirror_glass"              # Godot assigns its reflective material
LED_MAT = "mirror_led"                  # halo + LED diffuser, switched by Godot
TOUCH_MAT = "mirror_touch_led"          # sensor icon + ring
BRACKET_MAT = "BathMirrorMagnifierBracket"
ARM_MAT = "BathMirrorMagnifierArm"
TEX_BODY = 1024
TEX_BRACKET = 512
TEX_ARM = 512


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Baked render meshes of the main mirror (frame, backing, mount, LED channel)."""
    return part_objects("body", mesh_only=True)


def mirror_fx_objects():
    """Unbaked main-mirror meshes: glass, halo + diffuser, touch sensor."""
    return part_objects("mirror_fx", mesh_only=True)


def collision_objects():
    return part_objects("body_col")


def bracket_objects():
    return part_objects("mag_bracket")


def arm_objects():
    """Arm, knuckles, head and its glass, plus the HandleGrip empty."""
    return part_objects("mag_arm")
