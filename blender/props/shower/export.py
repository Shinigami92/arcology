"""Stage 3: export the body (static fixtures + glass pane + collision) and the three moving
parts (origins on their pivots / the holder seat, each with a HandleGrip empty).

  blender -b --factory-startup blender/props/shower.blend --python blender/props/shower/export.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import shower_common as C  # noqa: E402
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def export_part(root, objs, path):
    """Moving part at its pivot; its grip empty (FlowGrip, TempGrip, HandGrip in the .blend,
    unique names) is exported as `HandleGrip`, the name the Godot side looks for."""
    grips = [(o, o.name) for o in objs if o.type == "EMPTY"]
    for o, _ in grips:
        o.name = "HandleGrip"
    export_glb_at_origin(bpy.data.objects[root], objs, path)
    for o, name in grips:
        o.name = name


def main():
    export_glb(C.body_objects() + C.glass_objects() + C.collision_objects(), C.GLB_BODY)
    export_part("MixerFlow", C.flow_objects(), C.GLB_FLOW)
    export_part("MixerTemp", C.temp_objects(), C.GLB_TEMP)
    export_part("Handheld", C.handheld_objects(), C.GLB_HANDHELD)


if __name__ == "__main__":
    main()
