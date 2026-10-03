"""Stage 3 build: Silena's body (called by build.py after the arms).

Order matters: the top and trousers are cut from the skin first, the boots, belt and
its items sit on them, the coat is shaped around all of them (and sewn to the stage-2
sleeves' armholes), then the collar, the coat's spring chains, the weights, the head
and the visible skin, and the procedural source materials. Every part is bound to the
one `Armature` and tagged (scene.tag) for bake.py:

  coat, collar (coat body atlas); top, trousers, boot_left, belt, hangers, thigh_strap,
  hair (outfit atlas); passkey_glow (plain emissive); head, skin_v (MPFB skin).

The right boot is the left one mirrored in bake.py (one texture region for both).
"""

import bpy
from mathutils.bvhtree import BVHTree

from silena_vesper_common import GLOW_MAT, SKIN_MAT, SLEEVE_COLUMNS, TECH_VIOLET, armature, body, sleeve
import belt
import boots
import clothes
import coat
import head
import outfit_materials as mats
from arcology_blender import garment, rig
from arcology_blender.scene import get_collection, part_objects, tag, tri_count
from arcology_blender.shading import solid_mat

GLOW_STRENGTH = 4.0
LEG_SKIN = ("Hips", "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg", "LeftFoot", "RightFoot",
            "LeftToes", "RightToes")


def bind(ob, arm):
    mod = ob.modifiers.get("Armature") or ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()


def deform_bones(arm):
    return sorted(b.name for b in arm.data.bones if b.use_deform)


def clean_groups(ob, arm):
    """Drop vertex groups that aren't deforming bones (MPFB's masks, helpers) or are empty
    (a transfer creates every group; an empty `Right*` group on the left boot would clash
    with the renamed ones when it is mirrored)."""
    keep = set(deform_bones(arm))
    used = {g.group for v in ob.data.vertices for g in v.groups if g.weight > 0.0}
    for vg in [vg for vg in ob.vertex_groups if vg.name not in keep or vg.index not in used]:
        ob.vertex_groups.remove(vg)


def weight_from_skin(ob, skin, arm, smooth=6):
    """Transfer from the skin, diffuse a little (fabric doesn't follow every skin
    detail), drop far bones, at most 4 per vertex."""
    bones = deform_bones(arm)
    garment.transfer_weights(skin, ob, groups=bones)
    present = [b for b in bones if ob.vertex_groups.get(b) is not None]
    garment.smooth_weights(ob, range(len(ob.data.vertices)), present, iterations=smooth, factor=0.5)
    rig.drop_far_weights(ob, arm, 0.10)
    rig.limit_weights(ob, arm, 4)
    clean_groups(ob, arm)


def sleeve_rims():
    """The left sleeve's armhole rim (the first ring of its closing dome) and its mirror."""
    sl = sleeve("Left")
    k0 = sl["rim_ring"] * SLEEVE_COLUMNS
    mw = sl.matrix_world
    left = [tuple(mw @ sl.data.vertices[k0 + k].co) for k in range(SLEEVE_COLUMNS)]
    return [left, [(-x, y, z) for x, y, z in left]]


def obstacles(skin, parts, mirrored=()):
    """BVH of what the skirt must clear: leg and hip skin, the garments, mirrored copies."""
    legs = skin.copy()
    legs.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(legs)
    rig.extract_by_weight(legs, LEG_SKIN, 0.3)
    verts, polys = [], []

    def add(ob, flip=False):
        off = len(verts)
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            if flip:
                p.x = -p.x
            verts.append(p)
        polys.extend([[i + off for i in p.vertices] for p in ob.data.polygons])

    for ob in [legs] + list(parts):
        add(ob)
    for ob in mirrored:
        add(ob, True)
    ld = legs.data
    bpy.data.objects.remove(legs)
    bpy.data.meshes.remove(ld)
    return BVHTree.FromPolygons(verts, polys)


