"""Geometry of the five hover vehicles (authoring frame: z = 0 at the pod
bottoms, y = 0 mid-length, nose +Y, x = 0 the center plane).

A hull is a loft through key cross-sections (stations) interpolated with
a monotone cubic; each station is a rounded section with a belly, a skirt crease,
the belt line, a greenhouse (glass) and a rounded roof. Station keys:

  y   position along the length         zb  belly (bottom)
  zc  skirt crease                      zs  belt line (glass bottom)
  zg  glass top / roof edge             zr  roof
  wb  half width at the belly           ws  half width at the belt (widest)
  wg  half width mid-glass              wr  half width at the roof edge

Glass comes from key intervals (`glass_full`: windshield/rear window across
the top, `glass_side`: side windows); the rest is paint, the belly is trim.
Extras: thruster pods underneath (lathe, glowing disc), rear nozzles, lamp
lenses projected onto the hull (conform_patch, each its own UV island), the
taxi's roof sign, the patrol light bar, the bus's destination signs.

Every spec also feeds the materials: belt / belly heights, pods (x, y, r),
seams, thruster color.
"""

import math

from mathutils import Matrix, Vector

from lib_candidates import PartMesh, box_part, bvh_of_partmesh, conform_patch, interpolate_keys, lathe_part, loft_rings
from traffic_common import HOT_ATTR

KEYS = ("y", "zb", "zc", "zs", "zg", "zr", "wb", "ws", "wg", "wr")


def keys(rows, glass_drop=0.07):
    """Station dicts from rows (y, zb, zc, zs, zr, wb, ws, wg, wr[, zg])."""
    out = []
    for r in rows:
        y, zb, zc, zs, zr, wb, ws, wg, wr = r[:9]
        zg = r[9] if len(r) > 9 else zr - min(glass_drop, (zr - zs) * 0.35)
        out.append(dict(y=y, zb=zb, zc=zc, zs=zs, zg=zg, zr=zr, wb=wb, ws=ws, wg=wg, wr=wr))
    return out


def half_profile(s):
    """Right half of a section (x >= 0), bottom center to top center: 11 points, 10 segments.
    Segments: 0 belly, 1 lower corner, 2 skirt, 3 lower side, 4 upper side,
    5-6 glass, 7-8 roof edge, 9 roof."""
    zb, zc, zs, zg, zr = s["zb"], s["zc"], s["zs"], s["zg"], s["zr"]
    wb, ws, wg, wr = s["wb"], s["ws"], s["wg"], s["wr"]
    return [
        (0.0, zb),
        (wb * 0.62, zb),
        (wb, zb + (zc - zb) * 0.5),
        (ws * 0.975, zc),
        (ws, zc + (zs - zc) * 0.55),
        (ws * 0.988, zs),
        (wg, zs + (zg - zs) * 0.5),
        (wr, zg),
        (wr * 0.80, zg + (zr - zg) * 0.80),
        (wr * 0.50, zr),
        (0.0, zr),
    ]


K = 10  # segments per half profile


def ring(s):
    half = half_profile(s)
    pts = half + [(-x, z) for x, z in reversed(half[1:-1])]
    return [Vector((x, s["y"], z)) for x, z in pts]


def side_segment(j):
    """Ring segment j -> half-profile segment index."""
    return j if j < K else 2 * K - 1 - j


def hull(pm, spec):
    stations = interpolate_keys(spec["keys"], spec["steps"])
    full, side = set(spec.get("glass_full", ())), set(spec.get("glass_side", ()))
    side_slot = spec.get("side_glass_slot", "glass")
    top_z = spec.get("windshield_top", 1e9)
    intervals = [int(math.floor(s["key"] + 1e-6)) for s in stations]
    rings = [ring(s) for s in stations]

    def slot(i, j):
        k, seg = intervals[i], side_segment(j)
        if seg == 0:
            return "trim"
        n = len(rings[i])
        zc = (rings[i][j].z + rings[i][(j + 1) % n].z + rings[i + 1][j].z + rings[i + 1][(j + 1) % n].z) / 4
        if k in full and seg >= 5 and zc < top_z:
            return "glass"
        if k in side and seg in (5, 6):
            return side_slot
        return "paint"

    loft_rings(pm, rings, slot, cap_start="paint", cap_end="paint")
    pm.end_piece()
    return stations


