"""Near-ring corporate spires for the window view (style "spire" in tools/city/near_towers.json).
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

The JSON is the contract: name, footprint, roof height (top_y + 180 above the
street) and yaw per tower; Godot places each glb by pos/yaw. Only the look
lives here.

Stages (Blender 5.2, background, from the repo root):

  blender -b --factory-startup --python blender/architecture/city/spire/build.py
  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/bake.py
  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/export.py
  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/render.py -- [--quick] [--out DIR] [--only studio|night]
  blender -b --factory-startup --python blender/architecture/city/spire/verify.py

Outputs: assets/architecture/city/<tower>/<tower>.glb (one per tower) and the
shared kit textures in assets/architecture/city/_kit/spire/.

Coordinates: Blender Z up, meters, origin at the tower's base center on the
street (Godot local y = 0 = world y -180), the front (toward the apartment at
yaw 0) faces -Y (Godot +Z). Every tower is built at the origin in its own
collection; the night view moves them into place (render only, not saved).

Materials (Godot maps each name to one shared material, like window_trim):
  city_spire_glass   curtain wall: tiling 64 x 64 m set, 16 floors x 32 bays,
                     lit offices in the emission map (albedo, normal, ORM, emission)
  city_spire_metal   dark weathered cladding, louver rows for plant floors (albedo, normal, ORM)
  city_spire_lights  trim sheet of soft light strips, sky lobby and crown glow (albedo, ORM, emission)
  city_spire_ads     holo ad atlas (albedo, ORM, emission); ad panels are separate objects <tower>_ad<n>
"""

import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, repo_path, scratch_dir  # noqa: E402

NAME = "city_spire"
STYLE = "spire"
SPEC = repo_path("tools", "city", "near_towers.json")
BLEND = output_path("blender", "architecture", f"{NAME}.blend")
KIT = output_path("assets", "architecture", "city", "_kit", "spire")
SCRATCH = scratch_dir(NAME)


def glb_path(tower):
    return output_path("assets", "architecture", "city", tower, f"{tower}.glb")


def load_spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def towers(spec=None):
    """The spire towers of the JSON (dicts: name, pos, footprint, top_y, yaw)."""
    spec = spec or load_spec()
    return [t for t in spec["towers"] if t["style"] == STYLE]


def roof_height(t, spec=None):
    """Roof slab above the tower origin (the street): top_y - street_y."""
    spec = spec or load_spec()
    return t["top_y"] - spec["street_y"]


def seed_of(*parts):
    """Deterministic seed from strings (Python's hash() is salted per process)."""
    return zlib.crc32("/".join(str(p) for p in parts).encode())


# --- Materials ---------------------------------------------------------------------
MAT_GLASS = "city_spire_glass"
MAT_METAL = "city_spire_metal"
MAT_LIGHTS = "city_spire_lights"
MAT_ADS = "city_spire_ads"
MATERIALS = (MAT_GLASS, MAT_METAL, MAT_LIGHTS, MAT_ADS)

# glTF emissive strength (KHR_materials_emissive_strength = Godot emission energy).
# The textures carry the relative brightness (<= 1 linear).
EMISSION = {MAT_GLASS: 2.0, MAT_LIGHTS: 8.0, MAT_ADS: 4.0}

# --- Grid and texture sets --------------------------------------------------------
FLOOR = 4.0            # floor to floor (slab top at z = 4k above the street)
BAY = 2.0              # mullion spacing
GLASS_TILE = 64.0      # m per UV unit: 16 floors x 32 bays
GLASS_SIZE = 2048      # 32 px/m
METAL_TILE = 64.0      # m per UV unit, panel rows aligned with the floors
METAL_SIZE = 2048
LOUVER_V = (56.0, 64.0)  # metal tile rows (meters) with plant-floor louvers; panels below
LIGHTS_SIZE = 1024
LIGHTS_PX_M = 16.0     # lights sheet: U repeats every 64 m along a strip
ADS_SIZE = 2048

# Lights trim sheet: bands bottom-up (name, usable rows); V is stretched across a
# strip's width, or across the lobby / crown height. pad rows above and below.
LIGHT_PAD = 6
LIGHT_BANDS = (
    ("white", 32), ("cyan", 32), ("magenta", 32), ("uv", 32), ("amber", 32), ("red", 32),
    ("pad", 32), ("lobby", 192), ("lobby_warm", 192), ("crown", 256),
)


def light_band_rows():
    rows, nxt = {}, 0
    for name, n in LIGHT_BANDS:
        r0 = nxt + LIGHT_PAD
        rows[name] = (r0, n)
        nxt = r0 + n + LIGHT_PAD
    assert nxt <= LIGHTS_SIZE, f"lights sheet full ({nxt} rows)"
    return rows


LIGHT_ROWS = light_band_rows()


def light_uv(band, u_m, frac):
    """UV in the lights sheet: u_m meters along the strip, frac 0..1 across the band."""
    r0, n = LIGHT_ROWS[band]
    frac = min(max(frac, 0.0), 1.0)
    return (u_m * LIGHTS_PX_M / LIGHTS_SIZE, (r0 + 0.5 + frac * (n - 1)) / LIGHTS_SIZE)


# Ad atlas regions in pixels (x0, y0, x1, y1), y up from the image bottom.
AD_REGIONS = {
    "kagerou": (0, 0, 896, 1120),        # portrait 4:5   energy drink (blade front)
    "tensei": (896, 0, 1152, 1280),      # banner 1:5     cybernetics, cyan
    "ryujin": (1152, 0, 1408, 1280),     # banner 1:5     ramen, magenta
    "hoshizora": (1408, 0, 2048, 480),   # 4:3            airline, cyan
    "mirai": (1408, 480, 2048, 960),     # 4:3            bank, ultraviolet
    "kusuri": (1408, 960, 2048, 1280),   # 2:1            24 h pharmacy
    "ticker": (0, 1120, 896, 1280),      # 5.6:1          stock ticker
    "sorakaze": (0, 1280, 1024, 2048),   # 4:3            hover cars
    "okami": (1024, 1280, 2048, 2048),   # 4:3            security firm
}


def ad_aspect(region):
    x0, y0, x1, y1 = AD_REGIONS[region]
    return (x1 - x0) / (y1 - y0)


def ad_uv(region, a, b):
    """UV of the point (a, b) in 0..1 (left..right, bottom..top) of an ad region."""
    x0, y0, x1, y1 = AD_REGIONS[region]
    return ((x0 + 0.5 + a * (x1 - x0 - 1)) / ADS_SIZE, (y0 + 0.5 + b * (y1 - y0 - 1)) / ADS_SIZE)


# --- Part tags ---------------------------------------------------------------------
def body_part(tower):
    return tower


def ad_part(tower):
    return f"{tower}:ad"


def blink_part(tower):
    return f"{tower}:blink"


def tower_objects(tower):
    """Everything one glb exports: body, ad panels, blink lights."""
    return (part_objects(body_part(tower), mesh_only=True) + part_objects(ad_part(tower), mesh_only=True)
            + part_objects(blink_part(tower), mesh_only=True))


def kit_png(material, kind):
    return os.path.join(KIT, f"{material}_{kind}.png")
