"""Door swing check (variant opus-high): the door must not touch the cabinet anywhere from 0 to 100 deg,
and the fully pulled crisper drawer must clear the door at 100 deg.
blender --background blender/props/fridge__opus-high.blend --python check.py
"""
import bpy, math, os, sys
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as S


def tree(obs, mats):
    verts, polys = [], []
    for ob, M in zip(obs, mats):
        me = ob.data
        off = len(verts)
        verts += [M @ v.co for v in me.vertices]
        polys += [[off + i for i in p.vertices] for p in me.polygons]
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


D = bpy.data.objects
body = [D["FridgeCabinet"], D["FridgeLightPanel"], D["CrisperDrawer"]]
body_t = tree(body, [o.matrix_world.copy() for o in body])
door = D["FridgeDoor"]
H = Matrix.Translation((S.HINGE[0], S.HINGE[1], 0.0))
bad = []
for a in range(0, 101):
    M = H @ Matrix.Rotation(math.radians(-a), 4, "Z")
    hits = tree([door], [M]).overlap(body_t)
    if hits:
        bad.append((a, len(hits)))
print("SWEEP", "OK 0..100 deg" if not bad else f"COLLISIONS {bad[:10]}")
M100 = H @ Matrix.Rotation(math.radians(S.OPEN_DEG), 4, "Z")
dr = D["CrisperDrawer"]
Mdr = Matrix.Translation((0, -S.DRAWER_TRAVEL, 0)) @ dr.matrix_world
hits = tree([door], [M100]).overlap(tree([dr], [Mdr]))
print("DRAWER_OUT_VS_DOOR100", "OK" if not hits else f"{len(hits)} hits")
hits = tree([dr], [Mdr]).overlap(tree([D["FridgeCabinet"]], [D["FridgeCabinet"].matrix_world]))
print("DRAWER_OUT_VS_CABINET", "OK" if not hits else f"{len(hits)} hits")
vs = [M100 @ v.co for v in door.data.vertices]
print("DOOR100_BOUNDS x %.3f..%.3f y %.3f..%.3f" % (min(v.x for v in vs), max(v.x for v in vs),
                                                  min(v.y for v in vs), max(v.y for v in vs)))
