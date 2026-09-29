"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for the frame and the bedding, save.

  blender -b --factory-startup blender/props/bed_padded.blend --python blender/props/bed_padded/bake.py

Both parts bake with each other visible: nothing on the bed moves, so the
duvet's contact shadow on the platform lip and the pillows' on the headboard
pad are baked in.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from bed_common import BEDDING_MAT, BLEND, FRAME_MAT, TEX_SIZE, bed_objects, bedding_objects, collision_objects, frame_objects  # noqa: E402
from arcology_blender import bake, geo, soft  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in collision_objects():
        ob.hide_render = True
    bake.bake_part(frame_objects(), "bed_frame", FRAME_MAT, size=TEX_SIZE)
    bake.bake_part(bedding_objects(), "bed_bedding", BEDDING_MAT, size=TEX_SIZE)
    bake.remove_source_materials()
    for ob in bed_objects():
        geo.remove_attribute(ob, soft.SEAM_ATTR)  # the welt mask is baked; keep it out of the glb
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
