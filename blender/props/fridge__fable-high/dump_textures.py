"""Debug: write the packed atlases to the scratchpad as PNG and print UV bounds.

  blender -b --factory-startup <blend> --python dump_textures.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from fridge_common import SCRATCH, body_objects, door_objects  # noqa: E402


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    for img in bpy.data.images:
        if not img.name.startswith("fridge_"):
            continue
        path = os.path.join(SCRATCH, f"tex_{img.name}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save_render(path) if False else img.save(filepath=path)
        print("WROTE", path)
    for ob in body_objects() + door_objects():
        if ob.type != "MESH" or not ob.data.uv_layers:
            continue
        uv = ob.data.uv_layers.active.data
        us = [l.uv.x for l in uv]
        vs = [l.uv.y for l in uv]
        print(f"UV {ob.name:20s} u {min(us):.3f}..{max(us):.3f} v {min(vs):.3f}..{max(vs):.3f} "
              f"mats={[m.name for m in ob.data.materials]}")


if __name__ == "__main__":
    main()
