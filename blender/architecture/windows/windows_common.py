"""Procedural windows (D-033): a window spec file (JSON) -> finished window assets.
Built on blender/lib (D-028); quick reference: blender/lib/README.md.

The spec (default tools/props/windows/apartment.json) is the single source of
truth: every contract number (widths, heights, bays, wall depth, the shared
frame profile, vents, shades) is read from it here, never copied. The Godot
generator (tools/props/window.py) derives glass, collision, hinges and shades
from the same numbers plus a few constants of its own (GODOT below; verify.py
cross-checks them). Only the look (reveal liner, head cassette, LED channel,
sill shapes, handle, slots) is designed here, in DESIGN, and checked to fit.

Stages (Blender 5.2, background, from the repo root; `-- --spec <file>` picks
another spec, relative to the repo root):

  blender -b --factory-startup --python blender/architecture/windows/build.py [-- --spec F]
  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/bake.py
  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/export.py
  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/render.py -- [--quick] [--out DIR]
  blender -b --factory-startup --python blender/architecture/windows/verify.py [-- --spec F]

Outputs: assets/architecture/windows/<window>/<window>_frame.glb, _sash.glb and
_shade_bar_vent.glb (vent only), _shade_bar.glb; the shared kit in
assets/architecture/windows/_kit/ (panel, button, shade fabric and trim textures).

Coordinates: geometry is authored in each window's local Godot frame (origin
on the room floor, x = 0 at the opening's center, z = 0 on the wall's center
line, +Z room side) and converted with trim.GODOT_TO_BLENDER (Blender
(x, y, z) = Godot (x, -z, y)); the room side is Blender -Y. "west" = -X, "east"
= +X; bays are numbered from west to east.

Finishes: one shared trim sheet (window_trim.py) for every window, sash, bar
and panel, so a new spec needs no new bake; real-world UVs (512 px/m, U
repeats every 2 m).
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

from arcology_blender.scene import output_path, part_objects, repo_path, scratch_dir, script_args  # noqa: E402

NAME = "windows"
DEFAULT_SPEC = ("tools", "props", "windows", "apartment.json")
SCRATCH = scratch_dir(NAME)


def spec_path(args=None):
    args = script_args() if args is None else args
    if "--spec" in args:
        p = args[args.index("--spec") + 1]
        return p if os.path.isabs(p) else repo_path(p)
    return repo_path(*DEFAULT_SPEC)


def load_spec(path=None):
    path = path or spec_path()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return path, data


def spec_stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def blend_path(path=None):
    return output_path("blender", "architecture", f"windows_{spec_stem(path or spec_path())}.blend")


def asset_dir(*parts):
    return output_path("assets", "architecture", "windows", *parts)


def glb_frame(name):
    return asset_dir(name, f"{name}_frame.glb")


def glb_sash(name):
    return asset_dir(name, f"{name}_sash.glb")


def glb_bar(name, vent=False):
    return asset_dir(name, f"{name}_shade_bar{'_vent' if vent else ''}.glb")


GLB_PANEL = asset_dir("_kit", "window_panel.glb")
GLB_BUTTON = asset_dir("_kit", "window_panel_button.glb")
FABRIC_ALBEDO = asset_dir("_kit", "shade_fabric_albedo.png")
FABRIC_NORMAL = asset_dir("_kit", "shade_fabric_normal.png")
TRIM_PNG = {k: asset_dir("_kit", f"window_trim_{k}.png") for k in ("albedo", "normal", "orm")}

# Material slot names (Godot switches / colors these by name)
MAT_TRIM = "window_trim"        # the shared trim sheet (everything that isn't a light)
MAT_LED = "window_led"          # diffused LED channel: white emission, Godot colors it per spec
MAT_STATUS = "window_status"    # the sensor strip's tiny status LED
MAT_PANEL_LED = "panel_led"     # the wall panel's button rings and icons
LED_STRENGTH = 4.0
STATUS_STRENGTH = 3.0
PANEL_LED_STRENGTH = 3.0
STATUS_COLOR = (0.040, 1.0, 0.007)   # acid green #39FF14 (linear)

# Trim sheet and fabric texture sizes
TRIM_SIZE = 1024       # one 1024^2 set for every window part (<= 1024 also for the panel and handle)
TRIM_PX_PER_M = 512.0  # style guide: ~512 px/m for props in reach
FABRIC_SIZE = 1024     # 1 m x 1 m tile

# --- Numbers the Godot generator pins (tools/props/window.py; verify.py cross-checks) ---
GODOT = dict(
    sill_t=0.03,      # SILL_T: stone slab from bottom - 0.03 to bottom (top exactly at `bottom`), z -wd/2 .. wd/2 + overhang
    sill_ears=0.03,   # SILL_EARS: the slab reaches this far past the opening on each side
    shade_z=-0.02,    # SHADE_Z: shade plane (bar and fabric), between the glass and the frame's room face
)
GODOT_PY = ("tools", "props", "window.py")
GODOT_KEYS = {"sill_t": "SILL_T", "sill_ears": "SILL_EARS", "shade_z": "SHADE_Z"}


def godot_constants():
    """GODOT's keys as written in tools/props/window.py (None if the file is missing).
    ARCOLOGY_WINDOW_PY overrides the path (a worktree without the Godot side)."""
    path = os.environ.get("ARCOLOGY_WINDOW_PY") or repo_path(*GODOT_PY)
    if not os.path.exists(path):
        return None, path
    text = open(path, encoding="utf-8").read()
    out = {}
    for key, const in GODOT_KEYS.items():
        m = re.search(rf"^{const}\s*=\s*([-0-9.eE]+)", text, re.M)
        out[key] = float(m.group(1)) if m else None
    return out, path


# --- Design (the look; not part of the contract, checked against it) -------------
DESIGN = dict(
    chamfer=0.0015,           # crisp 45 degree chamfers on every aluminium edge
    liner=0.020,              # jamb liner thickness (visible face 20 mm inside the opening)
    shadow_gap=0.003,         # dark gap between the frame's room face and the liners
    head=0.020,               # head cassette depth below the opening's top
    stone_round=0.006,        # softened top front edge of the stone
    stone_round_low=0.002,
    threshold_top=0.002,      # floor sill: metal threshold, 2 mm proud of the floor
    threshold_below=0.010,
    channel_w=0.012,          # threshold channel (drain line), centered in the reveal
    channel_d=0.006,
    # head soffit, measured from the frame's interior face (frame_z[1]) toward the room
    sensor=(0.008, 0.018),    # flush black-glass sensor strip
    led=(0.028, 0.052),       # LED channel (24 mm)
    soffit_margin=0.006,      # minimum soffit left between the LED channel and the room edge
    led_depth=0.006,
    led_return=0.30,          # LED returns down the jambs
    sensor_len=0.16,
    status_r=0.0015,
    # shade: the fabric exits a slot in the head rail's sightline face (fixed bays) or
    # the sash's top rail (vent); the bar parks just below it
    slot_w=0.006,
    slot_depth=0.028,
    slot_inset=0.003,         # slot ends short of the shade's edges
    gasket_protrude=0.004,    # EPDM lips on both sides of the glass
    gasket_gap=0.0015,        # lip face distance from glass_z
    gasket_t=0.0045,
    stop_inset=0.012,         # vent bay: frame stop behind the sash
    stop_depth=0.025,
    sash_gap=0.003,           # sash clearance to the frame (sides and top)
    flashing_proj=0.055,
    flashing_drop=0.006,
    flashing_face=0.035,
    flashing_t=0.002,
    flashing_ext=0.015,       # past the opening on each side
    bar_h=0.022,              # shade bottom bar (length = the shade's width)
    bar_d=0.012,
    bar_cap=0.006,
)


class Window:
    """One window of a spec with every derived dimension (Godot local frame)."""

    def __init__(self, spec, profile):
        self.spec = spec
        self.name = spec["name"]
        self.W = float(spec["width"])
        self.B = float(spec["bottom"])
        self.T = float(spec["top"])
        self.wd = float(spec["wall_depth"])
        self.n = int(spec["bays"])
        self.sill = spec["sill"]
        self.vent = spec.get("vent")
        self.shade = bool(spec.get("shade"))
        p = profile
        self.ff = float(p["frame_face"])
        self.z0, self.z1 = (float(v) for v in p["frame_z"])
        self.mf = float(p["mullion_face"])
        self.gz = float(p["glass_z"])
        self.sf = float(p["sash_face"])
        self.sz0, self.sz1 = (float(v) for v in p["sash_z"])
        self.ov = float(p["interior_sill_overhang"])
        self.zi, self.ze = self.wd / 2, -self.wd / 2
        self.cw = (self.W - 2 * self.ff - (self.n - 1) * self.mf) / self.n
        self.y0, self.y1 = self.B + self.ff, self.T - self.ff
        self.ch = self.y1 - self.y0
        d = DESIGN
        self.head_y = self.T - d["head"]                     # soffit
        self.sill_y = self.B + (0.0 if self.sill == "stone" else d["threshold_top"])
        zr = lambda a: self.z1 + a  # noqa: E731
        self.sensor_z = tuple(zr(a) for a in d["sensor"])
        self.led_z = tuple(zr(a) for a in d["led"])
        self.shade_z = GODOT["shade_z"]
        self.slot_z = (self.shade_z - d["slot_w"] / 2, self.shade_z + d["slot_w"] / 2)

    # bays, numbered west (-X) to east
    def bay_x(self, i):
        x0 = -self.W / 2 + self.ff + i * (self.cw + self.mf)
        return x0, x0 + self.cw

    def mullion_x(self, k):
        """Center of the mullion east of bay k."""
        return self.bay_x(k)[1] + self.mf / 2

    @property
    def vent_bay(self):
        return int(self.vent["bay"]) if self.vent else None

    def glass_rect(self, i):
        """(x0, x1, y0, y1) at glass_z; a vent's glass is inset by sash_face (closed position)."""
        x0, x1 = self.bay_x(i)
        r = (x0, x1, self.y0, self.y1)
        if i == self.vent_bay:
            s = self.sf
            r = (x0 + s, x1 - s, self.y0 + s, self.y1 - s)
        return r

    # vent (tilt sash)
    @property
    def hinge(self):
        x0, x1 = self.bay_x(self.vent_bay)
        return ((x0 + x1) / 2, self.B + self.ff, self.sz1)

    @property
    def handle_x(self):
        x0, x1 = self.bay_x(self.vent_bay)
        return x0 + self.sf / 2 if self.vent["handle_stile"] == "west" else x1 - self.sf / 2

    @property
    def handle_y(self):
        return float(self.vent["handle_y"])

    @property
    def open_max(self):
        return float(self.vent["open_max_deg"])

    # shades
    def shade_top(self, i):
        """(x center, y, z) of bay i's shade: the bar's top center when up
        (fixed bays: under the head rail; vent: under the sash's top rail)."""
        x0, x1 = self.bay_x(i)
        y = self.y1 - self.sf if i == self.vent_bay else self.y1
        return ((x0 + x1) / 2, y, self.shade_z)

    def shade_width(self, i):
        return self.cw - 2 * self.sf if i == self.vent_bay else self.cw

    def slot_x(self, i):
        x0, x1 = self.bay_x(i)
        e = DESIGN["slot_inset"] + (self.sf if i == self.vent_bay else 0.0)
        return x0 + e, x1 - e

    def check_fits(self):
        """Fail loudly when the design can't fit this spec (a shallow wall, a frame
        deeper than the wall, a handle outside the sash)."""
        d = DESIGN
        errs = []
        if not (self.ze - 1e-6 <= self.z0 < self.z1 <= self.zi + 1e-6):
            errs.append(f"frame_z {self.z0, self.z1} outside the wall {self.ze, self.zi}")
        if self.led_z[1] + d["soffit_margin"] > self.zi:
            errs.append(f"reveal too shallow for the head cassette ({self.zi - self.z1:.3f} m)")
        if not (self.z0 < self.gz < self.z1):
            errs.append("glass_z outside the frame")
        g, p = self.gz + d["gasket_gap"] + d["gasket_t"], d["bar_d"] / 2
        if not (g < self.shade_z - p and self.shade_z + p < min(self.z1, self.sz1) - d["chamfer"]):
            errs.append(f"shade plane {self.shade_z} collides with the gaskets or the room face")
        if self.sill == "stone" and GODOT["sill_t"] <= d["stone_round"] + d["stone_round_low"]:
            errs.append("stone slab too thin for its rounded nose")
        if d["liner"] >= self.ff:
            errs.append("jamb liner wider than the frame face")
        if self.cw <= 2 * self.sf + 0.05:
            errs.append(f"bays too narrow ({self.cw:.3f} m)")
        if self.vent:
            if not (0 <= self.vent_bay < self.n):
                errs.append("vent bay out of range")
            if not (self.sz0 >= self.z0 and self.sz1 <= self.z1 and self.sz0 < self.gz < self.sz1):
                errs.append("sash_z must lie inside frame_z and around glass_z")
            if not (self.y0 + self.sf + 0.08 < self.handle_y < self.y1 - self.sf - 0.04):
                errs.append(f"handle_y {self.handle_y} outside the sash stile")
        if errs:
            raise SystemExit(f"WINDOW {self.name}: " + "; ".join(errs))


def windows(data):
    return [Window(w, data["profile"]) for w in data["windows"]]


# --- parts (tagged in build.py) ---------------------------------------------------
def frame_objects(name):
    return part_objects(f"frame:{name}", mesh_only=True)


def sash_objects(name):
    return part_objects(f"sash:{name}")


def bar_objects(name, vent=False):
    return part_objects(f"{'barvent' if vent else 'bar'}:{name}")


def panel_objects():
    return part_objects("panel")


def button_objects():
    return part_objects("button")
