"""Shared Blender toolkit for Arcology assets (D-026, D-028).

Asset build scripts live in `blender/<category>/<name>/` and run in Blender's
background mode, one stage per script:

    blender -b --factory-startup --python build.py              # geometry + procedural src_ materials
    blender -b --factory-startup <blend> --python bake.py       # UVs, bake to albedo/normal/ORM
    blender -b --factory-startup <blend> --python export.py     # glb files into assets/
    blender -b --factory-startup <blend> --python render.py     # studio thumbnails (not saved)
    blender -b --factory-startup --python verify.py             # clearance checks, glb re-import

Make the package importable from an asset script with:

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))

Modules:
    scene      scene setup, collections, part tags, GPU, triangle counts, paths
    geo        bmesh primitives, objects, bevel/boolean/shading, per-region materials
    shading    `Graph` node builder for procedural source materials, plain and emissive materials, bitmap text
    wear       reusable wear layers on a `Graph` (edge highlights, scuffs, grime, dust, smudges)
    materials  generic procedural recipes (plastics, rubber, paint, paper)
    bake       UV unwrap and Cycles bake of src_ materials into one PBR atlas set per part
    export     glTF export with the project's settings
    studio     neutral studio lights, camera and still renders
    checks     BVH clearance checks for hinged and sliding parts, glb import report

Conventions: Blender Z up, meters, the asset's front faces -Y (Godot +Z after
export). Procedural materials that get baked are named `src_*` and keep their
Principled BSDF node named "BSDF" (`Graph` does this). Objects are tagged with
a part name (`scene.tag`) so later stages find them without name lists.
Keep this package asset-agnostic: anything with an asset's dimensions belongs
in that asset's scripts.
"""
