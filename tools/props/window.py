"""Window scenes (D-033): assets/architecture/windows/<name>/<name>.tscn from the JSON specs.

    python tools/props/window.py [--check]

Reads every tools/props/windows/*.json, the contract shared with the Blender build
(blender/architecture/windows/). Each window, in its own frame (origin on the room floor,
x = 0 at the opening's center, z = 0 on the wall's center line, +Z = room, -Z = outside):

- the frame: the artist's <name>_frame.glb (its `window_led` slot gets the spec's LED
  material), or placeholder boxes until it exists;
- one glass quad per bay (assets/shaders/window_glass.gdshader; one ShaderMaterial per
  window, local to the scene, so rooms tint independently; the HUD bay's pane has
  `hud_enabled`);
- static collision (layer 1) for frame, mullions, sill and every fixed pane;
- a tilt vent where the spec has one: a sash on a horizontal hinge (HINGE_BOTTOM) with its
  pane, HingeStopSound (latch click), HingeSwing with a latch, blocker, pass-through and a
  HingeAmbience (city noise louder with the angle);
- motorized shades, one per bay (the vent's rides in its sash), all on one MotorizedShade;
- a wall panel beside the opening with two fingertip buttons: top = shade, bottom = tint
  (SmartGlass), and a WindowHud when the spec has a HUD.

Switching to the real assets is automatic: every glb and texture below is used as soon as
it exists; run this again, scan in the editor and force-reload open scenes. The numbers the
contract doesn't pin are the constants below; the artist's files have to agree with them.
tools/blockout/apartment.py cuts the wall openings with opening() and places the scenes.

Every window glb embeds the shared 1024² trim set (material `window_trim`). Before the
editor first sees new glbs, run

    python tools/props/window.py --imports

It writes their .import files so `window_trim` maps to the one shared
assets/materials/window_trim.tres (textures from _kit/) and the embedded copies are
discarded: one trim set in memory, no extracted duplicates next to each glb.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from prop_scenes import (HINGE_BOTTOM, ROOT, Scene, Sound, TextResource, glb_bounds, glb_node_position, main, raw,
                         ref, v2)

SPECS = Path(__file__).resolve().parent / "windows"
OUT = "assets/architecture/windows"
KIT = f"{OUT}/_kit"
SHADER = "assets/shaders/window_glass.gdshader"
LED = {"warm": "assets/materials/window_led_warm.tres", "cyan": "assets/materials/window_led_cyan.tres"}
FABRIC = "assets/materials/shade_fabric.tres"
TRIM = "assets/materials/window_trim.tres"
FRAME_MAT = "assets/materials/gunmetal.tres"
STONE_MAT = "assets/materials/ceramic.tres"
METAL_MAT = "assets/materials/brushed_steel.tres"

# Not pinned by the contract (window-local meters):
SILL_T = 0.03            # stone sill slab: y bottom - SILL_T .. bottom, z -wall_depth/2 .. wall_depth/2 + overhang
SILL_EARS = 0.03         # the sill reaches this far past the opening on each side
LINER = 0.02             # reveal liners (jambs, head soffit) between the frame's room face and the wall face
SHADE_Z = -0.02          # shade plane (bar and fabric), between the glass and the frame's room face
BAR = (0.03, 0.02)       # placeholder bar height and depth (the glb's own height wins)
FABRIC_INSET = 0.005     # fabric narrower than the bar on each side
PANEL_GAP = 0.12         # panel center from the opening's edge, on the wall's room face
PANEL = (0.08, 0.14, 0.012)
BUTTONS = (("ShadeButton", 0.03, "SHADE"), ("TintButton", -0.03, "TINT"))   # y from the panel center
KIT_BUTTON_EMPTIES = {"ShadeButton": "ButtonTop", "TintButton": "ButtonBottom"}
BUTTON_RADIUS = 0.018
BUTTON_TRAVEL = 0.004
GLASS_GROUP = ["window_glass"]   # RainOnGlass finds the panes by it
HUD_MARGIN = 0.08        # readout's right edge from the bay's east edge
HUD_Y = 1.2              # readout's lower edge above the floor
LED_STRIP = (0.012, 0.015)
GLASS_COLLISION = 0.03   # glass collision box thickness
HANDLE = (0.022, 0.13, 0.03)   # placeholder lever handle (w, h, d)


def load() -> list[tuple[dict, dict]]:
    """(profile, window spec) for every window in every spec file."""
    out = []
    for path in sorted(SPECS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out += [(data["profile"], w) for w in data["windows"]]
    return out


def spec(name: str) -> tuple[dict, dict]:
    for profile, w in load():
        if w["name"] == name:
            return profile, w
    raise KeyError(name)


def layout(profile: dict, w: dict) -> dict:
    """Derived numbers (profile _doc): bay width and centers, clear height, frame depth."""
    ff, mf, n = profile["frame_face"], profile["mullion_face"], w["bays"]
    width, bottom, top = w["width"], w["bottom"], w["top"]
    bay_w = (width - 2 * ff - (n - 1) * mf) / n
    clear_h = top - bottom - 2 * ff
    fz0, fz1 = profile["frame_z"]
    return {
        "W": width, "B": bottom, "T": top, "D": w["wall_depth"], "n": n, "ff": ff, "mf": mf,
        "bay_w": bay_w, "clear_h": clear_h, "clear_y": bottom + ff + clear_h / 2,
        "bay_x": [-width / 2 + ff + bay_w * (i + 0.5) + i * mf for i in range(n)],
        "fz": (fz0 + fz1) / 2, "fd": fz1 - fz0, "fz1": fz1,
        "gz": profile["glass_z"], "sf": profile["sash_face"], "sz": tuple(profile["sash_z"]),
        "overhang": profile["interior_sill_overhang"],
    }


def opening(profile: dict, w: dict) -> tuple[float, float, float, float]:
    """The wall cut (x0, x1, y0, y1) in the window frame: a stone sill sits in the cut below `bottom`."""
    y0 = w["bottom"] - (SILL_T if w["sill"] == "stone" else 0.0)
    return -w["width"] / 2, w["width"] / 2, y0, w["top"]


def pascal(name: str) -> str:
    return "".join(p.title() for p in name.split("_"))


def r(x: float) -> float:
    return round(x, 5) + 0.0


def rv(*c: float) -> tuple:
    return tuple(r(x) for x in c)


def paths(name: str) -> dict[str, str]:
    d = f"{OUT}/{name}"
    return {"frame": f"{d}/{name}_frame.glb", "sash": f"{d}/{name}_sash.glb", "bar": f"{d}/{name}_shade_bar.glb",
            "bar_vent": f"{d}/{name}_shade_bar_vent.glb",
            "panel": f"{KIT}/window_panel.glb", "button": f"{KIT}/window_panel_button.glb",
            "tscn": f"{d}/{name}.tscn"}


def exists(path: str) -> bool:
    return (ROOT / path).exists()


# ---------------------------------------------------------------- scene

def window(profile: dict, w: dict) -> Scene:
    g = layout(profile, w)
    p = paths(w["name"])
    W, B, T, D, n = g["W"], g["B"], g["T"], g["D"], g["n"]
    bay_w, ch, cy, ff = g["bay_w"], g["clear_h"], g["clear_y"], g["ff"]
    vent = w.get("vent")
    vent_bay = vent["bay"] if vent else -1
    hud = w.get("hud") or None
    panel_x = (1 if w["panel"]["side"] == "east" else -1) * (W / 2 + PANEL_GAP)

    s = Scene(pascal(w["name"]) + "Window", doc(w, g))
    glass_mat = s.sub("ShaderMaterial", "ShaderMaterial_glass", {
        "resource_local_to_scene": True, "render_priority": 0, "shader": s.ext(SHADER)})

    # Frame: collision (StaticBody3D, layer 1) and the model or its placeholder.
    frame_boxes = [
        ("HeadCollision", rv(0, T - ff / 2, g["fz"]), rv(W, ff, g["fd"])),
        ("BottomCollision", rv(0, B + ff / 2, g["fz"]), rv(W, ff, g["fd"])),
        ("JambWestCollision", rv(-W / 2 + ff / 2, cy, g["fz"]), rv(ff, ch, g["fd"])),
        ("JambEastCollision", rv(W / 2 - ff / 2, cy, g["fz"]), rv(ff, ch, g["fd"])),
    ]
    for i in range(n - 1):
        x = g["bay_x"][i] + bay_w / 2 + g["mf"] / 2
        frame_boxes.append((f"Mullion{i}Collision", rv(x, cy, g["fz"]), rv(g["mf"], ch, g["fd"])))
    liner_z, liner_d = (g["fz1"] + D / 2) / 2, D / 2 - g["fz1"]
    frame_boxes += [
        ("LinerWestCollision", rv(-W / 2 + LINER / 2, (B + T - LINER) / 2, liner_z), rv(LINER, T - B - LINER, liner_d)),
        ("LinerEastCollision", rv(W / 2 - LINER / 2, (B + T - LINER) / 2, liner_z), rv(LINER, T - B - LINER, liner_d)),
        ("SoffitCollision", rv(0, T - LINER / 2, liner_z), rv(W, LINER, liner_d)),
    ]
    if w["sill"] == "stone":
        z0, z1 = -D / 2, D / 2 + g["overhang"]
        frame_boxes.append(("SillCollision", rv(0, B - SILL_T / 2, (z0 + z1) / 2), rv(W + 2 * SILL_EARS, SILL_T, z1 - z0)))
    glass_boxes = [(f"Glass{i}Collision", rv(g["bay_x"][i], cy, g["gz"]), rv(bay_w, ch, GLASS_COLLISION))
                   for i in range(n) if i != vent_bay]
    s.node("Frame", "StaticBody3D")
    s.boxes("Frame", frame_boxes + glass_boxes, "frame")

    if exists(p["frame"]):
        s.instance("FrameModel", p["frame"])
        s.node("LedMaterial", "Node", props={"script": s.ext("named_material_override"), "root": ref("FrameModel"),
                                             "material_name": "window_led", "material": s.ext(LED[w["led"]])})
    else:
        s.node("FrameModel", "Node3D", props={"metadata/_doc": f"Placeholder until {p['frame']} exists."})
        for name, center, size in frame_boxes:
            if name.startswith(("Liner", "Soffit")):
                continue
            mat = STONE_MAT if name.startswith("Sill") else FRAME_MAT
            s.mesh(name.removesuffix("Collision"), s.box_mesh(size), parent="FrameModel", position=center, material=mat)
        led_z = (g["fz1"] + D / 2) / 2
        s.mesh("Led", s.box_mesh(rv(W - 0.02, LED_STRIP[0], LED_STRIP[1])), parent="FrameModel",
               position=rv(0, T - LED_STRIP[0] / 2, led_z), material=LED[w["led"]], shadow=False)

    # Glass: one quad per fixed bay (the vent's pane rides in its sash).
    panes: list[str] = []
    for i in range(n):
        if i == vent_bay:
            continue
        props: dict = {}
        if hud and hud["bay"] == i:
            props = hud_props(bay_w, cy)
        panes.append(s.mesh(f"Glass{i}", s.quad_mesh(r(bay_w), r(ch)), position=rv(g["bay_x"][i], cy, g["gz"]),
                            material=glass_mat, override=True, shadow=False, props=props, groups=GLASS_GROUP))

    # Shades: a head slot per bay.
    def bar_size(glb: str) -> tuple[float, float] | None:
        """(width, height) of a bar glb, or None while it doesn't exist."""
        b = glb_bounds(glb)
        return (b[1][0] - b[0][0], r(b[1][1] - b[0][1])) if b else None

    bar_h = (bar_size(p["bar"]) or (0, BAR[0]))[1]
    shade_nodes: list[str] = []
    drops: list[float] = []

    def shade(parent: str, i: int, position: tuple, width: float, drop: float, glb: str) -> None:
        """A shade: `glb` is its bar (the bay bar, or the vent's own); a bay bar is scaled to fit if needed."""
        if not exists(glb):
            glb = p["bar"]
        size = bar_size(glb)
        node = s.node(f"Shade{i}", "Node3D", parent=parent, position=position)
        if size:
            scale = width / size[0]
            bar = s.node("Bar", parent=node, props={"scale": rv(scale, 1, 1)} if abs(scale - 1) > 1e-3 else None,
                         instance=s.ext_id(glb))
        else:
            bar = s.node("Bar", "Node3D", parent=node)
            s.mesh("BarMesh", s.box_mesh(rv(width - 0.004, bar_h, BAR[1])), parent=bar, position=rv(0, -bar_h / 2, 0),
                   material=FRAME_MAT)
        s.mesh("Fabric", s.quad_mesh(r(width - 2 * FABRIC_INSET), 1.0), parent=node, material=FABRIC, override=True,
               props={"visible": False})
        shade_nodes.append(node)
        drops.append(r(drop))

    for i in range(n):
        if i != vent_bay and w.get("shade"):
            shade(".", i, rv(g["bay_x"][i], T - ff, SHADE_Z), bay_w, ch - bar_h, p["bar"])

    # Tilt vent.
    hinge = None
    if vent:
        sf, (sz0, sz1) = g["sf"], g["sz"]
        grip = glb_node_position(p["sash"], "HandleGrip") if exists(p["sash"]) else None
        if grip is None:
            side = -1 if vent["handle_stile"] == "west" else 1
            grip = rv(side * (bay_w / 2 - sf / 2), vent["handle_y"] - (B + ff), 0.03)
        joint = s.hinged_door(
            group="Vent", glb=p["sash"] if exists(p["sash"]) else None, model_name="SashModel",
            hinge_position=rv(g["bay_x"][vent_bay], B + ff, sz1), hinge_rotation=HINGE_BOTTOM,
            open_max=float(vent["open_max_deg"]), shape_prefix="sash",
            boxes=[("SashCollision", rv(0, ch / 2, (sz0 - sz1) / 2), rv(bay_w, ch, sz1 - sz0))],
            grip=grip, grab_radius=0.05,
            stop=Sound("sfx/vent_latch", props={"volume_db": -4.0}),
            stop_props={"min_speed": 4.0, "full_volume_speed": 40.0},
            swing={"friction": 60.0, "damping": 3.0, "bounce": 0.1, "max_speed": 120.0, "latch_angle": 2.5,
                   "latch_pull": 60.0})
        hinge = joint.joint
        body = joint.body
        depth, zc = sz1 - sz0, (sz0 - sz1) / 2
        if not exists(p["sash"]):
            s.node("SashModel", "Node3D", parent=body, props={"metadata/_doc": f"Placeholder until {p['sash']} exists."})
            model = f"{body}/SashModel"
            for name, center, size in [
                    ("RailBottom", (0, sf / 2, zc), (bay_w, sf, depth)), ("RailTop", (0, ch - sf / 2, zc), (bay_w, sf, depth)),
                    ("StileWest", (-bay_w / 2 + sf / 2, ch / 2, zc), (sf, ch - 2 * sf, depth)),
                    ("StileEast", (bay_w / 2 - sf / 2, ch / 2, zc), (sf, ch - 2 * sf, depth))]:
                s.mesh(name, s.box_mesh(rv(*size)), parent=model, position=rv(*center), material=FRAME_MAT)
            s.mesh("Handle", s.box_mesh(HANDLE), parent=model, position=rv(grip[0], grip[1], HANDLE[2] / 2),
                   material=METAL_MAT)
        panes.append(s.mesh(f"Glass{vent_bay}", s.quad_mesh(r(bay_w - 2 * sf), r(ch - 2 * sf)), parent=body,
                            position=rv(0, ch / 2, g["gz"] - sz1), material=glass_mat, override=True, shadow=False,
                            groups=GLASS_GROUP))
        if w.get("shade"):
            vent_bar_h = (bar_size(p["bar_vent"]) or (0, bar_h))[1]
            shade(body, vent_bay, rv(0, ch - sf, SHADE_Z - sz1), bay_w - 2 * sf, ch - 2 * sf - vent_bar_h, p["bar_vent"])
        s.sound("Ambience", "sfx/city_ambience", position=rv(g["bay_x"][vent_bay], B + ff + ch * 0.9, D / 2),
                volume_db=-80.0, unit_size=2.0, max_distance=25.0, script=s.ext("hinge_ambience"), hinge=ref(hinge),
                open_db=-4.0)
        # The rain outside, louder with the opening and the rain (RainOnGlass sets the gain).
        s.sound("RainAmbience", "sfx/rain_outside", position=rv(g["bay_x"][vent_bay], B + ff + ch * 0.9, D / 2),
                groups=["rain_ambience"], volume_db=-80.0, unit_size=2.5, max_distance=25.0,
                script=s.ext("hinge_ambience"), hinge=ref(hinge), open_db=0.0, gain=0.0)

    # Wall panel: top button runs the shades, bottom one steps the tint.
    s.node("Panel", "Node3D", position=rv(panel_x, w["panel"]["y"], D / 2))
    kit = exists(p["panel"])
    if kit:
        s.instance("PanelModel", p["panel"], parent="Panel")
        s.node("PanelLedMaterial", "Node", props={
            "script": s.ext("named_material_override"), "root": ref("Panel/PanelModel"), "material_name": "panel_led",
            "material": s.ext(LED[w["led"]])})
    else:
        s.mesh("Plate", s.box_mesh(PANEL), parent="Panel", position=rv(0, 0, PANEL[2] / 2), material=FRAME_MAT)
    for name, dy, label in BUTTONS:
        at = glb_node_position(p["panel"], KIT_BUTTON_EMPTIES[name]) if kit else None
        at = at or rv(0, dy, PANEL[2])
        button = s.area_button(name, position=at, radius=BUTTON_RADIUS, displacement=(0, 0, -BUTTON_TRAVEL),
                               shape_id="SphereShape3D_button", parent="Panel")
        if exists(p["button"]):
            s.instance("Model", p["button"], parent=f"{button}/Cap")
        else:
            s.mesh("CapMesh", s._sized("CylinderMesh", ("cap",), {
                "top_radius": 0.012, "bottom_radius": 0.012, "height": 0.006, "radial_segments": 24, "rings": 1}),
                parent=f"{button}/Cap", position=(0, 0, 0.003), rotation=(90, 0, 0), material=METAL_MAT)
        if not kit:
            s.node(f"{name}Label", "Label3D", parent="Panel", props={
                "position": rv(0, at[1] - 0.021, PANEL[2] + 0.001), "pixel_size": 0.0003,
                "modulate": raw("Color(0.75, 0.78, 0.8, 1)"), "font_size": 32, "outline_size": 0, "text": label})
    # Rain on the glass; RainOnGlass plays it and scales it by the rain (this volume = full rain).
    s.sound("RainPatter", "sfx/rain_patter", position=rv(0, cy, g["gz"]), groups=["rain_patter"], volume_db=-16.0,
            unit_size=2.0, max_distance=15.0)
    s.sound("PanelClick", "sfx/button_click", position=rv(panel_x, w["panel"]["y"], D / 2 + 0.02), volume_db=-8.0)

    if w.get("shade"):
        s.sound("ShadeMotor", "sfx/shade_motor", position=rv(0, T - 0.1, 0), volume_db=-14.0, unit_size=2.0,
                max_distance=15.0)
        s.node("Shade", "Node", props={
            "script": s.ext("motorized_shade"), "button": ref("Panel/ShadeButton"),
            "shades": [ref(x) for x in shade_nodes],
            "drops": raw("PackedFloat32Array(%s)" % ", ".join(f"{d:g}" for d in drops)),
            "motor": ref("ShadeMotor"), "click": ref("PanelClick")})
    if w.get("tint"):
        s.sound("TintTone", "sfx/tint_tone", position=rv(panel_x, w["panel"]["y"], D / 2 + 0.02), volume_db=-12.0)
        s.node("SmartGlass", "Node", props={
            "script": s.ext("smart_glass"), "button": ref("Panel/TintButton"), "panes": [ref(x) for x in panes],
            "tone": ref("TintTone"), "click": ref("PanelClick")})
    if hud:
        s.node("Hud", "Node", props={"script": s.ext("window_hud"), "panes": [ref(f"Glass{hud['bay']}")]})
    return s


