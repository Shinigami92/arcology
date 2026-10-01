"""Stage 5: contract checks (bounds, hinge clearance 0..100 degrees, sizes and positions for
Godot), then re-import the glb files.

  blender -b --factory-startup --python blender/props/door_entrance/verify.py [-- --no-import]

Godot coordinates: Blender (x, y, z) -> Godot (x, z, -y), relative to the frame origin.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from door_entrance_common import (  # noqa: E402
    BLEND, BOLT_Z, CASING_OUT, LEAF_X0, LEAF_X1, LEAF_Y0, LEAF_Y1, LEAF_Z1, SEAL_Z0, GLB_FRAME, GLB_LEAF, GLB_LEVER_APT, GLB_LEVER_COR, GLB_THUMBTURN, HINGE,
    LEVER_Z, LX, OPEN_DEG, OPEN_H, OX, WALL_Y, frame_collision_objects, frame_objects, hardware_objects,
    leaf_meshes, leaf_objects, lever_apartment, lever_corridor, thumbturn,
)
from arcology_blender.checks import (  # noqa: E402
    collision_report, fmt, godot, godot_size, hinge_clearance, import_report, inside, local_bounds,
    world_bounds,
)
from arcology_blender.scene import script_args, tri_count  # noqa: E402


def attach(objs, parent):
    """Parent the separate hardware to the leaf for the swing (keeps world transforms)."""
    for ob in objs:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    leaf = bpy.data.objects["Leaf"]
    ok = True

    # Frame stays inside the opening plus casings, floor to casing top
    lo, hi = world_bounds(frame_objects())
    # y: casings at +-0.112, hinge barrels stand 13.5 mm proud of the apartment casing
    limit_lo = Vector((-OX - CASING_OUT, -0.135, 0.0))
    limit_hi = Vector((OX + CASING_OUT, 0.13, OPEN_H + CASING_OUT))
    f_ok = inside(lo, hi, limit_lo, limit_hi)
    ok &= f_ok
    print(f"FRAME BOUNDS lo={fmt(lo)} hi={fmt(hi)} {'OK' if f_ok else 'OUT OF CONTRACT'}")
    llo, lhi = world_bounds(leaf_meshes() + hardware_objects())
    print(f"LEAF+HARDWARE BOUNDS (closed) lo={fmt(llo)} hi={fmt(lhi)}")

    # Swing: leaf + levers + thumb-turn against the frame
    attach(hardware_objects(), leaf)
    bpy.context.view_layer.update()
    print("HINGE SWING (leaf + hardware vs frame)")
    bad = hinge_clearance(leaf, leaf_meshes() + hardware_objects(), frame_objects(),
                          angles=range(0, int(OPEN_DEG) + 1, 5))
    # Also check the walls next to the frame (wall faces at +-WALL_Y outside the casings)
    import bmesh
    me = bpy.data.meshes.new("CheckWall")
    bm = bmesh.new()
    from arcology_blender.geo import bm_box
    bm_box(bm, (-1.6, -WALL_Y, 0.0), (-OX - CASING_OUT - 0.001, WALL_Y, 2.6))
    bm_box(bm, (OX + CASING_OUT + 0.001, -WALL_Y, 0.0), (1.6, WALL_Y, 2.6))
    bm.to_mesh(me)
    wall = bpy.data.objects.new("CheckWall", me)
    bpy.context.scene.collection.objects.link(wall)
    print("HINGE SWING (leaf + hardware vs walls beside the frame)")
    bad_wall = hinge_clearance(leaf, leaf_meshes() + hardware_objects(), [wall],
                               angles=range(0, int(OPEN_DEG) + 1, 10))
    ok &= not bad and not bad_wall
    print("CLEARANCE", "OK" if not bad and not bad_wall else f"FAIL frame={bad} wall={bad_wall}")

    # Godot numbers
    print("GODOT (relative to the frame origin = bottom center of the opening, wall center plane)")
    print(f"  hinge axis (leaf glb origin) at {fmt(godot(HINGE), 4)}, axis = Godot +Y; opens toward +Z "
          f"(Blender rotation -Z), 0..{OPEN_DEG:.0f} deg checked")
    slo = Vector((LEAF_X0, LEAF_Y0, SEAL_Z0)) - HINGE
    shi = Vector((LEAF_X1, LEAF_Y1, LEAF_Z1)) - HINGE
    print(f"  leaf slab box (leaf-local, for the DoorBody collision) center={fmt(godot((slo + shi) / 2), 4)} "
          f"size={fmt(godot_size(shi - slo), 4)}")
    blo, bhi = local_bounds(leaf)
    print(f"  leaf mesh bounds (leaf-local, Godot) x {blo.x:.4f}..{bhi.x:.4f} y {blo.z:.4f}..{bhi.z:.4f} "
          f"z {-bhi.y:.4f}..{-blo.y:.4f}")
    for ob in leaf_objects():
        if ob.type == "EMPTY":
            p = ob.matrix_world.translation
            print(f"  {ob.name}: frame {fmt(godot(p), 4)}  leaf-local {fmt(godot(p - HINGE), 4)}")
    for name, objs in (("LeverApartment", lever_apartment()), ("LeverCorridor", lever_corridor()),
                       ("ThumbTurn", thumbturn())):
        ob = objs[0]
        ob.parent = None
        p = Vector(ob.location)
        llo2, lhi2 = local_bounds(ob)
        print(f"  {name}: origin frame {fmt(godot(p), 4)} leaf-local {fmt(godot(p - HINGE), 4)} "
              f"size {fmt(godot_size(lhi2 - llo2), 4)} axis Godot Z (spindle through the leaf)")
    print(f"  spindle x={LX:.4f} z(height)={LEVER_Z:.3f}; deadbolt height {BOLT_Z:.3f}")
    collision_report(frame_collision_objects())

    tris = {"frame": sum(tri_count(o) for o in frame_objects()),
            "leaf": sum(tri_count(o) for o in leaf_meshes()),
            "lever_apartment": sum(tri_count(o) for o in lever_apartment()),
            "lever_corridor": sum(tri_count(o) for o in lever_corridor()),
            "thumbturn": sum(tri_count(o) for o in thumbturn())}
    print("TRIS " + " ".join(f"{k}={v}" for k, v in tris.items()) + f" total={sum(tris.values())}")
    print("CONTRACT", "OK" if ok else "FAIL")
    if "--no-import" not in script_args():
        for glb in (GLB_FRAME, GLB_LEAF, GLB_LEVER_APT, GLB_LEVER_COR, GLB_THUMBTURN):
            if os.path.exists(glb):
                import_report(glb)


if __name__ == "__main__":
    main()
