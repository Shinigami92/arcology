"""Stage 3: export the body (render meshes, fixtures, LED strip, collision), both drawers
(origin on the slide axis at the closed position, HandleGrip), the mixer lever (origin on
its pivot, HandleGrip) and the soap dispenser (origin at its bottom center) into
assets/props/vanity/.

  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/export.py

The grips are named HandleGripDrawerTop / HandleGripDrawerBottom / HandleGripLever in
the .blend (names are unique) and exported as `HandleGrip` in their own glb.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from vanity_common import (  # noqa: E402
    GLB_BODY, GLB_DISPENSER, GLB_DRAWER_BOTTOM, GLB_DRAWER_TOP, GLB_LEVER, body_objects, collision_objects,
    dispenser_objects, drawer_bottom_objects, drawer_top_objects, fixture_objects, lever_objects,
)
from lib_candidates import renamed  # noqa: E402
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402


def export_part(root, objs, path):
    grips = {ob: "HandleGrip" for ob in objs if ob.type == "EMPTY" and ob.name.startswith("HandleGrip")}
    with renamed(grips):
        export_glb_at_origin(bpy.data.objects[root], objs, path)


def main():
    export_glb(body_objects() + fixture_objects() + collision_objects(), GLB_BODY)
    export_part("DrawerTop", drawer_top_objects(), GLB_DRAWER_TOP)
    export_part("DrawerBottom", drawer_bottom_objects(), GLB_DRAWER_BOTTOM)
    export_part("Lever", lever_objects(), GLB_LEVER)
    export_part("SoapDispenser", dispenser_objects(), GLB_DISPENSER)


if __name__ == "__main__":
    main()
