class_name WorldState
extends Node
## The world's date, time of day and weather: the one place every system asks
## (D-051, D-052). [DayNight] lights the sky, the city and the windows from it,
## the window HUD shows its clock, temperature and weather, and [RainOnGlass]
## gets its rain from [method set_rain].
##
## By default the clock and the date follow the PC. [method set_time] jumps to
## a time and runs on from there at [member speed] (game seconds per real
## second; 0 stops the clock); [method follow_clock] goes back to the PC's
## time. `--time=<h|HH:MM|now>`, `--time-speed=<x>`, `--date=<MM-DD>` and
## `--weather=<clear|cloudy>` set them at start; tests, stills and perf runs
## start at a fixed date, time and weather unless told otherwise, so their
## results don't depend on when they run.
##
## The sun is the real sun at [member latitude]/[member longitude] on
## [member day_of_year] (seasons: in October it sets around 18:45, in June
## after 21:15), in local time [member utc_offset]. The apartment's windows
## (world -Z) face [member facing] on the compass, so in autumn and winter the
## sun sets right in front of them.
##
## Weather: [constant Weather.CLEAR] is a hazy day with the sun out (sun disk,
## shadows), [constant Weather.CLOUDY] an overcast one, [constant Weather.RAIN]
## overcast with rain. [member clouds] eases toward the weather's cover over
## [member weather_ease] seconds.
##
## [signal time_changed] fires once per game minute and [signal weather_changed]
## at most [constant WEATHER_RATE] times a second while the clouds move, never
## per frame; listeners do their work then.

signal time_changed(hours: float)
signal weather_changed

enum Weather { CLEAR, CLOUDY, RAIN }

