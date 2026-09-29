"""Stage 5: contract checks in the source (bounds, collision sizes for Godot), then re-import the glb.

  blender -b --factory-startup --python blender/props/<name>/verify.py

Moving parts: add checks.hinge_clearance / checks.slide_clearance (see the
fridge, wardrobe and nightstand verify.py).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from template_common import BLEND, GLB, LIMIT_HI, LIMIT_LO, body_objects, collision_objects  # noqa: E402
from arcology_blender.checks import collision_report, fmt, import_report, inside, world_bounds  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    lo, hi = world_bounds(body_objects())
    ok = inside(lo, hi, LIMIT_LO, LIMIT_HI)
    print(f"BOUNDS lo={fmt(lo)} hi={fmt(hi)} size={fmt(hi - lo)} {'OK' if ok else 'OUT OF CONTRACT'}")
    collision_report(collision_objects())
    print(f"TRIS body={sum(tri_count(o) for o in body_objects())}")
    print("CONTRACT", "OK" if ok else "FAIL")
    import_report(GLB)


if __name__ == "__main__":
    main()
