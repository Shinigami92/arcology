"""Clothing over MPFB skin (D-037): static skin copies, offset shells, tubes lofted
around a limb (cuffs, sleeves), weight transfer from the skin and rigid regions.

A garment worn over the skin is its own mesh: a shell offset from the skin (or a
loft sampled from it), weighted by transfer from the skin it covers, then
cleaned up (`rigid_blend` keeps stiff parts like cuffs on one bone). The
hidden skin underneath is deleted (`rig.extract_by_weight`, face deletion) so
it can't poke through.

Limb coordinates: a `LimbFrame` sits on a joint (e.g. the wrist) with `axis`
pointing up the limb (toward the elbow); `t` is the distance along the axis,
`theta` the angle around it from `ref` toward `lat` (radians).
"""

import math
from dataclasses import dataclass

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


# --- skin copies -------------------------------------------------------------------
def skin_copy(body, name, collection=None):
    """Static copy of an MPFB body: shape keys mixed in, no modifiers, no parent,
    world coordinates with an identity transform, vertex groups kept (the source
    of cut-out parts and weight transfers). The armature's pose doesn't matter:
    the copy is the rest shape."""
    saved = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in saved:
        m.show_viewport = False
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, dtype=np.float32)
    ev.data.vertices.foreach_get("co", co)
    for m, show in saved:
        m.show_viewport = show
    me = body.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if me.shape_keys is not None:
        ob.shape_key_clear()
    me.vertices.foreach_set("co", co)
    me.update()
    me.transform(body.matrix_world)  # world coordinates, identity transform
    for vg in body.vertex_groups:
        ob.vertex_groups.new(name=vg.name)
    return ob


def bvh_of(ob, faces=None):
    """World-space BVH of a mesh object (optionally only the polygon indices `faces`)."""
    mw = ob.matrix_world
    verts = [mw @ v.co for v in ob.data.vertices]
    polys = [list(p.vertices) for p in ob.data.polygons if faces is None or p.index in faces]
    return BVHTree.FromPolygons(verts, polys)


# --- limb frames and lofted tubes ------------------------------------------------------
@dataclass
class LimbFrame:
    origin: Vector   # joint position (world)
    axis: Vector     # unit, up the limb
    ref: Vector      # unit, perpendicular to axis: theta = 0
    lat: Vector      # unit, axis x ref: theta = 90 degrees

    def point(self, t, theta, r):
        return (self.origin + self.axis * t
                + (self.ref * math.cos(theta) + self.lat * math.sin(theta)) * r)

    def coords(self, p):
        """(t, theta, r) of a world point."""
        d = Vector(p) - self.origin
        t = d.dot(self.axis)
        x, y = d.dot(self.ref), d.dot(self.lat)
        return t, math.atan2(y, x), math.hypot(x, y)


def limb_frame(origin, axis, ref):
    """LimbFrame from a joint, a direction up the limb and a reference direction
    (projected perpendicular to the axis), e.g. the back of the hand."""
    axis = Vector(axis).normalized()
    ref = Vector(ref)
    ref = (ref - axis * ref.dot(axis)).normalized()
    return LimbFrame(Vector(origin), axis, ref, axis.cross(ref).normalized())


def ring_radii(bvh, frame, t, thetas, max_r=0.25, fallback=None):
    """Skin radius around the limb at `t` for each angle: a ray from the axis
    outward, the farthest hit within max_r (rays from an off-center bone can
    cross the surface twice in concave spots). Misses use `fallback` or the
    mean of the hits."""
    out = []
    for th in thetas:
        o = frame.origin + frame.axis * t
        d = (frame.ref * math.cos(th) + frame.lat * math.sin(th)).normalized()
        best, start, r0 = None, o, 0.0
        for _ in range(4):
            hit = bvh.ray_cast(start, d, max_r - r0)
            if hit[0] is None:
                break
            best = (hit[0] - o).dot(d)
            r0 = best + 1e-5
            start = o + d * r0
        out.append(best)
    hits = [r for r in out if r is not None]
    mean = sum(hits) / len(hits) if hits else (fallback or 0.03)
    return [r if r is not None else (fallback or mean) for r in out]


