"""Stage 4: renders of the hands in each pose. Not saved into the .blend.

  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/render.py -- [--quick] [--out DIR] [--suffix NAME] [--views fp_down,fp_palm,side] [--poses Open,Grip] [--size PX]

Views (the way Godot places the hand: the whole rig moves so the hand bone sits
where a controller would hold it):
- fp_down: first person, the camera at her eyes, the hand at chest height
  ~35 cm in front, palm down, fingers forward;
- fp_palm: first person, palm turned toward the eyes, fingers up;
- side: close view of the hand (palm down) from its outer side;
- cuff: looking into the cuff from the elbow side (a hollow or cut edge would show here).
Both hands are rendered when GloveRight exists (after bake.py).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from silena_vesper_common import NAME, POSES, SCRATCH, armature  # noqa: E402
import glove as glove_geo  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

HAND_DROP = 0.40     # palm center below the eyes
HAND_REACH = 0.35    # palm center in front of the eyes
HAND_SIDE = 0.10     # palm center beside the body's midline


def frame(across, along, palm):
    return Matrix((across, along, palm)).transposed()


def place(arm, side, view):
    """Move the armature so `side`'s palm center lands in front of the eyes."""
    arm.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    hf = glove_geo.HandFrame(arm, side)
    sx = 1.0 if side == "Left" else -1.0
    eye = Vector(arm["eye"])
    target = eye + Vector((sx * HAND_SIDE, -HAND_REACH, -HAND_DROP))
    if view == "fp_palm":
        to_eye = (eye - target).normalized()
        along = (Vector((0.0, 0.0, 1.0)) - to_eye * to_eye.z).normalized()
        palm = to_eye
        target = target + Vector((0.0, 0.05, 0.08))
    else:  # palm down, fingers forward and a little inward
        along = Vector((-sx * 0.2, -1.0, 0.35)).normalized()
        palm = Vector((0.0, 0.0, -1.0))
        palm = (palm - along * palm.dot(along)).normalized()
    across = palm.cross(along) if side == "Left" else along.cross(palm)
    rest = frame(hf.across, hf.along, hf.palm)
    want = frame(across.normalized(), along, palm)
    rot = (want @ rest.transposed()).to_4x4()
    center = hf.wrist + hf.along * hf.palm_length * 0.5
    arm.matrix_world = Matrix.Translation(target) @ rot @ Matrix.Translation(-center)
    bpy.context.view_layer.update()
    return eye, target, rot.to_3x3() @ hf.palm, rot.to_3x3() @ hf.across, rot.to_3x3() @ hf.limb.axis


def set_pose(arm, pose):
    for tr in arm.animation_data.nla_tracks:
        tr.mute = tr.name != pose
    arm.animation_data.action = None
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def lights(scene):
    """Studio key/fill/rim around the hand area (the default studio is set up for big props)."""
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

    area("Key", (0.9, -1.2, 2.4), (0.0, -0.45, 1.4), 1.0, 55.0, (1.0, 0.96, 0.9))
    area("Fill", (-1.2, -0.9, 1.6), (0.0, -0.45, 1.4), 1.6, 10.0, (0.85, 0.9, 1.0))
    area("Rim", (0.2, -1.6, 1.9), (0.0, -0.45, 1.4), 0.6, 45.0, (0.8, 0.85, 1.0))
    area("Top", (0.0, -0.2, 2.6), (0.0, -0.45, 1.4), 1.0, 12.0)


def main():
    opt = render_options(SCRATCH, samples=96, quick_samples=24)
    views = (opt.value("--views") or "fp_down,fp_palm,side,cuff").split(",")
    pose_names = (opt.value("--poses") or ",".join(POSES)).split(",")
    size = int(opt.value("--size") or 1024)
    scene = bpy.context.scene
    arm = armature()
    sides = [s for s in ("Left", "Right") if bpy.data.objects.get(f"Glove{s}")]
    cam = studio(scene, key=10.0, fill=10.0, rim=10.0)
    lights(scene)
    for ob in bpy.data.objects:
        if ob.name in ("StudioFloor", "StudioBack"):
            ob.hide_render = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.055, 0.065, 1.0)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    for side in sides:
        for ob in bpy.data.objects:
            if ob.type == "MESH" and not ob.name.startswith("Studio"):
                ob.hide_render = ob.name != f"Glove{side}"
        for pose in pose_names:
            set_pose(arm, pose)
            for view in views:
                eye, target, palm, across, up_arm = place(arm, side, "fp_palm" if view == "fp_palm" else "fp_down")
                if view in ("fp_down", "fp_palm"):
                    aim(cam, eye, target, 60.0)
                elif view == "side":
                    out = -across  # the little-finger side faces away from the body
                    aim(cam, target + out * 0.30 + Vector((0.0, 0.0, 0.06)), target, 50.0)
                elif view == "cuff":
                    aim(cam, target + up_arm * 0.40 - palm * 0.10, target + up_arm * 0.09, 50.0)
                lamp = None
                if view == "cuff":  # a little light from the camera shows the closed lining
                    ld = bpy.data.lights.new("CuffLamp", "POINT")
                    ld.energy, ld.shadow_soft_size = 1.5, 0.05
                    lamp = bpy.data.objects.new("CuffLamp", ld)
                    scene.collection.objects.link(lamp)
                    lamp.location = cam.location
                path = os.path.join(opt.out, f"{NAME}_{side.lower()}_{pose.lower()}_{view}{opt.suffix}.png")
                render_still(scene, path, opt.samples, size)
                if lamp is not None:
                    bpy.data.objects.remove(lamp)
    arm.matrix_world = Matrix.Identity(4)


if __name__ == "__main__":
    main()