def hud_props(bay_w: float, clear_y: float) -> dict:
    """Instance uniforms of the HUD pane: readout's lower right corner in pane meters."""
    return {"instance_shader_parameters/hud_enabled": True,
            "instance_shader_parameters/hud_anchor": v2(r(bay_w / 2 - HUD_MARGIN), r(HUD_Y - clear_y))}


def doc(w: dict, g: dict) -> str:
    parts = [f"Window {g['W']:g} x {g['T'] - g['B']:g} m, {g['n']} bay(s), opening {g['B']:g}..{g['T']:g} m above the "
             "floor. Origin on the room floor at the opening's center on the wall's center line; -Z is outside. "
             f"GENERATED by tools/props/window.py from tools/props/windows/ ({w['name']}); edit the spec, not this file."]
    if w.get("vent"):
        parts.append(f"Bay {w['vent']['bay']} is a tilt vent (grab its handle, 0..{w['vent']['open_max_deg']:g} degrees, "
                     "latches shut near closed; city noise while open).")
    parts.append(f"Panel on the {w['panel']['side']} side: top button runs the shades (press again to stop, again to "
                 "reverse), bottom button steps the smart glass tint (clear, half, dark).")
    if w.get("hud"):
        parts.append(f"HUD readout (time, temperature, weather) in the lower east corner of bay {w['hud']['bay']}.")
    return " ".join(parts)


