"""Shower scenes (built by blender/props/shower/):

- assets/props/shower/shower.tscn: walk-in shower (body glb with its collision: glass screen,
  shelf, stabiliser bar), the frameless glass with its own cheap glass shader, the mixer's flow
  lever and thermostat dial on hinges, and the hand shower in its holder;
- assets/props/shower/shower_handheld.tscn: the hand shower, a pickable that sits in the holder;
- assets/props/shower/shower_parts.tres: the one material the three part glbs share.

Numbers from the artist's report (Godot prop-local: origin = footprint center on the floor,
back wall at z -0.70, +Z out of the back wall into the room). Lever and dial boxes and grips
are in their pivot frames.

    python tools/props/shower.py [--check]
    python tools/props/shower.py --imports   # before the editor first sees the part glbs

The three part glbs embed the same ShowerParts texture set. --imports extracts it once into
shower_parts_{albedo,normal,orm}.png and writes the part glbs' .import files so their
`ShowerParts` slot maps to shower_parts.tres and the embedded copies are discarded: one
texture set in memory instead of three. It only writes files that don't exist yet.
"""

from __future__ import annotations

import sys

from prop_scenes import (RENDER_UNREFLECTED, TEXTURE_IMPORT, Scene, Sound, TextResource, color, glb_images,
                         glb_import_text, glb_node_position, main, pickable_scene, ref, raw, write_new_file)

D = "assets/props/shower"
BODY = f"{D}/shower_body.glb"
FLOW, TEMP, HANDHELD = f"{D}/shower_mixer_flow.glb", f"{D}/shower_mixer_temp.glb", f"{D}/shower_handheld.glb"
HANDHELD_TSCN = f"{D}/shower_handheld.tscn"
PARTS_MAT = f"{D}/shower_parts.tres"
PARTS_TEX = {kind: f"{D}/shower_parts_{kind}.png" for kind in ("albedo", "orm", "normal")}
GLASS_SHADER = "assets/shaders/shower_glass.gdshader"
# The screen (shower_body.glb `ShowerGlass`): plane z 0.70, x -0.40..1.386, y 0..2. Live reflection on
# both faces (D-049), faint like the windows, reaching across the bathroom.
GLASS_CENTER = (0.493, 1.0, 0.70)
GLASS_SIZE = (1.786, 2.0)
GLASS_PPM = 350.0
GLASS_REACH = 3.5

# Lever and dial turn about local +Z (the wall normal), positive = counterclockwise seen from the
# room. The XR Tools hinge turns about its local X: the HingeOrigin turned -90 about Y puts it on +Z.
WALL_AXIS = (0, -90, 0)
FLOW_PIVOT, TEMP_PIVOT = (-0.60, 1.175, -0.69), (-0.60, 1.025, -0.69)
# Flow lever: 0 = off (paddle down), +90 = rain head, -90 = hand shower; clicks into all three.
FLOW_DETENTS = [-90.0, 0.0, 90.0]
# Thermostat: ±120 degrees, + = hotter; a click at the 38 °C stop (0, indicator up).
TEMP_RANGE = 120.0
# The dial's grip sits on its rim (indicator side): a grip on the axis couldn't turn it.
TEMP_GRIP = (0, 0.035, 0.022)

HAND_HOLDER_GROUP = "shower_hand_holder"
HAND_POSE = ((-0.05, 1.55, -0.585), (12, 0, 0))   # holder seat and tilt
HAND_CENTER = (0, 0.03, 0)                        # the snap compares the middle of the hand shower

# The hose (D-058): simulated in Godot (ShowerHose) from the wall outlet's ferrule (the body glb keeps
# outlet, elbow, nut and that ferrule) to the hand shower's bottom; 1.85 m (1.5 and 1.7 m felt short in the headset).
HOSE_OUTLET = (-0.30, 0.806, -0.652)   # 8 mm inside the outlet ferrule (closed lathe, it hides the end); leaves down (-Y)
HOSE_LENGTH = 1.85
HOSE_SHADER = "assets/shaders/hose_braid.gdshader"
HAND_HOSE_END = (0, -0.105, 0)         # handheld frame: the handle's bottom; the hose leaves along -Y
HAND_SPRAY = (0, 0.115, 0.014)         # handheld frame: the spray face's middle; water leaves along +Z
RAIN_NOZZLES = (0.5, 2.592, 0.0)       # the rain head's nozzle plate; water falls along -Y
# Boxes the water vanishes on (min corner, size): floor, back wall, end walls, glass screen.
WATER_COLLIDERS = [((-3.0, -0.2, -3.0), (6.0, 0.2, 6.0)), ((-1.5, 0.0, -0.9), (3.0, 2.6, 0.2)),
                   ((-1.6, 0.0, -0.8), (0.2, 2.6, 1.6)), ((1.4, 0.0, -0.8), (0.2, 2.6, 1.6)),
                   ((-0.40, 0.0, 0.694), (1.786, 2.0, 0.012))]

