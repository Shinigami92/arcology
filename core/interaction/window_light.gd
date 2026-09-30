class_name WindowLight
extends Node
## Dims a room's city spill light (the big soft light outside its window,
## style guide "Lighting") by what the window lets through: the
## [SmartGlass] tint and how far the [MotorizedShade] is down. The spill
## light's energy in the scene is the clear, open window. Event driven: it
## only updates when the glass or the shade reports a change.

@export var light: Light3D
@export var glass: SmartGlass
@export var shade: MotorizedShade
## Share of the light that still gets past a closed (opaque) shade: gaps at
## the edges, light through the fabric.
@export_range(0.0, 1.0) var shade_leak := 0.06

var _base_energy := 0.0


func _ready() -> void:
	if not light:
		push_error("WindowLight needs a light: %s" % get_path())
		return
	_base_energy = light.light_energy
	if glass:
		glass.tint_changed.connect(_on_changed)
	if shade:
		shade.moved.connect(_on_changed)
	_update()


## The light's energy with nothing in the way.
func get_base_energy() -> float:
	return _base_energy


func _on_changed(_value: float) -> void:
	_update()


func _update() -> void:
	var factor := 1.0
	if glass:
		factor *= glass.get_transmission()
	if shade:
		factor *= lerpf(1.0, shade_leak, shade.get_closure())
	light.light_energy = _base_energy * factor
