"""Stage 3: export the body and door glb files.

  blender -b --factory-startup <blend> --python export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import (  # noqa: E402
    GLB_BODY, GLB_DOOR, body_collision_objects, body_objects, door_objects, tri_count,
)


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.hide_render = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Triangulate at export so MikkTSpace tangents can be computed for every mesh (n-gons from
    # booleans/bevels otherwise get no tangents). export_apply applies the modifier; not saved.
    tri_mods = []
    for ob in objs:
        if ob.type == "MESH":
            mod = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
            mod.quad_method = "BEAUTY"
            mod.ngon_method = "BEAUTY"
            tri_mods.append((ob, mod))
    kwargs = dict(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_animations=False,
        export_lights=False,
        export_cameras=False,
        export_extras=False,
        export_skins=False,
        export_morph=False,
    )
    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError as exc:
        print("export arg problem, retrying with a reduced set:", exc)
        for k in ("export_skins", "export_morph", "export_extras", "export_tangents"):
            kwargs.pop(k, None)
        bpy.ops.export_scene.gltf(**kwargs)
    for ob, mod in tri_mods:
        ob.modifiers.remove(mod)
    tris = sum(tri_count(o) for o in objs)
    print(f"EXPORTED {path} objects={len(objs)} tris={tris} size={os.path.getsize(path) / 1e6:.1f}MB")


def main():
    body = body_objects() + body_collision_objects()
    export(body, GLB_BODY)

    door = bpy.data.objects["Door"]
    saved = door.matrix_world.copy()
    door.location = (0.0, 0.0, 0.0)
    door.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    export(door_objects(), GLB_DOOR)
    door.matrix_world = saved


if __name__ == "__main__":
    main()
