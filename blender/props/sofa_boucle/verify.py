"""Stage 5: contract checks on the source (bounds, seat height, pillow size), then re-import the glb files.

  blender -b --factory-startup --python blender/props/sofa_boucle/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sofa_common import (  # noqa: E402
    BLEND, GLB_PILLOW, GLB_SOFA, HX, HY, PILLOW_MASS, SEAT_TOP, pillow_objects, sofa_collision_objects,
    sofa_objects,
)
from arcology_blender.checks import import_report  # noqa: E402


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    ok = True
    lo, hi = bounds(sofa_objects())
    print(f"SOFA bounds x {lo.x:.3f}..{hi.x:.3f}  y {lo.y:.3f}..{hi.y:.3f}  z {lo.z:.3f}..{hi.z:.3f}")
    if lo.x < -HX - 0.02 or hi.x > HX + 0.02 or lo.y < -0.46 or hi.y > 0.46 or lo.z < -0.001 or hi.z > 0.90:
        print("  FAIL: outside the contract envelope")
        ok = False
    # Seat surface: highest point of each seat cushion, and the sag center.
    for ob in sofa_objects():
        if "SeatCushion" not in ob.name:
            continue
        top = max((ob.matrix_world @ v.co).z for v in ob.data.vertices)
        cx = ob.location.x if ob.location.x else sum(v.co.x for v in ob.data.vertices) / len(ob.data.vertices)
        center = [(ob.matrix_world @ v.co) for v in ob.data.vertices]
        mid = min((p for p in center if p.z > 0.40), key=lambda p: (p.x - cx) ** 2 + (p.y + 0.16) ** 2)
        print(f"  {ob.name}: top {top:.3f} m, sag center {mid.z:.3f} m")
        if abs(top - SEAT_TOP) > 0.02 or abs(mid.z - SEAT_TOP) > 0.02:
            print("  FAIL: seat surface outside 0.44 +- 0.02")
            ok = False
    plo, phi = bounds(pillow_objects())
    print(f"PILLOW size {phi.x - plo.x:.3f} x {phi.y - plo.y:.3f} x {phi.z - plo.z:.3f} m, "
          f"center offset ({(plo.x + phi.x) / 2:.3f}, {(plo.y + phi.y) / 2:.3f}, {(plo.z + phi.z) / 2:.3f}), mass {PILLOW_MASS} kg")
    print("COLLISION (Godot: center x, y, z / size x, y, z; Blender (x, y, z) -> Godot (x, z, -y))")
    for ob in sorted(sofa_collision_objects(), key=lambda o: o.name):
        lo, hi = bounds([ob])
        c, s = (lo + hi) / 2, hi - lo
        print(f"  {ob.name:24s} center=({c.x:.3f}, {c.z:.3f}, {-c.y:.3f}) size=({s.x:.3f}, {s.z:.3f}, {s.y:.3f})")
    print("CONTRACT", "OK" if ok else "FAIL")
    import_report(GLB_SOFA)
    import_report(GLB_PILLOW)


if __name__ == "__main__":
    main()
