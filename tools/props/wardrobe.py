"""Wardrobe scenes: assets/props/wardrobe/wardrobe{,_lit}.tscn and their pickables (storage box, lid, hangers).

Two hinged doors (glbs with their origin on the hinge axis), two sliding drawers,
a HangingRail with RailHanger hangers, and a storage box with a lift-off lid.
`wardrobe` is Fable's (the apartment's), `wardrobe_lit` Opus's with an LED strip (D-032).

    python tools/props/wardrobe.py [--check]
"""

from prop_scenes import HINGE_LEFT, HINGE_RIGHT, Scene, Sound, main, open_box, pickable_scene

D = "assets/props/wardrobe"
DOC = ("Two-door wardrobe{extra}, 1.50 x 0.60 x 2.10 m. Origin = bottom center, front faces +Z. Doors hinge on the outer "
       "edges and open outward (0..95 degrees) by their handles, swing on after release and catch when nearly closed. "
       "{interior} slide out 0.40 m; the {box} and its lid are pickables; the hangers can be taken off the rail and hung "
       "back. Things can be put on the shelves.")
HANGER_DOC = ("{kind}lothes hanger. Origin = where the hook rests on a rail; shoulders along X. Pickable; dropped with its "
              "hook near a HangingRail, it hangs there.")


def mirror(box: tuple) -> tuple:
    name, (x, y, z), size = box
    return name, (-x, y, z), size


