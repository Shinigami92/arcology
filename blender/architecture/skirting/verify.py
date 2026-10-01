"""Stage 5: contract checks against the run file, the casings next to the ends, then re-import the glb.

  blender -b --factory-startup --python blender/architecture/skirting/verify.py [-- --runs F]

Checks (each prints OK / FAIL, the last line is CONTRACT OK / FAIL):
- coverage: rays from the room toward every run's wall line (every 2 cm, three heights) hit the
  board's face at the profile thickness, facing along the run normal;
- nothing extra: every vertex lies in the slab of a run segment (wall line .. thickness,
  0 .. height), open ends stop exactly at the run end points (square ends);
- bottom on the floor (z = 0), top at the profile height, thickness <= profile.thickness and <=
  the thinnest casing;
- normals: front faces point along their segment's run normal, back faces into the wall,
  eased arris faces outward;
- UVs: U along the run at the trim density (1 / BOARD per meter);
- joints: none closer than JOINT_CLEAR to a corner or end;
- casings: at every open end the frame next to it (door or window, placed as in
  tools/blockout/apartment.py) stands at least as proud as the board; prints the gap.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from skirting_common import (  # noqa: E402
    BOARD, CASING_MIN, JOINT_CLEAR, THICKNESS, apartment_placements, blend_path, g2b, glb_path, import_glb,
    joint_offsets, joints_of, load_runs, normal_to_blender, place, segment_count, skirting_objects, to_blender,
)
from arcology_blender.checks import import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

UP = Vector((0, 0, 1))
FAILS = []


def result(name, ok, detail=""):
    print(f"CHECK {name}: {'OK' if ok else 'FAIL'} {detail}")
    if not ok:
        FAILS.append(name)


def segments(data):
    """[(run, seg, a, b, d, n, length, start_kind, end_kind)] in Blender coordinates."""
    out = []
    for ri, run in enumerate(data["runs"]):
        pts = [to_blender(p) for p in run["points"]]
        m = segment_count(run)
        for si in range(m):
            a, b = pts[si], pts[(si + 1) % len(pts)]
            n = normal_to_blender(run["normals"][si])
            k0 = "end" if not run["closed"] and si == 0 else "corner"
            k1 = "end" if not run["closed"] and si == m - 1 else "corner"
            out.append((ri, si, a, b, (b - a).normalized(), n, (b - a).length, k0, k1))
    return out


def slab_of(p, segs, height, tol=1e-5):
    """Index of a segment whose slab holds p (corner ends extended by the thickness)."""
    for k, (_, _, a, _, d, n, length, k0, k1) in enumerate(segs):
        t = (p - a).dot(d)
        s = (p - a).dot(n)
        lo = -tol - (THICKNESS if k0 == "corner" else 0.0)
        hi = length + tol + (THICKNESS if k1 == "corner" else 0.0)
        if lo <= t <= hi and -tol <= s <= THICKNESS + tol and -tol <= p.z <= height + tol:
            return k
    return None


def check_mesh(ob, data, segs):
    height = data["profile"]["height"]
    me = ob.data
    result("identity transform", ob.matrix_world == ob.matrix_world.Identity(4))
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    zs = [v.z for v in verts]
    result("bottom on the floor", abs(min(zs)) < 1e-6, f"min z={min(zs):.6f}")
    result("top at the profile height", abs(max(zs) - height) < 1e-6, f"max z={max(zs):.6f} (height {height})")
    result("thickness", THICKNESS <= data["profile"]["thickness"] + 1e-9 and THICKNESS <= CASING_MIN,
           f"{THICKNESS * 1000:.1f} mm (limit {data['profile']['thickness'] * 1000:.1f} mm, casings >= "
           f"{CASING_MIN * 1000:.1f} mm)")
    outside = [v for v in verts if slab_of(v, segs, height) is None]
    result("nothing swept off the runs", not outside, f"{len(outside)} of {len(verts)} vertices outside every run slab"
           + (f", e.g. {tuple(round(c, 4) for c in outside[0])}" if outside else ""))

    # square ends: the vertices near an open end stop exactly at the end point
    bad_ends = 0
    for (_, _, a, b, d, n, length, k0, k1) in segs:
        for kind, p, sign in ((k0, a, -1.0), (k1, b, 1.0)):
            if kind != "end":
                continue
            near = [(v - p).dot(d) * sign for v in verts
                    if abs((v - p).dot(d)) < 0.02 and -1e-5 <= (v - p).dot(n) <= THICKNESS + 1e-5]
            if not near or max(near) > 1e-5 or sum(1 for x in near if abs(x) < 1e-6) < 4:
                bad_ends += 1
    n_ends = sum((k0 == "end") + (k1 == "end") for *_, k0, k1 in segs)
    result("square ends at the run end points", bad_ends == 0, f"{n_ends - bad_ends}/{n_ends}")

    # coverage by rays from the room
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    miss = wrong = total = 0
    for (ri, si, a, b, d, n, length, k0, k1) in segs:
        t0 = 0.002 if k0 == "end" else THICKNESS + 0.003
        t1 = length - (0.002 if k1 == "end" else THICKNESS + 0.003)
        steps = max(1, int((t1 - t0) / 0.02))
        for j in range(steps + 1):
            t = t0 + (t1 - t0) * j / steps
            for h in (0.005, 0.04, min(0.075, height - 0.006)):
                total += 1
                o = a + d * t + n * 0.05 + UP * h
                hit = bvh.ray_cast(o, -n, 0.1)
                if hit[0] is None:
                    miss += 1
                elif abs(hit[3] - (0.05 - THICKNESS)) > 2e-4 or hit[1].dot(n) < 0.99:
                    wrong += 1
    result("every run covered", miss == 0 and wrong == 0,
           f"{total} rays, {miss} misses, {wrong} at the wrong depth or facing away")

    # face normals by region
    bad = {"front": 0, "back": 0, "arris": 0}
    counts = {"front": 0, "back": 0, "arris": 0, "other": 0}
    for poly in me.polygons:
        c = ob.matrix_world @ poly.center
        nn = (ob.matrix_world.to_3x3() @ poly.normal).normalized()
        k = slab_of(c, segs, height, tol=1e-4)
        if k is None:
            counts["other"] += 1
            continue
        _, _, a, _, d, n, length, k0, k1 = segs[k]
        t, s = (c - a).dot(d), (c - a).dot(n)
        beyond = t < -1e-4 or t > length + 1e-4
        if abs(nn.z) > 0.2:
            counts["other"] += 1
        elif beyond and s > THICKNESS * 0.5:
            counts["arris"] += 1
            bad["arris"] += nn.dot(n) < -1e-3  # faces outward (toward this leg's room side or the other's)
        elif s > THICKNESS - 5e-4:
            counts["front"] += 1
            bad["front"] += abs(nn.dot(d)) < 0.5 and nn.dot(n) < 0.99
        elif s < 5e-4 and abs(nn.dot(d)) < 0.5:
            counts["back"] += 1
            bad["back"] += nn.dot(n) > -0.99
        else:
            counts["other"] += 1
    result("normals face the rooms", not any(bad.values()), f"faces {counts}, wrong {bad}")

    # UV density along the run on front faces
    uv = me.uv_layers.active.data
    ratios = []
    for poly in me.polygons:
        nn = poly.normal
        if abs(nn.z) > 0.2:
            continue
        loops = list(poly.loop_indices)
        for i in range(len(loops)):
            l0, l1 = loops[i], loops[(i + 1) % len(loops)]
            p0, p1 = me.vertices[me.loops[l0].vertex_index].co, me.vertices[me.loops[l1].vertex_index].co
            e = p1 - p0
            if e.length > 0.05 and abs(e.z) < 1e-6:
                ratios.append(abs(uv[l1].uv.x - uv[l0].uv.x) / e.length)
    lo, hi = min(ratios), max(ratios)
    result("UVs along the run", abs(lo * BOARD - 1) < 0.02 and abs(hi * BOARD - 1) < 0.02,
           f"U per meter {lo:.4f}..{hi:.4f} (1 / {BOARD} = {1 / BOARD:.4f})")

    # joints
    worst = 9.0
    joints = 0
    for (ri, si, a, b, d, n, length, k0, k1) in segs:
        for j in joints_of(length, joint_offsets(length, ri * 7 + si)):
            joints += 1
            worst = min(worst, j, length - j)
    result("joints clear of corners and ends", worst >= JOINT_CLEAR, f"{joints} joints, nearest end {worst:.2f} m")
    return bvh


def check_casings(data, segs):
    """Import the door and window frames next to the open ends and probe them."""
    coll = bpy.data.collections.new("Frames")
    bpy.context.scene.collection.children.link(coll)
    for name, glb, pos, yaw in apartment_placements():
        if os.path.exists(glb):
            place(import_glb(glb, coll), name, g2b(pos), yaw, coll)
    bpy.context.view_layer.update()
    frames = [o for o in coll.all_objects if o.type == "MESH" and not o.name.endswith("-convcolonly")
              and "colonly" not in o.name]
    deps = bpy.context.evaluated_depsgraph_get()
    trees = []
    for o in frames:
        me = o.evaluated_get(deps).to_mesh()
        mw = o.matrix_world
        trees.append(BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons]))
        o.evaluated_get(deps).to_mesh_clear()

    def cast(o, direction, dist):
        best = None
        for tr in trees:
            hit = tr.ray_cast(o, direction, dist)
            if hit[0] is not None and (best is None or hit[3] < best):
                best = hit[3]
        return best

    ok, loose = True, []
    for (ri, si, a, b, d, n, length, k0, k1) in segs:
        for kind, p, out in ((k0, a, -d), (k1, b, d)):
            if kind != "end":
                continue
            gaps, prouds = [], []
            for h in (0.01, 0.04, 0.07):
                # Start 1 mm back inside the board, so a tight butt (gap 0) still hits the frame's side face.
                gap = cast(p + n * (THICKNESS * 0.5) + UP * h - out * 0.001, out, 0.051)
                depth = cast(p + out * 0.006 + n * 0.05 + UP * h, -n, 0.1)  # frame face 6 mm past the end
                if gap is not None:
                    gaps.append(max(0.0, gap - 0.001))
                if depth is not None:
                    prouds.append(0.05 - depth)
            where = f"run {ri} end at Godot ({p.x:.3f}, {-p.y:.3f})"
            if not gaps:  # no frame in front of the wall: the run file's cut is wider than the frame's room side
                loose.append(where)
                print(f"  INPUT WARNING {where}: no frame face in front of the wall within 50 mm of the end")
                continue
            fine = bool(prouds) and min(prouds) >= THICKNESS - 1e-4 and max(gaps) < 0.006
            ok &= fine
            print(f"  END {where}: gap to the frame {', '.join(f'{g * 1000:.1f}' for g in gaps)} mm, frame proud "
                  f"{', '.join(f'{pr * 1000:.1f}' for pr in prouds) or '-'} mm {'OK' if fine else 'CHECK'}")
    result("frames at the ends stand proud of the board", ok,
           f"({len(loose)} ends without a frame next to them: {'; '.join(loose)})" if loose else "")


def main():
    data = load_runs()
    bpy.ops.wm.open_mainfile(filepath=blend_path())
    segs = segments(data)
    obs = skirting_objects()
    result("one mesh", len(obs) == 1, f"{[o.name for o in obs]}")
    ob = obs[0]
    mats = [m.name for m in ob.data.materials]
    result("one material skirting_paint", mats == ["skirting_paint"], f"{mats}")
    imgs = sorted({f"{n.image.name} {n.image.size[0]}x{n.image.size[1]}" for m in ob.data.materials
                   for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    print(f"  images {imgs}")
    total = sum(length for *_, length, _, _ in segs)
    print(f"  {len(data['runs'])} runs, {len(segs)} segments, {total:.2f} m")
    check_mesh(ob, data, segs)
    tris = tri_count(ob)
    result("triangle budget", tris <= 10000, f"{tris} tris")
    check_casings(data, segs)
    print("CONTRACT", "OK" if not FAILS else f"FAIL {FAILS}")
    import_report(glb_path())


if __name__ == "__main__":
    main()
