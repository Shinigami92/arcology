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
var _frame_start := _FrameStart.new()


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
		_viewport_rid = sub.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(_viewport_rid, true)
	# Disable player movement so the physics body doesn't fight the path.
	if player:
		var body := player.get_node_or_null("PlayerBody")
		if body:
			body.set("enabled", false)
	print("PERF: zone=%s mode=%s duration=%.0fs warmup=%.0fs markers=%d hidden=%s" % [
			zone_name, "xr" if _xr else "desktop-approx", duration, warmup, _markers.size(), hide_nodes])
	_last_usec = Time.get_ticks_usec()


func _process(delta: float) -> void:
	var now := Time.get_ticks_usec()
	var frame := (now - _last_usec) / 1000.0
	_last_usec = now
	_elapsed += delta

	var t := clampf(_elapsed / (duration + warmup), 0.0, 1.0)
	_mover.global_transform = _sample_path(t)

	if _elapsed > warmup:
		_frame_ms.append(frame)
		_gpu_ms.append(RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid))
		# Physics monitor is in seconds; render time is in ms.
		var render_cpu := RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid)
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

	var over := 0
	for ms in _frame_ms:
		if ms > frame_budget:
			over += 1
	var stats := {
		"zone": zone_name,
		"mode": "xr" if _xr else "desktop-approx",
		"hidden": hide_nodes,
		"date": Time.get_datetime_string_from_system(),
		"gpu": RenderingServer.get_video_adapter_name(),
		"frames": _frame_ms.size(),
		"frame_ms_avg": _avg(_frame_ms),
		"frame_ms_p95": _pct(_frame_ms, 0.95),
		"frame_ms_p99": _pct(_frame_ms, 0.99),
		"frame_ms_max": _pct(_frame_ms, 1.0),
		"frames_over_budget_pct": 100.0 * over / maxf(_frame_ms.size(), 1.0),
		"gpu_ms_avg": _avg(_gpu_ms),
		"gpu_ms_p95": _pct(_gpu_ms, 0.95),
		"cpu_ms_p95": _pct(_cpu_ms, 0.95),
		"render_cpu_ms_p95": _pct(_render_cpu_ms, 0.95),
		"process_ms_p95": _pct(_process_ms, 0.95),
		"physics_ms_p95": _pct(_physics_ms, 0.95),
		"draw_calls_max": _max_i(_draw_calls),
		"primitives_max": _max_i(_primitives),
		"objects_max": _max_i(_objects),
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


static func _max_i(values: PackedInt32Array) -> int:
	var m := 0
	for v in values:
		m = maxi(m, v)
	return m
