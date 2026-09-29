"""Generic helpers written for the nightstand A/B (opus-high), candidates for blender/lib (D-028).

Nothing here knows the nightstand's dimensions. Suggested homes when promoted:

    geo      set_point_attr, bm_lathe, smooth_path, bm_tube
    shading  combine (Graph extension), bevel_edges
    wear     convex_edges, cup_ring
    materials wood_veneer, brushed_metal, braided_cord (as layers returning
             (base, rough, height) so assets add their own wear on top)
    bake     bake_part_emissive (an extra emission atlas for switchable lights)
"""

import math

import bmesh
import bpy
from mathutils import Vector

from arcology_blender import bake

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def set_point_attr(ob, name, value):
    """Constant float point attribute on a mesh object (e.g. a per-panel grain
    frame the material reads with `Graph.attribute`). Survives `geo.join`.
    Remove it before export with `geo.remove_attribute`."""
    me = ob.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", [float(value)] * len(me.vertices))
    return a


def bm_lathe(bm, profile, segments=32, center=(0.0, 0.0, 0.0), closed=False, attrs=None,
             start_angle=0.0):
    """Revolve a profile about the Z axis through `center` (a surface of revolution).

    profile: [(r, z), ...] in order; points with r == 0 become single pole
    vertices (caps). The surface faces outward when the profile runs bottom
    to top on the outside (counter-clockwise in the r/z plane); normals are
    recalculated anyway. closed: also connect the last profile point to the
    first (a closed cross-section such as a lamp shade with rolled rims).
    attrs: {name: [value per profile point]} written as float point
    attributes (e.g. a per-region emission factor).
    Returns the new vertices.
    """
    c = Vector(center)
    layers = {k: bm.verts.layers.float.get(k) or bm.verts.layers.float.new(k) for k in (attrs or {})}
    rings = []
    new = []
    for i, (r, z) in enumerate(profile):
        if r < 1e-7:
            ring = [bm.verts.new(c + Vector((0.0, 0.0, z)))]
        else:
            ring = []
            for s in range(segments):
                a = start_angle + 2.0 * math.pi * s / segments
                ring.append(bm.verts.new(c + Vector((r * math.cos(a), r * math.sin(a), z))))
        for v in ring:
            for k, layer in layers.items():
                v[layer] = attrs[k][i]
        rings.append(ring)
        new += ring
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    faces = []
    for a, b in pairs:
        if len(a) == 1 and len(b) == 1:
            continue
        for s in range(segments):
            t = (s + 1) % segments
            if len(a) == 1:
                faces.append(bm.faces.new((a[0], b[s], b[t])))
            elif len(b) == 1:
                faces.append(bm.faces.new((a[s], b[0], a[t])))
            else:
                faces.append(bm.faces.new((a[s], a[t], b[t], b[s])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return new


def smooth_path(points, samples=6):
    """Catmull-Rom curve through `points` (3-tuples), `samples` steps per span.
    Returns a list of Vectors including both end points."""
    p = [Vector(q) for q in points]
    if len(p) < 3:
        return p
    ext = [p[0] * 2 - p[1]] + p + [p[-1] * 2 - p[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-1])
    return out


def bm_tube(bm, path, radius, segments=8, caps=True, along_attr="along", around_attrs=("around_c", "around_s")):
    """Sweep a circle along a polyline (cables, cords, pipes, wire spokes).

    Frames use parallel transport, so the tube doesn't twist. Writes float
    point attributes: `along_attr` (arc length in meters from the start) and
    the cosine/sine of the angle around the tube (`around_attrs`), which
    interpolate without a seam; a material recovers the angle with ARCTAN2
    for braids or stripes (`braided_cord`). Pass None to skip them.
    Returns the new vertices.
    """
    path = [Vector(p) for p in path]
    n = len(path)
    tangents = []
    for i in range(n):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    t0 = tangents[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    normal = t0.cross(ref).normalized()
    la = lc = ls = None
    if along_attr:
        la = bm.verts.layers.float.get(along_attr) or bm.verts.layers.float.new(along_attr)
    if around_attrs:
        lc = bm.verts.layers.float.get(around_attrs[0]) or bm.verts.layers.float.new(around_attrs[0])
        ls = bm.verts.layers.float.get(around_attrs[1]) or bm.verts.layers.float.new(around_attrs[1])
    rings = []
    new = []
    dist = 0.0
    for i in range(n):
        t = tangents[i]
        if i > 0:
            dist += (path[i] - path[i - 1]).length
            # parallel transport: remove the tangent component and renormalize
            normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal)
        ring = []
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            v = bm.verts.new(path[i] + (normal * math.cos(a) + binormal * math.sin(a)) * radius)
            if la is not None:
                v[la] = dist
            if lc is not None:
                v[lc] = math.cos(a)
                v[ls] = math.sin(a)
            ring.append(v)
        rings.append(ring)
        new += ring
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for s in range(segments):
            t = (s + 1) % segments
            faces.append(bm.faces.new((a[s], a[t], b[t], b[s])))
    if caps:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return new


# ---------------------------------------------------------------------------
# Shading helpers (Graph extensions)
# ---------------------------------------------------------------------------


def combine(g, x, y, z):
    """Vector socket from three floats/sockets (e.g. a remapped coordinate frame)."""
    n = g.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        g._set(n.inputs[i], v)
    return n.outputs[0]


def vscale(g, vector, sx, sy, sz, offset=(0.0, 0.0, 0.0)):
    """vector * (sx, sy, sz) + offset (constants)."""
    m = g.nodes.new("ShaderNodeVectorMath")
    m.operation = "MULTIPLY_ADD"
    g.links.new(vector, m.inputs[0])
    m.inputs[1].default_value = (sx, sy, sz)
    m.inputs[2].default_value = offset
    return m.outputs[0]


def noise_at(g, vector, detail=2.0, rough=0.5):
    """Noise Fac at an arbitrary vector (scale 1; scale the vector instead)."""
    return g.noise(1.0, detail, rough, vector=vector)


def bevel_edges(g, radius=0.003, lo=0.03, hi=0.25, samples=16):
    """0..1 mask on geometric edges (convex and concave) from Cycles' Bevel node:
    1 - dot(rounded normal, shading normal), remapped lo..hi. Works on sparse
    box geometry where pointiness only gives face-wide gradients. Raytraced,
    so it bakes (slightly noisy at 1 sample; keep lo/hi soft)."""
    bev = g.nodes.new("ShaderNodeBevel")
    bev.samples = samples
    bev.inputs["Radius"].default_value = radius
    dot = g.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    g.links.new(bev.outputs["Normal"], dot.inputs[0])
    g.links.new(g.geo.outputs["Normal"], dot.inputs[1])
    return g.maprange(g.sub(1.0, dot.outputs["Value"]), lo, hi)


def convex_edges(g, radius=0.003, lo=0.03, hi=0.25, ao_distance=0.01, samples=16):
    """`bevel_edges` restricted to convex edges (outer corners that wear):
    concave corners are rejected by a short-range local AO test."""
    ao = g.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = samples
    ao.only_local = True
    ao.inputs["Distance"].default_value = ao_distance
    open_ = g.maprange(ao.outputs["AO"], 0.75, 0.95)
    return g.mul(bevel_edges(g, radius, lo, hi, samples), open_)


# ---------------------------------------------------------------------------
# Material layers
# ---------------------------------------------------------------------------


def grain_frame(g, u_attr="grain_u", b_attr="grain_b", seed_attr="grain_seed"):
    """World coordinates remapped into a per-part wood frame.

    Mesh attributes pick the axes: `u_attr` = index (0/1/2 = x/y/z) of the
    axis the grain runs along, `b_attr` = index of the axis through the
    board's thickness; the remaining axis is `a` (across the grain on the
    face). `seed_attr` offsets the pattern per board. Returns (u, a, b, seed).
    """
    ua, ba, seed = g.attribute(u_attr), g.attribute(b_attr), g.attribute(seed_attr)

    def pick(idx_sock):
        m0 = g.maprange(idx_sock, 0.5, 0.4, smooth=False)
        m1 = g.band(idx_sock, 0.9, 1.1, 0.05)
        m2 = g.maprange(idx_sock, 1.5, 1.6, smooth=False)
        return g.add(g.add(g.mul(g.x, m0), g.mul(g.y, m1)), g.mul(g.z, m2))

    u, b = pick(ua), pick(ba)
    a = g.sub(g.sub(g.add(g.add(g.x, g.y), g.z), u), b)
    return u, a, b, seed


def set_grain(ob, u, b, seed, a0, b0):
    """Store a board's grain frame for `wood_veneer` (see `grain_frame`):
    u/b axis indices, a per-board seed, and the log axis position (a0, b0)
    in world meters on the board's a and b axes (put a0 near the middle of
    the face, b0 a few cm behind the face that matters most)."""
    for name, v in (("grain_u", u), ("grain_b", b), ("grain_seed", seed), ("grain_a0", a0), ("grain_b0", b0)):
        set_point_attr(ob, name, v)


def wood_veneer(g, mid, dark, light, ring_spacing=0.0065, tilt=(0.04, 0.06), wander=0.012,
                figure=0.0035, streak=0.5, late_amount=0.32, pores=0.30, rough=0.44,
                u_attr="grain_u", b_attr="grain_b", seed_attr="grain_seed",
                a0_attr="grain_a0", b0_attr="grain_b0"):
    """Flat-sawn hardwood veneer under a satin finish (walnut, oak, ...).

    Grain follows the per-board frame from `grain_frame`; `set_grain` stores
    it, including the log axis (a0, b0) the growth rings circle. The axis is
    tilted against the board (`tilt` = da/du, db/du) and wanders
    (`wander`, m), so faces show cathedral arches around a0 and long,
    tightening stripes toward the edges, like a real flat-sawn leaf. Rings
    are wavy (`figure`, m); latewood darkens toward `dark` (`late_amount`),
    `streak` mixes long lighter/darker streaks (light <-> mid <-> dark),
    `pores` adds fine low-contrast flecks along the grain. Features are mm to
    cm and low contrast (VR shimmer). Returns (base, rough, height in m).
    """
    u, a, b, seed = grain_frame(g, u_attr, b_attr, seed_attr)
    a0, b0 = g.attribute(a0_attr), g.attribute(b0_attr)
    so = g.mul(seed, 3.7)
    frame = combine(g, g.add(u, so), a, b)
    slow = g.sub(noise_at(g, vscale(g, frame, 2.2, 2.2, 2.2), 2.0, 0.5), 0.5)
    a0 = g.add(g.add(a0, g.mul(u, tilt[0])), g.mul(slow, wander))
    b0 = g.add(b0, g.mul(u, tilt[1]))
    wob = g.mul(g.sub(noise_at(g, vscale(g, frame, 2.0, 14.0, 14.0), 3.0, 0.55), 0.5), figure)
    wig = g.mul(g.sub(noise_at(g, vscale(g, frame, 9.0, 90.0, 90.0), 2.0, 0.5), 0.5), figure * 0.25)
    da, db = g.sub(a, a0), g.sub(b, b0)
    r = g.add(g.add(g.math("SQRT", g.add(g.mul(da, da), g.mul(db, db))), wob), wig)
    t = g.math("FRACT", g.math("DIVIDE", r, ring_spacing))
    late = g.band(t, 0.64, 0.90, 0.08)
    # long streaks and broad mottling (along the grain)
    st = noise_at(g, vscale(g, frame, 1.1, 22.0, 22.0), 3.0, 0.6)
    mot = noise_at(g, vscale(g, frame, 0.6, 4.0, 4.0), 2.0, 0.5)
    base = g.mixc(g.maprange(st, 0.28, 0.62), light, mid)
    base = g.mixc(g.mul(streak, g.maprange(st, 0.55, 0.78)), base, dark)
    base = g.scale_color(base, g.add(0.85, g.mul(mot, 0.30)))
    base = g.mixc(g.mul(late, late_amount), base, dark)
    pore = g.maprange(noise_at(g, vscale(g, frame, 25.0, 480.0, 480.0), 1.0, 0.5), 0.62, 0.74)
    base = g.scale_color(base, g.sub(1.0, g.mul(pore, pores)))
    r_out = g.add(g.add(rough, g.mul(pore, 0.10)), g.sub(g.mul(mot, 0.06), g.mul(late, 0.03)))
    height = g.sub(0.0, g.add(g.mul(pore, 0.00012), g.mul(late, 0.00005)))
    return base, r_out, height


def brushed_metal(g, rough=0.32, axis="Z", center=None, streak=0.07, height=0.00002):
    """Brushed finish: fine roughness streaks along a world axis ("X", "Y",
    "Z"), or circular (spun) around a vertical axis through `center` (x, y).
    Returns (rough, height in meters)."""
    if center is not None:
        d = g.dist_xy(center[0], center[1])
        v = combine(g, g.mul(d, 900.0), g.mul(g.z, 900.0), 0.0)
        n = noise_at(g, v, 2.0, 0.6)
    else:
        s = {"X": (3.0, 700.0, 700.0), "Y": (700.0, 3.0, 700.0), "Z": (700.0, 700.0, 3.0)}[axis]
        n = g.noise(1.0, 2.0, 0.6, vector=g.vec(*s))
    coarse = g.noise(8.0, 2.0)
    r = g.add(g.add(rough, g.mul(g.sub(n, 0.5), streak * 2)), g.mul(g.sub(coarse, 0.5), 0.06))
    return r, g.mul(n, height)


def braided_cord(g, color, pitch=0.007, strands=4, depth=0.00025, contrast=0.18,
                 along_attr="along", around_attrs=("around_c", "around_s")):
    """Textile braid on a `bm_tube` (reads its along/around attributes): two
    counter-rotating sets of `strands` helices with `pitch` meters per turn.
    Returns (base, rough, height in meters)."""
    s = g.attribute(along_attr)
    ang = g.math("ARCTAN2", g.attribute(around_attrs[1]), g.attribute(around_attrs[0]))
    k = 2.0 * math.pi / pitch
    p1 = g.math("SINE", g.add(g.mul(s, k), g.mul(ang, strands)))
    p2 = g.math("SINE", g.sub(g.mul(s, k), g.mul(ang, strands)))
    weave = g.mul(g.add(g.mul(p1, p2), 1.0), 0.5)
    fuzz = g.noise(400.0, 2.0)
    base = g.scale_color(color, g.add(1.0 - contrast, g.mul(weave, 2 * contrast)))
    rough = g.add(0.78, g.mul(g.sub(fuzz, 0.5), 0.1))
    return base, rough, g.mul(weave, depth)


def cup_ring(g, base, rough, center, radius, width=0.0025, z_band=(0.0, 10.0), strength=0.35,
             haze=(0.16, 0.13, 0.105), duller=0.22, broken=0.5, second=(0.011, -0.006, 0.6)):
    """Water/coffee ring left by a mug on a finished top: a thin, broken ring
    (upward-facing faces at world z within z_band) where the finish turned
    hazy (lighter, grayer) and dull. `second` = (dx, dy, fraction): a fainter
    offset ring from another time. Returns (base, rough)."""
    cx, cy = center[0], center[1]
    up = g.mul(g.maprange(g.nz, 0.8, 0.95), g.band(g.z, z_band[0], z_band[1], 0.002))

    def ring(x, y, amount):
        d = g.add(g.dist_xy(x, y), g.mul(g.sub(g.noise(35.0, 2.0), 0.5), width * 1.2))
        rim = g.band(d, radius - width, radius, width * 0.5)
        inner = g.mul(g.maprange(d, radius, radius * 0.85), 0.12)
        gaps = g.maprange(g.noise(18.0, 2.0), 0.35 * broken, 0.35 * broken + 0.2)
        return g.mul(g.add(g.mul(rim, gaps), inner), amount)

    m = g.mul(up, g.math("MAXIMUM", ring(cx, cy, 1.0), ring(cx + second[0], cy + second[1], second[2])))
    base = g.mixc(g.mul(m, strength), base, haze)
    rough = g.add(rough, g.mul(m, duller))
    return base, rough


# ---------------------------------------------------------------------------
# Bake
# ---------------------------------------------------------------------------


def bake_part_emissive(objs, prefix, material_name, strength, hide=(), size=1024):
    """`bake.bake_part` plus an emission atlas (<prefix>_emission, sRGB).

    The src_ materials' "Emission Color" input (a color pattern: a lamp
    shade's glow, a lit bulb) is baked into its own image and linked to the
    final material's Emission Color with `strength`, so the glTF exporter
    writes emissiveTexture (+ KHR_materials_emissive_strength). Godot can
    switch the light by the material's emission energy.
    """
    targets = bake.bakeable(objs)
    print(f"BAKE {prefix} (emissive): {[o.name for o in targets]}")
    bake.uv_unwrap(targets)
    for ob in hide:
        ob.hide_render = True
    albedo, normal, orm = bake.bake_atlas(targets, prefix, size)
    mats = bake.src_materials(targets)
    emission = bake.new_image(f"{prefix}_emission", size, "sRGB")
    bake.set_bake_target(mats, emission)
    with bake.EmitOverride(mats, "Emission Color"):
        bake.bake(targets, "EMIT")
    emission.pack()
    mat = bake.final_material(material_name, albedo, normal, orm)
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    te = nt.nodes.new("ShaderNodeTexImage")
    te.image = emission
    te.location = (-400, -600)
    nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    bake.assign_single(targets, mat)
    for ob in hide:
        ob.hide_render = False
    return mat
