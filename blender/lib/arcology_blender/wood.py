"""Wood veneer layers for `Graph` materials (D-028).

Two recipes, both returning (base, rough, height in m) like the `fabric`
layers, so an asset adds its own wear and ends with `g.finish_height`:

    veneer       flat-sawn veneer in a per-board frame (the best look): each
                 board stores its grain axis, thickness axis, a seed and the
                 log axis as mesh attributes (`set_grain`, or `board` which
                 builds a beveled box and sets them). Cathedral arches around
                 the log axis, tightening stripes toward the edges, streaks
                 and pores. Promoted from the nightstand (Opus 5.5).
    veneer_axis  sliced veneer with the grain along one world axis, no
                 attributes: quick for panels that share a grain direction
                 (one material per direction). Promoted from the lit wardrobe.

Keep the rings at mm-to-cm scale and low contrast: fine high-contrast grain
shimmers in VR. Remove the grain attributes before export (`GRAIN_ATTRS`,
`geo.remove_attribute`).
"""

import math

import bmesh
from mathutils import Vector

from .geo import bm_box, finish, new_object, set_point_attr

GRAIN_ATTRS = ("grain_u", "grain_b", "grain_seed", "grain_a0", "grain_b0")
AXIS = {"x": 0, "y": 1, "z": 2}


