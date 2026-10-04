"""Verify: contract checks on the .blend, then re-import the glbs.

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

Body (stage 3, `check_body`): triangles of Body / HeadMesh / Collar against the budgets,
materials (at most 6, textures at most 2048), the skeleton (the contract's bones only,
the coat chains' and the belt items' names, parents and direction, at most MAX_BONES),
weights (<= 4, normalized, nothing on a bone far from the vertex; every hanging belt
item vertex only on its own bones, no other vertex on them), the seams (Head and Collar meet
Body on shared points with identical weights), and every body test pose
(test_poses.BODY_TESTS): triangles of one garment crossing another's (legs through
the skirt, arms through the coat, the top through the coat, items through the coat).
Prints the landmarks in Godot coordinates (bone heads, eyes, the boots' floor contacts).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, BODY_GLB, BODY_TRI_BUDGET, COAT_BODY_MAT, COAT_CHAINS, COAT_MAT, COLLAR_TRI_BUDGET, GLB, GLOVE_MAT,
    GLOW_MAT, GRIP_DIAMETER, HAND_LENGTH_RANGE, HEAD_TRI_BUDGET, HEIGHT_TARGET, MAX_BONES, OUTFIT_MAT, POSES,
    SKIN_MAT, SOLE_Z, TEX_SIZE, arm_mesh, armature, chain_names,
)
from outfit_bake import PART_IDS  # noqa: E402
import belt as belt_geo  # noqa: E402
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


# --- body (stage 3) ---------------------------------------------------------------------------
FAR_BODY = 0.30          # the coat sits up to ~27 cm in front of the spine bones that carry its front
SEAM_ZONE = 0.045        # crossings this close to an armhole seam are the sleeve's piping over the coat
# legs/items is information: the belt's items rest on the trousers (contacts under the belt's
# edge, the tabs tucked under it); the others must be clean at rest
CROSS_PAIRS = (("legs", "skirt"), ("arms", "coat"), ("top", "coat"), ("items", "coat"), ("legs", "items"))
GROUPS = {
    "legs": ("trousers", "boot", "thigh_strap"),
    "arms": ("arm",),
    "top": ("top",),
    "items": ("belt", "hangers", "passkey_glow"),
}


def expected_bones():
    names = set(rig.GAME_ENGINE_TO_HUMANOID.values())
    for side in rig.SIDES:
        names.add(f"{side}Palm")
        names.add(f"{side}LowerArmTwist")
        for f in rig.FINGERS:
            names.add(f"{side}{f}Tip")
            if f != "Thumb":
                names.add(f"{side}{f}Metacarpal")
    for chain in COAT_CHAINS:
        names.update(chain_names(chain))
    names.update(belt_bones())
    return names


def belt_bones():
    return sorted({b for bs in belt_geo.HANG_BONES.values() for b in bs})


def check_belt_items(arm, body, head, collar):
    """The hanging items' bones (parents, pointing down) and weights: every vertex with a
    `hang` code only on its HANG_BONES (the chain on both cuff bones, the rest on one at
    1.0), clips and tabs and every other vertex on none of them."""
    from arcology_blender.checks import godot as gd

    bones = arm.data.bones
    want = {"BeltCuffs1": ("Hips", False), "BeltCuffs2": ("BeltCuffs1", True), "BeltPasskey1": ("Hips", False)}
    for name, (parent, connect) in want.items():
        b = bones.get(name)
        ok = b is not None and b.parent is not None and b.parent.name == parent and b.use_connect == connect
        down = b is not None and b.tail_local.z < b.head_local.z
        check(ok and down, f"{name}: child of {parent}{' (connected)' if connect else ''}, pointing down")
    belt_set = set(belt_bones())
    hang = body.data.attributes.get(belt_geo.HANG_ATTR)
    check(hang is not None, f"Body has the per-vertex `{belt_geo.HANG_ATTR}` codes")
    if hang is None:
        return
    codes = [d.value for d in hang.data]
    ws = weights(body, arm)
    bad, counts = [], {}
    for i, (c, w) in enumerate(zip(codes, ws)):
        counts[c] = counts.get(c, 0) + 1
        if c == belt_geo.HANG_CLIP:
            if set(w) & belt_set:
                bad.append((i, c, w))
            continue
        allowed = set(belt_geo.HANG_BONES[c])
        rigid = len(allowed) == 1
        if not set(w) <= allowed or (rigid and abs(w.get(next(iter(allowed)), 0.0) - 1.0) > 1e-4):
            bad.append((i, c, w))
    check(not bad, f"hanging items weighted only to their bones (vertices per code {dict(sorted(counts.items()))}, "
                   f"wrong {len(bad)} {bad[:3]})")
    for ob in (head, collar):
        on = sum(1 for w in weights(ob, arm) if set(w) & belt_set)
        check(on == 0, f"{ob.name}: no weights on the belt items' bones ({on})")
    chain = [w for c, w in zip(codes, ws) if c == belt_geo.HANG_CHAIN]
    mixed = sum(1 for w in chain if len(w) == 2)
    print(f"  cuffs' chain: {len(chain)} vertices, {mixed} blended between BeltCuffs1 and BeltCuffs2")
    print("  belt item bones (Godot coordinates of the glb: y up, the body faces +z; X/Y/Z = bone basis, "
          "Y along the bone, Z away from the body):")
    for name in want:
        b = bones[name]
        m = arm.matrix_world @ b.matrix_local
        x, y, z = (m.to_3x3().col[i] for i in range(3))
        hung = [i for i, c in enumerate(codes) if c in [k for k, v in belt_geo.HANG_BONES.items() if name in v]]
        reach = max((body.data.vertices[i].co - b.head_local).length for i in hung)
        print(f"    {name:13s} parent={b.parent.name:10s} head={fmt(gd(m.translation), 4)} "
              f"tail={fmt(gd(arm.matrix_world @ b.tail_local), 4)} length={b.length:.4f} "
              f"Y={fmt(gd(y))} X={fmt(gd(x))} Z={fmt(gd(z))} farthest vertex from the head {reach:.4f}")


def face_parts(ob):
    a = ob.data.attributes.get("part")
    inv = {v: k for k, v in PART_IDS.items()}
    return [inv.get(d.value, "") for d in a.data] if a else [""] * len(ob.data.polygons)


def tri_sets(ob):
    """{group: [triangles]} of the Body by garment; `skirt` is the coat below the waist."""
    from silena_vesper_common import WAIST_Z

    parts = face_parts(ob)
    ob.data.calc_loop_triangles()
    out = {k: [] for k in list(GROUPS) + ["coat", "skirt"]}
    co = ob.data.vertices
    for t in ob.data.loop_triangles:
        p = parts[t.polygon_index]
        if p == "coat":
            out["coat"].append(tuple(t.vertices))
            if min(co[i].co.z for i in t.vertices) < WAIST_Z - 0.06:
                out["skirt"].append(tuple(t.vertices))
            continue
        for g, members in GROUPS.items():
            if p in members:
                out[g].append(tuple(t.vertices))
    return out


def crossings(co, tris_a, tris_b, seam=None):
    """Crossing triangle pairs (not sharing a vertex); with `seam` (vertex indices), the
    count of those away from it (farther than SEAM_ZONE) and those near it."""
    verts = [Vector(p) for p in co]
    ta = BVHTree.FromPolygons(verts, tris_a, all_triangles=True)
    tb = BVHTree.FromPolygons(verts, tris_b, all_triangles=True)
    pairs = [(i, j) for i, j in ta.overlap(tb) if not set(tris_a[i]) & set(tris_b[j])]
    if seam is None:
        return len(pairs)
    sp = np.array([co[i] for i in seam])
    near = 0
    for i, _ in pairs:
        c = co[list(tris_a[i])].mean(axis=0)
        if np.min(np.linalg.norm(sp - c, axis=1)) < SEAM_ZONE:
            near += 1
    return len(pairs) - near, near


def seam_verts(ob):
    """Vertices shared by arm and coat faces: the welded armhole rims."""
    parts = face_parts(ob)
    arm_v, coat_v = set(), set()
    for p in ob.data.polygons:
        if parts[p.index] == "arm":
            arm_v.update(p.vertices)
        elif parts[p.index] == "coat":
            coat_v.update(p.vertices)
    return sorted(arm_v & coat_v)


def check_body(arm):
    from arcology_blender.checks import godot as gd
    from mathutils.kdtree import KDTree

    names = ("Body", "HeadMesh", "Collar")
    if any(bpy.data.objects.get(n) is None for n in names):
        check(False, "body meshes Body, HeadMesh, Collar exist (run bake.py)")
        return
    body, head, collar = (bpy.data.objects[n] for n in names)
    print("BODY")
    for ob, budget in ((body, BODY_TRI_BUDGET), (head, HEAD_TRI_BUDGET), (collar, COLLAR_TRI_BUDGET)):
        check(tri_count(ob) <= budget, f"{ob.name} triangles {tri_count(ob)} <= {budget}")
    mats = set()
    for ob in (body, head, collar):
        ms = [m.name for m in ob.data.materials]
        mats.update(ms)
        print(f"  {ob.name} materials {ms}")
        uvs = [u.name for u in ob.data.uv_layers]
        check(uvs == ["UVMap"], f"{ob.name} uv maps {uvs}")
        extra = [a.name for a in ob.data.attributes if not a.name.startswith(".") and a.name not in
                 ("position", "sharp_face", "UVMap", "material_index", "part", belt_geo.HANG_ATTR)]
        check(not extra, f"{ob.name}: no build-time attributes left {extra}")
    for i, m in enumerate(body.data.materials):
        if m.name in (COAT_BODY_MAT, OUTFIT_MAT, GLOVE_MAT, COAT_MAT):
            print(f"  Body texel density {m.name}: {texel_density(body, i):.0f} px/m")
    want = {GLOVE_MAT, COAT_MAT, COAT_BODY_MAT, OUTFIT_MAT, GLOW_MAT, SKIN_MAT}
    check(mats == want and len(mats) <= 6, f"materials {sorted(mats)} (6 at most)")
    for name in sorted(mats):
        m = bpy.data.materials[name]
        imgs = sorted({(n.image.name, n.image.size[0], n.image.size[1]) for n in m.node_tree.nodes
                       if n.type == "TEX_IMAGE" and n.image})
        check(all(max(w, h) <= TEX_SIZE for _, w, h in imgs), f"{name} textures {imgs}")
    # skeleton
    bones = arm.data.bones
    have = {b.name for b in bones}
    want_b = expected_bones()
    check(have == want_b, f"bones are the contract's ({len(have)}): missing {sorted(want_b - have)}, "
                          f"extra {sorted(have - want_b)}")
    check(len(have) <= MAX_BONES, f"bones {len(have)} <= {MAX_BONES}")
    for chain in COAT_CHAINS:
        cn = chain_names(chain)
        ok = bones[cn[0]].parent.name == "Hips" and all(bones[cn[k]].parent.name == cn[k - 1]
                                                        and bones[cn[k]].use_connect for k in range(1, len(cn)))
        down = all(bones[n].tail_local.z < bones[n].head_local.z for n in cn)
        check(ok and down, f"chain {chain}: {cn[0]} child of Hips, connected, pointing down "
                           f"(head z {bones[cn[0]].head_local.z:.3f}, tail z {bones[cn[-1]].tail_local.z:.3f})")
    check_belt_items(arm, body, head, collar)
    # weights
    for ob in (body, head, collar):
        ws = weights(ob, arm)
        counts = [len(w) for w in ws]
        sums = [sum(w.values()) for w in ws]
        check(max(counts) <= 4 and min(counts) >= 1, f"{ob.name} influences {min(counts)}..{max(counts)}")
        check(max(abs(s - 1.0) for s in sums) < 1e-3, f"{ob.name} normalized")
        nondef = {b for w in ws for b in w if not arm.data.bones[b].use_deform}
        check(not nondef, f"{ob.name}: only deforming bones {sorted(nondef)}")
        stray, worst = 0, 0.0
        fp = face_parts(ob)
        follows = set()     # the skirt and the hanging items follow the thigh's swing on purpose
        for poly in ob.data.polygons:
            if fp[poly.index] in ("coat", "hangers", "passkey_glow"):
                follows.update(poly.vertices)
        for vtx, w in zip(ob.data.vertices, ws):
            p = ob.matrix_world @ vtx.co
            for b, wt in w.items():
                if vtx.index in follows and (b.endswith("UpperLeg") or b == "Hips"):
                    continue
                d = rig.bone_region_distance(arm, arm.data.bones[b], p)
                if wt > 0.05 and d > FAR_BODY:
                    stray += 1
                    worst = max(worst, d)
        check(stray == 0, f"{ob.name}: no weights on bones farther than {FAR_BODY} m ({stray}, worst {worst:.3f})")
    # seams: HeadMesh and Collar meet Body on shared points with identical weights
    kd = KDTree(len(body.data.vertices))
    for vtx in body.data.vertices:
        kd.insert(vtx.co, vtx.index)
    kd.balance()
    bw = weights(body, arm)
    hparts = face_parts(head)
    skin_v = {i for p in head.data.polygons if hparts[p.index] == "head" for i in p.vertices}
    for ob in (head, collar):
        bm_ = bmesh.new()
        bm_.from_mesh(ob.data)
        if ob is head:      # the neck's cut (the hair has its own open edges)
            edge = [v.index for v in bm_.verts if v.is_boundary and v.index in skin_v]
        else:               # the collar is closed: its base ring sits on the coat's neckline
            edge = [v.index for v in bm_.verts]
        bm_.free()
        ow = weights(ob, arm)
        shared, same = 0, 0
        for i in edge:
            _, j, d = kd.find(ob.data.vertices[i].co)
            if d < 1e-5:
                shared += 1
                if all(abs(ow[i].get(k, 0.0) - bw[j].get(k, 0.0)) < 1e-3 for k in set(ow[i]) | set(bw[j])):
                    same += 1
        print(f"  {ob.name}: {len(edge)} seam candidates, {shared} on Body points, {same} with the same weights")
        if ob is head:
            check(shared == len(edge) and same == shared, "HeadMesh's neck seam lies on Body's with identical weights")
        else:
            check(shared > 0 and same == shared, "Collar's base lies on the coat with identical weights")
    # folds: faces turned against their neighbors (information: a few remain where the sleeve
    # heads stand above the shoulders)
    bm_ = bmesh.new()
    bm_.from_mesh(body.data)
    bm_.normal_update()
    bparts = face_parts(body)
    folds = []
    for f in bm_.faces:
        if bparts[f.index] != "coat":
            continue
        nb = [g for e in f.edges for g in e.link_faces if g is not f]
        avg = sum((g.normal for g in nb), Vector())
        if nb and avg.length > 1e-6 and f.normal.dot(avg.normalized()) < -0.3:
            folds.append(tuple(round(c, 3) for c in f.calc_center_median()))
    bm_.free()
    print(f"  coat faces folded against their neighbors: {len(folds)} {folds[:8]}")
    # intersections in the test poses
    print("BODY TEST POSES (crossing triangle pairs)")
    sets = tri_sets(body)
    seam = seam_verts(body)
    print("  triangles per group: " + ", ".join(f"{k} {len(t)}" for k, t in sets.items())
          + f"; armhole seam vertices {len(seam)}")
    fingers = {p: test_poses.finger_rotations(arm, p) for p in ("Open", "Grip")}
    for test in test_poses.BODY_TESTS:
        info = test_poses.body_apply(arm, test, fingers)
        co = posed(body)
        line = []
        for a, b in CROSS_PAIRS:
            if (a, b) == ("arms", "coat"):
                n, near = crossings(co, sets[a], sets[b], seam)
                line.append(f"{a}/{b} {n} (+{near} at the armhole seam)")
            else:
                n = crossings(co, sets[a], sets[b])
                line.append(f"{a}/{b} {n}")
            if test == "body_rest" and (a, b) != ("legs", "items"):
                check(n == 0, f"rest: {a} through {b}: {n}")
        print(f"  {test:15s} {info:34s} " + ", ".join(line) + f"; lowest point z {co[:, 2].min():.4f}")
    test_poses.reset_all(arm, {})
    set_pose(arm, None)
    # landmarks in Godot coordinates
    print("LANDMARKS (Godot coordinates of the glb: y up, the body faces +z)")
    for n in ("Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftUpperArm", "RightUpperArm",
              "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg", "LeftFoot", "RightFoot",
              "LeftToes", "RightToes"):
        print(f"  {n:14s} head {fmt(gd(arm.matrix_world @ bones[n].head_local), 4)}")
    print(f"  eyes (midpoint) {fmt(gd(arm['eye']), 4)}")
    co = np.array([tuple(body.matrix_world @ vtx.co) for vtx in body.data.vertices])
    parts = face_parts(body)
    boot_v = set()
    for p in body.data.polygons:
        if parts[p.index] == "boot":
            boot_v.update(p.vertices)
    bv = co[sorted(boot_v)]
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        s = bv[(bv[:, 0] * sx > 0.0) & (bv[:, 2] < SOLE_Z + 0.0015)]
        heel = s[s[:, 1].argmax()]
        toe = s[s[:, 1].argmin()]
        print(f"  {side} boot floor contact: heel {fmt(gd(heel), 4)} toe {fmt(gd(toe), 4)}")


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
    check_body(arm)
    print("CONTRACT", "OK" if not FAILS else f"FAIL ({len(FAILS)})")
    for f in FAILS:
        print("  FAILED:", f)
    for path in (GLB["Left"], GLB["Right"], BODY_GLB):
        if not os.path.exists(path):        # the arm glbs only exist after `export.py -- --arms`
            print(f"SKIP {path} (not exported)")
            continue
        import_report(path)
        a = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
        print(f"  BONES {len(a.data.bones)}: {', '.join(b.name for b in a.data.bones)}")
        roots = [b.name for b in a.data.bones if b.parent is None]
        print(f"  ROOT {roots}")
        print(f"  ANIMATIONS {sorted(act.name for act in bpy.data.actions)}")


if __name__ == "__main__":
    main()
