class_name PerfFlythrough
extends Node
## Scripted camera flythrough that logs frame times and fails on budget
## regressions. See CLAUDE.md "Performance test" for how to run it.
##
## Moves the view along the zone's PerfPath (Marker3D children, visited in
## order; each marker's -Z is the view direction), skips a warmup, samples
## every frame, compares against tools/perf/budgets.json, writes a JSON
## report to tools/perf/results/ and quits with exit code 0 (pass) or 1 (fail).
##
## XR mode (headset on, SteamVR running): moves the XR origin; the frame is
## real stereo. Desktop mode (--xr-mode off): renders a SubViewport at
## [constant DESKTOP_SIZE] (both eyes side by side) with a normal camera; an
## approximation for catching regressions without a headset.

const BUDGETS_PATH := "res://tools/perf/budgets.json"
const RESULTS_DIR := "res://tools/perf/results"
## Two eyes side by side at the per-eye render target SteamVR requested for
## the Steam Frame at 100% resolution (2644x2644, measured 2026-09-27).
const DESKTOP_SIZE := Vector2i(5288, 2644)

var zone_name := ""
var zone: Node3D
var player: XROrigin3D
## Foveated rendering: the desktop SubViewport gets the headset's shading rate map.
var foveation: Foveation
var duration := 20.0
var warmup := 3.0
## Zone-relative node paths to hide for A/B cost comparisons (--perf-hide).
var hide_nodes: PackedStringArray = []

var _markers: Array[Marker3D] = []
var _mover: Node3D
var _viewport_rid: RID
var _xr := false
var _elapsed := 0.0
var _last_usec := 0
var _frame_ms: PackedFloat32Array = []
var _gpu_ms: PackedFloat32Array = []
var _cpu_ms: PackedFloat32Array = []
var _render_cpu_ms: PackedFloat32Array = []
var _process_ms: PackedFloat32Array = []
var _physics_ms: PackedFloat32Array = []
var _draw_calls: PackedInt32Array = []
var _primitives: PackedInt32Array = []
var _objects: PackedInt32Array = []
var _reflection_gpu_ms: PackedFloat32Array = []
# Where each sampled frame was: seconds since start, nearest PerfPath marker.
var _frame_time: PackedFloat32Array = []
var _frame_marker: PackedInt32Array = []
# Pipeline compilations per frame (draw-time and specialization; the
# monitors are totals since startup). A hitch with compiles is a shader stall.
var _frame_compiles: PackedInt32Array = []
var _last_compiles := 0
var _frame_start := _FrameStart.new()
# Other viewports that render 3D (live reflections, D-049): their GPU/CPU time counts too.
var _extra_viewports: Array[SubViewport] = []


## Runs first in every idle frame so the flythrough (which runs last) can
## time the whole process pass. Performance.TIME_PROCESS isn't usable per
## frame for this.
class _FrameStart extends Node:
	var usec := 0

	func _process(_delta: float) -> void:
		usec = Time.get_ticks_usec()


func _ready() -> void:
	process_priority = 1 << 30
	_frame_start.process_priority = -(1 << 30)
	add_child(_frame_start)
	var path_root := zone.get_node_or_null("PerfPath")
	if path_root:
		for child in path_root.get_children():
			if child is Marker3D:
				_markers.append(child)
	if _markers.size() < 2:
		push_error("PERF: zone '%s' needs a PerfPath node with at least 2 Marker3D children" % zone_name)
		get_tree().quit(2)
		return

	for path in hide_nodes:
		var hidden := zone.get_node_or_null(path) as Node3D
		if hidden:
			hidden.visible = false
		else:
			push_warning("PERF: --perf-hide node not found: " + path)

	_xr = get_viewport().use_xr
	if _xr:
		_mover = player
		_viewport_rid = get_viewport().get_viewport_rid()
	else:
		var sub := SubViewport.new()
		sub.size = DESKTOP_SIZE
		sub.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		sub.msaa_3d = get_viewport().msaa_3d
		sub.use_occlusion_culling = get_viewport().use_occlusion_culling
		if foveation and foveation.enabled:
			sub.vrs_mode = Viewport.VRS_TEXTURE
			sub.vrs_texture = foveation.desktop_texture(Vector2i(DESKTOP_SIZE.x / 2, DESKTOP_SIZE.y), 2)
		sub.world_3d = get_viewport().world_3d
		var cam := Camera3D.new()
		cam.fov = 100.0
		cam.near = 0.03
		cam.far = 3000.0
		sub.add_child(cam)
		add_child(sub)
		cam.current = true
		# Only the SubViewport should cost GPU time.
		get_viewport().disable_3d = true
		_mover = cam
		# Live reflections follow this camera and render both eyes, as in the headset.
		PlanarReflection.view_camera = cam
		PlanarReflection.simulate_stereo = true
		_viewport_rid = sub.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(_viewport_rid, true)
	# Disable player movement so the physics body doesn't fight the path.
	if player:
		var body := player.get_node_or_null("PlayerBody")
		if body:
			body.set("enabled", false)
	print("PERF: zone=%s mode=%s duration=%.0fs warmup=%.0fs markers=%d hidden=%s foveation=%s" % [
			zone_name, "xr" if _xr else "desktop-approx", duration, warmup, _markers.size(), hide_nodes, _foveation_label()])
	_last_usec = Time.get_ticks_usec()
	_last_compiles = _pipeline_compiles()


