"""Silena's corset top and trousers (stage 3): shells cut from the MPFB skin, offset
and draped over it (garment.relax_shell), weighted from the skin.

- Top: a strapless corset from under the belt to the collarbones (a straight neckline cut
  by a plane), a deep V plunging from it cut with two planes; the neckline and the V's
  edges turn under (a bound edge, the violet underlayer's piping in the material). Black lace over a
  violet underlayer is the material's job (outfit_materials.py).
- Trousers: hips and legs from under the belt to inside the boots, fitted, the
  crotch bridged by the drape.

Per-vertex data for the materials (removed after baking): `region` (TOP_*/TR_*), `vd`
(distance from the V edge, m; top), `az` (azimuth around the torso / around the leg,
radians), `hz` (height, m), `ld` (leg: +1 left, -1 right, 0 hips).
"""

import math

import bmesh
from mathutils import Vector

from silena_vesper_common import TOP_HEM_Z, TROUSER_BOTTOM_Z, TROUSER_TOP_Z
from arcology_blender import garment, rig

TORSO_BONES = ("Hips", "Spine", "Chest", "UpperChest", "Neck", "LeftShoulder", "RightShoulder",
               "LeftUpperLeg", "RightUpperLeg")
LEG_BONES = ("Hips", "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg")
ARM_BONES = ("LeftUpperArm", "RightUpperArm", "LeftLowerArm", "RightLowerArm")

TOP_OFFSET = 0.0026          # lace over satin, fitted (corset)
TOP_NECK_Z = 1.505           # strapless: a straight neckline at the collarbones, the V plunging from it
V_BOTTOM = (0.0, 1.312)      # (x, z) of the V's point
V_TOP_X = 0.046              # V corners at the neck base, x (the lace shows between the V and the lapels)
V_TOP_Z = 1.585
V_TURN = 0.0022              # the V edge turns under this much
TROUSER_OFFSET = 0.0034
TROUSER_EASE_THIGH = 0.0016  # a little looser over the thighs

TOP_LACE, TOP_EDGE = 0, 1
TR_LEG = 2
ATTRS = ("region", "vd", "az", "hz", "ld")
AXIS_Y = -0.045


def smoothstep(x, a, b):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _copy_skin(skin, name, collection):
    ob = skin.copy()
    ob.data = skin.data.copy()
    ob.name = ob.data.name = name
    collection.objects.link(ob)
    for vg in [vg for vg in ob.vertex_groups if vg.name.endswith(".001")]:
        ob.vertex_groups.remove(vg)   # skin_copy's duplicate (empty) group names
    return ob


def _bone_weight(ob, names):
    ids = {vg.index for vg in ob.vertex_groups if vg.name in set(names)}
    return [sum(g.weight for g in v.groups if g.group in ids) for v in ob.data.vertices]


def _delete_where(ob, vert_pred, mode="any"):
    """Delete faces whose vertices satisfy vert_pred(index, co): mode 'any' or 'all' or
    'center' (the face center)."""
    me = ob.data
    doomed = []
    for p in me.polygons:
        if mode == "center":
            if vert_pred(-1, p.center):
                doomed.append(p.index)
            continue
        flags = [vert_pred(i, me.vertices[i].co) for i in p.vertices]
        if (any(flags) if mode == "any" else all(flags)):
            doomed.append(p.index)
    return garment.delete_faces(ob, doomed)


def _bisect(ob, co, no):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no), dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _attrs(ob):
    me = ob.data
    for a in ATTRS:
        if me.attributes.get(a) is None:
            me.attributes.new(a, "FLOAT", "POINT")
    return {a: me.attributes[a].data for a in ATTRS}


# --- V-neck geometry ------------------------------------------------------------------------
def v_planes():
    """((point, normal) left, (point, normal) right): the V's sides; inside is positive."""
    b = Vector((V_BOTTOM[0], 0.0, V_BOTTOM[1]))
    probe = Vector((0.0, 0.0, V_BOTTOM[1] + 0.1))   # inside: toward the center line above the point
    out = []
    for sx in (1.0, -1.0):
        t = Vector((sx * V_TOP_X, 0.0, V_TOP_Z))
        n = (t - b).cross(Vector((0.0, 1.0, 0.0))).normalized()
        if (probe - b).dot(n) < 0.0:
            n = -n
        out.append((b, n))
    return out


def in_v(co, margin=0.0):
    """True if a point lies inside the V opening (front of the body, above its point)."""
    if co.y > AXIS_Y or co.z < V_BOTTOM[1] - margin:
        return False
    return all((co - b).dot(n) > -margin for b, n in v_planes())


def v_distance(co):
    """Distance from the V's edge in the front view (x, z), positive outside the opening."""
    d = min((co - b).dot(n) for b, n in v_planes())
    return -d if co.z >= V_BOTTOM[1] else max(-d, V_BOTTOM[1] - co.z)


