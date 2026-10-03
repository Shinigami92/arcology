"""Armatures for characters (D-037): humanoid bone names, OpenXR hand joints,
bone pruning, skin weights and pose actions.

Bone names follow Godot's SkeletonProfileHumanoid (`Hips`, `LeftUpperArm`,
`LeftIndexProximal`, ...), so Godot's retargeting and IK nodes need no bone
map. Hands add the OpenXR joints the profile lacks (`LeftPalm`,
`LeftIndexMetacarpal`, `LeftIndexTip`, ...): XRHandModifier3D finds bones by
`Left`/`Right` + the OpenXR joint name, so hand tracking can drive the same
skeleton. Blender bones point along their local +Y; finger curl is a rotation
about the bone's local X.
"""

import bpy
from mathutils import Euler

SIDES = ("Left", "Right")
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")

# MPFB's "game_engine" rig (Unreal-style names) to Godot's humanoid profile.
GAME_ENGINE_TO_HUMANOID = {
    "Root": "Root",
    "pelvis": "Hips",
    "spine_01": "Spine",
    "spine_02": "Chest",
    "spine_03": "UpperChest",
    "neck_01": "Neck",
    "head": "Head",
}
for _s, _side in (("l", "Left"), ("r", "Right")):
    GAME_ENGINE_TO_HUMANOID.update({
        f"clavicle_{_s}": f"{_side}Shoulder",
        f"upperarm_{_s}": f"{_side}UpperArm",
        f"lowerarm_{_s}": f"{_side}LowerArm",
        f"hand_{_s}": f"{_side}Hand",
        f"thumb_01_{_s}": f"{_side}ThumbMetacarpal",
        f"thumb_02_{_s}": f"{_side}ThumbProximal",
        f"thumb_03_{_s}": f"{_side}ThumbDistal",
        f"thigh_{_s}": f"{_side}UpperLeg",
        f"calf_{_s}": f"{_side}LowerLeg",
        f"foot_{_s}": f"{_side}Foot",
        f"ball_{_s}": f"{_side}Toes",
    })
    for _src, _dst in (("index", "Index"), ("middle", "Middle"), ("ring", "Ring"), ("pinky", "Little")):
        for _n, _seg in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal")):
            GAME_ENGINE_TO_HUMANOID[f"{_src}_0{_n}_{_s}"] = f"{_side}{_dst}{_seg}"


def skinned_meshes(arm):
    """Mesh objects deformed by the armature (Armature modifier pointing at it)."""
    return [ob for ob in bpy.data.objects if ob.type == "MESH"
            and any(m.type == "ARMATURE" and m.object == arm for m in ob.modifiers)]


def _edit(arm):
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    return arm.data.edit_bones


def _object_mode():
    bpy.ops.object.mode_set(mode="OBJECT")


def rename_bones(arm, mapping):
    """Rename bones (and the skinned meshes' vertex groups with them); names missing
    from the armature are ignored. Returns the number renamed."""
    groups = [ob.vertex_groups for ob in skinned_meshes(arm)]
    count = 0
    for old, new in mapping.items():
        bone = arm.data.bones.get(old)
        if bone is None or old == new:
            continue
        bone.name = new
        for vgs in groups:
            vg = vgs.get(old)
            if vg is not None:  # Blender renames them for parented meshes, not always for modifier-only ones
                vg.name = new
        count += 1
    return count


def add_hand_joints(arm, side, metacarpal_start=0.15, tip_length=0.012):
    """Add the OpenXR joints Godot's humanoid profile lacks to one hand (`side` "Left"
    or "Right"): `<side>Palm`, metacarpals for index to little (between the hand and
    each proximal, starting `metacarpal_start` of the way from the wrist), and a
    `<side><Finger>Tip` past every distal. New bones don't deform; the proximals
    are reparented to their metacarpals."""
    eb = _edit(arm)
    hand = eb[f"{side}Hand"]
    for finger in FINGERS[1:]:
        prox = eb[f"{side}{finger}Proximal"]
        meta = eb.new(f"{side}{finger}Metacarpal")
        meta.head = hand.head.lerp(prox.head, metacarpal_start)
        meta.tail = prox.head.copy()
        meta.align_roll(prox.z_axis)
        meta.parent = hand
        meta.use_deform = False
        prox.use_connect = False
        prox.parent = meta
    for finger in FINGERS:
        distal = eb[f"{side}{finger}Distal"]
        tip = eb.new(f"{side}{finger}Tip")
        tip.head = distal.tail.copy()
        tip.tail = distal.tail + (distal.tail - distal.head).normalized() * tip_length
        tip.align_roll(distal.z_axis)
        tip.parent = distal
        tip.use_deform = False
    middle = eb[f"{side}MiddleProximal"]
    palm = eb.new(f"{side}Palm")
    palm.head = hand.head.lerp(middle.head, 0.5)
    palm.tail = palm.head + (middle.head - hand.head).normalized() * tip_length
    palm.align_roll(hand.z_axis)
    palm.parent = hand
    palm.use_deform = False
    _object_mode()


