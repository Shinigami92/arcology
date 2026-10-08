class_name HingeSwing
extends Node
## Gives an [XRToolsInteractableHinge] momentum. Released while moving, it
## keeps swinging, slows down by friction and bounces off its open limit.
## Near closed, an optional latch (a fridge's magnetic seal, a door's catch)
## pulls it shut.
##
## Closed is [member XRToolsInteractableHinge.hinge_limit_min]. Plays
## [member open_sound] when the hinge leaves closed (the seal letting go);
## the bump at the limits is [HingeStopSound]'s job.

@export var hinge: XRToolsInteractableHinge
## Constant deceleration while swinging (hinge and seal friction).
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s²") var friction := 120.0
## Speed-proportional slowdown (air, damper), per second.
@export var damping := 1.5
## Share of the speed kept when bouncing off the open limit.
@export_range(0.0, 1.0) var bounce := 0.3
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s") var max_speed := 600.0
## Within this angle of closed the latch pulls the hinge shut (0 = no latch).
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var latch_angle := 15.0
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s²") var latch_pull := 360.0
@export var open_sound: AudioStreamPlayer3D

## How far back the hand's motion is averaged for the release speed.
const SAMPLE_WINDOW := 0.12

var _velocity := 0.0
var _held := false
var _was_closed := true
var _sample_times: PackedFloat64Array = []
var _sample_angles: PackedFloat32Array = []


func _ready() -> void:
	if not hinge:
		push_error("HingeSwing needs a hinge: %s" % get_path())
		return
	_was_closed = _is_closed(hinge.hinge_position)
	hinge.grabbed.connect(_on_grabbed)
	hinge.released.connect(_on_released)
	hinge.hinge_moved.connect(_on_hinge_moved)
	set_process(false)


## Degrees per second; positive opens.
func get_velocity() -> float:
	return _velocity


## Lets it swing on at `velocity` (°/s, positive opens), e.g. after a shove
## by a bare hand ([HingeHandPush]). Ignored while held.
func coast(velocity: float) -> void:
	if _held:
		return
	_velocity = clampf(velocity, -max_speed, max_speed)
	set_process(true)


func _on_grabbed(_hinge: XRToolsInteractableHinge) -> void:
	_held = true
	_velocity = 0.0
	_sample_times.clear()
	_sample_angles.clear()
	set_process(false)


func _on_released(_hinge: XRToolsInteractableHinge) -> void:
	_held = false
	_velocity = clampf(_release_velocity(), -max_speed, max_speed)
	set_process(true)


func _on_hinge_moved(angle: float) -> void:
	var closed := _is_closed(angle)
	if _was_closed and not closed and open_sound:
		open_sound.play()
	_was_closed = closed
	if not _held:
		return
	var now := Time.get_ticks_usec() / 1e6
	_sample_times.append(now)
	_sample_angles.append(angle)
	while _sample_times.size() > 2 and now - _sample_times[0] > SAMPLE_WINDOW:
		_sample_times.remove_at(0)
		_sample_angles.remove_at(0)


func _release_velocity() -> float:
	var n := _sample_times.size()
	if n < 2:
		return 0.0
	var now := Time.get_ticks_usec() / 1e6
	# The hand stopped before letting go.
	if now - _sample_times[n - 1] > SAMPLE_WINDOW:
		return 0.0
	var dt := _sample_times[n - 1] - _sample_times[0]
	if dt < 0.02:
		return 0.0
	return (_sample_angles[n - 1] - _sample_angles[0]) / dt


func _process(delta: float) -> void:
	var closed := hinge.hinge_limit_min
	var angle := hinge.hinge_position
	var latching := latch_angle > 0.0 and angle - closed < latch_angle
	var v := _velocity
	if latching:
		v -= latch_pull * delta
	v *= exp(-damping * delta)
	if absf(v) <= friction * delta and not latching:
		v = 0.0
	elif not latching:
		v -= signf(v) * friction * delta

	var target := angle + v * delta
	if target <= closed:
		target = closed
		v = 0.0
	elif target >= hinge.hinge_limit_max:
		target = hinge.hinge_limit_max
		v = -v * bounce
	hinge.move_hinge(deg_to_rad(target))
	# Held back (the body blocker stops the leaf at the player).
	if not is_equal_approx(hinge.hinge_position, target):
		v = 0.0
	_velocity = v

	var at_rest := v == 0.0 and (not latching or _is_closed(hinge.hinge_position))
	if at_rest:
		set_process(false)


func _is_closed(angle: float) -> bool:
	return absf(angle - hinge.hinge_limit_min) < 0.5
