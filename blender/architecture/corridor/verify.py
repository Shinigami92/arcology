"""Stage 5: contract checks per asset (tools/blockout/corridor_kit.json), then re-import the glb.

  blender -b --factory-startup --python blender/architecture/corridor/verify.py [-- --asset a,b]

corridor_trim: one mesh at the world origin, materials `corridor_trim` + `corridor_led`; every
vertex inside a run's slab (wall line .. 35 mm, floor .. 1.05 m); rays from the corridor hit the
skirting, panel and cap faces at their depths along every run (grooves aside); the LED faces look
out and down; triangle budget; texture sizes.
Fixtures: bounds inside the contract box around the origin (the side that mounts is flush with
the origin plane), the contract's material slot present, at most one material plus one emissive,
triangle budget, texture sizes. The last line per asset is CONTRACT <asset> OK / FAIL.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from corridor_common import (  # noqa: E402
    blend_path, body_objects, contract, glb_path, kit, load_runs, selected_assets, to_blender,
)
import wainscot  # noqa: E402
from arcology_blender.checks import fmt, import_report, world_bounds  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

UP = Vector((0, 0, 1))


class Report:
    def __init__(self, asset):
        self.asset, self.fails = asset, []

    def check(self, name, ok, detail=""):
        print(f"CHECK {self.asset} {name}: {'OK' if ok else 'FAIL'} {detail}")
        if not ok:
            self.fails.append(name)


def images_of(objs):
    return sorted({(n.image.name, tuple(n.image.size)) for o in objs for m in o.data.materials if m
                   for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})


# --- trim -------------------------------------------------------------------------------------------
def segments(data):
    out = []
    for ri, run in enumerate(data["runs"]):
        pts = [to_blender(p) for p in run["points"]]
        m = wainscot.segment_count(run)
        for si in range(m):
            a, b = pts[si], pts[(si + 1) % len(pts)]
            n = Vector((run["normals"][si][0], -run["normals"][si][1], 0.0))
            k0 = "end" if not run["closed"] and si == 0 else "corner"
            k1 = "end" if not run["closed"] and si == m - 1 else "corner"
            out.append((ri, si, a, b, (b - a).normalized(), n, (b - a).length, k0, k1))
    return out


def in_slab(p, segs, depth, height, tol=1e-5):
    for (_, _, a, _, d, n, length, k0, k1) in segs:
        t, s = (p - a).dot(d), (p - a).dot(n)
        lo = -tol - (depth if k0 == "corner" else 0.0)
        hi = length + tol + (depth if k1 == "corner" else 0.0)
        if lo <= t <= hi and -tol <= s <= depth + tol and -tol <= p.z <= height + tol:
            return True
    return False


def verify_trim(r):
    c = contract("corridor_trim")
    data = load_runs()
    segs = segments(data)
    obs = body_objects()
    r.check("one mesh", len(obs) == 1, f"{[o.name for o in obs]}")
    ob = obs[0]
    r.check("identity transform", ob.matrix_world == ob.matrix_world.Identity(4))
    mats = sorted(m.name for m in ob.data.materials)
    r.check("materials", mats == sorted([wainscot.MAT, c["led_material"]]), f"{mats}")
    verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    zs = [v.z for v in verts]
    r.check("floor to rail top", abs(min(zs)) < 1e-6 and abs(max(zs) - c["height"]) < 1e-6,
            f"z {min(zs):.4f}..{max(zs):.4f} (contract 0..{c['height']})")
    outside = [v for v in verts if not in_slab(v, segs, c["depth"], c["height"])]
    r.check("nothing off the runs", not outside, f"{len(outside)} of {len(verts)} vertices outside every run slab "
            f"(depth {c['depth']} m)")

    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    expect = {"skirting": (0.05, wainscot.SKIRT_D), "panel": (0.55, wainscot.PANEL_D),
              "cap": (1.025, wainscot.CAP_D)}
    stats = {k: [0, 0, 0] for k in expect}   # rays, misses, wrong depth
    total = 0.0
    for (ri, si, a, b, d, n, length, k0, k1) in segs:
        total += length
        t0 = 0.003 if k0 == "end" else c["depth"] + 0.004
        t1 = length - (0.003 if k1 == "end" else c["depth"] + 0.004)
        steps = max(1, int((t1 - t0) / 0.02))
        for j in range(steps + 1):
            t = t0 + (t1 - t0) * j / steps
            for key, (h, depth) in expect.items():
                st = stats[key]
                st[0] += 1
                hit = bvh.ray_cast(a + d * t + n * 0.1 + UP * h, -n, 0.2)
                if hit[0] is None:
                    st[1] += 1
                elif abs((0.1 - hit[3]) - depth) > 2e-4:
                    in_groove = key == "panel" and depth - wainscot.GROOVE_D - 1e-4 <= 0.1 - hit[3] < depth
                    st[2] += 0 if in_groove else 1
    for key, (rays, miss, wrong) in stats.items():
        r.check(f"{key} face along every run", miss == 0 and wrong == 0,
                f"{rays} rays at {expect[key][0]} m, {miss} misses, {wrong} at the wrong depth")
    led = [p for p in ob.data.polygons if ob.data.materials[p.material_index].name == c["led_material"]]
    bad = 0
    for p in led:
        cpos = ob.matrix_world @ p.center
        nn = (ob.matrix_world.to_3x3() @ p.normal).normalized()
        side = [s for s in segs if in_slab(cpos, [s], c["depth"], c["height"], 1e-4)]
        if not side or nn.z >= 0 or nn.dot(side[0][5]) <= 0.5:
            bad += 1
    r.check("LED faces look out and down", led and bad == 0, f"{len(led)} faces, {bad} wrong")
    tris = tri_count(ob)
    r.check("triangle budget", tris <= kit()["budgets"]["trim_tris"], f"{tris} tris")
    imgs = images_of(obs)
    r.check("texture sizes", all(max(s) <= 2048 for _, s in imgs), f"{imgs}")
    print(f"  {len(data['runs'])} runs, {len(segs)} segments, {total:.2f} m")


# --- fixtures --------------------------------------------------------------------------------------
def contract_box(asset):
    """(lo, hi) in Blender coordinates around the contract origin."""
    sx, sy, sz = contract(asset)["size"]          # Godot x, y, z
    if asset == "exit_sign":                       # back on the wall plane, face toward Godot +Z (Blender -Y)
        return Vector((-sx / 2, -sz, -sy / 2)), Vector((sx / 2, 0.0, sy / 2))
    return Vector((-sx / 2, -sz / 2, -sy)), Vector((sx / 2, sz / 2, 0.0))   # hangs from the ceiling


def verify_fixture(r, asset):
    import fixtures
    c = contract(asset)
    obs = body_objects()
    lo, hi = world_bounds(obs)
    blo, bhi = contract_box(asset)
    tol = 1e-4
    inside = all(blo[i] - tol <= lo[i] and hi[i] <= bhi[i] + tol for i in range(3))
    r.check("bounds inside the contract", inside, f"lo={fmt(lo)} hi={fmt(hi)} contract lo={fmt(blo)} hi={fmt(bhi)}")
    mount = (hi.y if asset == "exit_sign" else hi.z)
    r.check("mounted flush on the origin plane", abs(mount) < 1e-4, f"{mount:.5f}")
    mats = sorted({m.name for o in obs for m in o.data.materials if m})
    need = fixtures.BAKE[asset]["required"]
    r.check("material slots", need in mats and len(mats) <= 2, f"{mats} (needs {need})")
    tris = sum(tri_count(o) for o in obs)
    r.check("triangle budget", tris <= kit()["budgets"]["small_part_tris"], f"{tris} tris")
    imgs = images_of(obs)
    r.check("texture sizes", all(max(s) <= 1024 for _, s in imgs), f"{imgs}")
    r.check("one mesh", len(obs) == 1, f"{[o.name for o in obs]}")
    print(f"  contract size (Godot) {c['size']}, measured {fmt(hi - lo)} (Blender x, y, z)")


def main():
    failed = []
    for asset in selected_assets():
        if not os.path.exists(blend_path(asset)):
            print(f"SKIP {asset}: no {blend_path(asset)}")
            continue
        bpy.ops.wm.open_mainfile(filepath=blend_path(asset))
        r = Report(asset)
        if asset == "corridor_trim":
            verify_trim(r)
        else:
            verify_fixture(r, asset)
        print(f"CONTRACT {asset}", "OK" if not r.fails else f"FAIL {r.fails}")
        failed += r.fails
        if os.path.exists(glb_path(asset)):
            import_report(glb_path(asset))
    print("VERIFY", "OK" if not failed else "FAIL")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
