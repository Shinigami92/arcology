"""Stage 2: unwrap all five vehicles into one atlas and bake albedo, normal,
ORM and emission into the shared `traffic_vehicle` material, save.

  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/bake.py

The vehicles are spread apart along X while baking (their AO must not see
each other; LocalGraph masks don't move with them). Texel density: lamps,
signs and the light bar get more, undersides less.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils.kdtree import KDTree  # noqa: E402

from traffic_common import (  # noqa: E402
    BLEND, EMISSION, HOT_ATTR, MATERIAL, PREFIX, SPREAD, TEX_SIZE, VEHICLES, vehicle_objects,
)
from arcology_blender import bake, geo  # noqa: E402
from arcology_blender.scene import save_blend  # noqa: E402

DENSE = {"headlight": 2.0, "taillight": 2.0, "bar_red": 2.0, "bar_blue": 2.0, "marker": 1.5, "sign": 2.6}


def face_weight(slot, normal_z):
    if slot in DENSE:
        return DENSE[slot]
    if normal_z < -0.6:
        return 0.45  # undersides: seen from below only, mostly dark
    return 1.0


def slot_name(mat_name):
    """src_<vehicle>_<slot> -> slot (vehicle names contain underscores)."""
    for v in VEHICLES:
        pre = f"src_{v}_"
        if mat_name.startswith(pre):
            return mat_name[len(pre):]
    return mat_name


def main():
    scene = bpy.context.scene
    bake.setup(scene)
    objs = vehicle_objects()
    trees = {}
    for ob in objs:
        me = ob.data
        kd = KDTree(len(me.polygons))
        vals = []
        for i, p in enumerate(me.polygons):
            kd.insert(p.center, i)
            vals.append(face_weight(slot_name(me.materials[p.material_index].name), p.normal.z))
        kd.balance()
        trees[ob.name] = (kd, vals)

    def weight(ob, center, normal):
        kd, vals = trees[ob.name]
        _, i, _ = kd.find(ob.matrix_world.inverted() @ center)
        return vals[i]

    with bake.Spread([(ob, i * SPREAD) for i, ob in enumerate(objs)], axis=0):
        bake.bake_part(objs, PREFIX, MATERIAL, size=TEX_SIZE, weight=weight, emission=EMISSION)
    bake.remove_source_materials()
    for img in list(bpy.data.images):
        if img.name.startswith("decal_"):
            bpy.data.images.remove(img)
    for ob in objs:
        geo.remove_attribute(ob, HOT_ATTR)
        if any(ob.location):
            raise RuntimeError(f"{ob.name} not back at the origin: {tuple(ob.location)}")
    bake.report_images()
    save_blend(BLEND)


if __name__ == "__main__":
    main()
