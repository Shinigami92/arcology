"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for frame, linen and throw, save.

  blender -b --factory-startup blender/props/bed.blend --python blender/props/bed/bake.py

Everything is static, so all parts bake with each other visible (contact AO
between duvet, pillows, throw and frame). Faces that are barely visible (the
platform underside, the headboard back against the wall, cloth undersides at
the hems) get less texture space (lib_candidates.bake_part_weighted).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import bed_common as C  # noqa: E402
import lib_candidates as L  # noqa: E402
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
    L.bake_part_weighted(C.frame_objects(), "bed_frame", C.FRAME_MAT, frame_weight, size=C.FRAME_TEX)
    L.bake_part_weighted(C.linen_objects(), "bed_linen", C.LINEN_MAT, cloth_weight, size=C.LINEN_TEX)
    L.bake_part_weighted(C.throw_objects(), "bed_throw", C.THROW_MAT, cloth_weight, size=C.THROW_TEX)
    bake.remove_source_materials()
    for ob in C.bed_objects():
        geo.remove_attribute(ob, soft.SEAM_ATTR)  # the hem mask is baked; keep it out of the glb
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
