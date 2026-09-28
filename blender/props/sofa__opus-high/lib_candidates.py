"""Candidate additions to `arcology_blender` from the sofa A/B run (opus-high).

Written as library code (asset-agnostic, documented) so they can be promoted
as they are. Suggested homes:

geo (soft goods)
    soft_box      upholstered block (cushion, arm, frame) with evenly rounded
                  edges, crowned panels and a per-vertex `seam` distance
                  attribute that drives welts/piping in the material
    press         height-weighted Gaussian dent (a seat's sag, an elbow spot)
    jitter        low-frequency irregularity along the vertex normals
    rotate_verts  rotate a bmesh about a pivot (lean a back cushion)
    pillow        knife-edge throw pillow: stuffed panels, pinched edges,
                  corner folds and a corded welt
    join          join objects into one mesh object (fewer draw calls)
    remove_attribute  drop a build-time mesh attribute before export

shading / materials (fabric)
    attribute     Graph helper: read a mesh attribute (e.g. `seam`)
    dist_xy       Graph helper: 2D distance from a point in world x/y
    fabric_base   heathered, slubbed upholstery color + soft weave height
    welt          piping cord and stitch groove from the `seam` attribute
    creases       ridged-noise fabric creases inside a mask
    rub           abrasion shine inside a mask (arm tops, seat fronts)
    pilling       fuzz balls inside a mask
    stain         a faint tide-mark stain on an upward-facing surface
    fabric_finish bump from the accumulated height, connect the BSDF

Fabric heights are accumulated in meters and turned into a normal once by
`fabric_finish` (Bump distance 1.0), so every layer's depth is physical.
Keep fabric detail at medium scale and low contrast: a fine, high-contrast
weave shimmers in VR, and the 512 px/m texel density can't hold it anyway.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

SEAM_ATTR = "seam"
FAR = 0.10  # seam distance stored for vertices without a seam (meters)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def _axis_coords(half, r, step, k):
    """Grid lines along one axis of a soft box: flat part every ~step, then k
    band lines per side placed so the rounded edge gets even angular steps."""
    inner = half - r
    n = max(1, int(round(2 * inner / step)))
    flat = [-inner + 2 * inner * i / n for i in range(n + 1)]
    band = [inner + r * math.tan(math.radians(45.0 * j / k)) for j in range(1, k + 1)]
    band[-1] = half
    return [-b for b in reversed(band)] + flat + band


def soft_box(center, size, radius, step=0.04, band_segments=3, panel_axis=2, crown=None,
             crown_power=3.0, open_faces=(), seam_attr=SEAM_ATTR):
    """Upholstered block as a new bmesh (world coordinates, all quads).

    center, size: box center and full size (meters). radius: edge roundness,
    the same on all edges (< half the smallest size). step: target quad size
    on the flat parts, a float or a per-axis 3-tuple. band_segments: quads per
    half of each rounded edge (2-3 is smooth with smooth shading).

    panel_axis: 0/1/2 = x/y/z, or None. The two faces perpendicular to it are
    the "panels" (a seat cushion's top and bottom, an arm's outer and inner
    side); their perimeter is the welt seam. Every vertex gets a float
    attribute `seam_attr`: the distance in meters along the surface to the
    nearest seam (FAR without seams), for `welt` in the material.

    crown: {"+z": 0.02, "-y": 0.01, ...} outward bulge per face in meters,
    falling off as (1 - |u|^p)(1 - |v|^p) toward the face edges (p =
    crown_power; higher is flatter with a steeper edge), which gives the
    filled look of a stuffed cushion while the seams stay taut.

    open_faces: faces ("-z", ...) whose flat interior is replaced by one
    n-gon (hidden undersides; saves triangles). Don't crown open faces.
    """
    c = Vector(center)
    H = Vector(size) / 2
    r = min(radius, 0.95 * min(H))
    steps = step if isinstance(step, (tuple, list)) else (step, step, step)
    coords = [_axis_coords(H[i], r, steps[i], band_segments) for i in range(3)]
    inner = [H[i] - r for i in range(3)]
    crown = crown or {}
    eps = 1e-7

    bm = bmesh.new()
    for n in range(3):
        a, b = [i for i in range(3) if i != n]
        for s in (-1.0, 1.0):
            label = ("-" if s < 0 else "+") + "xyz"[n]
            opened = label in open_faces
            grid = []
            for ca in coords[a]:
                row = []
                for cb in coords[b]:
                    p = [0.0, 0.0, 0.0]
                    p[n], p[a], p[b] = s * H[n], ca, cb
                    row.append(bm.verts.new(p))
                grid.append(row)
            for i in range(len(coords[a]) - 1):
                for j in range(len(coords[b]) - 1):
                    if opened and all(abs(coords[a][ii]) <= inner[a] + eps and abs(coords[b][jj]) <= inner[b] + eps
                                      for ii in (i, i + 1) for jj in (j, j + 1)):
                        continue
                    quad = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                    bm.faces.new(quad if s > 0 else list(reversed(quad)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)

    layer = bm.verts.layers.float.new(seam_attr)

    def arc_to_seam(p, axis):
        """Surface distance from p (pre-map, on a face containing `axis` in
        plane) to the box edge perpendicular to `axis`."""
        e = abs(p[axis]) - inner[axis]
        if e > 0:
            return r * (math.pi / 4 - math.atan(e / r))
        return r * math.pi / 4 - e

    for v in bm.verts:
        p = v.co.copy()
        on = [i for i in range(3) if abs(abs(p[i]) - H[i]) < 1e-6]
        # seam distance
        d = FAR
        if panel_axis is not None:
            if panel_axis in on:
                d = min(arc_to_seam(p, j) for j in range(3) if j != panel_axis)
            else:
                d = arc_to_seam(p, panel_axis)
            d = min(max(d, 0.0), FAR)
        v[layer] = d
        # rounded box mapping
        q = Vector([max(-inner[i], min(inner[i], p[i])) for i in range(3)])
        dv = p - q
        m = q + dv.normalized() * r if dv.length > 1e-9 else p
        # crown
        for n in on:
            s = 1.0 if p[n] > 0 else -1.0
            amt = crown.get(("-" if s < 0 else "+") + "xyz"[n], 0.0)
            if amt:
                f = 1.0
                for i in range(3):
                    if i != n:
                        f *= max(0.0, 1.0 - abs(p[i] / H[i]) ** crown_power)
                m[n] += s * amt * f
        v.co = m + c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm


def press(bm, center, radii, depth, direction=(0.0, 0.0, -1.0), thickness=0.12, power=1.0):
    """Dent a soft object as if pressed: vertices move by `depth` along
    `direction`, weighted by a Gaussian around `center` (radii per axis,
    the component along `direction` is ignored) and by their height above
    the object's base (`thickness` behind `center` along `direction`), so the
    underside stays put. Negative depth puffs up."""
    c = Vector(center)
    dirv = Vector(direction).normalized()
    rad = Vector(radii)
    for v in bm.verts:
        rel = v.co - c
        h = thickness + rel.dot(-dirv)
        w = max(0.0, min(1.0, h / thickness)) ** power
        if w <= 0.0:
            continue
        plane = rel - dirv * rel.dot(dirv)
        g = math.exp(-sum((plane[i] / rad[i]) ** 2 for i in range(3) if rad[i] > 0))
        v.co += dirv * (depth * g * w)
    bm.normal_update()


def jitter(bm, amount, scale=6.0, seed=0.0):
    """Low-frequency irregularity: move vertices along their normals by up to
    `amount` meters (Perlin noise at `scale` cycles per meter)."""
    bm.normal_update()
    off = Vector((seed * 13.7, seed * 7.3, seed * 3.1))
    for v in bm.verts:
        v.co += v.normal * (amount * noise.noise(v.co * scale + off))
    bm.normal_update()


def rotate_verts(bm, pivot, angle_deg, axis="X"):
    """Rotate the whole bmesh about `pivot` (e.g. lean a cushion back)."""
    bmesh.ops.rotate(bm, verts=bm.verts, cent=Vector(pivot),
                     matrix=Matrix.Rotation(math.radians(angle_deg), 3, axis))
    bm.normal_update()


def pillow(size=(0.45, 0.45), thickness=0.15, res=30, cord=0.004, pinch=0.07, fullness=0.95,
           folds=0.010, fold_count=7.0, edge_ripple=0.003, seed=1.0, seam_attr=SEAM_ATTR):
    """Knife-edge throw pillow as a new bmesh, centered on the origin, lying
    flat (panels face +Z/-Z). Returns the bmesh.

    size: panel size (x, y) before the edges pull in; thickness: stuffed
    height at the center; res: quads across a panel (denser near the edges);
    cord: welt radius; pinch: fraction the edge midpoints pull inward;
    fullness: exponent of the stuffed profile (lower = fuller); folds: height
    of the fabric folds radiating from the corners; edge_ripple: small waves
    along the edges. Vertices get the `seam_attr` distance (0 on the cord).
    """
    hx, hy = size[0] / 2, size[1] / 2
    tz = thickness / 2
    rnd = [noise.noise(Vector((seed * 3.1 + i, seed * 1.7, 0.5))) for i in range(8)]

    def warp(t):
        return math.copysign(1.0 - (1.0 - abs(t)) ** 1.35, t)

    params = [warp(2.0 * i / res - 1.0) for i in range(res + 1)]
    corners = [(sx, sy) for sx in (-1, 1) for sy in (-1, 1)]

    def panel_z(u, v, sgn):
        x, y = u * hx, v * hy
        f = max(0.0, (1.0 - abs(u) ** 2.0) * (1.0 - abs(v) ** 2.0)) ** fullness
        z = cord + (tz - cord) * f
        # folds radiating from the corners
        for ci, (sx, sy) in enumerate(corners):
            dx, dy = sx * hx - x, sy * hy - y
            dist = math.hypot(dx, dy)
            if dist > 0.2:
                continue
            ang = math.atan2(sy * dy, sx * dx) - math.pi / 4  # 0 on the diagonal, +-45 deg on the edges
            amp = folds * (1.0 - math.exp(-(dist / 0.03) ** 2)) * math.exp(-(dist / 0.10) ** 2)
            z += amp * math.sin(ang * fold_count + rnd[ci] * 3.0 + (0.0 if sgn > 0 else 1.3))
        # ripples along the edges, fading inward and toward the corners (the folds own those)
        de = min(hx - abs(x), hy - abs(y))
        along = y if hx - abs(x) < hy - abs(y) else x
        cmin = min(math.hypot(sx * hx - x, sy * hy - y) for sx, sy in corners)
        z += (edge_ripple * math.exp(-(de / 0.03) ** 2) * (1.0 - math.exp(-(cmin / 0.07) ** 2))
              * math.sin(along * 2 * math.pi / 0.07 + rnd[4 + (sgn > 0)] * 4))
        return sgn * z

    def pinched(u, v):
        x, y = u * hx, v * hy
        return (x * (1.0 - pinch * (1.0 - v * v)), y * (1.0 - pinch * (1.0 - u * u)))

    bm = bmesh.new()
    layer = bm.verts.layers.float.new(seam_attr)
    grids = {}
    for sgn in (1.0, -1.0):
        g = []
        for u in params:
            row = []
            for v in params:
                x, y = pinched(u, v)
                vert = bm.verts.new((x, y, panel_z(u, v, sgn)))
                vert[layer] = min(FAR, cord * math.pi / 2 + min(hx * (1 - abs(u)), hy * (1 - abs(v))))
                row.append(vert)
            g.append(row)
        grids[sgn] = g
        for i in range(res):
            for j in range(res):
                q = [g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]]
                bm.faces.new(q if sgn > 0 else list(reversed(q)))

    # perimeter loop (counter-clockwise seen from +Z), as grid indices
    loop = ([(i, 0) for i in range(res)] + [(res, j) for j in range(res)]
            + [(i, res) for i in range(res, 0, -1)] + [(0, j) for j in range(res, 0, -1)])
    n = len(loop)
    phis = [math.radians(a) for a in (45.0, 0.0, -45.0)]
    rings = []
    for k, (i, j) in enumerate(loop):
        top, bot = grids[1.0][i][j], grids[-1.0][i][j]
        pa = grids[1.0][loop[(k - 1) % n][0]][loop[(k - 1) % n][1]].co
        pb = grids[1.0][loop[(k + 1) % n][0]][loop[(k + 1) % n][1]].co
        t = Vector((pb.x - pa.x, pb.y - pa.y, 0.0)).normalized()
        out = Vector((t.y, -t.x, 0.0))  # outward for a counter-clockwise loop
        base = (top.co + bot.co) / 2
        half = (top.co.z - bot.co.z) / 2
        ring = [top]
        for phi in phis:
            vert = bm.verts.new(base + out * (cord * math.cos(phi)) + Vector((0, 0, half * math.sin(phi))))
            vert[layer] = cord * abs(phi)
            ring.append(vert)
        ring.append(bot)
        top[layer] = cord * math.pi / 2
        bot[layer] = cord * math.pi / 2
        rings.append(ring)
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for s in range(len(a) - 1):
            bm.faces.new([a[s], a[s + 1], b[s + 1], b[s]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm


def join(objs, name):
    """Join mesh objects into the first one, renamed `name` (mesh too)."""
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def remove_attribute(ob, name=SEAM_ATTR):
    """Drop a build-time attribute (e.g. `seam`) so it doesn't reach the glb."""
    a = ob.data.attributes.get(name)
    if a is not None:
        ob.data.attributes.remove(a)


