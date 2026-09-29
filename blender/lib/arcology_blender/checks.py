"""Checks: bounds and Godot conversions, clearance sweeps for moving parts,
collider-vs-render gaps, and a glb import report.

verify.py scripts open the saved .blend, print contract lines (bounds, seat
heights, collision sizes in Godot axes) and end with `import_report` per glb.
Blender (x, y, z) is Godot (x, z, -y); sizes (x, z, y).
"""

import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .geo import bvh
from .scene import tri_count


# --- bounds and reporting --------------------------------------------------------
def world_bounds(objs):
    """(lo, hi) world-space corners over the vertices of the mesh objects."""
    pts = [o.matrix_world @ v.co for o in objs if o.type == "MESH" for v in o.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def local_bounds(ob):
    """(lo, hi) of a mesh object's vertices in its own frame (a part's size around its origin)."""
    pts = [v.co for v in ob.data.vertices]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def godot(v):
    """Blender (x, y, z) -> Godot (x, z, -y), for positions."""
    return (v[0], v[2], -v[1])


def godot_size(size):
    """Blender (x, y, z) extent -> Godot (x, z, y)."""
    return (size[0], size[2], size[1])


def fmt(t, digits=3):
    return "(" + ", ".join(f"{c:.{digits}f}" for c in t) + ")"


def inside(lo, hi, limit_lo, limit_hi, tol=1e-4):
    """True if the box lo..hi lies within limit_lo..limit_hi (per axis, with tolerance)."""
    return all(limit_lo[i] - tol <= lo[i] and hi[i] <= limit_hi[i] + tol for i in range(3))


def collision_report(objs):
    """Print each collision object's Godot center and size (for the .tscn or a report)."""
    print("COLLISION (Godot center, size)")
    for ob in sorted(objs, key=lambda o: o.name):
        lo, hi = world_bounds([ob])
        print(f"  {ob.name:28s} center={fmt(godot((lo + hi) / 2))} size={fmt(godot_size(hi - lo))}")


def _tree(objs, inset=0.0):
    """One BVH of the objects' current world-space triangles.

    inset shrinks each object toward its bounding-box center by that many
    meters per side, so parts that merely touch (a drawer resting on its
    runners) don't count as overlapping.
    """
    verts, tris = [], []
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        off = len(verts)
        cos = [v.co.copy() for v in me.vertices]
        if inset and cos:
            lo = Vector([min(c[i] for c in cos) for i in range(3)])
            hi = Vector([max(c[i] for c in cos) for i in range(3)])
            mid, half = (lo + hi) / 2, (hi - lo) / 2
            scale = [max(h - inset, 0.0) / h if h > 0 else 1.0 for h in half]
            cos = [mid + Vector([(c[i] - mid[i]) * scale[i] for i in range(3)]) for c in cos]
        verts += [ob.matrix_world @ c for c in cos]
        tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris, epsilon=0.0)


def _meshes(objs):
    return [o for o in objs if o.type == "MESH"]


def hinge_clearance(root, moving, fixed, angles=range(0, 101, 5), axis="Z", sign=-1.0, contact=0.0005):
    """Rotate `root` (whose children are `moving`) through `angles` degrees about
    its local axis and report overlaps with `fixed`. Opening is `sign` * angle
    (the project's doors open with a negative rotation about Z). Touching
    within `contact` meters doesn't count. Fixed parts are read at their
    current matrix_world: after moving them (a door opened for a drawer
    check), call `bpy.context.view_layer.update()` first.

    Returns the angles that collide; prints one line per angle.
    """
    fixed_tree = _tree(_meshes(fixed))
    saved = root.rotation_euler.copy()
    bad = []
    for ang in angles:
        rot = [0.0, 0.0, 0.0]
        rot["XYZ".index(axis)] = math.radians(sign * ang)
        root.rotation_euler = rot
        bpy.context.view_layer.update()
        n = len(_tree(_meshes(moving), contact).overlap(fixed_tree))
        if n:
            bad.append(ang)
        print(f"  hinge {ang:5.1f} deg: {'clear' if not n else f'{n} overlapping triangle pairs'}")
    root.rotation_euler = saved
    bpy.context.view_layer.update()
    return bad


def slide_clearance(root, moving, fixed, direction, travel, steps=10, contact=0.0005):
    """Move `root` along `direction` (world) up to `travel` meters and report
    overlaps with `fixed` (touching within `contact` meters doesn't count).
    Returns the distances that collide."""
    fixed_tree = _tree(_meshes(fixed))
    saved = root.location.copy()
    d = Vector(direction).normalized()
    bad = []
    for i in range(steps + 1):
        s = travel * i / steps
        root.location = saved + d * s
        bpy.context.view_layer.update()
        n = len(_tree(_meshes(moving), contact).overlap(fixed_tree))
        if n:
            bad.append(s)
        print(f"  slide {s:.3f} m: {'clear' if not n else f'{n} overlapping triangle pairs'}")
    root.location = saved
    bpy.context.view_layer.update()
    return bad