func _process(delta: float) -> void:
	var now := Time.get_ticks_usec()
	var frame := (now - _last_usec) / 1000.0
	_last_usec = now
	_elapsed += delta

	var t := clampf(_elapsed / (duration + warmup), 0.0, 1.0)
	_mover.global_transform = _sample_path(t)

	if _elapsed > warmup:
		_frame_ms.append(frame)
		_frame_time.append(_elapsed)
		_frame_marker.append(roundi(t * (_markers.size() - 1)))
		var compiles := _pipeline_compiles()
		_frame_compiles.append(compiles - _last_compiles)
		_last_compiles = compiles
		var gpu := RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)
		# Physics monitor is in seconds; render time is in ms.
		var render_cpu := RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid)
		var reflections := 0.0
		for vp in PlanarReflection.rendering_viewports():
			var rid := vp.get_viewport_rid()
			if vp not in _extra_viewports:
				# Created on first use; measured from the next frame on.
				_extra_viewports.append(vp)
				RenderingServer.viewport_set_measure_render_time(rid, true)
				continue
			reflections += RenderingServer.viewport_get_measured_render_time_gpu(rid)
			render_cpu += RenderingServer.viewport_get_measured_render_time_cpu(rid)
		gpu += reflections
		_gpu_ms.append(gpu)
		_reflection_gpu_ms.append(reflections)
		var process := (Time.get_ticks_usec() - _frame_start.usec) / 1000.0
		var physics := Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
		_render_cpu_ms.append(render_cpu)
		_process_ms.append(process)
		_physics_ms.append(physics)
		_cpu_ms.append(render_cpu + process + physics)
		_draw_calls.append(int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
		_primitives.append(int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)))
		_objects.append(int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)))

	if _elapsed >= duration + warmup:
		set_process(false)
		_finish()


func _sample_path(t: float) -> Transform3D:
	var segments := _markers.size() - 1
	var f := t * segments
	var i := mini(int(f), segments - 1)
	var local := f - i
	var p0 := _markers[maxi(i - 1, 0)].global_position
	var p1 := _markers[i].global_position
	var p2 := _markers[i + 1].global_position
	var p3 := _markers[mini(i + 2, segments)].global_position
	var pos := p1.cubic_interpolate(p2, p0, p3, local)
	var q1 := _markers[i].global_basis.get_rotation_quaternion()
	var q2 := _markers[i + 1].global_basis.get_rotation_quaternion()
	var rot := Basis(q1.slerp(q2, smoothstep(0.0, 1.0, local)))
	if _xr:
		# The XR origin sits on the floor; markers are at eye height.
		pos.y -= 1.7
	return Transform3D(rot, pos)


