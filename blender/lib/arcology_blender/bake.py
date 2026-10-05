"""Bake procedural `src_*` materials into one PBR atlas set per part.

`bake_part` UV-unwraps a part's objects into one shared atlas, bakes base
color, roughness, metallic (via emission), a tangent-space normal map and AO,
packs roughness/metallic/AO into a glTF ORM image, and replaces the source
materials with one final material that the glTF exporter writes losslessly
(baseColor, metallicRoughness + occlusion, normal). Options: `weight` gives
barely visible faces less texture space (`uv_unwrap_weighted`), `emission`
bakes an extra emission atlas for switchable lights (exported as
emissiveTexture + KHR_materials_emissive_strength).

AO sees every object that renders: bake a part alone (`hide` the others)
when they move apart in the game (doors, drawers, a lid), or `Spread` parts
that share one atlas apart while baking. Parts that never move (cushions on
a frame, bedding on a bed) bake together for contact shadows.
"""

import math
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from .scene import set_colorspace, setup_gpu

# Soften baked AO: Godot adds SSAO on top.
AO_FLOOR = 0.65


def setup(scene, ao_distance=0.35):
    """Bake settings shared by every part. Call once before bake_part."""
    setup_gpu(scene)
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    try:
        scene.world.light_settings.distance = ao_distance
    except Exception as exc:
        print("AO distance not settable:", exc)


def bakeable(objs):
    """Mesh objects whose materials are all procedural sources (src_*)."""
    return [ob for ob in objs
            if ob.type == "MESH" and ob.data.materials
            and all(m is not None and m.name.startswith("src_") for m in ob.data.materials)]


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def uv_unwrap(objs, angle_limit=66.0, island_margin=0.002, pack_margin=0.004):
    """Smart-project all objects together and pack them into one 0..1 atlas."""
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=island_margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=pack_margin,
                                scale=True, merge_overlap=False, shape_method="CONCAVE")
    except Exception as exc:
        print("pack_islands failed:", exc)
    bpy.ops.object.mode_set(mode="OBJECT")


def _islands(bm, uv):
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    bm.faces.index_update()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        m1 = {l.vert: l[uv].uv for l in f1.loops}
        m2 = {l.vert: l[uv].uv for l in f2.loops}
        if all((m1[v] - m2[v]).length < 1e-5 for v in e.verts):
            a, b = find(f1.index), find(f2.index)
            if a != b:
                parent[a] = b
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return list(groups.values())


def uv_unwrap_weighted(objs, weight, angle_limit=66.0, island_margin=0.002, pack_margin=0.004):
    """Like uv_unwrap, but islands get a relative texel density:
    weight(ob, face_center_world, face_normal_world) -> factor (1 = normal,
    0.2 for faces that are barely visible, like the underside of a bed).
    An island takes the largest weight among its faces."""
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=island_margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for ob in objs:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for isl in _islands(bm, uv):
            w = max(weight(ob, mw @ f.calc_center_median(), (nm @ f.normal).normalized()) for f in isl)
            if abs(w - 1.0) < 1e-6:
                continue
            loops = [lp for f in isl for lp in f.loops]
            c = sum((lp[uv].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
            for lp in loops:
                lp[uv].uv = c + (lp[uv].uv - c) * w
        bm.to_mesh(ob.data)
        bm.free()
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=pack_margin,
                            scale=True, merge_overlap=False, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def new_image(name, size, colorspace):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, size, size, alpha=False)
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
    bpy.context.scene.cycles.samples = samples
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


def bake_atlas(objs, prefix, size=2048, ao_samples=48):
    """Bake <prefix>_albedo, <prefix>_normal and <prefix>_orm (packed images)."""
    mats = src_materials(objs)
    albedo = new_image(f"{prefix}_albedo", size, "sRGB")
    normal = new_image(f"{prefix}_normal", size, "Non-Color")
    orm = new_image(f"{prefix}_orm", size, "Non-Color")
    tmp_ao = new_image("tmp_ao", size, "Non-Color")
    tmp_rough = new_image("tmp_rough", size, "Non-Color")
    tmp_metal = new_image("tmp_metal", size, "Non-Color")

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
    bake(objs, "AO", samples=ao_samples)

    ao = pixels(tmp_ao)
    out = np.ones_like(ao)
    out[..., 0] = np.clip(ao[..., 0] * (1.0 - AO_FLOOR) + AO_FLOOR, 0.0, 1.0)
    out[..., 1] = pixels(tmp_rough)[..., 0]
    out[..., 2] = pixels(tmp_metal)[..., 0]
    orm.pixels.foreach_set(out.ravel())
    for img in (albedo, normal, orm):
        img.pack()
    for img in (tmp_ao, tmp_rough, tmp_metal):
        bpy.data.images.remove(img)
    return albedo, normal, orm


def _gltf_occlusion_group():
    """The node group the glTF exporter reads occlusion from."""
    ng = bpy.data.node_groups.get("glTF Material Output")
    if ng is None:
        ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        ng.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        inp = ng.nodes.new("NodeGroupInput")
        inp.location = (-200, 0)
    return ng


def final_material(name, albedo, normal, orm):
    """Principled material from baked images, laid out the way the glTF exporter expects.
    `normal=None` leaves the normal input unconnected (surfaces without relief: an eye)."""
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
    grp.node_tree = _gltf_occlusion_group()
    grp.location = (300, -500)
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])

    if normal is None:
        return m
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = normal
    tn.location = (-400, -300)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (-100, -300)
    nm.inputs["Strength"].default_value = 1.0
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def assign_single(objs, mat):
    for ob in objs:
        me = ob.data
        me.materials.clear()
        me.materials.append(mat)
        for p in me.polygons:
            p.material_index = 0


