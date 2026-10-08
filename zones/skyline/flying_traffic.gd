@tool
class_name FlyingTraffic
extends Node3D
## Flying traffic in straight lanes between the towers (The Fifth Element),
## all around our building (D-061).
##
## [constant CORRIDORS] holds the routes: a line on the map, the altitudes of
## its lane pairs (one each way, [constant LANE_GAP] apart, right-hand
## traffic), the lane speeds, the mean gap between vehicles and its group.
## Vehicles move on the GPU (assets/shaders/traffic_lane.gdshaderinc): this
## builds, per group, one MultiMesh of bodies per vehicle type plus one of
## light glows for all of them, all static, so traffic costs no CPU per frame.
## Corridors with meshes = false are far enough to be lights only. FarTowers
## keeps its roofs below every corridor ([method roof_limit]); the near towers
## are placed by hand, and the skyline test checks the lanes clear them
## ([method blocked_lanes]). Deterministic, rebuilt on load, never saved.
##
## Groups and sides: OutsideView draws a group's MultiMeshes while a window
## onto one of its sides is in view (metadata/outside_sides: the sides its
## lanes' ends lie on, [method OutsideView.sides_of], or [constant
## GROUP_SIDES]). "north" runs east-west in front of the apartment (the view
## D-047 built), "south" the same behind the building, "east" and "west" are
## the short north-south stretches between them. A north-south line ends at
## the east-west corridors and goes on in the next group, so a view out of one
## side never draws the traffic behind the building, and every group's bounds
## stay outside the building, so occlusion culls them behind its walls.

