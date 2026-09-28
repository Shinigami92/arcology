"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for cushions, frame and pillow, save.

  blender -b --factory-startup blender/props/sofa.blend --python blender/props/sofa/bake.py

Cushions and frame bake with each other visible, so the crevices between
them get contact AO (they never move apart). The pillow is pickable: it
bakes alone, and the sofa bakes without it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from sofa_common import (  # noqa: E402
    BLEND, CUSHION_MAT, FRAME_MAT, PILLOW_MAT, PILLOW_TEX, TEX_SIZE, collision_objects, cushion_objects,
    frame_objects, pillow_objects, sofa_objects,
)
from arcology_blender import geo, soft  # noqa: E402
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in collision_objects():
        ob.hide_render = True
    pillows = pillow_objects()
    bake.bake_part(cushion_objects(), "sofa_cushions", CUSHION_MAT, hide=pillows, size=TEX_SIZE)
    bake.bake_part(frame_objects(), "sofa_frame", FRAME_MAT, hide=pillows, size=TEX_SIZE)
    bake.bake_part(pillows, "sofa_pillow", PILLOW_MAT, hide=sofa_objects(), size=PILLOW_TEX)
    bake.remove_source_materials()
    for ob in sofa_objects() + pillows:
        geo.remove_attribute(ob, soft.SEAM_ATTR)  # the welt mask is baked; keep it out of the glb
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
