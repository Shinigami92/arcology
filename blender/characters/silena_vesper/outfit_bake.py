"""Stage 3 bake (called by bake.py after the arms): the body's two atlases and the
exported meshes.

1. Coat body atlas (`SilenaCoatBody`, 2048): the coat and the collar, unwrapped along
   their pattern seams (center back, side and shoulder seams, the rolled edges between
   leather and lining) with a minimum-stretch unwrap; the lining gets half the texel
   density. Everything else is hidden while it bakes (the legs move inside the skirt).
2. Outfit atlas (`SilenaOutfit`, 2048): top, trousers, the left boot, belt and items,
   thigh strap, hair (smart project, less space for soles and hair); baked together for
   contact shadows, the coat hidden.
3. The right boot is the left one mirrored (same UVs and texture region).
4. Body arms: copies of ArmLeft/ArmRight without the sleeve's closing dome, the sleeve's
   top re-weighted toward the skin's own weights over the last ARMHOLE_BLEND meters, so
   the shoulder and chest carry the armhole like the coat body sewn to it.
5. `Body` = arms + coat + top + trousers + boots + belt, items, glow + visible skin;
   `HeadMesh` = head + hair + eyes + lashes + brows (shape keys merged by name: the head's
   and lashes' BlinkLeft / BlinkRight / LookDownLids, the rest at their basis); `Collar` stays. The coat's armhole rims are merged with the
   sleeves' (same points, the sleeve's weights). Build-time data removed.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from silena_vesper_common import COAT_BODY_MAT, NAME, OUTFIT_MAT, TEX_SIZE, outfit_parts
import belt as belt_geo
import boots as boots_geo
import clothes
import coat as coat_geo
import head as head_geo
import outfit_materials
from arcology_blender import bake, garment, geo, rig
from arcology_blender.scene import tag

ARMHOLE_BLEND = 0.09           # sleeve re-weighted toward the skin within this distance of the rim
LINING_DENSITY = 0.12
BACK_DENSITY = 0.30
HAIR_DENSITY = 0.55
SOLE_DENSITY = 0.35


def one(part):
    obs = outfit_parts(part)
    return obs[0] if obs else None


def select_only(objs):
    bake.select_only(objs)


def unwrap_seams(objs, density):
    """Minimum-stretch unwrap along the marked seams, islands scaled by `density(ob,
    island faces)`, packed into one atlas."""
    select_only(objs)
    for ob in objs:
        me = ob.data
        uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        me.uv_layers.active = uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.002)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    _scale_islands(objs, density)
    _pack(objs)


def unwrap_smart(objs, density):
    select_only(objs)
    for ob in objs:
        me = ob.data
        uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        me.uv_layers.active = uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    _scale_islands(objs, density)
    _pack(objs)


def _scale_islands(objs, density):
    for ob in objs:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        layer = bm.loops.layers.uv["UVMap"]
        for isl in bake._islands(bm, layer):
            k = density(ob, bm, isl)
            if abs(k - 1.0) < 1e-6:
                continue
            loops = [lp for f in isl for lp in f.loops]
            c = sum((lp[layer].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
            for lp in loops:
                lp[layer].uv = c + (lp[layer].uv - c) * math.sqrt(k)
        bm.to_mesh(ob.data)
        bm.free()


def _pack(objs):
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=0.003, scale=True,
                            merge_overlap=False, shape_method="CONCAVE")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _attr_density(name, codes, value):
    def density(ob, bm, isl):
        layer = bm.verts.layers.float.get(name)
        if layer is None:
            return 1.0
        vals = [round(v[layer]) for f in isl for v in f.verts]
        share = sum(c in codes for c in vals) / len(vals)
        return value if share > 0.5 else 1.0
    return density


def coat_density(ob, bm, isl):
    """The front panels (in view when she looks down) get the most texels, the back pieces
    BACK_DENSITY, the lining LINING_DENSITY (area shares, packed afterwards)."""
    if ob.name != "Coat":
        return 1.0
    region = bm.verts.layers.float["region"]
    cu, cl = bm.verts.layers.float["cu"], bm.verts.layers.float["cl"]
    verts = {v for f in isl for v in f.verts}
    if sum(round(v[region]) == coat_geo.R_LINING for v in verts) > len(verts) * 0.5:
        return LINING_DENSITY
    edge = sum(min(v[cu], v[cl] - v[cu]) / max(v[cl], 1e-6) for v in verts) / len(verts)
    return 1.0 if edge < coat_geo.SIDE_SEAM_U else BACK_DENSITY


def outfit_density(ob, bm, isl):
    if ob.name == "Hair":
        return HAIR_DENSITY
    if ob.name == "BootLeft":
        return _attr_density("region", (boots_geo.B_SOLE, boots_geo.B_LINING), SOLE_DENSITY)(ob, bm, isl)
    return 1.0


def bake_atlases():
    scene = bpy.context.scene
    coat, collar = one("coat"), one("collar")
    outfit = [one(p) for p in ("top", "trousers", "boot_left", "belt", "hangers", "thigh_strap", "hair")]
    every = [ob for ob in bpy.data.objects if ob.type == "MESH" and not ob.hide_render]
    saved = {ob: ob.hide_render for ob in bpy.data.objects}
    scene.world.light_settings.distance = 0.05
    # coat body atlas
    for ob in every:
        ob.hide_render = ob not in (coat, collar)
    unwrap_seams([coat, collar], coat_density)
    albedo, normal, orm = bake.bake_atlas([coat, collar], f"{NAME}_coat_body", TEX_SIZE)
    mat = bake.final_material(COAT_BODY_MAT, albedo, normal, orm)
    bake.assign_single([coat, collar], mat)
    # outfit atlas
    for ob in every:
        ob.hide_render = ob not in outfit
    unwrap_smart(outfit, outfit_density)
    albedo, normal, orm = bake.bake_atlas(outfit, f"{NAME}_outfit", TEX_SIZE)
    mat = bake.final_material(OUTFIT_MAT, albedo, normal, orm)
    bake.assign_single(outfit, mat)
    for ob, h in saved.items():
        ob.hide_render = h
    outfit_materials.remove_images()


def strip(ob):
    attrs = set(coat_geo.ATTRS) | set(coat_geo.COLLAR_ATTRS) | set(clothes.ATTRS) | set(boots_geo.ATTRS) \
        | set(belt_geo.ATTRS) | set(head_geo.HAIR_ATTRS) | {"dome"}
    for name in attrs:
        geo.remove_attribute(ob, name)
    for uv in [u.name for u in ob.data.uv_layers if u.name != "UVMap"]:
        ob.data.uv_layers.remove(ob.data.uv_layers[uv])


# --- arms for the body ------------------------------------------------------------------------
def body_arm(src, name, skin, arm):
    """Copy of an exported arm without the sleeve's dome; the sleeve near the armhole
    blends into the skin's weights (all bones), exactly the skin's at the rim."""
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    src.users_collection[0].objects.link(ob)
    dome = ob.data.attributes["dome"].data
    garment.delete_faces(ob, [p.index for p in ob.data.polygons if dome[p.index].value])
    geo.remove_attribute(ob, "dome")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    rim = [v.co.copy() for v in bm.verts if v.is_boundary and v.co.z > 1.40 and abs(v.co.x) > 0.15]
    bm.free()
    bones = sorted(b.name for b in arm.data.bones if b.use_deform)
    sampler = garment.WeightSampler(skin, bones)
    side = "Left" if name.endswith("Left") else "Right"
    weights = garment.weights_of(ob)
    me = ob.data
    for v in me.vertices:
        d = min((v.co - r).length for r in rim)
        f = 1.0 - coat_geo.smoothstep(d, 0.0, ARMHOLE_BLEND)
        if f <= 0.0:
            continue
        ws = coat_geo.with_arm_follow(sampler.at(v.co), side, d)
        w = {k: x * (1.0 - f) for k, x in weights[v.index].items()}
        for k, x in ws.items():
            w[k] = w.get(k, 0.0) + x * f
        weights[v.index] = garment.limit_dict(w, 4)
    garment.set_weights(ob, weights)
    rig.limit_weights(ob, arm, 4)
    return ob


PART_IDS = {"arm": 1, "coat": 2, "top": 3, "trousers": 4, "belt": 5, "hangers": 6, "passkey_glow": 7,
            "thigh_strap": 8, "skin_v": 9, "boot": 10, "head": 11, "hair": 12, "eyes": 13, "lashes": 14,
            "brows": 15}


def mark_part(ob, pid):
    """Face attribute `part` (PART_IDS): which garment a face of a joined mesh came from
    (verify.py's intersection checks; glTF doesn't export face attributes)."""
    a = ob.data.attributes.get("part") or ob.data.attributes.new("part", "INT", "FACE")
    a.data.foreach_set("value", [pid] * len(ob.data.polygons))


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.hide_set(False)
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = objs[0]
    ob.name = ob.data.name = name
    return ob


def weld_armholes(body):
    """Merge the coat's rim rings with the sleeves' (same points): the sleeve's weights win."""
    me = body.data
    mats = [m.name for m in me.materials]
    coat_i = mats.index(COAT_BODY_MAT)
    sleeve_i = mats.index("SilenaCoat")
    coat_v, sleeve_v = set(), set()
    for p in me.polygons:
        if p.material_index == coat_i:
            coat_v.update(p.vertices)
        elif p.material_index == sleeve_i:
            sleeve_v.update(p.vertices)
    from mathutils.kdtree import KDTree

    kd = KDTree(len(sleeve_v))
    for i in sleeve_v:
        kd.insert(me.vertices[i].co, i)
    kd.balance()
    weights = garment.weights_of(body)
    pairs = []
    for i in coat_v:
        _, j, d = kd.find(me.vertices[i].co)
        if j is not None and d < 1e-6:
            weights[i] = dict(weights[j])
            pairs.append((i, j))
    garment.set_weights(body, weights)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    targetmap = {bm.verts[i]: bm.verts[j] for i, j in pairs}
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(pairs)