def surface_gap(render_objs, collider_objs, lo, hi, spacing, classify=None):
    """Distance between a render surface and its collider, sampled where the
    render surface is visible from above: vertical rays on a grid (offset by
    half a cell from any sampling grid) hit the render surface at p; the gap
    is the distance from p to the nearest collider point, signed + when the
    collider lies above p (vertical ray). classify(p) -> region name groups
    the results. Returns {region: [(gap, signed_dz, p), ...]}."""
    rt, ct = bvh(render_objs), bvh(collider_objs)
    nx = max(1, int(round((hi[0] - lo[0]) / spacing)))
    ny = max(1, int(round((hi[1] - lo[1]) / spacing)))
    down = Vector((0.0, 0.0, -1.0))
    out = {}
    for i in range(nx):
        for j in range(ny):
            x = lo[0] + (hi[0] - lo[0]) * (i + 0.5) / nx
            y = lo[1] + (hi[1] - lo[1]) * (j + 0.5) / ny
            h = rt.ray_cast(Vector((x, y, 3.0)), down)
            if h[0] is None:
                continue
            p = h[0]
            near = ct.find_nearest(p)
            hc = ct.ray_cast(Vector((x, y, 3.0)), down)
            dz = (hc[0].z - p.z) if hc[0] is not None else float("nan")
            region = classify(p) if classify else "all"
            out.setdefault(region, []).append((near[3], dz, p))
    return out


def probe_gap(render_objs, collider_objs, lo, hi, spacing, radius, classify=None):
    """Like surface_gap, but against the surface a probe sphere of `radius`
    feels when lowered onto the render mesh from above (a morphological
    closing of the heightfield): slots narrower than 2 * radius (between a
    mattress and a hanging hem, between two pillows) are bridged, as any
    real object would bridge them. Use a radius below the smallest object
    that should rest there (a can is 33 mm). For each probe position resting
    on the render surface, the gap is |distance(center, collider) - radius|:
    how far the same probe would float above or sink into the collider.
    Returns {region: [(gap, contact_point), ...]}."""
    import numpy as np

    from .collision import heightfield
    xs, ys, zs = heightfield(render_objs, lo, hi, spacing, -1.0)
    h = np.array(zs)
    k = int(radius / spacing)
    env = np.full_like(h, -1e9)
    nx, ny = h.shape
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            d2 = (di * spacing) ** 2 + (dj * spacing) ** 2
            if d2 > radius * radius:
                continue
            lift = math.sqrt(radius * radius - d2)
            sh = np.full_like(h, -1e9)
            sh[max(0, -di):nx - max(0, di), max(0, -dj):ny - max(0, dj)] = \
                h[max(0, di):nx - max(0, -di), max(0, dj):ny - max(0, -dj)]
            env = np.maximum(env, sh + lift)
    ct = bvh(collider_objs)
    out = {}
    for i in range(k, nx - k):
        for j in range(k, ny - k):
            c = Vector((xs[i], ys[j], float(env[i, j])))
            near = ct.find_nearest(c)
            p = c - Vector((0.0, 0.0, radius))
            region = classify(p) if classify else "all"
            out.setdefault(region, []).append((abs(near[3] - radius), p))
    return out


def import_report(path):
    """Re-import a glb into an empty scene and print objects, origins, triangles, materials."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    print(f"IMPORT {path}")
    total = 0
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        mats = [m.name for m in ob.data.materials] if ob.type == "MESH" else []
        t = tri_count(ob)
        total += t
        loc = ob.matrix_world.translation
        dims = ob.dimensions
        print(f"  {ob.name:26s} {ob.type:6s} parent={ob.parent.name if ob.parent else '-':8s} "
              f"pos=({loc.x:.3f},{loc.y:.3f},{loc.z:.3f}) dims=({dims.x:.3f},{dims.y:.3f},{dims.z:.3f}) "
              f"tris={t} mats={mats}")
    print(f"  TOTAL tris={total}")
    for m in bpy.data.materials:
        imgs = []
        if m.use_nodes:
            imgs = [f"{n.image.name}:{n.image.size[0]}x{n.image.size[1]}"
                    for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
        print(f"  MATERIAL {m.name} images={imgs}")
    return total
