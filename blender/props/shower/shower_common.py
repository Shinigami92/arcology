"""Walk-in shower for the hotel-style bathroom (bathroom set contract): dimensions, paths, parts.
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/shower/build.py
  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/bake.py
  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/export.py
  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/shower/verify.py

ARCOLOGY_OUT_DIR=<folder> sends every .blend and .glb there instead of the repo.

Local frame (unlike the wall-mounted bathroom assets, the origin is the
footprint center of the recess): X -1.40..1.40 (+X = north in the room,
toward the door), Y -0.70..0.70, floor Z 0, ceiling Z 2.60. The room shell
provides the walls at Y +0.70 (back), X +1.40 and X -1.40; the front
(Y -0.70) is open except for the fixed glass wall X -0.40..+1.40. Godot
places the asset at (-0.9, 0, 5.2) with yaw 90.

Exported parts:
  shower_body.glb        static fixtures + the glass pane (own object, `shower_glass`) + collision boxes
  shower_mixer_flow.glb  flow/diverter lever, origin on its pivot (rotates about the wall normal)
  shower_mixer_temp.glb  thermostat dial, origin on its pivot (rotates about the wall normal)
  shower_handheld.glb    hand shower, origin at its holder seat (handle axis = local +Z), HandleGrip
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Matrix, Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "shower"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB_BODY = output_path("assets", "props", NAME, "shower_body.glb")
GLB_FLOW = output_path("assets", "props", NAME, "shower_mixer_flow.glb")
GLB_TEMP = output_path("assets", "props", NAME, "shower_mixer_temp.glb")
GLB_HANDHELD = output_path("assets", "props", NAME, "shower_handheld.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails (render.py --out overrides)

# --- Room (shell, not ours) -------------------------------------------------------
HX, HY, CEIL = 1.40, 0.70, 2.60
BACK_Y = HY                      # back wall plane
LIMIT_LO, LIMIT_HI = Vector((-HX, -HY - 0.02, 0.0)), Vector((HX, HY, CEIL))

# --- Glass wall (front line) -------------------------------------------------------
GLASS_Y = -0.70                  # pane mid-plane
GLASS_T = 0.010
GLASS_X0 = -0.40                 # free edge (entry X -1.40..-0.40)
GLASS_X1 = 1.386                 # end inside the wall channel (wall at X 1.40)
GLASS_H = 2.00
GLASS_CORNER_R = 0.008           # dubbed free top corner
EDGE_DEPTH = 0.0025              # opaque polished-edge strip depth into the pane

CH_X0 = 1.372                    # wall U-channel: X CH_X0..HX, Y GLASS_Y +- CH_HALF
CH_HALF = 0.0135
CH_SLOT = 0.0058                 # slot half-width (glass half thickness + 0.8 mm)
CH_BASE = 0.003

# Stabiliser bar: glass fitting near the free top corner to the back wall
BAR_X, BAR_Z, BAR_R = -0.335, 1.955, 0.0095
BAR_FIT_R = 0.019

# --- Rain head (flush ceiling plate) ----------------------------------------------------
RAIN_C = Vector((0.50, 0.0))
RAIN_SIZE = 0.40
RAIN_T = 0.008
RAIN_PITCH = 0.021
RAIN_NOZZLES = 16

# --- Thermostatic mixer (back wall) -----------------------------------------------------
MIX_X, MIX_Z = -0.60, 1.10
PLATE_W, PLATE_H, PLATE_T = 0.12, 0.28, 0.010
PLATE_FRONT_Y = BACK_Y - PLATE_T   # 0.690
FLOW_PIVOT = Vector((MIX_X, PLATE_FRONT_Y, 1.175))
TEMP_PIVOT = Vector((MIX_X, PLATE_FRONT_Y, 1.025))
FLOW_TRAVEL = 90.0               # +-: + (counter-clockwise from the room) = rain head, - = hand shower
TEMP_TRAVEL = 120.0              # +-: 0 = 38 C (indicator up), + (counter-clockwise) = hotter
LEVER_LEN = 0.078                # flow lever tip circle center below the pivot
FLOW_GRIP = Vector((0.0, -0.027, -0.052))   # lever-local
TEMP_GRIP = Vector((0.0, -0.022, 0.0))      # dial-local (front of the dial, on the axis)

# --- Hand shower on a slide rail ---------------------------------------------------------
RAIL_X, RAIL_Y = -0.05, BACK_Y - 0.045
RAIL_Z0, RAIL_Z1, RAIL_R = 0.90, 1.90, 0.011
RAIL_BRACKETS = (0.935, 1.865)
SEAT = Vector((RAIL_X, RAIL_Y - 0.07, 1.55))   # holder seat on the handle axis
TILT_DEG = 12.0                                 # top leans out of the wall
HAND_ROT = Matrix.Rotation(math.radians(TILT_DEG), 4, "X")
HAND_GRIP = Vector((0.0, 0.0, -0.055))          # handheld-local, on the handle axis
HAND_BOTTOM = -0.105                            # hose end (handheld-local z)
OUTLET = Vector((-0.30, BACK_Y, 0.88))          # wall outlet (elbow) center on the wall
HOSE_R = 0.0072

# --- Marble ledge and linear drain ------------------------------------------------------
SHELF_X0, SHELF_X1 = 0.30, HX
SHELF_Y0 = BACK_Y - 0.14
SHELF_TOP, SHELF_T = 1.20, 0.03
DRAIN_Y0, DRAIN_Y1 = BACK_Y - 0.11, BACK_Y   # frame against the wall
DRAIN_H = 0.003                               # grate top 3 mm proud of the floor
DRAIN_SECTIONS = 4

# --- Colors (linear) ----------------------------------------------------------------------
def srgb(h):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


GUNMETAL = srgb("#3B3E44")
MARBLE = srgb("#E6E2DA")
VEIN = srgb("#8C8A86")
LIMESCALE = (0.55, 0.54, 0.50)
SILICONE = (0.018, 0.018, 0.020)

BODY_MAT = "ShowerBody"
PARTS_MAT = "ShowerParts"        # one atlas shared by the lever, dial and hand shower
GLASS_MAT = "shower_glass"       # Godot replaces it with its transparent glass shader
TEX_BODY = 2048
TEX_PARTS = 1024


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Render meshes of the body glb (no glass, no collision)."""
    return part_objects("body", mesh_only=True)


def glass_objects():
    return part_objects("glass", mesh_only=True)


def collision_objects():
    return part_objects("body_col")


def flow_objects():
    return part_objects("flow")


def temp_objects():
    return part_objects("temp")


def handheld_objects():
    return part_objects("handheld")


def part_meshes():
    return [o for o in flow_objects() + temp_objects() + handheld_objects() if o.type == "MESH"]
