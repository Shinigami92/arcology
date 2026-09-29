"""Collision for Godot's importer: boxes and heightfield trimeshes (D-028).

Name suffixes decide what Godot builds: `-convcolonly` a StaticBody3D with a
convex shape (boxes, `collision_box`), `-colonly` a trimesh
(ConcavePolygonShape3D, `heightfield_collider`). Moving parts (doors,
drawers) get their collision in the Godot scene instead. Check a trimesh
against its render surface with `checks.surface_gap` and `checks.probe_gap`.
Promoted from the bed (Opus 5.5).
"""

import math

import bmesh
import bpy
from mathutils import Vector

from .geo import bvh, collision_box  # noqa: F401  (collision_box re-exported)


def heightfield(objs, lo, hi, spacing, floor_z, top_z=3.0):
    """Top surface of `objs` seen from above: z of the first hit of a vertical
    ray on a grid over the world rectangle lo..hi (x, y), `floor_z` where
    nothing is hit. Returns (xs, ys, zs) with zs[i][j] at (xs[i], ys[j])."""
    tree = bvh(objs)
    nx = max(1, int(round((hi[0] - lo[0]) / spacing)))
    ny = max(1, int(round((hi[1] - lo[1]) / spacing)))
    xs = [lo[0] + (hi[0] - lo[0]) * i / nx for i in range(nx + 1)]
    ys = [lo[1] + (hi[1] - lo[1]) * j / ny for j in range(ny + 1)]
    down = Vector((0.0, 0.0, -1.0))
    zs = []
    for x in xs:
        row = []
        for y in ys:
            h = tree.ray_cast(Vector((x, y, top_z)), down)
            row.append(max(floor_z, h[0].z) if h[0] is not None else floor_z)
        zs.append(row)
    return xs, ys, zs


def heightfield_collider(name, objs, lo, hi, spacing, target_tris, skirt_z, collection, planar_angle=None,
                         protect=None, protect_factor=1.0):
    """Static trimesh collider (`<name>-colonly`: Godot makes a
    ConcavePolygonShape3D) that follows the visible top of soft goods (a
    duvet, pillows, a tablecloth) so resting objects sit on the cloth.

    Samples a dense heightfield (see `heightfield`), decimates it (quadric
    collapse) to about `target_tris` including a skirt that closes the
    boundary down to `skirt_z`, so nothing slips under the edge. Faces point
    up (skirt outward). planar_angle (degrees) first dissolves nearly flat
    regions (planar decimation), which spends the triangle budget on folds
    and edges instead of flat duvet; the collapse then reaches the target.
    protect(x, y, z) -> 0..1 marks samples the collapse should keep (e.g.
    around spots where a first pass was off). Decimate's vertex group
    weights mean "may collapse", so they are stored inverted (1 - protect)
    with strength `protect_factor`.
    Check the result with `checks.surface_gap` / `checks.probe_gap`.
    Returns the object."""
    xs, ys, zs = heightfield(objs, lo, hi, spacing, skirt_z)
    bm = bmesh.new()
    grid = [[bm.verts.new((x, y, zs[i][j])) for j, y in enumerate(ys)] for i, x in enumerate(xs)]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    me = bpy.data.meshes.new(name + "-colonly")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name + "-colonly", me)
    collection.objects.link(ob)
    if protect is not None:
        vg = ob.vertex_groups.new(name="_keep")
        for v in me.vertices:
            w = protect(*v.co)
            # Decimate collapses vertices by their group weight: 1 - protection
            vg.add([v.index], 1.0 - max(0.0, min(1.0, w)), "REPLACE")
    if planar_angle:
        pm = ob.modifiers.new("Planar", "DECIMATE")
        pm.decimate_type = "DISSOLVE"
        pm.angle_limit = math.radians(planar_angle)
        pm.delimit = set()
        tm = ob.modifiers.new("Tri", "TRIANGULATE")  # noqa: F841
        dg = bpy.context.evaluated_depsgraph_get()
        me1 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        ob.data = me1
        bpy.data.meshes.remove(me)
        me = me1
    me.calc_loop_triangles()
    dense = len(me.loop_triangles)
    base = ob.data

    def decimate(ratio):
        mod = ob.modifiers.new("Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        if protect is not None:
            mod.vertex_group = "_keep"
            mod.vertex_group_factor = protect_factor
        dg = bpy.context.evaluated_depsgraph_get()
        out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        return out

    def total_tris(m):
        bmx = bmesh.new()
        bmx.from_mesh(m)
        n = len(bmx.faces) + 2 * sum(1 for e in bmx.edges if e.is_boundary)
        bmx.free()
        return n

    # the collapse ratio doesn't map exactly to a count: iterate to the target (skirt included)
    ratio = target_tris / dense
    for attempt in range(4):
        me2 = decimate(ratio)
        n = total_tris(me2)
        if abs(n - target_tris) <= 0.03 * target_tris or attempt == 3:
            break
        ratio *= target_tris / n
        bpy.data.meshes.remove(me2)
    ob.data = me2
    bpy.data.meshes.remove(base)
    me2.name = ob.name

    bm = bmesh.new()
    bm.from_mesh(me2)
    boundary = [e for e in bm.edges if e.is_boundary]
    low = {}

    def drop(v):
        if v not in low:
            low[v] = bm.verts.new((v.co.x, v.co.y, skirt_z))
        return low[v]

    for e in boundary:
        f = e.link_faces[0]
        # the face walks the edge a -> b; the skirt walks it b -> a (consistent winding)
        for lp in f.loops:
            if lp.edge == e:
                a, b = lp.vert, lp.link_loop_next.vert
                break
        if a.co.z - skirt_z < 1e-4 and b.co.z - skirt_z < 1e-4:
            continue
        if a.co.z - skirt_z < 1e-4:
            bm.faces.new([b, a, drop(b)])
        elif b.co.z - skirt_z < 1e-4:
            bm.faces.new([b, a, drop(a)])
        else:
            bm.faces.new([b, a, drop(a), drop(b)])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(me2)
    bm.free()
    ob.vertex_groups.clear()
    ob.display_type = "WIRE"
    return ob