def trim_top(top):
    """Delete the top where the coat body covers it for good: everything but the front
    opening (her eyes look under the lapels: up to 5 cm behind the coat's front edge, 2.5 cm
    above the bust) and the hem under the belt. The shoulders, armpits, sides, back and the
    neck's base (the skin shows there, head.py) go, so they can't poke through the coat when
    an arm rises."""
    def keep(c):
        margin = 0.05 if c.z < 1.42 else 0.025        # the panel lies closer above the bust
        front = c.y < coat.AXIS_Y + 0.02 and abs(c.x) < coat.front_edge_x(min(c.z, 1.50)) + margin
        hem = c.z < 1.06
        return front or hem

    return garment.delete_faces(top, [p.index for p in top.data.polygons if not keep(p.center)])


def opaque_skin(mat):
    """MPFB's GAMEENGINE skin feeds an alpha map into the BSDF (glTF would export a masked
    or blended material): the skin is opaque."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for link in list(bsdf.inputs["Alpha"].links):
        nt.links.remove(link)
    bsdf.inputs["Alpha"].default_value = 1.0
    for n in [n for n in nt.nodes if n.type == "TEX_IMAGE" and not n.outputs["Color"].links
              and not n.outputs["Alpha"].links]:
        nt.nodes.remove(n)


def build():
    arm = armature()
    skin = part_objects("skin_ref", mesh_only=True)[0]
    human = body()
    human.name = human.data.name = "Human"
    for m in human.data.materials:
        if m is not None and m.name != SKIN_MAT:
            m.name = SKIN_MAT
    opaque_skin(human.data.materials[0])
    coll = get_collection("Outfit")

    top = clothes.build_top(skin, coll)
    trousers = clothes.build_trousers(skin, coll)
    boot = boots.build_boot(skin, arm, coll, "Left")
    belt_ob, hangers, glow, ring = belt.build_belt(top, trousers, coll)
    strap = belt.build_thigh_strap(trousers, arm, coll, ring)
    obst = obstacles(skin, [top, trousers, boot, belt_ob, hangers, glow, strap], mirrored=[boot])
    coat_ob, info = coat.build_coat(skin, obst, sleeve_rims(), coll, top)
    collar = coat.build_collar(info, coat_ob, coll)
    coat.add_chains(arm, info)
    print(f"OUTFIT top trimmed under the coat: {trim_top(top)} faces")

    for ob in (top, trousers, boot):
        weight_from_skin(ob, skin, arm)
    belt.weight_rigid(belt_ob, "Hips")
    belt.weight_hangers(hangers)
    belt.weight_hangers(glow)
    belt.weight_thigh_strap(strap)
    coat.weight_coat(coat_ob, skin, arm, info)
    coat.weight_collar(collar, coat_ob, arm, info)

    head.add_ears(human)
    head_ob, skin_v = head.split_skin(human, coll)
    hair = head.build_hair(head_ob, coll)
    for ob in (head_ob, skin_v):
        clean_groups(ob, arm)
        rig.limit_weights(ob, arm, 4)

    skin_mat = human.data.materials[0]
    for ob, mat in ((coat_ob, mats.src_coat_body()), (collar, mats.src_collar()), (top, mats.src_top()),
                    (trousers, mats.src_trousers()), (boot, mats.src_boots()), (hair, mats.src_hair())):
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    gear = mats.src_gear()
    for ob in (belt_ob, hangers, strap):
        ob.data.materials.clear()
        ob.data.materials.append(gear)
    glow.data.materials.clear()
    glow.data.materials.append(solid_mat(GLOW_MAT, (0.06, 0.02, 0.16), 0.35, 0.0, TECH_VIOLET, GLOW_STRENGTH))
    for ob in (head_ob, skin_v):
        ob.data.materials.clear()
        ob.data.materials.append(skin_mat)
    for ob in (coat_ob, collar, top, trousers, boot, hair, belt_ob, hangers, strap, glow, head_ob, skin_v):
        for p in ob.data.polygons:
            p.material_index = 0

    parts = {"coat": coat_ob, "collar": collar, "top": top, "trousers": trousers, "boot_left": boot,
             "belt": belt_ob, "hangers": hangers, "thigh_strap": strap, "hair": hair, "passkey_glow": glow,
             "head": head_ob, "skin_v": skin_v}
    for name, ob in parts.items():
        bind(ob, arm)
        tag(ob, name)
        ob.data.update()
    bones = len(arm.data.bones)
    print("OUTFIT tris " + " ".join(f"{n}={tri_count(o)}" for n, o in parts.items()) + f" bones={bones}")
    return parts