# ---------------------------------------------------------------------------
# Graph helpers and fabric layers (use with arcology_blender.shading.Graph)
# ---------------------------------------------------------------------------
def attribute(g, name):
    """Float value of a mesh attribute (interpolated across faces)."""
    n = g.nodes.new("ShaderNodeAttribute")
    n.attribute_type = "GEOMETRY"
    n.attribute_name = name
    return n.outputs["Fac"]


def dist_xy(g, cx, cy):
    """Distance in world x/y from (cx, cy)."""
    dx, dy = g.sub(g.x, cx), g.sub(g.y, cy)
    return g.math("SQRT", g.add(g.mul(dx, dx), g.mul(dy, dy)))


def fabric_base(g, color, rough=0.90, heather=0.05, slub=0.04, mottle=0.07, weave=0.00022,
                slub_height=0.00012, mottle_height=0.00006):
    """Woven upholstery: medium-scale heathering (a few cm, +-heather), yarn
    slubs stretched along world X (+-slub), a two-tone yarn mottle at about
    1 cm (+-mottle; the finest color detail that survives mipmapping without
    shimmer) and a soft, low weave relief. Keep rough high (0.88-0.95):
    lower values read as leather or vinyl. Returns (base, rough, height in m)."""
    h = g.sub(g.noise(9.0, 3.0, 0.55), 0.5)
    s = g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vec(30.0, 150.0, 150.0)), 0.5)
    m = g.sub(g.maprange(g.noise(95.0, 2.0, 0.6), 0.35, 0.65), 0.5)
    f = g.add(1.0, g.add(g.add(g.mul(h, 2 * heather), g.mul(s, 2 * slub)), g.mul(m, 2 * mottle)))
    base = g.scale_color(color, f)
    r = g.add(rough, g.add(g.mul(h, 0.06), g.mul(m, 0.04)))
    height = g.add(g.mul(g.noise(240.0, 2.0, 0.5), weave),
                   g.add(g.mul(s, slub_height), g.mul(m, mottle_height)))
    return base, r, height


