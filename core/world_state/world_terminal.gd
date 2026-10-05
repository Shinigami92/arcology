class_name WorldTerminal
extends Node3D
## Holographic wall terminal for the world state (D-053): the time, date,
## weather and temperature, and touch keys the fingertips press (D-031) to
## step the time, jump to sunrise, noon or sunset, go back to the PC's clock,
## set the clock's speed, the weather and the rain, and step the date. The
## controller rays press them from afar too (GrabRay, D-054): a pointed key
## lights up.
##
## The hologram is built at start from [constant KEYS]: one MultiMesh of tiles
## (assets/shaders/hologram_tile.gdshader: unshaded, additive, scanlines), a
## Label3D per key with an MSDF font (crisp at any distance) and a touch
## Area3D per key on the fingertips' layer. A touch flashes the key, clicks
## and buzzes the controller of the touching hand; the time keys repeat while
## held. Origin: the panel's center, +Z toward the viewer; the hologram floats
## [constant PLANE_Z] in front of it. Render layer 12 (in-world UI is never
## reflected).

## [id, label, row, column, repeats while held]
const KEYS: Array[Array] = [
	["hour_back", "−1 h", 0, 0, true], ["min_back", "−10 min", 0, 1, true],
	["min_fwd", "+10 min", 0, 2, true], ["hour_fwd", "+1 h", 0, 3, true],
	["sunrise", "SUNRISE", 1, 0, false], ["noon", "NOON", 1, 1, false],
	["sunset", "SUNSET", 1, 2, false], ["now", "NOW", 1, 3, false],
	["pause", "PAUSE", 2, 0, false], ["x1", "×1", 2, 1, false],
	["x60", "×60", 2, 2, false], ["x600", "×600", 2, 3, false],
	["clear", "CLEAR", 3, 0, false], ["cloudy", "CLOUDY", 3, 1, false],
	["rain_less", "RAIN −", 3, 2, true], ["rain_more", "RAIN +", 3, 3, true],
	["month_back", "−MONTH", 4, 0, true], ["day_back", "−DAY", 4, 1, true],
	["day_fwd", "+DAY", 4, 2, true], ["month_fwd", "+MONTH", 4, 3, true],
]
const MONTHS: Array[String] = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
const WEATHER_NAMES: Array[String] = ["CLEAR", "CLOUDY", "RAIN"]
const TILE_SHADER := preload("res://assets/shaders/hologram_tile.gdshader")
const FINGERTIP_LAYER := 131072
const UI_LAYER := 2048
## Panel and key sizes (m).
const PANEL := Vector2(0.46, 0.44)
const KEY := Vector2(0.098, 0.05)
const GAP := 0.012
const HEADER := 0.085
## The hologram floats this far in front of the wall (m).
const PLANE_Z := 0.035
## Seconds before a held key repeats, and between repeats.
const REPEAT_DELAY := 0.45
const REPEAT_EVERY := 0.12
const RAIN_STEP := 0.2

@export var color := Color(0.02, 0.85, 0.91)
@export var click: AudioStreamPlayer3D

var _world: WorldState
var _tiles: MultiMesh
var _keys := {}            # id -> {"index": tile index, "area": Area3D, "repeats": bool}
var _labels := {}          # header name -> Label3D
var _font: SystemFont
var _flash := {}           # tile index -> seconds left
var _held := ""
var _hovered := ""
var _held_for := 0.0
var _next_repeat := 0.0
var _controllers: Array[XRController3D] = []


func _ready() -> void:
	_world = WorldState.find(get_tree())
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Bahnschrift", "Segoe UI", "Arial"])
	_font.multichannel_signed_distance_field = true
	_build()
	for node in get_tree().root.find_children("*", "XRController3D", true, false):
		_controllers.append(node as XRController3D)
	if _world:
		_world.time_changed.connect(_on_time_changed)
		_world.weather_changed.connect(refresh)
	refresh()
	set_process(false)


## Presses the key [param id] as a touch would (tests).
func press(id: String) -> void:
	_on_key(id)


## The header's text, top to bottom (tests).
func get_header() -> PackedStringArray:
	return PackedStringArray([_labels["time"].text, _labels["date"].text, _labels["weather"].text, _labels["mode"].text])


## The key's touch area (tests).
func get_key_area(id: String) -> Area3D:
	return _keys[id]["area"]


