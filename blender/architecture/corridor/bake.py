"""Stage 2: textures. corridor_trim: generate the wainscot trim sheet (numpy, deterministic),
pack it and wire it into `corridor_trim` (no Cycles bake: the sheet tiles along every run, so a
layout change reuses exactly these pixels). Fixtures: unwrap and bake the `src_*` materials into
one albedo/normal/ORM atlas (bake.bake_part); emissive faces keep their plain material.

  blender -b --factory-startup blender/architecture/corridor/<asset>.blend --python blender/architecture/corridor/bake.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from corridor_common import asset_of_blend, body_objects  # noqa: E402
import wainscot  # noqa: E402
from arcology_blender import bake, geo  # noqa: E402
from arcology_blender.bake import final_material, report_images  # noqa: E402
from arcology_blender.scene import tag  # noqa: E402


def mounting_plane(asset):
    """A large plane just behind the fixture's open mounting side (never saved)."""
    import bmesh
    bm = bmesh.new()
    if asset == "exit_sign":
        pts = [(-1, 0.0002, -1), (1, 0.0002, -1), (1, 0.0002, 1), (-1, 0.0002, 1)]
    else:
        pts = [(-1, -1, 0.0002), (-1, 1, 0.0002), (1, 1, 0.0002), (1, -1, 0.0002)]
    bm.faces.new([bm.verts.new(p) for p in pts])
    return geo.new_object("BakeMount", bm, bpy.context.scene.collection)


def main():
    asset = asset_of_blend(bpy.data.filepath)
    if asset == "corridor_trim":
        albedo, normal, orm = wainscot.generate().images(wainscot.MAT)
        final_material(wainscot.MAT, albedo, normal, orm)
    else:
        import fixtures
        spec = fixtures.BAKE[asset]
        bake.setup(bpy.context.scene)
        mount = mounting_plane(asset)   # the ceiling or wall it's fixed to: contact AO
        bake.bake_part(body_objects(), asset, spec["material"], size=spec["size"])
        geo.remove(mount)
        bake.remove_source_materials()
        # one mesh per glb: the baked part and its plain emissive part as two surfaces
        joined = geo.join(body_objects(), fixtures.JOINED_NAME[asset])
        tag(joined, "body")
    report_images()
    bpy.ops.wm.save_mainfile(compress=False)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