def pod(pm, x, y, r, z_top, z_bot=0.0, stretch=1.45, segments=12):
    """Thruster pod under the belly, oval (longer along Y): housing (trim), a
    glowing band around its lower side (reads as a thruster, not a wheel, from
    any angle), a lip and the glowing exhaust disc underneath."""
    prof = [(r * 0.80, z_top), (r, z_bot + 0.15), (r, z_bot + 0.10), (r * 0.93, z_bot + 0.015), (r * 0.70, z_bot),
            (0.0, z_bot + 0.035)]
    m = Matrix.Translation((x, y, 0.0)) @ Matrix.Diagonal((1.0, stretch, 1.0, 1.0))
    lathe_part(pm, prof, segments, m, ["trim", "thruster", "trim", "trim", "thruster"],
               attrs=[0.0, 0.0, 0.0, 0.0, 0.2, 1.0], start_angle=math.pi / segments)
    pm.end_piece()


def nozzle(pm, x, y, z, r, length=0.30, segments=10):
    """Rear thruster nozzle opening toward -Y at (x, y, z), body extending into +Y."""
    prof = [(r * 0.85, length), (r, 0.06), (r * 0.94, 0.0), (r * 0.66, 0.0), (0.0, 0.05)]
    m = Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(-90.0), 4, "X")
    lathe_part(pm, prof, segments, m, ["trim", "trim", "trim", "thruster"], attrs=[0.0, 0.0, 0.0, 0.2, 1.0],
               start_angle=math.pi / segments)
    pm.end_piece()


def lens(pm, bvh, x, z, size, front, slot, nu=3, nv=1, y=None, rim="trim", round_corners=0.25):
    """A lamp lens on the nose (front=True, projected along -Y) or tail (+Y)."""
    d = (0.0, -1.0, 0.0) if front else (0.0, 1.0, 0.0)
    c = (x, 0.0 if y is None else y, z)
    _, centroid = conform_patch(pm, bvh, c, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), size, d, slot, rim,
                                nu=nu, nv=nv, round_corners=round_corners)
    if centroid is None:
        raise RuntimeError(f"lens {slot} at x={x} z={z} missed the hull")
    pm.end_piece()
    return centroid - Vector(d) * 0.012


def side_patch(pm, bvh, y, z, size, slot, side=1.0, nu=3, nv=1, rim="trim"):
    """A patch on a side (side=+1: +X, projected along -X)."""
    d = (-side, 0.0, 0.0)
    _, centroid = conform_patch(pm, bvh, (0.0, y, z), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), size, d, slot, rim,
                                nu=nu, nv=nv, round_corners=0.0)
    if centroid is None:
        raise RuntimeError(f"side patch {slot} at y={y} z={z} missed the hull")
    pm.end_piece()
    return centroid


def pair(pm, bvh, x, z, size, front, slot, **kw):
    a = lens(pm, bvh, -x, z, size, front, slot, **kw)
    b = lens(pm, bvh, x, z, size, front, slot, **kw)
    return (a + b) / 2


def boxes(pm, lo, hi, slot):
    box_part(pm, lo, hi, lambda n: slot)
    pm.end_piece()


# ---------------------------------------------------------------------------------------
# The fleet
# ---------------------------------------------------------------------------------------
SPECS = {}

