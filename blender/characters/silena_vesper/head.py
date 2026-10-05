"""Silena's head for stage 3 (a believable silhouette for shadows; stage 4 makes it
pretty) and the visible skin of the body.

- Ears: MPFB's pointed-ear targets (CC0) plus a stretch of the upper ear up and back,
  long elf ears.
- Skin split: a copy of the MPFB skin (with the ears) is cut by a plane across the neck
  (HEAD_CUT_Z: low at the throat, high at the nape, inside the collar); above it is
  `HeadMesh` (not `Head`: glTF shares one namespace between bones and meshes), below it only what clothes don't cover stays in the body: the V-neck
  (clothes.in_v, grown under the top's edge) and the neck down to the top's neckline.
  Both halves share the cut's vertices, positions and weights, so they never part.
- Hair (`Hair`, outfit atlas): a cap offset from the scalp, a messy updo (a lumpy bun
  of overlapping lobes at the back of the crown) and loose strands framing the face.
  Rigid on Head.

Per-vertex data for the hair material (removed after baking): `region` (always
HAIR_REGION), `hs` (strand coordinate: distance along a strand or up the cap, m), `ha`
(angle around the head, radians).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from silena_vesper_common import HEAD_CUT_Z
import clothes
from arcology_blender import curves, garment, human

EAR_TARGETS = (("ear-shape-pointed", 1.0), ("ear-scale-vert-incr", 0.6), ("ear-rot-backward", 0.4))
EAR_STRETCH = 0.018          # the tip goes this much further up and back
HAIR_OFFSET = 0.008
HEAD_RATIO = 0.70            # the stage-3 decimation: still the hair's source (the hair stays as it was)
FACE_RATIO = 0.62            # stage 4: the head decimated harder away from the eyes ...
EYE_KEEP = 0.030             # ... and not at all within this distance of an eyeball's center (lids, blink)
HAIR_REGION = 7
HAIR_ATTRS = ("region", "hs", "ha")


def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def add_ears(body):
    """Load the elf-ear targets onto the MPFB body (new shape keys)."""
    svc = human.mpfb()
    for side in ("l", "r"):
        for name, w in EAR_TARGETS:
            svc.TargetService.load_target(body, human.target_path(f"ears/{side}-{name}"), weight=w)


def stretch_ears(ob):
    """Pull the upper ear up and back into a longer point (falloff from mid ear to tip)."""
    vg = ob.vertex_groups["ears"]
    me = ob.data
    pts = {}
    for v in me.vertices:
        w = next((g.weight for g in v.groups if g.group == vg.index), 0.0)
        if w > 0.0:
            pts[v.index] = w
    for side in (1.0, -1.0):
        idx = [i for i in pts if me.vertices[i].co.x * side > 0.0]
        zs = np.array([me.vertices[i].co.z for i in idx])
        z0, z1 = np.percentile(zs, 45), zs.max()
        d = Vector((side * 0.25, 0.55, 1.0)).normalized()
        for i in idx:
            v = me.vertices[i]
            f = float(smoothstep(v.co.z, z0, z1)) ** 1.6 * pts[i]
            v.co += d * EAR_STRETCH * f
    me.update()


def split_skin(body, collection, eye_centers=()):
    """(Head, SkinV, HairSource): the skin with ears, cut across the neck; SkinV keeps only
    what the clothes leave visible. The head keeps full resolution within EYE_KEEP of the
    `eye_centers` (stage 4) and is decimated to FACE_RATIO elsewhere; HairSource is the
    stage-3 head (HEAD_RATIO everywhere), which the hair is built from, so it stays the
    same. The caller removes HairSource after the hair is built."""
    ob = garment.skin_copy(body, "HeadMesh", collection)
    for vg in [vg for vg in ob.vertex_groups if vg.name.endswith(".001")]:
        ob.vertex_groups.remove(vg)
    stretch_ears(ob)
    # plane through the two cut heights
    a = Vector((0.0, -0.085, HEAD_CUT_Z[0]))
    b = Vector((0.0, 0.025, HEAD_CUT_Z[1]))
    n = (b - a).cross(Vector((1.0, 0.0, 0.0))).normalized()
    if n.z < 0.0:
        n = -n
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=a, plane_no=n, dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    low = ob.copy()
    low.data = ob.data.copy()
    low.name = low.data.name = "SkinV"
    collection.objects.link(low)

    def above(co):
        return (co - a).dot(n) > 1e-6

    me = ob.data
    garment.delete_faces(ob, [p.index for p in me.polygons if not above(Vector(p.center))])
    hair_src = ob.copy()
    hair_src.data = ob.data.copy()
    hair_src.name = hair_src.data.name = "HairSource"
    collection.objects.link(hair_src)
    decimate(hair_src, HEAD_RATIO)
    eyes = [Vector(c) for c in eye_centers]
    decimate(ob, FACE_RATIO if eyes else HEAD_RATIO,
             keep=(lambda co: any((co - c).length < EYE_KEEP for c in eyes)) if eyes else None)
    me = low.data
    keep = []
    for p in me.polygons:
        c = Vector(p.center)
        if above(c):
            continue
        neck = c.z > 1.49 and abs(c.x) < 0.09 and c.y < 0.03   # the neck's base, down to the coat's neckline
        if neck or clothes.in_v(c, margin=0.016):
            keep.append(p.index)
    keep = set(keep)
    garment.delete_faces(low, [p.index for p in me.polygons if p.index not in keep])
    _keep_island_with(low, Vector((0.0, -0.06, 1.45)))
    return ob, low, hair_src


def decimate(ob, ratio, keep=None):
    """Collapse-decimate a mesh, its open boundary (the neck seam) untouched: Decimate's
    vertex group says how much a vertex may collapse, so the seam gets 0 (and so does
    every vertex for which `keep(co)` is true)."""
    import bmesh as _bm

    bm = _bm.new()
    bm.from_mesh(ob.data)
    seam = {v.index for v in bm.verts if v.is_boundary or (keep is not None and keep(v.co))}
    bm.free()
    vg = ob.vertex_groups.new(name="_decimate")
    vg.add([i for i in range(len(ob.data.vertices)) if i not in seam], 1.0, "REPLACE")
    mod = ob.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.vertex_group = vg.name
    mod.vertex_group_factor = 1.0
    mod.use_collapse_triangulate = False
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.vertex_groups.remove(ob.vertex_groups["_decimate"])


def _keep_island_with(ob, point):
    """Keep only the connected part nearest `point` (drops stray skin bits)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    start = min(bm.faces, key=lambda f: (f.calc_center_median() - point).length)
    seen, stack = {start}, [start]
    while stack:
        f = stack.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g not in seen:
                    seen.add(g)
                    stack.append(g)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in seen], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# --- hair ----------------------------------------------------------------------------------------
