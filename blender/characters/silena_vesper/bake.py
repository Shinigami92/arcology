"""Stage 2: unwrap and bake the left glove and the left sleeve (albedo, normal, ORM: one
set per material), drop the build-time data, join them into `ArmLeft` (two materials),
mirror it into `ArmRight` (same mesh mirrored, same texture sets), save.

  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/bake.py

Bakes in the rest pose (NLA muted), glove and sleeve together (each one's AO sees
the other: the gauntlet darkens where it enters the cuff; the body doesn't
render). The glove's unwrap follows its surface (smart project for the islands,
then a minimum stretch unwrap of the same islands); its lining deep in the cuff
gets less space. The sleeve keeps the surface-true unwrap sleeve.py computed
(`BakeUV`: three strips cut along the inner seam), packed into the atlas.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, COAT_MAT, GLOVE_MAT, NAME, TEX_SIZE, armature, glove, sleeve,
)
import coat_leather  # noqa: E402
import glove as glove_geo  # noqa: E402
import leather  # noqa: E402
import sleeve as sleeve_geo  # noqa: E402
from arcology_blender import bake, geo, rig  # noqa: E402
from arcology_blender.scene import save_blend, tag  # noqa: E402

HIDDEN_SCALE = 0.35   # texel density of the glove's lining and the tucked strap edges


def unwrap_glove(ob):
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
    pack(ob)


def unwrap_sleeve(ob):
    """The build's surface-true strips (meters) into UVMap, packed into the atlas."""
    me = ob.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    src = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers["BakeUV"].data.foreach_get("uv", src)
    uv.data.foreach_set("uv", src)
    me.uv_layers.active = uv
    uv.active_render = True
    bake.select_only([ob])
    pack(ob)


def pack(ob):
    bake.select_only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=0.004, scale=True,
                            merge_overlap=False, shape_method="CONCAVE")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def strip_build_data(ob, attrs, uvs, keys=()):
    me = ob.data
    for name in attrs:
        geo.remove_attribute(ob, name)
    for name in uvs:
        layer = me.uv_layers.get(name)
        if layer is not None:
            me.uv_layers.remove(layer)
    for key in keys:
        if key in ob.keys():
            del ob[key]


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = objs[0]
    ob.name = ob.data.name = name
    return ob


def main():
    scene = bpy.context.scene
    arm = armature()
    g, s = glove("Left"), sleeve("Left")
    tracks = arm.animation_data.nla_tracks
    for tr in tracks:
        tr.mute = True
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    bake.setup(scene, ao_distance=0.03)
    unwrap_glove(g)
    unwrap_sleeve(s)
    albedo, normal, orm = bake.bake_atlas([g], f"{NAME}_glove", TEX_SIZE)
    glove_mat = bake.final_material(GLOVE_MAT, albedo, normal, orm)
    albedo, normal, orm = bake.bake_atlas([s], f"{NAME}_coat", TEX_SIZE)
    coat_mat = bake.final_material(COAT_MAT, albedo, normal, orm)
    bake.assign_single([g], glove_mat)
    bake.assign_single([s], coat_mat)
    bake.remove_source_materials()
    leather.remove_images()
    coat_leather.remove_images()
    strip_build_data(g, ("region",) + glove_geo.FINGER_ATTRS + glove_geo.CUFF_ATTRS, glove_geo.UV_HELPERS,
                     ("snap_center", "snap_normal", "orn_origin"))
    strip_build_data(s, sleeve_geo.ATTRS, sleeve_geo.UV_HELPERS)

    for name in ("ArmLeft", "ArmRight"):
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old)
    left = join([g, s], "ArmLeft")
    tag(left, "arm_left")
    rig.limit_weights(left, arm, 4)
    right = rig.mirror_mesh(left, "ArmRight", "Left", "Right")
    tag(right, "arm_right")

    for tr in tracks:
        tr.mute = False
    arm.data.pose_position = "POSE"
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
