"""Generic helpers written for the nightstand and table lamp (Fable 5.1, A/B `fable-high`).

Candidates for `arcology_blender`, asset-agnostic and documented like library
code; nothing here knows the nightstand's dimensions. Where each would go:

    geo        bm_tube (tube along a polyline: cords, wire rings, spokes),
               smooth_polyline (Catmull-Rom subdivision for cord paths),
               bm_drum_shell (thin open shell of a lamp shade)
    materials  wood_veneer_layers / wood_veneer (flat-sawn grain with a
               chosen grain axis, pores, satin finish),
               brushed_metal_layers / brushed_metal (directional brushing)
    wear       cup_ring (pale water mark on a top), rubbed_finish (finish
               worn matte and lighter, e.g. around a pull)
    bake       emissive_from_albedo (tinted emissive image from a baked
               albedo, so a switchable emissive material keeps its texture)
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from arcology_blender.bake import pixels
from arcology_blender.scene import set_colorspace
from arcology_blender.shading import Graph, new_mat


# --- geometry -------------------------------------------------------------------
def smooth_polyline(points, subdiv=4):
    """Catmull-Rom subdivision of a polyline (endpoints kept). Returns Vectors."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3 or subdiv < 2:
        return pts
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(subdiv):
            t = k / subdiv
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(pts[-1])
    return out


def bm_tube(bm, points, radius, segments=8, closed=False, cap=True):
    """Round tube along a polyline (cords, wire rings, spokes), added to `bm`.

    Frames are parallel-transported along the path so the tube doesn't twist.
    `closed` joins the last point back to the first (a wire ring); open tubes
    get flat n-gon caps unless `cap` is False. Returns the new faces.
    """
    pts = [Vector(p) for p in points]
    n = len(pts)
    tangents = []
    for i in range(n):
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    t0 = tangents[0]
    ref = Vector((0.0, 0.0, 1.0)) if abs(t0.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    nrm = (ref - t0 * ref.dot(t0)).normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        binorm = t.cross(nrm)
        ring = []
        for k in range(segments):
            a = 2.0 * math.pi * k / segments
            ring.append(bm.verts.new(pts[i] + nrm * (radius * math.cos(a)) + binorm * (radius * math.sin(a))))
        rings.append(ring)
    faces = []
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(segments):
            faces.append(bm.faces.new((r0[k], r0[(k + 1) % segments], r1[(k + 1) % segments], r1[k])))
    if not closed and cap:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def bm_drum_shell(bm, r_bottom, r_top, z0, z1, thickness, segments=48):
    """Thin open shell of a (tapered) drum: outer wall, top rim, inner wall,
    bottom rim, closed and manifold, added to `bm`. Returns the faces."""
    rings = []
    for r, z in ((r_bottom, z0), (r_top, z1), (r_top - thickness, z1), (r_bottom - thickness, z0)):
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / segments),
                                    r * math.sin(2 * math.pi * k / segments), z)) for k in range(segments)])
    faces = []
    for i in range(4):
        a, b = rings[i], rings[(i + 1) % 4]
        for k in range(segments):
            faces.append(bm.faces.new((a[k], a[(k + 1) % segments], b[(k + 1) % segments], b[k])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


# --- materials --------------------------------------------------------------------
def _dot_other_axes(g, axis):
    """Sum of the two world coordinates perpendicular to `axis` (a socket):
    constant along the axis, so it drives stripes that run along it on every
    face parallel to the axis."""
    sel = [1.0, 1.0, 1.0]
    sel["XYZ".index(axis)] = 0.0
    n = g.nodes.new("ShaderNodeVectorMath")
    n.operation = "DOT_PRODUCT"
    g.links.new(g.geo.outputs["Position"], n.inputs[0])
    n.inputs[1].default_value = sel
    return n.outputs["Value"]


def _stretch(axis, across):
    s = [across] * 3
    s["XYZ".index(axis)] = 1.0
    return s


def wood_veneer_layers(g, dark, light, axis="X", rings_per_m=90.0, wobble=0.02, contrast=0.55,
                       figure=0.06, rough=0.34, pore_depth=0.0002, ring_depth=0.00004, seed=0.0):
    """Flat-sawn veneer with the grain running along world `axis`: growth
    rings as soft stripes (latewood toward `dark`, earlywood `light`,
    `rings_per_m`, wobbling by +-`wobble` m at two scales so no two rings
    run parallel), wider bands of alternating tone at a quarter of that
    frequency, a large-scale tone figure (+-`figure`), open pores stretched
    along the grain (rougher, slightly darker, `pore_depth` m deep) and a
    satin finish (`rough`). `contrast` 0..1 is how far the latewood goes
    toward `dark`. Returns (base, rough, height in m); finish with
    `g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))`.

    Grain axis per panel: X for a top or a front, Z for the sides of a
    cabinet, Y for a drawer box's sides and bottom.
    """
    n0 = g.add(_dot_other_axes(g, axis), seed)
    n = g.add(n0, g.add(g.mul(g.sub(g.noise(2.5, 2.0, 0.5), 0.5), 2.0 * wobble),
                        g.mul(g.sub(g.noise(11.0, 2.0, 0.5), 0.5), 0.3 * wobble)))
    t = g.math("FRACT", g.mul(n, rings_per_m))
    late = g.mul(g.mul(g.maprange(t, 0.25, 0.60), g.maprange(t, 1.0, 0.75)), contrast)
    base = g.mixc(late, light, dark)
    # Wider bands (a few cm) with their own wobble, and a large soft figure.
    n2 = g.add(n0, g.mul(g.sub(g.noise(1.4, 2.0, 0.5, g.vec(1.0, 1.0, 1.0)), 0.5), 5.0 * wobble))
    t2 = g.math("FRACT", g.add(g.mul(n2, rings_per_m / 4.3), 0.31))
    band = g.mul(g.maprange(t2, 0.2, 0.5), g.maprange(t2, 0.95, 0.7))
    base = g.scale_color(base, g.maprange(band, 0.0, 1.0, 1.0 + figure, 1.0 - figure))
    base = g.scale_color(base, g.maprange(g.noise(1.5, 2.0, 0.5), 0.3, 0.7, 1.0 - figure, 1.0 + figure))
    pores = g.maprange(g.noise(5.0, 3.0, 0.6, g.vec(*_stretch(axis, 40.0))), 0.52, 0.66)
    base = g.scale_color(base, g.sub(1.0, g.mul(pores, 0.20)))
    r = g.add(rough, g.add(g.mul(late, 0.05), g.mul(pores, 0.18)))
    height = g.sub(g.mul(late, ring_depth), g.mul(pores, pore_depth))
    return base, r, height


def wood_veneer(name, dark, light, axis="X", **kw):
    """`src_<name>` material from `wood_veneer_layers` with no extra wear."""
    g = Graph(new_mat(f"src_{name}"))
    base, rough, height = wood_veneer_layers(g, dark, light, axis, **kw)
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))


