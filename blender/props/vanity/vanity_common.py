"""Bathroom vanity with sink (luxury bathroom set): dimensions, paths and parts.
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

A wall-hung dark-walnut cabinet (1.40 x 0.52 m) with a honed marble top and
upstand, a centered undermount porcelain basin with a pop-up drain, a
deck-mounted single-lever mixer in gunmetal, two full-width soft-close
drawers (a shallow U-shaped top drawer around the drain, a deep bottom one)
with slim gunmetal edge pulls over handleless channels, and a warm LED strip
under the cabinet. A pickable matte-ceramic soap dispenser stands on the top.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/vanity/build.py
  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/bake.py
  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/export.py
  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/vanity/verify.py

Coordinates: Blender Z up, meters, the front faces -Y, the wall plane is
Y = 0 (the vanity sits at Y <= 0). Origin on the floor (Z 0) below the
back-center of the cabinet. Body objects are built in world coordinates.
Moving parts (drawers, lever) and the dispenser are built in world
coordinates, then re-origined onto their pivot (`lib_candidates.reorigin`):
drawers on their front's bottom center at the closed position (slide -Y),
the lever on its pivot, the dispenser at its bottom center.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "vanity"
BLEND = output_path("blender", "props", f"{NAME}.blend")
ASSET = ("assets", "props", NAME)
GLB_BODY = output_path(*ASSET, f"{NAME}_body.glb")
GLB_DRAWER_TOP = output_path(*ASSET, f"{NAME}_drawer_top.glb")
GLB_DRAWER_BOTTOM = output_path(*ASSET, f"{NAME}_drawer_bottom.glb")
GLB_LEVER = output_path(*ASSET, f"{NAME}_lever.glb")
GLB_DISPENSER = output_path(*ASSET, f"{NAME}_soap_dispenser.glb")
SCRATCH = scratch_dir(NAME)

# --- Fixed contract (the Godot scene depends on these) ---------------------------
W, D = 1.40, 0.52
HX = W / 2
MAX_Z = 1.13                       # the mirror's bottom edge is at 1.18
LIMIT_LO, LIMIT_HI = Vector((-HX, -D, 0.0)), Vector((HX, 0.0, MAX_Z))

# Carcass (walnut veneer boards)
CASE_Z0, CASE_Z1 = 0.32, 0.82      # floating: bottom panel at 0.32, top edge under the marble
T = 0.018                          # sides, bottom
X_OUT = 0.695                      # side panels' outer faces
X_IN = X_OUT - T                   # 0.677
CASE_FRONT = -0.4845               # front edges of sides and bottom (1.5 mm behind the fronts)
T_BACK = 0.016
BACK_Y0 = -T_BACK                  # front face of the back panel
BOTTOM_Z1 = CASE_Z0 + T            # 0.338

# Marble top and upstand
TOP_Z0, TOP_Z1 = 0.82, 0.86        # 40 mm slab; TOP_Z1 is the surface things stand on
TOP_FRONT = -D                     # 15 mm overhang over the fronts
TOP_EASE = 0.004                   # rounded (eased) edge of the basin cutout
SPLASH_T, SPLASH_Z1 = 0.020, 0.96  # upstand along the wall

# Basin (undermount porcelain), centered in x
BASIN_C = Vector((0.0, -0.28))
CUT_W, CUT_H, CUT_R = 0.490, 0.310, 0.075   # marble cutout (rounded rectangle)
CORNER_SEGS = 8                    # per corner (even: the 45 degree point maps to the slab corner)
# Inner bowl surface, top to drain: (z, width, depth, corner radius). The bowl
# sits 5 mm back under the marble edge (positive reveal) and dishes to the drain.
BOWL_RINGS = (
    (0.820, 0.500, 0.320, 0.080),
    (0.800, 0.496, 0.316, 0.080),
    (0.772, 0.474, 0.294, 0.082),
    (0.748, 0.428, 0.250, 0.085),
    (0.731, 0.350, 0.200, 0.085),
    (0.721, 0.230, 0.150, 0.068),
    (0.715, 0.120, 0.100, 0.050),
    (0.712, 0.066, 0.066, 0.033),
)
BOWL_T = 0.012                     # porcelain wall
BOWL_FLANGE = 0.012                # mounting flange under the marble
FLANGE_Z0 = 0.808
DRAIN_Z = 0.712                    # basin floor at the drain
DRAIN_R = 0.033                    # drain hole
BASIN_DEPTH = TOP_Z1 - DRAIN_Z     # 0.148 below the top surface

# Plumbing under the basin (gunmetal; visible with the top drawer open)
TRAP_Z = 0.655                     # horizontal waste run to the wall
TRAP_Y0, TRAP_Y1, TRAP_R = -0.22, -0.15, 0.028

# Mixer (deck-mounted, single lever), static body part
MIXER = Vector((0.0, -0.072, TOP_Z1))
MIXER_R = 0.021
MIXER_TOP = 1.010                  # body top
CAP_TOP = 1.016                    # cartridge cap the lever sits on
SPOUT_Z = 0.985                    # spout axis
SPOUT_END = -0.245                 # spout tip (y)
AERATOR = Vector((0.0, -0.233, SPOUT_Z - 0.009))
LEVER_PIVOT = Vector((0.0, MIXER.y, 1.0225))   # lever glb origin
LEVER_LEN = 0.110
LEVER_TILT = 6.0                   # degrees the blade rises toward its tip at rest (closed)
LEVER_LIFT = 30.0                  # flow: tip up, rotation about local X (negative angle)
LEVER_SWING = 40.0                 # temperature: +-, about local up; tip to the user's left = hot
LEVER_GRIP_LOCAL = Vector((0.0, -0.080, 0.008))  # on the blade's center line, near the tip (lever-local)

# Drawer fronts (full overlay over the carcass, slim gunmetal edge pull on top)
FRONT_Y = -0.505                   # front face
FRONT_T = 0.019
FRONT_X = 0.693                    # half width
PULL_T = 0.003                     # cap on the top edge
PULL_LIP = 0.010                   # visible strip down the front face
PULL_BACK = 0.022                  # rear lip the fingers hook behind
TOP_DRAWER_ORIGIN = Vector((0.0, FRONT_Y, 0.625))
TOP_FH = 0.160                     # front height incl. the pull cap -> top edge 0.785
BOTTOM_DRAWER_ORIGIN = Vector((0.0, FRONT_Y, CASE_Z0))
BOTTOM_FH = 0.270                  # -> top edge 0.590
DRAWER_TRAVEL = 0.40
CHANNEL_Y = -0.471                 # back web of the upper finger channel (in front of the basin)
MID_CHANNEL = (0.590, 0.625)       # z of the finger channel between the drawers

# Drawer boxes (drawer-local: y from the front face toward +Y, z from the front's bottom)
BOX_X = 0.664                      # outer half width (13 mm per side for the runners)
BOX_SIDE = 0.014
BOX_BACK = 0.445                   # local y of the back face (world -0.060)
BOX_FLOOR = 0.012
LINER_T = 0.003                    # felt liner on the drawer floors
TOP_BOX = dict(z0=0.007, z1=0.150, low=0.065,           # sides; walls under the basin
               divider=0.276, notch=0.065, notch_front=0.180)
BOTTOM_BOX = dict(z0=0.025, z1=0.258)
RUN_H = 0.022                      # runner height
TOP_RUN_Z = 0.030                  # local z of the runner bottom
BOTTOM_RUN_Z = 0.080
RUN_BODY_X0 = 0.6705               # body member x 0.6705..0.677
RUN_DRAWER_X1 = 0.6695             # drawer member x 0.664..0.6695

# LED strip under the cabinet (warm night light on the floor)
LED_X = 0.66
LED_Y0, LED_Y1 = -0.475, -0.459
LED_Z0 = 0.311

# Soap dispenser (pickable, dispenser-local: origin at its bottom center)
DISPENSER_POS = Vector((0.42, -0.24, TOP_Z1))
DISPENSER_R = 0.036
DISPENSER_H = 0.196
DISPENSER_MASS = 0.65              # kg: ceramic ~0.38, 250 ml soap, pump

# --- Colors (linear) from the shared set ------------------------------------------
def srgb(hexstr):
    c = [int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


FIXTURE = srgb("3B3E44")
MARBLE = srgb("E6E2DA")
MARBLE_VEIN = srgb("8C8A86")
WALNUT = srgb("4A3326")
PORCELAIN = srgb("F2F1EE")
LED_WARM = srgb("FFC58F")
CERAMIC = srgb("2F2D2C")           # matte charcoal ceramic dispenser

# --- Materials --------------------------------------------------------------------
BODY_MAT = "VanityBody"
FIXTURE_MAT = "VanityFixture"
DRAWER_TOP_MAT = "VanityDrawerTop"
DRAWER_BOTTOM_MAT = "VanityDrawerBottom"
LEVER_MAT = "VanityLever"
DISPENSER_MAT = "VanitySoapDispenser"
LED_MAT = "vanity_led"             # unbaked; Godot switches its emission by name
LED_STRENGTH = 3.0
TEX_BODY = 2048
TEX_FIXTURE = 512
TEX_DRAWER = 1024
TEX_LEVER = 256
TEX_DISPENSER = 512


# --- Parts (tagged in build.py) ---------------------------------------------------
def body_objects():
    """Static render meshes of the body glb (carcass, top, basin, plumbing, LED)."""
    return part_objects("body", mesh_only=True)


def fixture_objects():
    """Mixer body and spout, pop-up drain: static, own atlas, exported with the body."""
    return part_objects("fixture", mesh_only=True)


def collision_objects():
    return part_objects("body_col")


def drawer_top_objects():
    return part_objects("drawer_top")


def drawer_bottom_objects():
    return part_objects("drawer_bottom")


def drawer_collision(which):
    """Reference boxes for the Godot scene (not exported)."""
    return part_objects(f"drawer_{which}_col")


def lever_objects():
    return part_objects("lever")


def dispenser_objects():
    return part_objects("dispenser")
