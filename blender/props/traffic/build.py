"""Stage 1: build the five vehicles and their src_ materials, save the .blend.

  blender -b --factory-startup --python blender/props/traffic/build.py

Each vehicle is one mesh object tagged with its name, recentered so its
bounds center is the origin (custom props: `author_offset`, the shift the
materials add back; `headlights_center` / `taillights_center`, local points
between each lamp pair).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathutils import Vector  # noqa: E402

from traffic_common import BLEND, TRI_BUDGET, TRI_DEFAULT, VEHICLES  # noqa: E402
from arcology_blender.geo import shade  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag, tri_count  # noqa: E402
from traffic_materials import build_materials  # noqa: E402
from traffic_textures import build_all  # noqa: E402
from traffic_vehicles import build_vehicle  # noqa: E402


def main():
    clear_scene()
    decals = build_all()
    coll = get_collection("Traffic")
    for vehicle in VEHICLES:
        pm, ref, spec = build_vehicle(vehicle)
        pts = [v.co for v in pm.bm.verts]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        center = (lo + hi) / 2
        center.x = 0.0  # symmetric by construction; keep the mirror plane exact
        for v in pm.bm.verts:
            v.co -= center
        mats = build_materials(vehicle, tuple(center), spec, decals)
        ob = pm.to_object(vehicle, coll, mats)
        shade(ob, sharp_angle=42.0)
        tag(ob, vehicle)
        ob["author_offset"] = tuple(center)
        ob["headlights_center"] = tuple(ref["headlights"] - center)
        ob["taillights_center"] = tuple(ref["taillights"] - center)
        budget = TRI_BUDGET.get(vehicle, TRI_DEFAULT)
        tris = tri_count(ob)
        print(f"TRIS {vehicle}={tris} (budget {budget}) size={tuple(round(c, 3) for c in hi - lo)} "
              f"slots={[m.name for m in ob.data.materials]}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