class PathFrames:
    """Rotation-minimizing frames along a polyline (a limb's centerline through a bent
    joint: wrist, elbow fillet, shoulder): `frame(t)` is a `LimbFrame` at arc length `t`
    from the first point whose `axis` is the path's tangent and whose `ref` is
    parallel-transported from `ref` at the start, so rings lofted across the path
    (`frame(t).point(0, theta, r)`) don't twist. Beyond the ends the path continues
    straight. `theta(t, direction)` is the angle of a world direction around the path."""

    def __init__(self, points, ref, step=0.001):
        pts = [Vector(p) for p in points]
        seg = [(b - a).length for a, b in zip(pts, pts[1:])]
        self.length = sum(seg)
        n = max(2, int(math.ceil(self.length / step)) + 1)
        self.step = self.length / (n - 1)
        acc = [0.0]
        for s in seg:
            acc.append(acc[-1] + s)
        self.points = []
        i = 0
        for k in range(n):
            t = min(k * self.step, self.length)
            while i < len(seg) - 1 and acc[i + 1] < t:
                i += 1
            f = 0.0 if seg[i] <= 0.0 else (t - acc[i]) / seg[i]
            self.points.append(pts[i].lerp(pts[i + 1], max(0.0, min(1.0, f))))
        self.tangents = []
        for k in range(n):
            a, b = self.points[max(k - 1, 0)], self.points[min(k + 1, n - 1)]
            self.tangents.append((b - a).normalized())
        r = Vector(ref)
        r = (r - self.tangents[0] * r.dot(self.tangents[0])).normalized()
        self.refs = [r]
        for k in range(1, n):
            q = self.tangents[k - 1].rotation_difference(self.tangents[k])
            r = q @ self.refs[-1]
            r = (r - self.tangents[k] * r.dot(self.tangents[k])).normalized()
            self.refs.append(r)

    def frame(self, t):
        n = len(self.points)
        if t <= 0.0 or t >= self.length:
            k = 0 if t <= 0.0 else n - 1
            o = self.points[k] + self.tangents[k] * (t if t <= 0.0 else t - self.length)
            return limb_frame(o, self.tangents[k], self.refs[k])
        x = t / self.step
        k = min(int(x), n - 2)
        f = x - k
        axis = self.tangents[k].lerp(self.tangents[k + 1], f).normalized()
        return limb_frame(self.points[k].lerp(self.points[k + 1], f), axis,
                          self.refs[k].lerp(self.refs[k + 1], f))

    def theta(self, t, direction):
        fr = self.frame(t)
        d = Vector(direction)
        return math.atan2(d.dot(fr.lat), d.dot(fr.ref))


def loft(bm, rings, closed=True, cap_start=False, cap_end=False):
    """Quads between consecutive rings of points (each ring a list of the same
    length). `closed` joins each ring's last point to its first. Caps are
    triangle fans to the ring's centroid, wound consistently with the quads.
    Returns (vertex rings, cap center vertices, all new faces)."""
    vrings = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(rings[0])
    span = n if closed else n - 1
    faces = []
    for a, b in zip(vrings, vrings[1:]):
        for i in range(span):
            j = (i + 1) % n
            faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    centers = []
    for ring, start, use in ((vrings[0], True, cap_start), (vrings[-1], False, cap_end)):
        if not use:
            continue
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        centers.append(c)
        for i in range(span):
            j = (i + 1) % n
            faces.append(bm.faces.new((ring[j], ring[i], c) if start else (ring[i], ring[j], c)))
    return vrings, centers, faces


def orient(bm, faces, probe, outward):
    """Flip all `faces` (one consistently wound surface, e.g. from `loft`) if the
    `probe` face's normal points against `outward`. Returns True if flipped."""
    probe.normal_update()
    if probe.normal.dot(Vector(outward)) >= 0.0:
        return False
    bmesh.ops.reverse_faces(bm, faces=faces)
    for f in faces:
        f.normal_update()
    return True