def build_hair(head, collection):
    """Cap over the scalp, a messy bun, loose strands. Returns the object."""
    me = head.data
    scalp = head.vertex_groups.get("scalp")
    sc = {v.index for v in me.vertices if scalp and any(g.group == scalp.index and g.weight > 0.3 for g in v.groups)}
    bm = bmesh.new()
    L = {a: bm.verts.layers.float.new(a) for a in HAIR_ATTRS}
    # cap: scalp faces (plus a hairline margin), offset and relaxed in a temporary object
    cap = head.copy()
    cap.data = head.data.copy()
    bpy.context.scene.collection.objects.link(cap)
    garment.delete_faces(cap, [p.index for p in cap.data.polygons
                               if not all(i in sc for i in p.vertices) or p.center.z < 1.71])
    hbvh = garment.bvh_of(head)
    garment.offset_shell(cap, lambda i, co, n: HAIR_OFFSET + 0.008 * float(smoothstep(co.z, 1.80, 1.90)))
    garment.relax_shell(cap, hbvh, lambda i, co: HAIR_OFFSET * 0.8, iterations=6, factor=0.4)
    tmp = bmesh.new()
    tmp.from_mesh(cap.data)
    cd = cap.data
    bpy.data.objects.remove(cap)
    bpy.data.meshes.remove(cd)
    _merge(bm, L, tmp, lambda co: (co.z - 1.70, math.atan2(co.x, co.y)))
    # bun: overlapping lumpy lobes at the back of the crown, a messy updo
    rng = np.random.default_rng(7)
    center = Vector((0.0, 0.055, 1.875))
    for k, (off, r) in enumerate((((0.0, 0.0, 0.0), 0.046), ((0.026, -0.004, 0.016), 0.030),
                                  ((-0.026, 0.006, 0.010), 0.031), ((0.004, 0.020, -0.018), 0.030))):
        lobe = bmesh.new()
        prof = [(r * math.sin(a), -r * math.cos(a)) for a in np.linspace(0.0, math.pi, 7)]
        prof[0] = (0.0, prof[0][1])
        prof[-1] = (0.0, prof[-1][1])
        curves.lathe(lobe, prof, segments=12)
        for v in lobe.verts:
            n = v.co.normalized() if v.co.length > 0 else Vector((0.0, 0.0, 1.0))
            bump = 0.18 * math.sin(5.0 * n.x + 3.0 * n.z + k) * math.cos(4.0 * n.y + 2.0 * k)
            v.co = v.co * (1.0 + bump * 0.35) * Vector((1.0, 0.85, 0.9))
        m = Matrix.Translation(center + Vector(off)) @ Matrix.Rotation(rng.uniform(-0.6, 0.6), 4, "Y")
        bmesh.ops.transform(lobe, matrix=m, verts=lobe.verts)
        _merge(bm, L, lobe, lambda co: (0.3 + (co - center).length, math.atan2(co.x, co.y)))
    # loose strands framing the face and falling at the nape
    strands = (
        [(0.060, -0.075, 1.86), (0.072, -0.088, 1.80), (0.070, -0.090, 1.74), (0.062, -0.080, 1.69)],
        [(-0.058, -0.078, 1.865), (-0.071, -0.090, 1.79), (-0.069, -0.088, 1.73), (-0.058, -0.075, 1.685)],
        [(0.030, -0.095, 1.885), (0.050, -0.105, 1.83), (0.060, -0.100, 1.78)],
        [(0.040, 0.075, 1.80), (0.045, 0.090, 1.74), (0.040, 0.085, 1.68)],
        [(-0.035, 0.080, 1.80), (-0.044, 0.092, 1.73), (-0.036, 0.086, 1.665)],
    )
    for k, pts in enumerate(strands):
        path = curves.catmull_rom([Vector(p) for p in pts], samples=3)
        n = len(path)
        scales = [(1.0 - 0.75 * (i / (n - 1)) ** 1.4, 1.0 - 0.6 * (i / (n - 1))) for i in range(n)]
        sb = bmesh.new()
        prof = [(0.0075 * math.cos(a), 0.0024 * math.sin(a)) for a in np.linspace(0.0, 2.0 * math.pi, 6)[:-1]]
        out = (Vector(pts[0]) - Vector((0.0, 0.0, 1.78))).normalized()
        curves.sweep(sb, path, prof, up=out, scales=scales)
        start = Vector(pts[0])
        _merge(bm, L, sb, lambda co, s=start: (1.0 + (co - s).length, 0.0))
    bm.normal_update()
    me = bpy.data.meshes.new("Hair")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Hair", me)
    collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    garment.set_weights(ob, [{"Head": 1.0} for _ in me.vertices])
    return ob


def _merge(bm, L, part, coords):
    vmap = {}
    for v in part.verts:
        w = bm.verts.new(v.co)
        w[L["region"]] = float(HAIR_REGION)
        w[L["hs"]], w[L["ha"]] = coords(v.co)
        vmap[v] = w
    for f in part.faces:
        try:
            bm.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            pass
    part.free()
