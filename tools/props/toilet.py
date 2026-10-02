"""Toilet scenes (built by blender/props/toilet/):

- assets/props/toilet/toilet.tscn: wall-hung toilet in front of a marble-topped box (body glb
  with its collision), seat and lid on one hinge axis (HingeCoupling keeps them in order),
  dual flush buttons, a roll holder with a roll;
- assets/props/toilet/toilet_roll.tscn: the roll, a pickable that sits on the holder.

Numbers from the artist's report (Godot prop-local: origin on the floor at the wall plane on
the bowl's axis, front +Z). Seat and lid boxes and grips are relative to the hinge axis.

    python tools/props/toilet.py [--check]
"""

from prop_scenes import Scene, Sound, glb_node_position, main, pickable_scene, ref

D = "assets/props/toilet"
BODY, SEAT, LID = f"{D}/toilet_body.glb", f"{D}/toilet_seat.glb", f"{D}/toilet_lid.glb"
FLUSH_SMALL, FLUSH_LARGE, ROLL = f"{D}/toilet_flush_small.glb", f"{D}/toilet_flush_large.glb", f"{D}/toilet_roll.glb"
ROLL_TSCN = f"{D}/toilet_roll.tscn"

# Seat and lid turn about +X through HINGE; they open by negative rotation about +X (the front
# lifts toward the wall). The HingeOrigin turned 180 degrees about Y has its local X along -X,
# so the XR Tools hinge opens toward positive angles like every other hinge (0 = closed).
HINGE = (0, 0.425, 0.275)
HINGE_ROTATION = (0, 180, 0)
OPEN = 97.0
# Soft-close: below LATCH degrees the hinge sinks shut on its own like a damped lid under gravity
# (about 24 degrees/s, ~3.5 s from 80); above it, it rests against the box. No bounce.
SOFT_CLOSE = {"friction": 120.0, "damping": 2.5, "bounce": 0.0, "max_speed": 240.0, "latch_angle": 80.0,
              "latch_pull": 60.0}
# The seat's grip lies under the closed lid: it can be grabbed once the lid is open this far.
SEAT_UNLOCK = 60.0
STOP = Sound("sfx/drawer_bump", props={"volume_db": -10.0})
STOP_PROPS = {"min_speed": 30.0}   # a soft-close arrives at ~24 degrees/s: silent; slammed by hand: a knock

FLUSH_TRAVEL = 0.004
FLUSH_DEPTH = 0.016                # press field depth, 6 mm in front of the button face
FLUSH = [  # name, glb, origin (face center), button size (x, y), sound
    ("FlushSmall", FLUSH_SMALL, (-0.074, 1.100, 0.2105), (0.070, 0.130), "sfx/toilet_flush_short"),
    ("FlushLarge", FLUSH_LARGE, (0.0365, 1.100, 0.2105), (0.145, 0.130), "sfx/toilet_flush_full"),
]
FLUSH_SOUND_AT = (0, 0.35, 0.42)   # the bowl

ROLL_HOLDER_GROUP = "toilet_roll_holder"
ROLL_POSE = ((0.323, 0.6846, 0.272), (0, 0, -90))   # origin (bottom center) and rotation on the bar
ROLL_CENTER = (0, 0.049, 0)

DOC = ("Wall-hung toilet in front of a 1.20 x 1.25 x 0.20 m box with a marble shelf (top 1.25 m). Origin = floor at "
       "the wall plane, on the bowl's axis; front +Z. Lid and seat lift by their front edges (0..97 degrees, one axis): "
       "the seat's grip is under the lid, so it can be grabbed once the lid is open past 60 degrees, it can't rise past "
       "the lid, and the lid can't close while the seat is up. Both soft-close: let go below 80 degrees and they sink "
       "shut slowly; above, they rest open. Press the small or large flush button on the plate (one flush at a time). "
       "The roll sits on the holder until grabbed; put it back near the bar and it hangs again.")
ROLL_DOC = ("Toilet roll, 0.115 m across, 0.098 m long, 0.13 kg. Origin = bottom center, standing upright. Pickable; "
            "it starts on (and dropped near) a holder (a Marker3D in the 'toilet_roll_holder' group), it sits there "
            "frozen until grabbed.")


def toilet() -> Scene:
    s = Scene("Toilet", DOC)
    s.instance("Body", BODY)
    lid = s.hinged_door(
        group="Lid", glb=LID, hinge_position=HINGE, hinge_rotation=HINGE_ROTATION, open_max=OPEN,
        boxes=[("LidCollision", (0, 0.004, 0.2317), (0.356, 0.027, 0.4825))],
        grip=glb_node_position(LID, "HandleGrip") or (0, 0.006, 0.469), grab_radius=0.05, shape_prefix="lid",
        stop=STOP, stop_props=STOP_PROPS, swing=SOFT_CLOSE)
    seat = s.hinged_door(
        group="Seat", glb=SEAT, hinge_position=HINGE, hinge_rotation=HINGE_ROTATION, open_max=OPEN,
        boxes=[("SeatCollision", (0, -0.0078, 0.2307), (0.354, 0.0345, 0.4805))],
        grip=glb_node_position(SEAT, "HandleGrip") or (0, -0.0133, 0.467), grab_radius=0.05, shape_prefix="seat",
        stop=STOP, stop_props=STOP_PROPS, swing=SOFT_CLOSE)
    s.node("Coupling", "Node", props={"script": s.ext("hinge_coupling"), "outer": ref(lid.joint),
                                      "inner": ref(seat.joint), "inner_handles": ref(seat.leaf),
                                      "unlock_angle": SEAT_UNLOCK})

    buttons = {}
    for name, glb, origin, (w, h), _ in FLUSH:
        buttons[name] = s.area_button(name, position=origin, box=(w, h, FLUSH_DEPTH),
                                      shape_position=(0, 0, -0.002),
                                      displacement=(0, 0, -FLUSH_TRAVEL), shape_id=f"BoxShape3D_{name}")
        s.instance("Model", glb, parent=f"{name}/Cap")
    names = [f"{name}Sound" for name, *_ in FLUSH]
    for (name, _, _, _, stream), sound in zip(FLUSH, names):
        s.sound(sound, stream, position=FLUSH_SOUND_AT, volume_db=-4.0, unit_size=3.0, max_distance=20.0,
                script=s.ext("press_sound"), button=ref(buttons[name]),
                exclusive_with=[ref(other) for other in names if other != sound])

    position, rotation = ROLL_POSE
    s.node("RollHolder", "Marker3D", groups=[ROLL_HOLDER_GROUP], position=position, rotation_degrees=rotation)
    s.instance("Roll", ROLL_TSCN, position=position, rotation=rotation)
    return s


def roll() -> Scene:
    return pickable_scene(
        "ToiletRoll", ROLL, mass=0.13, boxes=[], cylinders=[("Collision", ROLL_CENTER, 0.057, 0.098)], doc=ROLL_DOC,
        sound="sfx/pillow_thud", friction=0.9, bounce=0.05, continuous_cd=True, release_unfrozen=True,
        holder=ROLL_HOLDER_GROUP, holder_props={"center": ROLL_CENTER},
        impact={"min_speed": 0.5, "max_speed": 4.0})


def scenes() -> dict[str, Scene]:
    return {f"{D}/toilet.tscn": toilet(), ROLL_TSCN: roll()}


if __name__ == "__main__":
    main(scenes)
