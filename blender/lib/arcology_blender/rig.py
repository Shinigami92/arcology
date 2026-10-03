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


def subtree(arm, root):
    """Names of `root` and every bone below it (e.g. what a hand glb keeps:
    `prune_bones(arm, subtree(arm, "LeftLowerArm"))`)."""
    names = [root]
    for bone in arm.data.bones[root].children_recursive:
        names.append(bone.name)
    return names


def mirror_name(name, src="Left", dst="Right"):
    """`LeftIndexTip` -> `RightIndexTip` (names without the side stay)."""
    return dst + name[len(src):] if name.startswith(src) else name


def mirror_rotations(arm, rotations, src="Left", dst="Right"):
    """Pose rotations for the other side: {bone: (x, y, z) degrees} in `src`'s bone-local
    axes -> the same for the mirrored `dst` bones (mirror plane x = 0 in armature space).
    Works for any bone rolls: each rotation is taken to armature space, reflected
    and brought back into the other bone's rest frame."""
    from mathutils import Matrix

    mirror = Matrix.Diagonal((-1.0, 1.0, 1.0))
    out = {}
    for name, deg in rotations.items():
        other = mirror_name(name, src, dst)
        rl = arm.data.bones[name].matrix_local.to_3x3()
        rr = arm.data.bones[other].matrix_local.to_3x3()
        q = Euler([d * 3.141592653589793 / 180.0 for d in deg], "XYZ").to_matrix()
        world = rl @ q @ rl.transposed()
        local = rr.transposed() @ (mirror @ world @ mirror) @ rr
        e = local.to_euler("XYZ")
        out[other] = tuple(a * 180.0 / 3.141592653589793 for a in e)
    return out


def mirror_mesh(ob, name, src="Left", dst="Right", collection=None):
    """Mirrored copy of a skinned mesh across world x = 0: vertices reflected,
    faces flipped back outward, `src` vertex groups renamed to `dst` (UVs and
    other layers kept, so a baked texture is shared). The copy keeps the
    Armature modifier and parent of the original. Returns the new object."""
    import bmesh

    me = ob.data.copy()
    me.name = name
    new = bpy.data.objects.new(name, me)
    (collection or ob.users_collection[0]).objects.link(new)
    new.matrix_world = ob.matrix_world.copy()
    mw = ob.matrix_world
    inv = mw.inverted()
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        w = mw @ v.co
        w.x = -w.x
        v.co = inv @ w
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.update()
    if len(new.vertex_groups) == len(ob.vertex_groups):  # group names travel with the mesh (Blender 4+)
        for vg in new.vertex_groups:
            vg.name = mirror_name(vg.name, src, dst)
    else:
        for vg in ob.vertex_groups:  # same order: the copied weights keep their group indices
            new.vertex_groups.new(name=mirror_name(vg.name, src, dst))
    for m in ob.modifiers:
        if m.type == "ARMATURE":
            mod = new.modifiers.new(m.name, "ARMATURE")
            mod.object = m.object
    new.parent = ob.parent
    new.matrix_world = ob.matrix_world.copy()
    for k in ob.keys():
        new[k] = ob[k]
    return new


def bone_region_distance(arm, bone, point):
    """Distance from a world point to the region a bone deforms: its own segment and
    the segments from its head to its children's heads (and through non-deforming
    children such as OpenXR metacarpals to their tails), so a short hand bone still
    owns the palm up to the knuckles."""
    mw = arm.matrix_world
    head = mw @ bone.head_local
    ends = [mw @ bone.tail_local] + [mw @ c.head_local for c in bone.children]
    ends += [mw @ c.tail_local for c in bone.children if not c.use_deform]
    best = None
    for end in ends:
        d = end - head
        t = 0.0 if d.length_squared == 0.0 else max(0.0, min(1.0, (point - head).dot(d) / d.length_squared))
        dist = (point - (head + d * t)).length
        best = dist if best is None or dist < best else best
    return best


def drop_far_weights(ob, arm, distance=0.045):
    """Remove weights of deforming bones whose region (`bone_region_distance`) is farther
    than `distance` from the vertex (stray weights from transfers or smoothing), then
    renormalize the vertex's remaining bone weights. Vertices whose every weight is far
    keep their weights. Returns the number of weights removed."""
    vgs = ob.vertex_groups
    bones = {vg.index: arm.data.bones[vg.name] for vg in vgs
             if arm.data.bones.get(vg.name) is not None and arm.data.bones[vg.name].use_deform}
    removed = 0
    mw = ob.matrix_world
    for v in ob.data.vertices:
        p = mw @ v.co
        pairs = [(g.group, g.weight) for g in v.groups if g.group in bones and g.weight > 0.0]
        far = [gi for gi, _ in pairs if bone_region_distance(arm, bones[gi], p) > distance]
        if not far or len(far) == len(pairs):
            continue
        for gi in far:
            vgs[gi].remove([v.index])
            removed += 1
        rest = [(gi, w) for gi, w in pairs if gi not in far]
        total = sum(w for _, w in rest) or 1.0
        for gi, w in rest:
            vgs[gi].add([v.index], w / total, "REPLACE")
    return removed