SPECS["aircar_sedan"] = dict(
    # Low fastback with a wraparound windshield, magenta accent line.
    keys=keys([
        (-2.40, 0.46, 0.56, 0.80, 0.86, 0.42, 0.62, 0.60, 0.52),
        (-2.28, 0.34, 0.46, 0.86, 0.93, 0.66, 0.86, 0.84, 0.74),
        (-1.85, 0.26, 0.40, 0.88, 0.99, 0.78, 0.94, 0.90, 0.80),
        (-1.15, 0.22, 0.37, 0.86, 1.22, 0.82, 0.96, 0.88, 0.68),
        (-0.35, 0.21, 0.36, 0.84, 1.38, 0.82, 0.96, 0.86, 0.64),
        (0.45, 0.21, 0.36, 0.82, 1.33, 0.82, 0.96, 0.86, 0.66),
        (1.15, 0.22, 0.36, 0.80, 0.90, 0.82, 0.96, 0.92, 0.82),
        (1.80, 0.24, 0.38, 0.76, 0.84, 0.80, 0.94, 0.90, 0.80),
        (2.22, 0.32, 0.42, 0.68, 0.74, 0.65, 0.85, 0.82, 0.72),
        (2.40, 0.42, 0.48, 0.62, 0.66, 0.36, 0.56, 0.53, 0.46),
    ]),
    steps=[1, 2, 2, 2, 2, 2, 2, 2, 1],
    glass_full=(2, 5), glass_side=(3, 4),
    belt=0.84, belly=0.22, thrust="cyan", cabin_glow=0.008,
    pods=[(-0.56, 1.45, 0.25), (0.56, 1.45, 0.25), (-0.60, -1.40, 0.30), (0.60, -1.40, 0.30)],
    seams_y=[(1.15, 0.30, 0.82), (0.05, 0.36, 0.84), (-1.10, 0.36, 0.86), (1.90, 0.70, 0.90), (-1.90, 0.80, 1.0)],
    seams_z=[],
    nozzles=[(-0.40, -2.34, 0.62, 0.13), (0.40, -2.34, 0.62, 0.13)],
    headlights=dict(x=0.34, z=0.565, size=(0.34, 0.10)),
    taillights=dict(x=0.36, z=0.76, size=(0.42, 0.11)),
    grille=dict(z=0.53, size=(0.28, 0.06)),
    vents=[(-1.55, 0.60, 0.46, 0.10)],
    side_lamps=dict(front=(2.20, 0.56, 0.22, 0.08), rear=(-2.22, 0.76, 0.24, 0.09)),
    spoiler=dict(x=0.78, y=(-2.32, -2.08), z=(1.03, 1.07), strut_x=0.55),
)

SPECS["aircar_taxi"] = dict(
    # Chunky yellow cab, upright greenhouse, roof sign.
    keys=keys([
        (-2.50, 0.48, 0.58, 0.84, 0.92, 0.48, 0.66, 0.64, 0.56),
        (-2.36, 0.34, 0.46, 0.90, 1.00, 0.74, 0.92, 0.90, 0.80),
        (-1.95, 0.26, 0.40, 0.92, 1.10, 0.82, 0.98, 0.94, 0.84),
        (-1.45, 0.24, 0.38, 0.92, 1.44, 0.84, 0.99, 0.90, 0.76),
        (-0.40, 0.24, 0.38, 0.92, 1.48, 0.84, 0.99, 0.90, 0.76),
        (0.65, 0.24, 0.38, 0.90, 1.46, 0.84, 0.99, 0.90, 0.76),
        (1.30, 0.25, 0.38, 0.88, 0.98, 0.84, 0.98, 0.94, 0.84),
        (1.95, 0.28, 0.40, 0.84, 0.92, 0.80, 0.95, 0.92, 0.80),
        (2.36, 0.36, 0.46, 0.76, 0.82, 0.66, 0.86, 0.83, 0.72),
        (2.50, 0.46, 0.54, 0.70, 0.74, 0.40, 0.60, 0.57, 0.50),
    ]),
    steps=[1, 2, 2, 2, 2, 2, 2, 2, 1],
    glass_full=(2, 5), glass_side=(3, 4),
    belt=0.91, belly=0.24, thrust="amber", cabin_glow=0.014,
    pods=[(-0.58, 1.55, 0.27), (0.58, 1.55, 0.27), (-0.60, -1.55, 0.29), (0.60, -1.55, 0.29)],
    seams_y=[(1.30, 0.32, 0.90), (0.10, 0.38, 0.92), (-1.05, 0.38, 0.92), (2.00, 0.75, 0.95), (-2.00, 0.85, 1.12)],
    seams_z=[],
    nozzles=[(-0.40, -2.44, 0.64, 0.13), (0.40, -2.44, 0.64, 0.13)],
    headlights=dict(x=0.32, z=0.62, size=(0.32, 0.10)),
    taillights=dict(x=0.38, z=0.80, size=(0.40, 0.11)),
    grille=dict(z=0.58, size=(0.24, 0.05)),
    vents=[(1.65, 0.60, 0.36, 0.09)],
    side_lamps=dict(front=(2.30, 0.62, 0.20, 0.08), rear=(-2.32, 0.80, 0.24, 0.09)),
    sign=dict(lo=(-0.13, -0.65, 1.51), hi=(0.13, 0.35, 1.79), base=((-0.08, -0.50, 1.42), (0.08, 0.20, 1.52))),
)

