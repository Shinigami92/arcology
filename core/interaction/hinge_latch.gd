class_name HingeLatch
extends Node
## Pulls an [XRToolsInteractableHinge] shut when it's released close to its
## closed limit, like a fridge's magnetic seal or a latching cabinet door.
##
## Plays [member open_sound] when the hinge leaves the closed position (the
## seal letting go). The closing bump is [HingeStopSound]'s job.

@export var hinge: XRToolsInteractableHinge
## Released within this angle of closed, the hinge swings shut by itself.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var snap_angle := 15.0
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s") var close_speed := 200.0
## Closed is [member XRToolsInteractableHinge.hinge_limit_min] unless set.
@export var closed_is_max := false
@export var open_sound: AudioStreamPlayer3D

var _closed := 0.0
var _was_closed := true


func _ready() -> void:
	if not hinge:
		push_error("HingeLatch needs a hinge: %s" % get_path())
		return
	_closed = hinge.hinge_limit_max if closed_is_max else hinge.hinge_limit_min
	_was_closed = _is_closed(hinge.hinge_position)
	hinge.released.connect(_on_released)
	hinge.grabbed.connect(_on_grabbed)
	hinge.hinge_moved.connect(_on_hinge_moved)
	set_process(false)


func _on_released(_hinge: XRToolsInteractableHinge) -> void:
	if absf(hinge.hinge_position - _closed) <= snap_angle:
		set_process(true)


func _on_grabbed(_hinge: XRToolsInteractableHinge) -> void:
	set_process(false)


func _on_hinge_moved(angle: float) -> void:
	var closed := _is_closed(angle)
	if _was_closed and not closed and open_sound:
		open_sound.play()
	_was_closed = closed


func _process(delta: float) -> void:
	var angle := move_toward(hinge.hinge_position, _closed, close_speed * delta)
	hinge.move_hinge(deg_to_rad(angle))
	# The body blocker may hold the hinge back; give up rather than push.
	if is_equal_approx(hinge.hinge_position, _closed) or not is_equal_approx(hinge.hinge_position, angle):
		set_process(false)


func _is_closed(angle: float) -> bool:
	return absf(angle - _closed) < 0.5