## Updates the header and the keys' highlights from the world state.
func refresh() -> void:
	if not _world:
		return
	var minutes := int(_world.hours * 60.0) % 1440
	@warning_ignore("integer_division")
	_labels["time"].text = "%02d:%02d" % [minutes / 60, minutes % 60]
	var date := _world.get_month_day()
	_labels["date"].text = "%02d %s" % [date.y, MONTHS[date.x - 1]]
	var weather := WEATHER_NAMES[_world.weather]
	if _world.rain > 0.0:
		weather = "RAIN %d %%" % roundi(_world.rain * 100.0)
	_labels["weather"].text = "%s · %d °C" % [weather, roundi(_world.get_temperature())]
	var mode := "LIVE"
	if not _world.follow_system_clock:
		mode = "PAUSED" if _world.speed == 0.0 else "×%s" % _speed_text(_world.speed)
	_labels["mode"].text = mode
	var active := {
		"now": _world.follow_system_clock,
		"pause": not _world.follow_system_clock and _world.speed == 0.0,
		"x1": not _world.follow_system_clock and _world.speed == 1.0,
		"x60": not _world.follow_system_clock and _world.speed == 60.0,
		"x600": not _world.follow_system_clock and _world.speed == 600.0,
		"clear": _world.weather == WorldState.Weather.CLEAR,
		"cloudy": _world.weather == WorldState.Weather.CLOUDY,
		"rain_more": _world.rain > 0.0,
	}
	for id: String in _keys:
		var on: bool = active.get(id, false)
		var tint := color * (1.0 if on else 0.55)
		var fill := 1.0 if on else 0.0
		if id == _hovered:
			tint = color.lerp(Color.WHITE, 0.35) * 1.3
			fill = 1.5
		_set_tile(_keys[id]["index"], tint, fill)


func _on_time_changed(_hours: float) -> void:
	refresh()


func _on_key(id: String) -> void:
	if not _world:
		return
	match id:
		"hour_back": _world.set_time(_world.hours - 1.0)
		"hour_fwd": _world.set_time(_world.hours + 1.0)
		"min_back": _world.set_time(_world.hours - 10.0 / 60.0)
		"min_fwd": _world.set_time(_world.hours + 10.0 / 60.0)
		"sunrise": _world.set_time(_world.find_sun_crossing(true))
		"noon": _world.set_time(_solar_noon())
		"sunset": _world.set_time(_world.find_sun_crossing(false) - 0.25)
		"now": _world.follow_clock()
		"pause": _world.set_time(_world.hours, 0.0)
		"x1": _world.set_time(_world.hours, 1.0)
		"x60": _world.set_time(_world.hours, 60.0)
		"x600": _world.set_time(_world.hours, 600.0)
		"clear": _world.set_weather(WorldState.Weather.CLEAR)
		"cloudy": _world.set_weather(WorldState.Weather.CLOUDY)
		"rain_less": _world.set_rain(snappedf(maxf(_world.rain - RAIN_STEP, 0.0), 0.01))
		"rain_more": _world.set_rain(snappedf(minf(_world.rain + RAIN_STEP, 1.0), 0.01))
		"day_back": _world.shift_days(-1)
		"day_fwd": _world.shift_days(1)
		"month_back": _world.shift_months(-1)
		"month_fwd": _world.shift_months(1)
	refresh()
	var index: int = _keys[id]["index"]
	_flash[index] = 0.15
	_set_tile(index, Color(0.75, 1.0, 1.0), 1.0)
	set_process(true)


## Local time of the sun's highest point today.
func _solar_noon() -> float:
	var rise := _world.find_sun_crossing(true)
	var down := _world.find_sun_crossing(false)
	return (rise + down) * 0.5 if rise >= 0.0 and down >= 0.0 else 12.0


func _process(delta: float) -> void:
	for index: int in _flash.keys():
		_flash[index] -= delta
		if _flash[index] <= 0.0:
			_flash.erase(index)
			refresh()
	if _held != "":
		_held_for += delta
		if _held_for >= _next_repeat:
			_next_repeat += REPEAT_EVERY
			_on_key(_held)
	if _flash.is_empty() and _held == "":
		set_process(false)


func _on_hover(on: bool, id: String) -> void:
	if on:
		_hovered = id
	elif _hovered == id:
		_hovered = ""
	refresh()


func _on_touch(area: Area3D, id: String) -> void:
	_on_key(id)
	if click:
		click.play()
	# A controller ray buzzes its own hand.
	if not area.has_meta(&"ray_presser"):
		_buzz(area.global_position)
	if _keys[id]["repeats"]:
		_held = id
		_held_for = 0.0
		_next_repeat = REPEAT_DELAY
		set_process(true)


func _on_release(_area: Area3D, id: String) -> void:
	if _held == id:
		_held = ""


