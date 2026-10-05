"""Faces for characters (D-037): eyeballs, eyelids, blink shapes, cards that follow the
lids, and painting an existing UV layout by surface position (makeup).

Eye frame (`EyeFrame`): the lids turn about a lid axis through the eyeball's rotation
center, from the inner to the outer corner. Cylindrical coordinates about it: `s` along
the axis (m), `phi` the angle around it from the eye's forward direction toward up
(degrees, the upper lid has phi > 0), `rho` the distance from the axis (m). Turning a
point about the axis keeps its distance from the eye's center, so a lid that clears the
eyeball keeps clearing it while it closes.

Opening (`measure_opening`): rays from the axis, in the plane across it at each `s`, scan
the angles around it; the free run nearest the forward direction is the opening, its
edges the lid margins (`Opening.up(s)`, `Opening.low(s)`), closed where no ray is free
(beyond the corners). Works on any topology (MPFB's lids fold into a closed pocket behind
the eyeball; the pocket is never "the margin" because rays start at the axis).

Lid motion: `lid_weights` says how much of a lid's turn a point takes (1 on the lid plate
next to the margin, fading toward the brow and cheek), `blink_turns` the turn per point
that closes both lids on a meeting line, `EyeFrame.turn` applies it. Shape keys:
`set_shape_key`.

Eyeball (`eyeball`): a sphere with a cornea bulge, open at the back (hidden in the head),
polar UVs: one disc for both eyes, the pupil at the center, the iris out to `EyeUV.iris`,
`u` toward the temple and `v` up on both sides. `eye_textures` paints it (numpy): iris
fibers, crypts, collarette, a dark limbal ring, pupil, warm sclera with veins, wet
roughness, lid occlusion and the cornea's dome as a normal map; one opaque material, no
transparent cornea shell. A geometric bulge (`eyeball(cornea=...)`) crosses the lid
margins when the eye turns up or down; a sphere with the normal-mapped dome never does.

Painting by position: `uv_positions` rasterizes a mesh's UV faces into texel positions
and normals (world space), so a layer can be composited into an existing texture from
3D masks (`dilate` grows it over island edges).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector


def smoothstep(x, a, b):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def srgb(hex_color):
    """'#5B3F86' -> linear RGB tuple."""
    h = hex_color.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


# --- eye frame and opening -------------------------------------------------------------------
class EyeFrame:
    """Lid axis frame of one eye: center `c`, axis `A` (inner to outer corner), forward `F`
    and up `U` orthogonal to it (numpy float64 vectors, armature/world space)."""

    def __init__(self, center, axis, forward=(0.0, -1.0, 0.0), up=(0.0, 0.0, 1.0)):
        self.c = np.array(center, dtype=np.float64)
        a = np.array(axis, dtype=np.float64)
        self.A = a / np.linalg.norm(a)
        f = np.array(forward, dtype=np.float64)
        f = f - self.A * f.dot(self.A)
        self.F = f / np.linalg.norm(f)
        u = np.array(up, dtype=np.float64)
        u = u - self.A * u.dot(self.A) - self.F * u.dot(self.F)
        self.U = u / np.linalg.norm(u)

    def coords(self, points):
        """(s, phi degrees, rho) of points (N, 3)."""
        d = np.asarray(points, dtype=np.float64) - self.c
        s = d @ self.A
        x, y = d @ self.F, d @ self.U
        return s, np.degrees(np.arctan2(y, x)), np.hypot(x, y)

    def direction(self, phi):
        p = math.radians(phi)
        return self.F * math.cos(p) + self.U * math.sin(p)

    def point(self, s, phi, rho):
        s, phi, rho = (np.asarray(v, dtype=np.float64) for v in (s, phi, rho))
        p = np.radians(phi)
        return (self.c + s[..., None] * self.A + rho[..., None] * (np.cos(p)[..., None] * self.F
                                                                   + np.sin(p)[..., None] * self.U))

    def turn(self, points, degrees):
        """Points turned about the axis by per-point angles (positive = from forward toward up)."""
        d = np.asarray(points, dtype=np.float64) - self.c
        s = d @ self.A
        x, y = d @ self.F, d @ self.U
        rest = d - s[:, None] * self.A - x[:, None] * self.F - y[:, None] * self.U
        a = np.radians(np.asarray(degrees, dtype=np.float64))
        ca, sa = np.cos(a), np.sin(a)
        x2, y2 = ca * x - sa * y, sa * x + ca * y
        return self.c + s[:, None] * self.A + x2[:, None] * self.F + y2[:, None] * self.U + rest


class Opening:
    """Measured lid margins of one eye: samples `s` with the margin angles `up`/`low`
    (degrees, NaN where closed); `corners` (s_in, s_out). Queries clamp to closed
    (up == low) beyond the corners, so a lid's turn fades to zero there."""

    def __init__(self, s, up, low, rho_up, rho_low, step):
        self.s, self.up_raw, self.low_raw = s, up, low
        self.rho_up_raw, self.rho_low_raw = rho_up, rho_low
        open_ = np.isfinite(up) & np.isfinite(low)
        if not open_.any():
            raise ValueError("eye opening: no open ray (wrong center or axis?)")
        idx = np.where(open_)[0]
        s0, s1 = idx[0], idx[-1]
        self.corners = (float(s[s0]), float(s[s1]))
        ss, uu, ll = s[s0:s1 + 1], up[s0:s1 + 1].copy(), low[s0:s1 + 1].copy()
        bad = ~(np.isfinite(uu) & np.isfinite(ll))     # a closed sample inside: interpolate over it
        if bad.any():
            uu[bad] = np.interp(ss[bad], ss[~bad], uu[~bad])
            ll[bad] = np.interp(ss[bad], ss[~bad], ll[~bad])
        m0, m1 = 0.5 * (uu[0] + ll[0]), 0.5 * (uu[-1] + ll[-1])
        self._s = np.concatenate([[ss[0] - step], ss, [ss[-1] + step]])
        self._up = np.concatenate([[m0], uu, [m1]])
        self._low = np.concatenate([[m0], ll, [m1]])
        ru, rl = rho_up[s0:s1 + 1], rho_low[s0:s1 + 1]
        self._rho_up = np.concatenate([[ru[0]], np.where(np.isfinite(ru), ru, np.nanmean(ru)), [ru[-1]]])
        self._rho_low = np.concatenate([[rl[0]], np.where(np.isfinite(rl), rl, np.nanmean(rl)), [rl[-1]]])
        self.gap_max = float(np.max(self._up - self._low))

    def up(self, s):
        return np.interp(s, self._s, self._up)

    def low(self, s):
        return np.interp(s, self._s, self._low)

    def rho_up(self, s):
        return np.interp(s, self._s, self._rho_up)

    def rho_low(self, s):
        return np.interp(s, self._s, self._rho_low)

    def mid(self, s):
        return 0.5 * (self.up(s) + self.low(s))

    def profile(self, s, power=0.5):
        """0 at the corners .. 1 where the opening is tallest (for turns uniform along the lid)."""
        return np.clip((self.up(s) - self.low(s)) / self.gap_max, 0.0, 1.0) ** power

    def margin_points(self, frame, side="up", n=40):
        """Points on a margin (the first hits), inner to outer corner."""
        s = np.linspace(self.corners[0], self.corners[1], n)
        if side == "up":
            return frame.point(s, self.up(s), self.rho_up(s))
        return frame.point(s, self.low(s), self.rho_low(s))