def prune_bones(arm, keep):
    """Delete every bone not in `keep`. Weights of a deleted bone move to its nearest
    kept ancestor (or are dropped if none), so the mesh still deforms as one piece."""
    keep = set(keep)
    target = {}
    for bone in arm.data.bones:
        if bone.name in keep:
            continue
        up = bone.parent
        while up is not None and up.name not in keep:
            up = up.parent
        target[bone.name] = up.name if up else None
    for ob in skinned_meshes(arm):
        vgs = ob.vertex_groups
        for dst in {t for t in target.values() if t and vgs.get(t) is None}:
            vgs.new(name=dst)
        index = {vg.index: vg.name for vg in vgs}
        moved = {}
        for v in ob.data.vertices:
            for g in v.groups:
                src = index[g.group]
                if src in target and target[src] and g.weight > 0.0:
                    moved.setdefault(target[src], {}).setdefault(v.index, 0.0)
                    moved[target[src]][v.index] += g.weight
        for dst, weights in moved.items():
            vg = vgs[dst]
            for vi, w in weights.items():
                vg.add([vi], w, "ADD")
        for src in target:
            vg = vgs.get(src)
            if vg is not None:
                vgs.remove(vg)
    eb = _edit(arm)
    for name in target:
        eb.remove(eb[name])
    _object_mode()


def extract_by_weight(ob, bones, min_weight=0.5):
    """Keep only the faces whose every vertex has at least `min_weight` total weight
    in `bones` (e.g. a hand and forearm cut from a full body). Returns faces kept."""
    import bmesh

    ids = {vg.index for vg in ob.vertex_groups if vg.name in set(bones)}
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    deform = bm.verts.layers.deform.verify()
    inside = {v.index for v in bm.verts if sum(w for g, w in v[deform].items() if g in ids) >= min_weight}
    doomed = [f for f in bm.faces if not all(v.index in inside for v in f.verts)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    kept = len(bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return kept


def limit_weights(ob, arm, limit=4, epsilon=1e-4):
    """Keep each vertex's `limit` strongest weights of `arm`'s deforming bones (glTF
    skins carry 4), drop weights under `epsilon` and normalize the rest to sum 1.
    Other vertex groups (MPFB's masks, helpers) are left alone."""
    vgs = ob.vertex_groups
    bones = {vg.index for vg in vgs if (b := arm.data.bones.get(vg.name)) is not None and b.use_deform}
    for v in ob.data.vertices:
        pairs = sorted(((g.weight, g.group) for g in v.groups if g.group in bones), reverse=True)
        kept = [(w, gi) for w, gi in pairs[:limit] if w > epsilon]
        for w, gi in pairs:
            if (w, gi) not in kept:
                vgs[gi].remove([v.index])
        total = sum(w for w, _ in kept) or 1.0
        for w, gi in kept:
            vgs[gi].add([v.index], w / total, "REPLACE")


def pose_action(arm, name, rotations=None):
    """Store a pose as action `name` on its own NLA track (exported as a glTF animation
    of that name). `rotations` maps bone names to (x, y, z) degrees in the bone's
    local axes; every other bone is keyed at rest so tracks don't leak into each
    other in Blender. The glTF exporter drops channels at rest; Godot's blending
    treats missing tracks as rest, so blends between poses still work."""
    rotations = rotations or {}
    unknown = set(rotations) - {b.name for b in arm.data.bones}
    if unknown:
        raise KeyError(f"pose {name!r}: no bones {sorted(unknown)}")
    if arm.animation_data is None:
        arm.animation_data_create()
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm.animation_data.action = action
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        deg = rotations.get(pb.name, (0.0, 0.0, 0.0))
        pb.rotation_quaternion = Euler([d * 3.141592653589793 / 180.0 for d in deg], "XYZ").to_quaternion()
        for frame in (0, 1):
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 0, action)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    return action
