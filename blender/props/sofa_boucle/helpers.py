"""Soft-shape and fabric helpers used by the boucle sofa only (Fable 5.1, D-029).

The sofa A/B promoted Opus's versions into arcology_blender.soft and .fabric;
these stay local so this asset rebuilds unchanged. Prefer the library for new assets;
merge something from here into it only when an asset needs it.

Generic helpers for soft, upholstered shapes and fabric materials. Written as
if they lived in `arcology_blender` (asset-agnostic, documented) so the
winner's helpers can be promoted: `soft.py` (rounded boxes and displacement)
and `materials.py` additions (fabric recipes). Nothing here knows the sofa's
dimensions.

Rounded boxes are generated as an explicit grid on the six faces of a box
(shared edges welded), then every grid point is projected onto the surface of
the rounded box (the Minkowski sum of an inner box and a sphere). With the
default cosine ("Chebyshev") spacing the samples crowd toward the box edges,
so the roundovers get several rings while the flat faces stay coarse. The
result is an all-quad, closed mesh that displaces cleanly (puff, sag, dents,
wrinkles) and shades smooth without split normals, which is what a cushion
needs and what `bm_box` + bevel + subdivision can't give at the same cost.
"""

import math

import bmesh
from mathutils import Vector, noise

from arcology_blender import wear
from arcology_blender.shading import Graph, new_mat


# --- rounded box grid ------------------------------------------------------
def _spacing(n, mode):
    """n+1 parameters in 0..1: uniform, or cosine-spaced (dense at both ends)."""
    if mode == "cheb":
        return [(1.0 - math.cos(math.pi * i / n)) / 2.0 for i in range(n + 1)]
    return [i / n for i in range(n + 1)]


def _project_rounded(p, half, radius):
    """Closest point on a rounded box (half extents, edge radius) for a point on the sharp box."""
    inner = Vector((max(half.x - radius, 0.0), max(half.y - radius, 0.0), max(half.z - radius, 0.0)))
    q = Vector((max(-inner.x, min(inner.x, p.x)),
                max(-inner.y, min(inner.y, p.y)),
                max(-inner.z, min(inner.z, p.z))))
    d = p - q
    if d.length < 1e-9:
        return p.copy()
    return q + d.normalized() * radius


def rounded_box(bm, size, radius, divisions, center=(0.0, 0.0, 0.0), spacing="cheb"):
    """Closed all-quad rounded box: `size` (x, y, z), edge `radius`, `divisions`
    (nx, ny, nz) grid cells per axis. Returns the new verts. Density near the
    edges comes from `spacing` ("cheb" or "uniform"); with "cheb" about a
    third of the samples land on the roundovers.
    """
    half = Vector(size) / 2.0
    c = Vector(center)
    nx, ny, nz = divisions
    ts = [_spacing(nx, spacing), _spacing(ny, spacing), _spacing(nz, spacing)]
    verts = {}

    def vert(ix, iy, iz):
        key = (ix, iy, iz)
        v = verts.get(key)
        if v is None:
            p = Vector(((ts[0][ix] * 2 - 1) * half.x, (ts[1][iy] * 2 - 1) * half.y, (ts[2][iz] * 2 - 1) * half.z))
            v = bm.verts.new(c + _project_rounded(p, half, radius))
            verts[key] = v
        return v

    def face(a, b, cc, d, flip):
        quad = [a, b, cc, d]
        if flip:
            quad.reverse()
        try:
            bm.faces.new(quad)
        except ValueError:
            pass

    # z faces (top/bottom), y faces (front/back), x faces (sides)
    for iz, flip in ((nz, False), (0, True)):
        for ix in range(nx):
            for iy in range(ny):
                face(vert(ix, iy, iz), vert(ix + 1, iy, iz), vert(ix + 1, iy + 1, iz), vert(ix, iy + 1, iz), flip)
    for iy, flip in ((0, False), (ny, True)):
        for ix in range(nx):
            for iz in range(nz):
                face(vert(ix, iy, iz), vert(ix + 1, iy, iz), vert(ix + 1, iy, iz + 1), vert(ix, iy, iz + 1), flip)
    for ix, flip in ((nx, False), (0, True)):
        for iy in range(ny):
            for iz in range(nz):
                face(vert(ix, iy, iz), vert(ix, iy + 1, iz), vert(ix, iy + 1, iz + 1), vert(ix, iy, iz + 1), flip)
    bm.normal_update()
    return list(verts.values())


