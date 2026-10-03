"""Stage 1: MPFB body + humanoid skeleton, the left glove (geometry, weights,
procedural leather), the hand poses; saves the .blend.

  blender -b --factory-startup --python blender/characters/silena_vesper/build.py

The right glove is the left one mirrored after baking (bake.py), so both share
one texture set.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from silena_vesper_common import (  # noqa: E402
    BLEND, HAND_LENGTH_RANGE, HEIGHT_TARGET, MACROS, RACE, SKIN, STRAP_T, STRAP_W, TARGETS,
)
import glove as glove_geo  # noqa: E402
import leather  # noqa: E402
import poses  # noqa: E402
from arcology_blender import garment, human, rig  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag, tri_count  # noqa: E402

SMOOTH_ITERATIONS = 6  # weight diffusion over the hand (see weight_glove)


def build_body():
    body, arm = human.create_human(rig="game_engine", race=RACE, targets=TARGETS, **MACROS)
    m = human.measure(body, arm, "Left")
    human.set_skin(body, SKIN)
    human.remove_helpers(body)
    rig.rename_bones(arm, rig.GAME_ENGINE_TO_HUMANOID)
    for side in rig.SIDES:
        rig.add_hand_joints(arm, side)
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


def weight_glove(ob, skin, arm, hf):
    """Weights by transfer from the skin, then the cuff, strap and snap rigid on
    the lower arm, fading into the hand's weights before the strap."""
    side = hf.side
    bones = glove_geo.arm_bones(side)
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
    print(f"WEIGHTS dropped {rig.drop_far_weights(ob, arm, 0.045)} stray weights")
    rig.limit_weights(ob, arm, 4)
    for vg in list(ob.vertex_groups):
        if vg.name not in keep:
            ob.vertex_groups.remove(vg)

    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()


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
    for o in (body, skin):
        o.hide_render = True
        o.hide_set(True)
    ref.hide_render = True
    print(f"TRIS glove_left={tri_count(ob)}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
