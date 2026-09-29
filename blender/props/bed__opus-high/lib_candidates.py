"""Generic helpers written for the bed (A/B opus-high), candidates for blender/lib (D-028).

Asset-agnostic; nothing here knows the bed's dimensions. Suggested homes
when promoted:

    cloth_grid, cloth_settle, thicken      -> soft (or a new `cloth` module)
    flatten_against                        -> soft
    wood_veneer, brushed_metal             -> materials (as Graph layers, like fabric)
    unwrap_weighted, bake_part_weighted    -> bake

Cloth workflow (draped bedding, throws, table cloths, curtains):

    bm = cloth_grid(width, length, spacing, place)   # flat sheet mapped into a start pose
    ob = geo.new_object(name, bm, coll, material=m)
    cloth_settle(ob, [(mattress, 0.03), (frame, 0.03)], frames=70, bending=3.0)
    thicken(ob, 0.03, keep_under_attr=..., drop_front_attr=...)

The simulated surface is the cloth's *front* (top) face; `thicken` grows the
thickness behind it, so collider distances equal the cloth thickness.
"""

import math

import bmesh
import bpy
from mathutils import Vector, noise

from arcology_blender import bake
from arcology_blender.soft import FAR, SEAM_ATTR

U_ATTR = "cloth_u"
S_ATTR = "cloth_s"


# --- Cloth -----------------------------------------------------------------------
def cloth_grid(width, length, spacing, place, seam_attr=SEAM_ATTR, corner_radius=0.0):
    """Rectangular cloth as a new bmesh of quads, mapped into a start pose.

    The flat sheet has coordinates u in [-width/2, width/2] (across) and
    s in [0, length] (along). `place(u, s)` returns the world position of
    that point in the start pose (e.g. flat above a bed, or with a fold);
    keep it isometric-ish so the simulation starts near rest. Faces are
    oriented so that for place(u, s) = (u, s, z) the front faces +Z.

    Every vertex gets float attributes `cloth_u` and `cloth_s` (flat
    coordinates, for masks after the simulation) and `seam_attr`: the flat
    distance to the nearest hem (clamped to soft.FAR), which `fabric.welt`
    turns into a hem or piping in the material.

    corner_radius > 0 rounds the four corners of the flat pattern (the grid
    is squeezed onto the arcs, no ragged edges). A slightly rounded pattern
    lets corners that hang over a box edge drop like the sides instead of
    flaring out into a cone.
    """
    rc = min(corner_radius, width / 2, length / 2)

    def pattern(u, s):
        """(u, s) on the rounded pattern and the flat distance to its hem."""
        cu, cs = width / 2 - rc, length / 2 - rc
        du, ds = abs(u) - cu, abs(s - length / 2) - cs
        if rc > 0 and du > 0 and ds > 0:
            m = max(du, ds)
            k = m / math.hypot(du, ds)
            du, ds = du * k, ds * k
            u2 = math.copysign(cu + du, u)
            s2 = length / 2 + math.copysign(cs + ds, s - length / 2)
            return u2, s2, rc - math.hypot(du, ds)
        return u, s, min(width / 2 - abs(u), s, length - s)

    nu = max(1, int(round(width / spacing)))
    ns = max(1, int(round(length / spacing)))
    bm = bmesh.new()
    lu = bm.verts.layers.float.new(U_ATTR)
    ls = bm.verts.layers.float.new(S_ATTR)
    lseam = bm.verts.layers.float.new(seam_attr)
    grid = []
    for i in range(nu + 1):
        u0 = -width / 2 + width * i / nu
        row = []
        for j in range(ns + 1):
            u2, s2, hem = pattern(u0, length * j / ns)
            v = bm.verts.new(place(u2, s2))
            v[lu] = u2
            v[ls] = s2
            v[lseam] = min(FAR, max(0.0, hem))
            row.append(v)
        grid.append(row)
    for i in range(nu):
        for j in range(ns):
            bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    bm.normal_update()
    return bm