# --- displacement on soft shapes ----------------------------------------------
def _norm_coords(v, center, half):
    return Vector(((v.co.x - center.x) / half.x, (v.co.y - center.y) / half.y, (v.co.z - center.z) / half.z))


def puff(bm, verts, size, amount, center=(0.0, 0.0, 0.0)):
    """Inflate along normals like stuffing pushing the fabric out: full at the
    middle of each face, zero at the edges (product of the two in-face
    parabolas, weighted by the normal). `amount` is meters, or a 3-tuple of
    meters per face axis (a pillow: fat top and bottom, thin sides)."""
    half, c = Vector(size) / 2.0, Vector(center)
    amt = Vector(amount) if isinstance(amount, (tuple, list)) else Vector((amount, amount, amount))
    bm.normal_update()
    for v in verts:
        u = _norm_coords(v, c, half)
        n = v.normal
        w = 0.0
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            w += amt[i] * abs(n[i]) * max(1.0 - u[j] * u[j], 0.0) * max(1.0 - u[k] * u[k], 0.0)
        v.co += n * w
    bm.normal_update()


def dent(bm, verts, center, sigma, depth, direction=(0.0, 0.0, 1.0)):
    """Press the surface in around `center` (meters): a gaussian dent of
    `depth` with radius `sigma` (2-tuple for an elliptic footprint), applied
    to verts whose normal faces `direction` (a sat-in seat: direction +Z; a
    lumbar hollow in a back cushion: direction -Y)."""
    c, d = Vector(center), Vector(direction).normalized()
    sx, sy = (sigma, sigma) if isinstance(sigma, (int, float)) else sigma
    bm.normal_update()
    # In-plane axes for the gaussian footprint.
    a = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    b = d.cross(a).normalized()
    a = b.cross(d).normalized()
    for v in verts:
        f = v.normal.dot(d)
        if f <= 0.2:
            continue
        rel = v.co - c
        g = math.exp(-0.5 * ((rel.dot(a) / sx) ** 2 + (rel.dot(b) / sy) ** 2))
        v.co -= d * (depth * g * min(f / 0.6, 1.0))
    bm.normal_update()


def wrinkles(bm, verts, amount, scale, seed=(0.0, 0.0, 0.0), octaves=2):
    """Low-frequency lumpiness along normals (soft filling, slack fabric).
    `scale` in features per meter; keep it under ~10 for VR (fine creases
    belong in the normal map)."""
    s = Vector(seed)
    bm.normal_update()
    for v in verts:
        p = v.co * scale + s
        h = noise.noise(p)
        if octaves > 1:
            h += 0.5 * noise.noise(p * 2.1 + Vector((3.7, 1.3, 9.1)))
        v.co += v.normal * (amount * h)
    bm.normal_update()


def taper(bm, verts, z0, z1, factor, keep_y):
    """Thin a shape toward the top: thickness in Y shrinks linearly to
    (1-factor) between z0 and z1 while the side at `keep_y` stays put (a back
    cushion squashed against the frame is thick at the seat, thin at the top)."""
    for v in verts:
        t = max(0.0, min(1.0, (v.co.z - z0) / (z1 - z0)))
        v.co.y = keep_y - (keep_y - v.co.y) * (1.0 - factor * t)
    bm.normal_update()


