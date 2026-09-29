"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/nightstand.blend --python blender/props/nightstand/bake.py

Parts: body, drawer, lamp (metal + cord) and the lamp's LampLight part
(shade + bulb), which also gets an emission atlas. The body bakes without
the drawer and lamp (both move or can be moved); the drawer bakes alone;
the lamp parts bake with each other and the body visible (contact AO where
the base and cord rest on the top).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import (  # noqa: E402
    BLEND, BODY_MAT, BUILD_ATTRS, DRAWER_MAT, LAMP_MAT, LIGHT_MAT, LIGHT_STRENGTH, TEX_BODY, TEX_DRAWER,
    TEX_LAMP, TEX_SHADE, body_collision_objects, body_objects, drawer_objects, lamp_light_objects, lamp_objects,
)
from arcology_blender import bake, geo  # noqa: E402
from arcology_blender.scene import meshes, save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene, ao_distance=0.12)
    for ob in body_collision_objects():
        ob.hide_render = True
    body, drawer = body_objects(), meshes(drawer_objects())
    lamp, light = meshes(lamp_objects()), meshes(lamp_light_objects())
    bake.bake_part(body, "nightstand_body", BODY_MAT, hide=drawer + lamp + light, size=TEX_BODY)
    bake.bake_part(drawer, "nightstand_drawer", DRAWER_MAT, hide=body + lamp + light, size=TEX_DRAWER)
    bake.bake_part(lamp, "table_lamp", LAMP_MAT, hide=drawer, size=TEX_LAMP)
    bake.bake_part(light, "table_lamp_shade", LIGHT_MAT, hide=drawer, size=TEX_SHADE, emission=LIGHT_STRENGTH)
    bake.remove_source_materials()
    for ob in body + drawer + lamp + light:
        for name in BUILD_ATTRS:
            geo.remove_attribute(ob, name)
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
