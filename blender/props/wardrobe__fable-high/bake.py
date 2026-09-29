"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) for the body and each door, save.

  blender -b --factory-startup blender/props/wardrobe__fable-high.blend --python blender/props/wardrobe__fable-high/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    BLEND, BODY_MAT, DOOR_LEFT_MAT, DOOR_RIGHT_MAT, TEX_SIZE_BODY, TEX_SIZE_DOOR,
    body_collision_objects, body_objects, door_meshes,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in body_collision_objects():
        ob.hide_render = True
    body, left, right = body_objects(), door_meshes("left"), door_meshes("right")
    # Each part bakes alone, so the others don't darken its AO (the closed doors would black out the interior).
    bake.bake_part(body, "wardrobe_body", BODY_MAT, hide=left + right, size=TEX_SIZE_BODY)
    bake.bake_part(left, "wardrobe_door_left", DOOR_LEFT_MAT, hide=body + right, size=TEX_SIZE_DOOR)
    bake.bake_part(right, "wardrobe_door_right", DOOR_RIGHT_MAT, hide=body + left, size=TEX_SIZE_DOOR)
    bake.remove_source_materials()
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