def soft_object(name, collection, size, radius, divisions, center, material,
                puff_amount=0.0, wrinkle=(0.0, 6.0), seed=0.0, spacing="cheb"):
    """Rounded box object with optional puff and wrinkles, smooth shaded.
    Returns (object, bmesh-less) after writing the mesh: use `edit(ob)` for
    further displacement."""
    from arcology_blender.geo import new_object

    bm = bmesh.new()
    verts = rounded_box(bm, size, radius, divisions, center, spacing)
    if puff_amount:
        puff(bm, verts, size, puff_amount, center)
    if wrinkle[0]:
        wrinkles(bm, verts, wrinkle[0], wrinkle[1], (seed, seed * 0.7, seed * 1.3))
    for f in bm.faces:
        f.smooth = True
    return new_object(name, bm, collection, material=material)


def edit(ob, fn):
    """Run `fn(bm, verts)` on the object's mesh (bmesh round trip), keep smooth shading."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    fn(bm, list(bm.verts))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# --- fabric materials (procedural, baked) ---------------------------------------
def welt(g, base, rough, height=0.003, nz_center=0.70, nz_half=0.07, darker=0.12):
    """Piping/welt cord along every roundover that faces ~45 degrees up or down
    (where the shading normal's z passes `nz_center`), as a half-round
    normal-map ridge with a darker, slightly smoother thread line. Needs no
    extra geometry: on a `rounded_box` the cord follows the top and bottom
    perimeter of the shape, like the welt on a box cushion. Returns (base,
    rough, height_socket)."""
    def cord(center):
        t = g.mul(g.sub(g.nz, center), 1.0 / nz_half)
        return g.math("SQRT", g.math("MAXIMUM", g.sub(1.0, g.mul(t, t)), 0.0))

    seam = g.math("MAXIMUM", cord(nz_center), cord(-nz_center))
    # Thread detail along the welt (stitch bumps at ~2 mm) is too fine for VR: keep it smooth.
    line = g.maprange(seam, 0.2, 0.6)
    base = g.scale_color(base, g.sub(1.0, g.mul(line, darker)))
    rough = g.sub(rough, g.mul(line, 0.08))
    return base, rough, g.mul(seam, height)


def creases(g, height, amount=0.0008, scale=5.0, distortion=8.0, mask=None):
    """Slack-fabric creases: sparse, wavy, roughly vertical folds on the sides
    of upholstery (boxing of cushions, arm fronts), in patches, fading out on
    top and bottom faces. Wave bands run along world X on Y-facing sides and
    along Y on X-facing sides, so every side gets vertical folds. Adds to a
    height socket; `mask` restricts them further."""
    lines_x = g.maprange(g.wave(scale, distortion, 2.0, "X"), 0.55, 0.85)
    lines_y = g.maprange(g.wave(scale, distortion, 2.0, "Y"), 0.55, 0.85)
    lines = g.add(g.mul(lines_x, g.math("ABSOLUTE", g.ny)), g.mul(lines_y, g.math("ABSOLUTE", g.nx)))
    sides = g.maprange(g.math("ABSOLUTE", g.nz), 0.75, 0.35)
    patches = g.maprange(g.noise(2.0, 2.0), 0.42, 0.62)
    fold = g.mul(g.mul(lines, sides), patches)
    if mask is not None:
        fold = g.mul(fold, mask)
    return g.add(height, g.mul(fold, amount))


def fabric(name, base=(0.095, 0.115, 0.145), rough=0.78, nub_scale=55.0, nub_height=0.0007,
           mottle=0.10, seam=True, seam_height=0.0025):
    """Upholstery fabric: mottled color, boucle-like nubs at medium scale (no
    fine weave: it shimmers in VR), high roughness with variation, optional
    welt seams on the roundovers (see `welt`). Returns a `Graph` and the
    (base, rough, height) so the caller can add asset-specific wear before
    `g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))`.
    """
    g = Graph(new_mat(f"src_{name}"))
    m = g.maprange(g.noise(30.0, 3.0, 0.6), 0.35, 0.65, 1.0 - mottle, 1.0 + mottle)
    base = g.scale_color(base, m)
    nubs = g.maprange(g.noise(nub_scale, 3.0, 0.65), 0.42, 0.62)
    coarse = g.noise(nub_scale * 0.35, 2.0, 0.5)
    height = g.add(g.mul(nubs, nub_height), g.mul(coarse, nub_height * 0.6))
    rough = g.add(rough, g.mul(g.sub(g.noise(18.0, 2.0), 0.5), 0.10))
    rough = g.sub(rough, g.mul(nubs, 0.05))
    if seam:
        base, rough, ridge = welt(g, base, rough, seam_height)
        height = g.add(height, ridge)
    height = creases(g, height)
    return g, base, rough, height


def sheen_wear(g, base, rough, region, smoother=0.22, darker=0.10, pilling=0.35):
    """Where fabric gets sat on and rubbed: fibers flatten (smoother, a touch
    darker) and pill (sparse light specks). `region` is a 0..1 mask."""
    r = g.mul(region, g.maprange(g.noise(4.0, 2.0), 0.35, 0.65))
    rough = g.sub(rough, g.mul(r, smoother))
    base = g.scale_color(base, g.sub(1.0, g.mul(r, darker)))
    pills = g.mul(r, g.maprange(g.noise(90.0, 1.0), 0.70, 0.78))
    base = g.scale_color(base, g.add(1.0, g.mul(pills, pilling)))
    rough = g.add(rough, g.mul(pills, 0.15))
    return base, rough


def stain(g, base, rough, center_xy, radius, color=(0.30, 0.22, 0.12), amount=0.30, z_lo=None, z_hi=None):
    """A faint dried spill on a horizontal surface at world (x, y): darker
    center, stronger ring at the rim, irregular outline."""
    dx, dy = g.sub(g.x, center_xy[0]), g.sub(g.y, center_xy[1])
    d = g.math("SQRT", g.add(g.mul(dx, dx), g.mul(dy, dy)))
    d = g.add(d, g.mul(g.sub(g.noise(25.0, 2.0), 0.5), radius * 0.6))
    inside = g.maprange(d, radius, radius * 0.85)
    rim = g.band(d, radius * 0.75, radius * 0.95, radius * 0.1)
    m = g.add(g.mul(inside, 0.45), g.mul(rim, 0.55))
    m = g.mul(m, g.maprange(g.nz, 0.7, 0.9))
    if z_lo is not None:
        m = g.mul(m, g.band(g.z, z_lo, z_hi, 0.01))
    base = g.mixc(g.mul(m, amount), base, color)
    rough = g.sub(rough, g.mul(m, 0.10))
    return base, rough


def velvet(name, base=(0.25, 0.075, 0.025), rough=0.72):
    """Short-pile velvet (throw pillows): matte, with the crushed-pile
    light/dark mottling velvet shows where the nap changes direction, a soft
    pile bump and a welt around the edge."""
    g = Graph(new_mat(f"src_{name}"))
    crush = g.noise(9.0, 3.0, 0.6)
    fine = g.noise(70.0, 2.0, 0.5)
    base = g.scale_color(base, g.maprange(crush, 0.3, 0.7, 0.80, 1.12))
    base = g.scale_color(base, g.maprange(fine, 0.4, 0.6, 0.95, 1.05))
    r = g.add(rough, g.mul(g.sub(crush, 0.5), 0.12))
    height = g.add(g.mul(fine, 0.0004), g.mul(g.noise(25.0, 2.0, 0.5), 0.0005))
    base, r, ridge = welt(g, base, r, 0.002, darker=0.16)
    height = g.add(height, ridge)
    height = creases(g, height, amount=0.0006, scale=8.0)
    base, r = wear.edge_highlight(g, base, r, brighter=0.10, smoother=0.04)
    return g.finish(base, r, 0.0, g.bump(height, 1.0, 1.0))


def dark_metal(name="metal", base=(0.027, 0.033, 0.041), rough=0.38):
    """Powder-coated gunmetal (legs, frames): metallic, satin, worn edges."""
    g = Graph(new_mat(f"src_{name}"))
    r = g.add(rough, g.mul(g.sub(g.noise(20.0), 0.5), 0.08))
    base, r = wear.edge_highlight(g, base, r, brighter=0.6, smoother=0.15)
    return g.finish(base, r, 1.0, g.bump(g.noise(120.0, 1.0), 1.0, 0.0004))
