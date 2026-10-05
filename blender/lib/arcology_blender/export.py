"""glTF export with the project's settings."""

import os

import bmesh
import bpy

from .scene import tri_count


def export_glb(objs, path, rigged=False, morphs=False):
    """Export the objects as one glb (Y up, transforms applied, textures embedded).

    Meshes are triangulated at export (not saved) so MikkTSpace tangents exist
    for every mesh: n-gons from booleans and bevels otherwise export without
    tangents and the normal maps break in Godot.

    `rigged=True` (characters, D-037): include the armature in `objs`; exports
    the skin with every bone (non-deforming ones too: OpenXR tips, palms) and
    each NLA track as an animation of the track's name (`rig.pose_action`).
    Limit weights to 4 per vertex first (`rig.limit_weights`).

    `morphs=True` also exports shape keys as morph targets (named in the mesh's
    `extras.targetNames`, Godot's blend shapes), with normals. The exporter drops
    shape keys of meshes whose modifiers it applies, so this path exports without
    applying modifiers: every mesh is triangulated on a temporary copy of its data
    instead (bmesh, the same Beauty method as the modifier, shape keys kept), and
    only Armature modifiers may remain on the objects.
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
    swapped = []
    for ob in objs:
        if ob.type != "MESH":
            continue
        if morphs:
            other = [m.name for m in ob.modifiers if m.type != "ARMATURE"]
            if other:
                raise ValueError(f"export_glb(morphs=True): {ob.name} has modifiers {other}; apply them first")
            orig = ob.data
            tmp = orig.copy()
            name = orig.name
            orig.name = name + "__export_src"
            tmp.name = name
            bm = bmesh.new()
            bm.from_mesh(tmp)
            bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(tmp)
            bm.free()
            ob.data = tmp
            swapped.append((ob, orig, tmp, name))
        else:
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
    if morphs:
        options.update(
            export_apply=False,
            export_morph=True,
            export_morph_normal=True,
            export_morph_tangent=False,
            export_morph_animation=False,
        )
    try:
        bpy.ops.export_scene.gltf(**options)
    finally:
        for ob, mod in tri_mods:
            ob.modifiers.remove(mod)
        for ob, orig, tmp, name in swapped:
            ob.data = orig
            bpy.data.meshes.remove(tmp)
            orig.name = name
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
