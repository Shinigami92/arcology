"""Stage 5: contract checks on the .blend, then re-import both glbs.

  blender -b --factory-startup --python blender/characters/silena_vesper/verify.py

Checks: body measurements; per glove triangles, materials, textures, UV maps;
weights (<= 4 deforming bones, normalized, no weight on a bone far from the
vertex, only bones of the exported subtree); the Grip pose against its handle
(how deep the leather presses in) and fingers colliding with each other or the
palm; the right glove as an exact mirror of the left in every pose. Prints the
hand bones' rest frames in Godot axes, then re-imports the glbs (bones,
animations, triangles).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, GLB, GLOVE_MAT, GRIP_DIAMETER, HAND_LENGTH_RANGE, HEIGHT_TARGET, POSES, TEX_SIZE, armature, glove,
)
from arcology_blender import rig  # noqa: E402
from arcology_blender.checks import fmt, godot, import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

TRI_BUDGET = 8000
FAR_BONE = 0.05         # a weight on a bone farther than this from its region is a stray
FAILS = []


def check(ok, msg):
    print(("  OK   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def set_pose(arm, pose):
    for tr in arm.animation_data.nla_tracks:
        tr.mute = tr.name != pose
    arm.animation_data.action = None
    if pose is None:
        for pb in arm.pose.bones:
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def posed(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    a = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", a)
    mw = np.array(ob.matrix_world)
    return a.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]


def weights(ob, arm):
    names = {vg.index: vg.name for vg in ob.vertex_groups}
    out = []
    for v in ob.data.vertices:
        out.append({names[g.group]: g.weight for g in v.groups if g.weight > 0.0
                    and arm.data.bones.get(names[g.group]) is not None})
    return out


def seg_dist(p, a, b):
    d = b - a
    t = max(0.0, min(1.0, (p - a).dot(d) / d.length_squared))
    return (p - (a + d * t)).length


def check_glove(arm, side):
    ob = glove(side)
    print(f"GLOVE {ob.name}")
    tris = tri_count(ob)
    check(tris <= TRI_BUDGET, f"triangles {tris} <= {TRI_BUDGET}")
    mats = [m.name for m in ob.data.materials]
    check(mats == [GLOVE_MAT], f"materials {mats}")
    imgs = sorted({f"{n.image.name} {n.image.size[0]}x{n.image.size[1]}" for m in ob.data.materials
                   for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    check(all(f"{TEX_SIZE}x{TEX_SIZE}" in i for i in imgs) and len(imgs) == 3, f"textures {imgs}")
    uvs = [u.name for u in ob.data.uv_layers]
    check(uvs == ["UVMap"], f"uv maps {uvs}")
    extra = [a.name for a in ob.data.attributes if not a.name.startswith(".") and a.name not in
             ("position", "sharp_face", "UVMap", "material_index")]
    check(not extra, f"no build-time attributes left {extra}")

    keep = set(rig.subtree(arm, f"{side}LowerArm"))
    ws = weights(ob, arm)
    counts = [len(w) for w in ws]
    sums = [sum(w.values()) for w in ws]
    check(max(counts) <= 4, f"max influences {max(counts)}")
    check(min(counts) >= 1, f"every vertex weighted (min {min(counts)})")
    check(max(abs(s - 1.0) for s in sums) < 1e-3, f"normalized (worst {max(abs(s - 1.0) for s in sums):.5f})")
    used = {b for w in ws for b in w}
    check(used <= keep, f"bones used are in the {side}LowerArm subtree ({len(used)} bones)")
    mw = arm.matrix_world
    stray = 0
    worst = 0.0
    for v, w in zip(ob.data.vertices, ws):
        p = ob.matrix_world @ v.co
        for b, wt in w.items():
            d = rig.bone_region_distance(arm, arm.data.bones[b], p)
            if wt > 0.02 and d > FAR_BONE:
                stray += 1
                worst = max(worst, d)
    check(stray == 0, f"no stray weights on far bones (> {FAR_BONE} m: {stray}, worst {worst:.3f})")
    return ob


def dominant_parts(ob, arm):
    """Per vertex: the finger (or 'Palm') whose bones dominate it."""
    out = []
    for w in weights(ob, arm):
        if not w:
            out.append("")
            continue
        b = max(w, key=w.get)
        part = next((f for f in rig.FINGERS if f in b), "Palm")
        out.append(part)
    return out


def check_pose(arm, ob, side, pose):
    set_pose(arm, pose)
    co = posed(ob)
    me = ob.data
    me.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    parts = dominant_parts(ob, arm)
    tree = BVHTree.FromPolygons([Vector(p) for p in co], tris)
    pairs = tree.overlap(tree)
    hits = {}
    for i, j in pairs:
        a, b = tris[i], tris[j]
        if set(a) & set(b):
            continue
        pa = {parts[k] for k in a}
        pb = {parts[k] for k in b}
        if len(pa) != 1 or len(pb) != 1:
            continue
        x, y = pa.pop(), pb.pop()
        if x == y or "" in (x, y):
            continue
        key = tuple(sorted((x, y)))
        hits[key] = hits.get(key, 0) + 1
    total = sum(hits.values()) // 2
    detail = ", ".join(f"{a}-{b}: {n // 2}" for (a, b), n in sorted(hits.items()))
    print(f"  {pose}: intersecting triangle pairs between fingers/palm {total} {detail}")
    if pose == "Grip":
        c = Vector(arm["grip_center"])
        ax = Vector(arm["grip_axis"])
        if side == "Right":
            c.x, ax.x = -c.x, -ax.x
        c, ax = np.array(c), np.array(ax)
        d = co - c
        r = np.linalg.norm(d - np.outer(d @ ax, ax), axis=1) - GRIP_DIAMETER * 0.5
        hand = np.array([p not in ("",) for p in parts])
        print(f"  Grip: leather vs {GRIP_DIAMETER * 1000:.0f} mm handle: deepest {r[hand].min() * 1000:.2f} mm "
              f"(negative = pressed in), vertices within 2 mm of it {(np.abs(r[hand]) < 0.002).sum()}")
    return co


def frames(arm):
    print("REST FRAMES (Godot axes: Y up, -Z forward; bone basis columns X, Y = along the bone, Z)")
    for name in ("LeftHand", "LeftMiddleProximal", "RightHand", "RightMiddleProximal"):
        b = arm.data.bones[name]
        m = arm.matrix_world @ b.matrix_local
        head = m.translation
        x, y, z = (m.to_3x3().col[i] for i in range(3))
        print(f"  {name:20s} head={fmt(godot(head), 4)} X={fmt(godot(x))} Y={fmt(godot(y))} Z={fmt(godot(z))}")


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    arm = armature()
    h, hl = arm["height"], arm["hand_length"]
    print(f"BODY height={h:.4f} eye={fmt(arm['eye'], 4)} hand_length={hl:.4f}")
    check(abs(h - HEIGHT_TARGET) < 0.01, f"height {h:.3f} ~ {HEIGHT_TARGET}")
    check(HAND_LENGTH_RANGE[0] <= hl <= HAND_LENGTH_RANGE[1], f"hand length {hl:.3f} in {HAND_LENGTH_RANGE}")
    tracks = [t.name for t in arm.animation_data.nla_tracks]
    check(tuple(tracks) == POSES, f"poses {tracks}")
    obs = {side: check_glove(arm, side) for side in ("Left", "Right")}
    print("POSES")
    posed_co = {}
    for side in ("Left", "Right"):
        for pose in POSES:
            posed_co[side, pose] = check_pose(arm, obs[side], side, pose)
    for pose in POSES:
        a, b = posed_co["Left", pose].copy(), posed_co["Right", pose]
        a[:, 0] *= -1.0
        diff = float(np.linalg.norm(a - b, axis=1).max())
        check(diff < 1e-4, f"{pose}: right glove mirrors the left (max {diff * 1000:.4f} mm)")
    set_pose(arm, None)
    frames(arm)
    print("CONTRACT", "OK" if not FAILS else f"FAIL ({len(FAILS)})")
    for side in ("Left", "Right"):
        import_report(GLB[side])
        a = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
        print(f"  BONES {len(a.data.bones)}: {', '.join(b.name for b in a.data.bones)}")
        roots = [b.name for b in a.data.bones if b.parent is None]
        print(f"  ROOT {roots}")
        print(f"  ANIMATIONS {sorted(act.name for act in bpy.data.actions)}")


if __name__ == "__main__":
    main()