const GROUP := &"world_state"
## Real seconds between re-reads of the PC's clock while following it (the
## clock runs on frame deltas in between).
const CLOCK_SYNC := 10.0
## weather_changed signals per second while the clouds move.
const WEATHER_RATE := 4.0
## Cloud cover of each weather.
const COVER: Array[float] = [0.0, 1.0, 1.0]
const MONTH_DAYS: Array[int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

## Follow the PC's local time and date (see the class description).
@export var follow_system_clock := true
## Game seconds per real second while not following the PC's clock.
@export var speed := 1.0
@export_range(-80.0, 80.0, 0.1, "suffix:°") var latitude := 48.0
## East positive.
@export_range(-180.0, 180.0, 0.1, "suffix:°") var longitude := 11.5
## Compass bearing the apartment's windows (world -Z) look toward.
@export_range(0.0, 360.0, 0.1, "suffix:°") var facing := 240.0
## Weather at start.
@export var start_weather := Weather.CLEAR
## Seconds the clouds take to come or go (time constant).
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var weather_ease := 8.0
## The day's mean temperature, its swing (coldest 05:00, warmest 15:00) and
## how much colder full rain makes it.
@export_custom(PROPERTY_HINT_NONE, "suffix:°C") var mean_temperature := 15.0
@export_custom(PROPERTY_HINT_NONE, "suffix:°C") var temperature_swing := 4.0
@export_custom(PROPERTY_HINT_NONE, "suffix:°C") var rain_chill := 3.0

## Hours since midnight, 0..24.
var hours := 22.0
## Day of the year, 1..365 (seasons).
var day_of_year := 172
## Hours local time is ahead of UTC (summer time included).
var utc_offset := 2.0
## The weather; [constant Weather.RAIN] whenever [member rain] > 0.
var weather := Weather.CLEAR
## Cloud cover now, 0 (sun out) .. 1 (overcast).
var clouds := 0.0
## How hard it rains, 0..1.
var rain := 0.0

var _minute := -1
var _sync_left := 0.0
var _dry_weather := Weather.CLEAR
var _weather_left := 0.0
# Set by set_date: the PC's date no longer overrides it.
var _date_fixed := false


func _enter_tree() -> void:
	add_to_group(GROUP)


func _ready() -> void:
	_read_system_date()
	set_weather(start_weather, true)
	if follow_system_clock:
		follow_clock()
	else:
		_update_processing()
		_announce(true)


## The scene's WorldState, or null.
static func find(tree: SceneTree) -> WorldState:
	return tree.get_first_node_in_group(GROUP) as WorldState


## Jumps to [param at] hours (0..24) and runs on at [param run_speed] (keeps
## [member speed] when negative; 0 stops the clock).
func set_time(at: float, run_speed := -1.0) -> void:
	follow_system_clock = false
	if run_speed >= 0.0:
		speed = run_speed
	hours = fposmod(at, 24.0)
	_update_processing()
	_announce(true)


## Sets the date (seasons) and, unless NAN, the local time's UTC offset.
func set_date(month: int, day: int, offset := NAN) -> void:
	day_of_year = _day_of_year(month, day)
	_date_fixed = true
	if not is_nan(offset):
		utc_offset = offset
	_announce(true)


## Steps the date by [param days] (wraps around the year).
func shift_days(days: int) -> void:
	day_of_year = posmod(day_of_year - 1 + days, 365) + 1
	_date_fixed = true
	_announce(true)


## Steps the date by [param months], keeping the day (clamped to the month).
func shift_months(months: int) -> void:
	var date := get_month_day()
	var month := posmod(date.x - 1 + months, 12) + 1
	set_date(month, mini(date.y, MONTH_DAYS[month - 1]))


## The date as (month, day).
func get_month_day() -> Vector2i:
	var day := day_of_year
	for month in 12:
		if day <= MONTH_DAYS[month]:
			return Vector2i(month + 1, day)
		day -= MONTH_DAYS[month]
	return Vector2i(12, 31)


## Follows the PC's local time and date again.
func follow_clock() -> void:
	follow_system_clock = true
	_date_fixed = false
	_read_system_date()
	hours = _system_hours()
	_sync_left = CLOCK_SYNC
	_update_processing()
	_announce(true)


## Sets the weather; immediate: the clouds jump there. Rain keeps its own
## amount ([method set_rain]); setting CLEAR or CLOUDY stops it.
func set_weather(kind: Weather, immediate := false) -> void:
	if kind != Weather.RAIN:
		_dry_weather = kind
		if rain > 0.0:
			set_rain(0.0, immediate)
	weather = kind
	if immediate:
		clouds = COVER[kind]
	_update_processing()
	weather_changed.emit()


## Sets the rain (0..1) and passes it on to the rain on the glass;
## immediate: wet or dry at once (tests, stills, perf). Rain brings the
## clouds; when it stops, the weather before it comes back.
func set_rain(amount: float, immediate := false) -> void:
	rain = clampf(amount, 0.0, 1.0)
	weather = Weather.RAIN if rain > 0.0 else _dry_weather
	if immediate:
		clouds = COVER[weather]
	var glass := get_tree().get_first_node_in_group(RainOnGlass.GROUP) as RainOnGlass
	if glass:
		glass.set_rain(rain, immediate)
	_update_processing()
	weather_changed.emit()


## The sun's direction in the world (unit vector toward it), from its
## azimuth and elevation and [member facing].
func get_sun_direction() -> Vector3:
	var sun := _sun_enu()
	var f := deg_to_rad(facing)
	var north_w := Vector3(-sin(f), 0.0, -cos(f))
	var east_w := Vector3(cos(f), 0.0, -sin(f))
	return (east_w * sun.x + north_w * sun.y + Vector3.UP * sun.z).normalized()


## The sun's height above the horizon in degrees (negative at night).
func get_sun_elevation() -> float:
	return rad_to_deg(asin(clampf(_sun_enu().z, -1.0, 1.0)))


## The sun's compass bearing in degrees (90 east, 180 south).
func get_sun_azimuth() -> float:
	var sun := _sun_enu()
	return fposmod(rad_to_deg(atan2(sun.x, sun.y)), 360.0)


## Local time (hours) the sun crosses [param elevation] today, rising or
## setting; -1 if it doesn't (polar day or night).
func find_sun_crossing(rising: bool, elevation := -0.833) -> float:
	var saved := hours
	var found := -1.0
	var previous := NAN
	for m in range(0, 1441, 2):
		hours = m / 60.0
		var e := get_sun_elevation() - elevation
		if not is_nan(previous) and ((rising and previous < 0.0 and e >= 0.0) or (not rising and previous >= 0.0 and e < 0.0)):
			found = hours - 2.0 / 60.0 * e / (e - previous)
			break
		previous = e
	hours = saved
	return found


## Temperature in °C: a daily curve, colder in the rain.
func get_temperature() -> float:
	var day := cos((hours - 15.0) / 24.0 * TAU)
	return mean_temperature + temperature_swing * day - rain_chill * rain


## What the window HUD shows (WindowHud.source).
func get_hud_state() -> Dictionary:
	var minutes := int(hours * 60.0) % 1440
	var shown := WindowHud.Weather.CLOUDY
	if rain > 0.0:
		shown = WindowHud.Weather.RAIN
	elif weather == Weather.CLEAR:
		shown = WindowHud.Weather.SUN if get_sun_elevation() > -0.833 else WindowHud.Weather.CLEAR_NIGHT
	@warning_ignore("integer_division")
	return {"hour": minutes / 60, "minute": minutes % 60,
			"temperature": roundi(get_temperature()), "weather": shown}


## Parses "now", "HH:MM" or decimal hours; -1 if it can't.
static func parse_time(text: String) -> float:
	if text == "now":
		return -1.0
	if text.contains(":"):
		var parts := text.split(":")
		return fposmod(float(parts[0]) + float(parts[1]) / 60.0, 24.0)
	return fposmod(float(text), 24.0) if text.is_valid_float() else -1.0


## Parses "MM-DD" or "YYYY-MM-DD" into [month, day]; empty if it can't.
static func parse_date(text: String) -> Array[int]:
	var parts := text.split("-")
	if parts.size() < 2 or not parts[-1].is_valid_int() or not parts[-2].is_valid_int():
		return []
	var month := int(parts[-2])
	var day := int(parts[-1])
	if month < 1 or month > 12 or day < 1 or day > 31:
		return []
	return [month, day]


## Weather by name: clear, cloudy, rain; -1 if unknown.
static func parse_weather(text: String) -> int:
	return ["clear", "cloudy", "rain"].find(text.to_lower())


func _process(delta: float) -> void:
	var before := hours
	if follow_system_clock:
		_sync_left -= delta
		if _sync_left <= 0.0:
			_sync_left = CLOCK_SYNC
			_read_system_date()
			hours = _system_hours()
		else:
			hours = fposmod(hours + delta / 3600.0, 24.0)
	elif speed != 0.0:
		hours = fposmod(hours + delta * speed / 3600.0, 24.0)
		if hours < before and speed > 0.0:
			day_of_year = day_of_year % 365 + 1
	_announce()
	_ease_clouds(delta)
	_update_processing()


func _ease_clouds(delta: float) -> void:
	var goal := COVER[weather]
	if clouds == goal:
		return
	clouds = lerpf(clouds, goal, 1.0 - exp(-delta / maxf(weather_ease, 0.001)))
	if absf(clouds - goal) < 0.005:
		clouds = goal
		_weather_left = 0.0
	_weather_left -= delta
	if _weather_left <= 0.0:
		_weather_left = 1.0 / WEATHER_RATE
		weather_changed.emit()


func _update_processing() -> void:
	set_process(follow_system_clock or speed != 0.0 or clouds != COVER[weather])


func _announce(force := false) -> void:
	var minute := int(hours * 60.0)
	if minute == _minute and not force:
		return
	_minute = minute
	time_changed.emit(hours)


## The sun as (east, north, up), unit length (NOAA's approximation: equation
## of time and declination from the day of the year).
func _sun_enu() -> Vector3:
	var gamma := TAU / 365.0 * (day_of_year - 1 + (hours - utc_offset - 12.0) / 24.0)
	var eq_time := 229.18 * (0.000075 + 0.001868 * cos(gamma) - 0.032077 * sin(gamma)
			- 0.014615 * cos(2.0 * gamma) - 0.040849 * sin(2.0 * gamma))
	var dec := 0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma) - 0.006758 * cos(2.0 * gamma) \
			+ 0.000907 * sin(2.0 * gamma) - 0.002697 * cos(3.0 * gamma) + 0.00148 * sin(3.0 * gamma)
	var solar_minutes := hours * 60.0 + eq_time + 4.0 * longitude - 60.0 * utc_offset
	var hour_angle := deg_to_rad(solar_minutes / 4.0 - 180.0)
	var lat := deg_to_rad(latitude)
	var east := -cos(dec) * sin(hour_angle)
	var north := sin(dec) * cos(lat) - cos(dec) * sin(lat) * cos(hour_angle)
	var up := sin(lat) * sin(dec) + cos(lat) * cos(dec) * cos(hour_angle)
	return Vector3(east, north, up)


func _read_system_date() -> void:
	if _date_fixed:
		return
	var local := Time.get_datetime_dict_from_system(false)
	var utc := Time.get_datetime_dict_from_system(true)
	day_of_year = _day_of_year(local.month, local.day)
	var offset_s := Time.get_unix_time_from_datetime_dict(local) - Time.get_unix_time_from_datetime_dict(utc)
	utc_offset = roundf(offset_s / 900.0) / 4.0


static func _day_of_year(month: int, day: int) -> int:
	var m := clampi(month, 1, 12)
	var start := 0
	for i in m - 1:
		start += MONTH_DAYS[i]
	return start + clampi(day, 1, MONTH_DAYS[m - 1])


static func _system_hours() -> float:
	var now := Time.get_time_dict_from_system()
	var fraction := fmod(Time.get_unix_time_from_system(), 1.0)
	return (now.hour * 3600.0 + now.minute * 60.0 + now.second + fraction) / 3600.0
