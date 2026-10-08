@tool
class_name FarTowers
extends Node3D
## Far city: the near ring's Blender towers repeated on a jittered grid out to
## [member outer_radius] all around our building, one MultiMesh per tower part
## and side of the building (a few dozen draw calls per side).
##
## Deterministic (fixed seed) so the view from a window is the same every
## run. Tower types come from [member near_towers]: each child with a Model
## (its glb) and metadata/footprint is a tower; one type per glb. Every cell
## gets a type that fits it, turned roughly toward the building, and sunk
## below the street so its roof lands at a random height. Every tower, near and
## far, stands on a dark root reaching [member root_bottom] (one MultiMesh of
## boxes per side): there is no street plane, the city goes down into the haze
## and no tower's end is ever in view (D-053). Beyond the towers, out to
## [member band_radius], a band of plain boxes with the same lit-window facade
## stands in for the rest of the city: silhouettes layered into the haze
## (D-054). Cells inside [member inner_radius] and [member keep_out] (our own
## building) and around the near towers stay empty; under a traffic corridor
## roofs stay below its lanes ([method FlyingTraffic.roof_limit]).
##
## Sides (D-061): every tower, root and band box belongs to the sides of the
## building it stands beyond ([method OutsideView.sides_of]; a corner to two),
## and each side gets its own MultiMeshes (metadata/outside_sides), drawn by
## OutsideView only while a window onto that side is in view. A corner's towers
## are in both its sides' MultiMeshes, so a view out of one side draws only
## that side. Each side's bounds end at its facade
## ([method OutsideView.clamp_to_side]): from inside, nothing behind it can be
## seen, and bounds that contain the camera could never be occlusion-culled
## behind the building's walls. The MultiMeshes are built on load and never
## saved.

@export var seed_value := 92
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var cell_size := 90.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var inner_radius := 110.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var outer_radius := 1400.0
## World Y of the street (docs/decisions.md D-008).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var street_y := -180.0
## Visible height above the street: roofs land between these.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var min_height := 60.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var max_height := 520.0
## Area (x/z, in world meters) kept free for our own building and its street.
@export var keep_out := Rect2(-40.0, -35.0, 90.0, 85.0)
## Cell center jitter, as a share of the cell.
@export_range(0.0, 0.3) var jitter := 0.1
## Largest tower radius (half the footprint's diagonal) per cell size: above
## 0.5 big neighbors may touch, which reads as one complex from afar.
@export_range(0.3, 0.7) var fit := 0.55
## Towers face the building within this many degrees.
@export_range(0.0, 180.0, 1.0, "suffix:°") var facing_spread := 35.0
## Parent of the near ring's towers (tools/props/city.py): the tower types,
## and each child's position and metadata/footprint clears the cells around it.
@export var near_towers: Node3D
## Its corridors cap the roofs beneath them.
@export var traffic: FlyingTraffic
## Where the towers' roots end, far below anything the windows show.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var root_bottom := -2000.0
## A root's footprint as a share of its tower's (inside the silhouette).
@export_range(0.3, 1.0) var root_scale := 0.8
## The far skyline band: boxes out to this radius, one per cell of
## [member band_cell], their roofs between [member band_height] (above the
## street), footprints between [member band_width].
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var band_radius := 3500.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var band_cell := 130.0
@export var band_height := Vector2(120.0, 640.0)
@export var band_width := Vector2(40.0, 85.0)

## The roots' facade: lit windows in world space, antialiased (D-020).
const ROOT_SHADER := preload("res://assets/shaders/skyline_facade.gdshader")
const SIDES := 4

var _root_material: ShaderMaterial
var _root_energy := 2.2
@export_tool_button("Regenerate") var regenerate_action := generate


func _ready() -> void:
	generate()


