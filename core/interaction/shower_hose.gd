class_name ShowerHose
extends Node3D
## A flexible hose between a fixed outlet ([member start]) and a pickable's
## connector ([member end]): a hand shower's hose (D-058). A Verlet rope in
## this node's frame (gravity, length, a little bending stiffness, a floor and
## a wall plane) drawn as one skinned tube, a bone per rope point, so a
## moving hose costs only bone updates. Both markers point their -Y along the
## hose where it leaves them.
##
## The hose holds the pickable: pulled further than its length, the hand
## lets go of it ([member snap_slack]), and dropped, it hangs from the hose
## instead of flying off. Simulates while the pickable is held or free, or
## the hose still moves; sleeps once everything rests.

@export var start: Node3D
@export var end: Node3D
## The pickable carrying [member end] (woken by it, held back by the hose).
@export var body: XRToolsPickable
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var length := 1.85
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var radius := 0.0072
@export_range(4, 64) var segments := 48
## Ring vertices around the tube.
@export_range(4, 24) var sides := 10
@export var material: Material
## Sleeve at the [member end] (the hand shower's ferrule): length, radius, material.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var ferrule_length := 0.034
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var ferrule_radius := 0.0098
@export var ferrule_material: Material
## Planes the hose rests on, in this node's frame: y >= floor_height, z >= wall_z.
@export var floor_height := 0.0
@export var wall_z := -0.70
## Held further than the hose reaches by this much, the hand lets go.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var snap_slack := 0.12
## Bounds of the tube for culling, in this node's frame.
@export var bounds := AABB(Vector3(-2, -0.1, -1), Vector3(4, 3, 3))

const ITERATIONS := 16
const DAMPING := 0.95
const REST_SPEED := 0.002  # m per step: below this everywhere the hose rests
const REST_STEPS := 20

var _points := PackedVector3Array()
var _previous := PackedVector3Array()
var _segment := 0.05
var _skeleton: Skeleton3D
var _rest_steps := 0
var _gravity := Vector3.DOWN * 9.8


func _ready() -> void:
	if not start or not end:
		push_error("ShowerHose needs start and end: %s" % get_path())
		return
	_segment = length / segments
	_gravity = Vector3.DOWN * float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))
	_build_tube()
	_lay_out()
	if body:
		body.picked_up.connect(_wake.unbind(1))
		body.dropped.connect(_wake.unbind(1))
	_wake()


func _wake() -> void:
	_rest_steps = 0
	set_physics_process(true)


## Rope points in this node's frame (first = start, last = end).
func get_points() -> PackedVector3Array:
	return _points


## Simulating (not resting).
func is_awake() -> bool:
	return is_physics_processing()


## A start: a sagging curve from start to end.
func _lay_out() -> void:
	var a := _local(start)
	var b := _local(end)
	_points.resize(segments + 1)
	for i in segments + 1:
		var t := float(i) / segments
		var p := a.lerp(b, t)
		p.y -= sin(t * PI) * maxf(0.0, length - a.distance_to(b)) * 0.45
		_points[i] = p
	_previous = _points.duplicate()
	for i in 40:
		_step(1.0 / 90.0)
	_update_bones()


func _local(marker: Node3D) -> Vector3:
	return to_local(marker.global_position)


func _local_dir(marker: Node3D) -> Vector3:
	return (global_basis.inverse() * -marker.global_basis.y).normalized()


func _physics_process(delta: float) -> void:
	_hold_body()
	var moved := _step(delta)
	_update_bones()
	var loose := body and (body.is_picked_up() or not body.freeze)
	_rest_steps = 0 if moved > REST_SPEED or loose else _rest_steps + 1
	if _rest_steps > REST_STEPS:
		set_physics_process(false)


## Keeps the pickable within the hose's reach.
func _hold_body() -> void:
	if not body or body.freeze and not body.is_picked_up():
		return
	var anchor := start.global_position
	var at := end.global_position
	var reach := length * 0.98
	var over := anchor.distance_to(at) - reach
	if over <= 0.0:
		return
	if body.is_picked_up():
		if over > snap_slack:
			body.drop()
		return
	# Free: pull it back onto the sphere it can reach, without outward speed.
	var out := (at - anchor).normalized()
	body.global_position -= out * over
	var outward := body.linear_velocity.dot(out)
	if outward > 0.0:
		body.linear_velocity -= out * outward


