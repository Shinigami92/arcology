"""Render-only test poses of an arm (render.py, verify.py; never exported).

The arm is posed the way Godot does it: rig.two_bone_pose puts the wrist where a
controller would hold the hand and solves the elbow (minimal swing from the
rest pose), and LowerArmTwist turns by TWIST_SHARE of the hand's roll against
the forearm (rig.twist_share). The fingers take the `Open` or `Grip` pose.

Poses (`TESTS`: name -> finger pose):
- fp_down / fp_down_grip / fp_up: the wrist at chest height ~30 cm in front of the
  eyes, palm down / gripping / palm up (this IK gives a roll of ~+70 / ~-110 degrees);
- roll_p90 / roll_m90: fp_down with the hand's roll against the forearm at +-90;
- flex_p60 / flex_m60: fp_down with the wrist flexed / extended 60 degrees;
- elbow0 / elbow90 / elbow145: the upper arm at rest, the elbow at that angle;
- rest: the bind pose.
"""

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from silena_vesper_common import TWIST_SHARE
import glove as glove_geo
from arcology_blender import rig

WRIST_DROP = 0.40     # wrist below the eyes
WRIST_REACH = 0.30    # wrist in front of the eyes
WRIST_SIDE = 0.13     # wrist beside the body's midline

TESTS = {
    "fp_down": "Open", "fp_down_grip": "Grip", "fp_up": "Open",
    "roll_p90": "Open", "roll_m90": "Open", "flex_p60": "Open", "flex_m60": "Open",
    "elbow0": "Open", "elbow90": "Open", "elbow145": "Open", "rest": "Open",
}
ARM_BONES = ("UpperArm", "LowerArm", "LowerArmTwist", "Hand")


def frame(across, along, palm):
    return Matrix((across, along, palm)).transposed()


def finger_rotations(arm, pose):
    """{bone: quaternion} of the hand pose `pose` (its NLA track evaluated); leaves every
    track muted so the pose bones can be set by hand."""
    tracks = arm.animation_data.nla_tracks
    for tr in tracks:
        tr.mute = tr.name != pose
    arm.animation_data.action = None
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    out = {pb.name: pb.rotation_quaternion.copy() for pb in arm.pose.bones}
    for tr in tracks:
        tr.mute = True
    bpy.context.scene.frame_set(1)
    return out