func generate() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()
	if not near_towers:
		return

	# Tower types (one per glb): parts (mesh + transform in the tower's frame),
	# radius, height, footprint. Every near tower clears the cells around it
	# and stands on a root.
	var types: Array[Dictionary] = []
	var type_keys: Dictionary[String, int] = {}
	var clear: Array[Vector3] = []  # x, z, radius
	var roots: Array[Array] = []  # per side: Array[Transform3D]
	for s in SIDES:
		roots.append([])
	for tower: Node3D in near_towers.get_children():
		var footprint: Vector2 = tower.get_meta(&"footprint", Vector2.ZERO)
		var radius := footprint.length() * 0.5
		var at := Vector2(tower.position.x, tower.position.z)
		clear.append(Vector3(at.x, at.y, radius + cell_size * 0.45))
		_add_to_sides(roots, _root(tower.transform, footprint), OutsideView.sides_of(at))
		var model := tower.get_node_or_null(^"Model") as Node3D
		if not model:
			continue
		var key := model.scene_file_path if model.scene_file_path else String(tower.name)
		if type_keys.has(key):
			continue
		type_keys[key] = types.size()
		var parts: Array[Array] = []
		_collect_parts(model, Transform3D.IDENTITY, parts)
		var height := 0.0
		for part: Array in parts:
			var mesh: Mesh = part[0]
			var xform: Transform3D = part[1]
			height = maxf(height, (xform * mesh.get_aabb()).end.y)
		types.append({"parts": parts, "radius": radius, "height": height, "footprint": footprint})
	if types.is_empty():
		return

	# The grid: every cell draws the same random numbers whether it's built or
	# not, so a change on one side doesn't move the towers on another.
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var placed: Array[Array] = []  # per side, per type: Array[Transform3D]
	for s in SIDES:
		var per_type: Array[Array] = []
		for t in types.size():
			per_type.append([])
		placed.append(per_type)
	var n := int(ceil(outer_radius / cell_size))
	for ix in range(-n, n + 1):
		for iz in range(-n, n + 1):
			var center := Vector2(ix, iz) * cell_size
			center += Vector2(rng.randf_range(-jitter, jitter), rng.randf_range(-jitter, jitter)) * cell_size
			var r_type := rng.randf()
			var r_height := rng.randf()
			var r_facing := rng.randf_range(-1.0, 1.0)
			var r_thin := rng.randf()
			var dist := center.length()
			if dist < inner_radius or dist > outer_radius or keep_out.has_point(center):
				continue
			# Thin out the far ring a little; the fog hides it anyway.
			if r_thin < clampf((dist - 600.0) / 1600.0, 0.0, 0.5):
				continue
			if clear.any(func(c: Vector3) -> bool: return center.distance_to(Vector2(c.x, c.y)) < c.z):
				continue
			var roof := lerpf(min_height, max_height, pow(r_height, 2.2))
			if traffic:
				roof = minf(roof, traffic.roof_limit(center, cell_size * fit) - street_y)
				if roof < min_height * 0.5:
					continue
			var t := _pick_type(types, roof, cell_size * fit, r_type)
			if t < 0:
				continue
			var height: float = types[t]["height"]
			var yaw := atan2(-center.x, -center.y) + deg_to_rad(facing_spread) * r_facing
			var base := Vector3(center.x, street_y - maxf(height - roof, 0.0), center.y)
			var xform := Transform3D(Basis(Vector3.UP, yaw), base)
			var sides := OutsideView.sides_of(center)
			for s in SIDES:
				if sides & (1 << s):
					(placed[s][t] as Array).append(xform)
			_add_to_sides(roots, _root(xform, types[t]["footprint"]), sides)
	_band(roots)

	_root_material = ShaderMaterial.new()
	_root_material.shader = ROOT_SHADER
	_root_energy = RenderingServer.shader_get_parameter_default(ROOT_SHADER.get_rid(), &"window_energy")
	for s in SIDES:
		var side := 1 << s
		var side_name := OutsideView.SIDE_NAMES[s]
		_add_roots(side_name + "Roots", roots[s], side)
		for t in types.size():
			var towers: Array = placed[s][t]
			if towers.is_empty():
				continue
			var parts: Array[Array] = types[t]["parts"]
			for p in parts.size():
				var part_mesh: Mesh = parts[p][0]
				var part_xform: Transform3D = parts[p][1]
				var mm := MultiMesh.new()
				mm.transform_format = MultiMesh.TRANSFORM_3D
				mm.mesh = part_mesh
				mm.instance_count = towers.size()
				var bounds := AABB()
				for i in towers.size():
					var tower_xform: Transform3D = towers[i]
					mm.set_instance_transform(i, tower_xform * part_xform)
					var box: AABB = tower_xform * part_xform * part_mesh.get_aabb()
					bounds = box if i == 0 else bounds.merge(box)
				mm.custom_aabb = OutsideView.clamp_to_side(bounds, side)
				var mmi := MultiMeshInstance3D.new()
				mmi.name = "%sType%dPart%d" % [side_name, t, p]
				mmi.multimesh = mm
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				mmi.set_meta(OutsideView.META_SIDES, side)
				add_child(mmi)


