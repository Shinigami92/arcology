class_name InteriorDaylight
extends Node
## A zone's side of the day (D-051): dims its room lights as daylight comes in
## and brings them back at dusk, like a smart home, and re-captures its
## reflection probes when the light has changed enough to show in them.
## Driven by [DayNight]'s [signal DayNight.changed]; no per-frame work.
##
## Physical room switches (later) override the dimming.

## Lights in rooms with windows: dimmed to [member day_scale] by day.
@export var lights: Array[Light3D] = []
## Their share of the night energy at full daylight; 0 switches them off.
@export_range(0.0, 1.0) var day_scale := 0.0
## Daylight at which the dimming starts and where it's complete.
@export_range(0.0, 1.0) var dim_from := 0.3
@export_range(0.0, 1.0) var dim_to := 0.8
## The lamps' glowing meshes: their emission dims with the lights (they get
## one shared copy of their material, so other rooms' lamps stay on).
@export var fixtures: Array[MeshInstance3D] = []
## Probes to re-capture (UPDATE_ONCE) when the daylight moved by
## [member probe_step] since their last capture.
@export var probes: Array[ReflectionProbe] = []
@export_range(0.0, 1.0) var probe_step := 0.1

## Frames the probes stay in UPDATE_ALWAYS for a re-capture.
const RECAPTURE_FRAMES := 8

var _energy: PackedFloat32Array = []
var _recapture_frames := 0
var _fixture_material: BaseMaterial3D
var _fixture_energy := 0.0
var _probe_daylight := 0.0
var _day_night: DayNight


func _ready() -> void:
	set_process(false)
	for light in lights:
		_energy.append(light.light_energy)
	for fixture in fixtures:
		if not _fixture_material:
			var original := fixture.get_active_material(0) as BaseMaterial3D
			if not original:
				continue
			_fixture_material = original.duplicate() as BaseMaterial3D
			_fixture_energy = _fixture_material.emission_energy_multiplier
		fixture.set_surface_override_material(0, _fixture_material)
	_day_night = DayNight.find(get_tree())
	if not _day_night:
		return
	_day_night.changed.connect(_update)
	_probe_daylight = _day_night.daylight
	_update()


## Share of the night energy the lights have now.
func get_light_scale() -> float:
	var daylight := _day_night.daylight if _day_night else 0.0
	return lerpf(1.0, day_scale, smoothstep(dim_from, dim_to, daylight))


func _update() -> void:
	var scale := get_light_scale()
	for i in lights.size():
		lights[i].light_energy = _energy[i] * scale
		# A light at 0 still costs its pass (and its shadow map): hide it.
		lights[i].visible = scale > 0.001
	if _fixture_material:
		_fixture_material.emission_energy_multiplier = _fixture_energy * scale
	if absf(_day_night.daylight - _probe_daylight) >= probe_step or (
			_day_night.daylight != _probe_daylight and _day_night.daylight in [0.0, 1.0]):
		_probe_daylight = _day_night.daylight
		recapture_probes()


## Makes the probes render again: a few frames in UPDATE_ALWAYS, then back to
## UPDATE_ONCE (changing a property doesn't re-render an UPDATE_ONCE probe,
## measured). Costs about as much as a probe pass per frame for those frames.
func recapture_probes() -> void:
	_recapture_frames = RECAPTURE_FRAMES
	for probe in probes:
		probe.update_mode = ReflectionProbe.UPDATE_ALWAYS
	set_process(true)


## True while the probes are being re-captured.
func is_recapturing() -> bool:
	return _recapture_frames > 0


func _process(_delta: float) -> void:
	_recapture_frames -= 1
	if _recapture_frames > 0:
		return
	for probe in probes:
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
	set_process(false)
