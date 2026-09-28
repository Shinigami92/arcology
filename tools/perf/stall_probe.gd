extends Node3D
## Measures frame hitches of an almost empty scene, to tell machine-level
## stalls (GPU monitoring tools, drivers, overlays) from content hitches.
## If this hitches, the perf flythrough will too, whatever the zone does.
##
##   "$GODOT4_EDITOR" --path . --xr-mode off res://tools/perf/stall_probe.tscn
##
## Prints every interval over 16.7 ms and a summary, then quits with the
## hitch count.

@export var duration := 25.0
@export var warmup := 1.0

var _last_usec := 0
var _elapsed := 0.0
var _frames := 0
var _hitches: Array[String] = []


func _ready() -> void:
	_last_usec = Time.get_ticks_usec()


func _process(delta: float) -> void:
	var now := Time.get_ticks_usec()
	var ms := (now - _last_usec) / 1000.0
	_last_usec = now
	_elapsed += delta
	if _elapsed < warmup:
		return
	_frames += 1
	if ms > 16.7:
		_hitches.append("%.2fs %.1fms" % [_elapsed, ms])
	if _elapsed >= duration + warmup:
		set_process(false)
		print("STALL PROBE: %d frames in %.0f s, %d hitches over 16.7 ms: %s" % [
				_frames, duration, _hitches.size(), ", ".join(_hitches)])
		get_tree().quit(_hitches.size())
