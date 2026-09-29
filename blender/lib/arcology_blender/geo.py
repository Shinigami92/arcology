"""Geometry: bmesh primitives, objects, instances, attributes, bevel/boolean/shading, per-region materials, BVH."""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from .scene import PART_KEY


# --- bmesh primitives (add to an existing bmesh) ------------------------------
def bm_box(bm, lo, hi):
    """Axis-aligned box from corner `lo` to corner `hi`."""
    lo, hi = Vector(lo), Vector(hi)
    size = hi - lo
    mat = Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((size.x, size.y, size.z, 1.0))
    return bmesh.ops.create_cube(bm, size=1.0, matrix=mat)["verts"]


def bm_cyl(bm, radius, depth, matrix, segments=24):
    """Capped cylinder along the matrix's Z axis (see cyl_x/cyl_y/cyl_z)."""
    return bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius, radius2=radius, depth=depth, matrix=matrix,
    )["verts"]


def cyl_z(center):
    return Matrix.Translation(Vector(center))


def cyl_y(center):
    """Cylinder axis along Y (e.g. a knob or standoff on a -Y facing front)."""
    return Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(90), 4, "X")


def cyl_x(center):
    return Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(90), 4, "Y")


def bm_quad(bm, points):
    """One face from four points (counter-clockwise seen from the front)."""
    return bm.faces.new([bm.verts.new(p) for p in points])


def bm_cone(bm, r_bottom, r_top, depth, matrix, segments=24):
    """Capped cone frustum along the matrix's Z axis (tapered legs, feet, spikes)."""
    return bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=r_bottom, radius2=r_top, depth=depth, matrix=matrix,
    )["verts"]


def bm_square_taper(bm, x, y, z0, z1, top, bottom):
    """Square furniture leg from z0 (`bottom` wide) to z1 (`top` wide), axis-aligned
    (a 4-sided cone turned 45 degrees)."""
    s2 = math.sqrt(2.0)
    mat = Matrix.Translation((x, y, (z0 + z1) / 2)) @ Matrix.Rotation(math.radians(45.0), 4, "Z")
    return bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=4,
                                 radius1=bottom / 2 * s2, radius2=top / 2 * s2, depth=z1 - z0,
                                 matrix=mat)["verts"]


def bm_open_box(bm, lo, hi, wall, floor=None, open_axis=2):
    """Open-top box (drawer, tray, bin) as five slabs: a floor `floor` thick
    (default `wall`) and four walls `wall` thick, between corners `lo` and
    `hi`; the open face is the +side of `open_axis`. Watertight slabs that
    share faces, meant for `finish` (bevel) afterwards. Flip it for a lid
    (scale z by -1, translate, recalc normals)."""
    lo, hi = Vector(lo), Vector(hi)
    f = wall if floor is None else floor
    a, b = [i for i in range(3) if i != open_axis]
    up = open_axis
    flo, fhi = lo.copy(), hi.copy()
    fhi[up] = lo[up] + f
    bm_box(bm, flo, fhi)
    for axis in (a, b):
        for side in (0, 1):
            wlo, whi = lo.copy(), hi.copy()
            wlo[up] = lo[up] + f
            if side == 0:
                whi[axis] = lo[axis] + wall
            else:
                wlo[axis] = hi[axis] - wall
            if axis == b:  # shorten so the corners don't double up
                wlo[a] += wall
                whi[a] -= wall
            bm_box(bm, wlo, whi)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)


def bm_merge(bm, other):
    """Append bmesh `other` into `bm` (frees `other`), e.g. several soft shapes in one object."""
    me = bpy.data.meshes.new("tmp_merge")
    other.to_mesh(me)
    other.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


