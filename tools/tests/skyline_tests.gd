extends Node
## Measures skyline shimmer: the share of city pixels whose luminance changes
## by more than 0.1 when the view turns by half a pixel (what small head
## movements do in VR). Lower is steadier. Started by main.gd:
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --test=skyline
##
## Prints "SHIMMER <variant>: <percent>" and fails if the default view is
## above [constant MAX_SHIMMER_PCT] (docs/decisions.md D-020). Traffic is frozen
## while measuring (moving vehicles aren't shimmer). Also checks that no traffic
## lane runs through a near tower (D-047), and that the city is hidden while no
## window is in view and drawn again through a doorway (OutsideView, D-048), that
## each side of the city is drawn only while a window facing it is on screen and
## its bounds stay outside the building (D-061), and that the live reflection in
## view renders, one at a time (D-049).

const MAX_SHIMMER_PCT := 7.0
const TRIALS := 4
## Camera views (position, yaw in degrees; 0 = -Z) and whether the city should be hidden.
const OUTSIDE_VIEWS: Array[Array] = [
	[Vector3(0.5, 1.7, 5.0), 0.0, true],      # bathroom, facing its north wall
	[Vector3(-1.0, 1.7, 2.9), 0.0, true],     # hallway, facing its north wall
	[Vector3(0.55, 1.7, 2.9), 180.0, true],   # hallway, facing the bathroom door
	[Vector3(2.05, 1.7, 3.3), 10.0, false],   # hallway, through the living room door to the window
	[Vector3(0.0, 1.7, -2.0), 0.0, false],    # living room, facing the window
]
## Stand-in windows facing east, south and west (until those units exist): a
## notifier outside the building (position, facing) and a camera in front of
## it looking out (position, yaw), with nothing else onto the city in view.
const SIDE_VIEWS: Array[Array] = [
	[Vector3(60, 1.7, 7), Vector3(1, 0, 0), Vector3(56, 1.7, 7), -90.0],
	[Vector3(5, 1.7, 60), Vector3(0, 0, 1), Vector3(5, 1.7, 56), 180.0],
	[Vector3(-50, 1.7, 7), Vector3(-1, 0, 0), Vector3(-46, 1.7, 7), 90.0],
]
## Camera views (position, yaw) and the PlanarReflections that must show live ([] = none at all).
const REFLECTION_VIEWS: Array[Array] = [
	[Vector3(1.4, 1.7, 5.2), 180.0, ["Props/BathMirror/Reflection"]],          # bathroom, facing the mirror
	[Vector3(0.0, 1.7, -1.5), 0.0, ["Windows/LivingWindow/Reflection"]],       # living room, facing the window
	[Vector3(-5.0, 1.7, -1.5), 0.0, ["Windows/BedroomWindow/Reflection"]],     # bedroom, facing the window
	[Vector3(4.7, 1.7, 2.9), 30.0, ["Windows/KitchenWindow/Reflection"]],      # hallway, through the kitchen
	[Vector3(1.3, 1.7, 5.2), 90.0, ["Props/Shower/Reflection"]],               # bathroom, facing the shower glass
	[Vector3(0.0, 1.7, -1.5), 180.0, []],                                      # living room, back to the window
	[Vector3(-1.0, 1.7, 2.9), 0.0, []],                                        # hallway, facing its north wall
]

var _main: Node3D


func _ready() -> void:
	_main = get_parent() as Node3D
	var player: XROrigin3D = _main.get_node("Player")
	player.get_node("PlayerBody").enabled = false
	player.global_transform = Transform3D.IDENTITY
	await get_tree().create_timer(1.0).timeout

	var traffic: FlyingTraffic = _main.get_node("Skyline/Traffic")
	var blocked := traffic.blocked_lanes(_main.get_node("Skyline/NearTowers"))
	print("TEST %s traffic_lanes_clear: %s" % ["PASS" if blocked.is_empty() else "FAIL", ", ".join(blocked) if blocked else "no lane hits a near tower"])
	var outside_ok := await _check_outside_view()
	outside_ok = await _check_sides() and outside_ok
	outside_ok = _check_side_bounds() and outside_ok
	var reflections_ok := await _check_reflections()
	traffic.set_frozen(true)

	var panes := _main.get_node("Zones/Apartment/Windows/LivingWindow").find_children("Glass*", "MeshInstance3D", true, false)
	var default_pct := await _shimmer()
	print("SHIMMER through_glass: %.2f %%" % default_pct)
	for pane: Node3D in panes:
		pane.visible = false
	print("SHIMMER without_glass: %.2f %%" % await _shimmer())
	for pane: Node3D in panes:
		pane.visible = true
	var env: Environment = _main.get_node("Skyline/WorldEnvironment").environment
	env.glow_enabled = false
	print("SHIMMER without_glow: %.2f %%" % await _shimmer())
	env.glow_enabled = true
	# Rain on the glass, frozen (the sliding itself isn't shimmer): only the view moves.
	var rain: RainOnGlass = _main.get_node("Weather/RainOnGlass")
	rain.set_rain(1.0, true)
	rain.set_process(false)
	await get_tree().create_timer(0.3).timeout
	print("SHIMMER rain_static: %.2f %%" % await _shimmer())
	rain.set_rain(0.0, true)

	traffic.set_frozen(false)

	var ok := default_pct <= MAX_SHIMMER_PCT
	print("TEST %s skyline_shimmer: %.2f %% (max %.1f %%)" % ["PASS" if ok else "FAIL", default_pct, MAX_SHIMMER_PCT])
	get_tree().quit((0 if ok else 1) + (0 if blocked.is_empty() else 1) + (0 if outside_ok else 1)
			+ (0 if reflections_ok else 1))


