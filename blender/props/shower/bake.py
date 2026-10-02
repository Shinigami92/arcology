"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM), save.

  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/bake.py

Two atlases: the static body (2048) and one shared by the three moving parts (lever, dial,
hand shower; 1024), so the set uses three materials in total (ShowerBody, ShowerParts,
shower_glass). The body bakes without the glass pane and the parts (they move or are
replaced); the parts bake alone, spread apart so the lever and dial don't shade each other.
Their materials use object-space patterns, so moving them doesn't change the texture.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import shower_common as C  # noqa: E402
from arcology_blender import bake, curves, geo  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene, ao_distance=0.2)
    for ob in C.collision_objects():
        ob.hide_render = True
    body, glass, parts = C.body_objects(), C.glass_objects(), C.part_meshes()
    bake.bake_part(body, "shower_body", C.BODY_MAT, hide=glass + parts, size=C.TEX_BODY)
    spread = [(bpy.data.objects["MixerFlow"], 0.0), (bpy.data.objects["MixerTemp"], 0.5),
              (bpy.data.objects["Handheld"], 1.0)]
    with bake.Spread(spread):
        bake.bake_part(parts, "shower_parts", C.PARTS_MAT, hide=body + glass, size=C.TEX_PARTS)
    bake.remove_source_materials()
    for ob in body + parts:
        for name in (curves.ALONG_ATTR,) + tuple(curves.AROUND_ATTRS):
            geo.remove_attribute(ob, name)
    bake.report_images()
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
