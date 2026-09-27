class_name GrabRay
extends Node3D
## Visible ray for XR Tools' ranged ("gravity") grab.
##
## Add as a child of an [XRToolsFunctionPickup]. While the hand is empty, a
## faint ray shows where the hand points; when the pickup has a ranged target
## the ray locks onto it and brightens, and the target is highlighted (see
## GrabHighlight). Pressing grip then pulls the object into the hand
## (the pickable's ranged_grab_method). Seated players can grab things from
## the floor or across a table this way.

## Show the faint ray even with no target.
@export var show_idle_ray := true
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var idle_length := 1.2
@export var idle_color := Color(0.02, 0.85, 0.91, 0.12)
@export var target_color := Color(0.02, 0.85, 0.91, 0.7)
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var radius := 0.003

var _pickup: XRToolsFunctionPickup
var _controller: XRController3D
var _beam: MeshInstance3D
var _material: StandardMaterial3D


func _ready() -> void:
	_pickup = get_parent() as XRToolsFunctionPickup
	if not _pickup:
		push_error("GrabRay must be a child of XRToolsFunctionPickup: %s" % get_path())
		set_process(false)
		return
	_controller = XRHelpers.get_xr_controller(self)

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
	_material.no_depth_test = false
	_beam = MeshInstance3D.new()
	_beam.mesh = mesh
	_beam.material_override = _material
	_beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_beam.visible = false
	add_child(_beam)


func _process(_delta: float) -> void:
	var active := _controller and _controller.get_is_active() and _pickup.enabled
	if not active or is_instance_valid(_pickup.picked_up_object):
		_beam.visible = false
		return

	var start := _pickup.global_position
	var target := _pickup.closest_object
	var ranged := is_instance_valid(target) \
			and start.distance_to(target.global_position) > _pickup.grab_distance + 0.05
	if ranged:
		_show(start, target.global_position, target_color)
	elif show_idle_ray and not is_instance_valid(target):
		_show(start, start - _pickup.global_basis.z * idle_length, idle_color)
	else:
		_beam.visible = false


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
