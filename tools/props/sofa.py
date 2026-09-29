"""Sofa scenes: assets/props/sofa/{sofa,sofa_boucle}.tscn (static glb) and their pickable throw pillows.

    python tools/props/sofa.py [--check]
"""

from prop_scenes import Scene, main, pickable_scene, static_prop_scene

DOC = ("Three-seat sofa, about 2.1 x 0.9 m, seat surface 0.44 m. Origin = bottom center, front faces +Z. Static; "
       "collision boxes come from the glb (-convcolonly): seat block, back, arms. Sit with the Seat area in the zone. ")

VARIANTS = {  # suffix: (doc tail, pillow size, pillow mass)
    "": ("Petrol-teal, piped seams, lived-in wear; built by blender/props/sofa/ (Opus 5.5, D-029).",
         (0.43, 0.13, 0.43), 0.45),
    "_boucle": ("Grey-blue boucle; not placed yet, kept for other apartments; built by blender/props/sofa_boucle/ "
                "(Fable 5.1, D-029).", (0.42, 0.11, 0.42), 0.6),
}


def pillow(suffix: str, size: tuple, mass: float) -> Scene:
    glb = f"assets/props/sofa/sofa{suffix}_pillow.glb"
    return pickable_scene(
        "Pillow", glb, mass=mass, doc=f"Throw pillow, {size[0]:g} x {size[1]:g} x {size[2]:g} m, {mass:g} kg. "
        "Origin = center. Pickable; soft thud on impact.",
        boxes=[("CollisionShape3D", (0, 0, 0), size, "BoxShape3D_pillow")],
        friction=0.9, linear_damp=0.3, angular_damp=1.5, material_id="PhysicsMaterial_fabric",
        ext_ids={"sfx/pillow_thud": "3_thud"})


def scenes() -> dict[str, Scene]:
    out: dict[str, Scene] = {}
    for suffix, (tail, size, mass) in VARIANTS.items():
        out[f"assets/props/sofa/sofa{suffix}.tscn"] = static_prop_scene(
            "Sofa", f"assets/props/sofa/sofa{suffix}.glb", DOC + tail, model_id="1_model")
        out[f"assets/props/sofa/sofa{suffix}_pillow.tscn"] = pillow(suffix, size, mass)
    return out


if __name__ == "__main__":
    main(scenes)
