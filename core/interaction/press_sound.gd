class_name PressSound
extends AudioStreamPlayer3D
## Plays [member stream] when [member button] (an XR Tools area button,
## pressed by a fingertip) is pressed: a flush, a beep, a chime.
##
## While it, or any player in [member exclusive_with], is still playing,
## presses are ignored (a dual-flush cistern runs one flush at a time).

@export var button: XRToolsInteractableAreaButton
@export var exclusive_with: Array[AudioStreamPlayer3D] = []
@export_range(0.0, 0.3, 0.01) var pitch_jitter := 0.03


func _ready() -> void:
	if not button:
		push_error("PressSound needs a button: %s" % get_path())
		return
	button.button_pressed.connect(_on_pressed)


## Whether this or an exclusive player is playing.
func is_busy() -> bool:
	if playing:
		return true
	for other in exclusive_with:
		if other and other.playing:
			return true
	return false


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	if is_busy():
		return
	pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	play()
