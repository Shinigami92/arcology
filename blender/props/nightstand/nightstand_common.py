"""Nightstand + table lamp (bedroom set), Opus 5.5, won the bedroom A/B (D-032). Built on blender/lib (D-028).

A slim walnut-veneer case on four tapered gunmetal legs: one drawer under
the top (bar pull, side runners), an open shelf below. A drum-shade table
lamp stands on the top, back right, its braided cord running off the back.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/nightstand/build.py
  blender -b --factory-startup blender/props/nightstand.blend --python blender/props/nightstand/bake.py
  blender -b --factory-startup blender/props/nightstand.blend --python blender/props/nightstand/export.py
  blender -b --factory-startup blender/props/nightstand.blend --python blender/props/nightstand/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/nightstand/verify.py

Coordinates: Blender Z up, meters, front faces -Y, origin at the bottom
center of the footprint. Body objects are built in world coordinates. The
drawer is built in drawer-local coordinates (origin at the drawer front's
bottom center, box toward +Y) and parented to `Drawer`, which sits at
DRAWER_ORIGIN; it slides along -Y. The lamp is built in lamp-local
coordinates (origin at the base's bottom center) under `TableLamp`, which
stands on the top at LAMP_POS.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

TAG = ""  # no variant tag: this is the apartment nightstand (D-032)
NAME = "nightstand"
BLEND = output_path("blender", "props", "nightstand.blend")
GLB_BODY = output_path("assets", "props", "nightstand", f"nightstand_body.glb")
GLB_DRAWER = output_path("assets", "props", "nightstand", f"nightstand_drawer.glb")
GLB_LAMP = output_path("assets", "props", "nightstand", f"table_lamp.glb")
SCRATCH = scratch_dir(NAME)

# --- Fixed contract ---------------------------------------------------------------
W, D, H = 0.45, 0.40, 0.55
HX, HY = W / 2, D / 2          # 0.225, 0.20
FRONT_Y = -HY

# Case (walnut veneer boards)
T_TOP = 0.022                  # top board
T = 0.018                      # sides, bottom, divider
T_BACK = 0.012
CASE_Z0 = 0.12                 # underside of the case (legs below)
TOP_Z0 = H - T_TOP             # 0.528
IN_X = HX - T                  # 0.207, inner face of the sides
BACK_Y0 = HY - T_BACK          # 0.188, front face of the back panel
BOTTOM_Z1 = CASE_Z0 + T        # 0.138, open shelf floor
DIV_Z0, DIV_Z1 = 0.360, 0.378  # divider between the drawer and the open shelf

# Legs (tapered square gunmetal tube, a mounting plate under the case, a glide)
LEG_INSET = 0.028              # leg center from the case edges
LEG_TOP, LEG_BOTTOM = 0.022, 0.016
PLATE = 0.046
GLIDE_H = 0.004

# Drawer (inset, flush with the case front; 2 mm reveals)
REVEAL = 0.002
DRAWER_ORIGIN = Vector((0.0, FRONT_Y, DIV_Z1 + REVEAL))  # (0, -0.20, 0.380): front's bottom center
FRONT_W = 2 * (IN_X - REVEAL)                          # 0.410
FRONT_H = TOP_Z0 - REVEAL - DRAWER_ORIGIN.z            # 0.146
FRONT_T = 0.018
BOX_X = 0.194                  # outer half width of the drawer box (runners take 13 mm per side)
BOX_SIDE = 0.010
BOX_BACK_Y = 0.370             # local y of the box's back face (world 0.170, 18 mm before the back panel)
BOX_Z0 = 0.004                 # local z of the box underside (6 mm above the divider)
BOX_BOTTOM_T = 0.008
BOX_Z1 = 0.124                 # local z of the box sides' top edge
DRAWER_TRAVEL = 0.28
# Inner box (local): x +-(BOX_X - BOX_SIDE), y FRONT_T..BOX_BACK_Y - BOX_SIDE, z BOX_Z0 + BOX_BOTTOM_T..BOX_Z1

# Runners (fixed member on the case sides, moving member on the drawer box)
RUN_Z0, RUN_Z1 = 0.048, 0.080  # local z of the drawer member (world 0.428..0.460)
RUN_BODY_X0 = 0.2005           # body member x 0.2005..0.207 (1 mm from the drawer member)
RUN_DRAWER_X1 = 0.1995

# Pull: round bar on two standoffs, 96 mm centers
PULL_Z = FRONT_H / 2           # local z of the bar axis
PULL_Y = -0.031                # local y of the bar axis (27 mm finger gap)
PULL_R = 0.0055
PULL_LEN = 0.134
PULL_CENTERS = 0.096
HANDLE_GRIP = Vector((0.0, PULL_Y, PULL_Z))  # drawer-local

# Lamp (lamp-local coordinates, origin at the base's bottom center)
LAMP_POS = Vector((0.085, 0.045, H))
BASE_R, BASE_H = 0.070, 0.018
STEM_R = 0.0055
SOCKET_Z0, SOCKET_Z1, SOCKET_R = 0.232, 0.272, 0.0175
WASHER_Z, WASHER_R = 0.262, 0.030
SHADE_Z0, SHADE_Z1 = 0.225, 0.400
SHADE_R0, SHADE_R1 = 0.125, 0.113  # bottom, top radius (slight taper)
BULB_CENTER_Z, BULB_R = 0.316, 0.0225  # G45 globe
CORD_R = 0.0028

# --- Materials --------------------------------------------------------------------
BODY_MAT = "Nightstand"
DRAWER_MAT = "NightstandDrawer"
LAMP_MAT = "TableLamp"
LIGHT_MAT = "LampLight"        # Godot switches its emission energy by name
LIGHT_STRENGTH = 4.0           # emission strength exported in the glb (lamp on)
TEX_BODY = 1024
TEX_DRAWER = 1024
TEX_LAMP = 512
TEX_SHADE = 1024

# Build-time mesh attributes (removed before export)
BUILD_ATTRS = ("grain_u", "grain_b", "grain_seed", "along", "around_c", "around_s", "glow")


# --- Parts (tagged in build.py) ---------------------------------------------------
def body_objects():
    return part_objects("body", mesh_only=True)


def body_collision_objects():
    return part_objects("body_col")


def drawer_objects():
    return part_objects("drawer")


def lamp_objects():
    return part_objects("lamp")


def lamp_light_objects():
    return part_objects("lamp_light")
