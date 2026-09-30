class_name RainDebugButton
extends Node3D
## Temporary debug control for rain on the glass (D-034) until the M2 weather
## system exists: each fingertip press of [member button] steps the rain
## through [member levels] (0 -> 0.4 -> 1 -> 0) on the scene's [RainOnGlass].

@export var button: XRToolsInteractableAreaButton
@export var levels: PackedFloat32Array = [0.0, 0.4, 1.0]
@export var click: AudioStreamPlayer3D


func _ready() -> void:
	if not button:
		push_error("RainDebugButton needs a button: %s" % get_path())
		return
	button.button_pressed.connect(_on_pressed)


## Steps to the level after the current rain target.
func cycle() -> void:
	var rain := get_tree().get_first_node_in_group(RainOnGlass.GROUP) as RainOnGlass
	if not rain or levels.is_empty():
		push_warning("RainDebugButton: no RainOnGlass in the scene")
		return
	var next := 0
	for i in levels.size():
		if is_equal_approx(levels[i], rain.target):
			next = (i + 1) % levels.size()
			break
	rain.set_rain(levels[next])
	if click:
		click.play()


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	cycle()
