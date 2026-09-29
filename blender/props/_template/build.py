"""Stage 1: build the geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python blender/props/<name>/build.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402

from template_common import (  # noqa: E402
    BLEND, D, GUNMETAL, H, LEG_BOTTOM, LEG_INSET, LEG_TOP, STEEL_BARE, TOP_T, W, WALNUT_DARK, WALNUT_LIGHT,
    WALNUT_MID, WALNUT_WORN,
)
from arcology_blender import metal, wear, wood  # noqa: E402
from arcology_blender.geo import bm_square_taper, collision_box, finish, join, new_object  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend, tag  # noqa: E402
from arcology_blender.shading import Graph, new_mat  # noqa: E402


# ---------------------------------------------------------------------------
# Materials: `src_*` Principled graphs, baked later. Wear everywhere, medium scale.
# ---------------------------------------------------------------------------
def mat_walnut():
    """Satin walnut veneer: worn convex edges, a little dust on the top."""
    g = Graph(new_mat("src_walnut"))
    base, rough, h = wood.veneer(g, WALNUT_MID, WALNUT_DARK, WALNUT_LIGHT)  # needs wood.board / set_grain
    edge = wear.convex_edges(g, radius=0.0025)
    base, rough = wear.edge_wear(g, base, rough, edge, 1.0, WALNUT_WORN, amount=0.45, rough_delta=0.08)
    base, rough = wear.top_dust(g, base, rough, H - 0.004, H - 0.001, color=(0.16, 0.15, 0.14), amount=0.06)
    return g.finish_height(base, rough, 0.0, h)


def mat_steel():
    """Brushed gunmetal legs: coating worn to bare steel on the edges, grime at the floor."""
    g = Graph(new_mat("src_steel"))
    rough, h = metal.brushed(g, 0.34, axis="Z")
    base = g.mixc(g.mul(wear.convex_edges(g, radius=0.0015), 0.30), GUNMETAL, STEEL_BARE)
    base = wear.floor_grime(g, base, 0.0, 0.03, 0.7)
    return g.finish_height(base, rough, 1.0, h)


def build_materials():
    return {"walnut": mat_walnut(), "steel": mat_steel()}


# ---------------------------------------------------------------------------
# Geometry (world coordinates). Bevel real edges: they catch light.
# ---------------------------------------------------------------------------
def build_body(coll, col_coll, mats):
    top = wood.board("Top", (-W / 2, -D / 2, H - TOP_T), (W / 2, D / 2, H), coll, mats["walnut"], "x", "z", 0.3)
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (W / 2 - LEG_INSET), sy * (D / 2 - LEG_INSET)
            bm_square_taper(bm, x, y, 0.0, H - TOP_T + 0.002, LEG_TOP, LEG_BOTTOM)
    legs = new_object("Legs", bm, coll, material=mats["steel"])
    finish(legs, 0.0015, 2)
    body = join([top, legs], "Template")  # one mesh per exported part, one baked material
    tag(body, "body")

    # Collision for Godot: simplified boxes named -convcolonly, never the render mesh
    tag(collision_box("ColBody", (-W / 2, -D / 2, 0.0), (W / 2, D / 2, H), col_coll), "body_col")
    return body


def main():
    clear_scene()
    mats = build_materials()
    build_body(get_collection("Body"), get_collection("BodyCollision"), mats)
    print(f"TRIS body={part_tris('body')} collision={part_tris('body_col')}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
