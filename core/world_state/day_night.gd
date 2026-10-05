class_name DayNight
extends Node
## Lights the world from the [WorldState] clock and weather (D-051, D-052):
## sky, ambient light, fog, the sun (by night the moon), the city's lit
## windows and signs, the traffic lights; and tells the rooms what comes in
## through their windows ([member window_color], [member window_scale]) and
## how much daylight there is ([member daylight]) through [signal changed].
##
## Night is the scene as authored (the skyline's environment, sky, moon and
## materials, captured at start). By day the weather's cloud cover blends two
## looks: a hazy day with the sun out (a soft glow in the smog, scattering in
## the fog, sharp shadows) and an overcast one (grey-blue, no sun to see,
## faint shadows). Dusk tints the horizon, the fog and the low sun; rain
## darkens the day.
##
## The sun casts shadows and lights everything, the rooms included: the walls
## keep it out except through the windows. Shadows reach
## [member shadow_distance]; the city beyond is lit unshadowed. The moon has no
## shadows, so it only lights what's outside (render layer 13 "Outside", set on
## [member outside] at start); it would shine through the walls otherwise.
##
## Event driven: it updates when the clock passes a minute or the weather
## changes, and only if the light changed visibly, so a night costs nothing.

signal changed

const GROUP := &"day_night"
## Render layer 13 "Outside": the city, the only thing the moon lights.
const LAYER_OUTSIDE := 1 << 12
const ALL_LAYERS := 0xFFFFF
## Smallest change that's worth an update.
const EPSILON := 0.002

@export var world_environment: WorldEnvironment
## The sun by day, the moon by night (its authored direction and energy).
@export var sky_light: DirectionalLight3D
## Everything outside: put on [constant LAYER_OUTSIDE] at start.
@export var outside: Array[Node3D] = []
## Emissive materials of lit windows: dimmed to [member lit_windows_day] by day.
@export var lit_windows: Array[BaseMaterial3D] = []
## Emissive signs and ads: dimmed to [member signs_day] by day.
@export var signs: Array[BaseMaterial3D] = []
@export var traffic: FlyingTraffic
## Its towers' roots have lit windows too (dimmed like [member lit_windows]).
@export var far_towers: FarTowers
## How far the sun's shadows reach (the rooms, not the city).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var shadow_distance := 24.0

@export_group("Sun out")
@export var clear_sky_top := Color(0.26, 0.34, 0.47)
@export var clear_sky_horizon := Color(0.55, 0.53, 0.5)
@export var clear_ambient_color := Color(0.45, 0.52, 0.64)
@export var clear_ambient_energy := 0.55
@export var clear_fog_color := Color(0.46, 0.46, 0.46)
@export var clear_sun_color := Color(1.0, 0.92, 0.8)
@export var clear_sun_energy := 1.8
## The sun's glow in the sky (degrees) and in the fog.
@export var clear_sun_glow := 7.0
@export_range(0.0, 1.0) var clear_sun_scatter := 0.1
@export var clear_window_color := Color(0.82, 0.88, 1.0)

@export_group("Overcast")
@export var overcast_sky_top := Color(0.3, 0.33, 0.38)
@export var overcast_sky_horizon := Color(0.44, 0.46, 0.49)
@export var overcast_ambient_color := Color(0.5, 0.55, 0.62)
@export var overcast_ambient_energy := 0.65
@export var overcast_fog_color := Color(0.38, 0.4, 0.44)
@export var overcast_sun_color := Color(0.85, 0.88, 0.95)
@export var overcast_sun_energy := 0.45
## Shadow strength under full cloud (the light comes from all over the sky).
@export_range(0.0, 1.0) var overcast_shadow := 0.35
@export var overcast_window_color := Color(0.78, 0.84, 0.95)

## Below the horizon the sky is the fog, so the towers fade into a haze with
## no floor; the streets far below add this glow to it at night (sodium and
## neon light scattered up through the smog).
@export var abyss_glow := Color(0.16, 0.07, 0.035)
## Share of the glow left by day.
@export_range(0.0, 1.0) var abyss_glow_day := 0.15

@export_group("Day")
@export var day_sky_energy := 1.0
@export var day_fog_energy := 1.0
## What the windows let in by day, relative to the night's city spill.
@export var day_window_scale := 2.2
@export_range(0.0, 1.0) var lit_windows_day := 0.2
@export_range(0.0, 1.0) var signs_day := 0.6
@export_range(0.0, 1.0) var traffic_lights_day := 0.3
## Full rain scales the day's light by this.
@export_range(0.0, 1.0) var rain_day := 0.6

