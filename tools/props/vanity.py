"""Vanity scenes (built by blender/props/vanity/):

- assets/props/vanity/vanity.tscn: floating walnut vanity with a marble top and basin (body glb
  with its collision), two drawers, the basin mixer's lever, an LED strip with a downlight;
- assets/props/vanity/vanity_soap_dispenser.tscn: the soap dispenser, a pickable on the top.

Numbers from the artist's report (Godot prop-local: origin on the floor below the back center,
wall plane z = 0, front +Z). Drawer boxes and grips in the drawer's frame (origin = front face
bottom center, closed); the lever's in its pivot frame.

    python tools/props/vanity.py [--check]
"""

from prop_scenes import Scene, Sound, color, glb_bounds, glb_node_position, main, pickable_scene

D = "assets/props/vanity"
BODY, LEVER, DISPENSER = f"{D}/vanity_body.glb", f"{D}/vanity_lever.glb", f"{D}/vanity_soap_dispenser.glb"
DISPENSER_TSCN = f"{D}/vanity_soap_dispenser.tscn"
TOP_Y = 0.860

DRAWER_TRAVEL = 0.40
DRAWER_SWING = {"soft_close": 0.05, "soft_close_pull": 1.2}


def lr(name: str, x: float, center_yz: tuple, size: tuple) -> list:
    """A left/right pair of boxes mirrored in x."""
    y, z = center_yz
    return [(f"{name}L", (-x, y, z), size), (f"{name}R", (x, y, z), size)]


DRAWERS = {
    # name: glb, origin, fallback grip, boxes
    "DrawerTop": (f"{D}/vanity_drawer_top.glb", (0, 0.625, 0.505), (0, 0.154, -0.010), [
        ("FrontCollision", (0, 0.080, -0.009), (1.386, 0.160, 0.019)),
        ("FloorFront", (0, 0.015, -0.093), (1.300, 0.015, 0.147)),
        *lr("Floor", 0.364, (0.015, -0.299), (0.571, 0.015, 0.265)),
        *lr("Side", 0.657, (0.079, -0.232), (0.014, 0.143, 0.426)),
        *lr("Back", 0.463, (0.079, -0.438), (0.374, 0.143, 0.014)),
        *lr("BackLow", 0.177, (0.036, -0.438), (0.197, 0.058, 0.014)),
        *lr("Divider", 0.283, (0.079, -0.225), (0.014, 0.143, 0.412)),
        *lr("NotchWall", 0.072, (0.036, -0.306), (0.014, 0.058, 0.279)),
        ("NotchFront", (0, 0.036, -0.173), (0.130, 0.058, 0.014)),
    ]),
    "DrawerBottom": (f"{D}/vanity_drawer_bottom.glb", (0, 0.320, 0.505), (0, 0.264, -0.010), [
        ("FrontCollision", (0, 0.135, -0.009), (1.386, 0.270, 0.019)),
        ("Floor", (0, 0.032, -0.225), (1.300, 0.015, 0.412)),
        *lr("Side", 0.657, (0.141, -0.232), (0.014, 0.233, 0.426)),
        ("Back", (0, 0.141, -0.438), (1.300, 0.233, 0.014)),
    ]),
}

# Basin mixer lever: flow only for now (lifts 0..30 degrees about local X; the temperature
# swing about Y needs a two-axis interactable). Lifting = negative rotation about +X, so the
# HingeOrigin turns 180 degrees about Y (its local X = -X) and the hinge opens toward +.
LEVER_PIVOT = (0, 1.0225, 0.072)
LEVER_LIFT = 30.0

LED_LIGHT = dict(position=(0, 0.30, 0.467), color=(1, 0.77, 0.56, 1), energy=0.6, range=0.8, angle=75.0)
DISPENSER_AT = (0.42, TOP_Y, 0.24)

DOC = ("Floating vanity 1.40 x 0.52 m, walnut drawers under a marble top (0.86 m) with an integrated basin. Origin = "
       "floor below the back center, on the wall plane; front +Z. Both drawers slide out 0.40 m by their pulls, slide "
       "on after release and soft-close; things put inside ride along. Lift the mixer lever (0..30 degrees; it stays "
       "where it's left). A warm LED strip under the cabinet lights the floor. The soap dispenser is a pickable.")
DISPENSER_DOC = ("Soap dispenser, 0.072 m across, 0.196 m tall, 0.65 kg, nozzle +Z. Origin = bottom center. Pickable.")


def lever_box() -> tuple:
    b = glb_bounds(LEVER) or ((-0.01, -0.0065, -0.0065), (0.01, 0.0142, 0.1095))
    lo, hi = b
    center = tuple(round((lo[i] + hi[i]) / 2, 4) + 0.0 for i in range(3))
    size = tuple(round(hi[i] - lo[i], 4) + 0.0 for i in range(3))
    return ("LeverCollision", center, size)


def vanity() -> Scene:
    s = Scene("Vanity", DOC)
    s.instance("Body", BODY)
    for name, (glb, origin, grip, boxes) in DRAWERS.items():
        s.sliding_drawer(name, glb=glb, origin=origin, travel=DRAWER_TRAVEL, boxes=boxes,
                         grip=glb_node_position(glb, "HandleGrip") or grip, shape_prefix=name.removeprefix("Drawer"),
                         grab_radius=0.05, swing=DRAWER_SWING)
    s.hinged_door(
        group="Lever", glb=LEVER, hinge_position=LEVER_PIVOT, hinge_rotation=(0, 180, 0), open_max=LEVER_LIFT,
        boxes=[lever_box()], grip=glb_node_position(LEVER, "HandleGrip") or (0, 0.008, 0.080),
        grab_radius=0.04, grab_shape="SphereShape3D_lever", shape_prefix="lever", stop=Sound("sfx/button_click", props={"volume_db": -20.0}),
        stop_props={"min_speed": 10.0, "full_volume_speed": 90.0}, no_swing=True)
    light = LED_LIGHT
    s.node("UnderLight", "SpotLight3D", props={
        "position": light["position"], "rotation_degrees": (-90, 0, 0), "light_color": color(*light["color"]),
        "light_energy": light["energy"], "spot_range": light["range"], "spot_angle": light["angle"]})
    s.instance("SoapDispenser", DISPENSER_TSCN, position=DISPENSER_AT)
    return s


def dispenser() -> Scene:
    return pickable_scene(
        "SoapDispenser", DISPENSER, mass=0.65, boxes=[], cylinders=[("Collision", (0, 0.098, 0), 0.036, 0.196)],
        doc=DISPENSER_DOC, sound="sfx/can_hit", friction=0.7, bounce=0.05, impact={"min_speed": 0.5})


def scenes() -> dict[str, Scene]:
    return {f"{D}/vanity.tscn": vanity(), DISPENSER_TSCN: dispenser()}


if __name__ == "__main__":
    main(scenes)
