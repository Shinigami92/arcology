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

Quick reference for every public function: blender/lib/README.md (read that
first; the modules' docstrings have the details). A copyable skeleton of the
stage scripts: blender/props/_template/.

Modules:
    scene      scene setup, collections, part tags, GPU, triangle counts, paths
    geo        bmesh primitives (box, cylinder, cone, open box), objects, instances, point attributes,
               bevel/boolean/shading, per-region materials, BVH, hidden-face trim
    curves     paths (Catmull-Rom, Chaikin, fillets, arcs), tubes, profile sweeps, lathes
    shading    `Graph` node builder for procedural source materials, plain and emissive materials, bitmap text
    wear       reusable wear layers on a `Graph` (edge highlights and masks, scuffs, grime, dust, smudges,
               scratches, cup rings, rubbed finishes)
    materials  generic procedural recipes (plastics, rubber, paint, paper)
    wood       veneer layers (per-board grain frame, or grain along a world axis)
    metal      brushed / spun metal finish layer
    soft       soft goods geometry: upholstered blocks, dents, lumps, throw pillows (with seam attribute)
    fabric     upholstery layers for `Graph`: base weave, welts/piping, creases, rub, pilling, stains,
               quilting, knit wool, braided cord
    cloth      cloth simulation (grid, settle, thicken), analytic drapes, garments, height helpers
    trim       trim sheets (numpy bands tiling along U), real-world trim UVs, a face builder with
               profile sweeps around rectangles, extrusions, lofts, slotted planar faces
    surface    seamless square texture tiles (numpy, periodic in U and V): oriented noise, Worley cells,
               staggered plank layouts, cracks, cavity AO, normals, PNG sets, seam checks
    collision  collision boxes and heightfield trimesh colliders for Godot
    bake       UV unwrap and Cycles bake of src_ materials into one PBR atlas set per part
               (texel weighting, emission atlases, spreading parts apart for AO)
    human      MPFB2 base humans (characters): body, detail targets, rig, skin, helper cleanup, measurements
    rig        character armatures: humanoid bone names, OpenXR hand joints, twist bones, pruning, weights,
               pose actions, mirroring meshes and poses to the other side, engine-style test poses (two-bone IK)
    garment    clothing over the skin: skin copies, offset shells, lofts around a limb or along a bent
               centerline, weight transfer, weight smoothing, splitting and rigid regions
    export     glTF export with the project's settings (static, or rigged with skin and animations)
    studio     neutral studio lights, camera and still renders, render.py options
    checks     bounds and Godot conversions, clearance sweeps, collider gaps, glb import report

Conventions: Blender Z up, meters, the asset's front faces -Y (Godot +Z after
export). Procedural materials that get baked are named `src_*` and keep their
Principled BSDF node named "BSDF" (`Graph` does this). Objects are tagged with
a part name (`scene.tag`) so later stages find them without name lists.
Keep this package asset-agnostic: anything with an asset's dimensions belongs
in that asset's scripts.
"""
