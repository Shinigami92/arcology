"""Stage 5: contract checks in the source, then re-import every glb.

  blender -b --factory-startup --python blender/architecture/city/brutalist/verify.py

Per tower: origin at the base center (the street footprint matches the JSON),
the roof slab's top face at top_y + 180, triangles <= 40 k, only the four
shared material names, a `<name>_blink` object where lights should blink, and
the window UVs on whole cells (panes stay on the geometry's bays). Then the
glb re-import (objects, origins, triangles, materials, embedded images).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from brutalist_common import BLEND, CELLS, MATERIALS, MAT_WINDOWS, glb_path, tower_objects, towers  # noqa: E402
from arcology_blender.checks import fmt, import_report, world_bounds  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

TRI_BUDGET = 40000


def roof_top_ok(ob, height, tol=1e-3):
    """An upward face whose vertices all lie at the roof slab height."""
    me = ob.data
    for p in me.polygons:
        if p.normal.z > 0.99 and all(abs(me.vertices[i].co.z - height) < tol for i in p.vertices):
            return True
    return False


def footprint(ob, z_max=1.0):
    pts = [v.co for v in ob.data.vertices if v.co.z < z_max]
    return (min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts), max(p.y for p in pts),
            min(p.z for p in pts))


def window_uv_report(ob):
    """Window faces: U and V offsets on whole cells (fractional part 0 at the bottom-left corner)."""
    me = ob.data
    slot = [i for i, m in enumerate(me.materials) if m and m.name == MAT_WINDOWS]
    if not slot:
        return 0, 0
    uv = me.uv_layers.active.data
    bad = n = 0
    for p in me.polygons:
        if p.material_index != slot[0]:
            continue
        n += 1
        us = [uv[li].uv.x * CELLS for li in p.loop_indices]
        if abs(min(us) - round(min(us))) > 1e-3:
            bad += 1
    return n, bad


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    ok_all = True
    total = 0
    for t in towers():
        name, W, D, H = t["name"], t["W"], t["D"], t["height"]
        objs = tower_objects(name)
        main_ob = [o for o in objs if o.name == name]
        blink = [o for o in objs if o.name == f"{name}_blink"]
        ok = bool(main_ob)
        ob = main_ob[0]
        tris = sum(tri_count(o) for o in objs)
        total += tris
        mats = sorted({m.name for o in objs for m in o.data.materials if m})
        x0, x1, y0, y1, zmin = footprint(ob)
        fp_ok = abs(x0 + W / 2) < 0.2 and abs(x1 - W / 2) < 0.2 and abs(y0 + D / 2) < 0.2 and abs(y1 - D / 2) < 0.2 \
            and abs(zmin) < 1e-4
        roof_ok = roof_top_ok(ob, H)
        lo, hi = world_bounds(objs)
        transforms_ok = all(o.location.length < 1e-6 and o.rotation_euler.to_quaternion().angle < 1e-6 and
                            all(abs(s - 1) < 1e-6 for s in o.scale) for o in objs)
        n_win, bad = window_uv_report(ob)
        checks = dict(footprint=fp_ok, roof=roof_ok, tris=tris <= TRI_BUDGET, materials=set(mats) <= set(MATERIALS),
                      transforms=transforms_ok, window_uv=bad == 0)
        ok = ok and all(checks.values())
        ok_all = ok_all and ok
        print(f"TOWER {name}: tris={tris} (main {tri_count(ob)}, blink {sum(tri_count(o) for o in blink)}) "
              f"materials={mats}")
        print(f"  street footprint x {x0:.2f}..{x1:.2f} y {y0:.2f}..{y1:.2f} (JSON {W} x {D}), base z={zmin:.3f}")
        print(f"  roof slab at {H:.2f} m (top_y {t['top_y']}): {'found' if roof_ok else 'MISSING'}; "
              f"bounds lo={fmt(lo, 2)} hi={fmt(hi, 2)}")
        print(f"  blink object: {blink[0].name if blink else '-'}; window faces {n_win}, off-cell {bad}")
        print(f"  CHECKS {' '.join(f'{k}={'OK' if v else 'FAIL'}' for k, v in checks.items())}")
    print(f"TOTAL tris={total}")
    from brutalist_textures import window_plan
    plan = window_plan()
    cells = [c for row in plan for c in row]
    lit = [c for c in cells if c["lit"]]
    print(f"WINDOWS lit {len(lit) / len(cells):.1%} of cells, cold {sum(c['cold'] for c in lit) / len(lit):.1%} of lit, "
          f"dim (deep inside light) {sum(c['dim'] for c in cells) / len(cells):.1%}")
    print("CONTRACT", "OK" if ok_all else "FAIL")
    for t in towers():
        import_report(glb_path(t["name"]))


if __name__ == "__main__":
    main()
