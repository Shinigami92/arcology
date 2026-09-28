"""Stage 2: unwrap and bake the sofa (2048) and the pillow (1024) into one PBR atlas set each.

  blender -b --factory-startup blender/props/sofa_boucle.blend --python blender/props/sofa_boucle/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from sofa_common import (  # noqa: E402
    BLEND, PILLOW_MAT, PILLOW_TEX_SIZE, SOFA_MAT, TEX_SIZE, pillow_objects, sofa_collision_objects,
    sofa_objects,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in sofa_collision_objects():
        ob.hide_render = True
    # Each part bakes alone: the pillow sits at the origin inside the sofa base.
    bake.bake_part(sofa_objects(), "sofa", SOFA_MAT, hide=pillow_objects(), size=TEX_SIZE)
    bake.bake_part(pillow_objects(), "sofa_pillow", PILLOW_MAT, hide=sofa_objects(), size=PILLOW_TEX_SIZE)
    bake.remove_source_materials()
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
