"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for frame, linen and throw, save.

  blender -b --factory-startup blender/props/bed.blend --python blender/props/bed/bake.py

Everything is static, so all parts bake with each other visible (contact AO
between duvet, pillows, throw and frame). Faces that are barely visible (the
platform underside, the headboard back against the wall, cloth undersides at
the hems) get less texture space (bake.bake_part with a weight).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import bed_common as C  # noqa: E402
from arcology_blender import bake, geo, soft  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def frame_weight(ob, c, n):
    if n.z < -0.9:
        return 0.2   # platform underside, leg bottoms
    if n.y > 0.9 and c.y > C.HB_Y1 - 0.01:
        return 0.35  # headboard back, against the wall
    return 1.0


def cloth_weight(ob, c, n):
    if n.z < -0.5:
        return 0.4   # cloth undersides at the hems, pillow bottoms
    if n.y > 0.6 and c.y > C.HB_Y0 - 0.15:
        return 0.5   # pillow backs against the headboard
    return 1.0


def main():
    bake.setup(bpy.context.scene)
    for ob in C.collision_objects():
        ob.hide_render = True
    bake.bake_part(C.frame_objects(), "bed_frame", C.FRAME_MAT, size=C.FRAME_TEX, weight=frame_weight)
    bake.bake_part(C.linen_objects(), "bed_linen", C.LINEN_MAT, size=C.LINEN_TEX, weight=cloth_weight)
    bake.bake_part(C.throw_objects(), "bed_throw", C.THROW_MAT, size=C.THROW_TEX, weight=cloth_weight)
    bake.remove_source_materials()
    for ob in C.bed_objects():
        geo.remove_attribute(ob, soft.SEAM_ATTR)  # the hem mask is baked; keep it out of the glb
    bake.report_images()
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