def measure_opening(bvh, frame, half_width=0.022, step=0.00025, max_dist=0.025, phi_step=0.25, phi_max=60.0,
                    scan_step=0.5):
    """Measure the eye opening on a skin BVH (`mathutils.bvhtree`, the eyeball not in it).
    At each `s` the rays from the axis scan -phi_max..phi_max for free directions; the
    free run nearest the forward direction (it needn't contain it: toward the corners the
    opening dips below or rises above the axis) is the opening, its edges refined by
    bisection. Returns an `Opening`."""
    ss = np.arange(-half_width, half_width + 1e-9, step)
    up = np.full(len(ss), np.nan)
    low = np.full(len(ss), np.nan)
    rho_up = np.full(len(ss), np.nan)
    rho_low = np.full(len(ss), np.nan)
    scan = np.arange(-phi_max, phi_max + 1e-9, scan_step)

    def hit(o, phi):
        h = bvh.ray_cast(o, Vector(frame.direction(phi)), max_dist)
        return h[3] if h[0] is not None else None

    def edge(o, free, blocked):
        for _ in range(9):
            m = 0.5 * (free + blocked)
            if hit(o, m) is None:
                free = m
            else:
                blocked = m
        return blocked

    for i, s in enumerate(ss):
        o = Vector(frame.c + frame.A * s)
        free = np.array([hit(o, p) is None for p in scan])
        if not free.any():
            continue
        runs, k = [], 0
        while k < len(scan):
            if free[k]:
                j = k
                while j + 1 < len(scan) and free[j + 1]:
                    j += 1
                runs.append((k, j))
                k = j + 1
            else:
                k += 1
        a, b = min(runs, key=lambda r: 0.0 if scan[r[0]] <= 0.0 <= scan[r[1]]
                   else min(abs(scan[r[0]]), abs(scan[r[1]])))
        if a == 0 or b == len(scan) - 1:          # open to the scan's end: not a lid opening
            continue
        up[i] = edge(o, scan[b], scan[b + 1])
        low[i] = edge(o, scan[a], scan[a - 1])
        rho_up[i] = hit(o, up[i])
        rho_low[i] = hit(o, low[i])
    return Opening(ss, up, low, rho_up, rho_low, step)


