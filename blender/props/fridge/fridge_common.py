"""Fridge dimensions, paths and parts (Fable 5.1 won the A/B, D-026). Built on blender/lib (D-028).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/fridge/build.py
  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/bake.py
  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/export.py
  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/render.py -- [--quick]
  blender -b --factory-startup --python blender/props/fridge/verify.py

Coordinates: Blender Z up, meters, fridge front faces -Y. Body objects are
built in world coordinates (identity transforms). Door objects are built in
door-local coordinates (hinge axis at the local origin, door extends along
+X, front face toward -Y) and parented to the `Door` object, which sits at
the hinge (-0.30, -0.325, 0).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "fridge"
BLEND = output_path("blender", "props", "fridge.blend")
GLB_BODY = output_path("assets", "props", "fridge", "fridge_body.glb")
GLB_DOOR = output_path("assets", "props", "fridge", "fridge_door.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails, texture dumps

# --- Fixed contract (the Godot scene depends on these) ---------------------------
CAB_W, CAB_D, CAB_H = 0.60, 0.65, 1.85
CAB_X = CAB_W / 2  # 0.30
CAB_Y = CAB_D / 2  # 0.325
HINGE = Vector((-CAB_X, -CAB_Y, 0.0))
OPEN_DEG = 100.0  # swing checked in Blender; Godot limits it to 92 for the kitchen wall

# Cabinet shell
WALL_SIDE = 0.045
WALL_BACK = 0.06
WALL_TOP = 0.08
CAV_X = CAB_X - WALL_SIDE  # 0.255
CAV_Y_BACK = CAB_Y - WALL_BACK  # 0.265
CAV_Z0 = 0.12
CAV_Z1 = CAB_H - WALL_TOP  # 1.77
PLINTH_Z = 0.085
PLINTH_DEPTH = 0.035

# Door (local coordinates, hinge at origin)
DOOR_W = 0.60
DOOR_T = 0.055
DOOR_Z0 = 0.09
DOOR_Z1 = 1.845  # 5 mm below the cabinet top / hinge bracket
DOOR_SKIN_Y0, DOOR_SKIN_Y1 = -DOOR_T, -0.012
DOOR_LINER_Y0, DOOR_LINER_Y1 = -0.012, -0.003
GASKET_Y0, GASKET_Y1 = -0.012, -0.001  # 1 mm clearance to the cabinet front
BIN_Y1 = 0.09  # how far the door bins reach into the cavity
BINS = ((0.42, 0.12), (0.86, 0.12), (1.36, 0.10))  # bottom z, front wall height

# Handle
HANDLE_X = 0.555
HANDLE_Y = -0.100
HANDLE_Z0, HANDLE_Z1 = 0.95, 1.55
HANDLE_R = 0.0125
HANDLE_GRIP = Vector((HANDLE_X, HANDLE_Y, 1.25))

# Shelves (top surface z) and crisper
SHELF_TOPS = [0.72, 1.07, 1.42]
SHELF_Y0 = -0.175
GLASS_T = 0.006
CRISPER_COVER_TOP = 0.35
CRISPER_Y0 = -0.22
CRISPER_W, CRISPER_D, CRISPER_H = 0.49, 0.44, 0.20
CRISPER_TRAVEL = 0.30
# Known: closed, the drawer front panel and grip lip reach 6 mm into the crisper cover's
# front trim (verify.py reports it at 0 m; clear from 3 cm out). Hidden behind the trim;
# lower them (CRISPER_H + 0.012) when the drawer becomes a slider.

BODY_MAT = "FridgeBody"
DOOR_MAT = "FridgeDoor"
GLASS_MAT = "FridgeGlass"
DISPLAY_MAT = "FridgeDisplay"
LIGHT_MAT = "FridgeLight"  # Godot's HingeLight switches this one by name

TEX_SIZE = 2048


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Render meshes of the body glb (no collision)."""
    return part_objects("body", mesh_only=True)


def body_collision_objects():
    return part_objects("body_col")


def door_objects():
    return part_objects("door")
