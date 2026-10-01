"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/door_interior.blend --python blender/props/door_interior/bake.py

Every part bakes alone (they move apart in the game; the bedroom and living room
doors have no thumb-turn), with a temporary floor (and, for the frame, the wall
around the opening) for contact AO. Faces that sit against the wall, the rough
opening or the floor, and the leaf's top and bottom edges get little texture space.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from door_interior_common import (  # noqa: E402
    BLEND, CASING_X0, CASING_Z0, FRAME_MAT, LEAF_MAT, LEAF_Z0, LEAF_Z1, LEVER_MAT, OPEN_H,
    OPEN_X, TEX_FRAME, TEX_LEAF, TEX_LEVER, TEX_THUMBTURN, THUMBTURN_MAT, WALL_Y, frame_collision_objects,
    frame_objects, leaf_objects, lever_objects, thumbturn_objects,
)
from lib_candidates import wall_with_opening  # noqa: E402
from arcology_blender import bake  # noqa: E402
from arcology_blender.geo import bm_box, new_object, remove  # noqa: E402
from arcology_blender.scene import get_collection, meshes, save_blend  # noqa: E402


def frame_weight(ob, c, n):
    """Hidden frame faces: against the wall (casing backs), the rough opening (lining
    outside), the floor (bottom ends)."""
    if n.z < -0.9 and c.z < 0.002:
        return 0.05
    if abs(n.y) > 0.9 and abs(abs(c.y) - WALL_Y) < 0.0008 and (abs(c.x) > CASING_X0 + 0.002 or c.z > CASING_Z0 + 0.002):
        return 0.05
    if abs(n.x) > 0.9 and abs(abs(c.x) - OPEN_X) < 0.0008:
        return 0.05
    if n.z > 0.9 and abs(c.z - OPEN_H) < 0.0008:
        return 0.05
    return 1.0


def leaf_weight(ob, c, n):
    """The leaf's top edge (above eye height) and bottom edge (never seen)."""
    if abs(n.z) > 0.9 and (abs(c.z - LEAF_Z1) < 0.001 or abs(c.z - LEAF_Z0) < 0.001):
        return 0.2
    return 1.0


def context_meshes(with_wall):
    coll = get_collection("BakeContext")
    bm = bmesh.new()
    bm_box(bm, (-2.0, -2.0, -0.05), (2.0, 2.0, 0.0))
    if with_wall:
        wall_with_opening(bm, -1.5, 1.5, 2.6, -WALL_Y + 0.0002, WALL_Y - 0.0002, -OPEN_X, OPEN_X, OPEN_H)
    return new_object("BakeContext", bm, coll)


def main():
    bake.setup(bpy.context.scene)
    for ob in frame_collision_objects():
        ob.hide_render = True
    frame = frame_objects()
    leaf = meshes(leaf_objects())
    lever = lever_objects()
    tt = meshes(thumbturn_objects())

    ctx = context_meshes(True)
    bake.bake_part(frame, "door_interior_frame", FRAME_MAT, hide=leaf + lever + tt, size=TEX_FRAME,
                   weight=frame_weight)
    remove(ctx)
    ctx = context_meshes(False)
    bake.bake_part(leaf, "door_interior_leaf", LEAF_MAT, hide=frame + lever + tt, size=TEX_LEAF, weight=leaf_weight)
    # Hardware sits on the leaf: keep the leaf for contact AO, hide the other hardware.
    bake.bake_part(lever, "door_interior_lever", LEVER_MAT, hide=tt, size=TEX_LEVER)
    bake.bake_part(tt, "door_interior_thumbturn", THUMBTURN_MAT, hide=lever, size=TEX_THUMBTURN)
    remove(ctx)
    bake.remove_source_materials()
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
