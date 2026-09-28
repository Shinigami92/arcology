"""Geometry: bmesh primitives, objects, bevel/boolean/shading, per-region materials."""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector


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
