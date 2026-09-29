# arcology_blender: quick reference

Shared toolkit for Arcology's scripted Blender assets (D-026, D-028). Read this page instead of
the modules; open a module only for the full docstring of a function you use. Start a new asset
by copying `blender/props/_template/` (a working five-stage skeleton; its `template_common.py`
says what to rename). Richer examples: `fridge` (hinged door, display), `nightstand` (drawer,
lamp with emission, per-board veneer), `bed` (cloth simulation, heightfield collider),
`wardrobe_lit` (sweeps, shared props atlas, `Spread`).

## Stage scripts

One asset = `blender/props/<name>/` with `<name>_common.py` (contract dimensions, colors, paths,
material names, texture sizes, part accessors) and five stages, each a separate Blender run
from the repo root (Blender 5.2: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"`):

| Stage | Command | Does |
|---|---|---|
| build | `blender -b --factory-startup --python build.py` | geometry, `src_*` materials, collision; saves the .blend |
| bake | `blender -b --factory-startup <blend> --python bake.py` | unwrap, bake atlases, final materials; saves the .blend |
| export | `blender -b --factory-startup <blend> --python export.py` | glb files into `assets/props/<name>/` |
| render | `blender -b --factory-startup <blend> --python render.py -- [--quick] [--out DIR] [--suffix S]` | studio thumbnails (not saved) |
| verify | `blender -b --factory-startup --python verify.py` | contract checks, clearance, glb re-import report |

- Every stage script starts with `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`;
  `<name>_common.py` adds `blender/lib` to the path. Import the library as `arcology_blender`.
- **Paths:** repo outputs only via `scene.output_path(...)` (`.blend`: `blender/props/<name>.blend`,
  glb: `assets/props/<name>/...`); never absolute paths. `ARCOLOGY_OUT_DIR=<dir>` redirects every
  `output_path` (the .blend too), so an asset can be rebuilt without touching the repo.
  Thumbnails and debug files go to `scene.scratch_dir(name)` (`ARCOLOGY_RENDER_DIR`, default
  `<temp>/arcology/<name>/`), or `--out`.
- **Part tags:** `scene.tag(ob, part)` sets `ob["arcology_part"]`; later stages find objects with
  `scene.part_objects(part, mesh_only)`, never by name lists. Conventions: `body` (static render
  meshes), `body_col` (collision boxes), `door`, `door_left`, `drawer`, `lamp`, `lamp_light`,
  `pillow`, one tag per exported moving part; `instance` for linked copies that aren't exported.
- **Materials:** procedural sources are `src_*` (built with `Graph`, which names the BSDF node
  "BSDF"); `bake.bake_part` replaces them with one final material per exported part. Unbaked
  materials (opaque glass, LED strips, screens) are plain Principled (`solid_mat`,
  `emissive_image_mat`) and keep their name, so Godot can switch them.
- **Coordinates:** Blender Z up, meters, front faces -Y (Godot +Z after export), origin at the
  bottom center of the footprint. Moving parts are built in local coordinates under a root
  object at the pivot (hinge axis, drawer front's bottom center) and exported with
  `export_glb_at_origin`; grips are `HandleGrip` empties (`geo.new_empty`).
- **Collision:** boxes named `*-convcolonly` (`geo.collision_box`), trimeshes `*-colonly`
  (`collision.heightfield_collider`, only for soft goods); never the render mesh. Moving parts
  get their collision in the Godot scene: print the sizes in verify.py (`checks.collision_report`).
- **Build-time attributes** (`soft.SEAM_ATTR`, `wood.GRAIN_ATTRS`, `curves.ALONG_ATTR`/`AROUND_ATTRS`,
  `cloth.U_ATTR`/`S_ATTR`, your own masks) feed the materials; remove them after baking
  (`geo.remove_attribute`).

## Modules

`g` is a `shading.Graph`; layer functions take and return `(base, rough)` or
`(base, rough, height)` sockets, heights in meters, finished with `g.finish_height(...)`.

### scene
- `repo_path(*parts)` absolute path in the repo; `output_path(*parts)` repo output, honors `ARCOLOGY_OUT_DIR`
- `scratch_dir(name)` thumbnail/debug folder outside the repo (`ARCOLOGY_RENDER_DIR`)
- `clear_scene()` empty scene, metric units; `get_collection(name)` get or create a scene collection
- `tag(ob, part)`, `part_objects(part, mesh_only=False)`, `meshes(objs)` part tags and mesh filter; `PART_KEY`
- `tri_count(ob)`, `part_tris(part)` triangle counts
- `setup_gpu(scene)` Cycles on OptiX, CPU fallback; `set_colorspace(image, name)`
- `save_blend(path)` save (uncompressed); `script_args()` args after `--`

### geo
- `bm_box(bm, lo, hi)`, `bm_cyl(bm, r, depth, matrix, segments=24)` with `cyl_x/cyl_y/cyl_z(center)`, `bm_quad(bm, points)`
- `bm_cone(bm, r_bottom, r_top, depth, matrix, segments=24)` frustum (tapered round legs)
- `bm_square_taper(bm, x, y, z0, z1, top, bottom)` tapered square leg
- `bm_open_box(bm, lo, hi, wall, floor=None, open_axis=2)` open-top box of five slabs (drawers, bins; flip for lids)
- `bm_merge(bm, other)` append a bmesh into another
- `new_object(name, bm, collection, origin, material, parent)`, `new_empty(name, collection, location, parent, display, size)`
- `smooth_object(name, bm, collection, material, angle=80, parent=None)` object + smooth shading (soft goods)
- `instance(src, name, location, rotation, collection=None, parent=None, part=None)` linked duplicate sharing the mesh
- `set_point_attr(ob, name, value)` constant float attribute; `set_float_attr(ob, name, fn(pos, attrs))` computed one
- `remove_attribute(ob, name)`; `set_uvs(ob, uvs)` explicit UVs for a single quad (screens)
- `bevel(ob, width, segments, angle)`, `boolean_cut(ob, cutter)`, `cut(ob, bm, collection)`, `apply_modifiers(ob)`, `remove(ob)`
- `shade(ob, sharp_angle=30)` smooth + sharp edges by angle; `finish(ob, bevel_width, segments, angle, sharp_angle)` bevel, apply, shade
- `assign_by_region(ob, [((lo, hi), mat), ...], default)` materials per polygon center
- `collision_box(name, lo, hi, collection)` `-convcolonly` box; `join(objs, name)`
- `bvh(objs)` world-space BVH; `trim_hidden(ob, covers, reach, dilate, min_nz)` delete upward faces hidden under covers

### curves
- `catmull_rom(points, samples=6)` smooth curve through points (cords); `chaikin(points, iterations=2, closed)` corner cutting
- `round_polyline(points, radius, steps=4, closed, min_turn=25)` fillet corners (bent wire)
- `arc_points(center, radius, a0, a1, n, u_axis, v_axis)` n+1 points on an arc (degrees)
- `circle_profile(radius, segments)`, `rounded_rect_profile(w, h, r, corner_segments)` closed 2D profiles
- `tube(bm, path, radius, segments=8, caps, along_attr, around_attrs, closed=False)` round tube with along/around attributes (braids)
- `sweep(bm, path, profile, up, scales=None, closed, caps)` any profile along a path, per-point scale (hanger arms)
- `lathe(bm, profile_rz, segments, center, closed, attrs, start_angle)` surface of revolution (lamp parts, knobs)
- `drum_shell(bm, r_bottom, r_top, z0, z1, thickness, segments)` thin open drum (plain lamp shade)

### shading
- `new_mat(name)`; `Graph(mat)`: `x y z nx ny nz` world position/normal sockets
- math: `math(op, a, b, clamp)`, `add`, `sub`, `mul`, `maprange(v, fmin, fmax, tmin, tmax, smooth)`, `band(v, lo, hi, soft)`, `rect_xz(lo, hi, soft)`, `dist_xy(cx, cy)`
- vectors: `vec(sx, sy, sz)` scaled position, `offset(offset)` shifted position, `combine(x, y, z)`, `vscale(vector, sx, sy, sz, offset)`
- textures: `noise(scale, detail, rough, vector)`, `wave(scale, distortion, detail, direction, wave_type="BANDS"|"RINGS", vector)`, `pointiness()`, `attribute(name)`
- mixing: `mixf`, `mixc(fac, a, b)`, `scale_color(col, f)`, `bump(height, strength, distance, normal)`
- `finish(base, rough, metal, normal)`, `finish_height(base, rough, metal, height)` connect the BSDF
- `solid_mat(name, base, rough, metal, emission, emission_strength)` unbaked material; `emissive_image_mat(name, image, ...)` screen
- bitmap text: `pixel_canvas`, `fill_rect`, `draw_text` (5x7 `GLYPHS`), `canvas_image`

### wear (all on a Graph)
- `edge_highlight(g, base, rough, lo, hi, smoother, brighter)` pointiness edges (dense meshes only)
- `bevel_edges(g, radius, lo, hi, samples=16)`, `convex_edges(...)` raytraced edge masks (sparse boxes); `edge_wear(g, base, rough, edge, mask, color, amount, rough_delta)`
- `smudges(g, base, rough, region, ...)` fingerprints; `fixture_wear(g, base, rough, points_xz, r_in, r_out, ...)` rubbed halo around knobs
- `rubbed_finish(g, base, rough, mask, lighter, rougher)` finish worn through by hands
- `bottom_scuffs(g, base, rough, z_clean, z_full, rougher, darker, mask=None)`, `floor_grime(g, base, z0, z1, darkest)`, `low_grime(...)`
- `top_dust(g, base, rough, z0, z1, color, amount, rougher)`
- `cup_ring(g, base, rough, center_xy, radius, width, z_band, ...)` mug ring on a top; `scratch(g, base, rough, height, p0_xz, p1_xz, width, mask, ...)`

### materials (finished `src_*` recipes)
- `white_plastic`, `frosted_plastic`, `dark_plastic`, `rubber`, `gloss_paint(name, base)`, `note_paper(name, lo, hi)`

### wood
- `board(name, lo, hi, coll, mat, grain="x", thick="z", seed, bevel, parent, face)` beveled box with its grain frame
- `set_grain(ob, u, b, seed, a0, b0)`, `grain_frame(g)` per-board frame (attributes `GRAIN_ATTRS`)
- `veneer(g, mid, dark, light, ring_spacing, tilt, wander, figure, streak, late_amount, pores, rough)` flat-sawn veneer on `board`s: (base, rough, height)
- `veneer_axis(g, axis, mid, light, dark, rough, figure, bands, streak, ...)` grain along a world axis, no attributes

### metal
- `brushed(g, rough, axis="Z", center=None, streak, height)` brushed or spun (`center`): (rough, height); color and wear are yours

### soft
- `soft_box(center, size, radius, step, band_segments, panel_axis, crown, crown_power, open_faces)` upholstered block with `SEAM_ATTR`
- `press(bm, center, radii, depth, direction, thickness, power)` dent; `jitter(bm, amount, scale, seed)` lumps; `rotate_verts(bm, pivot, deg, axis)`
- `pillow(size, thickness, res, cord, pinch, fullness, folds, fold_count, edge_ripple, seed)` knife-edge pillow
- `flatten_against(bm, point, normal, falloff, region)` squash against a plane (pillow on a mattress)

### fabric (layers on a Graph)
- `fabric_base(g, color, rough, heather, slub, mottle, weave, ...)` -> (base, rough, height); `fabric_finish(g, base, rough, height)`
- `welt(g, base, rough, height, attr=SEAM_ATTR, cord, groove, bead, ...)` piping from the seam attribute
- `creases(g, base, height, mask, stretch, depth, sharp, darker)`, `rub(g, base, rough, mask, shinier, tint)`, `pilling(g, base, height, mask, ...)`
- `stain(g, base, rough, center_xyz, radius, ...)` dried spill; `quilting(g, base, height, spacing, mask, ...)` baffle channels
- `wool_knit(name, color, rib_period, ...)` -> (g, base, rough, height); `braided_cord(g, color, pitch, strands, ...)` on a `curves.tube`

### cloth
- simulation: `cloth_grid(width, length, spacing, place, seam_attr, corner_radius)`, `fold_path(y0, z0, fold_y, radius)`,
  `cloth_settle(ob, [(collider, dist[, friction])], frames, quality, mass, ..., shrink, shrink_attr, shrink_max)`,
  `thicken(ob, thickness, keep_under_attr, drop_front_attr, taper_attr, taper_min)`, `soft_bounds(objs, lo, hi, knee)`
- analytic: `drape(rect, top_z(x, y), overhang, thickness, res, radius, corner_radius, fold_amp, ...)`, `shell_rim(bm, loop, inward, thickness, profile)`
- height helpers: `smoothstep(x, a, b)`, `ridge(x, y, a, b, amp, width, taper)`, `lumps(x, y, amp, scale, seed)`, `bumps(x, y, amount, scale, seed)`
- `hanging_garment(width, length, thick, ...)` shirt on a hanger

### collision
- `collision_box` (from geo); `heightfield(objs, lo, hi, spacing, floor_z)`;
  `heightfield_collider(name, objs, lo, hi, spacing, target_tris, skirt_z, collection, planar_angle, protect, protect_factor)` `-colonly` trimesh over soft goods

### bake
- `setup(scene, ao_distance=0.35)` once per bake stage
- `bake_part(objs, prefix, material_name, hide=(), size=2048, weight=None, emission=None)` unwrap, bake albedo/normal/ORM, assign `material_name`;
  `weight(ob, center, normal)` shrinks hidden faces' texels; `emission=strength` adds `<prefix>_emission`
- `emissive_from_albedo(mat, albedo_image, tint, strength)` glow from the baked albedo (lamp shade) without a second bake
- `Spread([(root, offset), ...], axis=0)` context manager: move parts apart while they bake into one atlas
- `remove_source_materials()`, `report_images()`; lower level: `uv_unwrap`, `uv_unwrap_weighted`, `bake_atlas`, `final_material`, `EmitOverride`, `pixels`

### export
- `export_glb(objs, path)` Y up, transforms applied, textures embedded, triangulated for tangents
- `export_glb_at_origin(root, objs, path)` moving part with its root at the glb origin

### studio
- `studio(scene, camera, target, lens, key, fill, rim)` camera, three area lights, floor, backdrop; `aim(cam, camera, target, lens)`
- `render_still(scene, path, samples=64, size=1024)`; `render_options(default_out)` -> `.samples .out .suffix .has(flag) .value(flag)`

### checks
- `world_bounds(objs)`, `local_bounds(ob)`, `inside(lo, hi, limit_lo, limit_hi)`, `godot(v)`, `godot_size(s)`, `fmt(t, digits=3)`
- `collision_report(objs)` Godot center/size per collider
- `hinge_clearance(root, moving, fixed, angles, axis="Z", sign=-1)`, `slide_clearance(root, moving, fixed, direction, travel, steps)`
- `surface_gap(render, colliders, lo, hi, spacing, classify)`, `probe_gap(..., radius)` collider vs visible surface
- `import_report(glb)` re-import and print objects, origins, triangles, materials (resets the scene: call last)

## Known Blender pitfalls

- **Tangents need triangles.** N-gons from booleans and bevels export without tangents and the
  normal maps break in Godot; `export_glb` adds a temporary Triangulate modifier. Don't bypass it.
- **Pointiness needs vertices.** `wear.edge_highlight` (pointiness) gives face-wide gradients on
  sparse boxes (a board with 8 corners); use `wear.bevel_edges` / `convex_edges` there.
- **Emission strength > 1** exports through `KHR_materials_emissive_strength`; Godot reads it as the
  emission energy, which `LightSwitch`/`HingeLight` switch by material name. Keep switchable lights on
  their own named material (`bake_part(..., emission=...)` or `solid_mat`).
- **AO sees everything that renders.** Hide collision boxes and parts that move apart before a
  bake (`hide=`, `bake.Spread`); a closed door would black out the interior. Bake static
  neighbors together for contact shadows.
- **Cloth solver:** `mass` is per vertex, so dense grids need small values (duvet 0.02); Blender
  clamps `shrink_max` at >= 0, so local expansion inverts the vertex-group weights
  (`cloth_settle` handles it); the result is deterministic for the same inputs.
- **Solidify spikes:** even thickness shoots spikes through sharp cloth wrinkles; `cloth.thicken`
  uses `use_even_offset=False` and `thickness_clamp=1`.
- **Decimate vertex groups mean "may collapse":** to protect vertices store `1 - protect`
  (`heightfield_collider`).
- **Stale matrices:** after moving or rotating objects in a script, call
  `bpy.context.view_layer.update()` before reading `matrix_world` (clearance checks, BVHs).
- **Orphan names:** removing an object keeps its mesh until the file is saved and reloaded; a new
  mesh of the same name becomes `.001` and that name lands in the glb. Re-running a stage that
  recreates objects (the bed's `collision.py`) changes mesh names, not geometry.
- **Boolean cutters without a material** add empty slots; `geo.apply_modifiers` repairs them.
- **mathutils `Vector` math is single precision** and float operations aren't associative:
  rewriting a formula "equivalently" moves vertices by an ulp and changes the glb bytes.
- **`bmesh.ops.create_uvsphere` isn't reproducible:** its face order changes with every Blender
  process (the vertices don't), so the glb changes on every rebuild. Build spheres and bulbs
  with `curves.lathe` (a half-circle profile) instead.
- **Bash reads a running script lazily:** don't edit a shell runner while it runs.

## Rebuild checks (byte identity)

Library changes must keep every existing asset's glbs byte-identical. Rebuild into a scratch
folder and `cmp` against `assets/`:

    ARCOLOGY_OUT_DIR=<scratch>/<name> blender -b --factory-startup --python blender/props/<name>/build.py
    ... bake.py and export.py on <scratch>/<name>/blender/props/<name>.blend (bed: collision.py after build)

Known noise, the same for the committed scripts: with Blender's default threading the glTF
export rounds tangents to 4 decimals and a value near a rounding boundary can flip between runs
(re-export the same .blend a few times; the sofa and both beds show it), and
`create_uvsphere` (the square nightstand's bulb) reorders faces per process. The bed's committed
glb also carries `.001` collider mesh names from an earlier `collision.py` re-run. To compare
two versions of the scripts with each other exactly, run every stage single-threaded
(`blender -t 1 ...`) and, for `create_uvsphere`, with a hook that sorts its faces loaded first
(`--python hook.py --python build.py`); both versions then rebuild deterministically.