## Dims the roots' lit windows to [param share] (DayNight, by day).
func set_light_scale(share: float) -> void:
	if _root_material:
		_root_material.set_shader_parameter(&"window_energy", _root_energy * share)


## Adds the far skyline band's boxes (deterministic), from [member root_bottom]
## up to their roofs, to [param roots] per side. The rows north of the
## building draw their numbers first, as they did before the band went all
## around (D-061), so the view from the apartment stays the same.
func _band(roots: Array[Array]) -> void:
	var n := int(ceil(band_radius / band_cell))
	for south: bool in [false, true]:
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_value + (3 if south else 2)
		for ix in range(-n, n + 1):
			for iz in (range(1, n + 1) if south else range(-n, 1)):
				var center := Vector2(ix, iz) * band_cell
				center += Vector2(rng.randf_range(-0.3, 0.3), rng.randf_range(-0.3, 0.3)) * band_cell
				var roof := street_y + lerpf(band_height.x, band_height.y, pow(rng.randf(), 1.8))
				var size := Vector2(rng.randf_range(band_width.x, band_width.y), rng.randf_range(band_width.x, band_width.y))
				var yaw := rng.randf_range(-0.4, 0.4) + atan2(-center.x, -center.y)
				var dist := center.length()
				if dist < outer_radius or dist > band_radius:
					continue
				var height := roof - root_bottom
				var box_basis := Basis(Vector3.UP, yaw).scaled_local(Vector3(size.x, height, size.y))
				var box := Transform3D(box_basis, Vector3(center.x, roof - height * 0.5, center.y))
				_add_to_sides(roots, box, OutsideView.sides_of(center))


static func _add_to_sides(per_side: Array[Array], value: Variant, sides: int) -> void:
	for s in SIDES:
		if sides & (1 << s):
			(per_side[s] as Array).append(value)


## A box from a tower's base down to [member root_bottom], inside its footprint.
func _root(tower: Transform3D, footprint: Vector2) -> Transform3D:
	var height := tower.origin.y - root_bottom
	var size := Vector3(footprint.x * root_scale, height, footprint.y * root_scale)
	var center := Vector3(tower.origin.x, tower.origin.y - height * 0.5, tower.origin.z)
	return Transform3D(tower.basis.orthonormalized().scaled_local(size), center)


func _add_roots(node_name: String, roots: Array, side: int) -> void:
	if roots.is_empty():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = BoxMesh.new()
	mm.instance_count = roots.size()
	var bounds := AABB()
	for i in roots.size():
		var root: Transform3D = roots[i]
		mm.set_instance_transform(i, root)
		# The facade's random pattern from the position: a corner's box is in two
		# sides' MultiMeshes and must look the same in both (they may overlap).
		var seed_hash := fposmod(sin(root.origin.x * 0.1271 + root.origin.z * 0.3117) * 43758.5453, 1.0)
		mm.set_instance_custom_data(i, Color(seed_hash, 0.0, 0.0, 0.0))
		var box := root * AABB(Vector3(-0.5, -0.5, -0.5), Vector3.ONE)
		bounds = box if i == 0 else bounds.merge(box)
	mm.custom_aabb = OutsideView.clamp_to_side(bounds, side)
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.material_override = _root_material
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.set_meta(OutsideView.META_SIDES, side)
	add_child(mmi)


## A random type at least [param roof] tall (else the tallest) that fits in
## [param max_radius]; -1 if none fits.
func _pick_type(types: Array[Dictionary], roof: float, max_radius: float, r: float) -> int:
	var fits: Array[int] = []
	var tallest := -1
	for t in types.size():
		if types[t]["radius"] > max_radius:
			continue
		if tallest < 0 or types[t]["height"] > types[tallest]["height"]:
			tallest = t
		if types[t]["height"] >= roof:
			fits.append(t)
	if fits.is_empty():
		return tallest
	return fits[mini(int(r * fits.size()), fits.size() - 1)]


func _collect_parts(node: Node, xform: Transform3D, parts: Array[Array]) -> void:
	for child: Node in node.get_children():
		var child_xform := xform
		if child is Node3D:
			child_xform = xform * (child as Node3D).transform
		if child is MeshInstance3D and (child as MeshInstance3D).mesh:
			parts.append([(child as MeshInstance3D).mesh, child_xform])
		_collect_parts(child, child_xform, parts)