# --- shells ------------------------------------------------------------------------------
def offset_shell(ob, distance):
    """Push every vertex along its (smooth) normal by `distance(index, co, normal)` meters
    (local coordinates). Returns the moved count."""
    me = ob.data
    me.update()
    cos = [v.co.copy() for v in me.vertices]
    nrm = [v.normal.copy() for v in me.vertices]
    for i, v in enumerate(me.vertices):
        v.co = cos[i] + nrm[i] * distance(i, cos[i], nrm[i])
    me.update()
    return len(cos)


def smooth_verts(ob, indices, factor=0.5, iterations=4, preserve_volume=False):
    """Laplacian-style smoothing of some vertices toward their neighbors' mean
    (removes skin details such as nail rims under a glove)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    sel = [bm.verts[i] for i in indices]
    for _ in range(iterations):
        if preserve_volume:
            bmesh.ops.smooth_laplacian_vert(bm, verts=sel, lambda_factor=factor, lambda_border=0.0,
                                            use_x=True, use_y=True, use_z=True, preserve_volume=True)
        else:
            bmesh.ops.smooth_vert(bm, verts=sel, factor=factor, use_axis_x=True, use_axis_y=True,
                                  use_axis_z=True)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# --- weights ------------------------------------------------------------------------------
def transfer_weights(src, dst, groups=None):
    """Copy vertex-group weights from `src` (the skin) to `dst` (the garment):
    Data Transfer, nearest face interpolated, applied (replaces dst's weights
    in those groups). `groups` limits it to those names (default: all of src's).
    Returns the group names transferred."""
    keep = [vg.name for vg in src.vertex_groups if groups is None or vg.name in set(groups)]
    created = []
    for vg in src.vertex_groups:  # the modifier only writes into existing groups
        if dst.vertex_groups.get(vg.name) is None:
            dst.vertex_groups.new(name=vg.name)
            created.append(vg.name)
    mod = dst.modifiers.new("WeightTransfer", "DATA_TRANSFER")
    mod.object = src
    mod.use_object_transform = True
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    mod.layers_vgroup_select_src = "ALL"
    mod.layers_vgroup_select_dst = "NAME"
    mod.mix_mode = "REPLACE"
    mod.mix_factor = 1.0
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    with bpy.context.temp_override(object=dst, active_object=dst, selected_objects=[dst]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for name in created:
        if name not in keep:
            dst.vertex_groups.remove(dst.vertex_groups[name])
    return keep


def weights_of(ob):
    """Per-vertex dict {group name: weight}."""
    names = {vg.index: vg.name for vg in ob.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 0.0} for v in ob.data.vertices]


def set_weights(ob, weights):
    """Replace all vertex-group weights with a per-vertex list of {name: weight}."""
    vgs = ob.vertex_groups
    for vg in list(vgs):
        vg.remove(list(range(len(ob.data.vertices))))
    for i, wd in enumerate(weights):
        for name, w in wd.items():
            if w <= 0.0:
                continue
            vg = vgs.get(name) or vgs.new(name=name)
            vg.add([i], w, "REPLACE")


def split_weights(weights, src, dst, factor):
    """Move `factor[i]` (0..1) of each vertex's `src` weight to `dst`: the distal forearm's
    LowerArm weight goes to a twist bone (`rig.add_twist_bone`) by how close the vertex is
    to the wrist, so a sleeve and the cuff under it share one blend. Returns new dicts."""
    out = []
    for wd, f in zip(weights, factor):
        nd = dict(wd)
        w = nd.get(src, 0.0)
        if f > 0.0 and w > 0.0:
            nd[dst] = nd.get(dst, 0.0) + w * f
            if f >= 1.0:
                del nd[src]
            else:
                nd[src] = w * (1.0 - f)
        out.append(nd)
    return out


def rigid_blend(weights, bone, factor):
    """Blend per-vertex weight dicts toward `bone` = 1 by factor[i] (0 keeps the
    vertex as is, 1 makes it rigid on the bone): stiff cuffs, buckles, collars."""
    out = []
    for wd, f in zip(weights, factor):
        if f <= 0.0:
            out.append(dict(wd))
            continue
        total = sum(wd.values()) or 1.0
        nd = {k: v / total * (1.0 - f) for k, v in wd.items()}
        nd[bone] = nd.get(bone, 0.0) + f
        out.append(nd)
    return out


def smooth_weights(ob, indices, groups, iterations=6, factor=0.5):
    """Diffuse the weights of `groups` over the vertices `indices` (each step mixes a
    vertex with the mean of its edge neighbors by `factor`), then renormalize those
    groups to their previous per-vertex total. Softens hard transitions at joints
    (knuckles, the thumb's base) so linear blend skinning keeps more volume."""
    me = ob.data
    n = len(me.vertices)
    names = [g for g in groups if ob.vertex_groups.get(g) is not None]
    col = {ob.vertex_groups[g].index: i for i, g in enumerate(names)}
    w = np.zeros((n, len(names)))
    for v in me.vertices:
        for g in v.groups:
            if g.group in col:
                w[v.index, col[g.group]] = g.weight
    total = w.sum(axis=1)
    edges = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    deg = np.bincount(edges.ravel(), minlength=n).astype(float)
    sel = np.zeros(n, dtype=bool)
    sel[list(indices)] = True
    for _ in range(iterations):
        acc = np.zeros_like(w)
        np.add.at(acc, edges[:, 0], w[edges[:, 1]])
        np.add.at(acc, edges[:, 1], w[edges[:, 0]])
        mean = acc / np.maximum(deg, 1.0)[:, None]
        w[sel] = (1.0 - factor) * w[sel] + factor * mean[sel]
    s = w.sum(axis=1)
    w = np.where(s[:, None] > 1e-9, w * (total / np.maximum(s, 1e-9))[:, None], w)
    for i, name in enumerate(names):
        vg = ob.vertex_groups[name]
        for vi in np.nonzero(sel)[0]:
            if w[vi, i] > 1e-5:
                vg.add([int(vi)], float(w[vi, i]), "REPLACE")
            else:
                vg.remove([int(vi)])


# --- whole-body garments (coat, top, trousers, boots) --------------------------------------
class WeightSampler:
    """Vertex-group weights of a mesh (the skin) at arbitrary world points: the nearest
    point on its surface, the weights interpolated barycentrically in that triangle
    (what Data Transfer's "nearest face interpolated" does, but per point and in plain
    Python, so two garments evaluated at the same point get identical weights: a sleeve's
    armhole and the coat body sewn to it). `groups` limits the groups read; results are
    normalized dicts {group: weight}."""

    def __init__(self, src, groups=None):
        me = src.data
        mw = src.matrix_world
        me.calc_loop_triangles()
        self.verts = [mw @ v.co for v in me.vertices]
        self.tris = [tuple(t.vertices) for t in me.loop_triangles]
        self.bvh = BVHTree.FromPolygons(self.verts, self.tris, all_triangles=True)
        keep = None if groups is None else set(groups)
        names = {vg.index: vg.name for vg in src.vertex_groups if keep is None or vg.name in keep}
        self.w = [{names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 0.0}
                  for v in me.vertices]

    def at(self, point):
        from mathutils.geometry import barycentric_transform

        loc, _, idx, _ = self.bvh.find_nearest(Vector(point))
        a, b, c = self.tris[idx]
        bary = barycentric_transform(loc, self.verts[a], self.verts[b], self.verts[c],
                                     Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)))
        out = {}
        for vi, f in zip((a, b, c), bary):
            f = min(max(f, 0.0), 1.0)
            for k, w in self.w[vi].items():
                out[k] = out.get(k, 0.0) + w * f
        total = sum(out.values())
        return {k: w / total for k, w in out.items()} if total > 0.0 else out


