"""Generic helpers written for the spires that belong in blender/lib once promoted
(artists don't change blender/lib during parallel work). Asset-agnostic.

- offset_polygon(pts, d)            convex CCW polygon with every edge moved inward by d (recesses, insets)
- scale_polygon(pts, s, center)     uniform scale about a center (tapers keep side faces planar)
- polygon_area(pts)                 signed area (> 0 = counter-clockwise)
- textured_material(name, albedo, orm=None, normal=None, emission=None, strength=1.0)
                                    Principled material from images laid out for the glTF exporter;
                                    unlike bake.final_material, ORM, normal and emission are optional
- whole_steps(rng, n, step)         a random offset in whole grid steps (UV offsets that keep a
                                    tiling pattern aligned with real geometry: floors, bays)
"""

import bpy
from mathutils import Vector


def polygon_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i][0], pts[i][1]
        x1, y1 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def offset_polygon(pts, d):
    """Convex counter-clockwise polygon (x, y) with every edge moved inward by d
    (outward for d < 0); vertices are the intersections of neighboring edges."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = Vector(pts[i][:2]), Vector(pts[(i + 1) % n][:2])
        t = (b - a).normalized()
        inward = Vector((-t.y, t.x))
        lines.append((a + inward * d, t))
    out = []
    for i in range(n):
        p0, t0 = lines[i - 1]
        p1, t1 = lines[i]
        den = t0.x * t1.y - t0.y * t1.x
        if abs(den) < 1e-9:
            out.append(tuple(p1))
            continue
        s = ((p1.x - p0.x) * t1.y - (p1.y - p0.y) * t1.x) / den
        q = p0 + t0 * s
        out.append((q.x, q.y))
    return out


def scale_polygon(pts, s, center=(0.0, 0.0)):
    cx, cy = center
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in pts]


def whole_steps(rng, n, step):
    """rng.randrange(n) * step: an offset in whole cells."""
    return rng.randrange(max(1, n)) * step


def textured_material(name, albedo, orm=None, normal=None, emission=None, strength=1.0,
                      rough=0.5, metal=0.0):
    """Principled material wired the way the glTF exporter reads it: albedo -> Base
    Color, ORM (R occlusion via the glTF Settings group, G roughness, B metallic),
    normal map, emission image * strength (KHR_materials_emissive_strength when > 1).
    Missing images fall back to the constant rough / metal. Reuses a material of
    that name (its nodes are replaced)."""
    from arcology_blender.bake import _gltf_occlusion_group
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = albedo
    ta.location = (-400, 300)
    nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if orm is not None:
        to = nt.nodes.new("ShaderNodeTexImage")
        to.image = orm
        to.location = (-400, 0)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-100, 0)
        nt.links.new(to.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = _gltf_occlusion_group()
        grp.location = (300, -500)
        nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    if normal is not None:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = normal
        tn.location = (-400, -300)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-100, -300)
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if emission is not None:
        te = nt.nodes.new("ShaderNodeTexImage")
        te.image = emission
        te.location = (-400, -600)
        nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = strength
    return m
