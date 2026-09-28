"""Export both glb files (variant opus-high).
blender --background blender/props/fridge__opus-high.blend --python export.py
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as S

D = bpy.data.objects
os.makedirs(os.path.dirname(S.GLB_BODY), exist_ok=True)
OPTS = dict(export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
            export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT",
            export_image_format="AUTO", export_cameras=False, export_lights=False, export_extras=False,
            export_animations=False)


def select(obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


body = [D["FridgeCabinet"], D["CrisperDrawer"], D["FridgeLightPanel"]] + list(bpy.data.collections["Collision"].objects)
select(body)
bpy.ops.export_scene.gltf(filepath=S.GLB_BODY, **OPTS)

door = D["FridgeDoor"]
loc, rot = door.location.copy(), door.rotation_euler.copy()
door.location = (0, 0, 0)
door.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
select([door, D["HandleGrip"]])
bpy.ops.export_scene.gltf(filepath=S.GLB_DOOR, **OPTS)
door.location, door.rotation_euler = loc, rot
for p in (S.GLB_BODY, S.GLB_DOOR):
    print("EXPORTED", p, os.path.getsize(p))
