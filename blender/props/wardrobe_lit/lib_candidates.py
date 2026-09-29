"""Generic helpers from the wardrobe A/B (opus-high), candidates for blender/lib/arcology_blender.

Nothing here knows the wardrobe's dimensions; each function would slot into
the named library module unchanged:

    geo      sweep, circle_profile, rounded_rect_profile, arc_points, smooth_path,
             tapered_square_leg
    shading  combine, wood_veneer, brushed_metal, bump_finish   (layer style, like fabric.fabric_base)
    wear     bevel_edges, scratch_xz, edge_wear, masked_scuffs
    bake     Spread, instance

Layer functions follow the `fabric` convention: they take and return
(base, rough, height) with height in meters, and `bump_finish` turns the
accumulated height into one normal (Bump distance 1.0), so each layer's depth
is physical. World-position masks come from `Graph` (g.x, g.y, g.z, g.nx...).
"""

import math

import bmesh
from mathutils import Matrix, Vector


# =============================================================================
# geo: swept tubes and bars
# =============================================================================
def circle_profile(radius, segments=8):
    """Closed 2D profile (list of (u, v)) for a round tube, counter-clockwise."""
    return [(radius * math.cos(2 * math.pi * i / segments), radius * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]


def rounded_rect_profile(width, height, radius, corner_segments=2):
    """Closed 2D profile of a rounded rectangle (u: width, v: height), counter-clockwise."""
    r = min(radius, 0.499 * min(width, height))
    hw, hh = width / 2 - r, height / 2 - r
    pts = []
    for cx, cy, a0 in ((hw, hh, 0.0), (-hw, hh, 90.0), (-hw, -hh, 180.0), (hw, -hh, 270.0)):
        for k in range(corner_segments + 1):
            a = math.radians(a0 + 90.0 * k / corner_segments)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def arc_points(center, radius, a0, a1, n, u_axis=(0.0, 1.0, 0.0), v_axis=(0.0, 0.0, 1.0)):
    """n + 1 points on a circular arc from angle a0 to a1 (degrees) in the plane
    spanned by u_axis (0 deg) and v_axis (90 deg) around `center`."""
    c, u, v = Vector(center), Vector(u_axis), Vector(v_axis)
    return [c + u * (radius * math.cos(math.radians(a0 + (a1 - a0) * i / n)))
            + v * (radius * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def smooth_path(points, iterations=2, closed=False):
    """Chaikin corner cutting: rounds a coarse polyline (keeps the end points of open paths)."""
    pts = [Vector(p) for p in points]
    for _ in range(iterations):
        out = [] if closed else [pts[0]]
        n = len(pts)
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            out += [a.lerp(b, 0.25), a.lerp(b, 0.75)]
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def sweep(bm, path, profile, up=(0.0, 0.0, 1.0), scales=None, closed=False, caps=True):
    """Sweep a closed 2D profile along a 3D polyline into `bm` (quads, capped ends).

    The frame follows the path by parallel transport, starting with the
    profile's v axis along `up` (projected off the first tangent) and u along
    tangent x v. For a path in a plane, pass the plane normal as `up` to keep
    the profile's v axis perpendicular to the plane (e.g. a hanger's
    thickness). scales: optional per-point (su, sv) profile scale (tapers).
    Returns the new faces.
    """
    pts = [Vector(p) for p in path]
    n = len(pts)
    tangents = []
    for i in range(n):
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    upv = Vector(up)
    nrm = upv - tangents[0] * upv.dot(tangents[0])
    if nrm.length < 1e-6:
        nrm = tangents[0].orthogonal()
    nrm.normalize()
    rings = []
    for i in range(n):
        t = tangents[i]
        if i > 0:
            nrm = tangents[i - 1].rotation_difference(t) @ nrm
            nrm = (nrm - t * nrm.dot(t)).normalized()
        bin_ = t.cross(nrm)
        su, sv = scales[i] if scales else (1.0, 1.0)
        rings.append([bm.verts.new(pts[i] + bin_ * (u * su) + nrm * (v * sv)) for u, v in profile])
    m = len(profile)
    faces = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(m):
            faces.append(bm.faces.new([a[j], b[j], b[(j + 1) % m], a[(j + 1) % m]]))
    if caps and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def tapered_square_leg(bm, x, y, z0, z1, top, bottom):
    """Square furniture leg from z0 (floor, `bottom` wide) to z1 (`top` wide), axis-aligned."""
    s2 = math.sqrt(2.0)
    mat = Matrix.Translation((x, y, (z0 + z1) / 2)) @ Matrix.Rotation(math.radians(45.0), 4, "Z")
    return bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=4,
                                 radius1=bottom / 2 * s2, radius2=top / 2 * s2, depth=z1 - z0,
                                 matrix=mat)["verts"]


# =============================================================================
# shading: layer recipes (return base, rough, height)
# =============================================================================
def _stretched(g, axis, across, along):
    s = [across, across, across]
    s["XYZ".index(axis)] = along
    return g.vec(*s)


def combine(g, a, b, c):
    """Vector from three float sockets or constants (CombineXYZ)."""
    n = g.nodes.new("ShaderNodeCombineXYZ")
    for i, v in enumerate((a, b, c)):
        g._set(n.inputs[i], v)
    return n.outputs[0]


def wood_veneer(g, axis="Z", mid=(0.040, 0.021, 0.012), light=(0.072, 0.039, 0.021),
                dark=(0.014, 0.007, 0.004), rough=0.40, figure=0.035, bands=0.85, streak=0.55,
                line_depth=0.00003, pore_depth=0.00002, seed=0.0):
    """Sliced wood veneer (dark walnut defaults) on axis-aligned boards, grain along world `axis`.

    Works on every face parallel to the grain (a panel's face and its long
    edges): the across-grain coordinate is the sum of the two other world
    axes. That coordinate is warped by slow noise (`figure` m of sideways
    wander), and every layer reads the warped coordinate, so streaks drift
    together like real grain: broad lighter/darker bands a few cm wide
    (`bands`), irregular dark streaks a few mm wide (`streak`, stretched
    noise, not a regular sine, so it doesn't read as pinstripes), faint
    growth lines and fine elongated pores (rougher, recessed). Contrast stays
    moderate: fine high-contrast lines shimmer in VR. rough is the finish
    (satin ~0.4). Returns (base, rough, height in m).
    """
    others = [c for c in "XYZ" if c != axis]
    coord = {"X": g.x, "Y": g.y, "Z": g.z}
    u = g.add(coord[others[0]], coord[others[1]])
    v = coord[axis]
    warp = g.add(g.mul(g.sub(g.noise(1.0, 2.0, 0.5, _stretched(g, axis, 3.0, 0.22)), 0.5), figure),
                 g.mul(g.sub(g.noise(1.0, 3.0, 0.5, _stretched(g, axis, 22.0, 1.1)), 0.5), figure * 0.22))
    uw = g.add(g.add(u, warp), seed)

    def grain_noise(across, along, detail=2.0, rough_=0.5, off=0.0):
        return g.noise(1.0, detail, rough_, combine(g, g.mul(uw, across), g.mul(v, along), seed * 7.0 + off))

    band = g.maprange(grain_noise(26.0, 0.45, 2.0, 0.5, 1.3), 0.32, 0.72)
    base = g.mixc(g.mul(band, bands), mid, light)
    fine = g.maprange(grain_noise(150.0, 1.4, 3.0, 0.6, 5.1), 0.50, 0.78)
    fine = g.mul(fine, g.maprange(grain_noise(9.0, 0.6, 1.0, 0.5, 9.7), 0.25, 0.75, 0.45, 1.0))
    base = g.mixc(g.mul(fine, streak), base, dark)
    heart = g.maprange(grain_noise(4.0, 0.2, 2.0, 0.5, 3.3), 0.58, 0.78)
    base = g.mixc(g.mul(heart, 0.45), base, dark)
    lines = g.maprange(g.math("SINE", g.mul(uw, 2 * math.pi / 0.011)), 0.80, 1.0)
    base = g.scale_color(base, g.sub(1.0, g.mul(lines, 0.12)))
    pores = g.maprange(grain_noise(700.0, 30.0, 1.0, 0.5, 2.2), 0.62, 0.74)
    base = g.scale_color(base, g.sub(1.0, g.mul(pores, 0.15)))
    r = g.add(rough, g.add(g.mul(g.sub(g.noise(9.0, 2.0), 0.5), 0.06),
                           g.add(g.mul(fine, 0.03), g.mul(pores, 0.08))))
    height = g.sub(0.0, g.add(g.mul(fine, line_depth), g.mul(pores, pore_depth)))
    return base, r, height


def brushed_metal(g, axis="Z", base=(0.052, 0.060, 0.072), rough=0.32, streak=0.05, tint=0.10,
                  depth=0.00001):
    """Brushed metal (gunmetal defaults), brushed along world `axis`: fine
    streaks in roughness and a faint tint variation. Returns (base, rough, height)."""
    n = g.noise(1.0, 3.0, 0.6, _stretched(g, axis, 260.0, 3.0))
    blotch = g.sub(g.noise(18.0, 2.0), 0.5)
    r = g.add(rough, g.add(g.mul(g.sub(n, 0.5), 2 * streak), g.mul(blotch, 0.05)))
    b = g.scale_color(base, g.add(1.0, g.mul(g.sub(n, 0.5), 2 * tint)))
    height = g.mul(g.sub(n, 0.5), depth)
    return b, r, height


def bump_finish(g, base, rough, metal, height):
    """Normal from accumulated height (meters) and connect the BSDF (like fabric.fabric_finish, with metal)."""
    return g.finish(base, rough, metal, g.bump(height, 1.0, 1.0))


# =============================================================================
# wear: masked layers
# =============================================================================
def scratch_xz(g, base, rough, height, p0, p1, width=0.0012, mask=1.0, color=(0.26, 0.19, 0.13),
               amount=0.8, rougher=0.25, depth=0.00008, wobble=0.5):
    """A thin straight scratch on a front- or back-facing surface, from world
    (x, z) p0 to p1, tapering to the ends and wobbling by `wobble` x width.
    Scratched lacquer turns lighter and duller. mask limits it (e.g. to a door front)."""
    x0, z0 = p0
    ex, ez = p1[0] - x0, p1[1] - z0
    l2 = ex * ex + ez * ez
    dx, dz = g.sub(g.x, x0), g.sub(g.z, z0)
    t = g.math("MINIMUM", g.math("MAXIMUM", g.mul(g.add(g.mul(dx, ex), g.mul(dz, ez)), 1.0 / l2), 0.0), 1.0)
    qx, qz = g.sub(dx, g.mul(t, ex)), g.sub(dz, g.mul(t, ez))
    d = g.math("SQRT", g.add(g.mul(qx, qx), g.mul(qz, qz)))
    d = g.add(d, g.mul(g.sub(g.noise(260.0, 2.0), 0.5), width * wobble))
    tt = g.sub(g.mul(t, 2.0), 1.0)
    w = g.mul(g.sub(1.0, g.mul(tt, tt)), width)  # widest in the middle
    s = g.mul(g.math("GREATER_THAN", w, 0.00005), g.maprange(g.math("DIVIDE", d, g.add(w, 1e-6)), 1.0, 0.35))
    s = g.mul(s, mask)
    base = g.mixc(g.mul(s, amount), base, color)
    rough = g.add(rough, g.mul(s, rougher))
    height = g.sub(height, g.mul(s, depth))
    return base, rough, height


def bevel_edges(g, radius=0.004, lo=0.02, hi=0.20):
    """0..1 mask of convex and concave edges within ~radius m, from Cycles'
    Bevel node (1 - dot of the beveled and the shading normal). Unlike
    pointiness it doesn't depend on vertex density, so large flat boards
    with vertices only at their corners get clean edge masks."""
    bev = g.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = radius
    dot = g.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    g.links.new(bev.outputs["Normal"], dot.inputs[0])
    g.links.new(g.geo.outputs["Normal"], dot.inputs[1])
    return g.maprange(g.sub(1.0, dot.outputs["Value"]), lo, hi)


def edge_wear(g, base, rough, edge, mask, color, amount=0.4, rough_delta=-0.08):
    """Edges (a 0..1 `edge` mask, e.g. bevel_edges) inside a 0..1 `mask` shift
    toward `color` by `amount` and change roughness by rough_delta (negative:
    polished by hands, positive: worn matte)."""
    e = g.mul(edge, mask)
    base = g.mixc(g.mul(e, amount), base, color)
    rough = g.add(rough, g.mul(e, rough_delta))
    return base, rough


def masked_scuffs(g, base, rough, mask, z_clean=0.30, z_full=0.12, rougher=0.12, darker=0.12):
    """Horizontal kick scuffs (like wear.bottom_scuffs) limited to a 0..1 mask."""
    low = g.mul(g.maprange(g.z, z_clean, z_full), mask)
    s = g.mul(low, g.maprange(g.noise(1.0, 3.0, 0.6, g.vec(5.0, 5.0, 90.0)), 0.52, 0.66))
    rough = g.add(rough, g.mul(s, rougher))
    base = g.scale_color(base, g.sub(1.0, g.mul(s, darker)))
    return base, rough


# =============================================================================
# bake: several moving parts in one atlas
# =============================================================================
class Spread:
    """Context manager: temporarily move groups of objects apart along one world
    axis, so separate parts baked into one shared atlas (bake.bake_part with all
    of them) don't darken each other's AO, e.g. a lid resting on its box, or
    garments hanging side by side that are picked up separately.

    groups: [(root_object, offset_m), ...]; children follow their root. The
    procedural materials must not depend on the world position along `axis`
    (0 = X) for the moved parts, or the offsets must keep them in the same mask
    regions; keep offset 0 for parts whose masks do.
    """

    def __init__(self, groups, axis=0):
        self.groups = groups
        self.axis = axis

    def __enter__(self):
        import bpy
        for ob, off in self.groups:
            ob.location[self.axis] += off
        bpy.context.view_layer.update()
        return self

    def __exit__(self, *args):
        import bpy
        for ob, off in self.groups:
            ob.location[self.axis] -= off
        bpy.context.view_layer.update()


def instance(src, name, location, rotation=(0.0, 0.0, 0.0), collection=None, part=None):
    """Linked duplicate (shares the mesh) at another place, e.g. the second of two
    identical drawers exported once. Tagged `part` (scene.PART_KEY) if given."""
    import bpy
    ob = bpy.data.objects.new(name, src.data)
    ob.location = location
    ob.rotation_euler = rotation
    (collection or src.users_collection[0]).objects.link(ob)
    if part is not None:
        ob["arcology_part"] = part
    return ob