def reset(arm, fingers):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        pb.rotation_quaternion = fingers.get(pb.name, (1.0, 0.0, 0.0, 0.0))
    for side in ("Left", "Right"):
        for b in ARM_BONES:
            arm.pose.bones[side + b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def share(arm, side):
    return rig.twist_share(arm, f"{side}LowerArm", f"{side}Hand", f"{side}LowerArmTwist", TWIST_SHARE)


def hold(arm, side, palm_up=False):
    """IK: the wrist at chest height in front of the eyes, palm down (or up), fingers forward."""
    hf = glove_geo.HandFrame(arm, side)
    sx = 1.0 if side == "Left" else -1.0
    eye = Vector(arm["eye"])
    target = eye + Vector((sx * WRIST_SIDE, -WRIST_REACH, -WRIST_DROP))
    if palm_up:
        along = Vector((-sx * 0.15, -1.0, 0.30)).normalized()
        palm = Vector((0.0, 0.0, 1.0))
    else:
        along = Vector((-sx * 0.25, -1.0, 0.10)).normalized()
        palm = Vector((0.0, 0.0, -1.0))
    palm = (palm - along * palm.dot(along)).normalized()
    across = palm.cross(along) if side == "Left" else along.cross(palm)
    rot = frame(across.normalized(), along, palm) @ frame(hf.across, hf.along, hf.palm).transposed()
    hand_rot = rot @ arm.data.bones[f"{side}Hand"].matrix_local.to_3x3()
    rig.two_bone_pose(arm, f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand", target,
                      Vector((sx * 0.7, 0.3, -1.0)), hand_rot)
    return share(arm, side)


def forearm_axis(arm, side):
    pb = arm.pose.bones[f"{side}LowerArm"]
    return (pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()


def roll(arm, side, degrees):
    """Turn the hand about the forearm until its roll against the forearm is `degrees`."""
    current = share(arm, side)
    rig.rotate_about(arm, f"{side}Hand", forearm_axis(arm, side), degrees - current)
    return share(arm, side)


def flex(arm, side, degrees):
    """Bend the wrist about the hand's across axis (index to little knuckle)."""
    hf = glove_geo.HandFrame(arm, side)
    pb = arm.pose.bones[f"{side}Hand"]
    rest = arm.data.bones[f"{side}Hand"].matrix_local.to_3x3()
    across = pb.matrix.to_3x3() @ rest.transposed() @ hf.across
    rig.rotate_about(arm, f"{side}Hand", across, degrees)
    return share(arm, side)


def bend(arm, side, degrees):
    """Elbow to `degrees` of flexion (0 = straight), the upper arm at rest."""
    b = arm.data.bones
    s, e, w = (b[f"{side}{n}"].head_local for n in ("UpperArm", "LowerArm", "Hand"))
    u, f = (e - s).normalized(), (w - e).normalized()
    rig.rotate_about(arm, f"{side}LowerArm", u.cross(f), degrees - math.degrees(u.angle(f)))


def apply(arm, side, test, fingers):
    """Pose `side`'s arm for `test` (fingers: {pose: finger_rotations}). Returns a note."""
    reset(arm, fingers[TESTS[test]])
    info = ""
    if test.startswith(("fp_", "roll", "flex")):
        r = hold(arm, side, palm_up=test == "fp_up")
        if test.startswith("roll"):
            r = roll(arm, side, 90.0 if test == "roll_p90" else -90.0)
        elif test.startswith("flex"):
            flex(arm, side, 60.0 if test == "flex_p60" else -60.0)
        info = f"roll {r:.0f}"
    elif test.startswith("elbow"):
        bend(arm, side, float(test[5:]))
        info = f"elbow {test[5:]}"
    return info


# --- whole-body test poses (stage 3) ----------------------------------------------------------
# - body_rest: the bind pose (A-pose), fingers open;
# - body_fp: both hands held at chest height in front (fp_down on each side), as Godot's
#   arm IK places them; legs at rest;
# - body_stride: her left foot 15 cm forward, the right 15 cm back (30 cm apart), feet
#   flat, the hips lowered so both feet stay on the floor (the coat's chains at rest);
# - body_arm_raise: her left arm raised to shoulder height (upper arm horizontal), 30 % of
#   it at the clavicle (SHOULDER_SHARE), the right arm in the fp hold;
# - body_belt_swing / body_belt_side: the bind pose with the belt items' bones turned
#   (BELT_SWING degrees) away from the body / sideways along the belt (BELT_SIDE, the
#   lower cuff also bent back against the upper one at the chain), as spring bones would.
BODY_TESTS = {"body_rest": "Open", "body_fp": "Open", "body_stride": "Open", "body_arm_raise": "Open",
              "body_belt_swing": "Open", "body_belt_side": "Open"}
BELT_SWING = {"BeltCuffs1": 30.0, "BeltPasskey1": 25.0}
BELT_SIDE = {"BeltCuffs1": 30.0, "BeltCuffs2": -35.0, "BeltPasskey1": 25.0}
STRIDE = 0.15
SHOULDER_SHARE = 0.3         # of an arm's elevation above the A-pose taken by the clavicle (Shoulder bone)
LEG_BONES = ("UpperLeg", "LowerLeg", "Foot")


def reset_all(arm, fingers):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        pb.rotation_quaternion = fingers.get(pb.name, (1.0, 0.0, 0.0, 0.0))
    for side in ("Left", "Right"):
        for b in ARM_BONES + LEG_BONES:
            arm.pose.bones[side + b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def step(arm, side, forward):
    """The foot `forward` meters ahead of its rest place, flat, the knee toward the front."""
    b = arm.data.bones
    ankle = b[f"{side}Foot"].head_local.copy()
    foot_rot = b[f"{side}Foot"].matrix_local.to_3x3()
    target = ankle + Vector((0.0, -forward, 0.0))
    rig.two_bone_pose(arm, f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot", target,
                      Vector((0.0, -1.0, 0.05)), foot_rot)


def body_apply(arm, test, fingers):
    reset_all(arm, fingers[BODY_TESTS[test]])
    info = ""
    if test in ("body_fp", "body_arm_raise"):
        rolls = [hold(arm, side) for side in ("Left", "Right")]
        info = "roll " + " ".join(f"{r:.0f}" for r in rolls)
    if test == "body_arm_raise":
        for b in ARM_BONES:
            arm.pose.bones["Left" + b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        up = arm.data.bones["LeftUpperArm"]
        d = (up.tail_local - up.head_local).normalized()
        ang = math.degrees(math.atan2(-d.z, d.x))
        # the clavicle takes a share of the elevation, as a real shoulder does
        rig.rotate_about(arm, "LeftShoulder", (0.0, 1.0, 0.0), -ang * SHOULDER_SHARE)
        rig.rotate_about(arm, "LeftUpperArm", (0.0, 1.0, 0.0), -ang * (1.0 - SHOULDER_SHARE))
        info = f"upper arm raised {ang:.1f} deg ({SHOULDER_SHARE:.0%} at the clavicle)"
    if test in ("body_belt_swing", "body_belt_side"):
        # about the bone's local X (Z, away from the body, swings outward) or local Z
        # (sideways, along the belt)
        swing = BELT_SWING if test == "body_belt_swing" else BELT_SIDE
        axis = (1.0, 0.0, 0.0) if test == "body_belt_swing" else (0.0, 0.0, 1.0)
        for name, deg in swing.items():
            arm.pose.bones[name].rotation_quaternion = Quaternion(axis, math.radians(deg))
        info = " ".join(f"{n} {d:.0f} deg" for n, d in swing.items())
    if test == "body_stride":
        b = arm.data.bones
        leg = (b["LeftFoot"].head_local - b["LeftUpperLeg"].head_local).length
        drop = leg - math.sqrt(leg * leg - STRIDE * STRIDE)
        arm.pose.bones["Hips"].location = (0.0, 0.0, 0.0)
        hips = arm.pose.bones["Hips"]
        rest = b["Hips"].matrix_local.to_3x3()
        hips.location = rest.transposed() @ Vector((0.0, 0.0, -drop))
        bpy.context.view_layer.update()
        step(arm, "Left", STRIDE)
        step(arm, "Right", -STRIDE)
        info = f"stride {2 * STRIDE:.2f} m, hips down {drop * 1000:.1f} mm"
    bpy.context.view_layer.update()
    return info
