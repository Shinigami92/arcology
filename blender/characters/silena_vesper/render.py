"""Render: the arms and the body in test poses (test_poses.py). Not saved into the .blend.

  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/render.py -- [--quick] [--out DIR] [--suffix NAME] [--shots fp_down,body_fp,...] [--sides Left,Right] [--size PX]

Body shots (`BODY_SHOTS`, after bake.py: meshes `Body`, `HeadMesh`, `Collar`): `fp30/50/70`
(first person: the camera at her eyes pitched down that far, a wide lens, the head
renders shadows only as in Godot), `armpit_fp` (the same pose from outside: where the
upper arm meets the coat), `front`, `side`, `back`, `q34` (full body), `stride`,
`stride_front`, `stride_q34` (a 30 cm stride), `belt` and `belt_low` (close on the belt's
items, from above and below), `armhole` and `armhole_back` (her left arm raised to
shoulder height).

Views per shot (`SHOTS`): `fp` (first person: the camera at her eyes, looking at the
hand), `side` (the whole arm from outside), `cuff` (close on the wrist and the
cuff), `crook` (into the bent elbow), `front`, `shoulder` (from her eyes toward
the shoulder: the armhole's closing dome). Before bake.py the meshes are
`GloveLeft` + `SleeveLeft`; after it `ArmLeft` / `ArmRight`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from silena_vesper_common import NAME, SCRATCH, armature  # noqa: E402
import test_poses  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

SHOTS = {  # test pose (test_poses.TESTS) -> views
    "fp_down": ("fp", "side", "cuff"),
    "fp_down_grip": ("fp", "cuff"),
    "fp_up": ("fp", "side"),
    "roll_p90": ("fp", "cuff"),
    "roll_m90": ("fp", "cuff"),
    "flex_p60": ("cuff",),
    "flex_m60": ("cuff",),
    "elbow0": ("side",),
    "elbow90": ("side", "crook"),
    "elbow145": ("side", "crook"),
    "rest": ("side", "front", "shoulder"),
}


BODY_SHOTS = {
    "body_fp": ("fp30", "fp50", "fp70", "armpit_fp"),
    "body_rest": ("front", "side", "back", "belt", "belt_low", "q34"),
    "body_stride": ("stride", "stride_front", "stride_q34"),
    "body_arm_raise": ("armhole", "armhole_back"),
}
BODY_MESHES = ("Body", "HeadMesh", "Collar")


def body_camera(arm, view):
    """(location, target, lens) of a body view."""
    import math

    eye = Vector(arm["eye"])
    if view.startswith("fp"):
        p = math.radians(float(view[2:]))
        return eye, eye + Vector((0.0, -math.cos(p), -math.sin(p))), 15.0
    views = {
        "front": ((0.0, -4.4, 1.05), (0.0, 0.0, 0.97), 45.0),
        "side": ((4.4, -0.15, 1.05), (0.0, 0.0, 0.97), 45.0),
        "back": ((0.0, 4.4, 1.05), (0.0, 0.0, 0.97), 45.0),
        "q34": ((2.6, -3.4, 1.55), (0.0, 0.0, 1.0), 45.0),
        "belt": ((0.10, -0.62, 1.20), (-0.01, -0.10, 0.93), 50.0),
        "belt_low": ((0.18, -0.55, 0.62), (0.0, -0.10, 0.92), 50.0),
        "armpit_fp": ((0.55, -0.55, 1.30), (0.15, -0.08, 1.45), 45.0),
        "stride": ((3.4, -0.6, 0.85), (0.0, -0.02, 0.62), 45.0),
        "stride_front": ((0.4, -3.4, 0.85), (0.0, 0.0, 0.62), 45.0),
        "stride_q34": ((2.4, -2.6, 1.1), (0.0, 0.0, 0.7), 45.0),
        "armhole": ((0.75, -0.55, 1.75), (0.22, -0.02, 1.52), 50.0),
        "armhole_back": ((0.55, 0.75, 1.75), (0.20, 0.0, 1.50), 50.0),
    }
    loc, target, lens = views[view]
    return Vector(loc), Vector(target), lens


def body_lights(scene):
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    coll = bpy.data.collections["Studio"]

    def area(name, loc, look, size, energy, color=(1.0, 1.0, 1.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        ob = bpy.data.objects.new(name, ld)
        coll.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("Key", (1.8, -2.6, 3.0), (0.0, 0.0, 1.1), 2.2, 520.0, (1.0, 0.96, 0.9))
    area("Fill", (-2.6, -1.8, 1.6), (0.0, 0.0, 1.0), 2.5, 160.0, (0.85, 0.9, 1.0))
    area("Rim", (-0.8, 2.6, 2.6), (0.0, 0.0, 1.2), 1.6, 420.0, (0.8, 0.85, 1.0))
    area("Top", (0.0, -0.4, 3.2), (0.0, 0.0, 1.2), 1.2, 140.0)


class BackfaceCulling:
    """Godot culls back faces, Cycles doesn't: while active, the meshes' materials show
    nothing on back faces (first-person views look out through the neck's open ring)."""

    def __init__(self, meshes):
        self.mats = {m for ob in meshes for m in ob.data.materials if m is not None}

    def __enter__(self):
        for m in self.mats:
            nt = m.node_tree
            out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
            src = out.inputs["Surface"].links[0].from_socket
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            geo.name = "CULL_GEO"
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            tr.name = "CULL_TR"
            mix = nt.nodes.new("ShaderNodeMixShader")
            mix.name = "CULL_MIX"
            nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
            nt.links.new(src, mix.inputs[1])
            nt.links.new(tr.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
        return self

    def __exit__(self, *args):
        for m in self.mats:
            nt = m.node_tree
            out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
            mix = nt.nodes["CULL_MIX"]
            nt.links.new(mix.inputs[1].links[0].from_socket, out.inputs["Surface"])
            for name in ("CULL_GEO", "CULL_TR", "CULL_MIX"):
                nt.nodes.remove(nt.nodes[name])


def render_body(opt, scene, cam, arm, shots, size):
    from silena_vesper_common import SOLE_Z

    body_lights(scene)
    floor = bpy.data.objects.get("StudioFloor")
    if floor is not None:
        floor.location.z = SOLE_Z
        floor.hide_render = False
    for ob in bpy.data.objects:
        if ob.type == "MESH" and not ob.name.startswith("Studio"):
            ob.hide_render = ob.name not in BODY_MESHES
    fingers = {p: test_poses.finger_rotations(arm, p) for p in ("Open", "Grip")}
    head = bpy.data.objects["HeadMesh"]
    for shot in shots:
        info = test_poses.body_apply(arm, shot, fingers)
        for view in BODY_SHOTS[shot]:
            head.visible_camera = not view.startswith("fp")
            camera, target, lens = body_camera(arm, view)
            aim(cam, camera, target, lens)
            cam.data.clip_start = 0.02
            path = os.path.join(opt.out, f"{NAME}_body_{view}{opt.suffix}.png")
            print(f"SHOT body {shot} {view} {info}")
            if view.startswith("fp"):
                with BackfaceCulling([bpy.data.objects[n] for n in BODY_MESHES]):
                    render_still(scene, path, opt.samples, size)
            else:
                render_still(scene, path, opt.samples, size)
    head.visible_camera = True
    test_poses.reset_all(arm, {})


def camera_for(arm, side, view):
    pbs = arm.pose.bones
    sx = 1.0 if side == "Left" else -1.0
    sh, el, wr = (pbs[f"{side}{n}"].head.copy() for n in ("UpperArm", "LowerArm", "Hand"))
    eye = Vector(arm["eye"])
    lateral = Vector((sx, 0.0, 0.0))
    if view == "fp":
        target = wr + (wr - el).normalized() * 0.02 + (el - wr) * 0.25
        return eye, target, 60.0
    if view == "side":
        mid = (sh + el + wr) / 3.0
        out = (lateral * 1.0 + Vector((0.0, -0.45, 0.15))).normalized()
        return mid + out * 1.05, mid, 50.0
    if view == "cuff":
        c = wr + (el - wr).normalized() * 0.06
        axis = (el - wr).normalized()
        up = Vector((0.0, 0.0, 1.0))
        out = (up - axis * up.dot(axis)).normalized() * 0.7 + (lateral - axis * lateral.dot(axis)).normalized() * 0.7
        return c + out.normalized() * 0.32, c, 50.0
    if view == "crook":
        axis_u, axis_f = (sh - el).normalized(), (wr - el).normalized()
        inside = (axis_u + axis_f).normalized()
        out = (inside * 0.8 + lateral * 0.35 + Vector((0.0, 0.0, 0.25))).normalized()
        return el + out * 0.45, el + inside * 0.03, 50.0
    if view == "front":
        mid = (sh + el + wr) / 3.0
        return mid + Vector((sx * 0.25, -1.1, 0.1)), mid, 50.0
    if view == "shoulder":
        return eye, sh + Vector((sx * 0.01, 0.0, 0.03)), 50.0
    raise KeyError(view)


def lights(scene):
    """Studio key/fill/rim around the arm (the default studio is set up for big props)."""
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    coll = bpy.data.collections["Studio"]

    def area(name, loc, look, size, energy, color=(1.0, 1.0, 1.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        ob = bpy.data.objects.new(name, ld)
        coll.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("Key", (0.9, -1.2, 2.4), (0.0, -0.3, 1.4), 1.2, 70.0, (1.0, 0.96, 0.9))
    area("Fill", (-1.2, -0.9, 1.6), (0.0, -0.3, 1.4), 1.6, 14.0, (0.85, 0.9, 1.0))
    area("Rim", (0.2, 1.4, 2.0), (0.0, -0.3, 1.4), 0.8, 50.0, (0.8, 0.85, 1.0))
    area("Top", (0.0, -0.2, 2.7), (0.0, -0.3, 1.4), 1.0, 14.0)


def arm_objects(side):
    names = [f"Arm{side}"] if bpy.data.objects.get(f"Arm{side}") else [f"Glove{side}", f"Sleeve{side}"]
    return [bpy.data.objects[n] for n in names if bpy.data.objects.get(n)]


def main():
    opt = render_options(SCRATCH, samples=96, quick_samples=24)
    shots = (opt.value("--shots") or ",".join(list(SHOTS) + list(BODY_SHOTS))).split(",")
    body_shots = [s for s in shots if s in BODY_SHOTS]
    shots = [s for s in shots if s in SHOTS]
    size = int(opt.value("--size") or 900)
    scene = bpy.context.scene
    arm = armature()
    sides = [s for s in (opt.value("--sides") or "Left,Right").split(",") if arm_objects(s)]
    cam = studio(scene, key=10.0, fill=10.0, rim=10.0)
    lights(scene)
    for ob in bpy.data.objects:
        if ob.name in ("StudioFloor", "StudioBack"):
            ob.hide_render = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.055, 0.065, 1.0)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    fingers = {p: test_poses.finger_rotations(arm, p) for p in ("Open", "Grip")}
    for side in sides:
        show = set(arm_objects(side))
        for ob in bpy.data.objects:
            if ob.type == "MESH" and not ob.name.startswith("Studio"):
                ob.hide_render = ob not in show
        for shot in shots:
            info = test_poses.apply(arm, side, shot, fingers)
            for view in SHOTS[shot]:
                camera, target, lens = camera_for(arm, side, view)
                aim(cam, camera, target, lens)
                path = os.path.join(opt.out, f"{NAME}_{side.lower()}_{shot}_{view}{opt.suffix}.png")
                print(f"SHOT {side} {shot} {view} {info}")
                render_still(scene, path, opt.samples, size)
    test_poses.reset(arm, {})
    if body_shots and bpy.data.objects.get("Body") is not None:
        render_body(opt, scene, cam, arm, body_shots, int(opt.value("--size") or 1024))


if __name__ == "__main__":
    main()