SPECS["hover_van"] = dict(
    # Boxy cargo hauler: short sloped cab, tall cargo box with HAKO EXPRESS livery.
    keys=keys([
        (-3.25, 0.44, 0.52, 1.20, 2.30, 0.96, 1.04, 1.03, 0.98),
        (-3.14, 0.34, 0.45, 1.25, 2.42, 1.04, 1.10, 1.09, 1.05, 2.36),
        (1.15, 0.34, 0.45, 1.25, 2.42, 1.04, 1.10, 1.09, 1.05, 2.36),
        (1.45, 0.34, 0.45, 1.22, 2.30, 1.04, 1.10, 1.08, 1.00),
        (2.15, 0.34, 0.45, 1.18, 2.22, 1.04, 1.09, 1.05, 0.94),
        (2.85, 0.38, 0.48, 1.10, 1.30, 1.00, 1.06, 1.03, 0.95),
        (3.15, 0.46, 0.54, 1.02, 1.14, 0.90, 1.00, 0.97, 0.88),
        (3.25, 0.56, 0.62, 0.96, 1.04, 0.70, 0.84, 0.82, 0.74),
    ]),
    steps=[1, 6, 1, 2, 2, 1, 1],
    glass_full=(4,), glass_side=(3,),
    belt=1.22, belly=0.34, thrust="amber", cabin_glow=0.008,
    pods=[(-0.70, 2.30, 0.30), (0.70, 2.30, 0.30), (-0.72, -0.20, 0.32), (0.72, -0.20, 0.32),
          (-0.72, -2.50, 0.32), (0.72, -2.50, 0.32)],
    seams_y=[(1.25, 0.40, 2.42), (2.15, 0.45, 1.22), (-3.05, 0.45, 2.40)],
    seams_z=[(0.62, -3.2, 3.2)],
    nozzles=[],
    headlights=dict(x=0.50, z=0.80, size=(0.36, 0.12)),
    taillights=dict(x=0.86, z=1.05, size=(0.16, 0.50), nu=1, nv=2),
    grille=dict(z=0.80, size=(0.40, 0.10)),
    side_lamps=dict(front=(3.05, 0.80, 0.18, 0.10), rear=(-3.12, 1.05, 0.16, 0.45)),
)

