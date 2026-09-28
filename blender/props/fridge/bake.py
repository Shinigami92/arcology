"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for body and door, save.

  blender -b --factory-startup blender/props/fridge.blend --python blender/props/fridge/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import (  # noqa: E402
    BLEND, BODY_MAT, DOOR_MAT, TEX_SIZE, body_collision_objects, body_objects, door_objects,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in body_collision_objects():
        ob.hide_render = True
    door_meshes = [o for o in door_objects() if o.type == "MESH"]
    # Each part bakes alone, so the other doesn't darken its AO.
    bake.bake_part(body_objects(), "fridge_body", BODY_MAT, hide=door_meshes, size=TEX_SIZE)
    bake.bake_part(door_meshes, "fridge_door", DOOR_MAT, hide=body_objects(), size=TEX_SIZE)
    bake.remove_source_materials()
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
