"""Entrance door scene: assets/props/door_entrance/door_entrance.tscn (frame glb + hinged leaf glb with levers and
deadbolt thumb-turn, built by blender/props/door_entrance/).

    python tools/props/door_entrance.py [--check]
"""

from prop_scenes import HINGE_LEFT, Scene, Sound, main

GLB = "assets/props/door_entrance/door_entrance_{}.glb"
DOC = ("Apartment entrance door: steel security frame and 65 mm leaf (0.84 x 2.06 m) for a 0.90 x 2.10 m opening in a "
       "0.20 m wall. Origin = bottom center of the opening on the wall's center plane; +Z = apartment side, the leaf "
       "opens toward it (0..100 degrees), hinge on the -X jamb. Levers at 1.1 m on both faces, deadbolt thumb-turn and "
       "smart-lock LED (material door_entrance_lock_led) on the apartment face, unit plate 4417 outside. Heavy: it "
       "swings on less and the latch catches it within 3 degrees. Built by blender/props/door_entrance/ (D-026).")

# Leaf frame = the leaf glb's origin on the hinge axis (frame coordinates (-0.4235, 0, 0.124)).
LEAF_BOX = ("LeafCollision", (0.423, 1.0423, -0.0465), (0.843, 2.0595, 0.065))
GRIPS = {"Back": (0.7095, 1.10, 0.048), "Front": (0.7095, 1.10, -0.141)}  # apartment side, corridor side
HARDWARE = [  # (node, glb part, leaf-frame position)
    ("LeverApartment", "lever_apartment", (0.7845, 1.10, -0.014)),
    ("LeverCorridor", "lever_corridor", (0.7845, 1.10, -0.079)),
    ("ThumbTurn", "thumbturn", (0.7845, 1.30, 0.012)),
]


def scenes() -> dict[str, Scene]:
    s = Scene("DoorEntrance", DOC)
    s.instance("Frame", GLB.format("frame"))
    joint = s.hinged_door(
        glb=GLB.format("leaf"), model_name="Model", hinge_position=(-0.4235, 0, 0.124), hinge_rotation=HINGE_LEFT,
        open_max=100.0, boxes=[LEAF_BOX], grips=GRIPS,
        stop=Sound("sfx/door_bump", props={"pitch_scale": 0.75}),
        swing={"friction": 110.0, "damping": 1.2, "bounce": 0.12, "latch_angle": 3.0, "latch_pull": 260.0})
    for name, part, position in HARDWARE:
        s.instance(name, GLB.format(part), parent=joint.body, position=position)
    return {"assets/props/door_entrance/door_entrance.tscn": s}


if __name__ == "__main__":
    main(scenes)