def brushed_metal_layers(g, color, axis="Z", rough=0.40, streak=0.12, tone=0.25):
    """Brushed metal with the brushing along world `axis`: long low-contrast
    streaks in roughness (+-`streak`), brightness (+-`tone`/2) and a very
    shallow relief. Returns (base, rough, height in m); metallic is the
    caller's (1.0 for bare metal)."""
    s = g.sub(g.noise(1.0, 2.0, 0.5, g.vec(*_stretch(axis, 80.0))), 0.5)
    base = g.scale_color(color, g.add(1.0, g.mul(s, tone)))
    r = g.add(rough, g.mul(s, streak))
    height = g.mul(s, 0.00008)
    return base, r, height


def brushed_metal(name, color, axis="Z", **kw):
    """`src_<name>` bare brushed metal (metallic 1)."""
    g = Graph(new_mat(f"src_{name}"))
    base, rough, height = brushed_metal_layers(g, color, axis, **kw)
    return g.finish(base, rough, 1.0, g.bump(height, 1.0, 1.0))


# --- wear ----------------------------------------------------------------------------
def cup_ring(g, base, rough, center, radius, width=0.005, color=(0.62, 0.58, 0.50), amount=0.55,
             rougher=0.30, broken=0.45):
    """A pale, broken water ring (a mug's tide mark) on an upward-facing
    surface at world `center` (x, y, z): a ring of `radius` and `width` m,
    `broken` 0..1 removes parts of it, blended toward `color` by `amount`
    and left rougher (the finish is hazed)."""
    cx, cy, cz = center
    d = g.add(g.dist_xy(cx, cy), g.mul(g.sub(g.noise(40.0, 2.0), 0.5), 0.003))
    ring = g.band(d, radius - width / 2, radius + width / 2, 0.0012)
    on_top = g.mul(g.band(g.z, cz - 0.003, cz + 0.003, 0.002), g.maprange(g.nz, 0.7, 0.9))
    breakup = g.maprange(g.noise(25.0, 2.0, 0.5), broken, broken + 0.25)
    fac = g.mul(g.mul(ring, on_top), breakup)
    base = g.mixc(g.mul(fac, amount), base, color)
    rough = g.add(rough, g.mul(fac, rougher))
    return base, rough


def rubbed_finish(g, base, rough, mask, lighter=0.14, rougher=0.28):
    """A finish worn through by hands inside a 0..1 mask (around a pull, a
    chair's arm): the wood shows lighter and matte, with a mottled breakup."""
    fac = g.mul(mask, g.maprange(g.noise(18.0, 3.0, 0.6), 0.35, 0.65))
    base = g.scale_color(base, g.add(1.0, g.mul(fac, lighter)))
    rough = g.add(rough, g.mul(fac, rougher))
    return base, rough


# --- bake --------------------------------------------------------------------------
def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def emissive_from_albedo(mat, albedo, tint, strength=1.0, name=None):
    """Give a baked material an emissive texture derived from its albedo
    (linear albedo times `tint`, e.g. a warm 2700 K color), so the surface
    glows with its own texture (a lamp shade's weave). `strength` becomes
    the glTF emissive strength; Godot scales it with
    `emission_energy_multiplier`. Returns the packed image."""
    name = name or albedo.name.replace("_albedo", "") + "_emissive"
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    src = pixels(albedo)
    out = np.ones_like(src)
    out[..., :3] = _linear_to_srgb(_srgb_to_linear(src[..., :3]) * np.asarray(tint, dtype=np.float32))
    img = bpy.data.images.new(name, albedo.size[0], albedo.size[1], alpha=False)
    set_colorspace(img, "sRGB")
    img.pixels.foreach_set(out.ravel())
    img.pack()
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, -600)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    return img
