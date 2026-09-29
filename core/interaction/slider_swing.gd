class_name SliderSwing
extends Node
## Gives an [XRToolsInteractableSlider] (a drawer) momentum. Let go while
## moving and it slides on, slows down by friction and bumps softly at its
## limits. Near closed, an optional soft-close pulls it shut.
##
## Closed is [member XRToolsInteractableSlider.slider_limit_min]. Units are
## meters along the slider's local X.

@export var slider: XRToolsInteractableSlider
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s²") var friction := 0.9
@export var damping := 2.0
@export_range(0.0, 1.0) var bounce := 0.15
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s") var max_speed := 2.0
## Within this distance of closed it pulls itself shut (0 = off).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var soft_close := 0.03
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s²") var soft_close_pull := 1.5
## Played when it hits a limit (volume by speed).
@export var stop_sound: AudioStreamPlayer3D
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s") var stop_sound_speed := 0.4

const SAMPLE_WINDOW := 0.12

var _velocity := 0.0
var _held := false
var _times: PackedFloat64Array = []
var _positions: PackedFloat32Array = []


func _ready() -> void:
	if not slider:
		push_error("SliderSwing needs a slider: %s" % get_path())
		return
	slider.grabbed.connect(_on_grabbed)
	slider.released.connect(_on_released)
	slider.slider_moved.connect(_on_moved)
	set_process(false)


## Meters per second; positive opens.
func get_velocity() -> float:
	return _velocity


func _on_grabbed(_slider: XRToolsInteractableSlider) -> void:
	_held = true
	_velocity = 0.0
	_times.clear()
	_positions.clear()
	set_process(false)


func _on_released(_slider: XRToolsInteractableSlider) -> void:
	_held = false
	_velocity = clampf(_release_velocity(), -max_speed, max_speed)
	set_process(true)


func _on_moved(pos: float) -> void:
	if not _held:
		return
	var now := Time.get_ticks_usec() / 1e6
	_times.append(now)
	_positions.append(pos)
	while _times.size() > 2 and now - _times[0] > SAMPLE_WINDOW:
		_times.remove_at(0)
		_positions.remove_at(0)


func _release_velocity() -> float:
	var n := _times.size()
	if n < 2:
		return 0.0
	if Time.get_ticks_usec() / 1e6 - _times[n - 1] > SAMPLE_WINDOW:
		return 0.0
	var dt := _times[n - 1] - _times[0]
	return 0.0 if dt < 0.02 else (_positions[n - 1] - _positions[0]) / dt


func _process(delta: float) -> void:
	var closed := slider.slider_limit_min
	var pos := slider.slider_position
	var closing := soft_close > 0.0 and pos - closed < soft_close
	var v := _velocity
	if closing:
		v -= soft_close_pull * delta
	v *= exp(-damping * delta)
	if absf(v) <= friction * delta and not closing:
		v = 0.0
	elif not closing:
		v -= signf(v) * friction * delta
	var target := pos + v * delta
	if target <= closed:
		target = closed
		_bump(v)
		v = 0.0
	elif target >= slider.slider_limit_max:
		target = slider.slider_limit_max
		_bump(v)
		v = -v * bounce
	slider.move_slider(target)
	_velocity = v
	if v == 0.0 and (not closing or is_equal_approx(slider.slider_position, closed)):
		set_process(false)


func _bump(speed: float) -> void:
	if stop_sound and absf(speed) > 0.05:
		stop_sound.volume_db = linear_to_db(clampf(absf(speed) / stop_sound_speed, 0.1, 1.0))
		stop_sound.play()
