"""Floor 44 corridor kit (D-060): the wainscot swept along the corridor's runs and four small
ceiling/wall fixtures, one glb each. Built on blender/lib (D-028); quick reference:
blender/lib/README.md.

Contract: tools/blockout/corridor_kit.json (names, origins, facing, sizes, material slots,
budgets; read here, never copied). Runs: tools/blockout/corridor_trim.json, written by
tools/blockout/corridor.py (format: tools/blockout/skirting.py, like the apartment skirting, D-036).

Assets (`--asset`, default: all, in this order):

  corridor_trim  wainscot: skirting band, laminate panel field with V-joints, LED reveal, rail cap
  corridor_light recessed-look linear LED fixture, ceiling
  corridor_vent  linear slot diffuser, ceiling
  exit_sign      back-lit emergency exit sign, wall
  holo_emitter   hologram projector puck, ceiling

Stages (Blender 5.2, background, from the repo root; one .blend per asset):

  blender -b --factory-startup --python blender/architecture/corridor/build.py [-- --asset a,b]
  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/bake.py
  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/export.py
  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/architecture/corridor/verify.py [-- --asset a,b]

Outputs: assets/architecture/corridor/<asset>.glb. ARCOLOGY_OUT_DIR=<dir> redirects the .blend
and glb files (rebuild checks).

Coordinates: Blender (x, y, z) = Godot (x, -z, y). The trim is authored at world positions (glb
origin = world origin). The fixtures are authored around their contract origin: Godot -Y (hanging
from the ceiling) is Blender -Z, Godot +Z (the exit sign's face) is Blender -Y.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from mathutils import Vector  # noqa: E402

from arcology_blender.scene import output_path, part_objects, repo_path, scratch_dir, script_args  # noqa: E402

KIT_JSON = ("tools", "blockout", "corridor_kit.json")
RUNS_JSON = ("tools", "blockout", "corridor_trim.json")
SCRATCH = scratch_dir("corridor")

ASSETS = ("corridor_trim", "corridor_light", "corridor_vent", "exit_sign", "holo_emitter")
CONTRACT_KEY = {"corridor_trim": "trim", "corridor_light": "ceiling_light", "corridor_vent": "vent",
                "exit_sign": "exit_sign", "holo_emitter": "holo_emitter"}


def kit():
    with open(repo_path(*KIT_JSON), encoding="utf-8") as f:
        return json.load(f)


def contract(asset):
    return kit()[CONTRACT_KEY[asset]]


def load_runs():
    with open(repo_path(*RUNS_JSON), encoding="utf-8") as f:
        return json.load(f)


def blend_path(asset):
    return output_path("blender", "architecture", "corridor", f"{asset}.blend")


def glb_path(asset):
    return output_path("assets", "architecture", "corridor", f"{asset}.glb")


def selected_assets(args=None):
    args = script_args() if args is None else args
    if "--asset" in args:
        names = args[args.index("--asset") + 1].split(",")
        bad = [n for n in names if n not in ASSETS]
        if bad:
            raise SystemExit(f"unknown asset {bad}; known: {ASSETS}")
        return names
    return list(ASSETS)


def asset_of_blend(filepath):
    """The asset a .blend holds (bake/export/render run on an opened .blend)."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    if name not in ASSETS:
        raise SystemExit(f"{filepath} is not a corridor kit .blend ({ASSETS})")
    return name


def to_blender(p):
    """Godot (x, z) on the floor -> Blender (x, y, 0)."""
    return Vector((p[0], -p[1], 0.0))


def godot_size_to_blender(size):
    """Godot (x, y, z) extents -> Blender (x, y, z) extents."""
    return Vector((size[0], size[2], size[1]))


def body_objects():
    return part_objects("body", mesh_only=True)


# --- Shared look ----------------------------------------------------------------------------
# Linear colors. Charcoal and teal carpet tiles below, warm off-white plaster above.
ANTHRACITE = (0.034, 0.035, 0.037)       # matte laminate, sRGB ~#353638
POWDER_BLACK = (0.020, 0.021, 0.022)     # powder-coated aluminium skirting, sRGB ~#272829
BRONZE = (0.205, 0.135, 0.082)           # brushed dark bronze (metal), sRGB ~#7C6650
BRONZE_POLISH = (0.27, 0.19, 0.12)       # hand-polished bronze
WHITE_POWDER = (0.70, 0.69, 0.66)        # white powder coat (ceiling fixtures), sRGB ~#DAD8D3
DUST = (0.36, 0.35, 0.33)
GRIME = (0.03, 0.028, 0.025)

LED_CYAN = (0.0015, 0.693, 0.807)        # #05D9E8 (style guide neon cyan)
LED_STRENGTH = 4.0                       # like the fridge's and the entrance door's LEDs
WARM_NEUTRAL = (1.0, 0.86, 0.70)         # ~3500 K: the corridor's ceiling light
EXIT_GREEN_HEX = "2BE07A"
