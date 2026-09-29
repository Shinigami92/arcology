"""Stage 5: contract checks in the source (bounds, door swing, drawer travel, part frames),
then re-import every glb.

  blender -b --factory-startup --python blender/props/wardrobe__opus-high/verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import wardrobe_common as C  # noqa: E402
from arcology_blender.checks import hinge_clearance, import_report, slide_clearance  # noqa: E402
from arcology_blender.scene import part_objects, tri_count  # noqa: E402


def world_bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs if o.type == "MESH" for v in o.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def local_bounds(ob):
    pts = [v.co for v in ob.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def godot(v):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    return (v[0], v[2], -v[1])


def fmt(t):
    return "(" + ", ".join(f"{c:.4f}" for c in t) + ")"


def box_line(name, lo, hi):
    """A box in Blender coordinates, reported as a Godot size and center."""
    lo, hi = Vector(lo), Vector(hi)
    size = hi - lo
    return f"    {name:12s} godot size {fmt((size.x, size.z, size.y))} center {fmt(godot((lo + hi) / 2))}"


def meshes(objs):
    return [o for o in objs if o.type == "MESH"]


def main():
    bpy.ops.wm.open_mainfile(filepath=C.BLEND)
    body = C.body_objects()
    lo, hi = world_bounds(body)
    ok_bounds = (lo.x >= -C.BX - 1e-4 and hi.x <= C.BX + 1e-4 and lo.y >= -C.BY - 1e-4 and hi.y <= C.BY + 1e-4
                 and lo.z >= -1e-4 and hi.z <= C.BODY_H + 1e-4)
    print(f"BODY bounds {fmt(lo)} .. {fmt(hi)} {'OK' if ok_bounds else 'OUTSIDE CONTRACT'}")
    for ob in C.body_collision_objects():
        a, b = local_bounds(ob)
        print(f"  COL {ob.name:28s} size(godot) {fmt(((b - a).x, (b - a).z, (b - a).y))} center(godot) {fmt(godot((a + b) / 2))}")

    drawers = [bpy.data.objects["Drawer"], bpy.data.objects["DrawerRight"]]
    props = meshes(C.prop_objects()) + [drawers[1]] + meshes(part_objects("instance"))
    props = list(dict.fromkeys(props))
    fails = {}
    doors = {}
    for label, sign, objs in (("Left", -1.0, C.door_left_objects), ("Right", 1.0, C.door_right_objects)):
        root = bpy.data.objects[f"Door{label}"]
        doors[label] = (root, sign)
        print(f"DOOR {label} swing (sign {sign:+.0f}) vs body and closed drawers, box, hangers")
        bad = hinge_clearance(root, objs(), body + props, angles=range(0, int(C.OPEN_DEG) + 1, 5), sign=sign)
        fails[f"door_{label}"] = bad

    # Drawer travel with both doors open 100 degrees
    for root, sign in doors.values():
        root.rotation_euler = (0.0, 0.0, math.radians(sign * C.RENDER_DEG))
    bpy.context.view_layer.update()  # slide_clearance reads matrix_world for the fixed parts
    door_meshes = meshes(C.door_left_objects() + C.door_right_objects())
    for d in drawers:
        fixed = body + door_meshes + [o for o in props if o is not d]
        print(f"DRAWER {d.name} travel along -Y to {C.DRAWER_TRAVEL} m (doors at {C.RENDER_DEG:.0f} deg)")
        fails[d.name] = slide_clearance(d, [d], fixed, (0.0, -1.0, 0.0), C.DRAWER_TRAVEL, steps=16)
    for root, _ in doors.values():
        root.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    print("CLEARANCE", "OK" if not any(fails.values()) else f"FAIL {fails}")

    # Part frames for the Godot side
    print("DRAWERS (drawer-local, origin at the front's outer face, bottom center)")
    for d in drawers:
        print(f"  {d.name} closed origin blender {fmt(d.location)} godot {fmt(godot(d.location))}")
    grip = bpy.data.objects["HandleGrip.D"]
    print(f"  HandleGrip local blender {fmt(grip.location)} godot {fmt(godot(grip.location))}")
    hw, bw, w = C.DR_FRONT_HW, C.DR_BOX_HW, C.DR_WALL
    y0, y1, z0, z1 = C.DR_BOX_Y0, C.DR_BOX_Y1, C.DR_BOX_Z0, C.DR_BOX_Z1
    print(f"  inner box (clear) {2 * (bw - w):.4f} W x {y1 - y0 - 2 * w:.4f} D x {z1 - z0 - C.DR_FLOOR:.4f} H "
          f"(floor top at local z {z0 + C.DR_FLOOR:.4f})")
    print("  collision (drawer-local, Godot):")
    print(box_line("Front", (-hw, 0.0, 0.0), (hw, C.DR_FRONT_T, C.DR_FRONT_H)))
    print(box_line("Floor", (-bw, y0, z0), (bw, y1, z0 + C.DR_FLOOR)))
    print(box_line("WallLeft", (-bw, y0, z0), (-bw + w, y1, z1)))
    print(box_line("WallRight", (bw - w, y0, z0), (bw, y1, z1)))
    print(box_line("WallFront", (-bw + w, y0, z0), (bw - w, y0 + w, z1)))
    print(box_line("WallBack", (-bw + w, y1 - w, z0), (bw - w, y1, z1)))

    print("BOX / LID")
    for name in ("Box", "Lid"):
        ob = bpy.data.objects[name]
        a, b = local_bounds(ob)
        print(f"  {name} origin blender {fmt(ob.location)} godot {fmt(godot(ob.location))} "
              f"size(godot) {fmt(((b - a).x, (b - a).z, (b - a).y))} tris {tri_count(ob)}")
    bx, by, bz = C.BOX_SIZE
    bwl = C.BOX_WALL
    print("  box collision (box-local, Godot):")
    print(box_line("Floor", (-bx / 2, -by / 2, 0.0), (bx / 2, by / 2, bwl)))
    print(box_line("WallLeft", (-bx / 2, -by / 2, 0.0), (-bx / 2 + bwl, by / 2, bz)))
    print(box_line("WallRight", (bx / 2 - bwl, -by / 2, 0.0), (bx / 2, by / 2, bz)))
    print(box_line("WallFront", (-bx / 2 + bwl, -by / 2, 0.0), (bx / 2 - bwl, -by / 2 + bwl, bz)))
    print(box_line("WallBack", (-bx / 2 + bwl, by / 2 - bwl, 0.0), (bx / 2 - bwl, by / 2, bz)))
    lx, ly, lz = C.LID_SIZE
    print(box_line("LidTop", (-lx / 2, -ly / 2, lz - C.LID_TOP), (lx / 2, ly / 2, lz)))

    print("HANGERS (hanger-local, origin at the hook's resting point)")
    print(f"  rail endpoints godot {fmt(godot((-C.IN_X + 0.001, C.RAIL_Y, C.RAIL_Z)))} .. "
          f"{fmt(godot((C.IN_X - 0.001, C.RAIL_Y, C.RAIL_Z)))} radius {C.RAIL_R}")
    for part in ("hanger", "hanger_a", "hanger_b"):
        ob = bpy.data.objects[C.PROPS[part][0]]
        a, b = local_bounds(ob)
        print(f"  {ob.name:13s} local bounds blender {fmt(a)} .. {fmt(b)} tris {tri_count(ob)}")
    for i, x in enumerate(C.HANGERS_X):
        kind = "shirt_a" if i == C.SHIRTS[0] else "shirt_b" if i == C.SHIRTS[1] else "bare"
        p = (x, C.RAIL_Y, C.RAIL_Z + C.RAIL_R)
        print(f"  slot {i}: {kind:7s} origin godot {fmt(godot(p))} rotation_degrees (0, {C.HANGER_ROT_Z:.0f}, 0)")

    total = sum(tri_count(o) for o in set(body + door_meshes + meshes(C.prop_objects()) + [drawers[1]]
                                            + meshes(part_objects("instance"))))
    print(f"TOTAL render tris with instances (2 drawers, 4 bare hangers): {total}")

    for path in (C.GLB_BODY, C.GLB_DOOR_L, C.GLB_DOOR_R) + tuple(p for _, p in C.PROPS.values()):
        import_report(path)


if __name__ == "__main__":
    main()
