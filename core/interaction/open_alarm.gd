class_name OpenAlarm
extends Node
## Beeps when an [XRToolsInteractableHinge] (a fridge door) is left open:
## after [member delay] seconds open, [member alarm] plays (looped) until
## the hinge is closed again. Closing resets the timer.

@export var hinge: XRToolsInteractableHinge
@export var alarm: AudioStreamPlayer3D
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var delay := 30.0
## Open wider than this counts as open.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var open_angle := 3.0

var _open_time := 0.0


func _ready() -> void:
	if not hinge or not alarm:
		push_error("OpenAlarm needs a hinge and an alarm: %s" % get_path())
		return
	hinge.hinge_moved.connect(_on_hinge_moved)
	set_process(false)


func is_ringing() -> bool:
	return alarm.playing


func _on_hinge_moved(angle: float) -> void:
	var open := absf(angle - hinge.hinge_limit_min) > open_angle
	if open and not is_processing() and not alarm.playing:
		_open_time = 0.0
		set_process(true)
	elif not open:
		set_process(false)
		alarm.stop()


func _process(delta: float) -> void:
	_open_time += delta
	if _open_time >= delay:
		set_process(false)
		alarm.play()
