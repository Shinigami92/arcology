"""Stage 5: verify the source (door swing clearance) and the exported glb files.

  blender -b --factory-startup --python verify.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from fridge_common import BLEND, GLB_BODY, GLB_DOOR, body_objects, door_objects, tri_count  # noqa: E402


def bvh(ob, matrix):
    me = ob.data
    me.calc_loop_triangles()
    verts = [matrix @ v.co for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris)


def swing_check():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    door = bpy.data.objects["Door"]
    body = [o for o in body_objects() if o.type == "MESH"]
    body_trees = [(o.name, bvh(o, o.matrix_world)) for o in body]
    door_meshes = [o for o in door_objects() if o.type == "MESH"]
    print("SWING CHECK (door objects vs body objects, overlapping triangle pairs)")
    for ang in (0, 5, 15, 30, 45, 60, 75, 90, 100):
        door.rotation_euler = (0, 0, math.radians(-ang))
        bpy.context.view_layer.update()
        hits = []
        for d in door_meshes:
            dt = bvh(d, d.matrix_world)
            for name, bt in body_trees:
                n = len(dt.overlap(bt))
                if n:
                    hits.append(f"{d.name}x{name}:{n}")
        print(f"  {ang:3d} deg: {'clear' if not hits else ' '.join(hits)}")
    door.rotation_euler = (0, 0, 0)


def import_report(path):
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
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    imgs.append(f"{n.image.name}:{n.image.size[0]}x{n.image.size[1]}")
        print(f"  MATERIAL {m.name} images={imgs}")


def main():
    swing_check()
    import_report(GLB_BODY)
    import_report(GLB_DOOR)


if __name__ == "__main__":
    main()
