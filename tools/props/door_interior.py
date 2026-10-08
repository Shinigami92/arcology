"""Interior door scenes (frame glb + hinged leaf glb with levers, built by blender/props/door_interior/):
assets/props/door_interior/door_interior.tscn and door_interior_bath.tscn (adds the privacy thumb-turn).

    python tools/props/door_interior.py [--check]
"""

from prop_scenes import HINGE_LEFT, LockSpec, Scene, Sound, main

GLB = "assets/props/door_interior/door_interior_{}.glb"
DOC = ("Interior door: painted frame and 40 mm leaf (0.85 x 2.07 m) for a 0.90 x 2.10 m opening in a 0.20 m wall. "
       "Origin = bottom center of the opening on the wall's center plane; the leaf opens toward +Z (0..100 degrees), "
       "hinge on the -X jamb. Levers at 1.1 m on both faces. Grab a lever to swing it; let go while moving and it "
       "swings on; the latch catches it within 3 degrees of closed. Open, bare hands push either face and grab the "
       "free edge.{} Built by blender/props/door_interior/ (D-026).")
BATH = (" Privacy thumb-turn on the +Z face (inside, the swing side): twist it (only while closed) to lock; locked, "
        "the levers only rattle the door. Coin release on the -Z face.")

# Leaf frame = the leaf glb's origin on the hinge axis at floor level (frame coordinates (-0.4265, 0, 0.1075)).
LEAF_BOX = ("LeafCollision", (0.4265, 1.042, -0.0275), (0.85, 2.066, 0.04))
GRIPS = {"Front": (0.7215, 1.10, 0.0525), "Back": (0.7215, 1.10, -0.1075)}
# Open, the free edge can be grabbed at any height (HingeHandPush slides this handle to the hand, D-058).
EDGE = ((0.82, 1.5, -0.0275), (0.09, 0.16, 0.14))
LEVERS = [("LeverFront", (0.7915, 1.10, -0.0075), None), ("LeverBack", (0.7915, 1.10, -0.0475), (180, 0, 0))]
# The glb has the turn on the -Z face; turned 180 degrees about the leaf's vertical mid-line it sits on the
# +Z (swing, bathroom) face and the coin release outside.
THUMBTURN = ((0.7915, 1.022, -0.0475), (0, 180, 0))
# Its knob (glb node ThumbTurn) turns about the axis 40 mm toward +Z, on the +Z face (D-058): the lock's hinge
# sits there, the knob's local -Z is the leaf's +Z. Blade 18 mm out of the face, 38 mm tall.
HINGE = (-0.4265, 0, 0.1075)
BATH_LOCK = LockSpec(
    (0.7915, 1.022, -0.0075), [("BladeCollision", (0, 0, 0.009), (0.012, 0.04, 0.018))], (0, 0.015, 0.011),
    visual="HingeOrigin/InteractableHinge/Leaf/DoorBody/ThumbTurn/Thumbturn/ThumbTurn", visual_axis=(0, 0, -1),
    bolt=Sound("sfx/deadbolt", props={"volume_db": -14.0, "pitch_scale": 1.6}),
    rattle=Sound("sfx/door_rattle", position=(0.79, 1.1, -0.03), props={"volume_db": -6.0, "pitch_scale": 1.2}))


def door(root: str, bath: bool) -> Scene:
    s = Scene(root, DOC.format(BATH if bath else ""))
    s.instance("Frame", GLB.format("frame"))
    joint = s.hinged_door(
        glb=GLB.format("leaf"), model_name="Model", hinge_position=HINGE, hinge_rotation=HINGE_LEFT,
        open_max=100.0, boxes=[LEAF_BOX], grips=GRIPS, stop=Sound("sfx/door_bump"),
        swing={"friction": 60.0, "damping": 0.8, "bounce": 0.25, "latch_angle": 3.0, "latch_pull": 200.0},
        hand_push=True, edge=EDGE)
    for name, position, rotation in LEVERS:
        s.instance(name, GLB.format("lever"), parent=joint.body, position=position, rotation=rotation)
    if bath:
        s.instance("ThumbTurn", GLB.format("thumbturn"), parent=joint.body, position=THUMBTURN[0], rotation=THUMBTURN[1])
        s.door_lock(joint, HINGE, BATH_LOCK)
    return s


def scenes() -> dict[str, Scene]:
    return {"assets/props/door_interior/door_interior.tscn": door("DoorInterior", False),
            "assets/props/door_interior/door_interior_bath.tscn": door("DoorInteriorBath", True)}


if __name__ == "__main__":
    main(scenes)
