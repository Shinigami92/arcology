"""Stage 1: build each kit asset's geometry and materials, save one .blend per asset.

  blender -b --factory-startup --python blender/architecture/corridor/build.py [-- --asset a,b]

corridor_trim: the wainscot swept along tools/blockout/corridor_trim.json (wainscot.py), one
mesh, materials `corridor_trim` (placeholder until bake.py wires the trim sheet) and
`corridor_led`. The fixtures: fixtures.py, procedural `src_*` materials baked by bake.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from corridor_common import ANTHRACITE, blend_path, contract, load_runs, selected_assets  # noqa: E402
import wainscot  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag, tri_count  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402


def check_runs(data):
    """The run file's own consistency: unit normals perpendicular to their segments."""
    from corridor_common import to_blender
    from mathutils import Vector
    total = 0.0
    for ri, run in enumerate(data["runs"]):
        pts, nrm = run["points"], run["normals"]
        nseg = wainscot.segment_count(run)
        if len(nrm) != nseg:
            raise SystemExit(f"run {ri}: {len(nrm)} normals for {nseg} segments")
        for si in range(nseg):
            d = to_blender(pts[(si + 1) % len(pts)]) - to_blender(pts[si])
            n = Vector((nrm[si][0], -nrm[si][1], 0.0))
            if abs(n.length - 1.0) > 1e-3 or abs(d.normalized().dot(n)) > 1e-3:
                print(f"INPUT WARNING run {ri} segment {si}: normal {nrm[si]} not a unit normal of {d}")
            total += d.length
    prof = data["profile"]
    c = contract("corridor_trim")
    if abs(prof["height"] - c["height"]) > 1e-6 or abs(prof["thickness"] - c["depth"]) > 1e-6:
        print(f"INPUT WARNING run file profile {prof} differs from the contract (height {c['height']}, depth {c['depth']})")
    print(f"INPUT {len(data['runs'])} runs, {total:.2f} m, profile {prof}")


def build_trim():
    data = load_runs()
    check_runs(data)
    sheet = wainscot.layout()
    mats = {wainscot.MAT: solid_mat(wainscot.MAT, ANTHRACITE, wainscot.LAMINATE_ROUGH),
            wainscot.MAT_LED: wainscot.led_material()}
    ob, report = wainscot.build(data, sheet, get_collection("Trim"), mats)
    tag(ob, "body")
    for line in report:
        print(line)
    return ob


def main():
    for asset in selected_assets():
        clear_scene()
        if asset == "corridor_trim":
            build_trim()
        else:
            import fixtures
            fixtures.BUILDERS[asset]()
        print(f"TRIS {asset} body={part_tris('body')}")
        save_blend(blend_path(asset))


if __name__ == "__main__":
    main()
