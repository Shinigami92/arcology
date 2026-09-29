"""Stage 2: UV unwrap and bake PBR atlases for body, drawer, lamp metal and lamp light (shade + bulb), save.

  blender -b --factory-startup blender/props/nightstand_square.blend --python blender/props/nightstand_square/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import (  # noqa: E402
    BLEND, BODY_MAT, DRAWER_MAT, LAMP_MAT, LIGHT_MAT, TEX_BODY, TEX_DRAWER, TEX_LAMP, TEX_LIGHT,
    body_collision_objects, body_objects, drawer_objects, lamp_light_objects, lamp_metal_objects,
    lamp_objects,
)
from lib_candidates import emissive_from_albedo  # noqa: E402
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402

WARM_2700K = (1.0, 0.64, 0.36)  # linear; the shade's linen modulates it


def meshes(objs):
    return [o for o in objs if o.type == "MESH"]


def main():
    bake.setup(bpy.context.scene, ao_distance=0.25)
    for ob in body_collision_objects():
        ob.hide_render = True
    body, drawer, lamp = body_objects(), meshes(drawer_objects()), meshes(lamp_objects())
    # Each part bakes alone, so the others don't darken its AO (the lamp keeps
    # its own shade while its metal bakes: that shadow is real).
    bake.bake_part(body, "nightstand_body", BODY_MAT, hide=drawer + lamp, size=TEX_BODY)
    bake.bake_part(drawer, "nightstand_drawer", DRAWER_MAT, hide=body + lamp, size=TEX_DRAWER)
    bake.bake_part(lamp_metal_objects(), "table_lamp", LAMP_MAT, hide=body + drawer, size=TEX_LAMP)
    light = bake.bake_part(meshes(lamp_light_objects()), "table_lamp_light", LIGHT_MAT, hide=body + drawer,
                           size=TEX_LIGHT)
    emissive_from_albedo(light, bpy.data.images["table_lamp_light_albedo"], WARM_2700K, strength=1.0)
    bake.remove_source_materials()
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
