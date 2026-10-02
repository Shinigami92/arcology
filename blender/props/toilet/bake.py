"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/bake.py

Every part bakes alone (hide the others), except the flush buttons, which stay
visible while the body bakes (they barely move: contact shadow in the plate's
pocket). The bowl's faces hidden inside the box and below the water line get
less texture space.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import toilet_common as C  # noqa: E402
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import part_objects, save_blend  # noqa: E402


def body_weight(ob, c, n):
    if ob.name == "Bowl":
        if c.y > C.BOX_FACE + 0.001:
            return 0.05  # inside the installation box
        if c.z < C.WATER_Z - 0.002 and c.y > -0.66 and abs(c.x) < 0.14 and n.z > -0.2:
            return 0.08  # basin below the (opaque) water
        if n.z < -0.6:
            return 0.5  # underside
    if ob.name == "Cladding" and c.y > -0.001:
        return 0.2
    return 1.0


def main():
    bake.setup(bpy.context.scene)
    for ob in C.body_collision_objects():
        ob.hide_render = True
    body = C.body_objects()
    seat, lid = C.meshes(C.seat_objects()), C.meshes(C.lid_objects())
    small, large = C.meshes(C.flush_small_objects()), C.meshes(C.flush_large_objects())
    roll = C.meshes(C.roll_objects())
    hanging = C.meshes(part_objects("instance"))
    everything = body + seat + lid + small + large + roll + hanging

    def others(objs):
        return [o for o in everything if o not in objs]

    bake.bake_part(body, f"{C.NAME}_body", C.BODY_MAT, hide=seat + lid + roll + hanging, size=C.BODY_TEX,
                   weight=body_weight)
    bake.bake_part(seat, f"{C.NAME}_seat", C.SEAT_MAT, hide=others(seat), size=C.SEAT_TEX)
    bake.bake_part(lid, f"{C.NAME}_lid", C.LID_MAT, hide=others(lid), size=C.LID_TEX)
    bake.bake_part(small, f"{C.NAME}_flush_small", C.FLUSH_SMALL_MAT, hide=others(small), size=C.BTN_TEX)
    bake.bake_part(large, f"{C.NAME}_flush_large", C.FLUSH_LARGE_MAT, hide=others(large), size=C.BTN_TEX)
    bake.bake_part(roll, f"{C.NAME}_roll", C.ROLL_MAT, hide=others(roll), size=C.ROLL_TEX)
    bake.remove_source_materials()
    bake.report_images()
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
