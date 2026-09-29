"""Stage 3: export the body glb (with collision), one glb per door (origin on its hinge
axis) and one per moving part (drawer, box, lid, three hangers; origins per wardrobe_common).

  blender -b --factory-startup blender/props/wardrobe__opus-high.blend --python blender/props/wardrobe__opus-high/export.py

Grip Empties are named `HandleGrip` in the glbs; in the .blend they are
`HandleGrip.L`, `HandleGrip.R` and `HandleGrip.D` (names are unique there) and
get renamed for their export.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import wardrobe_common as C  # noqa: E402
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402
from arcology_blender.scene import part_objects  # noqa: E402


def export_part(root_name, objs, path, grip=None):
    g = bpy.data.objects[grip] if grip else None
    if g is not None:
        g.name = "HandleGrip"
    export_glb_at_origin(bpy.data.objects[root_name], objs, path)
    if g is not None:
        g.name = grip


def main():
    export_glb(C.body_objects() + C.body_collision_objects(), C.GLB_BODY)
    export_part("DoorLeft", C.door_left_objects(), C.GLB_DOOR_L, "HandleGrip.L")
    export_part("DoorRight", C.door_right_objects(), C.GLB_DOOR_R, "HandleGrip.R")
    for part, (root, path) in C.PROPS.items():
        export_part(root, part_objects(part), path, "HandleGrip.D" if part == "drawer" else None)


if __name__ == "__main__":
    main()
