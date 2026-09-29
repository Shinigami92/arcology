"""Stage 1b: collision that follows the bedding (called by build.py; also runs on its own).

  blender -b --factory-startup blender/props/bed.blend --python blender/props/bed/collision.py

Replaces all collision objects in the .blend (render meshes stay untouched):

  BedTop-colonly         trimesh following the visible top of duvet, fold, throw, sheet and
                         pillows up to y 0.92, skirted down to the frame lip (Godot: ConcavePolygonShape3D)
  BedHead-colonly        the same for the pillows against the headboard (y 0.88 to the headboard)
  BedMattress-convcolonly  solid block under it, top just below its lowest point over the mattress
  BedBase-convcolonly    the platform, floor to lip
  Headboard-convcolonly  the headboard
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import bed_common as C  # noqa: E402
from arcology_blender.collision import collision_box, heightfield, heightfield_collider  # noqa: E402
from arcology_blender.scene import get_collection, save_blend, tag, tri_count  # noqa: E402


def surface_objects():
    """The render surface visible from above in the footprint (for the gap checks)."""
    return C.linen_objects() + C.throw_objects() + C.frame_objects()


def soft_objects():
    """What the trimesh follows; the platform lip is the BedBase box top."""
    return C.linen_objects() + C.throw_objects()


def build_collision():
    for ob in C.collision_objects():
        bpy.data.objects.remove(ob, do_unlink=True)
    coll = get_collection("BedCollision")
    tops = []
    for name, (y0, y1, spacing, tris) in C.COL_PIECES.items():
        ob = heightfield_collider(name, soft_objects(), (C.COL_TOP_LO[0], y0), (C.COL_TOP_HI[0], y1), spacing,
                                    tris, C.COL_SKIRT_Z, coll)
        tops.append(tag(ob, "bed_col"))

    # mattress block: inset so it stays inside the rounded mattress edges, top under the surface
    ins = C.COL_BLOCK_INSET
    lo = (-C.MAT_HALF_W + ins, C.MAT_Y0 + ins)
    hi = (C.MAT_HALF_W - ins, C.MAT_Y1 - ins)
    _, _, zs = heightfield(tops, lo, hi, 0.01, 0.0)
    zmin = min(min(r) for r in zs)
    block_top = zmin - C.COL_BLOCK_CLEAR
    tag(collision_box("BedMattress", (lo[0], lo[1], C.PLAT_Z1 - 0.01), (hi[0], hi[1], block_top), coll), "bed_col")
    for name, (blo, bhi) in C.COLLISION_BOXES.items():
        tag(collision_box(name, blo, bhi, coll), "bed_col")
    print(f"COLLISION {[(o.name, tri_count(o)) for o in tops]} surface min over mattress {zmin:.4f} "
          f"block top {block_top:.4f}")
    return tops, block_top


def main():
    build_collision()
    save_blend(C.BLEND)


if __name__ == "__main__":
    main()
