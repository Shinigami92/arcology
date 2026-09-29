"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM): body, each door, and one
shared atlas for the moving props (drawer, storage box, lid, hangers). Saves the .blend.

  blender -b --factory-startup blender/props/wardrobe.blend --python blender/props/wardrobe/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from wardrobe_common import (  # noqa: E402
    BLEND, BODY_MAT, DOOR_LEFT_MAT, DOOR_RIGHT_MAT, PROPS_MAT, TEX_SIZE_BODY, TEX_SIZE_DOOR,
    TEX_SIZE_PROPS, all_prop_meshes, body_collision_objects, body_objects, door_meshes, prop_meshes,
    prop_root,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in body_collision_objects():
        ob.hide_render = True
    body, left, right = body_objects(), door_meshes("left"), door_meshes("right")
    props = all_prop_meshes()
    # Each part bakes alone, so the others don't darken its AO (the closed doors would black
    # out the interior; the drawers would black out their compartments).
    bake.bake_part(body, "wardrobe_body", BODY_MAT, hide=left + right + props, size=TEX_SIZE_BODY)
    bake.bake_part(left, "wardrobe_door_left", DOOR_LEFT_MAT, hide=body + right + props, size=TEX_SIZE_DOOR)
    bake.bake_part(right, "wardrobe_door_right", DOOR_RIGHT_MAT, hide=body + left + props, size=TEX_SIZE_DOOR)
    # Props: one atlas. The upper drawer and the second bare hanger share meshes with the
    # baked originals (linked copies), so only the originals bake; the lid is lifted off the
    # box meanwhile so the box interior isn't shadowed.
    originals = [o for p in ("drawer_lower", "box", "lid", "hanger1", "hanger2", "hanger3") for o in prop_meshes(p)]
    instances = [o for o in props if o not in originals]
    lid = prop_root("lid")
    lid.location.z += 0.30
    bpy.context.view_layer.update()
    bake.bake_part(originals, "wardrobe_props", PROPS_MAT, hide=body + left + right + instances,
                   size=TEX_SIZE_PROPS)
    lid.location.z -= 0.30
    bake.remove_source_materials()
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