SPECS["patrol_cruiser"] = dict(
    # Low wedge, near-black with a white door band, red/blue light bar.
    keys=keys([
        (-2.60, 0.44, 0.56, 0.86, 0.94, 0.50, 0.70, 0.68, 0.60),
        (-2.46, 0.32, 0.46, 0.92, 1.02, 0.76, 0.94, 0.92, 0.82),
        (-2.00, 0.24, 0.40, 0.94, 1.10, 0.82, 0.99, 0.95, 0.84),
        (-1.30, 0.22, 0.38, 0.92, 1.34, 0.84, 1.00, 0.90, 0.72),
        (-0.20, 0.22, 0.38, 0.88, 1.36, 0.84, 1.00, 0.90, 0.72),
        (0.70, 0.22, 0.37, 0.84, 1.28, 0.84, 1.00, 0.90, 0.74),
        (1.40, 0.22, 0.36, 0.78, 0.86, 0.84, 0.99, 0.94, 0.84),
        (2.10, 0.24, 0.36, 0.68, 0.74, 0.80, 0.95, 0.92, 0.80),
        (2.48, 0.30, 0.38, 0.56, 0.60, 0.64, 0.84, 0.81, 0.70),
        (2.60, 0.36, 0.40, 0.50, 0.52, 0.36, 0.60, 0.58, 0.48),
    ]),
    steps=[1, 2, 2, 2, 2, 2, 2, 2, 1],
    glass_full=(2, 5), glass_side=(3, 4),
    belt=0.88, belly=0.22, thrust="cyan", cabin_glow=0.006,
    pods=[(-0.58, 1.60, 0.26), (0.58, 1.60, 0.26), (-0.62, -1.55, 0.30), (0.62, -1.55, 0.30)],
    seams_y=[(1.25, 0.30, 0.80), (-0.05, 0.38, 0.88), (-1.30, 0.38, 0.92), (2.15, 0.60, 0.80), (-2.05, 0.85, 1.12)],
    seams_z=[],
    nozzles=[(-0.40, -2.54, 0.66, 0.13), (0.40, -2.54, 0.66, 0.13)],
    headlights=dict(x=0.32, z=0.455, size=(0.36, 0.075)),
    taillights=dict(x=0.38, z=0.78, size=(0.40, 0.11)),
    grille=None,
    vents=[(-1.65, 0.62, 0.50, 0.08), (1.70, 0.55, 0.40, 0.07)],
    side_lamps=dict(front=(2.36, 0.48, 0.20, 0.06), rear=(-2.42, 0.80, 0.24, 0.09)),
    lightbar=dict(y=(-0.34, -0.10), x=0.62, z=(1.31, 1.38, 1.48)),
)

SPECS["sky_bus"] = dict(
    # Public skybus: long rounded box, lit window band, destination signs, six pods.
    keys=keys([
        (-6.00, 0.60, 0.72, 1.40, 2.55, 1.10, 1.28, 1.24, 1.10, 2.30),
        (-5.86, 0.48, 0.62, 1.40, 2.78, 1.30, 1.42, 1.40, 1.30, 2.44),
        (-5.45, 0.42, 0.58, 1.40, 2.88, 1.36, 1.45, 1.43, 1.36, 2.46),
        (4.25, 0.42, 0.58, 1.40, 2.88, 1.36, 1.45, 1.43, 1.36, 2.46),
        (5.10, 0.44, 0.60, 1.30, 2.82, 1.34, 1.44, 1.38, 1.26, 2.50),
        (5.75, 0.52, 0.66, 1.10, 1.70, 1.22, 1.38, 1.32, 1.18, 1.62),
        (6.00, 0.68, 0.78, 1.00, 1.30, 0.90, 1.10, 1.06, 0.94, 1.26),
    ]),
    steps=[1, 2, 8, 2, 2, 1],
    glass_full=(4,), glass_side=(2, 3), side_glass_slot="bus_glass", windshield_top=2.40,
    belt=1.40, belly=0.42, glass_top=2.46, window_y0=-5.30, window_period=1.32,
    thrust="cyan", cabin_glow=0.02,
    pods=[(-0.86, 4.10, 0.40), (0.86, 4.10, 0.40), (-0.86, -0.20, 0.40), (0.86, -0.20, 0.40),
          (-0.86, -4.40, 0.40), (0.86, -4.40, 0.40)],
    seams_y=[(-5.50, 0.5, 2.9), (4.30, 0.5, 2.9), (2.20, 0.58, 1.40), (-1.80, 0.58, 1.40)],
    seams_z=[(0.66, -6.0, 6.0)],
    nozzles=[(-0.75, -5.96, 1.00, 0.20), (0.75, -5.96, 1.00, 0.20)],
    headlights=dict(x=0.68, z=1.00, size=(0.44, 0.13)),
    taillights=dict(x=1.02, z=1.50, size=(0.16, 0.60), nu=1, nv=2),
    grille=dict(z=0.88, size=(0.70, 0.10)),
    side_lamps=dict(front=(5.85, 1.00, 0.20, 0.12), rear=(-5.80, 1.50, 0.16, 0.50)),
    sign_front_z=2.56, sign_rear_z=2.05,
    roof_units=[((-0.80, -3.6, 2.84), (0.80, -2.0, 3.02)), ((-0.70, 1.2, 2.84), (0.70, 2.6, 3.00))],
)