DOC = ("Walk-in shower 2.80 x 1.40 m with a frameless glass screen (entry at the -X end), rain head, slide rail, "
       "wall mixer and a marble shelf. Origin = footprint center on the floor; the back wall is at z -0.70, +Z "
       "points into the room. The flow lever turns ±90 degrees (+ rain head, - hand shower) and clicks into off and "
       "both ends; the thermostat dial turns ±120 degrees with a click at 38 °C (indicator up). The hand shower sits "
       "in its holder until grabbed; put it back near the holder and it clicks in again. Its hose hangs from the wall "
       "outlet (ShowerHose, 1.85 m); the flow lever runs water from the hand shower or the rain head (ShowerWater).")
HANDHELD_DOC = ("Hand shower 0.108 x 0.274 x 0.033 m, 0.35 kg. Origin = holder seat; handle along +Y, spray along +Z. "
                "Pickable; it starts in (and dropped near) a holder (a Marker3D in the 'shower_hand_holder' group), "
                "it sits there frozen until grabbed. HoseEnd: where the shower's hose attaches; SprayFace: where water leaves.")


def parts_material() -> TextResource:
    """shower_parts.tres: the baked ShowerParts set (albedo, ORM, normal), as Godot imports a glTF material."""
    return TextResource(
        '[gd_resource type="StandardMaterial3D" format=3]\n\n'
        f'[ext_resource type="Texture2D" path="res://{PARTS_TEX["albedo"]}" id="1_albedo"]\n'
        f'[ext_resource type="Texture2D" path="res://{PARTS_TEX["orm"]}" id="2_orm"]\n'
        f'[ext_resource type="Texture2D" path="res://{PARTS_TEX["normal"]}" id="3_normal"]\n\n'
        "[resource]\n"
        'resource_name = "ShowerParts"\n'
        "cull_mode = 2\n"
        'albedo_texture = ExtResource("1_albedo")\n'
        "metallic = 1.0\n"
        'metallic_texture = ExtResource("2_orm")\n'
        "metallic_texture_channel = 2\n"
        'roughness_texture = ExtResource("2_orm")\n'
        "roughness_texture_channel = 1\n"
        "normal_enabled = true\n"
        'normal_texture = ExtResource("3_normal")\n'
        "ao_enabled = true\n"
        'ao_texture = ExtResource("2_orm")\n'
        "ao_texture_channel = 0\n")


