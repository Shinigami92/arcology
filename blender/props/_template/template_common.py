"""Template prop (a small walnut side table on steel legs): dimensions, paths and parts.
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

New asset: copy this folder to blender/props/<name>/, rename this file to
<name>_common.py, replace `template_common` in the five stage scripts, set
NAME, then change the contract, materials and geometry. Delete what you
don't need; keep the stage split and the part tags.

Run the stages with Blender 5.2 in background mode, from the repo root:

  blender -b --factory-startup --python blender/props/<name>/build.py
  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/bake.py
  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/export.py
  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/props/<name>/verify.py

ARCOLOGY_OUT_DIR=<folder> sends every .blend and .glb there instead of the
repo (try-outs, rebuild checks); with it the paths below stay the same.

Coordinates: Blender Z up, meters, the front faces -Y, origin at the bottom
center of the footprint. Objects are built in world coordinates (identity
transforms); a moving part is built around its own root object (see export.py).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "template"
if NAME == "template" and not os.environ.get("ARCOLOGY_OUT_DIR"):
    raise SystemExit("The template would write into the repo: copy it first, or set ARCOLOGY_OUT_DIR.")
BLEND = output_path("blender", "props", f"{NAME}.blend")
GLB = output_path("assets", "props", NAME, f"{NAME}.glb")
SCRATCH = scratch_dir(NAME)  # thumbnails (render.py --out overrides)

# --- Fixed contract (the Godot scene depends on these) ---------------------------
W, D, H = 0.45, 0.35, 0.45     # footprint and height
LIMIT_LO, LIMIT_HI = Vector((-W / 2, -D / 2, 0.0)), Vector((W / 2, D / 2, H))

# Parts
TOP_T = 0.022                  # veneered top board
LEG_TOP, LEG_BOTTOM = 0.030, 0.020
LEG_INSET = 0.035              # leg center from the top's edges

# Colors (linear)
WALNUT_MID = (0.036, 0.019, 0.011)
WALNUT_DARK = (0.012, 0.0062, 0.0040)
WALNUT_LIGHT = (0.072, 0.040, 0.022)
WALNUT_WORN = (0.105, 0.066, 0.040)
GUNMETAL = (0.085, 0.090, 0.100)
STEEL_BARE = (0.36, 0.37, 0.39)

BODY_MAT = "TemplateBody"      # one baked material per exported part
TEX_SIZE = 1024                # small prop: <= 1024 (CLAUDE.md budgets)


# --- Parts (tagged in build.py) -------------------------------------------------
def body_objects():
    """Render meshes of the glb (no collision)."""
    return part_objects("body", mesh_only=True)


def collision_objects():
    return part_objects("body_col")
