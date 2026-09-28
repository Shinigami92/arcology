"""Shared constants and helpers for the fridge__fable-high build pipeline.

Run the stages with Blender 5.2 in background mode:

  blender -b --factory-startup --python build.py
  blender -b --factory-startup <blend> --python bake.py
  blender -b --factory-startup <blend> --python export.py
  blender -b --factory-startup <blend> --python render.py
  blender -b --factory-startup --python verify.py

Coordinates: Blender Z up, meters, fridge front faces -Y. Body objects are
built in world coordinates (identity transforms). Door objects are built in
door-local coordinates (hinge axis at the local origin, door extends along
+X, front face toward -Y) and parented to the `Door` object which sits at the
hinge (-0.30, -0.325, 0).
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

VARIANT = "fable-high"
ROOT = os.path.normpath("D:/shinigami/OpenSource/Shinigami92/vr/arcology")
BLEND = os.path.join(ROOT, "blender", "props", f"fridge__{VARIANT}.blend")
GLB_BODY = os.path.join(ROOT, "assets", "props", "fridge", f"fridge_body__{VARIANT}.glb")
GLB_DOOR = os.path.join(ROOT, "assets", "props", "fridge", f"fridge_door__{VARIANT}.glb")
SCRATCH = os.path.normpath(
    "C:/Users/SHINIG~1/AppData/Local/Temp/claude/"
    "D--shinigami-OpenSource-Shinigami92-vr-arcology/"
    "ba33803b-66f4-4d2d-888c-256bfbff8876/scratchpad/fridge"
)

# --- Fixed contract -------------------------------------------------------
CAB_W, CAB_D, CAB_H = 0.60, 0.65, 1.85
CAB_X = CAB_W / 2  # 0.30
CAB_Y = CAB_D / 2  # 0.325
HINGE = Vector((-CAB_X, -CAB_Y, 0.0))

# Cabinet shell
WALL_SIDE = 0.045
WALL_BACK = 0.06
WALL_TOP = 0.08
CAV_X = CAB_X - WALL_SIDE  # 0.255
CAV_Y_BACK = CAB_Y - WALL_BACK  # 0.265
CAV_Z0 = 0.12
CAV_Z1 = CAB_H - WALL_TOP  # 1.77
PLINTH_Z = 0.085
PLINTH_DEPTH = 0.035

# Door (local coordinates, hinge at origin)
DOOR_W = 0.60
DOOR_T = 0.055
DOOR_Z0 = 0.09
DOOR_Z1 = 1.845  # 5 mm below the cabinet top / hinge bracket
DOOR_SKIN_Y0, DOOR_SKIN_Y1 = -DOOR_T, -0.012
DOOR_LINER_Y0, DOOR_LINER_Y1 = -0.012, -0.003
GASKET_Y0, GASKET_Y1 = -0.012, -0.001  # 1 mm clearance to the cabinet front
BIN_Y1 = 0.09  # how far the door bins reach into the cavity

# Handle
HANDLE_X = 0.555
HANDLE_Y = -0.100
HANDLE_Z0, HANDLE_Z1 = 0.95, 1.55
HANDLE_R = 0.0125
HANDLE_GRIP = Vector((HANDLE_X, HANDLE_Y, 1.25))

# Shelves (top surface z) and crisper
SHELF_TOPS = [0.72, 1.07, 1.42]
SHELF_Y0 = -0.175
GLASS_T = 0.006
CRISPER_COVER_TOP = 0.35
CRISPER_Y0 = -0.22
CRISPER_W, CRISPER_D, CRISPER_H = 0.49, 0.44, 0.20
CRISPER_TRAVEL = 0.30

BODY_MAT = "FridgeBody"
DOOR_MAT = "FridgeDoor"
GLASS_MAT = "FridgeGlass"
DISPLAY_MAT = "FridgeDisplay"
LIGHT_MAT = "FridgeLight"

TEX_SIZE = 2048


# --- Scene helpers ----------------------------------------------------------
def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights,
                 bpy.data.cameras, bpy.data.node_groups):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def bm_box(bm, lo, hi):
    lo, hi = Vector(lo), Vector(hi)
    size = hi - lo
    center = (lo + hi) / 2
    mat = Matrix.Translation(center) @ Matrix.Diagonal((size.x, size.y, size.z, 1.0))
    return bmesh.ops.create_cube(bm, size=1.0, matrix=mat)["verts"]


def bm_cyl(bm, radius, depth, matrix, segments=24):
    return bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius, radius2=radius, depth=depth, matrix=matrix,
    )["verts"]


def cyl_matrix_z(center, ):
    return Matrix.Translation(Vector(center))


def cyl_matrix_y(center):
    """Cylinder axis along Y."""
    return Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(90), 4, "X")


def cyl_matrix_x(center):
    return Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(90), 4, "Y")


def new_object(name, bm, collection, origin=(0, 0, 0), material=None, parent=None):
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


def apply_modifiers(ob):
    """Replace the object's mesh with its evaluated mesh (modifiers applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    originals = [m for m in old.materials if m is not None]
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name + "_applied"
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
    mod = ob.modifiers.new("Cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    return mod


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
    if bevel_width:
        bevel(ob, bevel_width, segments, angle)
    if ob.modifiers:
        apply_modifiers(ob)
    shade(ob, sharp_angle)


def assign_by_region(ob, regions, default):
    """Assign materials per polygon by the polygon center (object-local coordinates).

    regions: list of ((lo, hi), material) checked in order.
    """
    me = ob.data
    me.materials.clear()
    mats = [default] + [m for _, m in regions]
    uniq = []
    for m in mats:
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


def tri_count(ob):
    me = ob.data
    if me is None or ob.type != "MESH":
        return 0
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def group_objects(prefix_names):
    return [bpy.data.objects[n] for n in prefix_names if n in bpy.data.objects]


def body_objects():
    """Render meshes of the body glb (no collision)."""
    return [ob for ob in bpy.data.objects
            if ob.get("fridge_part") == "body" and ob.type == "MESH"]


def body_collision_objects():
    return [ob for ob in bpy.data.objects if ob.get("fridge_part") == "body_col"]


def door_objects():
    return [ob for ob in bpy.data.objects if ob.get("fridge_part") == "door"]


def setup_gpu(scene):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        scene.cycles.device = "GPU"
    except Exception as exc:  # fall back to CPU
        print("GPU setup failed, using CPU:", exc)
        scene.cycles.device = "CPU"


def set_colorspace(image, name):
    try:
        image.colorspace_settings.name = name
    except TypeError:
        alt = {"Non-Color": "Non-Color", "sRGB": "sRGB"}.get(name, name)
        image.colorspace_settings.name = alt