def shower() -> Scene:
    s = Scene("Shower", DOC)
    s.instance("Body", BODY)
    glass = s.sub("ShaderMaterial", "ShaderMaterial_glass", {"resource_local_to_scene": True, "render_priority": 0,
                                                             "shader": s.ext(GLASS_SHADER)})
    s.node("GlassMaterial", "Node", props={"script": s.ext("named_material_override"), "root": ref("Body"),
                                           "material_name": "shower_glass", "material": glass,
                                           "cast_shadow": 0, "layers": RENDER_UNREFLECTED})
    s.node("Reflection", "Node3D", props={
        "position": GLASS_CENTER, "script": s.ext("planar_reflection"),
        "size": raw("Vector2(%g, %g)" % GLASS_SIZE), "materials": [glass], "two_sided": True,
        "pixels_per_meter": GLASS_PPM, "msaa": False, "reach": GLASS_REACH})
    flow = s.hinged_door(
        group="FlowLever", glb=FLOW, hinge_position=FLOW_PIVOT, hinge_rotation=WALL_AXIS,
        limit_min=-90.0, open_max=90.0,
        boxes=[("LeverCollision", (0, -0.0315, 0.015), (0.047, 0.110, 0.030))],
        grip=glb_node_position(FLOW, "HandleGrip") or (0, -0.052, 0.027), grab_radius=0.035,
        grab_shape="SphereShape3D_mixer", shape_prefix="flow", stop=None, no_swing=True)
    s.sound("FlowClick", "sfx/vent_latch", parent=flow.group, position=FLOW_PIVOT, volume_db=-16.0)
    s.node("Detents", "Node", parent=flow.group, props={
        "script": s.ext("hinge_detents"), "hinge": ref(flow.joint),
        "detents": raw("PackedFloat32Array(%s)" % ", ".join(f"{d:g}" for d in FLOW_DETENTS)),
        "capture": 15.0, "click": ref(f"{flow.group}/FlowClick")})
    temp = s.hinged_door(
        group="TempDial", glb=TEMP, hinge_position=TEMP_PIVOT, hinge_rotation=WALL_AXIS,
        limit_min=-TEMP_RANGE, open_max=TEMP_RANGE,
        boxes=[("DialCollision", (0, 0, 0.020), (0.060, 0.060, 0.040))],
        grip=TEMP_GRIP, grab_radius=0.035, grab_shape="SphereShape3D_mixer", shape_prefix="temp",
        stop=Sound("sfx/button_click", props={"volume_db": -20.0}), stop_props={"min_speed": 10.0}, no_swing=True)
    s.sound("TempClick", "sfx/button_click", parent=temp.group, position=TEMP_PIVOT, volume_db=-14.0)
    s.node("Detents", "Node", parent=temp.group, props={
        "script": s.ext("hinge_detents"), "hinge": ref(temp.joint), "detents": raw("PackedFloat32Array(0)"),
        "capture": 6.0, "click": ref(f"{temp.group}/TempClick")})

    position, rotation = HAND_POSE
    s.node("HandShowerHolder", "Marker3D", groups=[HAND_HOLDER_GROUP], position=position, rotation_degrees=rotation)
    s.instance("HandShower", HANDHELD_TSCN, position=position, rotation=rotation)

    s.node("HoseOutlet", "Marker3D", position=HOSE_OUTLET)
    braid = s.sub("ShaderMaterial", "ShaderMaterial_hose", {"render_priority": 0, "shader": s.ext(HOSE_SHADER)})
    chrome = s.sub("StandardMaterial3D", "StandardMaterial3D_ferrule", {
        "albedo_color": color(0.62, 0.63, 0.65), "metallic": 1.0, "roughness": 0.2})
    s.node("Hose", "Node3D", props={
        "script": s.ext("shower_hose"), "start": ref("HoseOutlet"), "end": ref("HandShower/HoseEnd"),
        "body": ref("HandShower"), "length": HOSE_LENGTH, "material": braid, "ferrule_material": chrome})
    s.node("RainNozzles", "Marker3D", position=RAIN_NOZZLES)
    boxes = ", ".join("AABB(%g, %g, %g, %g, %g, %g)" % (*lo, *size) for lo, size in WATER_COLLIDERS)
    s.node("Water", "Node", props={
        "script": s.ext("shower_water"), "flow": ref(flow.joint), "hand_nozzle": ref("HandShower/SprayFace"),
        "rain_nozzle": ref("RainNozzles"), "colliders": raw(f"Array[AABB]([{boxes}])")})
    return s


def handheld() -> Scene:
    s = pickable_scene(
        "HandShower", HANDHELD, mass=0.35, doc=HANDHELD_DOC,
        boxes=[("HandleCollision", (0, -0.02, 0), (0.033, 0.18, 0.033)),
               ("HeadCollision", (0, 0.115, 0), (0.108, 0.108, 0.026))],
        sound="sfx/can_hit", friction=0.7, bounce=0.1, release_unfrozen=True,
        holder=HAND_HOLDER_GROUP, holder_props={"center": HAND_CENTER, "snap_sound": ref("SnapSound")})
    s.sound("SnapSound", "sfx/vent_latch", volume_db=-12.0)
    s.node("HoseEnd", "Marker3D", position=HAND_HOSE_END)
    s.node("SprayFace", "Marker3D", position=HAND_SPRAY)
    return s


def write_imports() -> int:
    """The shared ShowerParts textures (from one part glb) and the part glbs' .import files."""
    count = 0
    images = glb_images(FLOW)
    for kind, path in PARTS_TEX.items():
        count += write_new_file(path, images[f"shower_parts_{kind}"])
        normal = kind == "normal"
        count += write_new_file(path + ".import", TEXTURE_IMPORT.format(
            path=path, normal_map=1 if normal else 0, roughness_mode=1 if normal else 0))
    for glb in (FLOW, TEMP, HANDHELD):
        count += write_new_file(glb + ".import", glb_import_text(glb, {"ShowerParts": PARTS_MAT}, embedded_images=0))
    return count


def scenes() -> dict:
    return {f"{D}/shower.tscn": shower(), HANDHELD_TSCN: handheld(), PARTS_MAT: parts_material()}


if __name__ == "__main__":
    if "--imports" in sys.argv[1:]:
        print(f"{write_imports()} file(s) written")
        sys.exit(0)
    main(scenes)
