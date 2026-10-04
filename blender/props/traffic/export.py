"""Stage 3: one glb per vehicle (textures embedded) and the shared atlas PNGs in _kit/.

  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/export.py

Every glb carries the same `traffic_vehicle` material and atlas; the Godot side
can map it to one shared material from the _kit PNGs (as city.py --imports does
for the towers) so the five MultiMeshes share one texture set.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from traffic_common import KIT_DIR, PREFIX, VEHICLES, glb_path, kit_png, vehicle_object  # noqa: E402
from arcology_blender.export import export_glb  # noqa: E402


def save_kit():
    os.makedirs(KIT_DIR, exist_ok=True)
    for kind in ("albedo", "normal", "orm", "emission"):
        img = bpy.data.images[f"{PREFIX}_{kind}"]
        path = kit_png(kind)
        img.save(filepath=path)  # writes the stored (packed) pixels; the .blend is not saved here
        print(f"KIT {path} {img.size[0]}x{img.size[1]} {img.colorspace_settings.name}")


def main():
    for vehicle in VEHICLES:
        ob = vehicle_object(vehicle)
        if any(ob.location) or any(ob.rotation_euler) or any(abs(s - 1.0) > 1e-9 for s in ob.scale):
            raise RuntimeError(f"{vehicle}: transform not identity")
        export_glb([ob], glb_path(vehicle))
    save_kit()


if __name__ == "__main__":
    main()
