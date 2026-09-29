"""Cloth: simulated drapes, analytic drapes, garments and height-field helpers (D-028).

Two ways to lay a sheet over something (bedding, throws, tablecloths, curtains):

Simulation (Blender's cloth solver; realistic folds, slower; from the bed, Opus 5.5):

    bm = cloth_grid(width, length, spacing, place)       # flat sheet mapped into a start pose
    ob = geo.new_object(name, bm, coll, material=m)
    cloth_settle(ob, [(mattress, 0.03), (frame, 0.03)], frames=70, bending=3.0)
    thicken(ob, 0.03, keep_under_attr=..., drop_front_attr=...)
    soft_bounds([ob, ...], lo=..., hi=...)                # after the last simulation

    The simulated surface is the cloth's *front* (top) face; `thicken` grows
    the thickness behind it, so collider distances equal the cloth thickness.
    Masks for thicken come from the flat coordinates (`U_ATTR`, `S_ATTR`) and
    `soft.SEAM_ATTR` via `geo.set_float_attr`; remove them before export.

Analytic (`drape`: a rounded-rectangle top from a height callback, hanging
sides with folds; instant and fully controlled; from the padded bed, Fable
5.1). Build the height callback from `lumps`, `ridge` and `smoothstep`.

Garments: `hanging_garment` (a shirt or jacket on a hanger).
"""

import math

import bmesh
import bpy
from mathutils import Vector, noise

from . import soft
from .soft import FAR, SEAM_ATTR

U_ATTR = "cloth_u"
S_ATTR = "cloth_s"


