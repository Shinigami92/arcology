"""Stage 5: contract checks in the source (bounds, collision, touch sensor, magnifier
pivot, swing clearance against the bracket and the main mirror), then re-import the glbs.

  blender -b --factory-startup --python blender/props/bath_mirror/verify.py

All positions are printed in Godot local coordinates: Blender (x, y, z) -> Godot (x, z, -y).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from bath_mirror_common import (  # noqa: E402
    BLEND, FRONT_Y, GLASS_MAT, GLB, GLB_ARM, GLB_BRACKET, LED_MAT, LIMIT_HI, LIMIT_LO, MAG_POS, PIVOT_Y,
    STANDOFF, SWING_MAX, TOUCH_AREA, TOUCH_MAT, TOUCH_X, TOUCH_Y, TOUCH_Z, arm_objects, body_objects,
    bracket_objects, collision_objects, mirror_fx_objects,
)
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, inside, world_bounds,
)
from arcology_blender.scene import meshes, part_objects, tri_count  # noqa: E402


def local_box(objs, root):
    """Bounds of `objs` in `root`'s frame (Godot axes): center, size."""
    inv = root.matrix_world.inverted()
    pts = [inv @ (o.matrix_world @ v.co) for o in objs for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return godot((lo + hi) / 2), godot_size(hi - lo)


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    mirror = body_objects() + mirror_fx_objects()
    lo, hi = world_bounds(mirror)
    ok = inside(lo, hi, LIMIT_LO, LIMIT_HI)
    print(f"BOUNDS mirror lo={fmt(lo)} hi={fmt(hi)} {'OK' if ok else 'OUT OF CONTRACT'}")
    flo, fhi = world_bounds(body_objects())
    print(f"FRAME size={fmt(godot_size(fhi - flo))} front_y={flo.y:.4f} standoff={STANDOFF:.3f} "
          f"(contract front {FRONT_Y:.4f})")
    collision_report(collision_objects())
    for name in ("MirrorGlass", "MirrorLight", "TouchSensor"):
        ob = bpy.data.objects[name]
        print(f"SLOT {name}: {[m.name for m in ob.data.materials]} tris={tri_count(ob)}")
    assert bpy.data.objects["MirrorGlass"].data.materials[0].name == GLASS_MAT
    assert bpy.data.objects["MirrorLight"].data.materials[0].name == LED_MAT
    assert bpy.data.objects["TouchSensor"].data.materials[0].name == TOUCH_MAT
    print(f"TOUCH center(godot)={fmt(godot((TOUCH_X, TOUCH_Y, TOUCH_Z)), 4)} area size(godot)={fmt(TOUCH_AREA)}")

    bracket, arm = bpy.data.objects["MagnifierBracket"], bpy.data.objects["MagnifierArm"]
    print(f"MAG bracket origin (mirror frame, godot)={fmt(godot(bracket.location))} "
          f"pivot from bracket origin (godot)={fmt(godot((0.0, PIVOT_Y, 0.0)))}")
    grip = bpy.data.objects["HandleGrip"]
    print(f"MAG HandleGrip arm-local (godot)={fmt(godot(grip.location))}")
    head = [o for o in meshes(arm_objects())]
    print("MAG arm+head bounds arm-local (godot center, size):", *(fmt(t) for t in local_box(head, arm)))
    for name in ("MagnifierGlass",):
        ob = bpy.data.objects[name]
        print(f"SLOT {name}: {[m.name for m in ob.data.materials]}")

    print(f"SWING (arm vs bracket and main mirror, 0..{SWING_MAX:.0f} deg, negative about Z)")
    fixed = meshes(bracket_objects()) + body_objects() + mirror_fx_objects()
    bad = hinge_clearance(arm, meshes(arm_objects()), fixed, angles=range(0, int(SWING_MAX) + 1, 10), axis="Z",
                          sign=-1.0)
    print("CLEARANCE", "OK" if not bad else f"FAIL {bad}")
    # the folded head must stay off the wall
    alo, ahi = world_bounds(meshes(arm_objects()))
    print(f"MAG folded y range {alo.y:.4f}..{ahi.y:.4f} (wall at 0)")
    for part, objs in (("mirror body", body_objects()), ("mirror fx", mirror_fx_objects()),
                       ("bracket", meshes(bracket_objects())), ("arm", meshes(arm_objects())),
                       ("collision", collision_objects() + part_objects("mag_bracket_col"))):
        print(f"TRIS {part}={sum(tri_count(o) for o in objs)}")
    print("CONTRACT", "OK" if ok and not bad else "FAIL")
    import_report(GLB)
    import_report(GLB_BRACKET)
    import_report(GLB_ARM)


if __name__ == "__main__":
    main()
