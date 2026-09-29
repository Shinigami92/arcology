"""Nightstand + table lamp: dimensions, paths and parts (A/B variant `fable-high`, Fable 5.1).

Built on blender/lib (D-028). Run the stages with Blender 5.2 in background mode:

  blender -b --factory-startup --python blender/props/nightstand__fable-high/build.py
  blender -b --factory-startup <blend> --python blender/props/nightstand__fable-high/bake.py
  blender -b --factory-startup <blend> --python blender/props/nightstand__fable-high/export.py
  blender -b --factory-startup <blend> --python blender/props/nightstand__fable-high/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/nightstand__fable-high/verify.py

Coordinates: Blender Z up, meters, front faces -Y. Body objects are built in
world coordinates (identity transforms). The drawer is built in drawer-local
coordinates (origin at the drawer front's bottom center, front face at local
y = 0, box extending along +Y) and parented to the `Drawer` object at
DRAWER_ORIGIN (closed). The lamp is built in lamp-local coordinates (origin at
the base's bottom center) and parented to `TableLamp` at LAMP_ORIGIN, standing
on the nightstand top.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

VARIANT = "__fable-high"
NAME = f"nightstand{VARIANT}"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB_BODY = output_path("assets", "props", "nightstand", f"nightstand_body{VARIANT}.glb")
GLB_DRAWER = output_path("assets", "props", "nightstand", f"nightstand_drawer{VARIANT}.glb")
GLB_LAMP = output_path("assets", "props", "nightstand", f"table_lamp{VARIANT}.glb")
SCRATCH = scratch_dir(NAME)

# --- Fixed contract (the Godot scene depends on these) ---------------------------
W, D, H = 0.45, 0.40, 0.55
HX, HY = W / 2, D / 2  # 0.225, 0.20
DRAWER_TRAVEL = 0.28  # along -Y

# --- Carcass ----------------------------------------------------------------------
PANEL = 0.018  # veneered panel thickness
BACK_T = 0.008
LEG_H = 0.10  # carcass floats on four slim legs
LEG_S = 0.016  # square tube section
LEG_INSET = 0.030  # leg center from the carcass corner
CARC_Z0 = LEG_H  # 0.10
BOTTOM_Z1 = CARC_Z0 + PANEL  # 0.118
TOP_Z0 = H - PANEL  # 0.532 (underside of the top)
INNER_X = HX - PANEL  # 0.207
BACK_Y0 = HY - BACK_T  # 0.192
DIV_Z1 = 0.373  # fixed divider between drawer and open shelf (top surface)
DIV_Z0 = DIV_Z1 - PANEL  # 0.355
# Drawer runners: two slim rails on the divider, the drawer box rests 1 mm above them
RAIL_X, RAIL_W, RAIL_H = 0.16, 0.012, 0.012
RAIL_Y0, RAIL_Y1 = -0.17, 0.185
RAIL_Z1 = DIV_Z1 + RAIL_H  # 0.385

# Open shelf (between bottom panel and divider): inner x +-0.207, y -0.20..0.192, z 0.118..0.355
SHELF_Z0, SHELF_Z1 = BOTTOM_Z1, DIV_Z0

# --- Drawer (local coordinates, origin at the front's bottom center) ----------------
REVEAL = 0.003  # gap around the inset front
DRAWER_ORIGIN = Vector((0.0, -HY, DIV_Z1 + REVEAL))  # world (0, -0.20, 0.376)
FRONT_HW = INNER_X - REVEAL  # 0.204
FRONT_H = TOP_Z0 - DIV_Z1 - 2 * REVEAL  # 0.153
FRONT_T = PANEL
BOX_HW = 0.190
BOX_Y0, BOX_Y1 = FRONT_T, 0.358
BOX_Z0 = RAIL_Z1 + 0.001 - DRAWER_ORIGIN.z  # 0.010 (1 mm above the rails)
BOX_Z1 = BOX_Z0 + 0.120  # 0.130
BOX_WALL, BOX_BOTTOM = 0.012, 0.008
# Inner box (small items fit): x +-0.178, y 0.030..0.346, z 0.018..0.130
INNER_BOX_LO = (-BOX_HW + BOX_WALL, BOX_Y0 + BOX_WALL, BOX_Z0 + BOX_BOTTOM)
INNER_BOX_HI = (BOX_HW - BOX_WALL, BOX_Y1 - BOX_WALL, BOX_Z1)
# Bar pull: horizontal gunmetal bar on two standoffs
PULL_LEN, PULL_R = 0.160, 0.005
PULL_STANDOFF_R = 0.0035
PULL_Y = -0.030  # bar axis in front of the front face
PULL_Z = FRONT_H / 2  # 0.0765
HANDLE_GRIP = Vector((0.0, PULL_Y, PULL_Z))

# --- Table lamp (local coordinates, origin at the base's bottom center) ------------
LAMP_ORIGIN = Vector((0.0, 0.07, H))  # standing on the top, toward the back
BASE_R, BASE_H = 0.075, 0.014
STEM_R = 0.007
STEM_Z1 = 0.240
SOCKET_R, SOCKET_Z0, SOCKET_Z1 = 0.014, 0.235, 0.275
BULB_R, BULB_Z = 0.019, 0.305  # LED candle bulb (center)
SHADE_R0, SHADE_R1 = 0.110, 0.095  # bottom, top radius of the drum shade
SHADE_Z0, SHADE_Z1 = 0.230, 0.400
SHADE_T = 0.0015
LAMP_H = SHADE_Z1  # 0.40
CORD_R = 0.0035
LIGHT_MAT = "LampLight"  # Godot switches this one by name (shade + bulb)
LIGHT_OBJECTS = ("LampShade", "LampBulb")

BODY_MAT = "NightstandBody"
DRAWER_MAT = "NightstandDrawer"
LAMP_MAT = "TableLamp"

TEX_BODY, TEX_DRAWER, TEX_LAMP, TEX_LIGHT = 1024, 1024, 512, 1024


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Render meshes of the body glb (no collision)."""
    return part_objects("body", mesh_only=True)


def body_collision_objects():
    return part_objects("body_col")


def drawer_objects():
    return part_objects("drawer")


def lamp_objects():
    return part_objects("lamp")


def lamp_light_objects():
    return [o for o in lamp_objects() if o.name in LIGHT_OBJECTS]


def lamp_metal_objects():
    return [o for o in lamp_objects() if o.type == "MESH" and o.name not in LIGHT_OBJECTS]