@export_group("Dusk")
@export var dusk_sky_top := Color(0.14, 0.13, 0.26)
@export var dusk_horizon := Color(0.85, 0.42, 0.32)
@export var dusk_fog_color := Color(0.5, 0.3, 0.3)
@export var dusk_sun_color := Color(1.0, 0.5, 0.28)
@export var dusk_window_color := Color(1.0, 0.62, 0.48)

## 0 at night, 1 by day (the sun more than 7° up), 0.5 at sunset.
var daylight := 0.0
## 1 while the sun is near the horizon, else 0.
var dusk := 0.0
## Cloud cover the light was made for (WorldState.clouds).
var clouds := 0.0
## What the windows let in, for [WindowLight]: blended toward this color by
## [member window_mix], energy times [member window_scale].
var window_color := Color.WHITE
var window_mix := 0.0
var window_scale := 1.0

var _world: WorldState
var _sky: ProceduralSkyMaterial
var _night := {}
var _lit_energy: PackedFloat32Array = []
var _sign_energy: PackedFloat32Array = []
var _applied := PackedFloat32Array([-1, -1, -1, -1, -1])
var _sun_mode := -1


func _enter_tree() -> void:
	add_to_group(GROUP)


func _ready() -> void:
	_capture_night()
	for node in outside:
		_tag_outside(node)
	if sky_light:
		sky_light.directional_shadow_max_distance = shadow_distance
	_world = WorldState.find(get_tree())
	if not _world:
		_set_sun_mode(false)
		return
	_world.time_changed.connect(_on_time_changed)
	_world.weather_changed.connect(refresh)
	refresh()


## The scene's DayNight, or null.
static func find(tree: SceneTree) -> DayNight:
	return tree.get_first_node_in_group(GROUP) as DayNight


## Recomputes the light from the world state; force: apply even if it barely
## changed.
func refresh(force := false) -> void:
	if not _world:
		return
	var elevation := _world.get_sun_elevation()
	var light := smoothstep(-7.0, 7.0, elevation)
	var low_sun := clampf(1.0 - absf(elevation - 1.0) / 10.0, 0.0, 1.0)
	# The sun's direction only matters while it's up (the moon stands still).
	var key := PackedFloat32Array([light, low_sun, snappedf(elevation, 0.25) if elevation > 0.0 else -1.0,
			_world.rain, _world.clouds])
	if not force and _close(key, _applied):
		return
	_applied = key
	daylight = light
	dusk = low_sun
	clouds = _world.clouds
	_apply(elevation, _world.rain)
	changed.emit()


func _on_time_changed(_hours: float) -> void:
	refresh()


func _apply(elevation: float, rain: float) -> void:
	var day := daylight
	var gloom := lerpf(1.0, rain_day, rain)
	var tint := dusk * (1.0 - clouds * 0.6)
	if _sky:
		var top := clear_sky_top.lerp(overcast_sky_top, clouds) * gloom
		var horizon := clear_sky_horizon.lerp(overcast_sky_horizon, clouds) * gloom
		_sky.sky_top_color = _mix(_night["sky_top"], top, day, dusk_sky_top, tint * 0.5)
		horizon = _mix(_night["sky_horizon"], horizon, day, dusk_horizon, tint * 0.7)
		_sky.sky_horizon_color = horizon
		_sky.ground_horizon_color = horizon
		_sky.sky_energy_multiplier = lerpf(_night["sky_energy"], day_sky_energy, day)
		_sky.sun_angle_max = clear_sun_glow * (1.0 - clouds) * smoothstep(-2.0, 2.0, elevation)
	var env := world_environment.environment if world_environment else null
	if env:
		var ambient := clear_ambient_color.lerp(overcast_ambient_color, clouds)
		var ambient_energy := lerpf(clear_ambient_energy, overcast_ambient_energy, clouds)
		env.ambient_light_color = (_night["ambient_color"] as Color).lerp(ambient, day)
		env.ambient_light_energy = lerpf(_night["ambient_energy"], ambient_energy * gloom, day)
		var fog := clear_fog_color.lerp(overcast_fog_color, clouds) * gloom
		env.fog_light_color = _mix(_night["fog_color"], fog, day, dusk_fog_color, tint * 0.6)
		env.fog_light_energy = lerpf(_night["fog_energy"], day_fog_energy, day)
		env.fog_sun_scatter = clear_sun_scatter * (1.0 - clouds) * smoothstep(-2.0, 4.0, elevation)
		if _sky:
			var glow := abyss_glow * lerpf(1.0, abyss_glow_day, day)
			_sky.ground_bottom_color = env.fog_light_color * env.fog_light_energy / maxf(_sky.sky_energy_multiplier, 0.01) + glow
		PlanarReflection.sync_environment(env)
	_apply_sky_light(elevation, gloom)
	for i in lit_windows.size():
		lit_windows[i].emission_energy_multiplier = _lit_energy[i] * lerpf(1.0, lit_windows_day, day)
	for i in signs.size():
		signs[i].emission_energy_multiplier = _sign_energy[i] * lerpf(1.0, signs_day, day)
	if traffic:
		traffic.set_light_scale(lerpf(1.0, traffic_lights_day, day))
	if far_towers:
		far_towers.set_light_scale(lerpf(1.0, lit_windows_day, day))
	window_color = clear_window_color.lerp(overcast_window_color, clouds).lerp(dusk_window_color, tint * 0.8)
	window_mix = day
	window_scale = lerpf(1.0, day_window_scale * gloom, day)


