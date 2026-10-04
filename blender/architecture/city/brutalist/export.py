"""Stage 3: one glb per tower into assets/architecture/city/<name>/, and the four
shared texture sets as PNGs into assets/architecture/city/_kit/brutalist/.

  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/export.py

Each glb holds the tower mesh `<name>` and `<name>_blink` (if any), origin at
the base center on the street, unrotated, with the four shared materials
(city_brutal_concrete / _windows / _metal / _neon). The glbs embed the same
texture pixels as the kit PNGs, so a glb also looks right on its own; Godot
maps the materials by name to shared materials made from the kit files and
discards the embedded copies (like window_trim, D-033).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from brutalist_common import MATERIALS, glb_path, kit_png, tower_objects, towers  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402
from arcology_blender.trim import image_pixels, write_png  # noqa: E402


def main():
    for t in towers():
        objs = sorted(tower_objects(t["name"]), key=lambda o: o.name)
        for o in objs:
            o.location = (0.0, 0.0, 0.0)
            o.rotation_euler = (0.0, 0.0, 0.0)
        export_glb(objs, glb_path(t["name"]))
    for mat in MATERIALS:
        for kind in ("albedo", "normal", "orm", "emission"):
            img = bpy.data.images.get(f"{mat}_{kind}")
            if img is not None:
                write_png(kit_png(mat, kind), image_pixels(img))


if __name__ == "__main__":
    main()
