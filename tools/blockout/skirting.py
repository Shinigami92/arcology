"""Skirting runs: where skirting boards go along the walls, from the generated layout (D-036).

The floor plan is rasterized on a grid that matches the layout's 5 cm step: a cell is
free when a floor box covers it and no floor-standing wall box, window opening or
excluded room does. The boundary between free and blocked cells is the foot of the
walls; it's traced into loops, simplified, and clipped where something else meets the
floor (door frames and floor-level window frames), which leaves open runs that end
against the casings. Archway reveals keep their skirting (it wraps around the jambs).

Output (JSON, consumed by blender/architecture/skirting/): Godot world coordinates
(x, z) at floor level y = 0. Each run is a polyline; `normals` holds one unit vector
per segment pointing into the room (away from the wall), so the profile's back sits
on the polyline and its face looks along the normal. Closed runs repeat no point;
the last segment joins the last point to the first.
"""

from __future__ import annotations

import json
from pathlib import Path

GRID = 0.05
Rect = tuple[float, float, float, float]  # x0, z0, x1, z1


def _cells(rect: Rect, x0: float, z0: float, nx: int, nz: int) -> tuple[range, range]:
    i0 = max(0, round((rect[0] - x0) / GRID))
    i1 = min(nx, round((rect[2] - x0) / GRID))
    k0 = max(0, round((rect[1] - z0) / GRID))
    k1 = min(nz, round((rect[3] - z0) / GRID))
    return range(i0, i1), range(k0, k1)


def trace(floors: list[Rect], blocked: list[Rect]) -> list[list[tuple[float, float]]]:
    """Closed boundary loops of (floors - blocked), counterclockwise in (x, z) with z up, so the
    free side is on the left of travel (see `_inward`)."""
    x0 = min(r[0] for r in floors)
    z0 = min(r[1] for r in floors)
    nx = round((max(r[2] for r in floors) - x0) / GRID)
    nz = round((max(r[3] for r in floors) - z0) / GRID)
    free = [[False] * nz for _ in range(nx)]
    for rect in floors:
        xs, zs = _cells(rect, x0, z0, nx, nz)
        for i in xs:
            for k in zs:
                free[i][k] = True
    for rect in blocked:
        xs, zs = _cells(rect, x0, z0, nx, nz)
        for i in xs:
            for k in zs:
                free[i][k] = False

    def is_free(i: int, k: int) -> bool:
        return 0 <= i < nx and 0 <= k < nz and free[i][k]

    # Directed grid edges (lattice points), oriented counterclockwise around each free cell
    # as seen with x right and z up: bottom (i,k)->(i+1,k), right, top, left.
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for i in range(nx):
        for k in range(nz):
            if not free[i][k]:
                continue
            for (di, dk), a, b in (((0, -1), (i, k), (i + 1, k)), ((1, 0), (i + 1, k), (i + 1, k + 1)),
                                   ((0, 1), (i + 1, k + 1), (i, k + 1)), ((-1, 0), (i, k + 1), (i, k))):
                if not is_free(i + di, k + dk):
                    edges.setdefault(a, []).append(b)
    loops = []
    while edges:
        start = min(edges)
        loop, at = [start], start
        while True:
            nexts = edges[at]
            nxt = nexts.pop(0)
            if not nexts:
                del edges[at]
            at = nxt
            if at == start:
                break
            loop.append(at)
        loops.append(_simplify([(x0 + i * GRID, z0 + k * GRID) for i, k in loop]))
    return loops


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drops collinear points of a closed axis-aligned loop."""
    out = []
    n = len(points)
    for j in range(n):
        p, a, b = points[j - 1], points[j], points[(j + 1) % n]
        if not ((abs(p[0] - a[0]) < 1e-9 and abs(a[0] - b[0]) < 1e-9) or
                (abs(p[1] - a[1]) < 1e-9 and abs(a[1] - b[1]) < 1e-9)):
            out.append(a)
    return out


def _inward(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """Unit normal into the free side: loops run counterclockwise in (x, z) with z up,
    so the free side is on the left of travel: left of (dx, dz) is (-dz, dx)."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dz * dz) ** 0.5
    return (-dz / length, dx / length)


def _inside(p: tuple[float, float], r: Rect) -> bool:
    return r[0] - 1e-9 <= p[0] <= r[2] + 1e-9 and r[1] - 1e-9 <= p[1] <= r[3] + 1e-9


def _clip_segment(a, b, cuts: list[Rect]) -> list[tuple[float, float, float]]:
    """Keeps the parts of axis-aligned segment a->b outside every cut: [(t0, t1)] in 0..1."""
    keep = [(0.0, 1.0)]
    for r in cuts:
        # Parameter range of the segment inside r (segments are axis-aligned).
        t_lo, t_hi = 0.0, 1.0
        for axis, (lo, hi) in ((0, (r[0], r[2])), (1, (r[1], r[3]))):
            d = b[axis] - a[axis]
            if abs(d) < 1e-12:
                if not lo - 1e-9 <= a[axis] <= hi + 1e-9:
                    t_lo, t_hi = 1.0, 0.0
            else:
                t0, t1 = (lo - a[axis]) / d, (hi - a[axis]) / d
                t_lo, t_hi = max(t_lo, min(t0, t1)), min(t_hi, max(t0, t1))
        if t_hi - t_lo <= 1e-9:
            continue
        keep = [part for k0, k1 in keep for part in ((k0, min(k1, t_lo)), (max(k0, t_hi), k1)) if part[1] - part[0] > 1e-9]
    return keep


def runs(floors: list[Rect], blocked: list[Rect], cuts: list[Rect], min_length: float = 0.04) -> list[dict]:
    """Skirting runs: traced loops with the parts inside `cuts` removed (see module doc)."""
    out = []
    for loop in trace(floors, blocked):
        n = len(loop)
        segments = [(loop[j], loop[(j + 1) % n]) for j in range(n)]
        pieces = []  # (a, b) kept sub-segments in loop order
        for a, b in segments:
            for t0, t1 in _clip_segment(a, b, cuts):
                pa = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                pb = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                pieces.append((pa, pb))
        if not pieces:
            continue
        if len(pieces) == len(segments) and all(p == s for p, s in zip(pieces, segments)):
            out.append({"closed": True, "points": loop, "normals": [_inward(a, b) for a, b in segments]})
            continue
        # Chain consecutive pieces into open polylines; rotate so a chain starts after a cut.
        chains: list[list[tuple]] = []
        for piece in pieces:
            if chains and _close(chains[-1][-1][1], piece[0]):
                chains[-1].append(piece)
            else:
                chains.append([piece])
        if len(chains) > 1 and _close(chains[-1][-1][1], chains[0][0][0]):
            chains[0] = chains.pop() + chains[0]
        for chain in chains:
            points = [chain[0][0]] + [p[1] for p in chain]
            length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in chain)
            if length >= min_length:
                out.append({"closed": False, "points": points, "normals": [_inward(a, b) for a, b in chain]})
    for run in out:
        run["points"] = [[round(x, 4), round(z, 4)] for x, z in run["points"]]
        run["normals"] = [[round(x, 4) + 0.0, round(z, 4) + 0.0] for x, z in run["normals"]]
    return out


def _close(p, q) -> bool:
    return abs(p[0] - q[0]) < 1e-9 and abs(p[1] - q[1]) < 1e-9


def write(path: Path, profile: dict, run_list: list[dict], doc: str) -> None:
    data = {"doc": doc, "profile": profile, "runs": run_list}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
