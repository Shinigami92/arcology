"""Fridge scene: assets/props/fridge/fridge.tscn (body glb + hinged door glb, built by blender/props/fridge/).

    python tools/props/fridge.py [--check]
"""

from prop_scenes import HINGE_LEFT, AlarmSpec, HingeLightSpec, OmniLight, Scene, Sound, main

DOC = ("Tall single-door fridge, cabinet 0.60 x 0.65 x 1.85 m. Origin = bottom center of the cabinet, front faces +Z, "
       "hinge on the left (-X) edge. Grab the handle to open (0..92 degrees); let go while moving and it swings on; "
       "within 15 degrees of closed the seal pulls it shut. Beeps (door display) when left open for 30 s, until closed. "
       "Interior light while open; cans stand on the shelves and in the door bins. Built by blender/props/fridge/ (D-026).")

# ext_resource order and ids as committed
EXTS = [("assets/props/fridge/fridge_body.glb", "1_body"), ("assets/props/fridge/fridge_door.glb", "2_door"),
        ("hinge", "3_hinge"), ("handle", "4_handle"), ("follower", "5_follower"), ("stop_sound", "6_stop"),
        ("blocker", "7_blocker"), ("pass_through", "8_pass"), ("hinge_swing", "9_swing"), ("hinge_light", "10_light"),
        ("sfx/fridge_close", "11_close"), ("sfx/fridge_seal", "12_seal"), ("sfx/fridge_hum", "13_hum"),
        ("open_alarm", "14_alarm"), ("sfx/fridge_alarm", "15_alarm_sound")]


def door_boxes() -> list:
    """Door frame (origin on the hinge axis): the slab, then three bins (floor, front, walls at the hinge and free side)."""
    boxes = [("SlabCollision", (0.3, 0.9675, 0.0275), (0.6, 1.755, 0.055))]
    for i, (floor_y, wall_y, wall_h) in enumerate([(0.42, 0.48, 0.12), (0.86, 0.92, 0.12), (1.36, 1.41, 0.1)], 1):
        boxes += [(f"Bin{i}Floor", (0.3, floor_y, -0.0435), (0.48, 0.012, 0.093)),
                  (f"Bin{i}Front", (0.3, wall_y, -0.084), (0.48, wall_h, 0.012)),
                  (f"Bin{i}WallHinge", (0.066, wall_y, -0.0435), (0.012, wall_h, 0.093)),
                  (f"Bin{i}WallFree", (0.534, wall_y, -0.0435), (0.012, wall_h, 0.093))]
    return boxes


def scenes() -> dict[str, Scene]:
    s = Scene("Fridge", DOC, exts=EXTS)
    s.instance("Body", "assets/props/fridge/fridge_body.glb")
    s.hinged_door(
        glb="assets/props/fridge/fridge_door.glb", model_name="Door",
        hinge_position=(-0.3, 0, 0.325), hinge_rotation=HINGE_LEFT, open_max=92.0,
        boxes=door_boxes(), grip=(0.555, 1.25, 0.1),
        stop=Sound("sfx/fridge_close", position=(-1.2, 0.5, 0)), stop_props={"min_speed": 10.0},
        open_sound=Sound("sfx/fridge_seal", position=(0.25, 1.2, 0.33), name="SealSound", props={"volume_db": -6.0}),
        light=HingeLightSpec(OmniLight((0, 1.7, 0.15), energy=0.6, range=0.9, color=(1, 0.96, 0.92, 1),
                                       attenuation=1.5, visible=False, name="InteriorLight"),
                             emissive_root="Body", emission_energy=1.5),
        alarm=AlarmSpec(Sound("sfx/fridge_alarm", position=(0.18, 1.63, 0.33), props={"volume_db": -22.0})),
        hand_push=True)
    s.sound("Hum", "sfx/fridge_hum", position=(0, 0.15, -0.3), before="InteriorLight",
            volume_db=-30.0, autoplay=True, max_distance=8.0)
    return {"assets/props/fridge/fridge.tscn": s}


if __name__ == "__main__":
    main(scenes)
