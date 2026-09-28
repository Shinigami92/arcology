"""Shared dimensions for the fridge (variant opus-high). Blender Z up, meters, front faces -Y.

Door-local coordinates: origin on the hinge axis at floor height, the closed door extends
along +X, its front face points to -Y (py < 0), the inner side (bins) points to +Y.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TAG = "opus-high"
BLEND = os.path.join(ROOT, "blender", "props", f"fridge__{TAG}.blend")
GLB_BODY = os.path.join(ROOT, "assets", "props", "fridge", f"fridge_body__{TAG}.glb")
GLB_DOOR = os.path.join(ROOT, "assets", "props", "fridge", f"fridge_door__{TAG}.glb")

# Cabinet
CAB_X = 0.30          # half width
CAB_Y = 0.325         # half depth
CAB_H = 1.85
FOOT_H = 0.015        # cabinet shell starts above the feet
PLINTH_TOP = 0.045    # recessed vent grille below the door
# Cavity (inner liner)
CAV_X = 0.255
CAV_BACK = 0.28
CAV_Z0 = 0.10
CAV_Z1 = 1.79
CAV_R = 0.018         # liner corner radius

# Door (door-local)
HINGE = (-0.30, -0.325)
DOOR_W = 0.60
DOOR_Z0 = 0.045
DOOR_Z1 = 1.845
SLAB_Y0 = -0.062      # front face
SLAB_Y1 = -0.012      # back face of the slab (gasket and liner behind it)
OPEN_DEG = -100.0

# Shelves: top surface z. Index 0 is the crisper cover.
CRISPER_COVER_TOP = 0.345
SHELF_TOPS = [0.64, 0.93, 1.21, 1.48]
SHELF_X = 0.2475
SHELF_Y0 = -0.207     # front of the trim
SHELF_Y1 = 0.262

# Crisper drawer (world, closed)
DRAWER_X = 0.245
DRAWER_Y0 = -0.205    # front face of the drawer front panel
DRAWER_Y1 = 0.250
DRAWER_Z0 = 0.103
DRAWER_Z1 = 0.316
DRAWER_TRAVEL = 0.30

# Door bins (door-local): (z bottom, height)
BINS = [(0.40, 0.13), (0.80, 0.095), (1.12, 0.095), (1.44, 0.085)]
BIN_X0, BIN_X1 = 0.086, 0.514
BIN_Y0, BIN_Y1 = 0.016, 0.104

# Handle (door-local)
HANDLE_X = 0.56
HANDLE_Y0, HANDLE_Y1 = -0.126, -0.102
HANDLE_Z0, HANDLE_Z1 = 0.95, 1.55
GRIP = (HANDLE_X, -0.114, 1.25)

# Display (door-local)
DISP_X0, DISP_X1 = 0.26, 0.34
DISP_Z0, DISP_Z1 = 1.5035, 1.5435

TEX = {"body_ext": 2048, "body_int": 2048, "door_ext": 2048, "door_int": 1024}
FINAL = {
    "body_ext": "FridgeBody",
    "body_int": "FridgeInterior",
    "door_ext": "FridgeDoor",
    "door_int": "FridgeDoorInterior",
}