## One Verlet step; returns the largest point movement.
func _step(delta: float) -> float:
	var n := _points.size()
	var g := global_basis.inverse() * _gravity * delta * delta
	var moved := 0.0
	for i in range(1, n - 1):
		var p := _points[i]
		var v := (p - _previous[i]) * DAMPING
		_previous[i] = p
		_points[i] = p + v + g
	var a := _local(start)
	var b := _local(end)
	var a_dir := _local_dir(start)
	var b_dir := _local_dir(end)
	for k in ITERATIONS:
		_points[0] = a
		_points[1] = a + a_dir * _segment
		_points[n - 1] = b
		_points[n - 2] = b + b_dir * _segment
		for i in n - 1:
			_constrain(i, i + 1, _segment, 1.0)
		# Bending: two apart stay at least 1.9 segments apart (no kinks).
		for i in n - 2:
			_constrain(i, i + 2, _segment * 1.9, 0.5)
		for i in range(2, n - 2):
			var p := _points[i]
			p.y = maxf(p.y, floor_height + radius)
			p.z = maxf(p.z, wall_z + radius)
			_points[i] = p
	_points[0] = a
	_points[1] = a + a_dir * _segment
	_points[n - 1] = b
	_points[n - 2] = b + b_dir * _segment
	for i in range(1, n - 1):
		moved = maxf(moved, _points[i].distance_to(_previous[i]))
	return moved


## Moves points i and j toward `distance` apart by `stiffness` (1 = exactly
## there; below 1 only pushes them apart, a soft minimum for bending); the
## pinned ends (two points each) don't move.
func _constrain(i: int, j: int, distance: float, stiffness: float) -> void:
	var d := _points[j] - _points[i]
	var current := d.length()
	if current < 1e-6 or (stiffness < 1.0 and current >= distance):
		return
	var n := _points.size()
	var wi := 0.0 if i < 2 or i > n - 3 else 1.0
	var wj := 0.0 if j < 2 or j > n - 3 else 1.0
	if wi + wj == 0.0:
		return
	var fix := d * ((current - distance) / current / (wi + wj) * stiffness)
	_points[i] += fix * wi
	_points[j] -= fix * wj


## One bone per point, oriented along the hose (parallel transport, so the
## tube doesn't twist).
func _update_bones() -> void:
	var n := _points.size()
	var up := Vector3.UP
	for i in n:
		var tangent := (_points[mini(i + 1, n - 1)] - _points[maxi(i - 1, 0)]).normalized()
		if tangent == Vector3.ZERO:
			tangent = Vector3.FORWARD
		var side := up.cross(tangent)
		if side.length_squared() < 1e-6:
			side = Vector3.RIGHT.cross(tangent)
		side = side.normalized()
		up = tangent.cross(side).normalized()
		_skeleton.set_bone_pose_position(i, _points[i])
		_skeleton.set_bone_pose_rotation(i, Basis(side, up, tangent).get_rotation_quaternion())


## The tube: rings along +Z at rest, ring i on bone i; the ferrule on the last bone.
func _build_tube() -> void:
	_skeleton = Skeleton3D.new()
	_skeleton.name = "Skeleton"
	add_child(_skeleton)
	for i in segments + 1:
		_skeleton.add_bone("P%d" % i)
		_skeleton.set_bone_rest(i, Transform3D(Basis.IDENTITY, Vector3(0, 0, i * _segment)))
	_skeleton.reset_bone_poses()

	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _tube_arrays(segments + 1, radius,
			func(ring: int) -> float: return ring * _segment,
			func(ring: int) -> int: return ring, true))
	mesh.surface_set_material(0, material)
	var last := segments
	var sleeve := _tube_arrays(2, ferrule_radius,
			func(ring: int) -> float: return last * _segment - ferrule_length * (1 - ring),
			func(_ring: int) -> int: return last, false)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, sleeve)
	mesh.surface_set_material(1, ferrule_material if ferrule_material else material)

	var tube := MeshInstance3D.new()
	tube.name = "Tube"
	tube.mesh = mesh
	tube.custom_aabb = bounds
	_skeleton.add_child(tube)
	tube.skin = _skeleton.create_skin_from_rest_transforms()
	tube.skeleton = NodePath("..")


## Rings of `sides` vertices at z = z_of(ring), each on bone bone_of(ring);
## UV: x around, y the length in meters.
func _tube_arrays(rings: int, r: float, z_of: Callable, bone_of: Callable, uv_length: bool) -> Array:
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var bones := PackedInt32Array()
	var weights := PackedFloat32Array()
	var indices := PackedInt32Array()
	for ring in rings:
		var z: float = z_of.call(ring)
		var bone: int = bone_of.call(ring)
		for k in sides + 1:
			var angle := TAU * k / sides
			var dir := Vector3(cos(angle), sin(angle), 0)
			verts.append(dir * r + Vector3(0, 0, z))
			normals.append(dir)
			uvs.append(Vector2(float(k) / sides, z if uv_length else float(ring)))
			bones.append_array([bone, 0, 0, 0])
			weights.append_array([1.0, 0.0, 0.0, 0.0])
	for ring in rings - 1:
		for k in sides:
			var a := ring * (sides + 1) + k
			var b := a + sides + 1
			indices.append_array([a, b, a + 1, a + 1, b, b + 1])
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_BONES] = bones
	arrays[Mesh.ARRAY_WEIGHTS] = weights
	arrays[Mesh.ARRAY_INDEX] = indices
	return arrays
