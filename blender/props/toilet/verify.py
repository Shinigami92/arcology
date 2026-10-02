"""Stage 5: contract checks in the source (bounds, shelf and seat heights, hinge
stops, button travel, roll on the holder, Godot numbers), then re-import the glbs.

  blender -b --factory-startup --python blender/props/toilet/verify.py

Godot numbers are in the toilet's local frame: Blender (x, y, z) -> Godot (x, z, -y).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import toilet_common as C  # noqa: E402
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, inside, local_bounds,
    slide_clearance, world_bounds,
)
from arcology_blender.scene import part_objects, tri_count  # noqa: E402


def first_contact(root, moving, fixed, start, stop, step=0.5):
    """Smallest opening angle in [start, stop] that touches `fixed` (None if clear)."""
    angles = [start + i * step for i in range(int((stop - start) / step) + 1)]
    bad = hinge_clearance(root, moving, fixed, angles, axis="X", sign=-1.0)
    return min(bad) if bad else None


def main():
    bpy.ops.wm.open_mainfile(filepath=C.BLEND)
    ok = True
    body = C.body_objects()
    lo, hi = world_bounds(body)
    inb = inside(lo, hi, C.LIMIT_LO, C.LIMIT_HI)
    ok &= inb
    print(f"BOUNDS body lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if inb else 'OUT OF CONTRACT'}")
    shelf = bpy.data.objects["Shelf"]
    print(f"SHELF top z={world_bounds([shelf])[1].z:.4f} (Godot y)")
    bowl = bpy.data.objects["Bowl"]
    blo, bhi = world_bounds([bowl])
    print(f"BOWL rim z={bhi.z:.4f} front y={blo.y:.4f} projection from box face={C.BOX_FACE - blo.y:.4f} "
          f"width={bhi.x - blo.x:.4f}")
    seat, lid = bpy.data.objects["Seat"], bpy.data.objects["Lid"]
    seat_m, lid_m = C.meshes(C.seat_objects()), C.meshes(C.lid_objects())
    print(f"SEAT top z={world_bounds([seat])[1].z:.4f}  LID top z={world_bounds([lid])[1].z:.4f}")

    fixed = [o for o in body if o.name not in ("HingePin", "Water")]  # the pin runs through the knuckles
    print("LID vs body (seat closed)")
    lid_stop = first_contact(lid, C.lid_objects(), fixed, 0.0, C.LID_OPEN_DEG + 4.0)
    print("LID vs closed seat at 0")
    hinge_clearance(lid, C.lid_objects(), seat_m, [0.0], axis="X", sign=-1.0)
    lid.rotation_euler = (math.radians(-C.LID_OPEN_DEG), 0.0, 0.0)
    bpy.context.view_layer.update()
    print(f"SEAT vs body + lid open {C.LID_OPEN_DEG}")
    seat_stop = first_contact(seat, C.seat_objects(), fixed + lid_m, 0.0, C.SEAT_OPEN_DEG + 4.0)
    lid.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    print(f"STOPS lid first contact={lid_stop} (LID_OPEN_DEG {C.LID_OPEN_DEG}), "
          f"seat first contact={seat_stop} (SEAT_OPEN_DEG {C.SEAT_OPEN_DEG})")
    ok &= lid_stop is not None and lid_stop > C.LID_OPEN_DEG and seat_stop is not None and seat_stop > C.SEAT_OPEN_DEG

    plate = [bpy.data.objects["FlushPlate"]]
    for name in ("FlushSmall", "FlushLarge"):
        b = bpy.data.objects[name]
        print(f"BUTTON {name} travel {C.BTN_TRAVEL} m along +Y (vs plate)")
        bad = slide_clearance(b, [b], plate, (0, 1, 0), C.BTN_TRAVEL, steps=4)
        ok &= not bad
        blo_, bhi_ = local_bounds(b)
        print(f"  {name}: origin Godot={fmt(godot(b.location), 4)} size Godot (x, y, z)={fmt(godot_size(bhi_ - blo_), 4)}")

    hang = bpy.data.objects["RollHanging"]
    holder = [bpy.data.objects[n] for n in ("HolderBar", "HolderTip", "HolderRose")]
    print("ROLL on the holder (overlap at rest)")
    bad = slide_clearance(hang, [hang], holder + [bpy.data.objects["Cladding"]], (1, 0, 0), 0.0, steps=1)
    ok &= not bad
    print(f"ROLL hang origin Godot={fmt(godot(hang.location), 4)} rotation_degrees=(0, 0, -90) "
          f"center Godot={fmt(godot(C.ROLL_HANG_CENTER), 4)} mass={C.ROLL_MASS} kg")
    print(f"ROLL slides off toward Godot +X: bar end x={C.BAR_X1 + 0.005:.3f}")
    roll = bpy.data.objects["Roll"]
    rlo, rhi = local_bounds(roll)
    print(f"ROLL size (diameter, width)=({rhi.x - rlo.x:.4f}, {rhi.z - rlo.z:.4f}) tris={tri_count(roll)}")

    print(f"HINGE axis Godot point={fmt(godot(C.HINGE), 4)} direction +X; opening = negative rotation about +X")
    for root in (seat, lid):
        grip = [o for o in root.children if o.name.startswith("HandleGrip")][0]
        slo, shi = local_bounds(root)
        print(f"  {root.name}: grip local Godot={fmt(godot(grip.location), 4)} "
              f"world Godot={fmt(godot(root.location + grip.location), 4)}")
        lo_, hi_ = world_bounds(C.meshes(root.children_recursive) + [root])
        c = (lo_ + hi_) / 2 - root.location
        print(f"  {root.name}: closed box center local Godot={fmt(godot(c), 4)} size Godot={fmt(godot_size(hi_ - lo_), 4)}")
    collision_report(C.body_collision_objects())
    for p in ("body", "seat", "lid", "flush_small", "flush_large", "roll"):
        print(f"TRIS {p}={sum(tri_count(o) for o in C.meshes(part_objects(p)))}")
    print("CONTRACT", "OK" if ok else "FAIL")
    for glb in (C.GLB_BODY, C.GLB_SEAT, C.GLB_LID, C.GLB_FLUSH_SMALL, C.GLB_FLUSH_LARGE, C.GLB_ROLL):
        import_report(glb)


if __name__ == "__main__":
    main()
