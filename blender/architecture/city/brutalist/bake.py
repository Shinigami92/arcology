"""Stage 2: generate the four shared texture sets (numpy, deterministic,
brutalist_textures.py), pack them into the .blend and wire the shared
materials the way the glTF exporter expects (bake.final_material + emission).
No Cycles bake: every surface maps into tiling sets, so the five towers (and
any later brutalist building) share exactly these pixels.

  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from brutalist_common import MAT_NEON, MAT_WINDOWS, NEON_EMISSION, WINDOW_EMISSION  # noqa: E402
from brutalist_textures import all_sets  # noqa: E402
from lib_candidates import link_emission  # noqa: E402
from arcology_blender.bake import final_material, report_images  # noqa: E402
from arcology_blender.trim import image_from_array  # noqa: E402

EMISSION = {MAT_WINDOWS: WINDOW_EMISSION, MAT_NEON: NEON_EMISSION}


def main():
    for mat, maps in all_sets().items():
        imgs = {k: image_from_array(f"{mat}_{k}", a, "sRGB" if k in ("albedo", "emission") else "Non-Color")
                for k, a in maps.items()}
        m = final_material(mat, imgs["albedo"], imgs["normal"], imgs["orm"])
        m.use_backface_culling = True  # glTF doubleSided = false: Godot culls back faces (fill rate)
        if "emission" in imgs:
            link_emission(m, imgs["emission"], EMISSION[mat])
    report_images()
    bpy.ops.wm.save_mainfile(compress=False)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
