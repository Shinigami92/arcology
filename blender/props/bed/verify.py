"""Stage 5: contract checks in the source (bounds, sleeping-surface height, headboard,
collision and its gap to the render surface), then re-import the glb.

  blender -b --factory-startup --python blender/props/bed/verify.py -- [--no-import]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import bed_common as C  # noqa: E402
import lib_candidates as L  # noqa: E402
from collision import surface_objects  # noqa: E402
from arcology_blender.checks import import_report  # noqa: E402
from arcology_blender.scene import script_args, tri_count  # noqa: E402

LIMIT_LO = Vector((-0.86, -1.08, 0.0))
LIMIT_HI = Vector((0.86, 1.08, 1.10))
# Seating area: along both long edges (foot half, below the turned-down fold) and the foot,
# 0.10-0.25 m in from the edge
SIT_POINTS = ([(sx * x, y) for sx in (-1, 1) for x in (0.58, 0.68) for y in (-0.65, -0.40, -0.15)]
              + [(x, -0.85) for x in (-0.4, 0.0, 0.4)])


def world_bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def godot(v):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    return (v.x, v.z, -v.y)


def fmt(t):
    return "(" + ", ".join(f"{c:.3f}" for c in t) + ")"


def tree_of(objs):
    verts, tris = [], []
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        off = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris)


def main():
    bpy.ops.wm.open_mainfile(filepath=C.BLEND)
    ok = True
    lo, hi = world_bounds(C.bed_objects())
    inside = all(LIMIT_LO[i] - 1e-4 <= lo[i] and hi[i] <= LIMIT_HI[i] + 1e-4 for i in range(3))
    ok &= inside
    print(f"BOUNDS bed lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if inside else 'OUT OF CONTRACT'}")
    for name, objs in (("frame", C.frame_objects()), ("linen", C.linen_objects()), ("throw", C.throw_objects())):
        a, b = world_bounds(objs)
        print(f"  {name:6s} lo={fmt(a)} hi={fmt(b)}")

    hb_top = world_bounds(C.frame_objects())[1].z
    good = 0.95 <= hb_top <= 1.10
    ok &= good
    print(f"HEADBOARD top {hb_top:.3f} m {'OK' if good else 'OUT OF 0.95-1.10'}")

    tree = tree_of(C.linen_objects() + C.throw_objects())
    hs = []
    for x, y in SIT_POINTS:
        hit = tree.ray_cast(Vector((x, y, 1.5)), Vector((0, 0, -1)))
        z = hit[0].z if hit[0] is not None else float("nan")
        hs.append(z)
        good = abs(z - C.SLEEP_TOP) <= 0.03
        ok &= good
        print(f"SLEEP z at x={x:+.2f} y={y:+.2f}: {z:.4f} m {'OK' if good else 'OUT OF 0.50 +- 0.03'}")
    print(f"SLEEP mean {sum(hs) / len(hs):.4f} min {min(hs):.4f} max {max(hs):.4f}")

    print("COLLISION (Godot bounds: center, size)")
    for ob in C.collision_objects():
        blo, bhi = world_bounds([ob])
        c, sz = (blo + bhi) / 2, bhi - blo
        print(f"  {ob.name:26s} tris={tri_count(ob):5d} center={fmt(godot(c))} size={fmt((sz.x, sz.z, sz.y))} "
              f"godot min={fmt((blo.x, blo.z, -bhi.y))} max={fmt((bhi.x, bhi.z, -blo.y))}")
    block = [o for o in C.collision_objects() if o.name.startswith("BedMattress")][0]
    print(f"BLOCK top {world_bounds([block])[1].z:.4f} m")

    # collider surface at the sit points
    top = [o for o in C.collision_objects() if o.name.endswith("-colonly") and not o.name.endswith("convcolonly")]
    ctree = tree_of(top)
    cz = [ctree.ray_cast(Vector((x, y, 1.5)), Vector((0, 0, -1)))[0].z for x, y in SIT_POINTS]
    good = all(abs(z - C.SLEEP_TOP) <= 0.03 for z in cz)
    ok &= good
    print(f"COLLIDER SLEEP mean {sum(cz) / len(cz):.4f} min {min(cz):.4f} max {max(cz):.4f} {'OK' if good else 'OUT'}")

    # gap between the render surface (visible from above) and the collider, 1 cm grid
    def classify(p):
        if p.z < C.PLAT_Z1 + 0.012:
            return "lip (frame, under hems; not gated)"
        if abs(p.x) > C.MAT_HALF_W - 0.02 or p.y < C.MAT_Y0 + 0.02:
            return "edges (hanging hems, lip)"
        if p.y > 0.50 and p.z > C.MAT_Z1 + 0.04:
            return "pillows"
        return "top (duvet, fold, throw, sheet)"

    colliders = top + [o for o in C.collision_objects() if o.name.startswith("BedBase")]
    res = L.surface_gap(surface_objects(), colliders, C.COL_TOP_LO, C.COL_TOP_HI, 0.01, classify)
    allg = []
    for region, vals in sorted(res.items()):
        g = sorted(v[0] for v in vals)
        dz = sorted(v[1] for v in vals if v[1] == v[1])
        if not region.startswith("lip"):
            allg += g
        n = len(g)
        within5 = sum(1 for x in g if x <= 0.005) / n
        worst = max(vals, key=lambda v: v[0])
        print(f"GAP {region:32s} n={n:6d} max={g[-1] * 1000:5.1f} mm p99={g[int(n * 0.99)] * 1000:4.1f} "
              f"p95={g[int(n * 0.95)] * 1000:4.1f} mean={sum(g) / n * 1000:4.2f} <=5mm {within5 * 100:5.1f}% "
              f"vertical dz min={dz[0] * 1000:+6.1f} max={dz[-1] * 1000:+6.1f} mm worst at {fmt(worst[2])}")
    good = max(allg) < 0.01
    ok &= good
    print(f"GAP bedding max {max(allg) * 1000:.1f} mm {'OK' if good else 'OVER 10 mm'}")
    # what an object actually feels: a 10 mm probe sphere lowered onto the render surface
    res = L.probe_gap(surface_objects(), colliders, C.COL_TOP_LO, C.COL_TOP_HI, 0.005, 0.010, classify)
    allp = []
    for region, vals in sorted(res.items()):
        g = sorted(v[0] for v in vals)
        if not region.startswith("lip"):
            allp += g
        n = len(g)
        worst = max(vals, key=lambda v: v[0])
        print(f"PROBE10 {region:32s} n={n:6d} max={g[-1] * 1000:5.1f} mm p99={g[int(n * 0.99)] * 1000:4.1f} "
              f"p95={g[int(n * 0.95)] * 1000:4.1f} mean={sum(g) / n * 1000:4.2f} "
              f"<=5mm {sum(1 for x in g if x <= 0.005) / n * 100:5.1f}% worst at {fmt(worst[1])}")
    good = max(allp) < 0.01
    ok &= good
    print(f"PROBE10 overall max {max(allp) * 1000:.1f} mm {'OK' if good else 'OVER 10 mm'}")

    for ob in C.bed_objects():
        mats = [m.name for m in ob.data.materials]
        print(f"OBJECT {ob.name:10s} tris={tri_count(ob)} mats={mats} attrs={[a.name for a in ob.data.attributes if not a.name.startswith('.')]}")
    print(f"TRIS bed={sum(tri_count(o) for o in C.bed_objects())}")
    print("CONTRACT", "OK" if ok else "FAIL")
    if "--no-import" not in script_args():
        import_report(C.GLB)


if __name__ == "__main__":
    main()