## A short pulse on the controller nearest the touching fingertip.
func _buzz(at: Vector3) -> void:
	var nearest: XRController3D = null
	for controller in _controllers:
		if is_instance_valid(controller) and (not nearest or controller.global_position.distance_to(at) < nearest.global_position.distance_to(at)):
			nearest = controller
	if nearest:
		nearest.trigger_haptic_pulse("haptic", 0.0, 0.35, 0.04, 0.0)


func _build() -> void:
	var top := PANEL.y * 0.5
	var left := -PANEL.x * 0.5
	var inner := PANEL.x - 2.0 * GAP
	var rects: Array[Rect2] = [Rect2(Vector2(left, -top), PANEL)]
	var key_rects: Array[Rect2] = []
	for key in KEYS:
		var x := -inner * 0.5 + (KEY.x + GAP) * int(key[3])
		var y := top - GAP - HEADER - GAP - (KEY.y + GAP) * int(key[2]) - KEY.y
		key_rects.append(Rect2(Vector2(x, y), KEY))
	rects.append_array(key_rects)

	_tiles = MultiMesh.new()
	_tiles.transform_format = MultiMesh.TRANSFORM_3D
	_tiles.use_colors = true
	_tiles.use_custom_data = true
	var quad := QuadMesh.new()
	_tiles.mesh = quad
	_tiles.instance_count = rects.size()
	for i in rects.size():
		var r := rects[i]
		var center := r.get_center()
		var tile_basis := Basis.from_scale(Vector3(r.size.x, r.size.y, 1.0))
		_tiles.set_instance_transform(i, Transform3D(tile_basis, Vector3(center.x, center.y, PLANE_Z)))
		_tiles.set_instance_custom_data(i, Color(r.size.x, r.size.y, 0.0, 0.0))
		_tiles.set_instance_color(i, color * 0.3)
	var material := ShaderMaterial.new()
	material.shader = TILE_SHADER
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Tiles"
	mmi.multimesh = _tiles
	mmi.material_override = material
	mmi.layers = UI_LAYER
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)

	var header_y := top - GAP - HEADER * 0.5
	_labels["time"] = _label("Time", "00:00", 150, Vector2(left + GAP, header_y), HORIZONTAL_ALIGNMENT_LEFT)
	var right := -left - GAP
	_labels["date"] = _label("Date", "", 52, Vector2(right, header_y + 0.024), HORIZONTAL_ALIGNMENT_RIGHT)
	_labels["weather"] = _label("Weather", "", 44, Vector2(right, header_y), HORIZONTAL_ALIGNMENT_RIGHT)
	_labels["mode"] = _label("Mode", "", 44, Vector2(right, header_y - 0.022), HORIZONTAL_ALIGNMENT_RIGHT)

	for i in KEYS.size():
		var key: Array = KEYS[i]
		var id: String = key[0]
		var r := key_rects[i]
		_label("Key_" + id, key[1], 46, r.get_center(), HORIZONTAL_ALIGNMENT_CENTER)
		var area := Area3D.new()
		area.name = "Touch_" + id
		area.collision_layer = 0
		area.collision_mask = FINGERTIP_LAYER
		area.monitorable = false
		area.position = Vector3(r.get_center().x, r.get_center().y, PLANE_Z + 0.005)
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(KEY.x, KEY.y, 0.04)
		shape.shape = box
		area.add_child(shape)
		area.area_entered.connect(_on_touch.bind(id))
		area.area_exited.connect(_on_release.bind(id))
		area.set_meta(&"ray_hover", _on_hover.bind(id))
		add_child(area)
		_keys[id] = {"index": i + 1, "area": area, "repeats": key[4]}


func _label(node_name: String, text: String, size: int, at: Vector2, align: HorizontalAlignment) -> Label3D:
	var label := Label3D.new()
	label.name = node_name
	label.text = text
	label.font = _font
	label.font_size = size
	label.pixel_size = 0.0002
	label.outline_size = 0
	label.modulate = Color(0.75, 1.0, 1.0)
	label.horizontal_alignment = align
	label.position = Vector3(at.x, at.y, PLANE_Z + 0.001)
	label.layers = UI_LAYER
	label.render_priority = 1
	label.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(label)
	return label


func _set_tile(index: int, tint: Color, fill: float) -> void:
	_tiles.set_instance_color(index, tint)
	var custom := _tiles.get_instance_custom_data(index)
	custom.b = fill
	_tiles.set_instance_custom_data(index, custom)


static func _speed_text(value: float) -> String:
	return str(int(value)) if value == floorf(value) else "%.1f" % value