def fabric_material() -> TextResource:
    """assets/materials/shade_fabric.tres: the artist's tileable 1 m fabric once it exists, else a flat linen grey."""
    albedo, normal = f"{KIT}/shade_fabric_albedo.png", f"{KIT}/shade_fabric_normal.png"
    ext, props = [], ['resource_name = "shade_fabric"']
    if exists(albedo):
        ext.append(f'[ext_resource type="Texture2D" path="res://{albedo}" id="1_albedo"]')
        props += ["albedo_texture = ExtResource(\"1_albedo\")"]
    else:
        props += ["albedo_color = Color(0.42, 0.4, 0.37, 1)"]
    props += ["roughness = 0.92"]
    if exists(normal):
        ext.append(f'[ext_resource type="Texture2D" path="res://{normal}" id="2_normal"]')
        props += ["normal_enabled = true", "normal_texture = ExtResource(\"2_normal\")"]
    head = '[gd_resource type="StandardMaterial3D" format=3]\n\n'
    body = "[resource]\n" + "\n".join(props) + "\n"
    return TextResource(head + ("\n".join(ext) + "\n\n" if ext else "") + body)


IMPORT = """[remap]

importer="scene"
importer_version=1
type="PackedScene"

[deps]

source_file="res://{path}"

[params]

nodes/root_type=""
nodes/root_name=""
nodes/root_script=null
mesh_library/use_node_names_as_mesh_names=false
array_mesh/deduplicate_surfaces=true
nodes/apply_root_scale=true
nodes/root_scale=1.0
nodes/import_as_skeleton_bones=false
nodes/use_name_suffixes=true
nodes/use_node_type_suffixes=true
meshes/ensure_tangents=true
meshes/generate_lods=true
meshes/create_shadow_meshes=true
meshes/light_baking=1
meshes/lightmap_texel_size=0.2
meshes/force_disable_compression=false
skins/use_named_skins=true
animation/import=true
animation/fps=30
animation/trimming=false
animation/remove_immutable_tracks=true
animation/import_rest_as_RESET=false
import_script/path=""
materials/extract=0
materials/extract_format=0
materials/extract_path=""
_subresources={{
"materials": {{
"window_trim": {{
"use_external/enabled": true,
"use_external/fallback_path": "res://{trim}",
"use_external/path": "res://{trim}"
}}
}}
}}
gltf/naming_version=2
gltf/embedded_image_handling=0
gltf/texture_map_mode=1
"""


def write_imports() -> int:
    """Writes the .import of every window glb that has none yet (see the module doc). Returns the count."""
    count = 0
    for glb in sorted((ROOT / OUT).rglob("*.glb")):
        imp = glb.with_name(glb.name + ".import")
        if imp.exists():
            continue
        rel = glb.relative_to(ROOT).as_posix()
        imp.write_text(IMPORT.format(path=rel, trim=TRIM), encoding="utf-8", newline="\n")
        print(f"wrote {rel}.import")
        count += 1
    return count


def scenes() -> dict:
    out: dict = {FABRIC: fabric_material()}
    for profile, w in load():
        out[paths(w["name"])["tscn"]] = window(profile, w)
    return out


if __name__ == "__main__":
    if "--imports" in sys.argv[1:]:
        print(f"{write_imports()} import file(s) written")
        sys.exit(0)
    main(scenes)
