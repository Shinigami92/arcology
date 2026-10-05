@tool
class_name FarTowers
extends Node3D
## Far city: the near ring's Blender towers repeated on a jittered grid out to
## [member outer_radius], one MultiMesh per tower part (a few dozen draw calls).
##
## Deterministic (fixed seed) so the view from the window is the same every
## run. Tower types come from [member near_towers]: each child with a Model
## (its glb) and metadata/footprint is one type. Every cell gets a type that
## fits it, turned roughly toward the apartment, and sunk below the street so
## its roof lands at a random height. Every tower, near and far, stands on a
## dark root reaching [member root_bottom] (one MultiMesh of boxes): there is
## no street plane, the city goes down into the haze and no tower's end is
## ever in view (D-053). Cells
## behind [member max_z] (the apartment's window wall faces -Z, nothing behind
## it can be seen from inside), inside [member keep_out] (our own building) and
## around the near towers stay empty; under a traffic corridor roofs stay
## below its lanes ([method FlyingTraffic.roof_limit]). The MultiMeshes are
## built on load and never saved.

@export var seed_value := 92
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var cell_size := 90.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var inner_radius := 110.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var outer_radius := 1400.0
## World Y of the street (docs/decisions.md D-008).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var street_y := -180.0
## Visible height above the street: roofs land between these.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var min_height := 60.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var max_height := 520.0
## Area (x/z, in world meters) kept free for the apartment's own building.
@export var keep_out := Rect2(-60.0, -25.0, 120.0, 200.0)
## Cells with a center behind this z aren't built (never visible from inside).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var max_z := 0.0
## The apartment's window plane (world z, the north wall's outer face): from
## inside, nothing behind it can be seen, so the MultiMeshes' bounds end there.
## The far ring wraps around the apartment: its bounds would contain the camera,
## and occlusion culling could then never hide it behind the apartment's walls.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var view_max_z := -3.2
## Cell center jitter, as a share of the cell.
@export_range(0.0, 0.3) var jitter := 0.1
## Largest tower radius (half the footprint's diagonal) per cell size: above
## 0.5 big neighbors may touch, which reads as one complex from afar.
@export_range(0.3, 0.7) var fit := 0.55
## Towers face the apartment within this many degrees.
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

## The roots' facade: lit windows in world space, antialiased (D-020).
const ROOT_SHADER := preload("res://assets/shaders/skyline_facade.gdshader")

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

	# Tower types: parts (mesh + transform in the tower's frame), radius, height.
	var types: Array[Dictionary] = []
	var clear: Array[Vector3] = []  # x, z, radius
	for tower: Node3D in near_towers.get_children():
		var footprint: Vector2 = tower.get_meta(&"footprint", Vector2.ZERO)
		var radius := footprint.length() * 0.5
		clear.append(Vector3(tower.position.x, tower.position.z, radius + cell_size * 0.45))
		var model := tower.get_node_or_null(^"Model") as Node3D
		if not model:
			continue
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

	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var placed: Array[Array] = []  # per type: Array[Transform3D]
	for t in types.size():
		placed.append([])
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
			if dist < inner_radius or dist > outer_radius or center.y > max_z or keep_out.has_point(center):
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
			placed[t].append(Transform3D(Basis(Vector3.UP, yaw), base))

	var roots: Array[Transform3D] = []
	for tower: Node3D in near_towers.get_children():
		roots.append(_root(tower.transform, tower.get_meta(&"footprint", Vector2.ZERO)))
	for t in types.size():
		for tower_xform: Transform3D in placed[t]:
			roots.append(_root(tower_xform, types[t]["footprint"]))
	_add_roots(roots)

	for t in types.size():
		var towers: Array = placed[t]
		if towers.is_empty():
			continue
		var parts: Array[Array] = types[t]["parts"]
		for p in parts.size():
			var part_xform: Transform3D = parts[p][1]
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = parts[p][0]
			mm.instance_count = towers.size()
			var bounds := AABB()
			for i in towers.size():
				var tower_xform: Transform3D = towers[i]
				mm.set_instance_transform(i, tower_xform * part_xform)
				var box: AABB = tower_xform * part_xform * parts[p][0].get_aabb()
				bounds = box if i == 0 else bounds.merge(box)
			if bounds.end.z > view_max_z:
				bounds.size.z = maxf(view_max_z - bounds.position.z, 0.0)
			mm.custom_aabb = bounds
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "Type%dPart%d" % [t, p]
			mmi.multimesh = mm
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(mmi)


## Dims the roots' lit windows to [param share] (DayNight, by day).
func set_light_scale(share: float) -> void:
	if _root_material:
		_root_material.set_shader_parameter(&"window_energy", _root_energy * share)


## A box from a tower's base down to [member root_bottom], inside its footprint.
func _root(tower: Transform3D, footprint: Vector2) -> Transform3D:
	var height := tower.origin.y - root_bottom
	var size := Vector3(footprint.x * root_scale, height, footprint.y * root_scale)
	var center := Vector3(tower.origin.x, tower.origin.y - height * 0.5, tower.origin.z)
	return Transform3D(tower.basis.orthonormalized().scaled_local(size), center)


func _add_roots(roots: Array[Transform3D]) -> void:
	if roots.is_empty():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = BoxMesh.new()
	mm.instance_count = roots.size()
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value + 1
	var bounds := AABB()
	for i in roots.size():
		mm.set_instance_transform(i, roots[i])
		mm.set_instance_custom_data(i, Color(rng.randf(), 0.0, 0.0, 0.0))
		var box := roots[i] * AABB(Vector3(-0.5, -0.5, -0.5), Vector3.ONE)
		bounds = box if i == 0 else bounds.merge(box)
	if bounds.end.z > view_max_z:
		bounds.size.z = maxf(view_max_z - bounds.position.z, 0.0)
	mm.custom_aabb = bounds
	_root_material = ShaderMaterial.new()
	_root_material.shader = ROOT_SHADER
	_root_energy = RenderingServer.shader_get_parameter_default(ROOT_SHADER.get_rid(), &"window_energy")
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Roots"
	mmi.multimesh = mm
	mmi.material_override = _root_material
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
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