def fold_path(y0, z0, fold_y, radius):
    """Profile along s for a sheet lying flat from y = y0 (s = 0) toward +Y at
    height z0, turned down at `fold_y` over a half circle of `radius`, and
    lying back toward -Y on top of itself. Returns f(s, fold_y=fold_y) ->
    (y, z, layer) with layer 0 below, 1 on the arc, 2 on top."""
    def f(s, fy=fold_y):
        s1 = fy - y0
        if s <= s1:
            return y0 + s, z0, 0
        a = (s - s1) / radius
        if a <= math.pi:
            return fy + radius * math.sin(a), z0 + radius * (1.0 - math.cos(a)), 1
        return fy - (s - s1 - math.pi * radius), z0 + 2.0 * radius, 2
    return f


def cloth_settle(ob, colliders, frames=60, quality=6, mass=0.3, tension=15.0, compression=15.0,
                 shear=5.0, bending=0.5, air_damping=1.0, friction=5.0, distance=0.004,
                 collision_quality=3, self_collision=False, self_distance=0.004, self_friction=5.0,
                 shrink=0.0, shrink_attr=None, shrink_max=0.0):
    """Drop a cloth object onto colliders with Blender's cloth solver and apply
    the result (the object keeps its topology and attributes).

    colliders: [(object, distance)] or [(object, distance, friction)]:
    distance is the collider's outer
    thickness, i.e. how far the simulated (front) surface rests from it;
    use the cloth thickness so `thicken` fills the gap. Collision modifiers
    are removed again afterwards. Stiffer `bending` gives broad folds (thick
    duvets, felt); low values give fine wrinkles (sheets, silk).
    shrink < 0 makes the cloth that much larger than its start mesh (e.g.
    -0.03 = 3 %), so it buckles into soft wrinkles as it settles: the easy
    way to get a rumpled, lived-in drape. Uniform expansion mostly slides
    off into the hanging parts, so for wrinkles in one place (where someone
    slept) give shrink_attr, a 0..1 float vertex attribute: the factor goes
    from `shrink` (at 0) to `shrink_max` (at 1, e.g. -0.10), and the local
    excess buckles in place (Blender can't expand at both ends: with
    shrink_max < shrink, `shrink` is clamped to >= 0). Deterministic for the
    same inputs.
    Returns the object.
    """
    scene = bpy.context.scene
    added = []
    for entry in colliders:
        col, dist = entry[0], entry[1]
        mod = col.modifiers.new("ClothCollision", "COLLISION")
        col.collision.thickness_outer = dist
        col.collision.thickness_inner = 0.02
        col.collision.cloth_friction = entry[2] if len(entry) > 2 else friction
        col.collision.damping = 0.5
        added.append((col, mod))
    mod = ob.modifiers.new("Cloth", "CLOTH")
    st = mod.settings
    st.quality = quality
    st.mass = mass
    st.air_damping = air_damping
    st.tension_stiffness = tension
    st.compression_stiffness = compression
    st.shear_stiffness = shear
    st.bending_stiffness = bending
    st.shrink_min = shrink
    if shrink_attr:
        # Blender clamps shrink_max to >= 0 and interpolates
        # factor = 1 - shrink_min + (shrink_min - shrink_max) * weight, so
        # local expansion needs the weights inverted: weight 0 = shrink_max.
        lo_f, hi_f = min(shrink, shrink_max), max(shrink, shrink_max)
        invert = shrink_max < shrink
        vg = ob.vertex_groups.get("_shrink") or ob.vertex_groups.new(name="_shrink")
        for i, d in enumerate(ob.data.attributes[shrink_attr].data):
            w = max(0.0, min(1.0, d.value))
            vg.add([i], 1.0 - w if invert else w, "REPLACE")
        st.shrink_min = lo_f if invert else shrink
        st.shrink_max = max(0.0, hi_f if invert else shrink_max)
        st.vertex_group_shrink = "_shrink"
    cs = mod.collision_settings
    cs.collision_quality = collision_quality
    cs.distance_min = distance
    cs.use_self_collision = self_collision
    cs.self_distance_min = self_distance
    cs.self_friction = self_friction
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames
    scene.frame_start, scene.frame_end = 1, frames
    for f in range(1, frames + 1):
        scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name
    for col, m in added:
        col.modifiers.remove(m)
    if "_shrink" in ob.vertex_groups:
        ob.vertex_groups.remove(ob.vertex_groups["_shrink"])
    scene.frame_set(1)
    return ob


