"""Stage 2: UV unwrap, bake PBR atlases (albedo, normal, ORM) per exported part, save.

  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/bake.py

Parts: body (carcass, top, basin, plumbing; 2048, hidden faces get less texture
space), fixture (mixer, spout, drain; baked with the body visible for contact
AO), the two drawers, the lever and the soap dispenser (each alone: they move).
The LED strip keeps its unbaked emissive material.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from vanity_common import (  # noqa: E402
    BACK_Y0, BASIN_C, BLEND, BODY_MAT, BOTTOM_Z1, CASE_FRONT, CASE_Z0, DISPENSER_MAT, DRAWER_BOTTOM_MAT,
    DRAWER_TOP_MAT, FIXTURE_MAT, LEVER_MAT, TEX_BODY, TEX_DISPENSER, TEX_DRAWER, TEX_FIXTURE, TEX_LEVER, TOP_Z0,
    X_IN, body_objects, collision_objects, dispenser_objects, drawer_bottom_objects, drawer_collision,
    drawer_top_objects, fixture_objects, lever_objects,
)
from arcology_blender import bake  # noqa: E402
from arcology_blender.scene import meshes, save_blend  # noqa: E402


def body_weight(ob, c, n):
    """Texel density per island: faces against the wall or under the marble get
    almost none, the carcass interior little, the marble top and bowl the most."""
    if n.y > 0.9 and c.y > -0.003:
        return 0.05                                   # against the wall
    if n.z < -0.9 and abs(c.z - TOP_Z0) < 0.003:
        return 0.2                                    # marble underside
    if c.z > TOP_Z0 + 0.001:
        return 1.3 if n.z > 0.9 else 1.0              # marble top, edges, upstand
    in_bowl = abs(c.x - BASIN_C.x) < 0.30 and abs(c.y - BASIN_C.y) < 0.20 and 0.69 < c.z <= TOP_Z0 + 0.001
    if in_bowl:
        to_axis = (BASIN_C.x - c.x) * n.x + (BASIN_C.y - c.y) * n.y
        return 1.0 if (to_axis > 0.0 or n.z > 0.3) else 0.25  # inside of the bowl / its outside
    if n.z < -0.9 and c.z < CASE_Z0 + 0.002:
        return 0.5                                    # underside (seen from low, lit by the LED)
    if abs(c.x) < X_IN and CASE_FRONT < c.y < BACK_Y0 and BOTTOM_Z1 - 0.001 < c.z < TOP_Z0:
        return 0.35                                   # carcass interior, plumbing, runners
    return 1.0


def main():
    bake.setup(bpy.context.scene, ao_distance=0.15)
    for ob in collision_objects() + drawer_collision("top") + drawer_collision("bottom"):
        ob.hide_render = True
    body, fixture = body_objects(), fixture_objects()
    top, bottom = meshes(drawer_top_objects()), meshes(drawer_bottom_objects())
    lever, disp = meshes(lever_objects()), meshes(dispenser_objects())
    movers = top + bottom + lever + disp
    bake.bake_part(body, "vanity_body", BODY_MAT, hide=movers, size=TEX_BODY, weight=body_weight)
    bake.bake_part(fixture, "vanity_fixture", FIXTURE_MAT, hide=movers, size=TEX_FIXTURE)
    bake.bake_part(top, "vanity_drawer_top", DRAWER_TOP_MAT, hide=body + fixture + bottom + lever + disp,
                   size=TEX_DRAWER)
    bake.bake_part(bottom, "vanity_drawer_bottom", DRAWER_BOTTOM_MAT, hide=body + fixture + top + lever + disp,
                   size=TEX_DRAWER)
    bake.bake_part(lever, "vanity_lever", LEVER_MAT, hide=body + fixture + top + bottom + disp, size=TEX_LEVER)
    bake.bake_part(disp, "vanity_soap_dispenser", DISPENSER_MAT, hide=body + fixture + top + bottom + lever,
                   size=TEX_DISPENSER)
    bake.remove_source_materials()
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
