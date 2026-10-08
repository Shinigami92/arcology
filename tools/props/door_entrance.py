"""Entrance door scene: assets/props/door_entrance/door_entrance.tscn (frame glb + hinged leaf glb with levers and
deadbolt thumb-turn, built by blender/props/door_entrance/).

    python tools/props/door_entrance.py [--check]
"""

from prop_scenes import HINGE_LEFT, LockSpec, Scene, Sound, main

GLB = "assets/props/door_entrance/door_entrance_{}.glb"
DOC = ("Apartment entrance door: steel security frame and 65 mm leaf (0.84 x 2.06 m) for a 0.90 x 2.10 m opening in a "
       "0.20 m wall. Origin = bottom center of the opening on the wall's center plane; +Z = apartment side, the leaf "
       "opens toward it (0..100 degrees), hinge on the -X jamb. Levers at 1.1 m on both faces, deadbolt thumb-turn and "
       "smart-lock LED (material door_entrance_lock_led: cyan open, red locked) on the apartment face, unit plate 4417 outside. Twist the thumb-turn (only while closed) to lock; locked, the lever only "
       "rattles the door. The peephole at 1.55 m shows the corridor (DoorViewer). Heavy: it "
       "swings on less and the latch catches it within 3 degrees. Open, bare hands push either face and grab the "
       "free edge. Built by blender/props/door_entrance/ (D-026).")

# Leaf frame = the leaf glb's origin on the hinge axis.
HINGE = (-0.4235, 0, 0.124)
LEAF_BOX = ("LeafCollision", (0.423, 1.0423, -0.0465), (0.843, 2.0595, 0.065))
GRIPS = {"Back": (0.7095, 1.10, 0.048), "Front": (0.7095, 1.10, -0.141)}  # apartment side, corridor side
# Open, the free edge can be grabbed at any height (HingeHandPush slides this handle to the hand, D-058).
EDGE = ((0.815, 1.5, -0.0465), (0.09, 0.16, 0.165))
HARDWARE = [  # (node, glb part, leaf-frame position)
    ("LeverApartment", "lever_apartment", (0.7845, 1.10, -0.014)),
    ("LeverCorridor", "lever_corridor", (0.7845, 1.10, -0.079)),
]
# Deadbolt thumb-turn (D-058): its own hinge about the leaf normal, 0 (fin vertical, open) .. 90 degrees
# counterclockwise seen from the apartment (fin horizontal, locked), clicking into both. It sits outside the
# door's hinge (a handle under the door's leaf would swing the door) and rides the leaf on a RemoteTransform3D.
THUMBTURN = (0.7845, 1.30, 0.012)  # leaf frame, the glb's origin (axis on the lock housing's face)
TURN_BOXES = [("FinCollision", (0, 0, 0.012), (0.011, 0.042, 0.019)),
              ("DiscCollision", (0, 0, 0.0015), (0.032, 0.032, 0.004))]
TURN_GRIP = (0, 0.016, 0.014)      # the fin's upper end: twisting the hand carries it around the axis
# Door viewer (D-058): the apartment-side lens' dome (0.5 mm in front of it), and the depth to the corridor lens' dome.
PEEPHOLE = (0.423, 1.55, -0.0027)
PEEPHOLE_DEPTH = 0.0815


def scenes() -> dict[str, Scene]:
    s = Scene("DoorEntrance", DOC)
    s.instance("Frame", GLB.format("frame"))
    joint = s.hinged_door(
        glb=GLB.format("leaf"), model_name="Model", hinge_position=HINGE, hinge_rotation=HINGE_LEFT,
        open_max=100.0, boxes=[LEAF_BOX], grips=GRIPS,
        stop=Sound("sfx/door_bump", props={"pitch_scale": 0.75}),
        swing={"friction": 110.0, "damping": 1.2, "bounce": 0.12, "latch_angle": 3.0, "latch_pull": 260.0},
        hand_push=True, edge=EDGE)
    for name, part, position in HARDWARE:
        s.instance(name, GLB.format(part), parent=joint.body, position=position)

    s.node("Peephole", "Node3D", parent=joint.leaf, position=PEEPHOLE, script=s.ext("door_viewer"),
           depth=PEEPHOLE_DEPTH)

    s.door_lock(joint, HINGE, LockSpec(
        THUMBTURN, TURN_BOXES, TURN_GRIP, glb=GLB.format("thumbturn"), led_root=f"{joint.body}/Model", beeps=True,
        rattle=Sound("sfx/door_rattle", position=(0.78, 1.1, -0.05), props={"volume_db": -4.0})))
    return {"assets/props/door_entrance/door_entrance.tscn": s}


if __name__ == "__main__":
    main(scenes)