func _check_outside_view() -> bool:
	var camera: Camera3D = _main.get_node("Player/XRCamera3D")
	var view: OutsideView = _main.get_node("Skyline/OutsideView")
	var wrong: Array[String] = []
	for v: Array in OUTSIDE_VIEWS:
		camera.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(v[1])), v[0])
		# Notifiers report a frame after drawing, and the occluders build a few frames after
		# start; showing the city again must take at most two frames (pop-in).
		var limit := 30 if v[2] else 2
		var frames := 0
		while view.is_outside_hidden() != v[2] and frames < limit:
			await RenderingServer.frame_post_draw
			frames += 1
		if view.is_outside_hidden() != v[2]:
			wrong.append("%s yaw %d: %s" % [v[0], v[1], "hidden" if view.is_outside_hidden() else "drawn"])
	var ok := wrong.is_empty()
	print("TEST %s outside_view: %s" % ["PASS" if ok else "FAIL", ", ".join(wrong) if wrong else "city hidden without a window in view"])
	return ok


## Each side is hidden until a window facing it is on screen, and then drawn
## alone; the apartment's windows draw the north only.
func _check_sides() -> bool:
	var camera: Camera3D = _main.get_node("Player/XRCamera3D")
	var view: OutsideView = _main.get_node("Skyline/OutsideView")
	var wrong: Array[String] = []
	var notifiers: Array[VisibleOnScreenNotifier3D] = []
	for v: Array in SIDE_VIEWS:
		var notifier := VisibleOnScreenNotifier3D.new()
		notifier.aabb = AABB(Vector3(-0.5, -1.0, -1.0), Vector3(1.0, 2.0, 2.0))
		notifier.set_meta(OutsideView.META_FACING, v[1])
		notifier.add_to_group(OutsideView.GROUP)
		_main.add_child(notifier)
		notifier.global_position = v[0]
		notifiers.append(notifier)
	# Added off screen (the camera faces the bathroom wall): nothing drawn.
	var steps: Array[Array] = [[Vector3(0.5, 1.7, 5.0), 0.0, 0]]
	for i in SIDE_VIEWS.size():
		steps.append([SIDE_VIEWS[i][2], SIDE_VIEWS[i][3], OutsideView.facing_sides(SIDE_VIEWS[i][1])])
	steps.append([Vector3(0.0, 1.7, -2.0), 0.0, OutsideView.NORTH])
	for step: Array in steps:
		camera.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(step[1])), step[0])
		var want: int = step[2]
		var frames := 0
		while (view.shown_sides() != want or not _parts_match(view)) and frames < 30:
			await RenderingServer.frame_post_draw
			frames += 1
		if view.shown_sides() != want or not _parts_match(view):
			wrong.append("%s yaw %d: sides %d (want %d)%s" % [step[0], step[1], view.shown_sides(), want,
					"" if _parts_match(view) else ", parts don't match"])
	for notifier in notifiers:
		notifier.queue_free()
	var counts := _side_counts()
	var ok := wrong.is_empty()
	print("TEST %s outside_sides: %s; %s" % ["PASS" if ok else "FAIL",
			", ".join(wrong) if wrong else "each side drawn only while a window facing it is in view", counts])
	return ok


## Every part's visibility follows the sides shown (none hidden by anything else).
func _parts_match(view: OutsideView) -> bool:
	for target: Node3D in view.targets:
		for part: Node in target.get_children():
			var node := part as Node3D
			var sides := int(node.get_meta(OutsideView.META_SIDES,
					OutsideView.sides_of(Vector2(node.global_position.x, node.global_position.z))))
			if node.visible != bool(sides & view.shown_sides()):
				return false
	return true