def build_meshes(arm):
    skin = outfit_parts("skin_ref")[0] if outfit_parts("skin_ref") else None
    boot_l = one("boot_left")
    boot_r = rig.mirror_mesh(boot_l, "BootRight", "Left", "Right")
    tag(boot_r, "boot_right")
    arms = [body_arm(bpy.data.objects[f"Arm{s}"], f"BodyArm{s}", skin, arm) for s in ("Left", "Right")]
    for name in ("ArmLeft", "ArmRight"):
        geo.remove_attribute(bpy.data.objects[name], "dome")
    parts = [one(p) for p in ("coat", "top", "trousers", "belt", "hangers", "passkey_glow", "thigh_strap",
                              "skin_v")] + [boot_l, boot_r]
    face_parts = [one(p) for p in ("eyes", "lashes", "brows")]
    for ob in parts + [one("collar"), one("head"), one("hair")] + face_parts:
        strip(ob)
    for ob in arms:
        mark_part(ob, PART_IDS["arm"])
    for ob in parts:
        p = ob.get("arcology_part")
        mark_part(ob, PART_IDS["boot"] if p.startswith("boot") else PART_IDS[p])
    mark_part(one("head"), PART_IDS["head"])
    mark_part(one("hair"), PART_IDS["hair"])
    for ob in face_parts:
        mark_part(ob, PART_IDS[ob["arcology_part"]])
    body = join(arms + parts, "Body")
    tag(body, "body_mesh")
    welded = weld_armholes(body)
    head = join([one("head"), one("hair")] + face_parts, "HeadMesh")
    tag(head, "head_mesh")
    collar = one("collar")
    collar.name = collar.data.name = "Collar"
    tag(collar, "collar_mesh")
    for ob in (body, head, collar):
        rig.limit_weights(ob, arm, 4)
    print(f"BODY welded {welded} armhole vertices")
    return body, head, collar
