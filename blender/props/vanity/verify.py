"""Stage 5: contract checks in the source (bounds, top height, basin, drawer travel, lever
travel, collision sizes in Godot axes), then re-import every glb.

  blender -b --factory-startup --python blender/props/vanity/verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from vanity_common import (  # noqa: E402
    BASIN_C, BLEND, BOTTOM_DRAWER_ORIGIN, DISPENSER_POS, DRAWER_TRAVEL, GLB_BODY, GLB_DISPENSER,
    GLB_DRAWER_BOTTOM, GLB_DRAWER_TOP, GLB_LEVER, LEVER_LIFT, LEVER_PIVOT, LEVER_SWING, LIMIT_HI, LIMIT_LO, MAX_Z,
    TOP_DRAWER_ORIGIN, TOP_Z1, body_objects, collision_objects, dispenser_objects, drawer_bottom_objects,
    drawer_collision, drawer_top_objects, fixture_objects, lever_objects,
)
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, inside, slide_clearance, world_bounds,
)
from arcology_blender.geo import bvh  # noqa: E402
from arcology_blender.scene import meshes, tri_count  # noqa: E402


def tris(objs):
    return sum(tri_count(o) for o in objs)


def local_collision(name, objs, origin):
    print(f"COLLISION {name} (Godot, drawer-local: center, size)")
    for ob in sorted(objs, key=lambda o: o.name):
        lo, hi = world_bounds([ob])
        c = (lo + hi) / 2 - origin
        print(f"  {ob.name:28s} center={fmt(godot(c))} size={fmt(godot_size(hi - lo))}")


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    static = body_objects() + fixture_objects()
    top, bottom = bpy.data.objects["DrawerTop"], bpy.data.objects["DrawerBottom"]
    lever = bpy.data.objects["Lever"]
    allr = static + meshes(drawer_top_objects() + drawer_bottom_objects() + lever_objects())
    lo, hi = world_bounds(allr)
    ok = inside(lo, hi, LIMIT_LO, LIMIT_HI)
    print(f"BOUNDS lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if ok else 'OUT OF CONTRACT'}")

    # Top surface and basin (vertical rays on the static meshes)
    tree = bvh(meshes(static))
    down = Vector((0, 0, -1))
    for x, y in ((-0.5, -0.30), (0.5, -0.40), (0.42, -0.24), (0.0, -0.48)):
        h = tree.ray_cast(Vector((x, y, 2.0)), down)
        print(f"TOP SURFACE at ({x:+.2f},{y:+.2f}) z={h[0].z:.4f}")
    for dx in (0.0, 0.06, 0.12):
        h = tree.ray_cast(Vector((BASIN_C.x + dx, BASIN_C.y, 2.0)), down)
        print(f"BASIN at x+{dx:.2f} z={h[0].z:.4f} depth below top={TOP_Z1 - h[0].z:.4f}")
    print(f"BASIN CENTER Godot={fmt(godot((BASIN_C.x, BASIN_C.y, 0.0)))}")

    # Drawer travel (each drawer against the static body, the other drawer closed, the lever)
    ok_all = ok
    for name, root, other in (("top", top, bottom), ("bottom", bottom, top)):
        print(f"DRAWER {name} TRAVEL")
        fixed = static + meshes([other]) + meshes(lever_objects())
        bad = slide_clearance(root, [root], fixed, (0, -1, 0), DRAWER_TRAVEL, steps=8)
        print("CLEARANCE", name, "OK" if not bad else f"FAIL {bad}")
        ok_all = ok_all and not bad

    # Lever: lift (about local X, negative) and swing (about local up) clear the mixer
    print("LEVER LIFT")
    bad = hinge_clearance(lever, [lever], fixture_objects() + body_objects(), range(0, int(LEVER_LIFT) + 1, 5),
                          axis="X", sign=-1.0)
    for sign in (-1.0, 1.0):
        print(f"LEVER SWING {'hot (left)' if sign < 0 else 'cold (right)'}")
        bad += hinge_clearance(lever, [lever], fixture_objects() + body_objects(),
                               range(0, int(LEVER_SWING) + 1, 10), axis="Z", sign=sign)
    print("CLEARANCE lever", "OK" if not bad else f"FAIL {bad}")
    ok_all = ok_all and not bad
    lever.rotation_euler = (math.radians(-LEVER_LIFT), 0.0, math.radians(LEVER_SWING))
    bpy.context.view_layer.update()
    lo2, hi2 = world_bounds(meshes(lever_objects()))
    print(f"LEVER lifted+swung max z={hi2.z:.4f} (limit {MAX_Z})")
    ok_all = ok_all and hi2.z < MAX_Z
    lever.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    print(f"LEVER PIVOT Godot={fmt(godot(LEVER_PIVOT), 4)}")

    for name, root, origin in (("top", top, TOP_DRAWER_ORIGIN), ("bottom", bottom, BOTTOM_DRAWER_ORIGIN),
                               ("lever", lever, LEVER_PIVOT)):
        grip = [c for c in root.children if c.name.startswith("HandleGrip")][0]
        print(f"GRIP {name} local Godot={fmt(godot(grip.location), 4)} vanity Godot="
              f"{fmt(godot(grip.matrix_world.translation), 4)}")
    for name, origin in (("top", TOP_DRAWER_ORIGIN), ("bottom", BOTTOM_DRAWER_ORIGIN)):
        print(f"DRAWER {name} origin Godot={fmt(godot(origin), 4)}")
        local_collision(f"drawer_{name}", drawer_collision(name), origin)
    collision_report(collision_objects())
    disp = meshes(dispenser_objects())
    dlo, dhi = world_bounds(disp)
    print(f"DISPENSER at Godot={fmt(godot(DISPENSER_POS))} size={fmt(godot_size(dhi - dlo))}")

    print(f"TRIS body={tris(body_objects())} fixture={tris(fixture_objects())} "
          f"drawer_top={tris(drawer_top_objects())} drawer_bottom={tris(drawer_bottom_objects())} "
          f"lever={tris(lever_objects())} dispenser={tris(dispenser_objects())} collision={tris(collision_objects())}")
    print("CONTRACT", "OK" if ok_all else "FAIL")
    for glb in (GLB_BODY, GLB_DRAWER_TOP, GLB_DRAWER_BOTTOM, GLB_LEVER, GLB_DISPENSER):
        import_report(glb)


if __name__ == "__main__":
    main()