def limit_dict(weights, limit=4, epsilon=1e-4):
    """A weight dict's `limit` largest entries above `epsilon`, normalized (the rule of
    rig.limit_weights for weights still held in Python)."""
    kept = sorted(((w, k) for k, w in weights.items() if w > epsilon), reverse=True)[:limit]
    total = sum(w for w, _ in kept) or 1.0
    return {k: w / total for w, k in kept}


def relax_shell(ob, bvh, clearance, iterations=12, factor=0.5, fixed=None):
    """Drape a shell (a garment offset from the skin) like fabric: each iteration moves
    every free vertex toward the mean of its edge neighbors by `factor` (bridging concave
    skin: the cleavage, the small of the back, between the legs), then pushes it back out
    of the skin `bvh` until it is at least `clearance(i, co)` meters outside along the
    skin's normal at the nearest point. `fixed`: vertex indices that don't move. Works in
    the object's local coordinates (build the BVH in the same space)."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    edges = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    deg = np.bincount(edges.ravel(), minlength=n).astype(float)
    free = np.ones(n, dtype=bool)
    if fixed is not None:
        free[list(fixed)] = False
    need = [clearance(i, Vector(co[i])) for i in range(n)]
    for _ in range(iterations):
        acc = np.zeros_like(co)
        np.add.at(acc, edges[:, 0], co[edges[:, 1]])
        np.add.at(acc, edges[:, 1], co[edges[:, 0]])
        mean = acc / np.maximum(deg, 1.0)[:, None]
        co[free] = (1.0 - factor) * co[free] + factor * mean[free]
        for i in np.nonzero(free)[0]:
            p = Vector(co[i])
            loc, nrm, _, _ = bvh.find_nearest(p)
            if loc is None:
                continue
            d = (p - loc).dot(nrm)
            if d < need[i]:
                co[i] = loc + nrm * need[i]
    me.vertices.foreach_set("co", co.ravel())
    me.update()


def boundary_loop(verts):
    """Order bmesh vertices that form one closed boundary loop (e.g. the edge of a hole cut
    into a surface) by walking their boundary edges from verts[0] (pass a list in a
    deterministic order). Returns the ordered list."""
    pool = set(verts)
    start = verts[0]                  # (not next(iter(pool)): sets of bmesh elements iterate by address)
    loop, prev, cur = [start], None, start
    while True:
        nxt = [e.other_vert(cur) for e in cur.link_edges if e.is_boundary and e.other_vert(cur) in pool
               and e.other_vert(cur) is not prev]
        if not nxt or nxt[0] is start:
            break
        prev, cur = cur, nxt[0]
        loop.append(cur)
        if len(loop) > len(pool):
            break
    return loop


def zip_loops(bm, loop_a, loop_b, center, axis):
    """Bridge two closed, ordered vertex loops around a common `axis` through `center` (an
    armhole cut into a coat body and a band around the sleeve's seam ring) with
    triangles, also when their vertex counts differ: loop_b is turned to wind the same
    way around the axis as loop_a and to start at the vertex nearest loop_a[0], then both
    are merged by their share of arc length. The strip is wound consistently; flip it
    with `orient` if needed. Returns the new faces."""
    axis = Vector(axis).normalized()
    c = Vector(center)

    def winding(loop):
        s = 0.0
        for v, w in zip(loop, loop[1:] + loop[:1]):
            s += (v.co - c).cross(w.co - c).dot(axis)
        return s

    a = list(loop_a)
    b = list(loop_b)
    if (winding(a) > 0.0) != (winding(b) > 0.0):
        b = b[::-1]
    k = min(range(len(b)), key=lambda i: (b[i].co - a[0].co).length_squared)
    b = b[k:] + b[:k]

    def shares(loop):
        acc = [0.0]
        for v, w in zip(loop, loop[1:] + loop[:1]):
            acc.append(acc[-1] + (w.co - v.co).length)
        return [x / acc[-1] for x in acc]

    sa, sb = shares(a), shares(b)
    a, b = a + [a[0]], b + [b[0]]
    faces = []
    i = j = 0
    while i < len(a) - 1 or j < len(b) - 1:
        if j >= len(b) - 1 or (i < len(a) - 1 and sa[i + 1] <= sb[j + 1]):
            tri = (a[i], a[i + 1], b[j])
            i += 1
        else:
            tri = (a[i], b[j + 1], b[j])
            j += 1
        if len(set(tri)) == 3 and bm.faces.get(tri) is None:
            faces.append(bm.faces.new(tri))
    return faces


def delete_faces(ob, faces):
    """Delete faces by index (and the vertices left without faces). Returns the count."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    doomed = [bm.faces[i] for i in sorted(set(faces))]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(doomed)
