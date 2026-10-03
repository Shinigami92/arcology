"""Stage 3: one glb per arm into assets/characters/silena_vesper/ (not saved).

  blender -b --factory-startup blender/characters/silena_vesper.blend --python blender/characters/silena_vesper/export.py

Each glb (`silena_vesper_arm_<side>.glb`) holds a copy of the skeleton pruned to
`<Side>UpperArm` and below (upper arm, lower arm, LowerArmTwist, hand, fingers,
OpenXR palm/metacarpal/tip joints) and the arm (glove + coat sleeve, one mesh
`Arm<Side>` with the materials SilenaGlove and SilenaCoat) bound to it, in body
coordinates (Godot places the hand at the controller and solves the elbow), with
the hand poses as animations (`Open`, `Grip`).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from silena_vesper_common import GLB, arm_mesh, armature  # noqa: E402
from arcology_blender import rig  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def export_side(side):
    src_arm, src_mesh = armature(), arm_mesh(side)
    names = (src_arm.name, src_arm.data.name, src_mesh.name, src_mesh.data.name)
    src_arm.name = src_arm.data.name = "ArmatureSource"
    src_mesh.name = src_mesh.data.name = f"Arm{side}Source"
    coll = src_mesh.users_collection[0]

    arm = src_arm.copy()
    arm.data = src_arm.data.copy()
    arm.name = arm.data.name = "Armature"
    coll.objects.link(arm)
    ob = src_mesh.copy()
    ob.data = src_mesh.data.copy()
    ob.name = ob.data.name = f"Arm{side}"
    coll.objects.link(ob)
    ob.parent = arm
    ob.modifiers["Armature"].object = arm
    for tr in arm.animation_data.nla_tracks:
        tr.mute = False
    rig.prune_bones(arm, rig.subtree(arm, f"{side}UpperArm"))
    rig.limit_weights(ob, arm, 4)
    bpy.context.view_layer.update()
    export_glb([arm, ob], GLB[side], rigged=True)

    for o in (ob, arm):
        data = o.data
        bpy.data.objects.remove(o)
        (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.armatures).remove(data)
    src_arm.name, src_arm.data.name, src_mesh.name, src_mesh.data.name = names


def main():
    for side in ("Left", "Right"):
        export_side(side)


if __name__ == "__main__":
    main()
