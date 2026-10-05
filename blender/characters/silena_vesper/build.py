"""Build: MPFB body + humanoid skeleton (with LowerArmTwist bones), the left glove
(geometry, weights, procedural leather), the hand poses, the left coat sleeve (geometry,
weights, procedural coat leather) (stages 1-2), then the body (stage 3, outfit.py: coat
body and collar sewn to the sleeves, top, trousers, boots, belt and its items, head,
visible skin, the coat's spring chains), then the eyes (stage 4, eyes.py: lashes and brows
fitted here while MPFB's helpers exist, the eyes, lids and shapes in outfit.py); saves the
.blend.

  blender -b --factory-startup --python blender/characters/silena_vesper/build.py

The right arm is the left one mirrored after baking (bake.py), so both share one
texture set per material.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, GLOVE_HIDE_T, HAND_LENGTH_RANGE, HEIGHT_TARGET, MACROS, RACE, SKIN, STRAP_T, STRAP_W, TARGETS, TWIST_AT,
    twist_factor,
)
import coat_leather  # noqa: E402
import eyes  # noqa: E402
import glove as glove_geo  # noqa: E402
import leather  # noqa: E402
import outfit  # noqa: E402
import poses  # noqa: E402
import sleeve as sleeve_geo  # noqa: E402
from arcology_blender import garment, human, rig  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag, tri_count  # noqa: E402

SMOOTH_ITERATIONS = 6  # weight diffusion over the hand (see weight_glove)


def build_body():
    body, arm = human.create_human(rig="game_engine", race=RACE, targets=TARGETS, **MACROS)
    m = human.measure(body, arm, "Left")
    human.set_skin(body, SKIN)
    eyes.fit(body, arm, get_collection("Reference"))      # stage 4: proxies need MPFB's helpers
    human.remove_helpers(body)
    rig.rename_bones(arm, rig.GAME_ENGINE_TO_HUMANOID)
    for side in rig.SIDES:
        rig.add_hand_joints(arm, side)
        rig.add_twist_bone(arm, f"{side}LowerArm", f"{side}LowerArmTwist", TWIST_AT)
    arm.name = arm.data.name = "Armature"
    body.name = body.data.name = "Body"
    coll = get_collection("Body")
    for ob in (body, arm):
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    tag(body, "body")
    arm["height"] = m["height"]
    arm["eye"] = tuple(m["eye"])
    arm["hand_length"] = m["hand_length"]
    print(f"BODY height={m['height']:.4f} (target {HEIGHT_TARGET}) eye={tuple(round(c, 4) for c in m['eye'])} "
          f"hand_length={m['hand_length']:.4f} (target {HAND_LENGTH_RANGE}) hand_width={m['hand_width']:.4f}")
    return body, arm


def bind(ob, arm):
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()


def weight_glove(ob, skin, arm, hf):
    """Weights by transfer from the skin, then the cuff, strap and snap rigid on
    the forearm, fading into the hand's weights before the strap; the forearm part
    shared between LowerArm and LowerArmTwist like the sleeve over it."""
    side = hf.side
    bones = glove_geo.arm_bones(side)
    twist = f"{side}LowerArmTwist"
    for vg in [vg for vg in ob.vertex_groups if vg.name in bones]:
        ob.vertex_groups.remove(vg)
    src = skin.copy()
    src.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(src)
    rig.extract_by_weight(src, bones, 0.3)
    garment.transfer_weights(src, ob, groups=bones)
    sd = src.data
    bpy.data.objects.remove(src)
    bpy.data.meshes.remove(sd)

    region = [d.value for d in ob.data.attributes["region"].data]
    lf = hf.limb
    factor = []
    for v, r in zip(ob.data.vertices, region):
        if round(r) != glove_geo.REGION_SHELL:
            factor.append(1.0)
        else:
            t = (v.co - lf.origin).dot(lf.axis)
            factor.append(glove_geo.smoothstep(t, 0.004, STRAP_T - STRAP_W * 0.5 + 0.002))
    weights = garment.rigid_blend(garment.weights_of(ob), f"{side}LowerArm", factor)
    keep = set(bones)
    weights = [{k: w for k, w in wd.items() if k in keep} for wd in weights]
    garment.set_weights(ob, weights)
    # softer transitions at the knuckles and the thumb's base keep volume when posed
    hand = [i for i, (v, r) in enumerate(zip(ob.data.vertices, region))
            if round(r) == glove_geo.REGION_SHELL and (v.co - lf.origin).dot(lf.axis) < 0.0]
    garment.smooth_weights(ob, hand, bones, iterations=SMOOTH_ITERATIONS, factor=0.5)
    # the web at the thumb's base folds hardest (the metacarpal turns ~45 degrees in the grip)
    thumb = f"{side}ThumbMetacarpal"
    in_hand = set(hand)
    web = [i for i, wd in enumerate(garment.weights_of(ob)) if i in in_hand and 0.02 < wd.get(thumb, 0.0) < 0.98]
    garment.smooth_weights(ob, web, bones, iterations=10, factor=0.5)
    print(f"WEIGHTS glove dropped {rig.drop_far_weights(ob, arm, 0.045)} stray weights")
    rig.limit_weights(ob, arm, 4)
    # stage 2: the forearm part rolls with LowerArmTwist like the sleeve over it
    ts = [(v.co - lf.origin).dot(lf.axis) for v in ob.data.vertices]
    weights = garment.split_weights(garment.weights_of(ob), f"{side}LowerArm", twist, [twist_factor(t) for t in ts])
    garment.set_weights(ob, weights)
    rig.limit_weights(ob, arm, 4)
    keep.add(twist)
    for vg in list(ob.vertex_groups):
        if vg.name not in keep:
            ob.vertex_groups.remove(vg)
    bind(ob, arm)


def weight_sleeve(ob, skin, arm, sf, side):
    """Transfer from the arm's skin (shoulder weights count as upper arm, hand weights as
    forearm: the sleeve doesn't follow the wrist), rigid on the upper arm toward the
    armhole and on the forearm below the elbow, a smoothed blend across the elbow, then
    the distal forearm shared with LowerArmTwist exactly like the glove's cuff."""
    shoulder, upper, lower, hand = (f"{side}{b}" for b in ("Shoulder", "UpperArm", "LowerArm", "Hand"))
    twist = f"{side}LowerArmTwist"
    groups = [shoulder, upper, lower, hand]
    src = skin.copy()
    src.data = skin.data.copy()
    bpy.context.scene.collection.objects.link(src)
    rig.extract_by_weight(src, groups, 0.3)
    garment.transfer_weights(src, ob, groups=groups)
    sd = src.data
    bpy.data.objects.remove(src)
    bpy.data.meshes.remove(sd)

    pt = [d.value for d in ob.data.attributes["pt"].data]
    region = [round(d.value) for d in ob.data.attributes["region"].data]
    weights = []
    for wd in garment.weights_of(ob):
        up = wd.get(shoulder, 0.0) + wd.get(upper, 0.0)
        lo = wd.get(lower, 0.0) + wd.get(hand, 0.0)
        tot = up + lo
        weights.append({upper: up / tot, lower: lo / tot} if tot > 0.0 else {lower: 1.0})
    weights = garment.rigid_blend(weights, upper, [glove_geo.smoothstep(t, sf.t_S - 0.17, sf.t_S - 0.11) for t in pt])
    weights = garment.rigid_blend(weights, upper, [glove_geo.smoothstep(t, sf.t_E + 0.045, sf.t_E + 0.075)
                                                   for t in pt])
    weights = garment.rigid_blend(weights, lower, [1.0 - glove_geo.smoothstep(t, sf.t_E - 0.10, sf.t_E - 0.06)
                                                   for t in pt])
    garment.set_weights(ob, weights)
    elbow = [i for i, (t, r) in enumerate(zip(pt, region))
             if r == sleeve_geo.R_BODY and abs(t - sf.t_E) < 0.10]
    garment.smooth_weights(ob, elbow, [upper, lower], iterations=10, factor=0.5)
    # the elbow's point: a narrow blend keeps it full when bent hard (a wide one pulls the
    # point toward the joint by cos(bend / 2)); the crook keeps the soft transferred blend
    rub = [d.value for d in ob.data.attributes["rub"].data]
    weights = garment.weights_of(ob)
    for i in elbow:
        m = min(1.0, rub[i] * 1.6)
        if m <= 0.0:
            continue
        narrow = 1.0 - glove_geo.smoothstep(pt[i], sf.t_E - 0.015, sf.t_E + 0.015)
        lo = weights[i].get(lower, 0.0) * (1.0 - m) + narrow * m
        weights[i] = {k: v for k, v in ((upper, 1.0 - lo), (lower, lo)) if v > 0.0}
    weights = garment.split_weights(weights, lower, twist, [twist_factor(t) for t in pt])
    garment.set_weights(ob, weights)
    rig.limit_weights(ob, arm, 4)
    for vg in list(ob.vertex_groups):
        if vg.name not in (upper, lower, twist):
            ob.vertex_groups.remove(vg)
    bind(ob, arm)


