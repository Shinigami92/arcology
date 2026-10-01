"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM): frame, leaf, and one shared
hardware atlas for the levers and the thumb-turn; save.

  blender -b --factory-startup blender/props/door_entrance.blend --python blender/props/door_entrance/bake.py

The frame bakes without the leaf (it opens: a closed leaf would darken the rebate), the leaf
without the frame but with its levers (contact shadow on the roses), the hardware spread
apart with everything else hidden.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from door_entrance_common import (  # noqa: E402
    BLEND, FRAME_MAT, FRAME_TEX, HW_MAT, HW_TEX, LEAF_MAT, LEAF_TEX, NAME, OPEN_H, OX, WALL_Y,
    frame_collision_objects, frame_objects, hardware_objects, leaf_meshes, lever_apartment, lever_corridor,
    thumbturn,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402

HIDDEN = 0.05


def frame_weight(ob, c, n):
    """Faces against the wall or the floor get almost no texels."""
    if c.z < 0.002 and n.z < -0.9:
        return HIDDEN  # feet
    if abs(c.y) < WALL_Y + 0.001 and abs(abs(c.x) - OX) < 0.002 and n.x * c.x > 0.9 * abs(c.x):
        return HIDDEN  # back of the jamb lining, against the reveal
    if abs(c.y) < WALL_Y + 0.001 and abs(c.z - OPEN_H) < 0.002 and n.z > 0.9:
        return HIDDEN  # top of the head lining
    if abs(abs(c.y) - WALL_Y) < 0.002 and n.y * c.y < -0.9 * abs(c.y):
        return HIDDEN  # casing backs against the wall faces
    return 1.0


def leaf_weight(ob, c, n):
    if n.z < -0.9 and c.z < 0.05:
        return 0.2  # underside
    return 1.0


def main():
    bake.setup(bpy.context.scene)
    for ob in frame_collision_objects():
        ob.hide_render = True
    frame, leaf, hw = frame_objects(), leaf_meshes(), hardware_objects()
    bake.bake_part(frame, f"{NAME}_frame", FRAME_MAT, hide=leaf + hw, size=FRAME_TEX, weight=frame_weight)
    bake.bake_part(leaf, f"{NAME}_leaf", LEAF_MAT, hide=frame, size=LEAF_TEX, weight=leaf_weight)
    groups = [(lever_apartment()[0], 0.0), (lever_corridor()[0], 0.5), (thumbturn()[0], 1.0)]
    with bake.Spread(groups, axis=0):
        bake.bake_part(hw, f"{NAME}_hardware", HW_MAT, hide=frame + leaf, size=HW_TEX)
    bake.remove_source_materials()
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
