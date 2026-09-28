"""Boucle sofa (Fable 5.1, runner-up of the sofa A/B, kept for other apartments, D-029):
dimensions, paths and parts. Built on blender/lib (D-028).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/sofa_boucle/build.py
  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/bake.py
  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/export.py
  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/render.py -- [--quick]
  blender -b --factory-startup --python blender/props/sofa_boucle/verify.py

Coordinates: Blender Z up, meters, sofa front faces -Y, origin at the bottom
center of the footprint. Every object is built in world coordinates (identity
transforms). The pillow is built centered on the world origin (its glb origin)
and only moved for the thumbnails.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "sofa_boucle"
BLEND = output_path("blender", "props", "sofa_boucle.blend")
GLB_SOFA = output_path("assets", "props", "sofa", "sofa_boucle.glb")
GLB_PILLOW = output_path("assets", "props", "sofa", "sofa_boucle_pillow.glb")
SCRATCH = scratch_dir(NAME)

# --- Fixed contract ---------------------------------------------------------------
W, D = 2.10, 0.90                     # overall footprint
HX, HY = W / 2, D / 2                 # 1.05, 0.45
SEAT_TOP = 0.44                       # seat surface (collision top, sit point)
BACK_TOP = 0.85
ARM_TOP = 0.63

# Frame
LEG_H = 0.10                          # black metal legs, floor to frame
LEG_R = 0.018
ARM_W = 0.15                          # arm slab thickness
ARM_X0 = HX - ARM_W                   # 0.90: inner face of the arms
DECK_TOP = 0.31                       # upholstered base frame top (cushions sink 1 cm into it)
BACK_Y0 = 0.30                        # back frame front face
BACK_R = 0.03

# Cushions (3 seats, 3 backs; centers at x = -0.60, 0, 0.60)
CUSHION_XS = (-0.60, 0.0, 0.60)
CUSHION_W = 0.585                     # 1.5 cm gaps between cushions and to the arms
SEAT_Y0, SEAT_Y1 = -0.448, 0.10       # 0.55 deep; puff + wrinkles reach y -0.46
SEAT_Z0, SEAT_Z1 = 0.30, 0.45         # 15 cm thick; welt at ~0.445, sag center ~0.43
SEAT_R = 0.045
SEAT_SAG = 0.030                      # right seat; the others 70-80 % of it
BACK_CUSHION_Y0, BACK_CUSHION_Y1 = 0.10, 0.31
BACK_CUSHION_Z0, BACK_CUSHION_Z1 = 0.42, 0.83
BACK_CUSHION_R = 0.05
BACK_TAPER = 0.40                     # top is 40 % thinner than the bottom

# Throw pillow (origin at its center)
PILLOW_W, PILLOW_T = 0.45, 0.06   # edge thickness; the puffed middle reaches ~0.15
PILLOW_R = 0.028
PILLOW_MASS = 0.6                     # kg; polyester-filled 45 cm cushion

SOFA_MAT = "Sofa"
PILLOW_MAT = "SofaPillow"
TEX_SIZE = 2048
PILLOW_TEX_SIZE = 1024


# --- Parts (tagged in build.py) ---------------------------------------------------
def sofa_objects():
    """Render meshes of the sofa glb (no collision)."""
    return part_objects("sofa", mesh_only=True)


def sofa_collision_objects():
    return part_objects("sofa_col")


def pillow_objects():
    return part_objects("pillow", mesh_only=True)
