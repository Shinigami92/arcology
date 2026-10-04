"""Stage 5: contract checks in the source, then re-import every glb.

  blender -b --factory-startup --python blender/architecture/city/spire/verify.py

Per tower: triangles (<= 40 k, <= 160 k for the five), materials (only the four
city_spire_* names, <= 4 in total), base on the street (min z = 0), roof height
(top_y + 180) reached by the body, footprint (body bounds at the base vs the JSON;
ads, the landing pad and crowns may reach beyond, reported), object names
(<tower>, <tower>_ad<n>, <tower>_blink), the blink lights' size (>= 1 m).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from spire_common import (  # noqa: E402
    BLEND, MATERIALS, ad_part, blink_part, body_part, glb_path, load_spec, roof_height, towers,
)
from arcology_blender.checks import fmt, import_report, world_bounds  # noqa: E402
from arcology_blender.scene import part_objects, tri_count  # noqa: E402

TRI_LIMIT, TRI_TOTAL = 40000, 160000


def base_extent(ob, z_max=1.0):
    xs = [v.co.x for v in ob.data.vertices if v.co.z <= z_max]
    ys = [v.co.y for v in ob.data.vertices if v.co.z <= z_max]
    return (min(xs), max(xs)), (min(ys), max(ys))


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    spec = load_spec()
    ok = True
    total = 0
    used = set()
    for t in towers(spec):
        name = t["name"]
        body = part_objects(body_part(name), mesh_only=True)
        ads = part_objects(ad_part(name), mesh_only=True)
        blink = part_objects(blink_part(name), mesh_only=True)
        objs = body + ads + blink
        tris = sum(tri_count(o) for o in objs)
        total += tris
        mats = sorted({m.name for o in objs for m in o.data.materials})
        used.update(mats)
        lo, hi = world_bounds(objs)
        blo, bhi = world_bounds(body)
        H = roof_height(t, spec)
        (x0, x1), (y0, y1) = base_extent(body[0])
        W, D = t["footprint"]
        names_ok = (len(body) == 1 and body[0].name == name and len(blink) == 1 and blink[0].name == f"{name}_blink"
                    and all(re.fullmatch(rf"{name}_ad\d+", o.name) for o in ads))
        blink_ok = all(min(o.dimensions) >= 1.0 for o in blink)
        checks = {
            "tris": tris <= TRI_LIMIT,
            "materials": set(mats) <= set(MATERIALS),
            "base_z0": abs(lo.z) < 1e-3,
            "roof": bhi.z >= H - 1e-3,
            "footprint": x0 >= -W / 2 - 1e-3 and x1 <= W / 2 + 1e-3 and y0 >= -D / 2 - 1e-3 and y1 <= D / 2 + 1e-3,
            "names": names_ok,
            "blink_size": blink_ok,
            "transforms": all(o.matrix_world.is_identity for o in objs),
        }
        ok &= all(checks.values())
        print(f"TOWER {name}: tris={tris} (body {sum(tri_count(o) for o in body)}, ads {sum(tri_count(o) for o in ads)}, "
              f"blink {sum(tri_count(o) for o in blink)}) mats={mats}")
        print(f"  roof H={H:.1f} body top={bhi.z:.1f} overall top={hi.z:.1f}; base x {x0:.1f}..{x1:.1f} y {y0:.1f}..{y1:.1f} "
              f"(footprint {W} x {D}); all bounds lo={fmt(lo, 1)} hi={fmt(hi, 1)}")
        print(f"  ads={[o.name for o in ads]} blink={[o.name for o in blink]} ({len(blink[0].data.polygons) // 6} lights)")
        print("  " + " ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in checks.items()))
    ok &= total <= TRI_TOTAL and len(used) <= 4
    print(f"TOTAL tris={total} (<= {TRI_TOTAL}) materials={sorted(used)}")
    print("CONTRACT", "OK" if ok else "FAIL")
    for t in towers(spec):
        import_report(glb_path(t["name"]))


if __name__ == "__main__":
    main()
