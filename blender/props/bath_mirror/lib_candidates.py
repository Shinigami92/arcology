"""Generic helpers written for the bathroom mirror, candidates for blender/lib (parallel run:
blender/lib must not change now). Asset-agnostic; each names the module it would join.

- planar_uvs(ob, fn)                       -> geo: UVs per loop from fn(local position) (decals, glass, wall quads)
- disc_y / annulus_y(bm, center, ...)      -> geo: flat round face(s) facing -Y (glass discs, ring lights, icons)
- rect_ring_quads(bm, outer, inner, y)     -> geo: flat rectangular frame of 8 quads facing -Y (halo, gasket)
- brushed_radial(g, rough, center, axis)   -> metal: spun finish around any world axis (`brushed` only spins about Z)
- water_spots(g, base, rough, mask, ...)   -> wear: dried water droplets (mineral rims) inside a mask
- backlight_halo(...)                      -> trim/surface (numpy): glow a backlit panel's LED loop throws on the wall
"""

import math

import bmesh
import numpy as np
from mathutils import Vector


# --- geo -------------------------------------------------------------------------
def planar_uvs(ob, fn, name="UVMap"):
    """Write one UV layer from fn(local vertex position) -> (u, v) for every loop."""
    me = ob.data
    layer = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    for loop in me.loops:
        layer.data[loop.index].uv = fn(me.vertices[loop.vertex_index].co)
    return layer


def _face_minus_y(bm, verts):
    f = bm.faces.new(verts)
    f.normal_update()
    if f.normal.y > 0.0:
        f.normal_flip()
    return f


def disc_y(bm, center, radius, segments=32):
    """Flat disc in the XZ plane at `center`, facing -Y (one n-gon; the exporter triangulates)."""
    c = Vector(center)
    verts = [bm.verts.new(c + Vector((radius * math.cos(2 * math.pi * i / segments), 0.0,
                                       radius * math.sin(2 * math.pi * i / segments))))
             for i in range(segments)]
    return [_face_minus_y(bm, verts)]


def annulus_y(bm, center, r_in, r_out, segments=48):
    """Flat ring in the XZ plane at `center`, facing -Y (quads)."""
    c = Vector(center)
    ring = []
    for r in (r_in, r_out):
        ring.append([bm.verts.new(c + Vector((r * math.cos(2 * math.pi * i / segments), 0.0,
                                               r * math.sin(2 * math.pi * i / segments))))
                     for i in range(segments)])
    a, b = ring
    return [_face_minus_y(bm, [a[i], a[(i + 1) % segments], b[(i + 1) % segments], b[i]])
            for i in range(segments)]


def rect_ring_quads(bm, outer, inner, y):
    """Flat rectangular frame (outer rect minus inner rect) in the plane Y = y,
    facing -Y, as 8 quads sharing vertices. outer/inner: (x0, z0, x1, z1)."""
    xs = [outer[0], inner[0], inner[2], outer[2]]
    zs = [outer[1], inner[1], inner[3], outer[3]]
    grid = [[bm.verts.new((x, y, z)) for x in xs] for z in zs]
    faces = []
    for j in range(3):
        for i in range(3):
            if i == 1 and j == 1:
                continue
            faces.append(_face_minus_y(bm, [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]))
    return faces


# --- metal -------------------------------------------------------------------------
def brushed_radial(g, rough=0.30, center=(0.0, 0.0, 0.0), axis="Y", streak=0.07, height=0.00002):
    """Spun (circular brushed) finish around a world axis "X", "Y" or "Z" through
    `center`: fine concentric roughness streaks, like `metal.brushed(center=...)`
    but for discs that don't face up (a mirror head's back, a wall rosette).
    Returns (rough, height in m)."""
    comps = {"X": (g.y, g.z, g.x), "Y": (g.x, g.z, g.y), "Z": (g.x, g.y, g.z)}[axis]
    i = "XYZ".index(axis)
    c = [center[k] for k in range(3) if k != i]
    da, db = g.sub(comps[0], c[0]), g.sub(comps[1], c[1])
    d = g.math("SQRT", g.add(g.mul(da, da), g.mul(db, db)))
    n = g.noise(1.0, 2.0, 0.6, vector=g.combine(g.mul(d, 900.0), g.mul(comps[2], 900.0), 0.0))
    coarse = g.noise(8.0, 2.0)
    r = g.add(g.add(rough, g.mul(g.sub(n, 0.5), streak * 2)), g.mul(g.sub(coarse, 0.5), 0.06))
    return r, g.mul(n, height)