# --- objects -------------------------------------------------------------------
def new_object(name, bm, collection, origin=(0, 0, 0), material=None, parent=None):
    """Mesh object from a bmesh (freed). Geometry is in object-local coordinates."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    collection.objects.link(ob)
    if material is not None:
        me.materials.append(material)
    if parent is not None:
        ob.parent = parent
    return ob


def new_empty(name, collection, location, parent=None, display="SPHERE", size=0.03):
    """Empty used as a marker exported to Godot (grip points, sockets)."""
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = display
    ob.empty_display_size = size
    ob.location = location
    ob.parent = parent
    collection.objects.link(ob)
    return ob


def instance(src, name, location, rotation=(0.0, 0.0, 0.0), collection=None, parent=None, part=None):
    """Linked duplicate sharing `src`'s mesh (same UVs and baked material), e.g.
    the second of two identical drawers: bake and export the original once,
    instance its glb twice in Godot. Linked into `collection` (default: the
    source's first collection) and tagged `part` if given."""
    ob = bpy.data.objects.new(name, src.data)
    ob.location = location
    ob.rotation_euler = rotation
    ob.parent = parent
    (collection or src.users_collection[0]).objects.link(ob)
    if part is not None:
        ob[PART_KEY] = part
    return ob


def smooth_object(name, bm, collection, material, angle=80.0, parent=None):
    """Mesh object from a bmesh, smooth shaded up to `angle` (80: soft goods,
    smooth everywhere)."""
    ob = new_object(name, bm, collection, material=material, parent=parent)
    shade(ob, angle)
    return ob


def set_point_attr(ob, name, value):
    """Constant float point attribute on a mesh object (e.g. a per-board grain
    frame the material reads with `Graph.attribute`). Survives `join`.
    Remove it before export with `remove_attribute`."""
    me = ob.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", [float(value)] * len(me.vertices))
    return a


def set_float_attr(ob, name, fn):
    """Write a float point attribute from fn(vertex world position, attrs dict)
    where attrs holds the vertex's existing float point attributes by name
    (masks computed after a simulation from the flat cloth coordinates, etc.)."""
    me = ob.data
    names = [a.name for a in me.attributes if a.domain == "POINT" and a.data_type == "FLOAT"]
    vals = {n: [d.value for d in me.attributes[n].data] for n in names}
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    mw = ob.matrix_world
    for i, v in enumerate(me.vertices):
        a.data[i].value = fn(mw @ v.co, {n: vals[n][i] for n in names})


def set_uvs(ob, uvs):
    """Explicit UVs for a single-face object (e.g. a screen that shows a whole texture)."""
    layer = ob.data.uv_layers.new(name="UVMap")
    for loop, uv in zip(layer.data, uvs):
        loop.uv = uv


def remove(ob):
    bpy.data.objects.remove(ob, do_unlink=True)


def apply_modifiers(ob):
    """Replace the object's mesh with its evaluated mesh (modifiers applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    originals = [m for m in old.materials if m is not None]
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name
    # A boolean cutter without material adds empty slots; keep the object's own material.
    if originals and any(m is None for m in me.materials):
        me.materials.clear()
        me.materials.append(originals[0])
        for p in me.polygons:
            p.material_index = 0


def bevel(ob, width, segments=2, angle=30.0):
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.miter_outer = "MITER_ARC"
    return mod


def boolean_cut(ob, cutter):
    """Adds a DIFFERENCE boolean (applied by finish/apply_modifiers)."""
    mod = ob.modifiers.new("Cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    return mod


def cut(ob, bm, collection):
    """Cut the shape in `bm` (same local frame as `ob`) out of `ob` and apply it."""
    cutter = new_object(ob.name + "Cutter", bm, collection, origin=ob.location, parent=ob.parent)
    boolean_cut(ob, cutter)
    apply_modifiers(ob)
    remove(cutter)


def shade(ob, sharp_angle=30.0):
    """Smooth shading with sharp edges marked by angle (exported as split normals)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    limit = math.radians(sharp_angle)
    for e in bm.edges:
        if e.is_boundary or not e.is_manifold:
            e.smooth = False
            continue
        e.smooth = e.calc_face_angle(0.0) < limit
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()


def finish(ob, bevel_width=None, segments=2, angle=30.0, sharp_angle=30.0):
    """Optional bevel, apply all modifiers, shade. Bevel real edges: they catch light."""
    if bevel_width:
        bevel(ob, bevel_width, segments, angle)
    if ob.modifiers:
        apply_modifiers(ob)
    shade(ob, sharp_angle)


def assign_by_region(ob, regions, default):
    """Assign materials per polygon by the polygon center (object-local coordinates).

    regions: list of ((lo, hi), material), first match wins; others get `default`.
    """
    me = ob.data
    me.materials.clear()
    uniq = []
    for m in [default] + [m for _, m in regions]:
        if m not in uniq:
            uniq.append(m)
    for m in uniq:
        me.materials.append(m)
    for p in me.polygons:
        c = p.center
        idx = 0
        for (lo, hi), m in regions:
            if lo[0] <= c.x <= hi[0] and lo[1] <= c.y <= hi[1] and lo[2] <= c.z <= hi[2]:
                idx = uniq.index(m)
                break
        p.material_index = idx


def collision_box(name, lo, hi, collection):
    """Box for Godot's importer: `-convcolonly` makes it a StaticBody3D with a convex shape."""
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    ob = new_object(f"{name}-convcolonly", bm, collection)
    ob.display_type = "WIRE"
    return ob


def join(objs, name):
    """Join mesh objects into the first one, renamed `name` (mesh too)."""
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def remove_attribute(ob, name):
    """Drop a build-time mesh attribute (e.g. `soft.SEAM_ATTR`) so it doesn't reach the glb."""
    a = ob.data.attributes.get(name)
    if a is not None:
        ob.data.attributes.remove(a)


def bvh(objs):
    """One world-space BVH over mesh objects (ray casts, nearest points).
    Call `bpy.context.view_layer.update()` first if transforms just changed."""
    verts, tris = [], []
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        off = len(verts)
        mw = ob.matrix_world
        verts += [mw @ v.co for v in me.vertices]
        tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris)


def trim_hidden(ob, covers, reach=0.08, dilate=0.09, min_nz=0.7):
    """Delete upward faces of `ob` (normal z > min_nz) hidden under `covers`
    (a mattress top under a duvet): rays along the face normal from the
    center and four dilated points all hit a cover within `reach`. Side faces
    stay: the gap behind a hanging hem is visible from low angles."""
    trees = [bvh([c]) for c in covers]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    kill = []
    for f in bm.faces:
        n = f.normal
        if n.z < min_nz:
            continue
        c = f.calc_center_median()
        t1 = n.orthogonal().normalized()
        t2 = n.cross(t1)
        pts = [c] + [c + t * dilate * s for t in (t1, t2) for s in (-1, 1)]
        if all(any(t.ray_cast(p + n * 0.001, n, reach)[0] is not None for t in trees) for p in pts):
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    print(f"TRIM {ob.name}: {len(kill)} hidden faces removed")
