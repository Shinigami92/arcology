"""Generic helpers written for the shower that belong in blender/lib (not promoted during the
parallel bathroom run: the contract forbids changing blender/lib). Asset-agnostic; each has a
README line suggestion in its docstring's first sentence.

Suggested homes:
  geo:     drop_faces_on_plane, extrude_outline, lathe_at
  curves:  tapered_capsule_outline
  shading: object_xyz, polar, dot_grid (Graph helpers, here as functions taking the Graph)
  metal:   spun_about, braid
  wear:    water_spots, limescale
"""

import math

import bmesh
from mathutils import Matrix, Vector

from arcology_blender import curves


# --- geometry -------------------------------------------------------------------------
def drop_faces_on_plane(ob, axis, value, sign, tol=1e-4):
    """Delete faces lying on an axis plane and facing `sign` along it (faces hidden against a
    wall, floor or ceiling the shell provides). axis 0/1/2, value in object-local units.
    Returns the number of faces removed."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    kill = [f for f in bm.faces
            if all(abs(v.co[axis] - value) < tol for v in f.verts) and f.normal[axis] * sign > 0.9]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    return len(kill)


def split_planes(ob, cuts, dist=1e-6):
    """Cut a mesh into disconnected pieces (no caps) along axis planes [(axis, value), ...], so
    smart-project UV islands of long members (a 2 m channel, a glass edge, a rail) stay short and
    the atlas packs denser. Seams are invisible on baked procedural materials; flat or smooth
    round members shade the same on both sides. Returns the number of edges split."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    total = 0
    for axis, value in cuts:
        co, no = Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
        co[axis], no[axis] = value, 1.0
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=dist,
                                     plane_co=co, plane_no=no)
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        bmesh.ops.split_edges(bm, edges=edges)
        total += len(edges)
    bm.to_mesh(ob.data)
    bm.free()
    return total


def extrude_outline(bm, outline, matrix, depth):
    """Prism from a closed 2D outline [(u, v), ...] (counter-clockwise) extruded `depth` along
    the frame's +Z; `matrix` maps (u, v, w) into the bmesh (e.g. a lever plate in a wall's
    x/z plane). Returns the new vertices."""
    bot = [bm.verts.new(matrix @ Vector((u, v, 0.0))) for u, v in outline]
    top = [bm.verts.new(matrix @ Vector((u, v, depth))) for u, v in outline]
    n = len(outline)
    faces = [bm.faces.new(list(reversed(bot))), bm.faces.new(top)]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return bot + top


def lathe_at(bm, profile, matrix, segments=32, closed=False):
    """`curves.lathe` (profile [(r, z), ...] about Z) placed by `matrix`, for revolved parts on any
    axis (a knob on a wall: Matrix.Rotation(90 deg, 'X') turns +Z into -Y). Returns the vertices."""
    verts = curves.lathe(bm, profile, segments=segments, closed=closed)
    bmesh.ops.transform(bm, matrix=matrix, verts=verts)
    return verts


