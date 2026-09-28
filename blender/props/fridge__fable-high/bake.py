"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM), finalize materials, save.

  blender -b --factory-startup <blend> --python bake.py
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from fridge_common import (  # noqa: E402
    BLEND, BODY_MAT, DOOR_MAT, TEX_SIZE, body_collision_objects, body_objects, door_objects,
    set_colorspace, setup_gpu,
)


def bakeable(objs):
    """Objects whose materials are procedural sources (src_*)."""
    out = []
    for ob in objs:
        if ob.type != "MESH" or not ob.data.materials:
            continue
        if all(m is not None and m.name.startswith("src_") for m in ob.data.materials):
            out.append(ob)
    return out


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def uv_unwrap(objs):
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.002,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=0.004,
                                scale=True, merge_overlap=False, shape_method="CONCAVE")
        print("pack_islands OK")
    except Exception as exc:
        print("pack_islands failed:", exc)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Report UV bounding boxes to confirm a joint packing (no object should span 0..1 alone)
    for ob in objs:
        uv = ob.data.uv_layers.active.data
        us = [l.uv.x for l in uv]
        vs = [l.uv.y for l in uv]
        print(f"  UV {ob.name:20s} u {min(us):.3f}..{max(us):.3f} v {min(vs):.3f}..{max(vs):.3f}")


def new_image(name, colorspace, alpha=False):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, TEX_SIZE, TEX_SIZE, alpha=alpha)
    set_colorspace(img, colorspace)
    return img


def src_materials(objs):
    mats = []
    for ob in objs:
        for m in ob.data.materials:
            if m not in mats:
                mats.append(m)
    return mats


def set_bake_target(mats, image):
    for m in mats:
        nt = m.node_tree
        node = nt.nodes.get("BakeTarget")
        if node is None:
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = "BakeTarget"
        node.image = image
        nt.nodes.active = node


class EmitOverride:
    """Temporarily route a Principled input into an Emission shader (bake type EMIT)."""

    def __init__(self, mats, socket):
        self.mats = mats
        self.socket = socket

    def __enter__(self):
        for m in self.mats:
            nt = m.node_tree
            bsdf = nt.nodes["BSDF"]
            out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
            em = nt.nodes.new("ShaderNodeEmission")
            em.name = "TMP_EMIT"
            sock = bsdf.inputs[self.socket]
            if sock.is_linked:
                nt.links.new(sock.links[0].from_socket, em.inputs["Color"])
            else:
                v = sock.default_value
                em.inputs["Color"].default_value = (v, v, v, 1.0) if isinstance(v, float) else tuple(v)
            em.inputs["Strength"].default_value = 1.0
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        return self

    def __exit__(self, *args):
        for m in self.mats:
            nt = m.node_tree
            em = nt.nodes.get("TMP_EMIT")
            if em is not None:
                nt.nodes.remove(em)
            out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
            nt.links.new(nt.nodes["BSDF"].outputs[0], out.inputs["Surface"])


def bake(objs, bake_type, samples=1, **kwargs):
    scene = bpy.context.scene
    scene.cycles.samples = samples
    select_only(objs)
    t0 = time.time()
    bpy.ops.object.bake(type=bake_type, margin=8, margin_type="EXTEND",
                        use_selected_to_active=False, use_clear=True, **kwargs)
    print(f"  bake {bake_type} {time.time() - t0:.1f}s")


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def bake_group(objs, prefix):
    mats = src_materials(objs)
    albedo = new_image(f"{prefix}_albedo", "sRGB")
    normal = new_image(f"{prefix}_normal", "Non-Color")
    orm = new_image(f"{prefix}_orm", "Non-Color")
    tmp_ao = new_image("tmp_ao", "Non-Color")
    tmp_rough = new_image("tmp_rough", "Non-Color")
    tmp_metal = new_image("tmp_metal", "Non-Color")

    set_bake_target(mats, albedo)
    with EmitOverride(mats, "Base Color"):
        bake(objs, "EMIT")
    set_bake_target(mats, tmp_rough)
    with EmitOverride(mats, "Roughness"):
        bake(objs, "EMIT")
    set_bake_target(mats, tmp_metal)
    with EmitOverride(mats, "Metallic"):
        bake(objs, "EMIT")
    set_bake_target(mats, normal)
    bake(objs, "NORMAL", normal_space="TANGENT")
    set_bake_target(mats, tmp_ao)
    bake(objs, "AO", samples=48)

    ao = pixels(tmp_ao)
    rough = pixels(tmp_rough)
    metal = pixels(tmp_metal)
    out = np.ones_like(ao)
    out[..., 0] = np.clip(ao[..., 0] * 0.35 + 0.65, 0.0, 1.0)  # soften AO: Godot adds SSAO on top
    out[..., 1] = rough[..., 0]
    out[..., 2] = metal[..., 0]
    orm.pixels.foreach_set(out.ravel())
    for img in (albedo, normal, orm):
        img.pack()
    for img in (tmp_ao, tmp_rough, tmp_metal):
        bpy.data.images.remove(img)
    return albedo, normal, orm


def gltf_ao_group():
    ng = bpy.data.node_groups.get("glTF Material Output")
    if ng is None:
        ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        ng.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        inp = ng.nodes.new("NodeGroupInput")
        inp.location = (-200, 0)
    return ng


def final_material(name, albedo, normal, orm):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = albedo
    ta.location = (-400, 300)
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])

    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = orm
    to.location = (-400, 0)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-100, 0)
    nt.links.new(to.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = gltf_ao_group()
    grp.location = (300, -500)
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])

    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = normal
    tn.location = (-400, -300)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (-100, -300)
    nm.inputs["Strength"].default_value = 1.0
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def assign_final(objs, mat):
    for ob in objs:
        me = ob.data
        me.materials.clear()
        me.materials.append(mat)
        for p in me.polygons:
            p.material_index = 0


def main():
    scene = bpy.context.scene
    setup_gpu(scene)
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    try:
        scene.world.light_settings.distance = 0.35
    except Exception as exc:
        print("AO distance not settable:", exc)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")

    body = bakeable(body_objects())
    door = bakeable(door_objects())
    cols = body_collision_objects()
    for ob in cols:
        ob.hide_render = True

    print("BODY bake objects:", [o.name for o in body])
    print("DOOR bake objects:", [o.name for o in door])

    # material slot stats for the cabinet (sanity check of the region assignment)
    cab = bpy.data.objects["Cabinet"]
    counts = {}
    for p in cab.data.polygons:
        counts[cab.data.materials[p.material_index].name] = counts.get(cab.data.materials[p.material_index].name, 0) + 1
    print("Cabinet material faces:", counts)

    uv_unwrap(body)
    uv_unwrap(door)

    for ob in door_objects():
        if ob.type == "MESH":
            ob.hide_render = True
    a, n, o = bake_group(body, "fridge_body")
    body_mat = final_material(BODY_MAT, a, n, o)
    assign_final(body, body_mat)
    for ob in door_objects():
        ob.hide_render = False

    for ob in body_objects():
        ob.hide_render = True
    a, n, o = bake_group(door, "fridge_door")
    door_mat = final_material(DOOR_MAT, a, n, o)
    assign_final(door, door_mat)
    for ob in body_objects():
        ob.hide_render = False

    for m in list(bpy.data.materials):
        if m.name.startswith("src_"):
            bpy.data.materials.remove(m)
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")

    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=False)
    print("SAVED", BLEND)


if __name__ == "__main__":
    main()
