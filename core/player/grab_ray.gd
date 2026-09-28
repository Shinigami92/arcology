class_name GrabRay
extends Node3D
## Ranged ("gravity") grab with a visible ray.
##
## Add as a child of an [XRToolsFunctionPickup] (with its own ranged_enable
## off). While the hand is empty and nothing is within reach, this finds the
## pickable closest to where the hand points (within [member max_distance]
## and [member max_angle], with line of sight), draws a ray to it and
## highlights it. Pressing grip hands it to the pickup, and the pickable's
## ranged_grab_method (LERP) flies it into the hand.
##
## Replaces XR Tools' built-in ranged grab, which is broken in 4.6.0-dev1
## (see docs/decisions.md D-017).

@export_custom(PROPERTY_HINT_NONE, "suffix:m") var max_distance := 6.0
@export_range(1.0, 30.0, 0.5, "degrees") var max_angle := 12.0
## Layers searched for pickables. Default: layer 3 (Pickable Objects).
@export_flags_3d_physics var pickable_mask := 1 << 2
## Layers that block line of sight. Default: layer 1 (Static World).
@export_flags_3d_physics var occluder_mask := 1
## Show the faint ray even with no target.
@export var show_idle_ray := true
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var idle_length := 2.5
@export var idle_color := Color(0.02, 0.85, 0.91, 0.12)
@export var target_color := Color(0.02, 0.85, 0.91, 0.75)
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var radius := 0.003

var target: XRToolsPickable

var _pickup: XRToolsFunctionPickup
var _controller: XRController3D
var _beam: MeshInstance3D
var _material: StandardMaterial3D
var _grip_down := false
var _query := PhysicsShapeQueryParameters3D.new()
var _sphere := SphereShape3D.new()
var _ray := PhysicsRayQueryParameters3D.new()


func _ready() -> void:
	_pickup = get_parent() as XRToolsFunctionPickup
	if not _pickup:
		push_error("GrabRay must be a child of XRToolsFunctionPickup: %s" % get_path())
		set_process(false)
		return
	_controller = XRHelpers.get_xr_controller(self)
	_sphere.radius = max_distance
	_query.shape = _sphere
	_query.collision_mask = pickable_mask
	_ray.collision_mask = occluder_mask
	_build_beam()


func _process(_delta: float) -> void:
	var active := _controller and _controller.get_is_active() and _pickup.enabled
	var busy := is_instance_valid(_pickup.picked_up_object) or is_instance_valid(_pickup.closest_object)
	_set_target(_find_target() if active and not busy else null)

	if active:
		_handle_grip()

	if not active or is_instance_valid(_pickup.picked_up_object):
		_beam.visible = false
	elif target:
		_show(_pickup.global_position, target.global_position, target_color)
	elif show_idle_ray and not busy:
		_show(_pickup.global_position, _pickup.global_position - _pickup.global_basis.z * idle_length, idle_color)
	else:
		_beam.visible = false


func _handle_grip() -> void:
	# Same hysteresis as XRToolsFunctionPickup, so both see the same press.
	var grip := _controller.get_float(_pickup.pickup_axis_action)
	var threshold := XRTools.get_grip_threshold()
	if _grip_down and grip < threshold - 0.1:
		_grip_down = false
	elif not _grip_down and grip > threshold + 0.1:
		_grip_down = true
		if target and not is_instance_valid(_pickup.picked_up_object):
			var grabbed := target
			_set_target(null)
			# XR Tools has no public "pick up this" call; this is what its own
			# ranged grab does on grip.
			_pickup._pick_up_object(grabbed)


func _find_target() -> XRToolsPickable:
	var origin := _pickup.global_position
	var forward := -_pickup.global_basis.z
	var min_dot := cos(deg_to_rad(max_angle))
	_query.transform = Transform3D(Basis.IDENTITY, origin)
	var space := get_world_3d().direct_space_state
	var best: XRToolsPickable
	var best_dot := min_dot
	for hit in space.intersect_shape(_query, 32):
		var pickable := hit.collider as XRToolsPickable
		if not pickable or not pickable.can_ranged_grab or not pickable.can_pick_up(_pickup):
			continue
		var to := pickable.global_position - origin
		var dist := to.length()
		if dist < 0.01 or dist > max_distance:
			continue
		var d := forward.dot(to / dist)
		if d <= best_dot:
			continue
		# Line of sight: nothing static between the hand and the object.
		_ray.from = origin
		_ray.to = pickable.global_position
		_ray.exclude = [pickable.get_rid()]
		if not space.intersect_ray(_ray).is_empty():
			continue
		best = pickable
		best_dot = d
	return best


func _set_target(new_target: XRToolsPickable) -> void:
	if new_target == target:
		return
	if is_instance_valid(target):
		target.request_highlight(self, false)
	target = new_target
	if target:
		target.request_highlight(self, true)


func _build_beam() -> void:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = 1.0
	mesh.radial_segments = 6
	mesh.rings = 1
	mesh.cap_top = false
	mesh.cap_bottom = false
	_material = StandardMaterial3D.new()
	_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	_beam = MeshInstance3D.new()
	_beam.mesh = mesh
	_beam.material_override = _material
	_beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_beam.visible = false
	add_child(_beam)


func _show(from: Vector3, to: Vector3, color: Color) -> void:
	var length := from.distance_to(to)
	if length < 0.01:
		_beam.visible = false
		return
	var dir := (to - from) / length
	# Cylinder is along Y; build a basis whose Y points at the target.
	var up := Vector3.UP if absf(dir.dot(Vector3.UP)) < 0.99 else Vector3.RIGHT
	var x := up.cross(dir).normalized()
	var z := x.cross(dir)
	_beam.global_transform = Transform3D(Basis(x, dir * length, z), from + dir * length * 0.5)
	_material.albedo_color = color
	_beam.visible = true