# ---------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------
def build_vehicle(vehicle):
    """PartMesh of one vehicle in the authoring frame + reference points
    (headlights, taillights: centers between the two lamps)."""
    spec = SPECS[vehicle]
    pm = PartMesh(HOT_ATTR)
    hull(pm, spec)
    bvh = bvh_of_partmesh(pm)
    ref = {}
    hl, tl = spec["headlights"], spec["taillights"]
    ref["headlights"] = pair(pm, bvh, hl["x"], hl["z"], hl["size"], True, "headlight",
                             nu=hl.get("nu", 3), nv=hl.get("nv", 1))
    ref["taillights"] = pair(pm, bvh, tl["x"], tl["z"], tl["size"], False, "taillight",
                             nu=tl.get("nu", 3), nv=tl.get("nv", 1))
    if spec.get("grille"):
        gr = spec["grille"]
        lens(pm, bvh, 0.0, gr["z"], gr["size"], True, "trim", nu=2, nv=1, round_corners=0.0)
    sl = spec.get("side_lamps")
    if sl:  # wrap-around corner lamps: lanes mostly cross the view, side-on
        for key, slot in (("front", "headlight"), ("rear", "taillight")):
            y, z, w, h = sl[key]
            for side in (-1.0, 1.0):
                side_patch(pm, bvh, y, z, (w, h), slot, side=side, nu=1, nv=1 if h < 0.2 else 2)
    for y, z, w, h in spec.get("vents", ()):
        for side in (-1.0, 1.0):
            side_patch(pm, bvh, y, z, (w, h), "trim", side=side, nu=2)
    if spec.get("spoiler"):
        sp = spec["spoiler"]
        (y0, y1), (z0, z1) = sp["y"], sp["z"]
        boxes(pm, (-sp["x"], y0, z0), (sp["x"], y1, z1), "paint")
        for sx in (-1.0, 1.0):
            cx = sx * sp["strut_x"]
            boxes(pm, (cx - 0.025, y0 + 0.06, z0 - 0.14), (cx + 0.025, y1 - 0.04, z0), "trim")
    belly = spec["belly"]
    for x, y, r in spec["pods"]:
        pod(pm, x, y, r, z_top=belly + 0.10)
    for x, y, z, r in spec["nozzles"]:
        nozzle(pm, x, y, z, r)

    if vehicle == "aircar_taxi":
        s = spec["sign"]
        boxes(pm, *s["base"], "trim")
        box_part(pm, s["lo"], s["hi"], lambda n: "sign")
        pm.end_piece()
    if vehicle == "patrol_cruiser":
        b = spec["lightbar"]
        (y0, y1), x, (z0, z1, z2) = b["y"], b["x"], b["z"]
        boxes(pm, (-x, y0, z0), (x, y1, z1), "trim")
        boxes(pm, (-x + 0.02, y0 + 0.02, z1), (-0.05, y1 - 0.02, z2), "bar_red")    # driver side (-X): red
        boxes(pm, (0.05, y0 + 0.02, z1), (x - 0.02, y1 - 0.02, z2), "bar_blue")     # passenger side (+X): blue
        boxes(pm, (-0.05, y0 + 0.03, z1), (0.05, y1 - 0.03, z2 - 0.01), "trim")
    if vehicle == "hover_van":
        # amber clearance lamps on the rear corners, high up
        for sx in (-1.0, 1.0):
            lens(pm, bvh, sx * 0.80, 2.18, (0.18, 0.08), False, "marker", nu=1, nv=1, round_corners=0.0)
    if vehicle == "sky_bus":
        lens(pm, bvh, 0.0, spec["sign_front_z"] + 0.13, (1.6, 0.26), True, "sign", nu=4, nv=1, round_corners=0.0)
        lens(pm, bvh, 0.0, spec["sign_rear_z"] + 0.15, (0.9, 0.30), False, "sign", nu=2, nv=1, round_corners=0.0)
        for lo, hi in spec["roof_units"]:
            boxes(pm, lo, hi, "trim")
    return pm, ref, spec
