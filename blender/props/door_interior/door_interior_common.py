"""Interior door (bedroom, living room, bathroom): frame + hinged leaf + lever + bathroom thumb-turn.
Built on blender/lib (D-028); quick reference: blender/lib/README.md. Generic helpers that
are not in the library yet live in lib_candidates.py (promote them, don't copy them).

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/door_interior/build.py
  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/bake.py
  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/export.py
  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/door_interior/verify.py

Coordinates: Blender Z up, meters. The frame origin is the bottom center of the
rough opening on the wall's center plane; the wall faces are at y = +-0.10. The
front (-Y, Godot +Z) is the side the leaf swings toward. The hinge is on the -X
side. Frame objects are built in world coordinates (identity transforms). Leaf
objects are built in leaf-local coordinates under the `Leaf` root, which sits on
the hinge axis at floor level (z = 0; the leaf itself starts at the 9 mm undercut).
The lever is a top-level object whose origin is on the spindle axis at the leaf's
front face; the back lever is the same mesh turned 180 degrees about X (an
`instance`, not exported). The thumb-turn set hangs under the `Thumbturn` empty
(spindle axis at the leaf's front face).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "door_interior"
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB_FRAME = output_path("assets", "props", NAME, f"{NAME}_frame.glb")
GLB_LEAF = output_path("assets", "props", NAME, f"{NAME}_leaf.glb")
GLB_LEVER = output_path("assets", "props", NAME, f"{NAME}_lever.glb")
GLB_THUMBTURN = output_path("assets", "props", NAME, f"{NAME}_thumbturn.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails (render.py --out overrides)

# --- Fixed contract: the rough opening (apartment generator) -----------------------
OPEN_W, OPEN_H = 0.90, 2.10
OPEN_X = OPEN_W / 2            # 0.45
WALL_Y = 0.10                  # wall faces at +-0.10 (0.20 m wall)

# --- Frame -------------------------------------------------------------------
LINING_T = 0.022
JAMB_X = OPEN_X - LINING_T     # 0.428: inner face of the jamb linings (clear opening 0.856)
HEAD_Z = OPEN_H - LINING_T     # 2.078: underside of the head lining
REVEAL = 0.006                 # casing set back from the lining's inner face
CASING_W, CASING_T = 0.080, 0.013
CASING_X0 = JAMB_X + REVEAL    # 0.434 casing inner edge
CASING_X1 = CASING_X0 + CASING_W   # 0.514: 64 mm over the wall
CASING_Z0 = HEAD_Z + REVEAL    # 2.084
CASING_Z1 = CASING_Z0 + CASING_W   # 2.164: 64 mm over the wall
STOP_T = 0.012                 # stop projects 12 mm from the lining
STOP_Y0, STOP_Y1 = -0.059, -0.024  # 1 mm behind the closed leaf's back face
STOP_X = JAMB_X - STOP_T       # 0.416
STOP_Z = HEAD_Z - STOP_T       # 2.066

# --- Leaf (frame coordinates) ---------------------------------------------------
GAP = 0.003                    # to the jambs and the head
UNDERCUT = 0.009               # above the floor
LEAF_T = 0.040
LEAF_Y0, LEAF_Y1 = -WALL_Y, -WALL_Y + LEAF_T   # front face flush with the lining edge: -0.100 .. -0.060
LEAF_X0, LEAF_X1 = -JAMB_X + GAP, JAMB_X - GAP  # -0.425 .. 0.425 (0.850 wide)
LEAF_Z0, LEAF_Z1 = UNDERCUT, HEAD_Z - GAP       # 0.009 .. 2.075 (2.066 tall)

# Hinge axis: in the gap line, 7.5 mm in front of the leaf, so the knuckles clear the
# lining edge and the casing (6 mm reveal) and the leaf opens to 100 degrees.
KNUCKLE_R = 0.0065
HINGE = Vector((-JAMB_X + GAP / 2, LEAF_Y0 - 0.0075, 0.0))   # (-0.4265, -0.1075, 0)
HINGE_ZS = (0.27, 1.05, 1.83)  # hinge centers
HINGE_H = 0.089                # 3.5" butt hinge, three knuckles (frame, leaf, frame)
KNUCKLE_GAP = 0.001
PLATE_T = 0.0008               # hinge plates in the 3 mm gap, 1.4 mm apart
PLATE_W = 0.0255               # plate depth along the jamb face from the knuckle tab
OPEN_DEG = 100.0               # checked in verify.py

# Hardware (frame coordinates). Lever rose and spindle; the leaf moves, these are closed-position.
SPINDLE_X = LEAF_X1 - 0.060    # 60 mm backset: 0.365
SPINDLE_Z = 1.10               # seated reach (CLAUDE.md)
TURN_Z = SPINDLE_Z - 0.078     # WC turn 78 mm below the spindle: 1.022
ROSE_R, ROSE_H = 0.026, 0.0095
LEVER_R = 0.0095               # 19 mm round bar
LEVER_OUT = 0.060              # lever bar axis from the leaf face
LEVER_LEN = 0.128              # spindle to the start of the end dome
GRIP_DX = -0.070               # grip point from the spindle, along the bar (toward the hinge)
FACEPLATE_Z = (0.975, 1.205)   # lock faceplate on the leaf edge
FACEPLATE_Y = (-0.0925, -0.0675)
STRIKE_Z = (0.985, 1.165)      # strike plate on the latch jamb
STRIKE_Y = (-0.0975, -0.0705)
LATCH_HOLE = ((-0.0890, -0.0770), (SPINDLE_Z - 0.011, SPINDLE_Z + 0.011))  # (y, z) ranges
BOLT_HOLE = ((-0.0870, -0.0790), (TURN_Z - 0.010, TURN_Z + 0.010))

# Colors (linear)
LEAF_PAINT = (0.366, 0.337, 0.288)     # soft warm grey, sRGB ~#A39D92
FRAME_PAINT = (0.275, 0.254, 0.216)    # same family, a step darker, sRGB ~#8F8A80
PRIMER = (0.62, 0.60, 0.56)            # paint worn through to the light undercoat
GRIME = (0.10, 0.09, 0.08)
STEEL = (0.50, 0.50, 0.51)
WALL_PLASTER = (0.686, 0.644, 0.552)   # style guide warm off-white #D8D2C4 (renders only)

FRAME_MAT = "DoorInteriorFrame"
LEAF_MAT = "DoorInteriorLeaf"
LEVER_MAT = "DoorInteriorLever"
THUMBTURN_MAT = "DoorInteriorThumbturn"
TEX_FRAME = 2048
TEX_LEAF = 2048
TEX_LEVER = 512
TEX_THUMBTURN = 512


def to_leaf(p):
    """Frame (world, closed) coordinates -> leaf-local coordinates."""
    return Vector(p) - HINGE


# --- Parts (tagged in build.py) -------------------------------------------------
def frame_objects():
    """Render meshes of the frame glb (no collision)."""
    return part_objects("body", mesh_only=True)


def frame_collision_objects():
    return part_objects("body_col")


def leaf_objects():
    """Leaf root, its meshes and its empties (grips, lever sockets)."""
    return part_objects("door")


def lever_objects():
    return part_objects("lever")


def thumbturn_objects():
    """The `Thumbturn` empty and its meshes."""
    return part_objects("thumbturn")


def mount_hardware():
    """Parent the lever, a back-lever instance and the thumb-turn set to the leaf,
    keeping their transforms, so a hinge rotation carries them (verify, render;
    never saved). Returns the hardware objects that now move with the leaf."""
    import math

    import bpy

    from arcology_blender.geo import instance

    leaf = bpy.data.objects["Leaf"]
    lever = bpy.data.objects["Lever"]
    back = instance(lever, "LeverBack", (SPINDLE_X, LEAF_Y1, SPINDLE_Z), (math.pi, 0.0, 0.0), part="instance")
    tt = bpy.data.objects["Thumbturn"]
    bpy.context.view_layer.update()
    for ob in (lever, back, tt):
        mw = ob.matrix_world.copy()
        ob.parent = leaf
        ob.matrix_parent_inverse = leaf.matrix_world.inverted()
        ob.matrix_world = mw
    bpy.context.view_layer.update()
    return [lever, back] + [o for o in thumbturn_objects() if o.type == "MESH"]
