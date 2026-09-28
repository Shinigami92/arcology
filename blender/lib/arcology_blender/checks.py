"""Checks for moving parts (BVH overlap sweeps) and a glb import report."""

import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .scene import tri_count


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
    within `contact` meters doesn't count.

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