def thicken(ob, thickness, keep_under_attr=None, drop_front_attr=None, taper_attr=None, taper_min=0.3):
    """Give a simulated cloth its thickness behind the front surface
    (Solidify with a rim), then drop hidden faces to save triangles.

    keep_under_attr: float vertex attribute; the back (shell) face is kept
    only where it is >= 0.5 on all its vertices (e.g. near hems and in a
    turned-down fold, where the back shows); elsewhere the back lies on the
    mattress and is deleted. None keeps the whole back.
    drop_front_attr: float vertex attribute; front faces whose vertices all
    have it >= 0.5 are deleted (e.g. the part of a fold lying face down).
    The rim is always kept. Attributes are copied to the shell by Solidify.
    taper_attr: float vertex attribute 0..1 scaling the thickness from
    taper_min (at 0) to 1 (e.g. a duvet thins out toward its hem seam).
    """
    ob.vertex_groups.new(name="_shell")
    mod = ob.modifiers.new("Thicken", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = -1.0
    mod.use_even_offset = False
    mod.thickness_clamp = 1.0  # no spikes in sharp wrinkles
    mod.use_quality_normals = True
    mod.use_rim = True
    mod.shell_vertex_group = "_shell"
    if taper_attr:
        vg = ob.vertex_groups.new(name="_taper")
        vals = [d.value for d in ob.data.attributes[taper_attr].data]
        for i, w in enumerate(vals):
            vg.add([i], max(0.0, min(1.0, w)), "REPLACE")
        mod.vertex_group = "_taper"
        mod.thickness_vertex_group = taper_min
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name
    gi = ob.vertex_groups["_shell"].index

    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.verify()
    keep = bm.verts.layers.float.get(keep_under_attr) if keep_under_attr else None
    drop = bm.verts.layers.float.get(drop_front_attr) if drop_front_attr else None

    def in_shell(v):
        return v[dl].get(gi, 0.0) > 0.5

    kill = []
    for f in bm.faces:
        shell = [in_shell(v) for v in f.verts]
        if all(shell):
            if keep is not None and not all(v[keep] >= 0.5 for v in f.verts):
                kill.append(f)
        elif not any(shell):
            if drop is not None and all(v[drop] >= 0.5 for v in f.verts):
                kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    for name in ("_shell", "_taper"):
        if name in ob.vertex_groups:
            ob.vertex_groups.remove(ob.vertex_groups[name])
    return ob


def set_float_attr(ob, name, fn):
    """Write a float point attribute from fn(vertex world position, attrs dict)
    where attrs holds the vertex's existing float attributes by name."""
    me = ob.data
    names = [a.name for a in me.attributes if a.domain == "POINT" and a.data_type == "FLOAT"]
    vals = {n: [d.value for d in me.attributes[n].data] for n in names}
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    mw = ob.matrix_world
    for i, v in enumerate(me.vertices):
        a.data[i].value = fn(mw @ v.co, {n: vals[n][i] for n in names})


def soft_bounds(objs, lo=(None, None, None), hi=(None, None, None), knee=0.015):
    """Keep simulated cloth inside a footprint without a hard edge: world
    coordinates beyond `hi[i] - knee` (or below `lo[i] + knee`) are
    compressed with a tanh so they approach but never pass the bound. The
    map is monotonic, so layers that didn't intersect (duvet, throw on top)
    still don't: apply it to all of them at once, after the last simulation.
    None skips that side of that axis."""
    for ob in objs:
        mw = ob.matrix_world
        inv = mw.inverted()
        for v in ob.data.vertices:
            p = mw @ v.co
            for i in range(3):
                if hi[i] is not None and p[i] > hi[i] - knee:
                    a = hi[i] - knee
                    p[i] = a + knee * math.tanh((p[i] - a) / knee)
                if lo[i] is not None and p[i] < lo[i] + knee:
                    a = lo[i] + knee
                    p[i] = a - knee * math.tanh((a - p[i]) / knee)
            v.co = inv @ p
        ob.data.update()


# --- Soft contact ----------------------------------------------------------------
def flatten_against(bm, point, normal, falloff=0.02, region=None):
    """Squash a soft object against a plane (a pillow on a mattress or against
    a headboard): vertices closer than `falloff` to the plane, or behind it,
    are pushed out so their signed distance becomes falloff * exp(d/falloff - 1)
    (smooth: untouched beyond `falloff`, a flat contact patch where the
    object pressed through). region(v.co) -> bool limits it to some vertices."""
    p, n = Vector(point), Vector(normal).normalized()
    for v in bm.verts:
        if region is not None and not region(v.co):
            continue
        d = (v.co - p).dot(n)
        if d < falloff:
            v.co += n * (falloff * math.exp(d / falloff - 1.0) - d)
    bm.normal_update()


def bumps(x, y, amount, scale, seed=0.0):
    """Non-negative low-frequency height (0..amount) for rumpled start poses."""
    return amount * max(0.0, noise.noise(Vector((x * scale + seed * 3.7, y * scale - seed * 1.3, seed))) + 0.15) / 1.15


# --- Material layers ---------------------------------------------------------------
def wood_veneer(g, across, figure_vec, dark, mid, light, lines_per_m=22.0, figure=3.0, rough=0.40,
                pore_vec=None, streak_vec=None, line_contrast=0.55):
    """Sliced-veneer wood (walnut, oak) for `Graph`: meandering growth lines
    of varying strength, finer secondary lines, color streaks along the
    grain, broad variation between flitches, and pores.

    across: socket, a world coordinate across the grain in meters (e.g. world
    z on vertical faces with horizontal grain); figure_vec: vector socket
    (e.g. g.vec(0.9, 0.9, 3.5)) for the low-frequency noise that makes the
    lines meander (low values along the grain); streak_vec: vector stretched
    along the grain for the color streaks (defaults to figure_vec); pore_vec:
    vector stretched along the grain for the pores (defaults to figure_vec).
    Medium scale by default (lines every ~4.5 cm, low contrast pores) so it
    survives mipmapping without shimmer. rough is a satin lacquer.
    Returns (base, rough, height in m)."""
    fig = g.noise(1.0, 3.0, 0.55, vector=figure_vec)
    t = g.add(g.mul(across, lines_per_m), g.mul(fig, figure))
    tri = g.math("ABSOLUTE", g.sub(g.mul(g.math("FRACT", t), 2.0), 1.0))
    # line strength varies along the grain, so lines fade in and out
    strength = g.maprange(g.noise(2.3, 2.0, 0.5, vector=figure_vec), 0.30, 0.70, 0.35, 1.0)
    late = g.mul(g.maprange(tri, 0.55, 0.98), strength)
    t2 = g.add(g.mul(across, lines_per_m * 3.3), g.mul(fig, figure * 2.1))
    tri2 = g.math("ABSOLUTE", g.sub(g.mul(g.math("FRACT", t2), 2.0), 1.0))
    fine = g.maprange(tri2, 0.72, 0.98)
    sv = streak_vec if streak_vec is not None else figure_vec
    streak = g.maprange(g.noise(1.0, 3.0, 0.6, vector=sv), 0.25, 0.75)
    broad = g.maprange(g.noise(1.0, 2.0, 0.5, vector=g.vec(1.2, 1.2, 1.2)), 0.30, 0.70)
    base = g.mixc(g.mul(g.add(streak, broad), 0.5), mid, light)
    base = g.mixc(g.add(g.mul(late, line_contrast), g.mul(fine, 0.18)), base, dark)
    pv = pore_vec if pore_vec is not None else figure_vec
    pores = g.maprange(g.noise(90.0, 2.0, 0.5, vector=pv), 0.63, 0.72)
    base = g.scale_color(base, g.sub(1.0, g.mul(pores, 0.22)))
    r = g.add(rough, g.add(g.mul(late, 0.04), g.mul(pores, 0.10)))
    r = g.add(r, g.mul(g.sub(g.noise(6.0, 2.0), 0.5), 0.06))
    height = g.sub(0.0, g.add(g.mul(late, 0.00004), g.mul(pores, 0.00010)))
    return base, r, height


def brushed_metal(g, base, rough, brush_vec, streak=0.07, height=0.00002):
    """Brushed finish for `Graph`: roughness and slight color streaks along
    the brush direction. brush_vec stretches the position so the noise is
    long along the brushing (e.g. g.vec(3, 150, 150) brushes along X).
    Returns (base, rough, height in m)."""
    n = g.noise(1.0, 3.0, 0.6, vector=brush_vec)
    s = g.sub(n, 0.5)
    rough = g.add(rough, g.mul(s, 2 * streak))
    base = g.scale_color(base, g.add(1.0, g.mul(s, 0.25)))
    return base, rough, g.mul(n, height)


# --- UV texel weighting and baking --------------------------------------------------
def _islands(bm, uv):
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    bm.faces.index_update()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        m1 = {l.vert: l[uv].uv for l in f1.loops}
        m2 = {l.vert: l[uv].uv for l in f2.loops}
        if all((m1[v] - m2[v]).length < 1e-5 for v in e.verts):
            a, b = find(f1.index), find(f2.index)
            if a != b:
                parent[a] = b
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return list(groups.values())


def unwrap_weighted(objs, weight, angle_limit=66.0, island_margin=0.002, pack_margin=0.004):
    """Like bake.uv_unwrap, but islands get a relative texel density:
    weight(ob, face_center_world, face_normal_world) -> factor (1 = normal,
    0.2 for faces that are barely visible, like the underside of a bed).
    An island takes the largest weight among its faces."""
    bake.select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=island_margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for ob in objs:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for isl in _islands(bm, uv):
            w = max(weight(ob, mw @ f.calc_center_median(), (nm @ f.normal).normalized()) for f in isl)
            if abs(w - 1.0) < 1e-6:
                continue
            loops = [l for f in isl for l in f.loops]
            c = sum((l[uv].uv for l in loops), Vector((0.0, 0.0))) / len(loops)
            for l in loops:
                l[uv].uv = c + (l[uv].uv - c) * w
        bm.to_mesh(ob.data)
        bm.free()
    bake.select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=pack_margin,
                            scale=True, merge_overlap=False, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_part_weighted(objs, prefix, material_name, weight, hide=(), size=2048):
    """bake.bake_part with unwrap_weighted instead of bake.uv_unwrap."""
    targets = bake.bakeable(objs)
    print(f"BAKE {prefix}: {[o.name for o in targets]}")
    unwrap_weighted(targets, weight)
    for ob in hide:
        ob.hide_render = True
    albedo, normal, orm = bake.bake_atlas(targets, prefix, size)
    mat = bake.final_material(material_name, albedo, normal, orm)
    bake.assign_single(targets, mat)
    for ob in hide:
        ob.hide_render = False
    return mat
