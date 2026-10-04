"""Stage 5: contract checks in the source, then re-import every glb.

  blender -b --factory-startup --python blender/props/traffic/verify.py

Prints per vehicle (Godot axes, relative to the origin): AABB size and
center, the points between the headlights and between the taillights, the
triangle count against the budget, the material; then checks each glb has
one mesh object with the one material, and the kit PNGs exist.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from traffic_common import (  # noqa: E402
    BLEND, EMISSION, MATERIAL, TRI_BUDGET, TRI_DEFAULT, VEHICLES, glb_path, kit_png, vehicle_object,
)
from arcology_blender.checks import fmt, godot, godot_size, local_bounds  # noqa: E402
from arcology_blender.scene import tri_count  # noqa: E402


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    ok = True
    for v in VEHICLES:
        ob = vehicle_object(v)
        lo, hi = local_bounds(ob)
        c = (lo + hi) / 2
        tris = tri_count(ob)
        budget = TRI_BUDGET.get(v, TRI_DEFAULT)
        mats = [m.name for m in ob.data.materials]
        head, tail = Vector(ob["headlights_center"]), Vector(ob["taillights_center"])
        good = (tris <= budget and mats == [MATERIAL] and c.length < 0.02 and head.y > 0 > tail.y
                and not any(ob.location))
        ok &= good
        print(f"VEHICLE {v}: size={fmt(godot_size(hi - lo), 3)} center={fmt(godot(c), 3)} "
              f"headlights={fmt(godot(head), 3)} taillights={fmt(godot(tail), 3)} "
              f"tris={tris}/{budget} mats={mats} {'OK' if good else 'FAIL'}")
    mat = bpy.data.materials[MATERIAL]
    bsdf = [n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
    print(f"EMISSION strength={bsdf.inputs['Emission Strength'].default_value} (expected {EMISSION})")
    for kind in ("albedo", "normal", "orm", "emission"):
        p = kit_png(kind)
        print(f"KIT {p} {'exists' if os.path.exists(p) else 'MISSING'}")
        ok &= os.path.exists(p)

    for v in VEHICLES:
        path = glb_path(v)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=path)
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        others = [o.name for o in bpy.data.objects if o.type != "MESH"]
        ob = meshes[0] if len(meshes) == 1 else None
        mats = [m.name for m in ob.data.materials] if ob else []
        imgs = sorted(f"{i.name}:{i.size[0]}x{i.size[1]}" for i in bpy.data.images)
        lo, hi = local_bounds(ob) if ob else (Vector(), Vector())
        nose = ob is not None and _nose_is_plus_y(ob)
        good = (ob is not None and not others and mats == [MATERIAL] and ((lo + hi) / 2).length < 0.02
                and ob.matrix_world.is_identity and nose)
        ok &= good
        print(f"GLB {os.path.basename(path)} {os.path.getsize(path) / 1e6:.2f}MB meshes={len(meshes)} "
              f"other={others} tris={tri_count(ob) if ob else 0} mats={mats} nose+Y={nose} images={imgs} "
              f"{'OK' if good else 'FAIL'}")
    print("CONTRACT", "OK" if ok else "FAIL")


def _nose_is_plus_y(ob):
    """The headlight faces (brightest emission) sit at the +Y end (Godot -Z after import)."""
    mat = ob.data.materials[0]
    tex = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and "emissi" in n.image.name.lower()]
    if not tex:
        return False
    img = tex[0].image
    w, h = img.size
    px = img.pixels[:]
    uv = ob.data.uv_layers.active.data
    front, back = 0.0, 0.0
    lo, hi = local_bounds(ob)
    for p in ob.data.polygons:
        u, v = sum((uv[i].uv for i in p.loop_indices), Vector((0.0, 0.0))) / p.loop_total
        x, y = min(int(u * w), w - 1), min(int(v * h), h - 1)
        k = (y * w + x) * 4
        r, g, b = px[k], px[k + 1], px[k + 2]
        white = min(r, g, b)  # headlights are white, everything else colored
        if p.center.y > hi.y - 0.4:
            front = max(front, white)
        if p.center.y < lo.y + 0.4:
            back = max(back, white)
    return front > 0.8 and front > back


if __name__ == "__main__":
    main()