def lid_weights(frame, opening, points, upper=(14.0, 40.0), lower=(6.0, 22.0), rho=(0.024, 0.031)):
    """Per point (upper weight, lower weight): how much of the upper/lower lid's turn it
    takes. 1 up to upper[0] degrees above the upper margin (the lid plate), 0 from
    upper[1] on (the brow); the lower lid likewise below its margin; both fade out with
    the distance from the axis between rho[0] and rho[1]. Points behind the eye get 0."""
    s, phi, r = frame.coords(points)
    up, low = opening.up(s), opening.low(s)
    mid = 0.5 * (up + low)
    fade = 1.0 - smoothstep(r, rho[0], rho[1])
    w_up = np.where(phi >= mid, 1.0 - smoothstep(phi - up, upper[0], upper[1]), 0.0) * fade
    w_low = np.where(phi < mid, 1.0 - smoothstep(low - phi, lower[0], lower[1]), 0.0) * fade
    return w_up, w_low


def blink_turns(opening, s, meet=0.3, overshoot=1.0, lower_overshoot=0.0, corner_power=1.0):
    """(upper, lower) turn in degrees at `s` that closes the eye: both margins reach the
    meeting line `meet` of the way up from the lower margin, the upper one `overshoot`
    degrees further (it closes over the lower lid) and the lower one `lower_overshoot`
    degrees past it, both fading to zero at the corners as `opening.profile(s,
    corner_power)` (smaller powers keep more of the overlap toward the corners, where lids
    meeting edge to edge leave a slit)."""
    up, low = opening.up(s), opening.low(s)
    m = low + meet * (up - low)
    prof = opening.profile(s, corner_power)
    return m - up - overshoot * prof, m - low + lower_overshoot * prof


def margin_side(opening, frame, points):
    """+1 for points above the opening's middle line (upper lid), -1 below."""
    s, phi, _ = frame.coords(points)
    return np.where(phi >= opening.mid(s), 1, -1)