VARIANTS = {
    "": dict(
        doc=DOC.format(extra="", interior="Two drawers in the right bay", box="linen box on the upper right shelf"),
        door=[("SlabCollision", (0.3735, 1.09, 0.0115), (0.747, 2.016, 0.02)),
              ("HandleCollision", (0.702, 1.2, 0.0615), (0.012, 0.5, 0.012))],
        drawers={"DrawerLower": (0.4955, 0.24, 0.23), "DrawerUpper": (0.4955, 0.503, 0.23)},
        drawer=[("FrontCollision", (0, 0.1285, -0.009), (0.467, 0.257, 0.018)),
                ("FloorCollision", (0, 0.02, -0.248), (0.444, 0.01, 0.46)),
                ("WallLeft", (-0.217, 0.1125, -0.248), (0.01, 0.175, 0.46)),
                ("WallRight", (0.217, 0.1125, -0.248), (0.01, 0.175, 0.46)),
                ("WallFront", (0, 0.1125, -0.023), (0.444, 0.175, 0.01)),
                ("WallBack", (0, 0.1125, -0.473), (0.444, 0.175, 0.01))],
        drawer_grip=(0, 0.245, 0.004),
        rail=((-0.728, 1.66, 0), (0.237, 1.66, 0)), box=(0.4955, 1.362, 0), lid=(0.4955, 1.553, 0),
        hook=(1.6725, 0), hangers=[(-0.56, "shirt_a"), (-0.46, "shirt_b"), (-0.34, "hanger"), (-0.22, "hanger")],
        # pickables
        hanger_kind="Wire c", hanger_mass=(0.05, 0.3), shirts=("a linen shirt", "a charcoal shirt"),
        hanger_boxes=[("NeckCollision", (0, -0.036, 0), (0.032, 0.081, 0.005)),
                      ("ArmsCollision", (0, -0.126, 0), (0.42, 0.102, 0.005))],
        garments=[((0, -0.413, 0), (0.42, 0.68, 0.046)), ((0, -0.413, 0), (0.42, 0.68, 0.046))],
        box_mass=1.2, box_doc="Linen storage box 0.30 x 0.22 x 0.36 m with a folded knit inside.",
        box_boxes=[("Floor", (0, 0.004, 0), (0.3, 0.008, 0.36)),
                   ("WallLeft", (-0.146, 0.114, 0), (0.008, 0.212, 0.36)),
                   ("WallRight", (0.146, 0.114, 0), (0.008, 0.212, 0.36)),
                   ("WallFront", (0, 0.114, 0.176), (0.3, 0.212, 0.008)),
                   ("WallBack", (0, 0.114, -0.176), (0.3, 0.212, 0.008))],
        lid_mass=0.35, lid_doc="Lid of the linen storage box, 0.32 x 0.04 x 0.38 m.",
        lid_boxes=[("LidTop", (0, 0.035, 0), (0.32, 0.01, 0.38)),
                   ("SkirtLeft", (-0.156, 0.015, 0), (0.008, 0.03, 0.38)),
                   ("SkirtRight", (0.156, 0.015, 0), (0.008, 0.03, 0.38)),
                   ("SkirtFront", (0, 0.015, 0.186), (0.32, 0.03, 0.008)),
                   ("SkirtBack", (0, 0.015, -0.186), (0.32, 0.03, 0.008))]),
    "_lit": dict(
        doc=DOC.format(extra=" with an LED strip (kept for other apartments)", interior="Two drawers",
                       box="storage box"),
        door=[("SlabCollision", (0.37425, 1.1, 0.011), (0.7485, 1.996, 0.02)),
              ("HandleCollision", (0.6935, 1.2, 0.053), (0.014, 0.5, 0.014))],
        drawers={"DrawerLeft": (-0.37025, 0.122, 0.262), "DrawerRight": (0.37025, 0.122, 0.262)},
        drawer=[("FrontCollision", (0, 0.1175, -0.009), (0.7155, 0.235, 0.018)),
                ("FloorCollision", (0, 0.014, -0.270), (0.6965, 0.008, 0.504)),
                ("WallLeft", (-0.3422, 0.1065, -0.270), (0.012, 0.193, 0.504)),
                ("WallRight", (0.3422, 0.1065, -0.270), (0.012, 0.193, 0.504)),
                ("WallFront", (0, 0.1065, -0.024), (0.6725, 0.193, 0.012)),
                ("WallBack", (0, 0.1065, -0.516), (0.6725, 0.193, 0.012))],
        drawer_grip=(0, 0.19, 0.018),
        rail=((-0.73, 1.735, 0.01), (0.73, 1.735, 0.01)), box=(0.41, 0.381, 0), lid=(0.41, 0.527, 0),
        hook=(1.7475, 0.01), hangers=[(-0.575, "hanger"), (-0.505, "hanger"), (-0.215, "shirt_a"),
                                      (-0.135, "shirt_b"), (0.285, "hanger"), (0.360, "hanger")],
        # pickables
        hanger_kind="C", hanger_mass=(0.12, 0.32), shirts=("an off-white shirt", "a sand shirt"),
        hanger_boxes=[("ArmsCollision", (0, -0.171, 0), (0.444, 0.167, 0.011)),
                      ("NeckCollision", (-0.01, -0.058, 0), (0.025, 0.06, 0.005))],
        garments=[((0, -0.444, 0), (0.479, 0.748, 0.039)), ((0, -0.464, 0), (0.479, 0.788, 0.039))],
        box_mass=0.8, box_doc="Fabric storage box 0.38 x 0.175 x 0.32 m with a folded scarf inside.",
        box_boxes=open_box(0.38, 0.175, 0.32, 0.005),
        lid_mass=0.2, lid_doc="Lid of the fabric storage box, 0.389 x 0.035 x 0.329 m.",
        lid_boxes=[("LidTop", (0, 0.0325, 0), (0.389, 0.005, 0.329)),
                   ("SkirtLeft", (-0.1925, 0.015, 0), (0.004, 0.03, 0.329)),
                   ("SkirtRight", (0.1925, 0.015, 0), (0.004, 0.03, 0.329)),
                   ("SkirtFront", (0, 0.015, 0.1625), (0.381, 0.03, 0.004)),
                   ("SkirtBack", (0, 0.015, -0.1625), (0.381, 0.03, 0.004))]),
}
PICKABLES = {"hanger": "p_hanger", "shirt_a": "p_shirt_a", "shirt_b": "p_shirt_b"}


