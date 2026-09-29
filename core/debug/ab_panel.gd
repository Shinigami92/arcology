class_name ABPanel
extends Node3D
## Wall panel with a push button that flips every ABSwitch between its A and
## B variant, and a label showing which one is shown.

@export var button: XRToolsInteractableAreaButton
@export var label: Label3D
@export var click: AudioStreamPlayer3D


func _ready() -> void:
	button.button_pressed.connect(_on_pressed)
	_show.call_deferred("A")


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	_show(ABSwitch.toggle_all(get_tree()))
	if click:
		click.play()


func _show(variant: String) -> void:
	label.text = "A / B\n%s" % variant