def welt(g, base, rough, height, attr=SEAM_ATTR, cord=0.005, groove=0.0035, bead=0.0022,
         darker=0.28, lighter=0.05, shinier=0.06):
    """Piping along the seams: a rounded cord (1 at the seam, 0 at `cord`
    meters) and a darker stitch groove just outside it. The cord's crest is
    a little lighter and smoother (it rubs first)."""
    d = attribute(g, attr)
    cordm = g.maprange(d, cord, 0.0)
    groovem = g.band(d, cord, cord + groove, 0.0012)
    height = g.add(height, g.sub(g.mul(cordm, bead), g.mul(groovem, bead * 0.6)))
    base = g.scale_color(base, g.add(g.sub(1.0, g.mul(groovem, darker)), g.mul(cordm, lighter)))
    rough = g.sub(rough, g.mul(cordm, shinier))
    return base, rough, height


def creases(g, base, height, mask, stretch=(22.0, 6.0, 12.0), depth=0.0012, sharp=0.72, darker=0.10):
    """Fabric creases inside a 0..1 mask: valleys along the 0.5 contours of a
    noise stretched by `stretch` (world x, y, z; small = long creases along
    that axis), slightly darker in the fold."""
    n = g.noise(1.0, 2.0, 0.5, vector=g.vec(*stretch))
    ridge = g.sub(1.0, g.math("ABSOLUTE", g.sub(g.mul(n, 2.0), 1.0)))
    c = g.mul(g.maprange(ridge, sharp, 1.0), mask)
    height = g.sub(height, g.mul(c, depth))
    base = g.scale_color(base, g.sub(1.0, g.mul(c, darker)))
    return base, height


