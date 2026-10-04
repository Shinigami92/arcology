"""Flying traffic vehicles (assets/props/traffic/, D-047): import settings only.

    python tools/props/traffic.py --imports   # before the editor first sees new vehicle glbs

The vehicles have no scenes of their own: FlyingTraffic (zones/skyline/flying_traffic.gd)
takes each glb's single mesh and draws it with one ShaderMaterial on the shared
traffic_vehicle atlas (assets/props/traffic/_kit/, moved along its lane by
assets/shaders/traffic_vehicle.gdshader). So the glbs' embedded copies of the atlas are
discarded on import, and the kit textures get mipmaps (and the normal map its flag).
It only writes files that don't exist yet.
"""

from __future__ import annotations

import sys

from prop_scenes import ROOT, TEXTURE_IMPORT, glb_import_text, main, write_new_file

D = "assets/props/traffic"
VEHICLES = ("aircar_sedan", "aircar_taxi", "hover_van", "patrol_cruiser", "sky_bus")


def write_imports() -> int:
    count = 0
    for kind in ("albedo", "orm", "normal", "emission"):
        path = f"{D}/_kit/traffic_vehicle_{kind}.png"
        if (ROOT / path).exists():
            normal = kind == "normal"
            count += write_new_file(path + ".import", TEXTURE_IMPORT.format(
                path=path, normal_map=1 if normal else 0, roughness_mode=1 if normal else 0))
    for name in VEHICLES:
        glb = f"{D}/{name}/{name}.glb"
        if (ROOT / glb).exists():
            count += write_new_file(glb + ".import", glb_import_text(glb, {}, embedded_images=0))
    return count


def scenes() -> dict:
    return {}


if __name__ == "__main__":
    if "--imports" in sys.argv[1:]:
        print(f"{write_imports()} file(s) written")
        sys.exit(0)
    main(scenes)
