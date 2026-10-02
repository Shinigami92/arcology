class_name LightSwitch
extends Node
## A physical switch: each press of [member button] (an XR Tools area button,
## pressed by a fingertip or hand) toggles [member lights] and the emissive
## material [member material_name] under [member emissive_root].
## Use it for lamps, room light switches, appliance buttons.

@export var button: XRToolsInteractableAreaButton
@export var lights: Array[Light3D] = []
@export var emissive_root: Node
@export var material_name := ""
## Emission energy when on; < 0 keeps the imported energy.
@export var emission_energy := -1.0
@export var on := true
@export var click: AudioStreamPlayer3D
## Optional indicator (a touch sensor's ring) under [member emissive_root]:
## bright while on, dim while off, so it can be found in the dark.
@export var indicator_material := ""
## Indicator energy when on; < 0 keeps the imported energy.
@export var indicator_energy_on := -1.0
@export var indicator_energy_off := 0.3

var _materials: EmissiveMaterials
var _indicator: EmissiveMaterials


func _ready() -> void:
	if not button:
		push_error("LightSwitch needs a button: %s" % get_path())
		return
	_materials = EmissiveMaterials.new(emissive_root, material_name, emission_energy)
	if emissive_root and material_name and _materials.is_empty():
		push_warning("LightSwitch: no material named '%s' under %s" % [material_name, emissive_root.get_path()])
	if emissive_root and indicator_material:
		_indicator = EmissiveMaterials.new(emissive_root, indicator_material, indicator_energy_on, indicator_energy_off)
		if _indicator.is_empty():
			push_warning("LightSwitch: no indicator material '%s' under %s" % [indicator_material, emissive_root.get_path()])
	button.button_pressed.connect(_on_pressed)
	_apply()


func toggle() -> void:
	on = not on
	_apply()
	if click:
		click.play()


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	toggle()


func _apply() -> void:
	for light in lights:
		light.visible = on
	_materials.set_on(on)
	if _indicator:
		_indicator.set_on(on)