# --- twist bones and test poses -------------------------------------------------------------
def add_twist_bone(arm, parent, name, at=0.5):
    """Add a twist bone: a deforming leaf child of `parent` (not connected), head `at` of
    the way along it, tail at the parent's tail, same roll (its +Y is the limb axis, its
    X/Z match the parent's). The parent's children keep their parent (a humanoid Hand
    stays under LowerArm). The engine rotates it about its own Y by a share of the next
    joint's roll (`twist_share`), so the distal limb weighted to it (`garment.split_weights`)
    doesn't candy-wrap. Returns the name."""
    eb = _edit(arm)
    p = eb[parent]
    b = eb.new(name)
    b.head = p.head.lerp(p.tail, at)
    b.tail = p.tail.copy()
    b.align_roll(p.z_axis)
    b.parent = p
    b.use_connect = False
    b.use_deform = True
    _object_mode()
    return name


def rotate_about(arm, bone, axis, degrees, pivot=None):
    """Pose: turn `bone` (and what hangs below it) by `degrees` about an armature-space
    `axis` through its posed head (or `pivot`), on top of its current pose."""
    from mathutils import Matrix, Vector

    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    c = Vector(pivot) if pivot is not None else pb.head.copy()
    rot = Matrix.Rotation(degrees * 3.141592653589793 / 180.0, 4, Vector(axis).normalized())
    pb.matrix = Matrix.Translation(c) @ rot @ Matrix.Translation(-c) @ pb.matrix
    bpy.context.view_layer.update()


def two_bone_pose(arm, upper, lower, end, target, pole, end_rotation=None):
    """Pose a two-bone chain (shoulder, elbow, wrist) like an engine's two-bone IK: `end`'s
    head reaches `target` (armature space; clamped to the chain's reach), the middle
    joint bends toward the `pole` direction, each bone swings minimally from its current
    direction. `end_rotation` (3x3, armature space, the end bone's axes) orients the end
    bone, e.g. a hand on a controller. For test poses and renders. Returns the middle
    joint's posed position."""
    from mathutils import Matrix, Vector

    bones, pbs = arm.data.bones, arm.pose.bones
    bpy.context.view_layer.update()
    s = pbs[upper].head.copy()
    l1 = (bones[lower].head_local - bones[upper].head_local).length
    l2 = (bones[end].head_local - bones[lower].head_local).length
    d = Vector(target) - s
    dist = min(max(d.length, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    dn = d.normalized()
    p = Vector(pole)
    pn = (p - dn * p.dot(dn)).normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
    mid = s + dn * a + pn * (max(l1 * l1 - a * a, 0.0) ** 0.5)
    tip = s + dn * dist

    def swing(name, child, goal):
        bpy.context.view_layer.update()
        pb = pbs[name]
        head = pb.head.copy()
        cur = pbs[child].head - head
        rot = cur.rotation_difference(goal - head).to_matrix().to_4x4()
        pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix

    swing(upper, lower, mid)
    swing(lower, end, tip)
    if end_rotation is not None:
        bpy.context.view_layer.update()
        pb = pbs[end]
        m = Matrix(end_rotation).to_4x4()
        m.translation = pb.head
        pb.matrix = m
    bpy.context.view_layer.update()
    return mid


def twist_share(arm, lower, end, twist, share=0.7):
    """Drive a twist bone the way the engine does: the roll of `end` about `lower`'s axis
    relative to their rest relation (swing-twist decomposition), `share` of it applied to
    `twist` about its own Y (`lower`'s axis). Returns the full roll in degrees."""
    import math

    from mathutils import Quaternion, Vector

    bpy.context.view_layer.update()
    bones, pbs = arm.data.bones, arm.pose.bones
    rl0 = bones[lower].matrix_local.to_3x3()
    re0 = bones[end].matrix_local.to_3x3()
    rl = pbs[lower].matrix.to_3x3()
    re = pbs[end].matrix.to_3x3()
    q = (rl0 @ rl.transposed() @ re @ re0.transposed()).to_quaternion()  # end's extra turn, rest frame
    axis = rl0.col[1].normalized()
    v = Vector((q.x, q.y, q.z)).dot(axis)
    roll = 2.0 * math.atan2(v, q.w)
    if roll > math.pi:
        roll -= 2.0 * math.pi
    elif roll < -math.pi:
        roll += 2.0 * math.pi
    pbs[twist].rotation_mode = "QUATERNION"
    pbs[twist].rotation_quaternion = Quaternion((0.0, 1.0, 0.0), share * roll)
    bpy.context.view_layer.update()
    return math.degrees(roll)
