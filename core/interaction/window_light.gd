class_name WindowLight
extends Node
## Dims a room's city spill light (the big soft light outside its window,
## style guide "Lighting") by what the window lets through: the
## [SmartGlass] tint and how far the [MotorizedShade] is down. The spill
## light's energy and color in the scene are the clear, open window at night;
## by day [DayNight] brightens it and blends it toward daylight. Event driven:
## it only updates when the glass, the shade or the daylight reports a change.

@export var light: Light3D
@export var glass: SmartGlass
@export var shade: MotorizedShade
## Share of the light that still gets past a closed (opaque) shade: gaps at
## the edges, light through the fabric.
@export_range(0.0, 1.0) var shade_leak := 0.06

var _base_energy := 0.0
var _night_color := Color.WHITE
var _day_night: DayNight


func _ready() -> void:
	if not light:
		push_error("WindowLight needs a light: %s" % get_path())
		return
	_base_energy = light.light_energy
	_night_color = light.light_color
	_day_night = DayNight.find(get_tree())
	if _day_night:
		_day_night.changed.connect(_update)
	if glass:
		glass.tint_changed.connect(_on_changed)
	if shade:
		shade.moved.connect(_on_changed)
	_update()


## The light's energy with nothing in the way, at night.
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
	if _day_night:
		factor *= _day_night.window_scale
		light.light_color = _night_color.lerp(_day_night.window_color, _day_night.window_mix)
	light.light_energy = _base_energy * factor