def rub(g, base, rough, mask, shinier=0.20, tint=0.0):
    """Abrasion inside a 0..1 mask: compressed fibers are smoother (a soft
    shine); tint > 0 lightens (worn fuzz), < 0 darkens (skin oils)."""
    rough = g.sub(rough, g.mul(mask, shinier))
    base = g.scale_color(base, g.add(1.0, g.mul(mask, tint)))
    return base, rough


def pilling(g, base, height, mask, scale=140.0, amount=0.0005, lighter=0.05):
    """Small fuzz balls inside a 0..1 mask (low contrast; they sit on worn areas)."""
    p = g.mul(g.maprange(g.noise(scale, 1.0, 0.5), 0.60, 0.70), mask)
    height = g.add(height, g.mul(p, amount))
    base = g.scale_color(base, g.add(1.0, g.mul(p, lighter)))
    return base, height


def stain(g, base, rough, center, radius, z_band=0.03, strength=0.12, ring=0.18,
          color=(0.045, 0.034, 0.020)):
    """A faint dried spill on an upward-facing surface: an irregular disc
    around world `center` (x, y, z) with a darker tide mark at its rim."""
    cx, cy, cz = center
    d = g.add(dist_xy(g, cx, cy), g.mul(g.sub(g.noise(28.0, 2.0), 0.5), radius * 0.6))
    region = g.mul(g.band(g.z, cz - z_band, cz + z_band, 0.01), g.maprange(g.nz, 0.4, 0.8))
    inside = g.maprange(d, radius, radius * 0.75)
    rim = g.band(d, radius * 0.86, radius, radius * 0.07)
    fac = g.mul(region, g.add(g.mul(inside, strength), g.mul(rim, ring)))
    base = g.mixc(fac, base, color)
    rough = g.sub(rough, g.mul(fac, 0.25))
    return base, rough


def fabric_finish(g, base, rough, height):
    """Normal from the accumulated height (meters) and connect the BSDF."""
    return g.finish(base, rough, 0.0, g.bump(height, 1.0, 1.0))
