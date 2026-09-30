class_name WindowHud
extends Node
## Feeds the glass HUD readout (time HH:MM, temperature, weather glyph) that
## window_glass.gdshader draws on panes with `hud_enabled`. Updates once per
## second from a Timer; no per-frame work.
##
## The state comes from [member source] when set (any object with
## `get_hud_state() -> Dictionary` returning hour, minute, temperature and
## weather, e.g. the M2 WorldState later), else from the system clock with
## the fixed placeholder [member temperature] and [member weather].

enum Weather { CLEAR_NIGHT, CLOUDY, RAIN }

@export var panes: Array[GeometryInstance3D] = []
@export_custom(PROPERTY_HINT_NONE, "suffix:°C") var temperature := 14
@export var weather := Weather.CLOUDY
## Optional state provider (see the class description).
var source: Object

var _materials: Array[ShaderMaterial] = []
var _shown := ""


func _ready() -> void:
	for pane in panes:
		var mat := pane.material_override as ShaderMaterial
		if mat and not _materials.has(mat):
			_materials.append(mat)
	if _materials.is_empty():
		push_warning("WindowHud: no ShaderMaterial on its panes: %s" % get_path())
		return
	var timer := Timer.new()
	timer.wait_time = 1.0
	timer.autostart = true
	timer.timeout.connect(refresh)
	add_child(timer)
	refresh()


## Reads the state and updates the glass if anything changed.
func refresh() -> void:
	var state := _state()
	var hour: int = state.get("hour", 0)
	var minute: int = state.get("minute", 0)
	var temp: int = state.get("temperature", temperature)
	var kind: int = state.get("weather", weather)
	var key := "%d:%d:%d:%d" % [hour, minute, temp, kind]
	if key == _shown:
		return
	_shown = key
	var digits := Vector4i(hour / 10, hour % 10, minute / 10, minute % 10)
	for mat in _materials:
		mat.set_shader_parameter("hud_time", digits)
		mat.set_shader_parameter("hud_temperature", temp)
		mat.set_shader_parameter("hud_weather", kind)


func _state() -> Dictionary:
	if source and source.has_method("get_hud_state"):
		return source.call("get_hud_state")
	var now := Time.get_time_dict_from_system()
	return {"hour": now.hour, "minute": now.minute, "temperature": temperature, "weather": weather}