## Sun above the horizon, moon below; both fade out near it, so the switch
## doesn't show.
func _apply_sky_light(elevation: float, gloom: float) -> void:
	if not sky_light:
		return
	if elevation >= 0.0:
		_set_sun_mode(true)
		var sun := _world.get_sun_direction()
		sky_light.global_basis = Basis.looking_at(-sun, Vector3.UP)
		var color := clear_sun_color.lerp(overcast_sun_color, clouds)
		sky_light.light_color = dusk_sun_color.lerp(color, smoothstep(0.0, 20.0, elevation))
		var energy := lerpf(clear_sun_energy, overcast_sun_energy, clouds)
		sky_light.light_energy = energy * gloom * smoothstep(0.0, 10.0, elevation)
		sky_light.shadow_opacity = lerpf(1.0, overcast_shadow, clouds)
	else:
		_set_sun_mode(false)
		sky_light.global_basis = _night["moon_basis"]
		sky_light.light_color = _night["moon_color"]
		sky_light.light_energy = _night["moon_energy"] * smoothstep(2.0, 7.0, -elevation)
	sky_light.visible = sky_light.light_energy > 0.001


## Sun: shadows, lights every layer. Moon: no shadows, outside only.
func _set_sun_mode(sun: bool) -> void:
	if _sun_mode == int(sun):
		return
	_sun_mode = int(sun)
	sky_light.shadow_enabled = sun
	sky_light.light_cull_mask = ALL_LAYERS if sun else LAYER_OUTSIDE


func _capture_night() -> void:
	var env := world_environment.environment if world_environment else null
	if env:
		_sky = env.sky.sky_material as ProceduralSkyMaterial if env.sky else null
		_night["ambient_color"] = env.ambient_light_color
		_night["ambient_energy"] = env.ambient_light_energy
		_night["fog_color"] = env.fog_light_color
		_night["fog_energy"] = env.fog_light_energy
	if _sky:
		_night["sky_top"] = _sky.sky_top_color
		_night["sky_horizon"] = _sky.sky_horizon_color
		_night["sky_energy"] = _sky.sky_energy_multiplier
	if sky_light:
		_night["moon_basis"] = sky_light.global_basis
		_night["moon_color"] = sky_light.light_color
		_night["moon_energy"] = sky_light.light_energy
	for mat in lit_windows:
		_lit_energy.append(mat.emission_energy_multiplier)
	for mat in signs:
		_sign_energy.append(mat.emission_energy_multiplier)


## Night blended toward day by day, then toward a dusk color by tint.
static func _mix(night: Color, day_color: Color, day: float, dusk_color: Color, tint: float) -> Color:
	return night.lerp(day_color, day).lerp(dusk_color, tint)


static func _close(a: PackedFloat32Array, b: PackedFloat32Array) -> bool:
	for i in a.size():
		if i == 2:
			if a[i] != b[i]:
				return false
		elif absf(a[i] - b[i]) >= EPSILON:
			return false
	return true


## Puts the city on the Outside layer and keeps it out of the sun's shadow
## map: towers between the sun and the rooms would double its cost.
static func _tag_outside(node: Node) -> void:
	var visual := node as VisualInstance3D
	if visual:
		visual.layers |= LAYER_OUTSIDE
	var geometry := node as GeometryInstance3D
	if geometry:
		geometry.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children():
		_tag_outside(child)
