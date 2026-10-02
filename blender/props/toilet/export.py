"""Stage 3: export the glb files: body (+ collision boxes), seat and lid (origins on the
hinge axis, closed), the two flush buttons (origins at their face centers), the roll
(origin at its bottom center, upright).

  blender -b --factory-startup blender/props/toilet.blend --python blender/props/toilet/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import toilet_common as C  # noqa: E402
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def grip_of(root):
    return [o for o in root.children if o.type == "EMPTY" and o.name.startswith("HandleGrip")][0]


def export_hinged(root, objs, path, other):
    """Each glb's grip must be named exactly `HandleGrip`; Blender names are unique per
    file, so the other part's grip steps aside while this one exports."""
    mine, theirs = grip_of(root), grip_of(other)
    theirs.name = "HandleGripAside"
    mine.name = "HandleGrip"
    export_glb_at_origin(root, objs, path)


def main():
    export_glb(C.body_objects() + C.body_collision_objects(), C.GLB_BODY)
    seat, lid = bpy.data.objects["Seat"], bpy.data.objects["Lid"]
    export_hinged(seat, C.seat_objects(), C.GLB_SEAT, lid)
    export_hinged(lid, C.lid_objects(), C.GLB_LID, seat)
    export_glb_at_origin(bpy.data.objects["FlushSmall"], C.flush_small_objects(), C.GLB_FLUSH_SMALL)
    export_glb_at_origin(bpy.data.objects["FlushLarge"], C.flush_large_objects(), C.GLB_FLUSH_LARGE)
    export_glb_at_origin(bpy.data.objects["Roll"], C.roll_objects(), C.GLB_ROLL)


if __name__ == "__main__":
    main()