# --- height-field helpers (for start poses and height callbacks) ----------------------
def smoothstep(x, a, b):
    """0 below a, 1 above b, Hermite in between."""
    if b == a:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def ridge(x, y, a, b, amp, width, taper=0.15):
    """Height of a soft fold ridge along the segment a-b (world x/y): a Gaussian
    of `amp` meters and `width` (1/e half width) across the line, fading over
    `taper` meters at both ends. Negative amp is a furrow."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return 0.0
    t = ((x - ax) * dx + (y - ay) * dy) / l2
    tc = max(0.0, min(1.0, t))
    dist = math.hypot(x - (ax + tc * dx), y - (ay + tc * dy))
    length = math.sqrt(l2)
    end = smoothstep(min(t * length, (1.0 - t) * length), 0.0, taper)
    return amp * math.exp(-(dist / width) ** 2) * end


def lumps(x, y, amp, scale, seed=0.0, octaves=2):
    """Filling lumps for a height callback: Perlin noise at `scale` features per
    meter, +-amp meters, with a half-amplitude octave at twice the frequency."""
    p = Vector((x * scale, y * scale, seed))
    h = noise.noise(p)
    if octaves > 1:
        h += 0.5 * noise.noise(p * 2.1 + Vector((3.7, 1.3, 9.1)))
    return amp * h


def bumps(x, y, amount, scale, seed=0.0):
    """Non-negative low-frequency height (0..amount) for rumpled start poses."""
    return amount * max(0.0, noise.noise(Vector((x * scale + seed * 3.7, y * scale - seed * 1.3, seed))) + 0.15) / 1.15


# --- simulated cloth --------------------------------------------------------------------
def cloth_grid(width, length, spacing, place, seam_attr=SEAM_ATTR, corner_radius=0.0):
    """Rectangular cloth as a new bmesh of quads, mapped into a start pose.

    The flat sheet has coordinates u in [-width/2, width/2] (across) and
    s in [0, length] (along). `place(u, s)` returns the world position of
    that point in the start pose (e.g. flat above a bed, or with a fold,
    see `fold_path`); keep it isometric-ish so the simulation starts near
    rest. Faces are oriented so that for place(u, s) = (u, s, z) the front
    faces +Z.

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
    lying back toward -Y on top of itself (a duvet's turn-down). Returns
    f(s, fold_y=fold_y) -> (y, z, layer) with layer 0 below, 1 on the arc,
    2 on top."""
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
    distance is the collider's outer thickness, i.e. how far the simulated
    (front) surface rests from it; use the cloth thickness so `thicken`
    fills the gap. Collision modifiers are removed again afterwards. Stiffer
    `bending` gives broad folds (thick duvets, felt); low values give fine
    wrinkles (sheets, silk). `mass` is per vertex (kg), so it scales with
    the grid density: keep it small (0.02-0.3) or dense cloth sags through.
    shrink < 0 makes the cloth that much larger than its start mesh (e.g.
    -0.03 = 3 %), so it buckles into soft wrinkles as it settles: the easy
    way to get a rumpled, lived-in drape. Uniform expansion mostly slides
    off into the hanging parts, so for wrinkles in one place (where someone
    slept) give shrink_attr, a 0..1 float vertex attribute: the factor goes
    from `shrink` (at 0) to `shrink_max` (at 1, e.g. -0.10), and the local
    excess buckles in place (Blender clamps shrink_max at >= 0, so the
    weights are inverted internally when shrink_max < shrink). Deterministic
    for the same inputs. Returns the object.
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
    Even thickness is off and the offset clamped: with even thickness,
    sharp wrinkles shoot spikes through the back.
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


# --- analytic drape ---------------------------------------------------------------------
RIM_PROFILE = ((0.42, 0.28), (0.42, 0.78), (-0.25, 1.0))


def shell_rim(bm, loop, inward, thickness, profile=RIM_PROFILE):
    """Close the boundary of an open surface with a rounded rim: `loop` is the
    boundary vertices in order (counter-clockwise seen from the surface's
    front), `inward` the interior neighbor of each (for the tangent). Each
    profile point (out, down) is in units of `thickness`: out along the
    surface away from the interior, down along the negative normal. Returns
    the new faces. The default profile is a half-round edge that turns
    under, like the hem of a duvet."""
    n = len(loop)
    rings = []
    for v, vin in zip(loop, inward):
        nrm = v.normal.copy()
        t_in = vin.co - v.co
        t_in -= nrm * t_in.dot(nrm)
        if t_in.length < 1e-9:
            t_in = Vector((1.0, 0.0, 0.0))
        t_in.normalize()
        out = -t_in
        ring = [v]
        for o, d in profile:
            ring.append(bm.verts.new(v.co + out * (o * thickness) - nrm * (d * thickness)))
        rings.append(ring)
    faces = []
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for s in range(len(a) - 1):
            faces.append(bm.faces.new([a[s], a[s + 1], b[s + 1], b[s]]))
    return faces


def _rrect(u, v, rect, rc):
    """Rounded rectangle helper: for a point (u, v) return (d, b, n, s):
    signed distance to the boundary (> 0 outside), the closest boundary point,
    the outward normal there and the perimeter coordinate s (meters,
    counter-clockwise from the start of the -y side). b, n, s are None inside."""
    x0, y0, x1, y1 = rect
    ix0, ix1, iy0, iy1 = x0 + rc, x1 - rc, y0 + rc, y1 - rc
    qx, qy = min(max(u, ix0), ix1), min(max(v, iy0), iy1)
    dx, dy = u - qx, v - qy
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return -min(u - x0, x1 - u, v - y0, y1 - v), None, None, None
    nx, ny = dx / length, dy / length
    wi, hi, arc = ix1 - ix0, iy1 - iy0, rc * math.pi / 2
    if dy < 0 and dx == 0:
        s = qx - ix0
    elif dx > 0 and dy == 0:
        s = wi + arc + (qy - iy0)
    elif dy > 0 and dx == 0:
        s = wi + 2 * arc + hi + (ix1 - qx)
    elif dx < 0 and dy == 0:
        s = 2 * wi + 3 * arc + hi + (iy1 - qy)
    else:
        th = math.atan2(dy, dx)
        if dx > 0 and dy < 0:
            s = wi + (th + math.pi / 2) * rc
        elif dx > 0 and dy > 0:
            s = wi + arc + hi + th * rc
        elif dx < 0 and dy > 0:
            s = 2 * wi + 2 * arc + hi + (th - math.pi / 2) * rc
        else:
            s = 2 * wi + 3 * arc + 2 * hi + (th + math.pi) * rc
    return length - rc, (qx + nx * rc, qy + ny * rc), (nx, ny), s


def _perimeter(rect, rc):
    x0, y0, x1, y1 = rect
    return 2 * (x1 - x0 - 2 * rc) + 2 * (y1 - y0 - 2 * rc) + 2 * math.pi * rc


def _drape_coords(lo, hi, ov_lo, ov_hi, r_lo, r_hi, res):
    """Cloth coordinates along one axis: uniform over the top, 4 steps over
    each roll, then ~0.8 res steps down the hang."""
    n = max(1, int(round((hi - lo) / res)))
    inner = [lo + (hi - lo) * i / n for i in range(n + 1)]

    def ext(ov, r):
        if ov <= 1e-9:
            return []
        arc = r * math.pi / 2
        a = min(ov, arc)
        pts = [a * j / 4 for j in range(1, 5)] if a > 0 else []
        if ov > arc + 1e-6:
            m = max(1, int(round((ov - arc) / (res * 0.8))))
            pts += [arc + (ov - arc) * j / m for j in range(1, m + 1)]
        return pts

    return [lo - d for d in reversed(ext(ov_lo, r_lo))] + inner + [hi + d for d in ext(ov_hi, r_hi)]


def _soft_clamp(t):
    """t for t <= 0.85, then saturating toward ~1.12 (a cloth corner hangs a
    little lower than the sides but doesn't reach the floor)."""
    if t <= 0.85:
        return t
    return 0.85 + 0.27 * math.tanh((t - 0.85) / 0.27)


def drape(rect, top_z, overhang, thickness, res=0.03, radius=0.04, corner_radius=0.08,
          fold_amp=0.010, fold_period=0.18, hem_wave=0.006, flare=0.05, seed=0.0, rim_profile=RIM_PROFILE):
    """Cloth sheet lying on a rounded rectangle and hanging over its edges, as
    a new bmesh (world coordinates): a duvet on a mattress, a throw over an
    arm, a tablecloth. No simulation.

    rect: (x0, y0, x1, y1), the covered top (a mattress top; corners rounded
    by corner_radius so the hanging cloth turns the corner instead of
    stretching). top_z(x, y): height of the cloth's top surface over the top
    region, including the cloth's thickness and any rumples (see `ridge`,
    `lumps`). overhang: {"-x": m, "+x": m, "-y": m, "+y": m}, cloth length
    past each edge (missing = 0: the cloth ends at that edge); radius: roll
    radius at the edges, a float or the same kind of dict (a fold-back edge
    gets a fatter roll). The hanging cloth gets vertical folds (fold_amp
    meters, fold_period meters along the edge, growing toward the hem), a
    wavy hem (+-hem_wave) and flares outward by `flare` meters per meter of
    drop. Cloth corners hang up to ~12% lower than the sides. The boundary is
    closed with `shell_rim` (thickness, rim_profile). Quads of about `res`.
    """
    x0, y0, x1, y1 = rect
    ov = {k: overhang.get(k, 0.0) for k in ("-x", "+x", "-y", "+y")}
    rad = {k: (radius.get(k, 0.04) if isinstance(radius, dict) else radius) for k in ov}
    us = _drape_coords(x0, x1, ov["-x"], ov["+x"], rad["-x"], rad["+x"], res)
    vs = _drape_coords(y0, y1, ov["-y"], ov["+y"], rad["-y"], rad["+y"], res)
    per = _perimeter(rect, corner_radius)
    k1 = max(1, int(round(per / fold_period)))
    k2 = max(1, int(round(per / (fold_period * 2.7))))
    ph1, ph2 = seed * 2.39, seed * 1.17 + 0.8

    def blend(d, n):
        """Per-side values blended by the outward normal."""
        wx, wy = abs(n[0]), abs(n[1])
        kx, ky = ("+x" if n[0] > 0 else "-x"), ("+y" if n[1] > 0 else "-y")
        return (wx * d[kx] + wy * d[ky]) / max(wx + wy, 1e-9)

    def point(u, v):
        d, b, n, s = _rrect(u, v, rect, corner_radius)
        if d <= 0.0:
            return Vector((u, v, top_z(u, v)))
        r = blend(rad, n)
        total = blend(ov, n)
        arc = r * math.pi / 2
        ztop = top_z(b[0], b[1])
        nv = Vector((n[0], n[1], 0.0))
        base = Vector((b[0], b[1], 0.0))
        max_drop = max(total - arc, 1e-6)
        if d < arc:
            a = d / r
            p = base + nv * (r * math.sin(a))
            p.z = ztop - r * (1.0 - math.cos(a))
            drop = 0.0
        else:
            drop = max_drop * _soft_clamp((d - arc) / max_drop)
            p = base + nv * (r + flare * drop)
            p.z = ztop - r - drop
        prog = min(1.0, d / max(total, 1e-6)) ** 1.5
        if fold_amp and total > arc:
            amp_mod = 0.6 + 0.4 * noise.noise(Vector((s * 2.0, seed, 0.0)))
            f = (math.sin(2 * math.pi * k1 * s / per + ph1)
                 + 0.5 * math.sin(2 * math.pi * k2 * s / per + ph2))
            p += nv * (fold_amp * amp_mod * prog * f)
        if hem_wave and drop > 0:
            p.z -= hem_wave * (drop / max_drop) * (0.5 + 0.5 * math.sin(2 * math.pi * k2 * s / per + ph2 * 1.7))
        return p

    bm = bmesh.new()
    grid = [[bm.verts.new(point(u, v)) for v in vs] for u in us]
    nu, nv_ = len(us), len(vs)
    for i in range(nu - 1):
        for j in range(nv_ - 1):
            bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    bm.normal_update()
    loop_idx = ([(i, 0) for i in range(nu - 1)] + [(nu - 1, j) for j in range(nv_ - 1)]
                + [(i, nv_ - 1) for i in range(nu - 1, 0, -1)] + [(0, j) for j in range(nv_ - 1, 0, -1)])

    def inward(i, j):
        ii = 1 if i == 0 else (nu - 2 if i == nu - 1 else i)
        jj = 1 if j == 0 else (nv_ - 2 if j == nv_ - 1 else j)
        return grid[ii][jj]

    shell_rim(bm, [grid[i][j] for i, j in loop_idx], [inward(i, j) for i, j in loop_idx], thickness, rim_profile)
    bm.normal_update()
    return bm


# --- garments -----------------------------------------------------------------------------
def hanging_garment(width=0.42, length=0.68, thick=0.04, shoulder_drop=0.05, taper=0.12,
                    step=(0.04, 0.02, 0.05), drape=0.008, drape_period=0.13, folds=0.003, seed=0.0):
    """A shirt or jacket on a hanger as a new bmesh: a soft slab in the XZ
    plane (panels face +-Y, shoulders along X) with sloping shoulders, thinner
    and narrower toward the hem, vertical drape folds (`drape` amplitude,
    `drape_period` across) that grow toward the hem, and low-frequency
    wrinkles. The shoulder line is z = 0 at the neck, the hanger plane y = 0;
    move it into place with bmesh.ops.translate. It carries `soft.SEAM_ATTR`
    (remove it if the material doesn't use it)."""
    bm = soft.soft_box((0.0, 0.0, -length / 2), (width, thick, length), min(0.015, thick * 0.45),
                       step=step, panel_axis=1)
    for v in bm.verts:
        x, z = v.co.x, v.co.z
        d = max(0.0, min(1.0, -z / length))            # 0 at the shoulders, 1 at the hem
        top = max(0.0, min(1.0, 1.0 + z / 0.30))        # 1 at the shoulders, 0 from 30 cm down
        v.co.z -= shoulder_drop * (abs(x) / (width / 2)) * top
        v.co.y *= 1.0 - 0.55 * d
        v.co.x *= 1.0 - taper * d
        v.co.y += drape * (0.25 + 0.75 * d) * math.sin(x * 2 * math.pi / drape_period + seed * 1.7)
    if folds:
        soft.jitter(bm, folds, 7.0, seed)
    bm.normal_update()
    return bm
