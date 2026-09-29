"""Stage 5: contract checks in the source (bounds, sleeping surface, collision), then re-import the glb.

  blender -b --factory-startup --python blender/props/bed__fable-high/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from bed_common import (  # noqa: E402
    BLEND, GLB, HEAD_Z1, LIMIT_X, LIMIT_Y, SIT_POINTS, SLEEP_TOP, bed_objects, bedding_objects, collision_objects,
)
from arcology_blender.checks import import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402


def world_bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def godot(v):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    return (v.x, v.z, -v.y)


def fmt(t):
    return "(" + ", ".join(f"{c:.3f}" for c in t) + ")"


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    ok = True
    lo, hi = world_bounds(bed_objects())
    inside = (lo.x >= -LIMIT_X - 1e-4 and hi.x <= LIMIT_X + 1e-4 and lo.y >= -LIMIT_Y - 1e-4
              and hi.y <= LIMIT_Y + 1e-4 and lo.z >= -1e-4 and 0.95 <= hi.z <= 1.10)
    ok &= inside
    print(f"BOUNDS bed lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if inside else 'OUT OF CONTRACT'}")
    print(f"HEADBOARD top {hi.z:.3f} (panel {HEAD_Z1:.3f})")

    bed = bedding_objects()[0]
    me = bed.data
    me.calc_loop_triangles()
    tree = BVHTree.FromPolygons([bed.matrix_world @ v.co for v in me.vertices],
                                [t.vertices for t in me.loop_triangles])
    for x, y in SIT_POINTS:
        hit = tree.ray_cast(Vector((x, y, 1.5)), Vector((0, 0, -1)))
        z = hit[0].z if hit[0] is not None else float("nan")
        good = abs(z - SLEEP_TOP) <= 0.03
        ok &= good
        print(f"SURFACE z at x={x:+.2f} y={y:+.2f}: {z:.4f} m {'OK' if good else 'OUT OF 0.50 +- 0.03'}")

    print("COLLISION (Godot center, size)")
    for ob in collision_objects():
        blo, bhi = world_bounds([ob])
        c, s = (blo + bhi) / 2, bhi - blo
        print(f"  {ob.name:22s} center={fmt(godot(c))} size={fmt((s.x, s.z, s.y))}")

    print(f"TRIS bed={sum(tri_count(o) for o in bed_objects())}")
    print("CONTRACT", "OK" if ok else "FAIL")
    import_report(GLB)


if __name__ == "__main__":
    main()