def cut_hidden_glove(ob, hf):
    """Delete the glove inside the sleeve: the gauntlet above GLOVE_HIDE_T, its rolled hem,
    lining and the disk closing it (the sleeve's opening hides the cut edge)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    reg = bm.verts.layers.float["region"]
    lf = hf.limb
    hidden = {v for v in bm.verts if round(v[reg]) in (glove_geo.REGION_HEM, glove_geo.REGION_LINING)
              or (round(v[reg]) == glove_geo.REGION_CUFF and (v.co - lf.origin).dot(lf.axis) > GLOVE_HIDE_T)}
    doomed = [f for f in bm.faces if all(v in hidden for v in f.verts)]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(doomed)


def main():
    clear_scene()
    body, arm = build_body()
    ref = get_collection("Reference")
    skin = garment.skin_copy(body, "SkinRef", ref)
    tag(skin, "skin_ref")
    gloves = get_collection("Gloves")
    ob, hf = glove_geo.build_glove(skin, arm, "Left", gloves)
    tag(ob, "glove_left")
    weight_glove(ob, skin, arm, hf)
    if ob.vertex_groups.get("fingernails"):
        ob.vertex_groups.remove(ob.vertex_groups["fingernails"])
    ob.data.materials.append(leather.src_leather(hf))
    poses.build_poses(arm, ob, hf)

    sleeves = get_collection("Sleeves")
    sl, sf, sb = sleeve_geo.build_sleeve(skin, arm, ob, hf, sleeves, "SleeveLeft")
    tag(sl, "sleeve_left")
    weight_sleeve(sl, skin, arm, sf, "Left")
    sl.data.materials.append(coat_leather.src_coat(sf))
    arm["t_elbow"], arm["t_shoulder"] = sf.t_E, sf.t_S
    sl["rim_ring"] = sb.b_end + 1          # the dome's first ring: stage 3 sews the coat body to it
    print(f"SLEEVE t_elbow={sf.t_E:.4f} t_shoulder={sf.t_S:.4f} rings={len(sb.vrings)}")
    print(f"GLOVE cut {cut_hidden_glove(ob, hf)} hidden faces")
    print(f"TRIS glove_left={tri_count(ob)} sleeve_left={tri_count(sl)} arm_left={tri_count(ob) + tri_count(sl)}")

    outfit.build()                         # stage 3: the body (after the arms, which it doesn't change)
    for o in (body, skin):
        o.hide_render = True
        o.hide_set(True)
    ref.hide_render = True
    save_blend(BLEND)


if __name__ == "__main__":
    main()
