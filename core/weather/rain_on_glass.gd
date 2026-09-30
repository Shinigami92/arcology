class_name RainOnGlass
extends Node
## Rain on the window glass (D-034). Smooths how hard it rains, how wet the
## glass is and how many drops still slide, and feeds that to:
## - every window pane's material (window_glass.gdshader; panes in the
##   "window_glass" group): rain_amount, rain_wet, rain_time, rain_slide_time;
## - the patter on each window ("rain_patter" group: AudioStreamPlayer3D,
##   authored volume = full rain);
## - the outside rain at open vents ("rain_ambience" group: HingeAmbience,
##   gain = rain).
##
## Entry point: [method set_rain]. The M2 weather system calls it later; for
## now the living room's debug button and `--rain=<0..1>` do.
##
## After the rain stops, the runners stop within [member slide_stop_time],
## then the beads evaporate over [member dry_time]. Fully dry, every uniform is
## 0, the panes go back to the dry shader (no rain code, no screen read: the
## wet one makes Godot copy the screen every frame) and this node stops
## processing. Both shaders are preloaded, so switching doesn't load or parse.

signal rain_changed(amount: float)

const GROUP := "rain_on_glass"
const GROUP_GLASS := "window_glass"
const GROUP_PATTER := "rain_patter"
const GROUP_AMBIENCE := "rain_ambience"
const DRY_SHADER := preload("res://assets/shaders/window_glass.gdshader")
const WET_SHADER := preload("res://assets/shaders/window_glass_wet.gdshader")
const PRIME_FRAMES := 3

## Seconds the rain takes to set in or ease off (time constant).
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var ease_time := 3.0
## Seconds until the glass is about fully wet.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var wet_time := 12.0
## Seconds the beads take to dry off completely once the rain has stopped.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var dry_time := 45.0
## Seconds the sliding drops take to come to a stop once the rain eases off.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var slide_stop_time := 4.0
## Speeds all of the above up (tests).
@export var time_scale := 1.0

## The rain asked for (0..1).
var target := 0.0
## How hard it rains now (smoothed).
var amount := 0.0
## How wet the glass is (bead coverage).
var wetness := 0.0
## Share of runners still sliding.
var slide := 0.0
var rain_time := 0.0
var slide_time := 0.0

var _materials: Array[ShaderMaterial] = []
var _patter: Array[AudioStreamPlayer3D] = []
var _patter_db: PackedFloat32Array = []
var _ambience: Array[HingeAmbience] = []
var _wet_shader := false


func _ready() -> void:
	add_to_group(GROUP)
	refresh_targets()
	set_process(false)
	_prime()


## Draws the wet variant for a few frames at startup, so its pipelines and the
## screen copy's buffers exist before the first rain (the first switch stalled
## the main thread for about 45 ms otherwise, measured with --rain-delay).
func _prime() -> void:
	if _materials.is_empty() or _wet_shader:
		return
	_set_wet_shader(true)
	for i in PRIME_FRAMES:
		await RenderingServer.frame_post_draw
	_apply()


## Sets how hard it rains, 0..1. immediate: jump there (tests, shots, perf),
## glass wet or dry at once.
func set_rain(value: float, immediate := false) -> void:
	target = clampf(value, 0.0, 1.0)
	if immediate:
		amount = target
		wetness = _wet_target() if target > 0.0 else 0.0
		slide = amount
	rain_changed.emit(target)
	_apply()
	set_process(true)


## Finds the panes, patter players and vent ambiences again (after a zone loads).
func refresh_targets() -> void:
	_materials.clear()
	_patter.clear()
	_patter_db.clear()
	_ambience.clear()
	for node in get_tree().get_nodes_in_group(GROUP_GLASS):
		var pane := node as GeometryInstance3D
		if not pane:
			continue
		var mat := pane.material_override as ShaderMaterial
		if mat and not _materials.has(mat):
			_materials.append(mat)
	for node in get_tree().get_nodes_in_group(GROUP_PATTER):
		var player := node as AudioStreamPlayer3D
		if player:
			_patter.append(player)
			_patter_db.append(player.volume_db)
	for node in get_tree().get_nodes_in_group(GROUP_AMBIENCE):
		var ambience := node as HingeAmbience
		if ambience:
			_ambience.append(ambience)
	_set_wet_shader(_wet_shader, true)
	_apply()


## True while the panes use the wet (rain) shader.
func is_wet_shader() -> bool:
	return _wet_shader


## True when nothing is wet and nothing moves: the glass costs its dry price.
func is_dry() -> bool:
	return target == 0.0 and amount == 0.0 and wetness == 0.0 and slide == 0.0


func _wet_target() -> float:
	return lerpf(0.3, 1.0, amount)


func _process(delta: float) -> void:
	var dt := delta * time_scale
	amount = _approach(amount, target, dt, ease_time)
	if amount > 0.0:
		var wet_goal := _wet_target()
		if wetness < wet_goal:
			wetness = _approach(wetness, wet_goal, dt, wet_time / 3.0)
		else:
			wetness = maxf(wet_goal, wetness - dt / dry_time)
	else:
		wetness = maxf(0.0, wetness - dt / dry_time)
	# Runners slide while it rains and stop soon after it stops.
	var slide_goal := amount if target > 0.0 else 0.0
	slide = _approach(slide, slide_goal, dt, ease_time if slide_goal > slide else slide_stop_time / 3.0)
	slide = minf(slide, wetness)
	rain_time += dt * amount
	slide_time += dt * slide
	_apply()
	if is_dry():
		set_process(false)


## Exponential approach with time constant tau; snaps when close.
static func _approach(value: float, goal: float, dt: float, tau: float) -> float:
	var next := lerpf(value, goal, 1.0 - exp(-dt / maxf(tau, 0.001)))
	return goal if absf(next - goal) < 0.002 else next


func _set_wet_shader(wet: bool, force := false) -> void:
	if wet == _wet_shader and not force:
		return
	_wet_shader = wet
	for mat in _materials:
		mat.shader = WET_SHADER if wet else DRY_SHADER


func _apply() -> void:
	_set_wet_shader(target > 0.0 or amount > 0.0 or wetness > 0.0)
	for mat in _materials:
		mat.set_shader_parameter("rain_amount", amount)
		mat.set_shader_parameter("rain_wet", wetness)
		mat.set_shader_parameter("rain_time", rain_time)
		mat.set_shader_parameter("rain_slide_time", slide_time)
	for i in _patter.size():
		var player := _patter[i]
		if amount > 0.01:
			player.volume_db = _patter_db[i] + linear_to_db(amount)
			if not player.playing:
				player.play()
		elif player.playing:
			player.stop()
	for ambience in _ambience:
		ambience.gain = amount
