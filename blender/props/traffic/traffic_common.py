"""Flying traffic for the city view (five hover vehicles, The Fifth Element style):
contract, paths, colors, parts. Built on blender/lib (D-028); quick reference
blender/lib/README.md. Generic helpers this asset needed are in lib_candidates.py.

Stages, from the repo root (Blender 5.2, background mode):

  blender -b --factory-startup --python blender/props/traffic/build.py
  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/bake.py
  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/export.py
  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/render.py -- [--quick] [--out DIR] [--only sheet|far]
  blender -b --factory-startup --python blender/props/traffic/verify.py

Contract (the Godot MultiMesh lanes depend on it):
  - one glb per vehicle, assets/props/traffic/<name>/<name>.glb: a single mesh
    object, a single material `traffic_vehicle` shared by all five (one atlas)
  - origin at the vehicle's bounding-box center; nose toward Blender +Y
    (Godot -Z), up Blender +Z (Godot +Y); transforms applied
  - one 2048 atlas set: albedo, normal, ORM, emission (lights, signs, windows,
    thrusters), also written to assets/props/traffic/_kit/traffic_vehicle_*.png
  - <= 2,000 triangles per vehicle (sky_bus <= 3,000); no collision, no lights
  - light bar: red faces on the -X half, blue on +X, each its own UV island;
    in the emission map red pixels have R >> B and blue ones B >> R

Vehicles are authored with z = 0 at the bottom of their thruster pods and
y = 0 mid-length; build.py moves each mesh so its bounds center is the origin
and stores the offset (`author_offset`), which the LocalGraph materials add
back, so their masks stay in authoring coordinates.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, scratch_dir  # noqa: E402

NAME = "traffic"
BLEND = output_path("blender", "props", f"{NAME}.blend")
VEHICLES = ("aircar_sedan", "aircar_taxi", "hover_van", "patrol_cruiser", "sky_bus")
KIT_DIR = output_path("assets", "props", "traffic", "_kit")
SCRATCH = os.environ.get("ARCOLOGY_RENDER_DIR") or scratch_dir(NAME)

MATERIAL = "traffic_vehicle"   # the one shared final material
PREFIX = "traffic_vehicle"     # atlas image names: traffic_vehicle_{albedo,normal,orm,emission}
TEX_SIZE = 2048
EMISSION = 6.0                 # glTF emissive strength (Godot emission energy) of the whole atlas

TRI_BUDGET = {"sky_bus": 3000}
TRI_DEFAULT = 2000

HOT_ATTR = "glow_hot"          # build-time point attribute: thruster cores (removed after baking)
SPREAD = 16.0                  # m between vehicles while baking (AO must not see the neighbors)


def glb_path(vehicle):
    return output_path("assets", "props", "traffic", vehicle, f"{vehicle}.glb")


def kit_png(kind):
    return os.path.join(KIT_DIR, f"{PREFIX}_{kind}.png")


def vehicle_object(vehicle):
    objs = part_objects(vehicle, mesh_only=True)
    if len(objs) != 1:
        raise RuntimeError(f"{vehicle}: expected one mesh object, found {[o.name for o in objs]}")
    return objs[0]


def vehicle_objects():
    return [vehicle_object(v) for v in VEHICLES]


# --- Colors (linear) -----------------------------------------------------------------
# Neon/emission colors stay <= 1 per channel: the emission atlas is 8-bit and
# EMISSION scales all of it.
HEADLIGHT = (1.0, 0.95, 0.86)
TAILLIGHT = (1.0, 0.022, 0.012)
CYAN = (0.02, 0.70, 0.88)           # neon cyan #05D9E8
CYAN_HOT = (0.70, 1.0, 1.0)
AMBER = (1.0, 0.43, 0.0)            # sodium amber #FFB000
AMBER_HOT = (1.0, 0.86, 0.55)
MAGENTA = (1.0, 0.024, 0.15)        # neon magenta #FF2A6D
BAR_RED = (1.0, 0.02, 0.02)
BAR_BLUE = (0.02, 0.16, 1.0)
CABIN_WARM = (1.0, 0.62, 0.36)      # ~2700 K interiors

GUNMETAL = (0.026, 0.030, 0.036)
PRIMER = (0.20, 0.20, 0.20)
GRIME = (0.018, 0.016, 0.014)
DUST = (0.30, 0.29, 0.28)