def tapered_capsule_outline(r0, r1, length, segments=24):
    """Closed 2D outline (counter-clockwise) of the convex hull of a circle r0 at (0, 0) and a
    circle r1 at (0, -length): a teardrop lever paddle, a tapered tab."""
    s = (r0 - r1) / length                     # sine of the tangent's tilt
    s = max(-0.99, min(0.99, s))
    phi = math.asin(s)
    pts = []
    # big circle: from the right tangent point over the top to the left one
    a0, a1 = -phi, math.pi + phi
    for i in range(segments + 1):
        a = a0 + (a1 - a0) * i / segments
        pts.append((r0 * math.cos(a), r0 * math.sin(a)))
    # small circle: from the left tangent point under the bottom to the right one
    b0, b1 = math.pi + phi, 2 * math.pi - phi
    for i in range(segments // 2 + 1):
        a = b0 + (b1 - b0) * i / (segments // 2)
        pts.append((r1 * math.cos(a), -length + r1 * math.sin(a)))
    return pts


# --- shading (Graph) ------------------------------------------------------------------------
def object_xyz(g):
    """Object-space position (x, y, z) sockets: patterns that stay put on a part whatever its
    pose (a dial's knurl, a hand shower tilted in its holder)."""
    tc = g.nodes.new("ShaderNodeTexCoord")
    sep = g.nodes.new("ShaderNodeSeparateXYZ")
    g.links.new(tc.outputs["Object"], sep.inputs[0])
    return tc.outputs["Object"], sep.outputs[0], sep.outputs[1], sep.outputs[2]


def polar(g, a, b):
    """(radius, angle in radians) of two coordinate sockets (e.g. x and z around a wall-normal
    axis); angle = atan2(a, b), so 0 points along +b."""
    r = g.math("SQRT", g.add(g.mul(a, a), g.mul(b, b)))
    return r, g.math("ARCTAN2", a, b)


def dot_grid(g, u, v, pitch, radius, soft=0.0006, u0=0.0, v0=0.0):
    """0..1 mask of round dots on a square grid (nozzles, perforations) in the u/v coordinate
    sockets, dot centers at u0 + (i + 0.5) * pitch."""
    fu = g.sub(g.math("FRACT", g.mul(g.sub(u, u0), 1.0 / pitch)), 0.5)
    fv = g.sub(g.math("FRACT", g.mul(g.sub(v, v0), 1.0 / pitch)), 0.5)
    d = g.mul(g.math("SQRT", g.add(g.mul(fu, fu), g.mul(fv, fv))), pitch)
    return g.maprange(d, radius + soft, radius - soft)


# --- metal ------------------------------------------------------------------------------------
def spun_about(g, a, b, along, rough=0.30, streak=0.06, height=0.00002):
    """Spun (circular) brushing around an arbitrary axis: `a`, `b` are the two coordinates across
    the axis (relative to it), `along` the one along it (sockets, e.g. from object_xyz).
    Returns (rough, height in m), like `metal.brushed`."""
    d = g.math("SQRT", g.add(g.mul(a, a), g.mul(b, b)))
    n = g.noise(1.0, 2.0, 0.6, vector=g.combine(g.mul(d, 900.0), g.mul(along, 900.0), 0.0))
    coarse = g.noise(8.0, 2.0)
    r = g.add(g.add(rough, g.mul(g.sub(n, 0.5), streak * 2)), g.mul(g.sub(coarse, 0.5), 0.05))
    return r, g.mul(n, height)


def braid(g, pitch=0.009, strands=6, depth=0.0003, along_attr=curves.ALONG_ATTR,
          around_attrs=curves.AROUND_ATTRS):
    """Woven braid on a `curves.tube` (metal hose, braided cable): two counter-rotating sets of
    `strands` helices, `pitch` m per turn. Returns (weave 0..1, height in m); color and roughness
    stay with the caller (`fabric.braided_cord` is the textile version)."""
    s = g.attribute(along_attr)
    ang = g.math("ARCTAN2", g.attribute(around_attrs[1]), g.attribute(around_attrs[0]))
    k = 2.0 * math.pi / pitch
    p1 = g.math("SINE", g.add(g.mul(s, k), g.mul(ang, strands)))
    p2 = g.math("SINE", g.sub(g.mul(s, k), g.mul(ang, strands)))
    # over/under: whichever helix is on top shows its crown
    weave = g.mul(g.add(g.math("MAXIMUM", p1, p2), 1.0), 0.5)
    return weave, g.mul(weave, depth)


# --- wear -------------------------------------------------------------------------------------
def water_spots(g, base, rough, mask, scale=150.0, amount=0.15, rougher=0.12,
                color=(0.30, 0.30, 0.29), vector=None):
    """Dried water spots inside a 0..1 mask: small irregular drops with a brighter mineral rim,
    slightly lighter and rougher (taps, glass fittings, a shower floor). Returns (base, rough)."""
    n = g.noise(scale, 1.0, 0.5, vector)
    sparse = g.maprange(g.noise(scale / 12.0, 2.0, 0.5, vector), 0.45, 0.65)
    rim = g.mul(g.band(n, 0.675, 0.682, 0.004), sparse)
    core = g.mul(g.maprange(n, 0.675, 0.70), sparse)
    spot = g.mul(mask, g.add(g.mul(rim, 0.8), g.mul(core, 0.25)))
    base = g.mixc(g.mul(spot, amount), base, color)
    rough = g.add(rough, g.mul(spot, rougher))
    return base, rough


def limescale(g, base, rough, mask, color=(0.55, 0.54, 0.50), amount=0.5, rougher=0.45,
              scale=40.0, vector=None):
    """Chalky limescale crust inside a 0..1 mask (drains, nozzles, the waterline), patchy at a
    medium scale. Returns (base, rough, crust 0..1) so the caller can add a little height."""
    patch = g.mul(g.maprange(g.noise(scale, 3.0, 0.6, vector), 0.48, 0.62),
                  g.maprange(g.noise(scale / 6.0, 2.0, 0.5, vector), 0.35, 0.6))
    crust = g.mul(mask, patch)
    base = g.mixc(g.mul(crust, amount), base, color)
    rough = g.add(rough, g.mul(crust, rougher))
    return base, rough, crust
