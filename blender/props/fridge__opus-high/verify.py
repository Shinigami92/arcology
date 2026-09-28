"""Re-import the exported glb files in a clean scene and print what arrived (variant opus-high).
blender --background --factory-startup --python verify.py
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as S

for p in (S.GLB_BODY, S.GLB_DOOR):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(coll):
            coll.remove(d)
    bpy.ops.import_scene.gltf(filepath=p)
    print("=== ", os.path.basename(p), f"{os.path.getsize(p) / 1e6:.1f} MB")
    total = 0
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        line = f"  {o.name:32s} {o.type:6s} loc=({o.location.x:.4f}, {o.location.y:.4f}, {o.location.z:.4f})"
        line += f" rot={tuple(round(r, 4) for r in o.rotation_euler)} scale={tuple(round(s, 4) for s in o.scale)}"
        if o.parent:
            line += f" parent={o.parent.name}"
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            n = len(o.data.loop_triangles)
            if "col" not in o.name:
                total += n
            vs = [o.matrix_world @ v.co for v in o.data.vertices]
            line += f" tris={n} mats={[m.name for m in o.data.materials]}"
            line += " bounds x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]" % (
                min(v.x for v in vs), max(v.x for v in vs), min(v.y for v in vs), max(v.y for v in vs),
                min(v.z for v in vs), max(v.z for v in vs))
        print(line)
    print("  render tris:", total)
    for im in bpy.data.images:
        print(f"  image {im.name}: {im.size[0]}x{im.size[1]}")
    for m in bpy.data.materials:
        nt = m.node_tree
        p_ = nt.nodes.get("Principled BSDF") if nt else None
        if p_:
            links = {s.name: s.links[0].from_node.type for s in p_.inputs if s.is_linked}
            print(f"  material {m.name}: {links} emission_strength={p_.inputs['Emission Strength'].default_value:.2f}")
