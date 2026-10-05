@tool
class_name FlyingTraffic
extends Node3D
## Flying traffic in straight lanes between the towers (The Fifth Element).
##
## [constant CORRIDORS] holds the routes: a line on the map, the altitudes of
## its lane pairs (one each way, [constant LANE_GAP] apart, right-hand
## traffic), the lane speeds and the mean gap between vehicles. Vehicles move
## on the GPU (assets/shaders/traffic_lane.gdshaderinc): this builds one
## MultiMesh of bodies per vehicle type plus one of light glows, all static,
## so traffic costs no CPU per frame. Corridors with meshes = false are far
## enough to be lights only. FarTowers keeps its roofs below every corridor
## ([method roof_limit]); the near towers are placed by hand, and the skyline
## test checks the lanes clear them ([method blocked_lanes]). Deterministic,
## rebuilt on load, never saved.

const CORRIDORS: Array[Dictionary] = [
	# Crosses the whole view 70 m in front of the windows, around eye level and
	# deep below it: the deep lanes fade into the haze and show how far down
	# the city goes.
	{"from": Vector2(-1500, -70), "to": Vector2(1500, -70), "levels": [-130.0, -95.0, -60.0, -30.0, -8.0, 14.0, 40.0],
		"speed": Vector2(28, 45), "spacing": 150.0, "meshes": true},
	# Between the near ring's spires, higher up.
	{"from": Vector2(-1500, -420), "to": Vector2(1500, -420), "levels": [70.0, 110.0, 150.0],
		"speed": Vector2(40, 60), "spacing": 170.0, "meshes": true},
	# Far express lanes: lights only.
	{"from": Vector2(-1500, -850), "to": Vector2(1500, -850), "levels": [200.0, 260.0],
		"speed": Vector2(60, 80), "spacing": 120.0, "meshes": false},
	# Two avenues running away from the apartment, left and right; they start
	# behind the window wall, so vehicles appear at the edge of the view.
	{"from": Vector2(-500, 500), "to": Vector2(-500, -1500), "levels": [20.0, 60.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	{"from": Vector2(450, 500), "to": Vector2(450, -1500), "levels": [-20.0, 30.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
]
## Distance between a lane pair's two directions (m).
const LANE_GAP := 8.0
## Room kept around lanes: sideways (m) and below the lowest lane (m).
const CLEARANCE := 20.0
const CLEARANCE_BELOW := 15.0
const VEHICLE_SHADER := preload("res://assets/shaders/traffic_vehicle.gdshader")
const LIGHTS_SHADER := preload("res://assets/shaders/traffic_lights.gdshader")

@export var seed_value := 92
## Vehicle types (glb scenes, each one mesh on the traffic_vehicle atlas,
## nose -Z). Empty: placeholder boxes.
@export var vehicles: Array[PackedScene] = []
## Relative frequency per entry of [member vehicles].
@export var weights: PackedFloat32Array = []
## Shared atlas of the vehicle glbs (traffic_vehicle_*.png in their _kit).
@export var albedo: Texture2D
@export var orm: Texture2D
@export var normal: Texture2D
@export var emission: Texture2D
@export var emission_energy := 4.0
## Brightness of the light glows at night (DayNight scales it by day).
@export var light_energy := 8.0
## Its fog settings are mirrored into the light glows (unshaded, additive).
@export var world_environment: WorldEnvironment
## The apartment's window plane (world z, the north wall's outer face): from
## inside, nothing behind it can be seen, so the MultiMeshes' bounds end there.
## Bounds around the apartment would contain the camera, and occlusion culling
## could then never hide the traffic behind the apartment's walls.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var view_max_z := -3.2
@export_tool_button("Regenerate") var regenerate_action := generate

# The light glows' material and the share of light_energy shown now (DayNight
# dims the glows by day).
var _glow_material: ShaderMaterial
var _light_scale := 1.0


func _ready() -> void:
	generate()


## Lowest world height a tower roof within [param radius] of [param center]
## (x, z) may reach; INF when no corridor passes nearby.
func roof_limit(center: Vector2, radius: float) -> float:
	var limit := INF
	for c: Dictionary in CORRIDORS:
		var a: Vector2 = c["from"]
		var b: Vector2 = c["to"]
		var closest := Geometry2D.get_closest_point_to_segment(center, a, b)
		if center.distance_to(closest) < radius + LANE_GAP * 0.5 + CLEARANCE:
			var levels: Array = c["levels"]
			limit = minf(limit, float(levels.min()) - CLEARANCE_BELOW)
	return limit


## Lanes that pass through a near tower (its footprint plus CLEARANCE, below
## the top of its model): "corridor/level -> tower" per hit.
func blocked_lanes(near_towers: Node3D) -> PackedStringArray:
	var hits: PackedStringArray = []
	for tower: Node3D in near_towers.get_children():
		var footprint: Vector2 = tower.get_meta(&"footprint", Vector2.ZERO)
		var top := tower.global_position.y + _model_height(tower)
		var world_to_tower := tower.global_transform.affine_inverse()
		for ci in CORRIDORS.size():
			var c: Dictionary = CORRIDORS[ci]
			for level: float in c["levels"]:
				if level > top + CLEARANCE:
					continue
				for lane: Array in _lanes(c, level):
					var start: Vector3 = lane[0]
					var dir: Vector3 = lane[1]
					var length: float = lane[2]
					for s in range(0, int(length) + 1, 4):
						var p := world_to_tower * (start + dir * s)
						if absf(p.x) < footprint.x * 0.5 + CLEARANCE and absf(p.z) < footprint.y * 0.5 + CLEARANCE:
							hits.append("%d/%.0f -> %s" % [ci, level, tower.name])
							break
	return hits


## Stops (or restarts) every vehicle where it is now. Frozen, the lanes start
## over from their phase 0 positions.
func set_frozen(frozen: bool) -> void:
	for mmi: Node in get_children():
		var material := (mmi as MultiMeshInstance3D).material_override as ShaderMaterial
		material.set_shader_parameter(&"time_scale", 0.0 if frozen else 1.0)


## Dims the light glows to [param share] of [member light_energy] (DayNight).
func set_light_scale(share: float) -> void:
	_light_scale = share
	if _glow_material:
		_glow_material.set_shader_parameter(&"energy", light_energy * share)


func generate() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()

	var types := _vehicle_types()
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var bodies: Array[Array] = []  # per type: [Transform3D, Color]
	var glows: Array[Array] = []
	for t in types.size():
		bodies.append([])
		glows.append([])
	var bounds := AABB()
	var total := 0.0
	for w: float in _weights(types.size()):
		total += w

	for c: Dictionary in CORRIDORS:
		var speed: Vector2 = c["speed"]
		for level: float in c["levels"]:
			for lane: Array in _lanes(c, level):
				var start: Vector3 = lane[0]
				var dir: Vector3 = lane[1]
				var length: float = lane[2]
				var lane_box := AABB(start, Vector3.ZERO).expand(start + dir * length)
				bounds = lane_box if bounds.size == Vector3.ZERO else bounds.merge(lane_box)
				var frame := Transform3D(Basis.looking_at(dir), start)
				var lane_speed := rng.randf_range(speed.x, speed.y)
				var count := maxi(1, int(length / float(c["spacing"])))
				for i in count:
					var phase := (i + rng.randf_range(-0.35, 0.35)) / count
					var custom := Color(fposmod(phase, 1.0), lane_speed / length, length, rng.randf())
					var t := _pick(types.size(), total, rng.randf())
					glows[t].append([frame, custom])
					if c["meshes"]:
						bodies[t].append([frame, custom])

	bounds = bounds.grow(10.0)
	if bounds.end.z > view_max_z:
		bounds.size.z = view_max_z - bounds.position.z
	var body_material := ShaderMaterial.new()
	body_material.shader = VEHICLE_SHADER
	for key: String in ["albedo", "orm", "normal", "emission"]:
		var tex: Texture2D = get(key)
		if tex:
			body_material.set_shader_parameter(key + "_tex", tex)
	if not albedo:
		body_material.set_shader_parameter(&"paint", Color(0.12, 0.13, 0.15))
	body_material.set_shader_parameter(&"emission_energy", emission_energy)
	var glow_material := ShaderMaterial.new()
	glow_material.shader = LIGHTS_SHADER
	glow_material.set_shader_parameter(&"energy", light_energy * _light_scale)
	_glow_material = glow_material
	if world_environment and world_environment.environment:
		var env := world_environment.environment
		glow_material.set_shader_parameter(&"fog_density", env.fog_density if env.fog_enabled else 0.0)
		glow_material.set_shader_parameter(&"fog_height", env.fog_height)
		glow_material.set_shader_parameter(&"fog_height_density", env.fog_height_density if env.fog_enabled else 0.0)
	var quad := QuadMesh.new()

	for t in types.size():
		var mesh: Mesh = types[t]["mesh"]
		var aabb := mesh.get_aabb()
		if not bodies[t].is_empty():
			_add_multimesh("Bodies%d" % t, mesh, bodies[t], bounds, body_material)
		if not glows[t].is_empty():
			var mmi := _add_multimesh("Lights%d" % t, quad, glows[t], bounds, glow_material)
			mmi.set_instance_shader_parameter(&"head_z", aabb.position.z)
			mmi.set_instance_shader_parameter(&"tail_z", aabb.end.z)
			mmi.set_instance_shader_parameter(&"lamp_y", aabb.get_center().y)


func _add_multimesh(node_name: String, mesh: Mesh, instances: Array, bounds: AABB, material: Material) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = instances.size()
	for i in instances.size():
		var frame: Transform3D = instances[i][0]
		var custom: Color = instances[i][1]
		mm.set_instance_transform(i, frame)
		mm.set_instance_custom_data(i, custom)
	# The shader moves the instances along their lanes: cull by the lanes' bounds.
	mm.custom_aabb = bounds
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.material_override = material
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)
	return mmi


## [start, direction, length] of each direction of a corridor's lane pair at
## [param level]: right-hand traffic, LANE_GAP apart.
func _lanes(c: Dictionary, level: float) -> Array[Array]:
	var a: Vector2 = c["from"]
	var b: Vector2 = c["to"]
	var length := a.distance_to(b)
	var d := (b - a) / length
	var right := Vector2(-d.y, d.x)  # right of travel, seen from above (x east, z south)
	var lanes: Array[Array] = []
	for way: float in [1.0, -1.0]:
		var start := (a if way > 0.0 else b) + right * way * LANE_GAP * 0.5
		lanes.append([Vector3(start.x, level, start.y), Vector3(d.x, 0.0, d.y) * way, length])
	return lanes


func _vehicle_types() -> Array[Dictionary]:
	var types: Array[Dictionary] = []
	for scene: PackedScene in vehicles:
		if not scene:
			continue
		# Read the mesh from the scene's data: instancing a glb and freeing it
		# again left ~130 meshes rendering (+150 draw calls, D-047).
		var state := scene.get_state()
		var mesh: Mesh = null
		for n in state.get_node_count():
			for p in state.get_node_property_count(n):
				if not mesh and state.get_node_property_name(n, p) == &"mesh":
					mesh = state.get_node_property_value(n, p) as Mesh
		if mesh:
			types.append({"mesh": mesh})
	if types.is_empty():
		var box := BoxMesh.new()
		box.size = Vector3(2.0, 1.4, 4.8)
		types.append({"mesh": box})
	return types


func _weights(count: int) -> PackedFloat32Array:
	var w := PackedFloat32Array()
	for i in count:
		w.append(weights[i] if i < weights.size() else 1.0)
	return w


func _pick(count: int, total: float, r: float) -> int:
	var w := _weights(count)
	var x := r * total
	for i in count:
		x -= w[i]
		if x < 0.0:
			return i
	return count - 1


func _model_height(tower: Node3D) -> float:
	var top := 0.0
	for mi: Node in tower.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var aabb := tower.global_transform.affine_inverse() * m.global_transform * m.get_aabb()
		top = maxf(top, aabb.end.y)
	return top