# --- top ---------------------------------------------------------------------------------------
def build_top(skin, collection):
    ob = _copy_skin(skin, "Top", collection)
    rig.extract_by_weight(ob, TORSO_BONES, 0.5)
    arm_w = _bone_weight(ob, ARM_BONES)
    _delete_where(ob, lambda i, co: arm_w[i] > 0.35, "any")
    neck_w = _bone_weight(ob, ("Neck", "Head"))
    _delete_where(ob, lambda i, co: neck_w[i] > 0.6, "all")
    for z in (TOP_HEM_Z, TOP_NECK_Z):
        _bisect(ob, (0.0, 0.0, z), (0.0, 0.0, 1.0))
    _delete_where(ob, lambda i, co: co.z < TOP_HEM_Z - 1e-4 or co.z > TOP_NECK_Z + 1e-4, "center")
    for b, n in v_planes():
        _bisect(ob, b, n)
    _bisect(ob, (0.0, 0.0, V_BOTTOM[1]), (0.0, 0.0, 1.0))
    _delete_where(ob, lambda i, co: in_v(co), "center")
    _keep_largest(ob)

    edge = _boundary_verts(ob)
    vfront = {i for i in edge if ob.data.vertices[i].co.y < AXIS_Y and ob.data.vertices[i].co.z > V_BOTTOM[1] - 0.01}
    _flatten_nipples(ob, edge)
    bvh = garment.bvh_of(ob)              # drape over the flattened body, not the raw skin
    garment.offset_shell(ob, lambda i, co, n: TOP_OFFSET)
    garment.relax_shell(ob, bvh, lambda i, co: TOP_OFFSET, iterations=10, factor=0.45, fixed=vfront)
    _turn_edge(ob, vfront, V_TURN)
    a = _attrs(ob)
    for v in ob.data.vertices:
        co = v.co
        a["vd"][v.index].value = v_distance(co)
        a["az"][v.index].value = math.atan2(co.x, -(co.y - AXIS_Y))
        a["hz"][v.index].value = co.z
        a["ld"][v.index].value = 0.0
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _flatten_nipples(ob, keep):
    """A corset doesn't show them: smooth MPFB's nipple geometry (and a ring around it) out
    of the shell before it is offset, or the offset turns it into a spike."""
    me = ob.data
    w = _bone_weight(ob, ("nipple", "nippleTip"))
    sel = {i for i, x in enumerate(w) if x > 0.0}
    for _ in range(2):
        sel |= {j for e in me.edges for j in e.vertices if (e.vertices[0] in sel or e.vertices[1] in sel)}
    sel = sorted(i for i in sel if i not in keep)
    if sel:
        garment.smooth_verts(ob, sel, factor=0.6, iterations=12)


def _keep_largest(ob):
    """Drop small disconnected islands left by the cuts (bits of shoulder, armpit)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, islands = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, isl = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        islands.append(isl)
    islands.sort(key=len, reverse=True)
    doomed = [f for isl in islands[1:] for f in isl]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _boundary_verts(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out = {v.index for e in bm.edges if e.is_boundary for v in e.verts}
    bm.free()
    return out


def _turn_edge(ob, verts, depth):
    """Turn the boundary through `verts` under (against the normals) by `depth`: a bound
    edge with visible thickness, new faces in the boundary edges' order (built by hand:
    bmesh.ops.extrude_edge_only orders its output by memory address, which made the top's
    face order, and everything measured against it, change from run to run). The new
    vertices get region TOP_EDGE."""
    me = ob.data
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    sel = {bm.verts[i] for i in verts}
    edges = [e for e in bm.edges if e.is_boundary and all(v in sel for v in e.verts)]
    under = {}
    for e in edges:
        for v in sorted(e.verts, key=lambda v: v.index):
            if v.index not in under:
                under[v.index] = bm.verts.new(v.co - v.normal * depth)
    for e in edges:
        f0 = e.link_faces[0]
        # keep the winding of the face the edge belongs to (the strip faces the same way)
        loop = next(lp for lp in f0.loops if lp.edge == e)
        a, b = loop.vert, loop.link_loop_next.vert
        bm.faces.new((b, a, under[a.index], under[b.index]))
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    reg = _attrs(ob)["region"]
    new = set(range(len(me.vertices) - len(under), len(me.vertices)))
    for v in me.vertices:
        reg[v.index].value = float(TOP_EDGE if v.index in new else TOP_LACE)


# --- trousers ----------------------------------------------------------------------------------------
def build_trousers(skin, collection):
    ob = _copy_skin(skin, "Trousers", collection)
    rig.extract_by_weight(ob, LEG_BONES, 0.5)
    arm_w = _bone_weight(ob, ARM_BONES + ("LeftHand", "RightHand"))
    _delete_where(ob, lambda i, co: arm_w[i] > 0.1, "any")
    for z in (TROUSER_BOTTOM_Z, TROUSER_TOP_Z):
        _bisect(ob, (0.0, 0.0, z), (0.0, 0.0, 1.0))
    _delete_where(ob, lambda i, co: co.z < TROUSER_BOTTOM_Z - 1e-4 or co.z > TROUSER_TOP_Z + 1e-4, "center")
    _keep_largest(ob)
    bvh = garment.bvh_of(skin)
    edge = _boundary_verts(ob)

    def ease(i, co):
        thigh = smoothstep(co.z, 0.55, 0.70) * (1.0 - smoothstep(co.z, 0.86, 0.95))
        return TROUSER_OFFSET + TROUSER_EASE_THIGH * thigh

    garment.offset_shell(ob, lambda i, co, n: ease(i, co))
    garment.relax_shell(ob, bvh, ease, iterations=14, factor=0.5, fixed=edge)
    a = _attrs(ob)
    for v in ob.data.vertices:
        co = v.co
        side = 1.0 if co.x > 0.0 else -1.0
        leg = co.z < 0.86
        a["region"][v.index].value = float(TR_LEG)
        a["hz"][v.index].value = co.z
        a["ld"][v.index].value = side if leg else 0.0
        cx = side * 0.13 if leg else 0.0
        a["az"][v.index].value = math.atan2(co.x - cx, -(co.y - AXIS_Y))
        a["vd"][v.index].value = 1.0
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


