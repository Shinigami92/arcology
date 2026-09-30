"""Stage 2: generate the shared window trim sheet and the shade fabric (numpy,
deterministic, window_trim.py), pack them into the .blend and wire the trim
into the `window_trim` material the way the glTF exporter expects
(bake.final_material). No Cycles bake: the trim tiles along every member at
real-world scale, so a new spec reuses exactly these pixels.

  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from windows_common import FABRIC_SIZE, MAT_TRIM, TRIM_PX_PER_M, TRIM_SIZE  # noqa: E402
import window_trim  # noqa: E402
from arcology_blender.bake import final_material, report_images  # noqa: E402
from arcology_blender.trim import image_from_array, linear_to_srgb  # noqa: E402


def main():
    sheet = window_trim.generate(TRIM_SIZE, TRIM_PX_PER_M)
    albedo, normal, orm = sheet.images(MAT_TRIM)
    final_material(MAT_TRIM, albedo, normal, orm)
    fa, fn = window_trim.shade_fabric(FABRIC_SIZE)
    for img in (image_from_array("shade_fabric_albedo", linear_to_srgb(fa), "sRGB"),
                image_from_array("shade_fabric_normal", fn, "Non-Color")):
        img.use_fake_user = True  # no material uses them in Blender (Godot's shade does)
    report_images()
    bpy.ops.wm.save_mainfile(compress=False)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
