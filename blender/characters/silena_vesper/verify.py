"""Stage 5: contract checks on the .blend, then re-import both glbs.

  blender -b --factory-startup --python blender/characters/silena_vesper/verify.py

Checks: body measurements; per arm (glove + sleeve, one mesh after bake.py)
triangles, materials, textures, UV maps, texel density; weights (<= 4 deforming
bones, normalized, no weight on a bone far from the vertex, only bones of the
exported `<Side>UpperArm` subtree); the Grip pose against its handle and fingers
colliding with each other or the palm; the right arm as an exact mirror of the
left in every pose; the render-only test poses (test_poses.py): no glove
triangle may cross a sleeve triangle (the gauntlet poking through the cuff),
and how far the sleeve stays from the elbow joint (volume at the bend). Prints
the arm bones' rest frames and the eyes in Godot axes, then re-imports the glbs
(bones, animations, triangles).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, COAT_MAT, GLB, GLOVE_MAT, GRIP_DIAMETER, HAND_LENGTH_RANGE, HEIGHT_TARGET, POSES, TEX_SIZE, arm_mesh,
    armature,
)
import test_poses  # noqa: E402
from arcology_blender import rig  # noqa: E402
from arcology_blender.checks import fmt, godot, import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

TRI_BUDGET = 14000
FAR_GLOVE = 0.05        # a weight on a bone farther than this from its region is a stray (glove)
FAR_SLEEVE = 0.10       # the sleeve is loose: up to ~6 cm off the bones
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


def parts(ob):
    """Per vertex: True for the glove (material 0), False for the sleeve."""
    glove_v = np.zeros(len(ob.data.vertices), dtype=bool)
    for p in ob.data.polygons:
        if p.material_index == 0:
            glove_v[list(p.vertices)] = True
    return glove_v


def tris_of(ob, material):
    ob.data.calc_loop_triangles()
    return [tuple(t.vertices) for t in ob.data.loop_triangles if t.material_index == material]


def texel_density(ob, material):
    """Baked texels per meter (UV area vs surface area of the material's faces)."""
    me = ob.data
    uv = me.uv_layers["UVMap"].data
    area3, area2 = 0.0, 0.0
    for p in me.polygons:
        if p.material_index != material:
            continue
        area3 += p.area
        pts = [uv[i].uv for i in p.loop_indices]
        a = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            a += x0 * y1 - x1 * y0
        area2 += abs(a) * 0.5
    return TEX_SIZE * (area2 / area3) ** 0.5 if area3 > 0 else 0.0


def check_arm(arm, side):
    ob = arm_mesh(side)
    print(f"ARM {ob.name}")
    tris = tri_count(ob)
    g_tris = len(tris_of(ob, 0))
    check(tris <= TRI_BUDGET, f"triangles {tris} <= {TRI_BUDGET} (glove {g_tris}, sleeve {tris - g_tris})")
    mats = [m.name for m in ob.data.materials]
    check(mats == [GLOVE_MAT, COAT_MAT], f"materials {mats}")
    for m in ob.data.materials:
        imgs = sorted(f"{n.image.name} {n.image.size[0]}x{n.image.size[1]}" for n in m.node_tree.nodes
                      if n.type == "TEX_IMAGE" and n.image)
        check(all(f"{TEX_SIZE}x{TEX_SIZE}" in i for i in imgs) and len(imgs) == 3, f"{m.name} textures {imgs}")
    uvs = [u.name for u in ob.data.uv_layers]
    check(uvs == ["UVMap"], f"uv maps {uvs}")
    extra = [a.name for a in ob.data.attributes if not a.name.startswith(".") and a.name not in
             ("position", "sharp_face", "UVMap", "material_index")]
    check(not extra, f"no build-time attributes left {extra}")
    print(f"  texel density: glove {texel_density(ob, 0):.0f} px/m, sleeve {texel_density(ob, 1):.0f} px/m")

    keep = set(rig.subtree(arm, f"{side}UpperArm"))
    ws = weights(ob, arm)
    counts = [len(w) for w in ws]
    sums = [sum(w.values()) for w in ws]
    check(max(counts) <= 4, f"max influences {max(counts)}")
    check(min(counts) >= 1, f"every vertex weighted (min {min(counts)})")
    check(max(abs(s - 1.0) for s in sums) < 1e-3, f"normalized (worst {max(abs(s - 1.0) for s in sums):.5f})")
    used = {b for w in ws for b in w}
    check(used <= keep, f"bones used are in the {side}UpperArm subtree ({len(used)} bones: no "
                        f"{sorted(keep - used)})")
    glove_v = parts(ob)
    stray, worst = 0, 0.0
    for v, w, is_glove in zip(ob.data.vertices, ws, glove_v):
        p = ob.matrix_world @ v.co
        far = FAR_GLOVE if is_glove else FAR_SLEEVE
        for b, wt in w.items():
            d = rig.bone_region_distance(arm, arm.data.bones[b], p)
            if wt > 0.02 and d > far:
                stray += 1
                worst = max(worst, d)
    check(stray == 0, f"no stray weights on far bones (glove > {FAR_GLOVE} m, sleeve > {FAR_SLEEVE} m: {stray}, "
                      f"worst {worst:.3f})")
    return ob


def dominant_parts(ob, arm):
    """Per vertex: the finger (or 'Palm') whose bones dominate it ('' for the sleeve)."""
    out = []
    glove_v = parts(ob)
    for w, is_glove in zip(weights(ob, arm), glove_v):
        if not w or not is_glove:
            out.append("")
            continue
        b = max(w, key=w.get)
        out.append(next((f for f in rig.FINGERS if f in b), "Palm"))
    return out


def check_pose(arm, ob, side, pose):
    set_pose(arm, pose)
    co = posed(ob)
    tris = tris_of(ob, 0)
    parts_ = dominant_parts(ob, arm)
    tree = BVHTree.FromPolygons([Vector(p) for p in co], tris)
    hits = {}
    for i, j in tree.overlap(tree):
        a, b = tris[i], tris[j]
        if set(a) & set(b):
            continue
        pa = {parts_[k] for k in a}
        pb = {parts_[k] for k in b}
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
        hand = np.array([p != "" for p in parts_])
        print(f"  Grip: leather vs {GRIP_DIAMETER * 1000:.0f} mm handle: deepest {r[hand].min() * 1000:.2f} mm "
              f"(negative = pressed in), vertices within 2 mm of it {(np.abs(r[hand]) < 0.002).sum()}")
    return co


def check_deformation(arm, side, ob):
    """Every test pose: glove vs sleeve crossings (must be none), sleeve folding into
    itself (crook of the elbow: expected when bent hard), the elbow's volume."""
    print(f"TEST POSES {side}")
    fingers = {p: test_poses.finger_rotations(arm, p) for p in ("Open", "Grip")}
    g_tris, s_tris = tris_of(ob, 0), tris_of(ob, 1)
    glove_v = parts(ob)
    rest_co = None
    elbow_bone = arm.data.bones[f"{side}LowerArm"]
    for test in test_poses.TESTS:
        info = test_poses.apply(arm, side, test, fingers)
        co = posed(ob)
        if test == "rest":
            rest_co = co
        verts = [Vector(p) for p in co]
        gt = BVHTree.FromPolygons(verts, g_tris)
        st = BVHTree.FromPolygons(verts, s_tris)
        cross = len(gt.overlap(st))
        self_hits = sum(1 for i, j in st.overlap(st) if not set(s_tris[i]) & set(s_tris[j]))
        j = np.array(arm.pose.bones[f"{side}LowerArm"].head)
        near = (~glove_v) & (np.linalg.norm(co - j, axis=1) < 0.09)
        dmin = np.linalg.norm(co[near] - j, axis=1).min() if near.any() else 0.0
        check(cross == 0, f"{test:12s} {info:10s} glove/sleeve crossings {cross}, sleeve self-crossings "
                          f"{self_hits // 2}, closest sleeve to the elbow joint {dmin * 1000:.1f} mm")
    test_poses.reset(arm, {})
    j0 = np.array(elbow_bone.head_local)
    zone = (~glove_v) & (np.linalg.norm(rest_co - j0, axis=1) < 0.09)
    print(f"  rest: closest sleeve to the elbow joint {np.linalg.norm(rest_co[zone] - j0, axis=1).min() * 1000:.1f} mm")


def frames(arm):
    print("REST FRAMES (Godot axes: Y up, -Z forward; bone basis columns X, Y = along the bone, Z)")
    for side in ("Left", "Right"):
        for n in ("UpperArm", "LowerArm", "LowerArmTwist", "Hand", "MiddleProximal"):
            b = arm.data.bones[side + n]
            m = arm.matrix_world @ b.matrix_local
            x, y, z = (m.to_3x3().col[i] for i in range(3))
            print(f"  {side + n:22s} head={fmt(godot(m.translation), 4)} length={b.length:.4f} X={fmt(godot(x))} "
                  f"Y={fmt(godot(y))} Z={fmt(godot(z))} parent={b.parent.name}")
        b = arm.data.bones
        upper = (b[side + "LowerArm"].head_local - b[side + "UpperArm"].head_local).length
        fore = (b[side + "Hand"].head_local - b[side + "LowerArm"].head_local).length
        print(f"  {side}: upper arm (shoulder to elbow joint) {upper:.4f} m, forearm (elbow to wrist) {fore:.4f} m")
    print(f"  eyes (midpoint) {fmt(godot(arm['eye']), 4)}")


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    arm = armature()
    h, hl = arm["height"], arm["hand_length"]
    print(f"BODY height={h:.4f} eye={fmt(arm['eye'], 4)} hand_length={hl:.4f}")
    check(abs(h - HEIGHT_TARGET) < 0.01, f"height {h:.3f} ~ {HEIGHT_TARGET}")
    check(HAND_LENGTH_RANGE[0] <= hl <= HAND_LENGTH_RANGE[1], f"hand length {hl:.3f} in {HAND_LENGTH_RANGE}")
    tracks = [t.name for t in arm.animation_data.nla_tracks]
    check(tuple(tracks) == POSES, f"poses {tracks}")
    obs = {side: check_arm(arm, side) for side in ("Left", "Right")}
    print("POSES")
    posed_co = {}
    for side in ("Left", "Right"):
        for pose in POSES:
            posed_co[side, pose] = check_pose(arm, obs[side], side, pose)
    for pose in POSES:
        a, b = posed_co["Left", pose].copy(), posed_co["Right", pose]
        a[:, 0] *= -1.0
        diff = float(np.linalg.norm(a - b, axis=1).max())
        check(diff < 1e-4, f"{pose}: right arm mirrors the left (max {diff * 1000:.4f} mm)")
    for side in ("Left", "Right"):
        check_deformation(arm, side, obs[side])
    set_pose(arm, None)
    frames(arm)
    print("CONTRACT", "OK" if not FAILS else f"FAIL ({len(FAILS)})")
    for f in FAILS:
        print("  FAILED:", f)
    for side in ("Left", "Right"):
        import_report(GLB[side])
        a = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
        print(f"  BONES {len(a.data.bones)}: {', '.join(b.name for b in a.data.bones)}")
        roots = [b.name for b in a.data.bones if b.parent is None]
        print(f"  ROOT {roots}")
        print(f"  ANIMATIONS {sorted(act.name for act in bpy.data.actions)}")


if __name__ == "__main__":
    main()
