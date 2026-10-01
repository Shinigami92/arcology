"""Stage 2: generate the skirting trim sheet (numpy, deterministic, skirting_trim.py), pack it
into the .blend and wire it into `skirting_paint` the way the glTF exporter expects
(bake.final_material). No Cycles bake: the sheet tiles along every run at real-world scale,
so a layout change reuses exactly these pixels.

  blender -b --factory-startup blender/architecture/apartment_skirting.blend --python blender/architecture/skirting/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from skirting_common import MAT, load_runs  # noqa: E402
import skirting_trim  # noqa: E402
from arcology_blender.bake import final_material, report_images  # noqa: E402


def main():
    sheet = skirting_trim.generate(load_runs()["profile"]["height"])
    albedo, normal, orm = sheet.images(MAT)
    final_material(MAT, albedo, normal, orm)
    report_images()
    bpy.ops.wm.save_mainfile(compress=False)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
