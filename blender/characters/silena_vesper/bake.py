"""Stage 2: unwrap and bake the left glove (albedo, normal, ORM), drop the build-time
data, mirror it into the right glove (same mesh mirrored, same texture set), save.

  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/bake.py

Bakes in the rest pose (NLA muted), the glove alone (the body doesn't render).
The unwrap follows the surface (smart project for the islands, then a minimum
stretch unwrap of the same islands), so seams, stitches and the filigree keep
an even texel density; the lining deep in the cuff and the strap's tucked
edges get less space.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from silena_vesper_common import BLEND, GLOVE_MAT, NAME, TEX_SIZE, armature, glove  # noqa: E402
import glove as glove_geo  # noqa: E402
import leather  # noqa: E402
from arcology_blender import bake, geo, rig  # noqa: E402
from arcology_blender.scene import save_blend, tag  # noqa: E402

HIDDEN_SCALE = 0.35   # texel density of the lining and the tucked strap edges


def unwrap(ob):
    me = ob.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    me.uv_layers.active = uv
    uv.active_render = True
    bake.select_only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.uv.smart_project(angle_limit=math.radians(58.0), island_margin=0.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.002)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")

    # less space for what is barely seen
    bm = bmesh.new()
    bm.from_mesh(me)
    layer = bm.loops.layers.uv["UVMap"]
    region = bm.verts.layers.float["region"]
    for isl in bake._islands(bm, layer):
        codes = [round(v[region]) for f in isl for v in f.verts]
        hidden = sum(c == glove_geo.REGION_LINING for c in codes) / len(codes)
        if hidden < 0.5:
            continue
        loops = [lp for f in isl for lp in f.loops]
        c = sum((lp[layer].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
        for lp in loops:
            lp[layer].uv = c + (lp[layer].uv - c) * HIDDEN_SCALE
    bm.to_mesh(me)
    bm.free()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=0.004, scale=True,
                            merge_overlap=False, shape_method="CONCAVE")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def strip_build_data(ob):
    me = ob.data
    for name in ("region",) + glove_geo.FINGER_ATTRS + glove_geo.CUFF_ATTRS:
        geo.remove_attribute(ob, name)
    for name in glove_geo.UV_HELPERS:
        layer = me.uv_layers.get(name)
        if layer is not None:
            me.uv_layers.remove(layer)
    for key in ("snap_center", "snap_normal", "orn_origin"):
        if key in ob.keys():
            del ob[key]


def main():
    scene = bpy.context.scene
    arm = armature()
    left = glove("Left")
    tracks = arm.animation_data.nla_tracks
    for tr in tracks:
        tr.mute = True
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    bake.setup(scene, ao_distance=0.03)
    unwrap(left)
    albedo, normal, orm = bake.bake_atlas([left], f"{NAME}_glove", TEX_SIZE)
    mat = bake.final_material(GLOVE_MAT, albedo, normal, orm)
    bake.assign_single([left], mat)
    bake.remove_source_materials()
    leather.remove_images()
    strip_build_data(left)

    old = bpy.data.objects.get("GloveRight")
    if old is not None:
        bpy.data.objects.remove(old)
    right = rig.mirror_mesh(left, "GloveRight", "Left", "Right")
    tag(right, "glove_right")

    for tr in tracks:
        tr.mute = False
    arm.data.pose_position = "POSE"
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
