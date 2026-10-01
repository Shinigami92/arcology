"""Stage 1: sweep the skirting profile along every run of the run file, with trim UVs, save.

  blender -b --factory-startup --python blender/architecture/skirting/build.py [-- --runs F]

One mesh for all runs (one draw call), one material slot `skirting_paint` (a plain
placeholder until bake.py wires the trim sheet). Mitered inside corners, eased and rubbed
outside corners, square ends at the run end points.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skirting_common import (  # noqa: E402
    ARRIS_R, ARRIS_STEPS, CASING_MIN, FRAME_PAINT, MAT, PAINT_ROUGH, PLAIN, RUB_MARGIN, THICKNESS, blend_path,
    joint_offsets, joints_of, load_runs, normal_to_blender, profile, runs_path, segment_count, stem, to_blender,
)
import skirting_trim  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, save_blend, tag, tri_count  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.trim import TrimMesh  # noqa: E402


def check_input(data):
    """The run file's own consistency: unit normals perpendicular to their segments."""
    prof = data["profile"]
    if THICKNESS > prof["thickness"] + 1e-9 or THICKNESS > CASING_MIN:
        raise SystemExit(f"THICKNESS {THICKNESS} exceeds the profile limit {prof['thickness']} or the casings")
    total = 0.0
    for ri, run in enumerate(data["runs"]):
        pts, nrm = run["points"], run["normals"]
        if len(nrm) != segment_count(run):
            raise SystemExit(f"run {ri}: {len(nrm)} normals for {segment_count(run)} segments")
        for si in range(segment_count(run)):
            a, b = to_blender(pts[si]), to_blender(pts[(si + 1) % len(pts)])
            d = b - a
            n = normal_to_blender(nrm[si])
            if abs(n.length - 1.0) > 1e-3 or abs(d.normalized().dot(n)) > 1e-3:
                print(f"INPUT WARNING run {ri} segment {si}: normal {nrm[si]} not a unit normal of {d}")
            total += d.length
    print(f"INPUT {len(data['runs'])} runs, {total:.2f} m, profile {prof}")


def build(data, sheet, coll):
    pts, bands = profile(data["profile"]["height"])
    plain = [k for k, b in enumerate(bands) if b == PLAIN]
    mesh = TrimMesh(sheet, band_mats={b: MAT for b in list(sheet.bands)})
    for ri, run in enumerate(data["runs"]):
        path = [to_blender(p) for p in run["points"]]
        sides = [normal_to_blender(n) for n in run["normals"]]
        n = len(path)
        offsets, report = [], []
        for si in range(segment_count(run)):
            length = (path[(si + 1) % n] - path[si]).length
            off = joint_offsets(length, ri * 7 + si)
            offsets.append(off)
            js = joints_of(length, off)
            report.append(f"{length:.3f}" + (f" (joints at {', '.join(f'{j:.2f}' for j in js)})" if js else ""))
        print(f"RUN {ri}: {len(path)} points, segments {'; '.join(report)}")
        mesh.polyline_sweep(path, pts, bands, up=(0.0, 0.0, 1.0), sides=sides, closed=run["closed"],
                            u_offsets=offsets, ease=THICKNESS - ARRIS_R, ease_steps=ARRIS_STEPS,
                            ease_bands={"paint": "paint_arris"}, margin=RUB_MARGIN,
                            margin_bands={"paint": "paint_rub"}, cap_band="paint", stretch=plain)
    mat = solid_mat(MAT, FRAME_PAINT, PAINT_ROUGH)
    ob = mesh.to_object(stem().replace("_", " ").title().replace(" ", ""), coll, {MAT: mat}, sharp_angle=35.0)
    tag(ob, "body")
    return ob


def main():
    clear_scene()
    data = load_runs()
    check_input(data)
    sheet = skirting_trim.layout()
    ob = build(data, sheet, get_collection("Skirting"))
    print(f"TRIS {ob.name}={tri_count(ob)} (runs from {os.path.relpath(runs_path())})")
    save_blend(blend_path())


if __name__ == "__main__":
    main()
