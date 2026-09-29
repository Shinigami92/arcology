"""Stage 5: drawer travel clearance in the source (closed to 0.28 m out), then re-import the glb files.

  blender -b --factory-startup --python blender/props/nightstand__fable-high/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import (  # noqa: E402
    BLEND, DRAWER_TRAVEL, GLB_BODY, GLB_DRAWER, GLB_LAMP, body_objects, drawer_objects, lamp_objects,
)
from arcology_blender.checks import import_report, slide_clearance  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    drawer = bpy.data.objects["Drawer"]
    fixed = body_objects() + [o for o in lamp_objects() if o.type == "MESH"]
    print("DRAWER TRAVEL (drawer vs body + lamp)")
    slide = slide_clearance(drawer, drawer_objects(), fixed, (0, -1, 0), DRAWER_TRAVEL, steps=14)
    print("CLEARANCE", "OK" if not slide else f"FAIL slide={slide}")
    for path in (GLB_BODY, GLB_DRAWER, GLB_LAMP):
        import_report(path)


if __name__ == "__main__":
    main()
