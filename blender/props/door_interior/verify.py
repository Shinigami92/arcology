"""Stage 5: contract checks (opening, gaps, swing clearance 0..100 deg with the hardware mounted),
Godot numbers for the scene (hinge, leaf box, grips, sockets, frame colliders), then re-import the glbs.

  blender -b --factory-startup --python blender/props/door_interior/verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from door_interior_common import (  # noqa: E402
    BLEND, GLB_FRAME, GLB_LEAF, GLB_LEVER, GLB_THUMBTURN, HEAD_Z, HINGE, JAMB_X, OPEN_DEG, OPEN_H, OPEN_X, WALL_Y,
    frame_collision_objects, frame_objects, leaf_objects, lever_objects, mount_hardware, thumbturn_objects,
)
from lib_candidates import wall_with_opening  # noqa: E402
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, local_bounds, world_bounds,
)
from arcology_blender.geo import bm_box, new_object  # noqa: E402
from arcology_blender.scene import get_collection, meshes, tri_count  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    ok = True
    leaf = bpy.data.objects["Leaf"]
    frame = frame_objects()

    lo, hi = world_bounds(frame)
    print(f"FRAME bounds lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)}")
    lining = bpy.data.objects["Lining"]
    llo, lhi = world_bounds([lining])
    print(f"LINING outer x={llo.x:.4f}..{lhi.x:.4f} top={lhi.z:.4f} depth y={llo.y:.4f}..{lhi.y:.4f}")
    ok &= abs(llo.x + OPEN_X) < 1e-4 and abs(lhi.x - OPEN_X) < 1e-4 and abs(lhi.z - OPEN_H) < 1e-4
    ok &= abs(llo.y + WALL_Y) < 1e-4 and abs(lhi.y - WALL_Y) < 1e-4

    slab = leaf
    slo, shi = local_bounds(slab)
    print(f"LEAF slab local lo={fmt(slo, 4)} hi={fmt(shi, 4)} size={fmt(shi - slo, 4)}")
    wlo, whi = world_bounds([slab])
    print(f"LEAF gaps: hinge side {wlo.x + JAMB_X:.4f}, latch side {JAMB_X - whi.x:.4f}, head {HEAD_Z - whi.z:.4f}, "
          f"floor {wlo.z:.4f}")

    hardware = mount_hardware()
    moving = meshes(leaf_objects()) + hardware
    print("SWING (leaf + levers + thumb-turn vs frame)")
    bad = hinge_clearance(leaf, moving, frame, angles=range(0, int(OPEN_DEG) + 1, 5))
    ok &= not bad

    # Against the wall around the opening and a perpendicular wall 0.25 m from the hinge side.
    coll = get_collection("VerifyWall")
    bm = bmesh.new()
    wall_with_opening(bm, -1.5, 1.5, 2.6, -WALL_Y, WALL_Y, -OPEN_X, OPEN_X, OPEN_H)
    bm_box(bm, (-OPEN_X - 0.25 - 0.1, -1.2, 0.0), (-OPEN_X - 0.25, -WALL_Y, 2.6))
    wall = new_object("VerifyWall", bm, coll)
    print("SWING (leaf + hardware vs wall and a side wall at 0.25 m)")
    bad_wall = hinge_clearance(leaf, moving, [wall], angles=(0, 45, 90, 100))
    ok &= not bad_wall
    leaf.rotation_euler = (0, 0, math.radians(-OPEN_DEG))
    bpy.context.view_layer.update()
    olo, ohi = world_bounds(moving)
    print(f"OPEN {OPEN_DEG:.0f} deg leaf+hardware world lo={fmt(olo)} hi={fmt(ohi)}")
    leaf.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    collision_report(frame_collision_objects())

    print("GODOT (frame origin = bottom center of the opening, wall center plane; leaf opens toward +Z)")
    print(f"  hinge axis           {fmt(godot(HINGE), 4)}  (vertical, Godot Y)")
    c = (slo + shi) / 2
    print(f"  leaf box (leaf-local) center={fmt(godot(c), 4)} size={fmt(godot_size(shi - slo), 4)}")
    for e in sorted((o for o in leaf_objects() if o.type == "EMPTY"), key=lambda o: o.name):
        rot = tuple(round(math.degrees(a), 1) for a in e.rotation_euler)
        print(f"  {e.name:20s} leaf-local={fmt(godot(e.location), 4)} frame={fmt(godot(e.location + HINGE), 4)}"
              f" rot(blender)={rot}")
    lever = bpy.data.objects["Lever"]
    a, b = (godot(v) for v in local_bounds(lever))
    lo_g, hi_g = [min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]
    print(f"  lever extent (glb)   lo={fmt(lo_g, 4)} hi={fmt(hi_g, 4)}")
    print("TRIS frame={} collision={} leaf={} lever={} thumbturn={}".format(
        sum(tri_count(o) for o in frame), sum(tri_count(o) for o in frame_collision_objects()),
        sum(tri_count(o) for o in meshes(leaf_objects())), sum(tri_count(o) for o in lever_objects()),
        sum(tri_count(o) for o in thumbturn_objects())))
    print("CONTRACT", "OK" if ok else f"FAIL swing={bad} wall={bad_wall}")
    for glb in (GLB_FRAME, GLB_LEAF, GLB_LEVER, GLB_THUMBTURN):
        if os.path.exists(glb):
            import_report(glb)


if __name__ == "__main__":
    main()
