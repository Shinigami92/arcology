"""Stage 5: check every window against its spec and fail loudly on drift, then
re-import the glbs.

  blender -b --factory-startup --python blender/architecture/windows/verify.py [-- --spec F]

Checks (Godot axes, window-local): nothing intrudes into the wall volume
beyond the opening (and the stone cut); frame faces and mullions sit exactly
on the bay edges (ray probes from each bay's center at several depths); the
frame spans frame_z; the glass plane is free up to each bay's glass rectangle
and nothing comes within the gasket gap of it; the sash's hinge axis, rails
(sash_face inset, sash_z depth), HandleGrip height and swing clearance up to
open_max_deg; the stone slab and the shade bars against the Godot generator's
constants (tools/props/window.py); triangle, material and texture budgets.
Prints the numbers the Godot side needs (REPORT lines). Exit code 1 on failure.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from windows_common import (  # noqa: E402
    DESIGN, GLB_BUTTON, GLB_PANEL, GODOT, MAT_LED, MAT_PANEL_LED, bar_objects, blend_path, button_objects,
    frame_objects, glb_bar, glb_frame, glb_sash, godot_constants, load_spec, panel_objects, sash_objects, windows,
)
from arcology_blender.checks import hinge_clearance, import_report  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402

TOL = 2e-4       # 0.2 mm
FAILS = []
BUDGET = dict(frame=30000, sash=8000, kit=3000, bar=5000)


def check(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        FAILS.append(what)
    return ok


def g(v):
    """Blender world -> Godot."""
    return Vector((v[0], v[2], -v[1]))


def tree(objs):
    verts, tris = [], []
    for ob in objs:
        if ob.type != "MESH":
            continue
        me = ob.data
        me.calc_loop_triangles()
        off = len(verts)
        mw = ob.matrix_world
        verts += [g(mw @ v.co) for v in me.vertices]
        tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris), verts


def hit(bvh, origin, direction, dist=10.0):
    loc, _, _, d = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
    return d


def fmt(*v):
    return "(" + ", ".join(f"{x:.4f}" for x in v) + ")"


def check_window(w):
    print(f"WINDOW {w.name}: {w.W} x {w.T - w.B} m, {w.n} bay(s), clear {w.cw:.4f} x {w.ch:.4f} m")
    frame = frame_objects(w.name)
    bvh, verts = tree(frame)
    eps = 1e-4
    stone = w.sill == "stone"
    cut_b = w.B - (GODOT["sill_t"] if stone else 0.0)
    # 1. nothing inside the wall volume outside the opening (z strictly inside the wall)
    bad = [p for p in verts if w.ze + eps < p.z < w.zi - eps
           and (abs(p.x) > w.W / 2 + eps or p.y > w.T + eps or p.y < cut_b - (0.0 if stone else DESIGN["threshold_below"]) - eps)]
    check(not bad, f"no geometry inside the wall beyond the opening ({len(bad)} vertices)")
    # 2. frame faces and mullions on the bay edges, frame depth
    for i in range(w.n):
        x0, x1 = w.bay_x(i)
        cx, cy = (x0 + x1) / 2, (w.y0 + w.y1) / 2
        levels = [w.z1 - 0.004, -0.035] + ([] if i == w.vent_bay else [w.z0 + 0.004])
        for z in levels:
            dx0 = hit(bvh, (cx, cy, z), (-1, 0, 0))
            dx1 = hit(bvh, (cx, cy, z), (1, 0, 0))
            dy0 = hit(bvh, (cx, cy, z), (0, -1, 0))
            dy1 = hit(bvh, (cx, cy, z), (0, 1, 0))
            ok = all(d is not None for d in (dx0, dx1, dy0, dy1)) and abs(dx0 - w.cw / 2) < TOL and \
                abs(dx1 - w.cw / 2) < TOL and abs(dy0 - w.ch / 2) < TOL and abs(dy1 - w.ch / 2) < TOL
            check(ok, f"bay {i} edges at z={z:+.3f}: x {cx - (dx0 or 0):.4f}..{cx + (dx1 or 0):.4f} "
                      f"y {cy - (dy0 or 0):.4f}..{cy + (dy1 or 0):.4f} (want {x0:.4f}..{x1:.4f}, {w.y0:.4f}..{w.y1:.4f})")
        if i == w.vent_bay:
            d = hit(bvh, (cx, cy, w.z0 + 0.004), (1, 0, 0))
            check(d is not None and abs(d - (w.cw / 2 - DESIGN["stop_inset"])) < TOL,
                  f"vent bay {i}: sash stop {DESIGN['stop_inset'] * 1000:.0f} mm behind the sash")
    for k in range(w.n - 1):
        xm = w.mullion_x(k)
        zin = hit(bvh, (xm, w.T / 2 + w.B / 2, 1.0), (0, 0, -1))
        zout = hit(bvh, (xm, w.T / 2 + w.B / 2, -1.0), (0, 0, 1))
        check(zin is not None and zout is not None and abs(1.0 - zin - w.z1) < TOL and abs(-1.0 + zout - w.z0) < TOL,
              f"mullion {k} at x={xm:.4f}, faces z {(-1 + zout) if zout else 0:.4f}..{(1 - zin) if zin else 0:.4f}")
    i_probe = (DESIGN["liner"] + w.ff) / 2
    for name, p in (("west jamb", (-w.W / 2 + i_probe, (w.B + w.T) / 2)), ("east jamb", (w.W / 2 - i_probe, (w.B + w.T) / 2)),
                    ("head", (0.3, w.T - (w.ff + DESIGN["head"]) / 2))):
        zin = hit(bvh, (p[0], p[1], 1.0), (0, 0, -1))
        zout = hit(bvh, (p[0], p[1], -1.0), (0, 0, 1))
        check(zin is not None and abs(1.0 - zin - w.z1) < TOL, f"{name} interior face at frame_z[1]={w.z1}")
        check(zout is not None and abs(-1.0 + zout - w.z0) < TOL, f"{name} exterior face at frame_z[0]={w.z0}")
    # 3. glass planes: free up to the glass rectangle, nothing within the gasket gap
    gap = DESIGN["gasket_gap"]
    for i in range(w.n):
        x0, x1, y0, y1 = w.glass_rect(i)
        objs = frame if i != w.vent_bay else [o for o in sash_objects(w.name) if o.type == "MESH"]
        b2, _ = tree(objs) if i == w.vent_bay else (bvh, None)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ds = [hit(b2, (cx, cy, w.gz), d) for d in ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0))]
        want = [(x1 - x0) / 2] * 2 + [(y1 - y0) / 2] * 2
        ok = all(d is not None and abs(d - wv) < TOL for d, wv in zip(ds, want))
        # under the gasket lips (1 mm inside the edge): the lips keep the gasket gap to the glass plane
        near = []
        e = 0.001
        for t in range(1, 40):
            s = t / 40
            for p in ((x0 + e, y0 + s * (y1 - y0)), (x1 - e, y0 + s * (y1 - y0)),
                      (x0 + s * (x1 - x0), y0 + e), (x0 + s * (x1 - x0), y1 - e)):
                for dz in (1, -1):
                    d = hit(b2, (p[0], p[1], w.gz), (0, 0, dz), 0.05)
                    near.append(d if d is not None else 1.0)
        check(ok and min(near) > gap - 1e-4,
              f"bay {i} glass plane clear to {fmt(x0, x1, y0, y1)} at z={w.gz} (gaskets {min(near) * 1000:.2f} mm off it)")
    # 4. sash
    if w.vent:
        sash = [o for o in sash_objects(w.name) if o.type == "MESH"][0]
        grip = [o for o in sash_objects(w.name) if o.name.startswith("HandleGrip")][0]
        o = g(sash.matrix_world.translation)
        check((o - Vector(w.hinge)).length < 1e-5, f"hinge axis at {fmt(*o)} (want {fmt(*w.hinge)})")
        pts = [g(sash.matrix_world @ v.co) for v in sash.data.vertices]
        rails = [p for p in pts if p.z <= w.sz1 + eps]
        x0, x1 = w.bay_x(w.vent_bay)
        lo = Vector([min(p[k] for p in rails) for k in range(3)])
        hi = Vector([max(p[k] for p in rails) for k in range(3)])
        gp = DESIGN["sash_gap"]
        check(abs(lo.z - w.sz0) < TOL and abs(hi.z - w.sz1) < TOL, f"sash depth z {lo.z:.4f}..{hi.z:.4f} = sash_z")
        check(abs(lo.x - (x0 + gp)) < TOL and abs(hi.x - (x1 - gp)) < TOL and abs(lo.y - w.y0) < TOL
              and abs(hi.y - (w.y1 - gp)) < TOL, f"sash outline x {lo.x:.4f}..{hi.x:.4f} y {lo.y:.4f}..{hi.y:.4f}")
        gw = g(grip.matrix_world.translation)
        check(abs(gw.x - w.handle_x) < 1e-4 and abs(gw.y - w.handle_y) < 1e-4 and gw.z > w.sz1,
              f"HandleGrip at {fmt(*gw)} (handle_y {w.handle_y}, {w.vent['handle_stile']} stile x {w.handle_x:.4f})")
        hmax = max(p.z for p in pts)
        check(hmax < w.shade_z - DESIGN["bar_d"] / 2 or hmax > 0, f"handle reaches z={hmax:.4f} into the room")
        print("  swing (sash vs frame)")
        steps = [a * 0.5 for a in range(int(w.open_max * 2) + 1)]
        bad = hinge_clearance(sash, [sash], frame, angles=steps, axis="X", sign=1.0)
        check(not bad, f"sash swings clear 0..{w.open_max} deg")
        top = max(math.hypot(p.y - w.y0, p.z - w.sz1) for p in rails)
        check(w.y0 + top < w.y1 - 1e-3, f"sash's swept top {w.y0 + top:.4f} under the head rail {w.y1:.4f}")
    # 5. stone slab / threshold
    sill_pts = [p for p in verts if p.y <= w.B + eps and p.z > w.z1 - eps]
    if stone:
        top = max(p.y for p in sill_pts)
        low = min(p.y for p in verts if p.z > w.zi - eps)
        zmax = max(p.z for p in verts)
        xmax = max(abs(p.x) for p in verts if p.z > w.zi + eps)
        check(abs(top - w.B) < TOL and abs(low - (w.B - GODOT["sill_t"])) < TOL and abs(zmax - (w.zi + w.ov)) < TOL
              and abs(xmax - (w.W / 2 + GODOT["sill_ears"])) < TOL,
              f"stone slab y {low:.4f}..{top:.4f}, to z={zmax:.4f}, ears to x=+-{xmax:.4f}")
    else:
        top = max(p.y for p in verts if w.z1 + eps < p.z < w.zi - eps and p.y < w.B + 0.01)
        check(abs(top - w.sill_y) < TOL, f"threshold top y={top:.4f}")
    # 6. shade bars
    for vent in (False, True):
        objs = bar_objects(w.name, vent)
        if not objs:
            continue
        bar = objs[0]
        bay = w.vent_bay if vent else [i for i in range(w.n) if i != w.vent_bay][0]
        lo = Vector([min(v.co[k] for v in bar.data.vertices) for k in range(3)])
        hi = Vector([max(v.co[k] for v in bar.data.vertices) for k in range(3)])
        size = Vector((hi.x - lo.x, hi.z - lo.z, hi.y - lo.y))  # Godot (x, y, z)
        top = g(bar.matrix_world.translation)
        check(abs(size.x - w.shade_width(bay)) < TOL and abs(hi.z) < 1e-6 and abs(lo.x + hi.x) < 1e-6,
              f"{'vent ' if vent else ''}bar {fmt(*size)} (want width {w.shade_width(bay):.4f}), origin top center")
        check((top - Vector(w.shade_top(bay))).length < 1e-5, f"bar parked at {fmt(*top)}")
        x0, x1 = w.slot_x(bay)
        check(x1 - x0 < size.x, f"slot {x0:.4f}..{x1:.4f} hidden by the bar")
    # 7. budgets
    ft = sum(tri_count(o) for o in frame)
    mats = {m.name for o in frame for m in o.data.materials}
    check(ft <= BUDGET["frame"] and len(mats) <= 5 and MAT_LED in mats,
          f"frame {ft} tris, materials {sorted(mats)}")
    if w.vent:
        st = sum(tri_count(o) for o in sash_objects(w.name))
        check(st <= BUDGET["sash"], f"sash {st} tris")


def report(w):
    print(f"REPORT {w.name}")
    for i in range(w.n):
        x0, x1, y0, y1 = w.glass_rect(i)
        tag = " (vent, closed; sash-local " + fmt(x0 - w.hinge[0], x1 - w.hinge[0], y0 - w.hinge[1], y1 - w.hinge[1]) + \
            f" at z={w.gz - w.hinge[2]:.4f})" if i == w.vent_bay else ""
        print(f"  glass bay {i}: x {x0:.4f}..{x1:.4f} y {y0:.4f}..{y1:.4f} z {w.gz}{tag}")
    if w.vent:
        sash = [o for o in sash_objects(w.name) if o.type == "MESH"][0]
        grip = [o for o in sash_objects(w.name) if o.name.startswith("HandleGrip")][0]
        print(f"  hinge axis along X through {fmt(*w.hinge)}; HandleGrip window {fmt(*g(grip.matrix_world.translation))} "
              f"sash-local {fmt(*g(grip.matrix_world.translation - sash.matrix_world.translation))}")
    for i in range(w.n):
        if not w.shade:
            break
        x0, x1 = w.slot_x(i)
        t = w.shade_top(i)
        where = "sash top rail" if i == w.vent_bay else "head rail"
        print(f"  shade bay {i}: slot in the {where} y={t[1]:.4f} z {w.slot_z[0]:.4f}..{w.slot_z[1]:.4f} "
              f"x {x0:.4f}..{x1:.4f}; bar top center {fmt(*t)}, bar {w.shade_width(i):.4f} x {DESIGN['bar_h']} x "
              f"{DESIGN['bar_d']} m")
    if w.sill == "stone":
        print(f"  stone slab y {w.B - GODOT['sill_t']:.3f}..{w.B:.3f}, z {w.ze:.3f}..{w.zi + w.ov:.3f}, "
              f"x +-{w.W / 2 + GODOT['sill_ears']:.3f} (nose only past the opening)")
    print(f"  LED channel y={w.head_y + DESIGN['led_depth']:.4f} z {w.led_z[0]:.4f}..{w.led_z[1]:.4f}, "
          f"returns down the jambs to y={w.head_y - min(DESIGN['led_return'], 0.25 * (w.head_y - w.sill_y)):.4f}")


def check_kit():
    print("KIT")
    panel = [o for o in panel_objects() if o.type == "MESH"][0]
    btn = button_objects()[0]
    t = tri_count(panel) + tri_count(btn)
    mats = {m.name for m in panel.data.materials}
    check(t <= BUDGET["kit"] and MAT_PANEL_LED in mats, f"panel + button {t} tris, panel materials {sorted(mats)}")
    for e in [o for o in panel_objects() if o.type == "EMPTY"]:
        p = g(e.matrix_world.translation - panel.matrix_world.translation)
        print(f"REPORT panel {e.name} (button cap back center, panel-local) {fmt(*p)}")
    lo = Vector([min(v.co[k] for v in panel.data.vertices) for k in range(3)])
    hi = Vector([max(v.co[k] for v in panel.data.vertices) for k in range(3)])
    print(f"REPORT panel size {fmt(hi.x - lo.x, hi.z - lo.z, hi.y - lo.y)} (x, y, z), back at z={-hi.y:.4f}")
    lo = Vector([min(v.co[k] for v in btn.data.vertices) for k in range(3)])
    hi = Vector([max(v.co[k] for v in btn.data.vertices) for k in range(3)])
    print(f"REPORT button cap size {fmt(hi.x - lo.x, hi.z - lo.z, hi.y - lo.y)}, back at z={-hi.y:.4f}")
    for img in bpy.data.images:
        if img.size[0] and img.packed_file is not None:
            lim = 1024
            check(max(img.size) <= lim, f"image {img.name} {img.size[0]}x{img.size[1]} <= {lim}")


def main():
    path, data = load_spec()
    print("SPEC", path)
    const, cpath = godot_constants()
    if const is None:
        print(f"  (no Godot generator at {cpath}: constants not cross-checked)")
    else:
        for k, v in const.items():
            check(v is not None and abs(v - GODOT[k]) < 1e-9, f"Godot {k} = {v} matches {GODOT[k]} ({cpath})")
    bpy.ops.wm.open_mainfile(filepath=blend_path(path))
    wins = windows(data)
    for w in wins:
        w.check_fits()
        check_window(w)
    check_kit()
    for w in wins:
        report(w)
    print("VERIFY", "OK" if not FAILS else f"FAIL ({len(FAILS)}): " + "; ".join(FAILS))
    glbs = []
    for w in wins:
        glbs.append(glb_frame(w.name))
        if w.vent:
            glbs += [glb_sash(w.name), glb_bar(w.name, True)]
        glbs.append(glb_bar(w.name))
    glbs += [GLB_PANEL, GLB_BUTTON]
    for p in glbs:
        if os.path.exists(p):
            import_report(p)
        else:
            print("MISSING", p)
            FAILS.append(f"missing {p}")
    if FAILS:
        sys.exit(1)


if __name__ == "__main__":
    main()
