"""Stage 2: UV unwrap and bake PBR atlases (albedo, normal, ORM), join each glb's meshes, save.

  blender -b --factory-startup blender/props/wardrobe_lit.blend --python blender/props/wardrobe_lit/bake.py

Atlases: WardrobeBody (static carcass and interior, 2048), WardrobeProps (every
moving part: drawer, box with scarf, lid, three hangers, 1024), one per door
(1024). The body bakes without doors and props (they move). The props bake
together into one atlas, spread apart along X while baking (bake.Spread)
so the lid doesn't shadow the box and the shirts don't shadow each other; the
drawer stays in place (its fingerprint mask is positional). Each door bakes alone.
Afterwards every exported part is joined into one mesh, and the second drawer and
the other three bare hangers are added as linked instances (not exported).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import wardrobe_common as C  # noqa: E402
from arcology_blender import bake, geo, soft  # noqa: E402
from arcology_blender.scene import meshes, save_blend, tag  # noqa: E402


def main():
    bake.setup(bpy.context.scene)
    for ob in C.body_collision_objects():
        ob.hide_render = True
    left, right = meshes(C.door_left_objects()), meshes(C.door_right_objects())
    body = C.body_objects()
    props = meshes(C.prop_objects())
    bake.bake_part(body, "wardrobe_body", C.BODY_MAT, hide=left + right + props, size=C.BODY_TEX)
    roots = {p: bpy.data.objects[name] for p, (name, _) in C.PROPS.items()}
    spread = [(roots["box"], 2.0), (roots["lid"], 3.0), (roots["hanger"], 4.0),
              (roots["hanger_a"], 5.0), (roots["hanger_b"], 6.0)]
    with bake.Spread(spread):
        bake.bake_part(props, "wardrobe_props", C.PROPS_MAT, hide=body + left + right, size=C.PROPS_TEX)
    bake.bake_part(left, "wardrobe_door_left", C.DOOR_L_MAT, hide=body + props + right, size=C.DOOR_TEX)
    bake.bake_part(right, "wardrobe_door_right", C.DOOR_R_MAT, hide=body + props + left, size=C.DOOR_TEX)
    bake.remove_source_materials()
    for ob in body + props:
        geo.remove_attribute(ob, soft.SEAM_ATTR)  # build-time masks, keep them out of the glb

    tag(geo.join(body, "WardrobeBody"), "body")
    for label, objs in (("Left", left), ("Right", right)):
        root = bpy.data.objects[f"Door{label}"]
        geo.join([root] + [o for o in objs if o is not root], root.name)
    for part, root in roots.items():
        kids = [o for o in meshes(C.prop_objects(part)) if o is not root]
        if kids:
            geo.join([root] + kids, root.name)

    # Instances for the .blend and the thumbnails (Godot instances the glbs the same way)
    geo.instance(roots["drawer"], "DrawerRight", C.DRAWER_ORIGINS[1], part="instance")
    for i in C.BARE_HANGERS[1:]:
        geo.instance(roots["hanger"], f"Hanger{i}", (C.HANGERS_X[i], C.RAIL_Y, C.RAIL_Z + C.RAIL_R),
                    (0.0, 0.0, math.radians(C.HANGER_ROT_Z)), part="instance")
    bake.report_images()
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