## Near towers, far tower instances and vehicles per side, for the report.
func _side_counts() -> String:
	var view: OutsideView = _main.get_node("Skyline/OutsideView")
	var out: PackedStringArray = []
	for s in 4:
		var bit := 1 << s
		var near := 0
		var far := 0
		var vehicles := 0
		for tower: Node3D in _main.get_node("Skyline/NearTowers").get_children():
			if OutsideView.sides_of(Vector2(tower.position.x, tower.position.z)) & bit:
				near += 1
		for part: Node in view.targets[1].get_children():
			if part.name.ends_with("Part0") and int(part.get_meta(OutsideView.META_SIDES, 0)) & bit:
				far += (part as MultiMeshInstance3D).multimesh.instance_count
		for part: Node in view.targets[2].get_children():
			if part.name.contains("Bodies") and int(part.get_meta(OutsideView.META_SIDES, 0)) & bit:
				vehicles += (part as MultiMeshInstance3D).multimesh.instance_count
		out.append("%s: %d near, %d far, %d vehicles" % [OutsideView.SIDE_NAMES[s], near, far, vehicles])
	return "; ".join(out)


## Every side's far towers and traffic have bounds outside the building, so
## occlusion can cull them behind its walls (D-048).
func _check_side_bounds() -> bool:
	var wrong: Array[String] = []
	var building := OutsideView.BUILDING.grow(-0.01)  # bounds end on the facade line
	for path: String in ["Skyline/FarTowers", "Skyline/Traffic"]:
		for part: Node in _main.get_node(path).get_children():
			var sides := int(part.get_meta(OutsideView.META_SIDES, OutsideView.ALL_SIDES))
			if sides == OutsideView.ALL_SIDES:
				continue  # drawn whenever a window is in view: its bounds may hold the building
			var box := (part as MultiMeshInstance3D).multimesh.custom_aabb
			if Rect2(box.position.x, box.position.z, box.size.x, box.size.z).intersects(building):
				wrong.append("%s/%s" % [path.get_file(), part.name])
	var ok := wrong.is_empty()
	print("TEST %s outside_side_bounds: %s" % ["PASS" if ok else "FAIL", ", ".join(wrong) if wrong else "every side's bounds end at its facade"])
	return ok


func _check_reflections() -> bool:
	var camera: Camera3D = _main.get_node("Player/XRCamera3D")
	var zone := _main.get_node("Zones/Apartment")
	var wrong: Array[String] = []
	for v: Array in REFLECTION_VIEWS:
		camera.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(v[1])), v[0])
		for i in 6:
			await RenderingServer.frame_post_draw
		var active: Array[String] = []
		for node in zone.find_children("*", "PlanarReflection", true, false):
			if (node as PlanarReflection).is_active():
				active.append(str(zone.get_path_to(node)))
		var required: Array = v[2]
		var missing := required.filter(func(path: String) -> bool: return path not in active)
		if not missing.is_empty() or (required.is_empty() and not active.is_empty()):
			wrong.append("%s yaw %d: live %s" % [v[0], v[1], active])
		# The windows share one wall plane: one renderer for all of them (two scene passes).
		var window_renderers := 0
		for node in zone.get_node("Windows").find_children("*", "PlanarReflection", true, false):
			if (node as PlanarReflection).is_rendering():
				window_renderers += 1
		if window_renderers > 1:
			wrong.append("%s yaw %d: %d window renderers" % [v[0], v[1], window_renderers])
	var ok := wrong.is_empty()
	print("TEST %s live_reflections: %s" % ["PASS" if ok else "FAIL", ", ".join(wrong) if wrong else "what's in view reflects live; the windows share one renderer"])
	return ok


func _shimmer() -> float:
	var camera: Camera3D = _main.get_node("Player/XRCamera3D")
	var viewport := camera.get_viewport()
	var half_px := deg_to_rad(camera.fov / viewport.get_visible_rect().size.x) * 0.5
	var total := 0.0
	for trial in TRIALS:
		var yaw := trial * 0.013
		camera.transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(0.0, 1.7, -2.0))
		var a := await _capture(viewport)
		camera.transform = Transform3D(Basis(Vector3.UP, yaw + half_px), Vector3(0.0, 1.7, -2.0))
		var b := await _capture(viewport)
		total += _changed_pct(a, b)
	return total / TRIALS


func _capture(viewport: Viewport) -> Image:
	for i in 3:
		await RenderingServer.frame_post_draw
	return viewport.get_texture().get_image()


## City only: two regions left and right of the window mullion.
static func _changed_pct(a: Image, b: Image) -> float:
	var w := a.get_width()
	var h := a.get_height()
	var changed := 0
	var n := 0
	for y in range(int(h * 0.35), int(h * 0.7), 2):
		for range_x: Array in [[0.18, 0.42], [0.58, 0.82]]:
			for x in range(int(w * range_x[0]), int(w * range_x[1]), 2):
				n += 1
				if absf(a.get_pixel(x, y).get_luminance() - b.get_pixel(x, y).get_luminance()) > 0.1:
					changed += 1
	return 100.0 * changed / maxi(n, 1)