def _link_emission(mat, image, strength):
    """Connect an emission image to a final material's Emission Color with `strength`."""
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    te = nt.nodes.new("ShaderNodeTexImage")
    te.image = image
    te.location = (-400, -600)
    nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength


def bake_part(objs, prefix, material_name, hide=(), size=2048, weight=None, emission=None):
    """Unwrap, bake and assign the final material for one exported part.

    objs: the part's objects (non-src_ materials such as glass or lights are
    skipped and keep their material). hide: other objects to hide while
    baking, so they don't shadow the AO (e.g. the door while baking the body).
    weight: optional weight(ob, center, normal) -> texel density factor for
    `uv_unwrap_weighted` (less space for hidden undersides).
    emission: optional strength; the src_ materials' "Emission Color" (a
    glow pattern: a lamp shade, a lit bulb) is baked into <prefix>_emission
    (sRGB) and linked with that strength, so the glTF exporter writes
    emissiveTexture + KHR_materials_emissive_strength and Godot can switch
    the light by the material's emission energy.
    """
    targets = bakeable(objs)
    label = " (emissive)" if emission is not None else ""
    print(f"BAKE {prefix}{label}: {[o.name for o in targets]}")
    if weight is None:
        uv_unwrap(targets)
    else:
        uv_unwrap_weighted(targets, weight)
    for ob in hide:
        ob.hide_render = True
    albedo, normal, orm = bake_atlas(targets, prefix, size)
    emission_img = None
    if emission is not None:
        mats = src_materials(targets)
        emission_img = new_image(f"{prefix}_emission", size, "sRGB")
        set_bake_target(mats, emission_img)
        with EmitOverride(mats, "Emission Color"):
            bake(targets, "EMIT")
        emission_img.pack()
    mat = final_material(material_name, albedo, normal, orm)
    if emission_img is not None:
        _link_emission(mat, emission_img, emission)
    assign_single(targets, mat)
    for ob in hide:
        ob.hide_render = False
    return mat


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def emissive_from_albedo(mat, albedo, tint, strength=1.0, name=None):
    """Give a baked material an emissive texture derived from its albedo
    (linear albedo times `tint`, e.g. a warm 2700 K color), so the surface
    glows with its own texture (a lamp shade's weave) without a second bake.
    `strength` becomes the glTF emissive strength; Godot scales it with
    `emission_energy_multiplier`. Returns the packed image."""
    name = name or albedo.name.replace("_albedo", "") + "_emissive"
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    src = pixels(albedo)
    out = np.ones_like(src)
    out[..., :3] = _linear_to_srgb(_srgb_to_linear(src[..., :3]) * np.asarray(tint, dtype=np.float32))
    img = bpy.data.images.new(name, albedo.size[0], albedo.size[1], alpha=False)
    set_colorspace(img, "sRGB")
    img.pixels.foreach_set(out.ravel())
    img.pack()
    _link_emission(mat, img, strength)
    return img


class Spread:
    """Context manager: temporarily move groups of objects apart along one world
    axis, so separate parts baked into one shared atlas (bake_part with all
    of them) don't darken each other's AO, e.g. a lid resting on its box, or
    garments hanging side by side that are picked up separately.

    groups: [(root_object, offset_m), ...]; children follow their root. The
    procedural materials must not depend on the world position along `axis`
    (0 = X, 2 = Z) for the moved parts, or the offsets must keep them in the
    same mask regions; keep offset 0 for parts whose masks do.
    """

    def __init__(self, groups, axis=0):
        self.groups = groups
        self.axis = axis

    def __enter__(self):
        for ob, off in self.groups:
            ob.location[self.axis] += off
        bpy.context.view_layer.update()
        return self

    def __exit__(self, *args):
        for ob, off in self.groups:
            ob.location[self.axis] -= off
        bpy.context.view_layer.update()


def remove_source_materials():
    for m in list(bpy.data.materials):
        if m.name.startswith("src_"):
            bpy.data.materials.remove(m)


def report_images():
    """Print every image with its size and whether it is packed (end of a bake stage)."""
    for img in bpy.data.images:
        print(f"IMAGE {img.name} {img.size[0]}x{img.size[1]} packed={img.packed_file is not None}")
