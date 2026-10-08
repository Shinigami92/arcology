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
##
## The same ray presses buttons from afar (D-054): pointing at anything a
## fingertip can press ([RayButtons]) snaps the ray to it and highlights it;
## [member press_action] (Steam Frame: R1 or R2; elsewhere the trigger)
## presses it through the button's own touch signals, as a fingertip would,
## and holds it until released. An exact hit on a button wins over a pickable;
## a pickable wins over a button the ray only passes near.

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
## OpenXR action that presses the pointed button.
@export var press_action := "ui_press"
## The ray snaps to a button whose center is within this angle.
@export_range(0.5, 10.0, 0.5, "degrees") var snap_angle := 3.0

const HIGHLIGHT := preload("res://assets/materials/grab_highlight.tres")

var target: XRToolsPickable
## The button the ray points at (or holds pressed), and where it meets it.
var button: Area3D
var button_point := Vector3.ZERO

var _pickup: XRToolsFunctionPickup
var _controller: XRController3D
var _beam: MeshInstance3D
var _material: StandardMaterial3D
var _grip_down := false
var _query := PhysicsShapeQueryParameters3D.new()
var _sphere := SphereShape3D.new()
var _ray := PhysicsRayQueryParameters3D.new()
# Stand-in fingertip that presses buttons (it never touches physics).
var _presser: Area3D
var _pressing: Area3D
var _press_down := false
var _hover_meshes: Array[MeshInstance3D] = []


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
	_presser = Area3D.new()
	_presser.name = "RayPresser"
	_presser.top_level = true
	_presser.monitoring = false
	_presser.monitorable = false
	_presser.collision_layer = 0
	_presser.collision_mask = 0
	_presser.set_meta(&"ray_presser", true)
	add_child(_presser)


func _process(_delta: float) -> void:
	var active := _controller and _controller.get_is_active() and _pickup.enabled
	var busy := is_instance_valid(_pickup.picked_up_object) or is_instance_valid(_pickup.closest_object)
	var aim := {}
	var pickable: XRToolsPickable = null
	if is_instance_valid(_pressing):
		aim = {"area": _pressing, "point": button_point}
	elif active and not busy:
		aim = find_button(_pickup.global_position, -_pickup.global_basis.z)
		if aim.is_empty() or not aim["exact"]:
			pickable = _find_target()
			if pickable:
				aim = {}
	_set_target(pickable)
	_set_button(aim.get("area"), aim.get("point", Vector3.ZERO))

	if active:
		_handle_grip()
		_handle_press()
	elif is_instance_valid(_pressing):
		release_button()

	if not active or is_instance_valid(_pickup.picked_up_object):
		_beam.visible = false
	elif button:
		_show(_pickup.global_position, button_point, target_color)
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


## The button a ray from [param origin] along [param forward] points at
## ({"area", "point", "exact"}, empty if none); see [RayButtons].
func find_button(origin: Vector3, forward: Vector3) -> Dictionary:
	return RayButtons.pick(get_tree(), get_world_3d().direct_space_state, origin, forward.normalized(),
			max_distance, snap_angle, occluder_mask)


## Presses [param area] at [param point] as a fingertip would, until
## [method release_button].
func press_button(area: Area3D, point: Vector3) -> void:
	release_button()
	_pressing = area
	button_point = point
	_presser.global_position = point
	area.area_entered.emit(_presser)
	if _controller:
		_controller.trigger_haptic_pulse("haptic", 0.0, 0.35, 0.04, 0.0)


func release_button() -> void:
	if is_instance_valid(_pressing):
		_pressing.area_exited.emit(_presser)
	_pressing = null


func _handle_press() -> void:
	var down := _controller.is_button_pressed(press_action)
	if down == _press_down:
		return
	_press_down = down
	if down and button:
		press_button(button, button_point)
	elif not down:
		release_button()


func _set_button(area: Area3D, point: Vector3) -> void:
	button_point = point
	if not is_instance_valid(button):
		button = null  # freed with a zone that streamed out (D-062)
	if area == button:
		return
	_hover(button, false)
	button = area
	_hover(button, true)


## Hover look: the button's own (a "ray_hover" Callable in its metadata, e.g.
## the world terminal's keys), else the grab highlight on its visible part.
func _hover(area: Area3D, on: bool) -> void:
	if not is_instance_valid(area):
		for mesh in _hover_meshes:
			if is_instance_valid(mesh):
				mesh.material_overlay = null
		_hover_meshes.clear()
		return
	if area.has_meta(&"ray_hover"):
		(area.get_meta(&"ray_hover") as Callable).call(on)
		return
	if on:
		var root: Node = area
		var area_button := area as XRToolsInteractableAreaButton
		if area_button and area_button.has_node(area_button.button):
			root = area_button.get_node(area_button.button)
		if root is MeshInstance3D:
			_hover_meshes.append(root)
		for node in root.find_children("*", "MeshInstance3D", true, false):
			_hover_meshes.append(node as MeshInstance3D)
		for mesh in _hover_meshes:
			mesh.material_overlay = HIGHLIGHT
	else:
		for mesh in _hover_meshes:
			if is_instance_valid(mesh):
				mesh.material_overlay = null
		_hover_meshes.clear()


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
	# A pointer, not a light: never drawn in mirrors (D-049).
	_beam.layers = PlanarReflection.LAYER_UNREFLECTED
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