def push_clear(ob, center, radius, mask=None, iterations=6, keep=0.85):
    """Push the skin of `ob` (world = local coordinates) out to at least `radius` from
    `center` where its normal faces away from it (the outside of the lids), then spread
    the push to the neighbors (`iterations` rounds, each keeping `keep` of the
    neighbors' mean), so the lid margin moves as a whole. `mask(co) -> bool` limits it.
    Returns the largest push (m)."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("normal", nr)
    nr = nr.reshape(n, 3)
    d = co - np.asarray(center)
    r = np.linalg.norm(d, axis=1)
    radial = d / r[:, None]
    need = np.where((np.einsum("ij,ij->i", nr, radial) > 0.2) & (r < radius), radius - r, 0.0)
    if mask is not None:
        need *= np.array([bool(mask(p)) for p in co])
    push = need.copy()
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    for _ in range(iterations):
        acc = np.zeros(n)
        cnt = np.zeros(n)
        np.add.at(acc, ev[:, 0], push[ev[:, 1]])
        np.add.at(acc, ev[:, 1], push[ev[:, 0]])
        np.add.at(cnt, ev[:, 0], 1)
        np.add.at(cnt, ev[:, 1], 1)
        push = np.maximum(need, keep * acc / np.maximum(cnt, 1))
    co = co + radial * push[:, None]
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    return float(push.max())


def set_shape_key(ob, name, co):
    """Shape key `name` with positions `co` (N, 3, object-local); adds a Basis first."""
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    kb = ob.data.shape_keys.key_blocks.get(name) or ob.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set("co", np.asarray(co, dtype=np.float32).ravel())
    kb.value = 0.0
    return kb


def vertex_positions(ob):
    n = len(ob.data.vertices)
    co = np.empty(n * 3)
    ob.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


# --- eyeball -----------------------------------------------------------------------------------
class EyeUV:
    """Polar UV layout of `eyeball`: the radius in UV (0 at the pupil .. 0.5 at the disc's
    edge) is a piecewise-linear function of the angle from the eye's axis, so the iris
    gets most of the texture and the hidden back almost none."""

    def __init__(self, iris_deg, back_deg):
        self.iris = iris_deg
        self.back = back_deg
        self.knots_deg = np.array([0.0, iris_deg, iris_deg + 6.0, 60.0, back_deg])
        self.knots_r = np.array([0.0, 0.215, 0.27, 0.44, 0.497])

    def radius(self, theta_deg):
        return np.interp(theta_deg, self.knots_deg, self.knots_r)

    def theta(self, radius_uv):
        return np.interp(radius_uv, self.knots_r, self.knots_deg)


def cornea_height(theta_deg, iris_deg, height, transition=1.2):
    """Height of the cornea bulge over the eyeball sphere at an angle from the axis: a
    smooth dome (1 - t^2)^2, zero just past the limbus."""
    t = np.clip(np.asarray(theta_deg) / (iris_deg + transition), 0.0, 1.0)
    return height * (1.0 - t * t) ** 2


def eye_rings(iris_deg, back_deg):
    base = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, iris_deg - 2.0, iris_deg - 0.6, iris_deg + 0.8, iris_deg + 3.0,
            iris_deg + 7.0, 36.0, 46.0, 58.0, 72.0, 86.0, back_deg]
    return sorted({round(a, 3) for a in base if 0.0 <= a <= back_deg})


def eyeball(bm, center, forward, lateral, radius, iris_radius, cornea, segments=32, back_deg=100.0,
            rings=None, uv_layer="UVMap"):
    """Add one eyeball to `bm`: sphere `radius` about `center` looking along `forward`,
    a cornea bulge `cornea` m high over the iris (`iris_radius` m), open beyond
    `back_deg` degrees from the axis (hidden in the head). UVs: `EyeUV` disc, `u` toward
    `lateral` (the temple), `v` up. Returns (faces, EyeUV)."""
    c = Vector(center)
    f = Vector(forward).normalized()
    lat = Vector(lateral)
    lat = (lat - f * lat.dot(f)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    up = (up - f * up.dot(f) - lat * up.dot(lat)).normalized()
    iris_deg = math.degrees(math.asin(iris_radius / radius))
    layout = EyeUV(iris_deg, back_deg)
    rings = rings or eye_rings(iris_deg, back_deg)
    uv = bm.loops.layers.uv.get(uv_layer) or bm.loops.layers.uv.new(uv_layer)
    verts, uvs = [], []
    for th in rings:
        r = radius + float(cornea_height(th, iris_deg, cornea))
        t = math.radians(th)
        ring, ring_uv = [], []
        for k in range(1 if th == 0.0 else segments):
            psi = 2.0 * math.pi * k / segments
            d = f * math.cos(t) + (lat * math.cos(psi) + up * math.sin(psi)) * math.sin(t)
            ring.append(bm.verts.new(c + d * r))
            ru = float(layout.radius(th))
            ring_uv.append((0.5 + ru * math.cos(psi), 0.5 + ru * math.sin(psi)))
        verts.append(ring)
        uvs.append(ring_uv)
    faces = []
    for i in range(len(rings) - 1):
        a, b = verts[i], verts[i + 1]
        ua, ub = uvs[i], uvs[i + 1]
        for k in range(segments):
            k1 = (k + 1) % segments
            if len(a) == 1:
                fv, fu = (a[0], b[k], b[k1]), (ua[0], ub[k], ub[k1])
            else:
                fv, fu = (a[k], b[k], b[k1], a[k1]), (ua[k], ub[k], ub[k1], ua[k1])
            face = bm.faces.new(fv)
            for loop, q in zip(face.loops, fu):
                loop[uv].uv = q
            face.smooth = True
            faces.append(face)
    bm.normal_update()
    for face in faces:                       # outward, whichever way the frame turns
        if face.normal.dot(face.calc_center_median() - c) < 0.0:
            face.normal_flip()
    return faces, layout


def _seg_paint(img, alpha_img, p0, p1, w0, w1, a0, a1, color):
    """Antialiased segment from p0 to p1 (pixels) with widths and opacities ramping."""
    h, w = alpha_img.shape
    r = max(w0, w1) + 1.5
    x0, x1 = int(max(min(p0[0], p1[0]) - r, 0)), int(min(max(p0[0], p1[0]) + r + 1, w))
    y0, y1 = int(max(min(p0[1], p1[1]) - r, 0)), int(min(max(p0[1], p1[1]) + r + 1, h))
    if x0 >= x1 or y0 >= y1:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
    d = np.array(p1) - np.array(p0)
    L2 = max(d.dot(d), 1e-9)
    t = np.clip(((xs - p0[0]) * d[0] + (ys - p0[1]) * d[1]) / L2, 0.0, 1.0)
    dist = np.hypot(xs - (p0[0] + t * d[0]), ys - (p0[1] + t * d[1]))
    width = w0 + (w1 - w0) * t
    a = (a0 + (a1 - a0) * t) * np.clip(width * 0.5 + 0.5 - dist, 0.0, 1.0)
    cur = alpha_img[y0:y1, x0:x1]
    new = np.maximum(cur, a)
    gain = np.where(new > cur, (new - cur) / np.maximum(1.0 - cur, 1e-6), 0.0)
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1.0 - gain[..., None]) + np.asarray(color) * gain[..., None]
    alpha_img[y0:y1, x0:x1] = new


def eye_textures(size, layout, radius, iris_radius, style, cornea=0.001, seed=1):
    """Paint the `eyeball` UV disc. Returns (albedo, normal, orm) float arrays (size, size,
    3): albedo linear, normal tangent space (OpenGL, as glTF), ORM. The normal map gives a
    sphere the cornea's dome (`cornea` m high over the iris, `cornea_height`): its small,
    sharp highlight without geometry that could cross the lid margins. `style` (linear
    colors, fractions of the iris radius):
      pupil (radius fraction), pupil_color, ruff (pupillary ruff), inner (iris inside the
      collarette), mid, outer, limbal (dark ring), fleck (light flecks), crypt (dark),
      collarette (radius fraction), crypts (count), sclera, sclera_corner (toward the
      corners and the back), vein, veins (count), rough_cornea, rough_sclera, lid_shade
      (albedo darkening under the upper lid at rest), lid_ao."""
    rng = np.random.default_rng(seed)
    n = size
    yy, xx = np.mgrid[0:n, 0:n]
    du = (xx + 0.5) / n - 0.5
    dv = (yy + 0.5) / n - 0.5
    ru = np.hypot(du, dv)
    psi = np.arctan2(dv, du)
    theta = layout.theta(np.minimum(ru, layout.knots_r[-1]))
    th = np.radians(theta)
    t = np.sin(np.minimum(th, math.pi / 2)) * radius / iris_radius      # projected iris radius fraction
    S = style

    def col(name):
        return np.asarray(S[name], dtype=np.float64)

    def angular(kmin, kmax, count, drift, power=0.5):
        f = np.zeros_like(t)
        for _ in range(count):
            k = rng.integers(kmin, kmax)
            f += np.cos(k * psi + rng.uniform(0, 2 * math.pi) + rng.uniform(-drift, drift) * t) / k ** power
        return f / (np.abs(f).max() + 1e-9)

    # iris: radial fibers (wavy, broken up along the radius), collarette, crypts, furrows, flecks
    fib = angular(30, 260, 80, 5.0)
    fine = angular(200, 600, 50, 9.0, 0.0)
    breakup = angular(8, 40, 20, 14.0) * np.cos(2 * math.pi * t * 3.0 + 3.0 * angular(3, 9, 6, 4.0))
    lobes = angular(5, 17, 6, 0.0, 1.0)
    col_r = S["collarette"] + 0.035 * lobes
    pupil = S["pupil"]
    inner_zone = 1.0 - smoothstep(t, col_r - 0.025, col_r + 0.03)
    outer_zone = smoothstep(t, 0.60, 0.93)
    base = col("mid") * (1.0 - inner_zone[..., None]) + col("inner") * inner_zone[..., None]
    base = base * (1.0 - outer_zone[..., None]) + col("outer") * outer_zone[..., None]
    shade = 1.0 + 0.42 * fib + 0.16 * fine + 0.12 * breakup
    shade *= 1.0 + 0.10 * np.cos(2 * math.pi * t * 7.0 + 2.0 * lobes) * smoothstep(t, 0.6, 0.8)    # furrows
    iris = base * np.clip(shade, 0.25, 2.0)[..., None]
    ring = np.exp(-((t - col_r) / 0.02) ** 2) * (0.55 + 0.45 * fib)
    iris = iris + (col("fleck") - iris) * (0.40 * ring)[..., None]
    fl = np.clip((fib + 0.7 * fine - 0.5) * 2.2, 0.0, 1.0) * smoothstep(t, pupil + 0.02, pupil + 0.08) \
        * (1.0 - smoothstep(t, col_r + 0.05, col_r + 0.25))
    iris = iris + (col("fleck") - iris) * (0.50 * fl)[..., None]
    streak = np.clip((fib - 0.35) * 2.0, 0.0, 1.0) * smoothstep(t, col_r + 0.05, 0.6) * (1.0 - smoothstep(t, 0.75, 0.9))
    iris = iris + (col("fleck") - iris) * (0.25 * streak)[..., None]
    crypt = np.zeros_like(t)
    for _ in range(int(S.get("crypts", 34))):
        cp, ct = rng.uniform(-math.pi, math.pi), rng.uniform(S["collarette"] + 0.06, 0.82)
        sp, st = rng.uniform(0.03, 0.09), rng.uniform(0.025, 0.06)
        dp = np.angle(np.exp(1j * (psi - cp)))
        crypt = np.maximum(crypt, np.exp(-(dp / sp) ** 2 - ((t - ct) / st) ** 2))
    iris = iris + (col("crypt") - iris) * (0.6 * crypt)[..., None]
    ruff = np.exp(-((t - pupil - 0.012) / 0.014) ** 2)
    iris = iris + (col("ruff") - iris) * (0.85 * ruff)[..., None]
    limbal = smoothstep(t, 0.84, 0.985)
    iris = iris + (col("limbal") - iris) * (0.88 * limbal)[..., None]
    pup = 1.0 - smoothstep(t, pupil - 0.006, pupil + 0.006)
    iris = iris + (col("pupil_color") - iris) * pup[..., None]

    # sclera: warm white, greyer and pinker toward the corners and the back, veins
    side = np.abs(np.cos(psi)) ** 1.5
    toward = smoothstep(theta, layout.iris + 4.0, 52.0) * (0.35 + 0.65 * side)
    mott = angular(2, 11, 12, 3.0, 1.0)
    sclera = col("sclera") * (1.0 + 0.04 * mott[..., None])
    sclera = sclera + (col("sclera_corner") - sclera) * np.clip(toward + 0.12 * mott, 0.0, 1.0)[..., None]
    halo = np.exp(-((theta - layout.iris - 1.0) / 2.2) ** 2)        # the limbus' soft grey edge
    sclera = sclera * (1.0 - 0.25 * halo[..., None])
    alpha = np.zeros((n, n))

    def to_px(theta_deg, psi_r):
        r = layout.radius(theta_deg)
        return ((0.5 + r * math.cos(psi_r)) * n, (0.5 + r * math.sin(psi_r)) * n)

    vein_col = col("vein")
    for k in range(int(S.get("veins", 28))):
        if k % 4 != 3:
            p0 = rng.choice([0.0, math.pi]) + rng.normal(0.0, 0.35)
        else:
            p0 = rng.choice([0.5, -0.5]) * math.pi + rng.normal(0.0, 0.5)
        stack = [(rng.uniform(50.0, 80.0), p0, rng.uniform(1.2, 2.2), rng.uniform(0.25, 0.55), 0)]
        while stack:
            a, p, w, op, depth = stack.pop()
            end = rng.uniform(layout.iris + 3.0, layout.iris + 18.0)
            heading = rng.normal(0.0, 0.25)
            while a > end and w > 0.25:
                step = rng.uniform(1.0, 2.2)
                heading = max(min(heading + rng.normal(0.0, 0.35), 1.2), -1.2)
                a2 = a - step * math.cos(heading)
                p2 = p + math.radians(step * math.sin(heading)) / max(math.sin(math.radians(a)), 0.2)
                w2, op2 = w * 0.94, op * 0.94
                _seg_paint(sclera, alpha, to_px(a, p), to_px(a2, p2), w, w2, op, op2, vein_col)
                if depth < 2 and rng.random() < 0.10:
                    stack.append((a2, p2, w2 * 0.7, op2 * 0.8, depth + 1))
                a, p, w, op = a2, p2, w2, op2
    blend = smoothstep(t, 0.985, 1.05)
    albedo = iris * (1.0 - blend[..., None]) + sclera * blend[..., None]
    lid = smoothstep(np.sin(psi), 0.1, 0.8) * smoothstep(theta, 4.0, 18.0)       # under the upper lid at rest
    albedo *= (1.0 - S.get("lid_shade", 0.08) * lid)[..., None]

    # cornea dome as a normal map: the surface tilts away from the axis by atan(-h'(theta) / r)
    eps = 0.05
    dh = (cornea_height(theta + eps, layout.iris, cornea) - cornea_height(np.maximum(theta - eps, 0.0), layout.iris,
                                                                          cornea)) / math.radians(2 * eps)
    tilt = -dh / (radius + cornea_height(theta, layout.iris, cornea))
    nz = 1.0 / np.sqrt(1.0 + tilt * tilt)
    normal = np.stack([0.5 + 0.5 * tilt * nz * np.cos(psi), 0.5 + 0.5 * tilt * nz * np.sin(psi), 0.5 + 0.5 * nz], -1)

    rough = np.where(theta < layout.iris + 1.2, S["rough_cornea"], S["rough_sclera"]) + 0.015 * mott * (theta > 25)
    ao = (1.0 - S.get("lid_ao", 0.25) * lid) * (1.0 - 0.35 * smoothstep(theta, 55.0, 95.0))
    orm = np.stack([ao, rough, np.zeros_like(ao)], axis=-1)
    return np.clip(albedo, 0.0, 1.0), np.clip(normal, 0.0, 1.0), np.clip(orm, 0.0, 1.0)


def draw_strands(shape, strands):
    """Antialiased hair strands into (alpha, value) images of `shape` (H, W): `strands` is a
    list of (points (N, 2) in pixels (x, y), width at the root, width at the tip, value);
    `value` is each strand's shade (where strands overlap the darker/later one wins by
    coverage). For hair-card textures (brows, lashes) cut with alpha scissor: separate,
    opaque strands instead of a soft painted blur."""
    alpha = np.zeros(shape)
    value = np.zeros(shape + (1,))
    for pts, w0, w1, val in strands:
        n = len(pts) - 1
        for k in range(n):
            a0, a1 = w0 + (w1 - w0) * k / n, w0 + (w1 - w0) * (k + 1) / n
            _seg_paint(value, alpha, pts[k], pts[k + 1], a0, a1, 1.0, 1.0, (val,))
    return alpha, value[..., 0]


# --- painting an existing UV layout by position ----------------------------------------------
def uv_positions(ob, size, faces=None, uv_layer=None, other_uv=None):
    """Rasterize the UV faces of a mesh (object-local = world here) into a (size, size)
    texture: per texel the surface position (3), normal (3) and a coverage mask, plus
    with `other_uv` (a UV layer name) where that layer puts the same surface point (for
    resampling a texture from an old layout; zeros otherwise). `faces`: polygon indices
    to draw (default all). Rows are image rows from the bottom (Blender's pixel order).
    Returns (pos, nrm, mask, other)."""
    me = ob.data
    me.calc_loop_triangles()
    uv = (me.uv_layers[uv_layer] if uv_layer else me.uv_layers.active).data
    ouv = me.uv_layers[other_uv].data if other_uv else None
    pos = np.zeros((size, size, 3))
    nrm = np.zeros((size, size, 3))
    oth = np.zeros((size, size, 2))
    mask = np.zeros((size, size), dtype=bool)
    keep = None if faces is None else set(faces)
    vco = vertex_positions(ob)
    vn = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", vn)
    vn = vn.reshape(-1, 3)
    for tri in me.loop_triangles:
        if keep is not None and tri.polygon_index not in keep:
            continue
        q = np.array([uv[li].uv for li in tri.loops]) * size - 0.5
        x0, y0 = np.floor(q.min(axis=0)).astype(int)
        x1, y1 = np.ceil(q.max(axis=0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        (ax, ay), (bx, by), (cx, cy) = q
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        l2 = 1.0 - l0 - l1
        inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not inside.any():
            continue
        vi = list(tri.vertices)
        sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        p = l0[..., None] * vco[vi[0]] + l1[..., None] * vco[vi[1]] + l2[..., None] * vco[vi[2]]
        nn = l0[..., None] * vn[vi[0]] + l1[..., None] * vn[vi[1]] + l2[..., None] * vn[vi[2]]
        pos[sl][inside] = p[inside]
        nrm[sl][inside] = nn[inside]
        mask[sl][inside] = True
        if ouv is not None:
            o = [np.array(ouv[li].uv) for li in tri.loops]
            oo = l0[..., None] * o[0] + l1[..., None] * o[1] + l2[..., None] * o[2]
            oth[sl][inside] = oo[inside]
    return pos, nrm, mask, oth


def sample_bilinear(img, uv):
    """Sample an (H, W, C) array at UV coordinates (..., 2) (Blender pixel order, clamped)."""
    h, w = img.shape[:2]
    x = np.clip(uv[..., 0] * w - 0.5, 0.0, w - 1.0)
    y = np.clip(uv[..., 1] * h - 0.5, 0.0, h - 1.0)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy)
            + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def magnify_uv(ob, faces, scale, center, uv_layer=None):
    """Give `faces` their own UV island: their loops' UVs scaled by `scale` about the
    island's bounding-box center and moved to `center` (the neighbors keep theirs, so a
    seam forms on the island's edge). For more texels where they're needed (eye makeup)
    in a layout that has unused space; resample the old texture into it
    (`uv_positions(..., other_uv=...)` + `sample_bilinear`). Returns the new (lo, hi)."""
    me = ob.data
    uv = (me.uv_layers[uv_layer] if uv_layer else me.uv_layers.active).data
    loops = [li for f in faces for li in me.polygons[f].loop_indices]
    q = np.array([uv[li].uv for li in loops])
    c0 = 0.5 * (q.min(axis=0) + q.max(axis=0))
    new = np.asarray(center) + (q - c0) * scale
    for li, p in zip(loops, new):
        uv[li].uv = tuple(p)
    return new.min(axis=0), new.max(axis=0)


def uv_islands(ob, faces, uv_layer=None, tol=1e-6):
    """Split `faces` into UV islands (connected through edges whose two faces agree on
    both UVs). Returns lists of polygon indices, largest first."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    layer = bm.loops.layers.uv[uv_layer] if uv_layer else bm.loops.layers.uv.active
    keep = set(faces)
    seen, out = set(), []

    def uv_at(f, v):
        return next(lp[layer].uv for lp in f.loops if lp.vert is v)

    for f0 in faces:
        if f0 in seen:
            continue
        stack, comp = [f0], []
        seen.add(f0)
        while stack:
            fi = stack.pop()
            comp.append(fi)
            f = bm.faces[fi]
            for e in f.edges:
                for g in e.link_faces:
                    if g.index == fi or g.index not in keep or g.index in seen:
                        continue
                    if all((uv_at(f, v) - uv_at(g, v)).length < tol for v in e.verts):
                        seen.add(g.index)
                        stack.append(g.index)
        out.append(comp)
    bm.free()
    return sorted(out, key=len, reverse=True)


def uv_occupancy(ob, faces, size=512, uv_layer=None):
    """(size, size) bool map of the UV area `faces` cover (overlap checks)."""
    me = ob.data
    me.calc_loop_triangles()
    uv = (me.uv_layers[uv_layer] if uv_layer else me.uv_layers.active).data
    keep = set(faces)
    occ = np.zeros((size, size), dtype=bool)
    for tri in me.loop_triangles:
        if tri.polygon_index not in keep:
            continue
        q = np.array([uv[li].uv for li in tri.loops]) * size
        x0, y0 = np.floor(q.min(axis=0)).astype(int)
        x1, y1 = np.ceil(q.max(axis=0)).astype(int)
        occ[max(y0, 0):min(y1, size - 1) + 1, max(x0, 0):min(x1, size - 1) + 1] = True
    return occ


def dilate(values, mask, steps=4):
    """Grow `values` (H, W, C) from covered texels (`mask`) into their uncovered
    neighbors, `steps` pixels (texture filtering at island edges must not see the old
    texture under a painted layer). Returns (values, grown mask)."""
    v = values.copy()
    m = mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(v)
        cnt = np.zeros(m.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = np.roll(m, (dy, dx), axis=(0, 1))
            sv = np.roll(v, (dy, dx), axis=(0, 1))
            acc += sv * sm[..., None]
            cnt += sm
        grow = (~m) & (cnt > 0)
        v[grow] = acc[grow] / cnt[grow][:, None]
        m = m | grow
    return v, m


def image_from(name, rgba, colorspace="sRGB"):
    """Packed Blender image from a float array (H, W, 3|4) in display values (sRGB for
    color images: convert linear data first). Replaces an image of the same name."""
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    h, w = rgba.shape[:2]
    a = np.ones((h, w, 4), dtype=np.float32)
    a[..., :rgba.shape[2]] = rgba
    img = bpy.data.images.new(name, w, h, alpha=rgba.shape[2] == 4)
    img.colorspace_settings.name = colorspace
    img.pixels.foreach_set(a.ravel())
    img.pack()
    return img


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def image_array(img):
    """(H, W, 4) float pixels of a Blender image."""
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def mesh_bmesh_islands(ob):
    """Connected parts of a mesh as lists of vertex indices."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            comp.append(a.index)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        out.append(comp)
    bm.free()
    return out
