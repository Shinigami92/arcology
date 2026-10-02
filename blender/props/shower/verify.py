"""Stage 5: contract checks in the source (bounds, glass pane, pivots and collision in Godot
coordinates, lever/dial sweeps, hand shower lift-out), then re-import the glb files.

  blender -b --factory-startup --python blender/props/shower/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import shower_common as C  # noqa: E402
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, inside, local_bounds, slide_clearance,
    world_bounds,
)
from arcology_blender.scene import tri_count  # noqa: E402


def glass_report(glass):
    bm = bmesh.new()
    bm.from_mesh(glass.data)
    bm.normal_update()
    normals = {tuple(round(c, 4) for c in f.normal) for f in bm.faces}
    ys = {round(v.co.y, 6) for v in bm.verts}
    single = len(normals) == 1 and len(ys) == 1
    bm.free()
    lo, hi = world_bounds([glass])
    mats = [m.name for m in glass.data.materials]
    print(f"GLASS faces={len(glass.data.polygons)} tris={tri_count(glass)} normals={normals} plane_y={ys} "
          f"materials={mats} {'single layer OK' if single else 'NOT A SINGLE LAYER'}")
    print(f"  extent Blender x {lo.x:.3f}..{hi.x:.3f} z {lo.z:.3f}..{hi.z:.3f}; Godot center={fmt(godot((lo + hi) / 2))} "
          f"size={fmt(godot_size(hi - lo))}")
    return single and mats == [C.GLASS_MAT]


def part_report(name, root, objs):
    lo, hi = local_bounds(root)
    grip = [o for o in objs if o.type == "EMPTY"]
    print(f"PART {name}: origin Godot {fmt(godot(root.matrix_world.translation))} rot_deg={fmt([r * 57.29578 for r in root.rotation_euler], 1)} "
          f"local bounds Godot lo={fmt(godot(lo))} hi={fmt(godot(hi))} size={fmt(godot_size(hi - lo))} "
          f"tris={sum(tri_count(o) for o in objs if o.type == 'MESH')} grip={[fmt(godot(g.location)) for g in grip]}")


def main():
    bpy.ops.wm.open_mainfile(filepath=C.BLEND)
    body, glass = C.body_objects(), C.glass_objects()
    lo, hi = world_bounds(body + glass)
    ok = inside(lo, hi, C.LIMIT_LO, C.LIMIT_HI)
    print(f"BOUNDS lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if ok else 'OUT OF CONTRACT'}")
    ok &= glass_report(glass[0])
    collision_report(C.collision_objects())
    flow, temp, hand = (bpy.data.objects[n] for n in ("MixerFlow", "MixerTemp", "Handheld"))
    part_report("flow", flow, C.flow_objects())
    part_report("temp", temp, C.temp_objects())
    part_report("handheld", hand, C.handheld_objects())
    print(f"SHELF top z={C.SHELF_TOP} Blender x {C.SHELF_X0}..{C.HX} y {C.SHELF_Y0:.2f}..{C.BACK_Y}")
    tris = {"body": sum(tri_count(o) for o in body), "glass": sum(tri_count(o) for o in glass),
            "flow": sum(tri_count(o) for o in C.flow_objects() if o.type == "MESH"),
            "temp": sum(tri_count(o) for o in C.temp_objects() if o.type == "MESH"),
            "handheld": sum(tri_count(o) for o in C.handheld_objects() if o.type == "MESH")}
    print(f"TRIS {tris} total={sum(tris.values())}")

    fixed = body + [temp]
    print(f"FLOW LEVER SWEEP (+-{C.FLOW_TRAVEL} deg about the wall normal) vs body + dial")
    bad = hinge_clearance(flow, [flow], fixed, angles=range(-int(C.FLOW_TRAVEL), int(C.FLOW_TRAVEL) + 1, 15),
                          axis="Y", sign=-1.0, contact=0.0003)
    print(f"DIAL SWEEP (+-{C.TEMP_TRAVEL} deg) vs body + lever")
    bad += hinge_clearance(temp, [temp], body + [flow], angles=range(-int(C.TEMP_TRAVEL), int(C.TEMP_TRAVEL) + 1, 30),
                           axis="Y", sign=-1.0, contact=0.0003)
    a = C.HAND_ROT.to_3x3() @ Vector((0.0, 0.0, 1.0))
    print("HAND SHOWER LIFT-OUT (along its handle axis) vs body")
    lift = slide_clearance(hand, [hand], body, a, 0.20, steps=8, contact=0.0001)
    ok &= not bad and not lift
    print("CONTRACT", "OK" if ok else "FAIL")
    for path in (C.GLB_BODY, C.GLB_FLOW, C.GLB_TEMP, C.GLB_HANDHELD):
        import_report(path)


if __name__ == "__main__":
    main()
