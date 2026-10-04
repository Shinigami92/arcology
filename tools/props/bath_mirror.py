"""Bathroom mirror scenes (built by blender/props/bath_mirror/):

- assets/props/bath_mirror/bath_mirror.tscn: backlit mirror; a touch sensor toggles the halo
  and a small warm light on the vanity top.
- assets/props/bath_mirror_magnifier/bath_mirror_magnifier.tscn: wall bracket with a
  swing-arm magnifying mirror on a vertical hinge.

Numbers from the artist's report (Godot prop-local, front +Z).

    python tools/props/bath_mirror.py [--check]
"""

from prop_scenes import HINGE_LEFT, RENDER_UNREFLECTED, OmniLight, Scene, Sound, glb_node_position, main, raw, ref

MIRROR_GLB = "assets/props/bath_mirror/bath_mirror.glb"
BRACKET_GLB = "assets/props/bath_mirror_magnifier/bath_mirror_magnifier_bracket.glb"
ARM_GLB = "assets/props/bath_mirror_magnifier/bath_mirror_magnifier_arm.glb"
MIRROR_SHADER = "assets/shaders/planar_mirror.gdshader"
# The glass (blender/props/bath_mirror: frame 1.20 x 0.90 inside an 8 mm lip, surface 55.3 mm off the wall):
# center and size of the live reflection (D-049).
GLASS_CENTER = (0, 0.45, 0.0553)
# How far the reflection reaches (m): the bathroom and the hallway outside its door.
MIRROR_REACH = 5.0
GLASS_SIZE = (1.184, 0.884)
# The magnifier's glass: a 189 mm disc on the arm, 6.2 mm in front of its pivot line (arm glb).
MAG_GLASS_CENTER = (0.315, 0, 0.0062)
MAG_GLASS_SIZE = 0.189
# How much it enlarges (a 5x cosmetic mirror at arm's length reads about like this) and how far it
# reaches (the face in front of it and the bathroom behind).
MAG_ZOOM = 3.0
MAG_REACH = 3.0

# The halo ring and its diffusers: an additive glow (black + emission adds nothing where the
# texture is dark), no specular or ambient, so only the emission shows; no shadows.
LED_PROPS = raw('{"blend_mode": 1, "specular_mode": 2, "disable_ambient_light": true, "metallic": 0.0, '
                '"roughness": 1.0}')
TOUCH = (0, 0.070, 0.0556)          # touch sensor center
TOUCH_FIELD = (0.05, 0.05, 0.03)    # press box

MIRROR_DOC = ("Backlit bathroom mirror, frame 1.20 x 0.90 m, 35 mm off the wall, with a warm LED halo on the wall "
              "around it. Origin = bottom center of its back, on the wall plane; front +Z. Touch the round sensor "
              "near the bottom of the glass to switch the halo and the vanity light (on by default; the sensor ring "
              "stays dimly lit when off). The glass is a live mirror, one reflection per eye while it's in view (D-049).")
MAGNIFIER_DOC = ("Swing-arm magnifying mirror on a wall bracket. Origin = wall plane behind the pivot, at pivot height; "
                 "front +Z. Folded flat along +X at 0 degrees; grab the head's rim and swing it out (0..170 degrees "
                 "about the vertical pivot 40 mm off the wall, 90 = straight into the room); it stays where it's left. "
                 "The glass is a live mirror that enlarges (D-049).")


def mirror() -> Scene:
    s = Scene("BathMirror", MIRROR_DOC)
    s.instance("Model", MIRROR_GLB)
    glass = s.sub("ShaderMaterial", "ShaderMaterial_mirror", {"resource_local_to_scene": True,
                                                              "shader": s.ext(MIRROR_SHADER)})
    s.node("GlassMaterial", "Node", props={"script": s.ext("named_material_override"), "root": ref("Model"),
                                           "material_name": "mirror_glass", "material": glass,
                                           "layers": RENDER_UNREFLECTED})
    s.node("Reflection", "Node3D", props={"position": GLASS_CENTER, "script": s.ext("planar_reflection"),
                                          "size": raw("Vector2(%g, %g)" % GLASS_SIZE), "materials": [glass],
                                          "reach": MIRROR_REACH})
    s.node("HaloMaterial", "Node", props={"script": s.ext("named_material_override"), "root": ref("Model"),
                                          "material_name": "mirror_led", "properties": LED_PROPS, "cast_shadow": 0})
    # Stands in for the halo's spill on the vanity top (no GI): small, warm, unshadowed.
    s.omni_light(OmniLight((0, -0.15, 0.16), energy=0.6, range=1.1, color=(1, 0.77, 0.56, 1), name="VanityLight"))
    s.light_switch("Halo", position=TOUCH, lights=["VanityLight"], emissive_root="Model", material_name="mirror_led",
                   box=TOUCH_FIELD, displacement=(0, 0, 0),
                   click=Sound("sfx/button_click", name="TouchClick", props={"volume_db": -16.0}),
                   switch_props={"indicator_material": "mirror_touch_led", "indicator_energy_off": 0.25})
    return s


def magnifier() -> Scene:
    s = Scene("BathMirrorMagnifier", MAGNIFIER_DOC)
    s.instance("Bracket", BRACKET_GLB)
    grip = glb_node_position(ARM_GLB, "HandleGrip") or (0.414, 0, 0)
    joint = s.hinged_door(
        glb=ARM_GLB, model_name="Arm", hinge_position=(0, 0, 0.04), hinge_rotation=HINGE_LEFT, open_max=170.0,
        boxes=[("HeadCollision", (0.315, 0, -0.0035), (0.204, 0.204, 0.025)),
               ("ArmCollision", (0.110, 0, 0), (0.200, 0.013, 0.013))],
        grip=grip, grab_radius=0.05,
        stop=Sound("sfx/vent_latch", props={"volume_db": -14.0}),
        stop_props={"min_speed": 15.0, "full_volume_speed": 120.0},
        no_swing=True)
    glass = s.sub("ShaderMaterial", "ShaderMaterial_mirror", {"resource_local_to_scene": True,
                                                              "shader": s.ext(MIRROR_SHADER)})
    s.node("GlassMaterial", "Node", props={"script": s.ext("named_material_override"), "root": ref(f"{joint.body}/Arm"),
                                           "material_name": "mirror_glass", "material": glass,
                                           "layers": RENDER_UNREFLECTED})
    # Rides on the arm (its transform follows the swing every frame).
    s.node("Reflection", "Node3D", parent=joint.body, props={
        "position": MAG_GLASS_CENTER, "script": s.ext("planar_reflection"),
        "size": raw("Vector2(%g, %g)" % (MAG_GLASS_SIZE, MAG_GLASS_SIZE)), "materials": [glass],
        "reach": MAG_REACH, "magnification": MAG_ZOOM})
    return s


def scenes() -> dict[str, Scene]:
    return {"assets/props/bath_mirror/bath_mirror.tscn": mirror(),
            "assets/props/bath_mirror_magnifier/bath_mirror_magnifier.tscn": magnifier()}


if __name__ == "__main__":
    main(scenes)
