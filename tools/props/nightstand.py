"""Nightstand scenes: assets/props/nightstand/{nightstand,nightstand_square}.tscn.

Body glb, a sliding drawer glb, a table lamp glb with an unshadowed bulb light and a
fingertip lamp switch. Drawer boxes and grip are in the drawer's frame.

    python tools/props/nightstand.py [--check]
"""

from prop_scenes import OmniLight, Scene, Sound, main

DOC = ("{name} 0.45 x 0.40 x 0.55 m with a table lamp on top. Origin = bottom center, front faces +Z. The drawer slides "
       "out 0.28 m by its pull, slides on after release and soft-closes; small things fit inside. Press {switch} to "
       "switch the lamp.")

VARIANTS = {
    "": dict(
        name="Nightstand", switch="the push button on the lamp base",
        drawer_origin=(0, 0.38, 0.2), grip=(0, 0.073, 0.031),
        drawer_boxes=[("FrontCollision", (0, 0.073, -0.009), (0.41, 0.146, 0.018)),
                      ("FloorCollision", (0, 0.008, -0.189), (0.368, 0.008, 0.342)),
                      ("WallLeft", (-0.189, 0.064, -0.194), (0.01, 0.12, 0.352)),
                      ("WallRight", (0.189, 0.064, -0.194), (0.01, 0.12, 0.352)),
                      ("WallBack", (0, 0.062, -0.365), (0.368, 0.116, 0.01)),
                      ("PullCollision", (0, 0.073, 0.018), (0.134, 0.011, 0.036))],
        lamp=(0.085, 0.55, -0.045), bulb=(0.085, 0.866, -0.045), switch_pos=(0.085, 0.572, -0.002)),
    "_square": dict(
        name="Square-leg nightstand (kept for other apartments)", switch="the inline rocker on the cord behind the lamp",
        drawer_origin=(0, 0.376, 0.2), grip=(0, 0.0765, 0.03),
        drawer_boxes=[("FrontCollision", (0, 0.0765, -0.009), (0.408, 0.153, 0.018)),
                      ("FloorCollision", (0, 0.014, -0.188), (0.38, 0.008, 0.34)),
                      ("WallLeft", (-0.184, 0.074, -0.188), (0.012, 0.112, 0.34)),
                      ("WallRight", (0.184, 0.074, -0.188), (0.012, 0.112, 0.34)),
                      ("WallFront", (0, 0.074, -0.024), (0.38, 0.112, 0.012)),
                      ("WallBack", (0, 0.074, -0.352), (0.38, 0.112, 0.012)),
                      ("PullCollision", (0, 0.0765, 0.0175), (0.16, 0.01, 0.035))],
        lamp=(0, 0.55, -0.07), bulb=(0, 0.855, -0.07), switch_pos=(0, 0.556, -0.175)),
}


def nightstand(tag: str, v: dict) -> Scene:
    body, drawer, lamp = (f"assets/props/nightstand/{n}{tag}.glb" for n in ("nightstand_body", "nightstand_drawer", "table_lamp"))
    # ext_resource order and ids as committed (the hinge script is listed but unused)
    s = Scene("Nightstand", DOC.format(name=v["name"], switch=v["switch"]), exts=[
        (body, "body"), (drawer, "drawer"), (lamp, "lamp"), ("hinge", "h_hinge"), ("handle", "h_handle"),
        ("follower", "h_follower"), ("pass_through", "h_pass"), ("slider", "slider"), ("slider_swing", "swing"),
        ("sfx/drawer_bump", "bump"), ("area_button", "switch_button"), ("light_switch", "switch_script"),
        ("sfx/button_click", "switch_click")])
    s.instance("Body", body)
    s.sliding_drawer("Drawer", glb=drawer, origin=v["drawer_origin"], travel=0.28, boxes=v["drawer_boxes"],
                     grip=v["grip"], shape_prefix="drawer", grab_radius=0.05)
    s.instance("Lamp", lamp, position=v["lamp"])
    s.omni_light(OmniLight(v["bulb"], energy=0.45, range=1.8, color=(1, 0.72, 0.45, 1), name="LampLight"))
    s.light_switch("LampSwitch", position=v["switch_pos"], lights=["LampLight"], emissive_root="Lamp",
                   material_name="LampLight", shape_id="SphereShape3D_switch",
                   click=Sound("sfx/button_click", name="SwitchClick", props={"volume_db": -8.0}))
    return s


def scenes() -> dict[str, Scene]:
    return {f"assets/props/nightstand/nightstand{tag}.tscn": nightstand(tag, v) for tag, v in VARIANTS.items()}


if __name__ == "__main__":
    main(scenes)
