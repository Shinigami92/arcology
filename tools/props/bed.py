"""Bed scenes: assets/props/bed/{bed,bed_padded}.tscn (static glb; collision comes from the glb).

    python tools/props/bed.py [--check]
"""

from prop_scenes import Scene, main, static_prop_scene

SIZE = "about 1.70 x 2.15 m, sleeping surface 0.50 m. Origin = bottom center, head end at -Z. Static; collision comes from the glb"
SIT = "Sit with the Seat area in the zone."

DOCS = {
    "bed": f"Double bed, {SIZE}: trimeshes that follow the duvet, fold, throw and pillows (-colonly) over a hidden "
           f"mattress block and the frame (-convcolonly). {SIT}",
    "bed_padded": f"Padded-headboard double bed (kept for other apartments), {SIZE} (-convcolonly). {SIT}",
}


def scenes() -> dict[str, Scene]:
    return {f"assets/props/bed/{name}.tscn": static_prop_scene("Bed", f"assets/props/bed/{name}.glb", doc, model_id="model")
            for name, doc in DOCS.items()}


if __name__ == "__main__":
    main(scenes)
