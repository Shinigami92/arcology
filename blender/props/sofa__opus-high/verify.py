"""Stage 5: contract checks in the source (bounds, seat height, collision, pillow), then re-import the glbs.

  blender -b --factory-startup --python blender/props/sofa__opus-high/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from sofa_common import (  # noqa: E402
    BLEND, GLB_PILLOW, GLB_SOFA, SEAT_TOP, SEAT_X, SIT_Y, collision_objects, cushion_objects,
    pillow_objects, sofa_objects,
)
from arcology_blender.checks import import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

LIMIT_LO, LIMIT_HI = Vector((-1.07, -0.46, 0.0)), Vector((1.07, 0.46, 0.90))


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
    lo, hi = world_bounds(sofa_objects())
    inside = all(LIMIT_LO[i] - 1e-4 <= lo[i] and hi[i] <= LIMIT_HI[i] + 1e-4 for i in range(3))
    ok &= inside
    print(f"BOUNDS sofa lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if inside else 'OUT OF CONTRACT'}")

    cush = cushion_objects()[0]
    me = cush.data
    me.calc_loop_triangles()
    tree = BVHTree.FromPolygons([cush.matrix_world @ v.co for v in me.vertices],
                                [t.vertices for t in me.loop_triangles])
    heights = []
    for x in SEAT_X:
        for y in (SIT_Y, SIT_Y - 0.1, SIT_Y + 0.1):
            hit = tree.ray_cast(Vector((x, y, 1.2)), Vector((0, 0, -1)))
            # the first hit from above over the seat may be a back cushion; seats are below 0.5 m
            z = hit[0].z if hit[0] is not None else float("nan")
            if z > 0.5:
                hit = tree.ray_cast(Vector((x, y, 0.5)), Vector((0, 0, -1)))
                z = hit[0].z
            heights.append((x, y, z))
    for x, y, z in heights:
        good = abs(z - SEAT_TOP) <= 0.02
        ok &= good
        print(f"SEAT z at x={x:+.3f} y={y:+.3f}: {z:.4f} m {'OK' if good else 'OUT OF 0.44 +- 0.02'}")

    print("COLLISION (Godot center, size)")
    for ob in collision_objects():
        blo, bhi = world_bounds([ob])
        c, s = (blo + bhi) / 2, bhi - blo
        print(f"  {ob.name:22s} center={fmt(godot(c))} size={fmt((s.x, s.z, s.y))}")

    p = pillow_objects()[0]
    plo, phi = world_bounds([p])
    print(f"PILLOW lo={fmt(plo)} hi={fmt(phi)} size={fmt(phi - plo)} center={fmt((plo + phi) / 2)} "
          f"tris={tri_count(p)}")
    print(f"TRIS sofa={sum(tri_count(o) for o in sofa_objects())}")
    print("CONTRACT", "OK" if ok else "FAIL")
    import_report(GLB_SOFA)
    import_report(GLB_PILLOW)


if __name__ == "__main__":
    main()