def wardrobe(tag: str, v: dict) -> Scene:
    glb = {n: f"{D}/wardrobe_{n}{tag}.glb" for n in ("body", "door_left", "door_right", "drawer")}
    tscn = {n: f"{D}/wardrobe_{n}{tag}.tscn" for n in ("box", "box_lid", "hanger", "hanger_shirt_a", "hanger_shirt_b")}
    # ext_resource order and ids as committed
    s = Scene("Wardrobe", v["doc"], exts=[
        (glb["body"], "body"), (glb["door_left"], "door_left"), (glb["door_right"], "door_right"),
        ("hinge", "h_hinge"), ("handle", "h_handle"), ("follower", "h_follower"), ("pass_through", "h_pass"),
        ("stop_sound", "stop"), ("blocker", "blocker"), ("hinge_swing", "swing"), ("sfx/door_bump", "bump"),
        ("slider", "d_slider"), ("slider_swing", "d_swing"), ("sfx/drawer_bump", "d_bump"), (glb["drawer"], "d_model"),
        ("hanging_rail", "rail"), (tscn["box"], "p_box"), (tscn["box_lid"], "p_lid"), (tscn["hanger"], "p_hanger"),
        (tscn["hanger_shirt_a"], "p_shirt_a"), (tscn["hanger_shirt_b"], "p_shirt_b")])
    s.instance("Body", glb["body"])
    for side, sign, rotation in (("Left", 1, HINGE_LEFT), ("Right", -1, HINGE_RIGHT)):
        boxes = v["door"] if sign > 0 else [mirror(b) for b in v["door"]]
        s.hinged_door(
            group=f"Door{side}", glb=glb[f"door_{side.lower()}"], shape_prefix=side,
            hinge_position=(-0.75 * sign, 0, 0.3), hinge_rotation=rotation, open_max=95,
            boxes=boxes, grip=boxes[1][1],
            stop=Sound("sfx/door_bump", props={"volume_db": -8.0}),  # at the grip (the default)
            swing={"friction": 90.0, "damping": 1.2, "bounce": 0.2, "latch_angle": 4.0, "latch_pull": 220.0},
            hand_push=True)
    s.flush_subs()  # the grab sphere sits between the door and drawer boxes
    for name, origin in v["drawers"].items():
        s.sliding_drawer(name, glb=glb["drawer"], origin=origin, travel=0.4, boxes=v["drawer"], grip=v["drawer_grip"])
    s.hanging_rail("Rail", start=v["rail"][0], end=v["rail"][1])
    s.instance("StorageBox", tscn["box"], position=v["box"])
    s.instance("StorageBoxLid", tscn["box_lid"], position=v["lid"])
    hook_y, hook_z = v["hook"]
    for i, (x, kind) in enumerate(v["hangers"]):
        key = "hanger" if kind == "hanger" else f"hanger_{kind}"
        s.instance(f"Hanger{i}", tscn[key], position=(x, hook_y, hook_z), rotation=(0, 90, 0))
    return s


def pickables(tag: str, v: dict) -> dict[str, Scene]:
    def glb(name: str) -> str:
        return f"{D}/{name}{tag}.glb"

    doc = HANGER_DOC.format(kind=v["hanger_kind"])
    hanger = dict(release_unfrozen=True, hook=(0, 0, 0))
    out = {
        "wardrobe_hanger": pickable_scene("Hanger", glb("wardrobe_hanger"), mass=v["hanger_mass"][0],
                                          boxes=v["hanger_boxes"], doc=doc, sound="sfx/can_hit", **hanger),
    }
    for (letter, shirt), (center, size) in zip((("a", v["shirts"][0]), ("b", v["shirts"][1])), v["garments"]):
        out[f"wardrobe_hanger_shirt_{letter}"] = pickable_scene(
            f"HangerShirt{letter.upper()}", glb(f"wardrobe_hanger_shirt_{letter}"), mass=v["hanger_mass"][1],
            boxes=v["hanger_boxes"] + [("GarmentCollision", center, size)], doc=f"{doc} With {shirt}.", **hanger)
    out["wardrobe_box"] = pickable_scene(
        "StorageBox", glb("wardrobe_box"), mass=v["box_mass"], boxes=v["box_boxes"],
        doc=v["box_doc"] + " Origin = bottom center. Pickable; the lid lifts off.")
    out["wardrobe_box_lid"] = pickable_scene(
        "StorageBoxLid", glb("wardrobe_box_lid"), mass=v["lid_mass"], boxes=v["lid_boxes"],
        doc=v["lid_doc"] + " Origin = bottom of its skirt. Pickable.")
    return {f"{D}/{name}{tag}.tscn": scene for name, scene in out.items()}


def scenes() -> dict[str, Scene]:
    out: dict[str, Scene] = {}
    for tag, v in VARIANTS.items():
        out[f"{D}/wardrobe{tag}.tscn"] = wardrobe(tag, v)
        out.update(pickables(tag, v))
    return out


if __name__ == "__main__":
    main(scenes)