# --- per-board frame -------------------------------------------------------------
def grain_frame(g, u_attr="grain_u", b_attr="grain_b", seed_attr="grain_seed"):
    """World coordinates remapped into a per-board wood frame.

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
    """Store a board's grain frame for `veneer` (see `grain_frame`): u/b axis
    indices, a per-board seed, and the log axis position (a0, b0) in world
    meters on the board's a and b axes (put a0 near the middle of the face,
    b0 a few cm behind the face that matters most)."""
    for name, v in (("grain_u", u), ("grain_b", b), ("grain_seed", seed), ("grain_a0", a0), ("grain_b0", b0)):
        set_point_attr(ob, name, v)


def board(name, lo, hi, coll, mat, grain, thick, seed, bevel=0.0018, parent=None, face=1):
    """A veneered board: a beveled box (corners `lo`, `hi`, in the parent's
    frame) with its grain frame stored for `veneer`.

    grain/thick: "x"/"y"/"z", the axis the grain runs along / through the
    thickness. seed: 0..1, varies the figure per board. face: +1/-1 = the
    side of the thickness axis that shows most (the log axis sits 45 mm
    behind it). Parents may only translate (the frame is in world meters)."""
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    ob = new_object(name, bm, coll, material=mat, parent=parent)
    finish(ob, bevel, 2)
    u, b = AXIS[grain], AXIS[thick]
    a = 3 - u - b
    # frame positions in world meters (parents only translate)
    off = parent.location if parent is not None else Vector((0, 0, 0))
    lo_w, hi_w = Vector(lo) + off, Vector(hi) + off
    size_a = hi_w[a] - lo_w[a]
    a0 = (lo_w[a] + hi_w[a]) / 2 + (seed - 0.5) * 0.5 * size_a
    b0 = (lo_w[b] + hi_w[b]) / 2 - face * 0.045
    set_grain(ob, u, b, seed, a0, b0)
    return ob


def veneer(g, mid, dark, light, ring_spacing=0.0065, tilt=(0.04, 0.06), wander=0.012,
           figure=0.0035, streak=0.5, late_amount=0.32, pores=0.30, rough=0.44,
           u_attr="grain_u", b_attr="grain_b", seed_attr="grain_seed",
           a0_attr="grain_a0", b0_attr="grain_b0"):
    """Flat-sawn hardwood veneer under a satin finish (walnut, oak, ...).

    Grain follows the per-board frame from `grain_frame`; `set_grain` (or
    `board`) stores it, including the log axis (a0, b0) the growth rings
    circle. The axis is tilted against the board (`tilt` = da/du, db/du) and
    wanders (`wander`, m), so faces show cathedral arches around a0 and long,
    tightening stripes toward the edges, like a real flat-sawn leaf. Rings
    are wavy (`figure`, m); latewood darkens toward `dark` (`late_amount`),
    `streak` mixes long lighter/darker streaks (light <-> mid <-> dark),
    `pores` adds fine low-contrast flecks along the grain. Features are mm to
    cm and low contrast (VR shimmer). Returns (base, rough, height in m).
    """
    u, a, b, seed = grain_frame(g, u_attr, b_attr, seed_attr)
    a0, b0 = g.attribute(a0_attr), g.attribute(b0_attr)
    so = g.mul(seed, 3.7)
    frame = g.combine(g.add(u, so), a, b)
    slow = g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vscale(frame, 2.2, 2.2, 2.2)), 0.5)
    a0 = g.add(g.add(a0, g.mul(u, tilt[0])), g.mul(slow, wander))
    b0 = g.add(b0, g.mul(u, tilt[1]))
    wob = g.mul(g.sub(g.noise(1.0, 3.0, 0.55, vector=g.vscale(frame, 2.0, 14.0, 14.0)), 0.5), figure)
    wig = g.mul(g.sub(g.noise(1.0, 2.0, 0.5, vector=g.vscale(frame, 9.0, 90.0, 90.0)), 0.5), figure * 0.25)
    da, db = g.sub(a, a0), g.sub(b, b0)
    r = g.add(g.add(g.math("SQRT", g.add(g.mul(da, da), g.mul(db, db))), wob), wig)
    t = g.math("FRACT", g.math("DIVIDE", r, ring_spacing))
    late = g.band(t, 0.64, 0.90, 0.08)
    # long streaks and broad mottling (along the grain)
    st = g.noise(1.0, 3.0, 0.6, vector=g.vscale(frame, 1.1, 22.0, 22.0))
    mot = g.noise(1.0, 2.0, 0.5, vector=g.vscale(frame, 0.6, 4.0, 4.0))
    base = g.mixc(g.maprange(st, 0.28, 0.62), light, mid)
    base = g.mixc(g.mul(streak, g.maprange(st, 0.55, 0.78)), base, dark)
    base = g.scale_color(base, g.add(0.85, g.mul(mot, 0.30)))
    base = g.mixc(g.mul(late, late_amount), base, dark)
    pore = g.maprange(g.noise(1.0, 1.0, 0.5, vector=g.vscale(frame, 25.0, 480.0, 480.0)), 0.62, 0.74)
    base = g.scale_color(base, g.sub(1.0, g.mul(pore, pores)))
    r_out = g.add(g.add(rough, g.mul(pore, 0.10)), g.sub(g.mul(mot, 0.06), g.mul(late, 0.03)))
    height = g.sub(0.0, g.add(g.mul(pore, 0.00012), g.mul(late, 0.00005)))
    return base, r_out, height


# --- world-axis grain -------------------------------------------------------------
def _stretched(g, axis, across, along):
    s = [across, across, across]
    s["XYZ".index(axis)] = along
    return g.vec(*s)


def veneer_axis(g, axis="Z", mid=(0.040, 0.021, 0.012), light=(0.072, 0.039, 0.021),
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
    (satin ~0.4). Use one material per grain direction. Returns (base,
    rough, height in m).
    """
    others = [c for c in "XYZ" if c != axis]
    coord = {"X": g.x, "Y": g.y, "Z": g.z}
    u = g.add(coord[others[0]], coord[others[1]])
    v = coord[axis]
    warp = g.add(g.mul(g.sub(g.noise(1.0, 2.0, 0.5, _stretched(g, axis, 3.0, 0.22)), 0.5), figure),
                 g.mul(g.sub(g.noise(1.0, 3.0, 0.5, _stretched(g, axis, 22.0, 1.1)), 0.5), figure * 0.22))
    uw = g.add(g.add(u, warp), seed)

    def grain_noise(across, along, detail=2.0, rough_=0.5, off=0.0):
        return g.noise(1.0, detail, rough_, g.combine(g.mul(uw, across), g.mul(v, along), seed * 7.0 + off))

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