func _finish() -> void:
	var budgets: Dictionary = {}
	var file := FileAccess.open(BUDGETS_PATH, FileAccess.READ)
	if file:
		budgets = JSON.parse_string(file.get_as_text())
	var frame_budget: float = budgets.get("frame_budget_ms", 11.11)
	var zone_budget: Dictionary = budgets.get("zones", {}).get(zone_name, {})

	# In XR the runtime paces frames to the display, so intervals jitter
	# around the budget (11.1 ms +/- a little) and "over budget" counts
	# normal frames. A dropped frame is a missed refresh: > 1.5x the budget.
	var over := 0
	var dropped := 0
	var dropped_at: Array[Dictionary] = []
	var compiles_at: Array[Dictionary] = []
	for i in _frame_ms.size():
		if _frame_compiles[i] > 0:
			compiles_at.append({"t": snappedf(_frame_time[i], 0.01), "n": _frame_compiles[i], "ms": snappedf(_frame_ms[i], 0.1)})
		var ms := _frame_ms[i]
		if ms > frame_budget:
			over += 1
		if ms > frame_budget * 1.5:
			dropped += 1
			dropped_at.append({
				"t": snappedf(_frame_time[i], 0.01),
				"ms": snappedf(ms, 0.1),
				"marker": _markers[_frame_marker[i]].name,
				"gpu_ms": snappedf(_gpu_ms[i], 0.1),
				"cpu_ms": snappedf(_cpu_ms[i], 0.1),
				"pipeline_compiles": _frame_compiles[i],
			})
	var stats := {
		"zone": zone_name,
		"mode": "xr" if _xr else "desktop-approx",
		"hidden": hide_nodes,
		"foveation": _foveation_label(),
		"date": Time.get_datetime_string_from_system(),
		"gpu": RenderingServer.get_video_adapter_name(),
		"frames": _frame_ms.size(),
		"frame_ms_avg": _avg(_frame_ms),
		"frame_ms_p95": _pct(_frame_ms, 0.95),
		"frame_ms_p99": _pct(_frame_ms, 0.99),
		"frame_ms_max": _pct(_frame_ms, 1.0),
		"frames_over_budget_pct": 100.0 * over / maxf(_frame_ms.size(), 1.0),
		"frames_dropped": dropped,
		"frames_dropped_pct": 100.0 * dropped / maxf(_frame_ms.size(), 1.0),
		# Hitches: time since start and the nearest PerfPath marker.
		"frames_dropped_at": dropped_at,
		"pipeline_compiles": _sum_i(_frame_compiles),
		"pipeline_compiles_at": compiles_at,
		"gpu_ms_avg": _avg(_gpu_ms),
		"gpu_ms_p95": _pct(_gpu_ms, 0.95),
		# Live reflections' share of gpu_ms (D-049).
		"reflection_gpu_ms_avg": _avg(_reflection_gpu_ms),
		"reflection_gpu_ms_p95": _pct(_reflection_gpu_ms, 0.95),
		"cpu_ms_p95": _pct(_cpu_ms, 0.95),
		"render_cpu_ms_p95": _pct(_render_cpu_ms, 0.95),
		"process_ms_p95": _pct(_process_ms, 0.95),
		"physics_ms_p95": _pct(_physics_ms, 0.95),
		"draw_calls_max": _max_i(_draw_calls),
		"primitives_max": _max_i(_primitives),
		"objects_max": _max_i(_objects),
		# What each stretch of the path costs (frames grouped by nearest marker):
		# shows what culling saves where, e.g. the city from the hallway.
		"per_marker": _per_marker(),
	}

	var failures: Array[String] = []
	for key: String in zone_budget:
		if not stats.has(key):
			continue
		# In desktop mode the frame pacing isn't the headset's, so only
		# GPU/CPU cost and scene counts are checked.
		if not _xr and key.begins_with("frame"):
			continue
		if float(stats[key]) > float(zone_budget[key]):
			failures.append("%s %.2f > %.2f" % [key, float(stats[key]), float(zone_budget[key])])
	stats["budget"] = zone_budget
	stats["failures"] = failures
	stats["pass"] = failures.is_empty()

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(RESULTS_DIR))
	var stamp := Time.get_datetime_string_from_system().replace(":", "-")
	var out_path := "%s/%s-%s-%s.json" % [RESULTS_DIR, zone_name, stats.mode, stamp]
	var out := FileAccess.open(out_path, FileAccess.WRITE)
	if out:
		out.store_string(JSON.stringify(stats, "  "))

	print("PERF: ", JSON.stringify(stats))
	print("PERF: %s (%s) report=%s" % ["PASS" if failures.is_empty() else "FAIL", ", ".join(failures), out_path])
	get_tree().quit(0 if failures.is_empty() else 1)


func _per_marker() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for m in _markers.size():
		var gpu: PackedFloat32Array = []
		var refl: PackedFloat32Array = []
		var draws: PackedInt32Array = []
		var prims: PackedInt32Array = []
		var objects: PackedInt32Array = []
		for i in _frame_marker.size():
			if _frame_marker[i] == m:
				gpu.append(_gpu_ms[i])
				refl.append(_reflection_gpu_ms[i])
				draws.append(_draw_calls[i])
				prims.append(_primitives[i])
				objects.append(_objects[i])
		if gpu.is_empty():
			continue
		out.append({
			"marker": _markers[m].name,
			"frames": gpu.size(),
			"gpu_ms_avg": snappedf(_avg(gpu), 0.01),
			"reflection_gpu_ms_avg": snappedf(_avg(refl), 0.01),
			"draw_calls_max": _max_i(draws),
			"primitives_max": _max_i(prims),
			"objects_max": _max_i(objects),
		})
	return out


func _foveation_label() -> String:
	if not foveation or not foveation.enabled:
		return "off"
	return "%.0f,%.1f" % [foveation.min_radius, foveation.strength]


static func _avg(values: PackedFloat32Array) -> float:
	if values.is_empty():
		return 0.0
	var sum := 0.0
	for v in values:
		sum += v
	return sum / values.size()


static func _pct(values: PackedFloat32Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted := values.duplicate()
	sorted.sort()
	return sorted[clampi(int(ceil(p * sorted.size())) - 1, 0, sorted.size() - 1)]


static func _pipeline_compiles() -> int:
	return int(Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_DRAW)
			+ Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_SPECIALIZATION))


static func _sum_i(values: PackedInt32Array) -> int:
	var s := 0
	for v in values:
		s += v
	return s


static func _max_i(values: PackedInt32Array) -> int:
	var m := 0
	for v in values:
		m = maxi(m, v)
	return m
