"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/<name>.blend --python blender/props/<name>/bake.py

Parts that move apart in the game (doors, drawers, pickables) bake alone:
pass the others as `hide`, or `bake.Spread` them apart when they share an
atlas. Parts that never move bake together for contact AO.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from template_common import BLEND, BODY_MAT, NAME, TEX_SIZE, body_objects, collision_objects  # noqa: E402
from arcology_blender import bake, geo, wood  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in collision_objects():
        ob.hide_render = True  # colliders must not shadow the AO
    bake.bake_part(body_objects(), f"{NAME}_body", BODY_MAT, size=TEX_SIZE)
    bake.remove_source_materials()
    for ob in body_objects():
        for name in wood.GRAIN_ATTRS:  # build-time masks are baked now; keep them out of the glb
            geo.remove_attribute(ob, name)
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
