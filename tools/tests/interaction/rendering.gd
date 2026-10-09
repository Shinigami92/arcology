extends "res://tools/tests/interaction/base.gd"
## Rendering group: the door viewer (peephole), foveation, the MSAA/foveation A/B, reflection warm-up.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["door_viewer", _test_door_viewer],
		["foveation_on_xr_start", _test_foveation_on_xr_start],
		["ab_viewport", _test_ab_viewport],
		["reflections_warmed", _test_reflections_warmed],
	]


## The entrance door's peephole renders its corridor camera only while an eye
## is at the lens on the apartment side, and keeps the image afterwards.
func _test_door_viewer() -> void:
	var viewer: DoorViewer = _main.get_node(PROPS + "DoorEntrance/HingeOrigin/InteractableHinge/Leaf/Peephole")
	var cam := Camera3D.new()
	_main.add_child(cam)
	var saved := PlanarReflection.view_camera
	PlanarReflection.view_camera = cam
	var awake: Array[bool] = []
	# Far, 4 cm in front, 4 cm behind (corridor side), far again.
	for z: float in [1.5, 0.04, -0.12, 1.5]:
		cam.global_position = viewer.to_global(Vector3(0, 0, z))
		viewer.check_eye()
		awake.append(viewer.is_awake())
	PlanarReflection.view_camera = saved
	cam.queue_free()
	# The lens shader compiles (a parse error leaves no uniforms; the lens then isn't drawn).
	var uniforms := DoorViewer.SHADER.get_shader_uniform_list().map(func(u: Dictionary) -> String: return u.name)
	_check("door_viewer", str(awake) == "[false, true, false, false]" and uniforms.has("shown_view"),
			"camera renders far %s, eye at the lens %s, behind the door %s, far again %s; lens shader uniforms %s" % (
				awake + [uniforms]))
	# One eye looks through: centered, the dominant (left) one; the right one when clearly nearer the axis.
	var eyes: Array[int] = [DoorViewer.choose_eye(0.032, 0.032), DoorViewer.choose_eye(0.0, 0.063),
			DoorViewer.choose_eye(0.063, 0.0), DoorViewer.choose_eye(0.03, 0.02)]
	_check("door_viewer_one_eye", str(eyes) == "[0, 0, 1, 0]",
			"eye looking through (0 left, 1 right): centered %d, left at the lens %d, right at the lens %d, right 1 cm nearer %d" % eyes)


## Foveation starts with XR, not before, and refills the shading rate map every
## frame: VRS from the first (desktop) frame with Godot's update-once default
## left XR's map empty, and the headset rendered black (D-056).
func _test_foveation_on_xr_start() -> void:
	var foveation := _main.get_node("Foveation") as Foveation
	var viewport := _main.get_viewport()
	var before := [viewport.vrs_mode, viewport.vrs_update_mode]
	var setting: int = ProjectSettings.get_setting("rendering/vrs/mode")
	foveation.call("_on_xr_started")
	var mode := viewport.vrs_mode
	var update := viewport.vrs_update_mode
	viewport.vrs_mode = before[0]
	viewport.vrs_update_mode = before[1]
	_check("foveation_on_xr_start", setting == Viewport.VRS_DISABLED and mode == Viewport.VRS_XR and update == Viewport.VRS_UPDATE_ALWAYS,
			"project vrs/mode %d (0), after XR start mode %d (XR=2), update %d (always=2)" % [setting, mode, update])


## Every live reflection rendered once at start (its own renderer or a coplanar
## lead's), so its pipelines compiled while loading: entering the bathroom used
## to compile 38 at once (a 23 ms frame, D-056).
func _test_reflections_warmed() -> void:
	var cold: Array[String] = []
	var instances: Array[PlanarReflection] = PlanarReflection._instances
	for r in instances:
		var warmed := not r._viewports.is_empty()
		for other in instances:
			if not other._viewports.is_empty() and r.magnification == 1.0 and other.magnification == 1.0 and other._coplanar(r):
				warmed = true
		if not warmed:
			cold.append(str(r.get_path()))
	_check("reflections_warmed", instances.size() > 0 and cold.is_empty(), "%d surfaces, cold: %s" % [instances.size(), cold])


## ABViewport flips MSAA and foveation with its variant and puts them back.
func _test_ab_viewport() -> void:
	var viewport := _main.get_viewport()
	var foveation := Foveation.find(_main.get_tree())
	var before := [viewport.msaa_3d, foveation.enabled, foveation.min_radius, foveation.strength]
	var ab := ABViewport.new()
	ab.a = {"msaa": 4, "foveation_radius": 35.0}
	ab.b = {"msaa": 2, "foveation_radius": 0.0}
	_main.add_child(ab)
	var a_ok := viewport.msaa_3d == Viewport.MSAA_4X and foveation.enabled and is_equal_approx(foveation.min_radius, 35.0)
	ab.set_variant("B")
	var b_ok := viewport.msaa_3d == Viewport.MSAA_2X and not foveation.enabled
	ab.set_variant("A")
	var back_ok := viewport.msaa_3d == Viewport.MSAA_4X and foveation.enabled
	ab.free()
	viewport.msaa_3d = before[0]
	foveation.set_foveation(before[1], before[2], before[3])
	_check("ab_viewport", a_ok and b_ok and back_ok, "A %s, B (2x, foveation off) %s, A again %s" % [a_ok, b_ok, back_ok])