# --- wear -------------------------------------------------------------------------
def water_spots(g, base, rough, mask, scale=55.0, density=0.35, amount=0.10, rougher=0.12,
                color=(0.55, 0.55, 0.53)):
    """Dried water droplets inside a 0..1 `mask`: Voronoi cells, a share
    (`density`) of which hold a spot of varying size with a faint mineral rim;
    spots shift toward `color` by `amount` and get rougher. `scale` is cells per
    meter (55: spots of about 2..6 mm). Medium scale, low contrast: no shimmer."""
    vor = g.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = scale
    vor.inputs["Randomness"].default_value = 1.0
    g.links.new(g.geo.outputs["Position"], vor.inputs["Vector"])
    d = vor.outputs["Distance"]
    sep = g.nodes.new("ShaderNodeSeparateColor")
    g.links.new(vor.outputs["Color"], sep.inputs[0])
    keep = g.maprange(sep.outputs["Red"], 1.0 - density, 1.0 - density + 0.02)
    size = g.add(0.10, g.mul(sep.outputs["Green"], 0.22))        # spot radius in cell units
    inner = g.maprange(g.sub(d, size), 0.0, -0.04)                # 1 inside the spot
    rim = g.maprange(g.math("ABSOLUTE", g.sub(d, size)), 0.025, 0.0)
    spot = g.mul(g.mul(keep, mask), g.add(g.mul(inner, 0.35), rim))
    base = g.mixc(g.mul(spot, amount), base, color)
    rough = g.add(rough, g.mul(spot, rougher))
    return base, rough


# --- numpy textures -------------------------------------------------------------------
def backlight_halo(extent, loop, height, size=512, bounce=0.05, bounce_dist=0.05, gain=2.0,
                   inner=None, reach=None, fade=0.02, samples_per_m=200, dither_seed=1):
    """Intensity (0..1, HxW float32, row 0 = bottom like Blender images) of the glow
    an LED loop on the back of a wall-hung panel throws onto the wall.

    extent: (x0, z0, x1, z1) wall area the texture covers (meters).
    loop: (x0, z0, x1, z1) rectangle the LED strip runs along, `height` meters
    off the wall, emitting toward it (Lambertian at both ends: h^2 / r^4 per
    unit length). Adds a soft `bounce` term (exp falloff over `bounce_dist`
    outside the loop), normalizes so the wall just outside `inner` (the panel
    outline, default the loop) reads 1 before tone mapping 1 - exp(-gain * E),
    fills the area behind `inner` with 1, windows the glow to 0 at `reach`
    meters outside `inner` (smoothly from 0.35 * reach; default: the nearest
    texture border), fades to 0 over `fade` meters at the texture border, and
    dithers +-0.5/255 against banding."""
    x0, z0, x1, z1 = extent
    xs = x0 + (np.arange(size) + 0.5) / size * (x1 - x0)
    zs = z0 + (np.arange(size) + 0.5) / size * (z1 - z0)
    X, Z = np.meshgrid(xs, zs)
    lx0, lz0, lx1, lz1 = loop
    pts = []
    for (ax, az), (bx, bz) in (((lx0, lz0), (lx1, lz0)), ((lx1, lz0), (lx1, lz1)),
                               ((lx1, lz1), (lx0, lz1)), ((lx0, lz1), (lx0, lz0))):
        n = max(2, int(math.hypot(bx - ax, bz - az) * samples_per_m))
        t = (np.arange(n) + 0.5) / n
        ds = math.hypot(bx - ax, bz - az) / n
        for ti in t:
            pts.append((ax + (bx - ax) * ti, az + (bz - az) * ti, ds))
    h2 = height * height
    E = np.zeros_like(X)
    for px, pz, ds in pts:
        r2 = (X - px) ** 2 + (Z - pz) ** 2 + h2
        E += ds * h2 / (r2 * r2)
    ix0, iz0, ix1, iz1 = inner if inner is not None else loop
    # distance outside the panel outline (0 inside)
    dx = np.maximum(np.maximum(ix0 - X, X - ix1), 0.0)
    dz = np.maximum(np.maximum(iz0 - Z, Z - iz1), 0.0)
    d_out = np.sqrt(dx * dx + dz * dz)
    # reference: middle of the bottom edge, just outside the outline
    cx = 0.5 * (ix0 + ix1)
    ref = 0.0
    for px, pz, ds in pts:
        r2 = (cx - px) ** 2 + (iz0 - pz) ** 2 + h2
        ref += ds * h2 / (r2 * r2)
    e = E / ref + bounce * np.exp(-d_out / bounce_dist)
    out = 1.0 - np.exp(-gain * e)
    out[d_out <= 0.0] = 1.0
    if reach is None:
        reach = min(ix0 - x0, x1 - ix1, iz0 - z0, z1 - iz1)
    w = np.clip((d_out - 0.35 * reach) / (0.65 * reach), 0.0, 1.0)
    out *= 1.0 - w * w * (3.0 - 2.0 * w)
    edge = np.minimum.reduce([X - x0, x1 - X, Z - z0, z1 - Z])
    t = np.clip(edge / fade, 0.0, 1.0)
    out *= t * t * (3.0 - 2.0 * t)
    rng = np.random.default_rng(dither_seed)
    out += (rng.random(out.shape) - 0.5) / 255.0
    return np.clip(out, 0.0, 1.0).astype(np.float32)