const CORRIDORS: Array[Dictionary] = [
	# North of the building (the apartment's view, D-047). Crosses the whole
	# view 70 m in front of the windows, around eye level and deep below it:
	# the deep lanes fade into the haze and show how far down the city goes.
	{"group": "north", "from": Vector2(-1500, -70), "to": Vector2(1500, -70), "levels": [-130.0, -95.0, -60.0, -30.0, -8.0, 14.0, 40.0],
		"speed": Vector2(28, 45), "spacing": 150.0, "meshes": true},
	# Between the near ring's spires, higher up.
	{"group": "north", "from": Vector2(-1500, -420), "to": Vector2(1500, -420), "levels": [70.0, 110.0, 150.0],
		"speed": Vector2(40, 60), "spacing": 170.0, "meshes": true},
	# Far express lanes: lights only.
	{"group": "north", "from": Vector2(-1500, -850), "to": Vector2(1500, -850), "levels": [200.0, 260.0],
		"speed": Vector2(60, 80), "spacing": 120.0, "meshes": false},
	# Two avenues running away from the apartment, left and right, from the
	# near corridor on (south of it they go on as "cross", then "south").
	{"group": "north", "from": Vector2(-500, -70), "to": Vector2(-500, -1500), "levels": [20.0, 60.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	{"group": "north", "from": Vector2(450, -70), "to": Vector2(450, -1500), "levels": [-20.0, 30.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	# South of the building, the same pattern 83 m off its south facade.
	{"group": "south", "from": Vector2(-1500, 100), "to": Vector2(1500, 100), "levels": [-122.0, -88.0, -54.0, -26.0, -4.0, 18.0, 44.0],
		"speed": Vector2(28, 45), "spacing": 150.0, "meshes": true},
	{"group": "south", "from": Vector2(1500, 480), "to": Vector2(-1500, 480), "levels": [80.0, 120.0, 160.0],
		"speed": Vector2(40, 60), "spacing": 170.0, "meshes": true},
	{"group": "south", "from": Vector2(1500, 900), "to": Vector2(-1500, 900), "levels": [210.0, 270.0],
		"speed": Vector2(60, 80), "spacing": 120.0, "meshes": false},
	{"group": "south", "from": Vector2(-500, 100), "to": Vector2(-500, 1500), "levels": [20.0, 60.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	{"group": "south", "from": Vector2(450, 100), "to": Vector2(450, 1500), "levels": [-20.0, 30.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	# East and west of the building, between the two: the near corridors
	# crossing the east and west views (levels between the east-west ones, so
	# no two lanes meet at a height) and the avenues' middle stretches.
	{"group": "east", "from": Vector2(95, -70), "to": Vector2(95, 100), "levels": [-112.0, -77.0, -43.0, -18.0, 4.0, 28.0],
		"speed": Vector2(25, 40), "spacing": 85.0, "meshes": true},
	{"group": "west", "from": Vector2(-85, 100), "to": Vector2(-85, -70), "levels": [-108.0, -74.0, -40.0, -16.0, 6.0, 30.0],
		"speed": Vector2(25, 40), "spacing": 85.0, "meshes": true},
	{"group": "east", "from": Vector2(450, -70), "to": Vector2(450, 100), "levels": [-20.0, 30.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
	{"group": "west", "from": Vector2(-500, -70), "to": Vector2(-500, 100), "levels": [20.0, 60.0],
		"speed": Vector2(35, 50), "spacing": 150.0, "meshes": true},
]
## Distance between a lane pair's two directions (m).
const LANE_GAP := 8.0
## Groups drawn for fewer sides than their lanes reach: the east and west
## stretches start at the north corridor and end at the south one, so from a
## north or south window they'd only be a stub at the very edge of the view
## (north views draw exactly what they did before D-061).
const GROUP_SIDES := {"east": OutsideView.EAST, "west": OutsideView.WEST}
## Vehicle types the glow shader knows lamps for (traffic_lights.gdshader).
const MAX_TYPES := 8
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
	var total := 0.0
	for w: float in _weights(types.size()):
		total += w
	# Per group (in table order): bodies per type and glows, each [Transform3D,
	# Color]; the lanes' bounds and the sides they reach.
	var groups: Array[String] = []
	var group_bodies: Array[Array] = []
	var group_glows: Array[Array] = []
	var group_bounds: Array[AABB] = []
	var group_sides: PackedInt32Array = []

	for c: Dictionary in CORRIDORS:
		var group: String = c.get("group", "north")
		var g := groups.find(group)
		if g < 0:
			g = groups.size()
			groups.append(group)
			var per_type: Array[Array] = []
			for t in types.size():
				per_type.append([])
			group_bodies.append(per_type)
			group_glows.append([])
			group_bounds.append(AABB())
			group_sides.append(0)
		group_sides[g] = GROUP_SIDES.get(group, group_sides[g] | OutsideView.sides_of(c["from"]) | OutsideView.sides_of(c["to"]))
		var speed: Vector2 = c["speed"]
		for level: float in c["levels"]:
			for lane: Array in _lanes(c, level):
				var start: Vector3 = lane[0]
				var dir: Vector3 = lane[1]
				var length: float = lane[2]
				var lane_box := AABB(start, Vector3.ZERO).expand(start + dir * length)
				group_bounds[g] = lane_box if group_bounds[g].size == Vector3.ZERO else group_bounds[g].merge(lane_box)
				var frame := Transform3D(Basis.looking_at(dir), start)
				var lane_speed := rng.randf_range(speed.x, speed.y)
				var count := maxi(1, int(length / float(c["spacing"])))
				for i in count:
					var phase := (i + rng.randf_range(-0.35, 0.35)) / count
					var seed_frac := minf(rng.randf(), 0.999)
					var t := _pick(types.size(), total, rng.randf())
					# w: the type (its lamps in the glow shader) plus the bob's seed.
					var custom := Color(fposmod(phase, 1.0), lane_speed / length, length, t + seed_frac)
					(group_glows[g] as Array).append([frame, custom])
					if c["meshes"]:
						(group_bodies[g][t] as Array).append([frame, custom])

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
	# Each type's lamp pair (head z, tail z, height) for the glows.
	var lamps := PackedVector3Array()
	lamps.resize(MAX_TYPES)
	for t in mini(types.size(), MAX_TYPES):
		var aabb := (types[t]["mesh"] as Mesh).get_aabb()
		lamps[t] = Vector3(aabb.position.z, aabb.end.z, aabb.get_center().y)
	glow_material.set_shader_parameter(&"lamps", lamps)
	var quad := QuadMesh.new()

	for g in groups.size():
		var prefix := groups[g].capitalize()
		var bounds := group_bounds[g].grow(10.0)
		for t in types.size():
			var bodies: Array = group_bodies[g][t]
			if not bodies.is_empty():
				_add_multimesh("%sBodies%d" % [prefix, t], types[t]["mesh"], bodies, bounds, body_material, group_sides[g])
		if not (group_glows[g] as Array).is_empty():
			_add_multimesh("%sLights" % prefix, quad, group_glows[g], bounds, glow_material, group_sides[g])


func _add_multimesh(node_name: String, mesh: Mesh, instances: Array, bounds: AABB, material: Material,
		sides: int) -> MultiMeshInstance3D:
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
	mmi.set_meta(OutsideView.META_SIDES, sides)
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
