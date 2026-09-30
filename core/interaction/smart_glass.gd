class_name SmartGlass
extends Node
## Electrochromic window glass: each press of [member button] steps the tint
## of [member panes] through [member levels] (clear, half, dark, clear, ...)
## with a short fade and a soft tone. The panes use window_glass.gdshader;
## their ShaderMaterials (one per window, shared by its panes) get `tint`.
## Idle while not fading.

signal tint_changed(tint: float)

@export var button: XRToolsInteractableAreaButton
@export var panes: Array[GeometryInstance3D] = []
@export var levels: PackedFloat32Array = [0.0, 0.5, 0.9]
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var fade_time := 1.5
@export var tone: AudioStreamPlayer3D
@export var click: AudioStreamPlayer3D

## Current tint, 0 = clear, 1 = fully tinted.
var tint := 0.0

var _materials: Array[ShaderMaterial] = []
var _level := 0
var _from := 0.0
var _to := 0.0
var _t := 1.0


func _ready() -> void:
	if not button:
		push_error("SmartGlass needs a button: %s" % get_path())
		return
	_collect()
	button.button_pressed.connect(_on_pressed)
	_set_tint(levels[_level] if not levels.is_empty() else 0.0)
	set_process(false)


## Share of the view (and of the city's light) the glass lets through at the
## current tint, relative to clear glass (1 = clear).
func get_transmission() -> float:
	_collect()
	var tint_alpha := 0.96
	var clear_alpha := 0.035
	if not _materials.is_empty():
		var a: Variant = _materials[0].get_shader_parameter("tint_alpha")
		if a != null:
			tint_alpha = a
		var c: Variant = _materials[0].get_shader_parameter("clear_alpha")
		if c != null:
			clear_alpha = c
	var coverage := lerpf(clear_alpha, tint_alpha, tint)
	return (1.0 - coverage) / (1.0 - clear_alpha)


## Sets the tint at once (no fade, no tone); the next press steps on from the nearest level.
func set_tint(value: float) -> void:
	set_process(false)
	var best := 0
	for i in levels.size():
		if absf(levels[i] - value) < absf(levels[best] - value):
			best = i
	_level = best
	_set_tint(clampf(value, 0.0, 1.0))


## Steps to the next tint level.
func cycle() -> void:
	if levels.is_empty():
		return
	_level = (_level + 1) % levels.size()
	_from = tint
	_to = levels[_level]
	_t = 0.0
	set_process(true)
	if tone:
		# A little lower for darker glass.
		tone.pitch_scale = 1.0 - 0.15 * _to
		tone.play()
	if click:
		click.play()


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	cycle()


func _process(delta: float) -> void:
	_t = minf(_t + delta / maxf(fade_time, 0.01), 1.0)
	_set_tint(lerpf(_from, _to, smoothstep(0.0, 1.0, _t)))
	if _t >= 1.0:
		set_process(false)


func _set_tint(value: float) -> void:
	tint = value
	for mat in _materials:
		mat.set_shader_parameter("tint", value)
	tint_changed.emit(value)


func _collect() -> void:
	if not _materials.is_empty():
		return
	for pane in panes:
		var mat := pane.material_override as ShaderMaterial
		if mat and not _materials.has(mat):
			_materials.append(mat)
