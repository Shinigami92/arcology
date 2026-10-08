class_name DoorViewer
extends Node3D
## A door viewer (peephole, D-058). Origin at the inner lens' center, +Z toward
## the viewer. A camera at the outer lens renders the far side into a small
## mono SubViewport; a disc on the inner lens (door_viewer.gdshader) shows it
## as through a fisheye. The camera renders once at start (its pipelines
## compile while loading, D-057) and then only while the viewer's eye is
## within [member wake_distance] in front of the lens, checked 4 times a
## second; in between the lens keeps the last image.
##
## Like a real one, it's seen with one eye: the eye nearer the lens axis, or
## [member dominant_eye] when both are about as near (a head centered on it).
## The other eye sees the lens as dark glass. From afar both see it.

## From the inner lens to the outer lens' face, along -Z (the door's thickness).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var depth := 0.09
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var radius := 0.0072
## Square texture size.
@export var resolution := 384
## The camera's field of view (perspective, so below 180).
@export_range(60.0, 150.0) var fov := 120.0
## Lens angle out per angle in: an eye 4 cm off the lens (the camera's 3 cm
## near plane is the closest it gets) sees the whole field of view.
@export var magnification := 6.0
## The camera renders while an eye is this close in front of the lens.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var wake_distance := 0.35
## The camera's far plane.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var reach := 12.0
@export_flags_3d_render var cull_mask := PlanarReflection.ALL_LAYERS & ~PlanarReflection.LAYER_UNREFLECTED

enum Eye { LEFT, RIGHT }

## The eye that looks through when both are about as near the lens' axis.
## The user is left-eye dominant (D-058).
static var dominant_eye := Eye.LEFT
## How much nearer the axis the other eye must be to take over.
const EYE_MARGIN := 0.015
const HALF_IPD := 0.032

const SHADER := preload("res://assets/shaders/door_viewer.gdshader")
const CHECK_INTERVAL := 0.25

var _viewport: SubViewport
var _camera: Camera3D
var _material: ShaderMaterial
var _shown_view := -1


func _ready() -> void:
	_viewport = SubViewport.new()
	_viewport.name = "View"
	_viewport.size = Vector2i(resolution, resolution)
	_viewport.use_hdr_2d = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	_viewport.positional_shadow_atlas_size = 0
	_viewport.use_occlusion_culling = true
	_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	_camera = Camera3D.new()
	_camera.fov = fov
	_camera.near = 0.01
	_camera.far = reach
	_camera.cull_mask = cull_mask
	_camera.environment = PlanarReflection.environment_for(get_world_3d())
	_viewport.add_child(_camera)
	add_child(_viewport)
	_place_camera()

	_material = ShaderMaterial.new()
	_material.shader = SHADER
	_material.set_shader_parameter("view_texture", _viewport.get_texture())
	_material.set_shader_parameter("live", 1.0)
	_material.set_shader_parameter("radius", radius)
	_material.set_shader_parameter("magnification", magnification)
	_material.set_shader_parameter("tan_half_fov", tan(deg_to_rad(fov) / 2.0))
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * radius * 2.0
	var lens := MeshInstance3D.new()
	lens.name = "Lens"
	lens.mesh = quad
	lens.material_override = _material
	lens.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lens.layers = PlanarReflection.LAYER_UNREFLECTED
	add_child(lens)

	var timer := Timer.new()
	timer.wait_time = CHECK_INTERVAL
	timer.autostart = true
	timer.timeout.connect(check_eye)
	add_child(timer)
	set_process(false)


## Rendering now (an eye is at the lens).
func is_awake() -> bool:
	return _viewport.render_target_update_mode == SubViewport.UPDATE_ALWAYS


func _process(_delta: float) -> void:
	_place_camera()
	var view := _view_eye()
	if view != _shown_view:
		_shown_view = view
		_material.set_shader_parameter("shown_view", view)


## The view index (eye) that sees through the lens now.
func _view_eye() -> int:
	var cam := _eye()
	var xr := XRServer.primary_interface
	if not cam is XRCamera3D or not xr or not xr.is_initialized() or xr.get_view_count() < 2:
		return 0
	var eyes: Array[Vector3] = []
	var origin := (cam.get_parent() as Node3D).global_transform
	for view in 2:
		eyes.append(xr.get_transform_for_view(view, origin).origin)
	# Implausible view poses (not two eyes at the head): half an IPD either side of it.
	var head := cam.global_position
	if eyes[0].distance_to(eyes[1]) > 0.09 or eyes[0].distance_to(head) > 0.1 or eyes[1].distance_to(head) > 0.1:
		eyes = [cam.global_transform * Vector3(-HALF_IPD, 0, 0), cam.global_transform * Vector3(HALF_IPD, 0, 0)]
	var off_axis: Array[float] = []
	for e in eyes:
		var local := to_local(e)
		off_axis.append(Vector2(local.x, local.y).length())
	var view := choose_eye(off_axis[0], off_axis[1])
	if view != _shown_view:
		print("DoorViewer: %s eye looks through (off the lens axis: left %.3f m, right %.3f m)" % [
				["left", "right"][view], off_axis[0], off_axis[1]])
	return view


## The eye (view index) that looks through, from each eye's distance to the
## lens' axis: the nearer one, the dominant one unless the other is clearly nearer.
static func choose_eye(left_off_axis: float, right_off_axis: float) -> int:
	var dominant := int(dominant_eye)
	var off_axis: Array[float] = [left_off_axis, right_off_axis]
	return 1 - dominant if off_axis[1 - dominant] < off_axis[dominant] - EYE_MARGIN else dominant


## Wakes the camera while an eye is at the lens (also called by tests).
func check_eye() -> void:
	var eye := _eye()
	var local := to_local(eye.global_position) if eye else Vector3.ZERO
	var awake := eye != null and local.z > 0.0 and local.length() < wake_distance
	if awake == is_awake():
		return
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS if awake else SubViewport.UPDATE_DISABLED
	set_process(awake)
	if not awake:
		_shown_view = -1
		_material.set_shader_parameter("shown_view", -1)


func _eye() -> Camera3D:
	if PlanarReflection.view_camera and is_instance_valid(PlanarReflection.view_camera):
		return PlanarReflection.view_camera
	return get_viewport().get_camera_3d()


func _place_camera() -> void:
	# Just past the outer lens, looking out (-Z), upright like the door.
	_camera.global_transform = global_transform.translated_local(Vector3(0, 0, -depth - 0.002)).orthonormalized()
