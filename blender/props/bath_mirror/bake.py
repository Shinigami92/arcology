"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/bake.py

Parts: the mirror body (frame, backing, mount, LED channel; hidden faces get
little texture space), the magnifier bracket and the magnifier arm + head.
The unbaked slots (mirror_glass, mirror_led, mirror_touch_led) keep their
materials. The magnifier parts bake with each other visible (the knuckles
nest at every angle), without the main mirror.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from bath_mirror_common import (  # noqa: E402
    ARM_MAT, BLEND, BODY_MAT, BRACKET_MAT, FRONT_Y, H, HX, STANDOFF, TEX_ARM, TEX_BODY, TEX_BRACKET, arm_objects,
    body_objects, bracket_objects, collision_objects, mirror_fx_objects,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import meshes, part_objects, save_blend  # noqa: E402


def body_weight(ob, c, n):
    """Full density on the frame's visible faces (front, outer sides, the lip's
    inner edge); the mount, backing and the frame's inside get 8 %."""
    eps = 0.0006
    if c.y > -STANDOFF + eps:
        return 0.08                                   # mount rails, bumpers, behind the frame
    if n.y < -0.7 and c.y < FRONT_Y + eps:
        return 1.0                                    # frame face
    if abs(c.x) > HX - eps or c.z < eps or c.z > H - eps:
        return 1.0                                    # outer skirt
    if c.y < FRONT_Y + 0.0016 and n.y > -0.7 and n.y < 0.7:
        return 1.0                                    # lip's inner edge around the glass
    return 0.08


def main():
    bake.setup(bpy.context.scene, ao_distance=0.10)
    for ob in collision_objects() + part_objects("mag_bracket_col"):
        ob.hide_render = True
    body, fx = body_objects(), mirror_fx_objects()
    bracket, arm = meshes(bracket_objects()), meshes(arm_objects())
    bake.bake_part(body, "bath_mirror_body", BODY_MAT, hide=fx + bracket + arm, size=TEX_BODY, weight=body_weight)
    bake.bake_part(bracket, "bath_mirror_magnifier_bracket", BRACKET_MAT, hide=body + fx, size=TEX_BRACKET)
    bake.bake_part(arm, "bath_mirror_magnifier_arm", ARM_MAT, hide=body + fx, size=TEX_ARM)
    bake.remove_source_materials()
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
