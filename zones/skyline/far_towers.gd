@tool
class_name FarTowers
extends Node3D
## Far city: the near ring's Blender towers repeated on a jittered grid out to
## [member outer_radius], one MultiMesh per tower part (a few dozen draw calls).
##
## Deterministic (fixed seed) so the view from the window is the same every
## run. Tower types come from [member near_towers]: each child with a Model
## (its glb) and metadata/footprint is one type. Every cell gets a type that
## fits it, turned roughly toward the apartment, and sunk into the street so
## its roof lands at a random height: the street plane hides the rest. Cells
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
		types.append({"parts": parts, "radius": radius, "height": height})
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
			for i in towers.size():
				var tower_xform: Transform3D = towers[i]
				mm.set_instance_transform(i, tower_xform * part_xform)
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "Type%dPart%d" % [t, p]
			mmi.multimesh = mm
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
