"""glTF export with the project's settings."""

import os

import bpy

from .scene import tri_count


def export_glb(objs, path, rigged=False):
    """Export the objects as one glb (Y up, transforms applied, textures embedded).

    Meshes are triangulated at export (not saved) so MikkTSpace tangents exist
    for every mesh: n-gons from booleans and bevels otherwise export without
    tangents and the normal maps break in Godot.

    `rigged=True` (characters, D-037): include the armature in `objs`; exports
    the skin with every bone (non-deforming ones too: OpenXR tips, palms) and
    each NLA track as an animation of the track's name (`rig.pose_action`).
    Limit weights to 4 per vertex first (`rig.limit_weights`).
    """
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.hide_render = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tri_mods = []
    for ob in objs:
        if ob.type == "MESH":
            mod = ob.modifiers.new("ExportTriangulate", "TRIANGULATE")
            mod.quad_method = "BEAUTY"
            mod.ngon_method = "BEAUTY"
            tri_mods.append((ob, mod))
    options = dict(
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
    if rigged:
        options.update(
            export_skins=True,
            export_animations=True,
            export_animation_mode="NLA_TRACKS",
            export_def_bones=False,
            export_all_influences=False,
            export_optimize_animation_size=False,
        )
    bpy.ops.export_scene.gltf(**options)
    for ob, mod in tri_mods:
        ob.modifiers.remove(mod)
    tris = sum(tri_count(o) for o in objs)
    print(f"EXPORTED {path} objects={len(objs)} tris={tris} size={os.path.getsize(path) / 1e6:.1f}MB")


def export_glb_at_origin(root, objs, path):
    """Export a moving part (door, drawer, lid) with its root object at the origin,
    so the glb's origin is the pivot (hinge axis, slide start)."""
    saved = root.matrix_world.copy()
    root.location = (0.0, 0.0, 0.0)
    root.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    export_glb(objs, path)
    root.matrix_world = saved
