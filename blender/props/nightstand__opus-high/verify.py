"""Stage 5: drawer travel clearance in the source, then re-import the glb files.

  blender -b --factory-startup --python blender/props/nightstand__opus-high/verify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from nightstand_common import (  # noqa: E402
    BLEND, DRAWER_TRAVEL, GLB_BODY, GLB_DRAWER, GLB_LAMP, body_objects, drawer_objects, lamp_light_objects,
    lamp_objects,
)
from arcology_blender.checks import import_report, slide_clearance  # noqa: E402


def bounds(objs):
    import mathutils
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    drawer = bpy.data.objects["Drawer"]
    fixed = body_objects() + lamp_objects() + lamp_light_objects()
    print("DRAWER TRAVEL (drawer vs body and lamp)")
    slide = slide_clearance(drawer, [drawer], fixed, (0, -1, 0), DRAWER_TRAVEL, steps=14)
    print("CLEARANCE", "OK" if not slide else f"FAIL slide={slide}")
    for name, objs in (("body", body_objects()), ("drawer", [drawer]),
                       ("lamp", lamp_objects() + lamp_light_objects())):
        lo, hi = bounds(objs)
        print(f"BOUNDS {name} lo=({lo[0]:.4f},{lo[1]:.4f},{lo[2]:.4f}) hi=({hi[0]:.4f},{hi[1]:.4f},{hi[2]:.4f})")
    grip = bpy.data.objects["HandleGrip"]
    print(f"HANDLEGRIP local={tuple(round(v, 4) for v in grip.location)} "
          f"world={tuple(round(v, 4) for v in grip.matrix_world.translation)}")
    import_report(GLB_BODY)
    import_report(GLB_DRAWER)
    import_report(GLB_LAMP)


if __name__ == "__main__":
    main()
