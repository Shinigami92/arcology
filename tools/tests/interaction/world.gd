extends "res://tools/tests/interaction/base.gd"
## World group: clock, sun, seasons, weather, day/night, the world terminal, ray buttons, probe re-capture.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["world_clock", _test_world_clock],
		["world_sun", _test_world_sun],
		["world_seasons", _test_world_seasons],
		["world_weather", _test_world_weather],
		["day_night", _test_day_night],
		["day_night_idle", _test_day_night_idle],
		["day_night_update_cost", _test_day_night_update_cost],
		["world_rain", _test_world_rain],
		["world_terminal_touch", _test_world_terminal_touch],
		["world_terminal_keys", _test_world_terminal_keys],
		["ray_buttons", _test_ray_buttons],
		["probe_recapture", _test_probe_recapture],
	]


func _day_night() -> DayNight:
	return _main.get_node("Skyline/DayNight")


## Tests start at a fixed, stopped night; set_time runs on at its speed and
## announces each game minute; follow_clock goes back to the PC's time.
func _test_world_clock() -> void:
	var world := _world()
	var fixed := is_equal_approx(world.hours, 22.0) and not world.is_processing() and not world.follow_system_clock
	var minutes: Array[float] = []
	var record := func(h: float) -> void: minutes.append(h)
	world.time_changed.connect(record)
	world.set_time(10.0, 600.0)  # 10 game minutes per real second
	await get_tree().create_timer(0.5).timeout
	world.time_changed.disconnect(record)
	var advanced := (world.hours - 10.0) * 60.0
	var ran := advanced > 3.0 and advanced < 8.0 and minutes.size() >= 3 and minutes.size() <= 9
	world.follow_clock()
	var now := Time.get_time_dict_from_system()
	var pc := float(now.hour) + float(now.minute) / 60.0
	var gap := absf(world.hours - pc)
	var follows := world.follow_system_clock and world.is_processing() and minf(gap, 24.0 - gap) < 0.05
	var followed := world.hours
	world.set_time(22.0, 0.0)
	# follow_clock() also took the PC's date.
	world.set_date(10, 5, 2.0)
	_check("world_clock_fixed_for_tests", fixed, "%.2f h, running %s" % [world.hours, world.is_processing()])
	_check("world_clock_runs", ran, "%.1f game minutes in 0.5 s at 600x, %d announcements (1 + one per minute)" % [advanced, minutes.size()])
	_check("world_clock_follows_pc", follows, "%.3f h, PC %.3f h" % [followed, pc])


## The sun on the tests' date (Oct 5, UTC+2, 48° N 11.5° E; real values:
## up 07:16, down 18:52, 37° high): its direction follows the windows'
## facing (240°): south is ahead-left at noon, the sunset ahead-right.
func _test_world_sun() -> void:
	var world := _world()
	var rise := world.find_sun_crossing(true)
	var down := world.find_sun_crossing(false)
	world.hours = 13.05
	var noon := world.get_sun_elevation()
	var noon_dir := world.get_sun_direction()
	world.hours = down
	var set_azimuth := world.get_sun_azimuth()
	var set_dir := world.get_sun_direction()
	world.set_time(22.0, 0.0)
	_check("world_sun", absf(rise - 7.27) < 0.1 and absf(down - 18.87) < 0.1 and absf(noon - 37.2) < 1.0
			and noon_dir.x < -0.5 and noon_dir.z < 0.0 and set_azimuth > 255.0 and set_azimuth < 270.0 and set_dir.x > 0.2 and set_dir.z < -0.8,
			"rise %.2f h, set %.2f h (azimuth %.0f°, ahead-right %s), noon %.1f° ahead-left %s" % [
			rise, down, set_azimuth, set_dir.x > 0.2 and set_dir.z < -0.8, noon, noon_dir.x < -0.5 and noon_dir.z < 0.0])


## Seasons follow the date: long June evenings, short December days with the
## sun setting right in front of the windows.
func _test_world_seasons() -> void:
	var world := _world()
	world.set_date(6, 21, 2.0)
	var june := world.find_sun_crossing(false)
	world.set_date(12, 21, 1.0)
	var december := world.find_sun_crossing(false)
	world.hours = december
	var december_azimuth := world.get_sun_azimuth()
	world.set_date(10, 5, 2.0)
	world.set_time(22.0, 0.0)
	_check("world_seasons", absf(june - 21.3) < 0.15 and absf(december - 16.35) < 0.15 and absf(december_azimuth - world.facing) < 10.0,
			"sunset June 21 %.2f h, December 21 %.2f h at %.0f° (windows face %.0f°)" % [june, december, december_azimuth, world.facing])


## Weather: the clouds ease toward the weather's cover (signals at most 4 a
## second), rain brings them and its end brings back the weather before it;
## the HUD shows a sun by day when it's clear.
func _test_world_weather() -> void:
	var world := _world()
	var dn := _day_night()
	var pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var hud_mat := pane.material_override as ShaderMaterial
	world.set_time(13.0, 0.0)
	world.set_weather(WorldState.Weather.CLEAR, true)
	await _frames(2)
	var sun_glyph: int = hud_mat.get_shader_parameter("hud_weather")
	var clear_sun: float = (_main.get_node("Skyline/SkyLight") as DirectionalLight3D).light_energy
	var signals := [0]
	var count := func() -> void: signals[0] += 1
	world.weather_changed.connect(count)
	world.set_weather(WorldState.Weather.CLOUDY)
	await get_tree().create_timer(1.0).timeout
	var eased := world.clouds
	var easing := eased > 0.05 and eased < 0.5 and world.is_processing()
	world.weather_changed.disconnect(count)
	world.set_weather(WorldState.Weather.CLOUDY, true)
	await _frames(2)
	var cloudy_sun: float = (_main.get_node("Skyline/SkyLight") as DirectionalLight3D).light_energy
	var cloud_glyph: int = hud_mat.get_shader_parameter("hud_weather")
	world.set_weather(WorldState.Weather.CLEAR, true)
	world.set_rain(0.5, true)
	var rain_clouds := world.clouds
	world.set_rain(0.0, true)
	var after_rain := world.weather
	world.set_time(22.0, 0.0)
	await _frames(2)
	_check("world_weather", sun_glyph == WindowHud.Weather.SUN and cloud_glyph == WindowHud.Weather.CLOUDY and easing
			and signals[0] >= 3 and signals[0] <= 6 and cloudy_sun < clear_sun * 0.5 and dn.clouds == 0.0
			and rain_clouds == 1.0 and after_rain == WorldState.Weather.CLEAR,
			"HUD sun %s, cloud %s; clouds after 1 s %.2f (%d signals); sun %.2f clear, %.2f overcast; rain clouds %.1f, after the rain %s" % [
			sun_glyph == WindowHud.Weather.SUN, cloud_glyph == WindowHud.Weather.CLOUDY, eased, signals[0],
			clear_sun, cloudy_sun, rain_clouds, WorldState.Weather.keys()[after_rain]])


## Day lights the sky, the city and the rooms (the sun with shadows, the
## window spill), dims the city's lit windows and the room lamps (lights
## hidden, panels dark; the windowless hallway stays on), and the HUD shows
## the time; dusk tints; back at night everything is as authored (the moon
## without shadows, outside only).
func _test_day_night() -> void:
	var world := _world()
	var dn := _day_night()
	var env: Environment = (_main.get_node("Skyline/WorldEnvironment") as WorldEnvironment).environment
	var sky := env.sky.sky_material as ProceduralSkyMaterial
	var sun: DirectionalLight3D = _main.get_node("Skyline/SkyLight")
	var tower: VisualInstance3D = _main.get_node("Skyline/FarTowers").get_child(0)
	var lit: BaseMaterial3D = load("res://assets/materials/city/city_brutal_windows.tres")
	var spill: Light3D = _main.get_node("Zones/Apartment/Lighting/LivingCitySpill")
	var ceiling: Light3D = _main.get_node("Zones/Apartment/Lighting/LivingCeiling")
	var hall: Light3D = _main.get_node("Zones/Apartment/Lighting/Hall1")
	var lamp: MeshInstance3D = _main.get_node("Zones/Apartment/Living/LampDisc")
	var bath_lamp: MeshInstance3D = _main.get_node("Zones/Apartment/Bathroom/LampDisc")
	var pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var hud_mat := pane.material_override as ShaderMaterial
	var night: Array = [sky.sky_top_color, env.ambient_light_energy, sun.light_energy, lit.emission_energy_multiplier,
			spill.light_energy, spill.light_color, ceiling.light_energy, _emission(lamp), hall.light_energy]
	var night_basis := sun.global_basis

	world.set_time(13.0, 0.0)
	await _frames(2)
	var day_details := "daylight %.2f, sky %.2f (night %.2f), ambient %.2f, sun %.2f toward the sun %s, shadows on everything %s, city windows %.2f, spill %.2f, ceiling %s %.2f, lamp %.2f, bath lamp %.2f, hall %.2f, HUD %s" % [
			dn.daylight, sky.sky_top_color.v, (night[0] as Color).v, env.ambient_light_energy, sun.light_energy,
			sun.global_basis.z.dot(world.get_sun_direction()) > 0.999, sun.shadow_enabled and sun.light_cull_mask == DayNight.ALL_LAYERS and tower.layers & DayNight.LAYER_OUTSIDE != 0,
			lit.emission_energy_multiplier, spill.light_energy, ceiling.visible, ceiling.light_energy, _emission(lamp), _emission(bath_lamp),
			hall.light_energy, hud_mat.get_shader_parameter("hud_time")]
	var day_ok: bool = dn.daylight > 0.99 and sky.sky_top_color.v > (night[0] as Color).v + 0.2 and env.ambient_light_energy > float(night[1]) \
			and sun.light_energy > 1.0 and sun.global_basis.z.dot(world.get_sun_direction()) > 0.999 \
			and sun.shadow_enabled and sun.light_cull_mask == DayNight.ALL_LAYERS and tower.layers & DayNight.LAYER_OUTSIDE != 0 \
			and absf(lit.emission_energy_multiplier - float(night[3]) * dn.lit_windows_day) < 0.01 \
			and spill.light_energy > float(night[4]) * 2.0 and not ceiling.visible and ceiling.light_energy == 0.0 \
			and _emission(lamp) == 0.0 and _emission(bath_lamp) > 0.0 and hall.visible and hall.light_energy == float(night[8]) \
			and hud_mat.get_shader_parameter("hud_time") == Vector4i(1, 3, 0, 0)

	world.set_time(world.find_sun_crossing(false) - 0.1, 0.0)
	await _frames(2)
	var dusk_ok := dn.dusk > 0.5 and dn.daylight > 0.3 and dn.daylight < 0.95 and ceiling.visible and ceiling.light_energy > 0.0
	var dusk_details := "dusk %.2f, daylight %.2f, ceiling %.2f" % [dn.dusk, dn.daylight, ceiling.light_energy]

	world.set_time(22.0, 0.0)
	await _frames(2)
	var now: Array = [sky.sky_top_color, env.ambient_light_energy, sun.light_energy, lit.emission_energy_multiplier,
			spill.light_energy, spill.light_color, ceiling.light_energy, _emission(lamp), hall.light_energy]
	var back := sun.global_basis.is_equal_approx(night_basis) and ceiling.visible and not sun.shadow_enabled \
			and sun.light_cull_mask == DayNight.LAYER_OUTSIDE
	for i in night.size():
		back = back and (str(night[i]) == str(now[i]))
	_check("day_night_day", day_ok, day_details)
	_check("day_night_dusk", dusk_ok, dusk_details)
	_check("day_night_back_to_night", back, "night %s, now %s" % [night, now])


func _emission(mesh: MeshInstance3D) -> float:
	return (mesh.get_active_material(0) as BaseMaterial3D).emission_energy_multiplier


## A night costs nothing: with the clock running fast through the night,
## DayNight never updates.
func _test_day_night_idle() -> void:
	var world := _world()
	var dn := _day_night()
	var updates := [0]
	var count := func() -> void: updates[0] += 1
	dn.changed.connect(count)
	world.set_time(22.5, 3600.0)  # an hour per real second
	await get_tree().create_timer(1.0).timeout
	dn.changed.disconnect(count)
	var reached := world.hours
	world.set_time(22.0, 0.0)
	_check("day_night_idle_at_night", updates[0] == 0 and reached > 23.3, "%d updates from 22:30 to %.2f h" % [updates[0], reached])


## One light update at dusk (sky, ambient, fog, sun, city, window lights)
## takes well under a millisecond on the CPU and no GPU spike follows.
func _test_day_night_update_cost() -> void:
	var world := _world()
	var sunset := world.find_sun_crossing(false)
	world.set_time(sunset - 0.3, 0.0)
	await _frames(10)
	var quiet := await _gpu_frames(6)
	var t0 := Time.get_ticks_usec()
	world.set_time(sunset - 0.2, 0.0)
	var cpu_ms := (Time.get_ticks_usec() - t0) / 1000.0
	var update := await _gpu_frames(6)
	world.set_time(22.0, 0.0)
	await _frames(10)
	var quiet_max := 0.0
	for ms in quiet:
		quiet_max = maxf(quiet_max, ms)
	var spike := 0.0
	for ms in update:
		spike = maxf(spike, ms - quiet_max)
	_check("day_night_update_cost", cpu_ms < 1.0 and spike < 1.0, "CPU %.2f ms; GPU ms per frame: before %s, after %s" % [
			cpu_ms, _ms_list(quiet), _ms_list(update)])


static func _ms_list(values: PackedFloat32Array) -> String:
	var parts: PackedStringArray = []
	for ms in values:
		parts.append("%.2f" % ms)
	return ", ".join(parts)


## GPU time of the main viewport in each of the next frames (skips one).
func _gpu_frames(frames: int) -> PackedFloat32Array:
	var vp := get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	await RenderingServer.frame_post_draw
	var out: PackedFloat32Array = []
	for i in frames:
		await RenderingServer.frame_post_draw
		out.append(snappedf(RenderingServer.viewport_get_measured_render_time_gpu(vp), 0.01))
	return out


## Rain goes through the world state: the glass gets it, the HUD shows rain
## and a colder temperature.
func _test_world_rain() -> void:
	var world := _world()
	var rain: RainOnGlass = _main.get_node("Weather/RainOnGlass")
	var pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var hud_mat := pane.material_override as ShaderMaterial
	var dry_temp: int = hud_mat.get_shader_parameter("hud_temperature")
	world.set_rain(1.0, true)
	await _frames(2)
	var wet_weather: int = hud_mat.get_shader_parameter("hud_weather")
	var wet_temp: int = hud_mat.get_shader_parameter("hud_temperature")
	var glass := rain.target
	world.set_rain(0.0, true)
	await _frames(2)
	var dry_weather: int = hud_mat.get_shader_parameter("hud_weather")
	_check("world_rain", glass == 1.0 and wet_weather == WindowHud.Weather.RAIN and wet_temp == dry_temp - 3
			and dry_weather == WindowHud.Weather.CLEAR_NIGHT and rain.target == 0.0,
			"glass %.1f, HUD weather %d -> %d, %d°C -> %d°C" % [glass, wet_weather, dry_weather, dry_temp, wet_temp])


## A fingertip touch on the world terminal presses a key; the time keys
## repeat while the finger stays; the header follows.
func _test_world_terminal_touch() -> void:
	var world := _world()
	var terminal: WorldTerminal = _main.get_node("Zones/Apartment/Props/WorldTerminal")
	var area := terminal.get_key_area("min_fwd")
	var tip := _dummy_fingertip()
	tip.global_position = area.global_position + area.global_basis.z * 0.2
	await _frames(2)
	tip.global_position = area.global_position
	await _frames(3)
	var once := roundi((world.hours - 22.0) * 60.0)
	await get_tree().create_timer(0.8).timeout
	tip.global_position = area.global_position + area.global_basis.z * 0.2
	await _frames(3)
	var held := roundi((world.hours - 22.0) * 60.0)
	var header := terminal.get_header()
	await get_tree().create_timer(0.3).timeout
	var after := roundi((world.hours - 22.0) * 60.0)
	tip.queue_free()
	world.set_time(22.0, 0.0)
	_check("world_terminal_touch", once == 10 and held >= 30 and held <= 60 and after == held and header[0] == "22:%02d" % held,
			"+10 min: %d min after the touch, %d after holding 0.8 s, %d after letting go; header %s" % [once, held, after, header])


## Every key of the world terminal does what it says.
func _test_world_terminal_keys() -> void:
	var world := _world()
	var terminal: WorldTerminal = _main.get_node("Zones/Apartment/Props/WorldTerminal")
	var fails: Array[String] = []
	var expect := func(key: String, ok: bool) -> void:
		if not ok:
			fails.append(key)
	terminal.press("hour_fwd")
	expect.call("hour_fwd", is_equal_approx(world.hours, 23.0))
	terminal.press("hour_back")
	terminal.press("min_back")
	expect.call("min_back", is_equal_approx(world.hours, 22.0 - 10.0 / 60.0))
	terminal.press("sunrise")
	expect.call("sunrise", is_equal_approx(world.hours, world.find_sun_crossing(true)))
	terminal.press("noon")
	expect.call("noon", absf(world.hours - 13.03) < 0.1)
	terminal.press("sunset")
	expect.call("sunset", is_equal_approx(world.hours, world.find_sun_crossing(false) - 0.25))
	terminal.press("x60")
	expect.call("x60", world.speed == 60.0 and not world.follow_system_clock and terminal.get_header()[3] == "×60")
	terminal.press("x600")
	expect.call("x600", world.speed == 600.0)
	terminal.press("x1")
	expect.call("x1", world.speed == 1.0)
	terminal.press("pause")
	expect.call("pause", world.speed == 0.0 and terminal.get_header()[3] == "PAUSED")
	terminal.press("cloudy")
	expect.call("cloudy", world.weather == WorldState.Weather.CLOUDY)
	terminal.press("rain_more")
	terminal.press("rain_more")
	expect.call("rain_more", is_equal_approx(world.rain, 0.4) and terminal.get_header()[2].begins_with("RAIN 40 %"))
	terminal.press("rain_less")
	expect.call("rain_less", is_equal_approx(world.rain, 0.2))
	terminal.press("clear")
	expect.call("clear", world.rain == 0.0 and world.weather == WorldState.Weather.CLEAR)
	terminal.press("day_fwd")
	expect.call("day_fwd", world.get_month_day() == Vector2i(10, 6))
	terminal.press("day_back")
	terminal.press("month_back")
	expect.call("month_back", world.get_month_day() == Vector2i(9, 5) and terminal.get_header()[1] == "05 SEP")
	terminal.press("month_fwd")
	terminal.press("month_fwd")
	expect.call("month_fwd", world.get_month_day() == Vector2i(11, 5))
	terminal.press("now")
	expect.call("now", world.follow_system_clock and terminal.get_header()[3] == "LIVE")
	world.set_weather(WorldState.Weather.CLEAR, true)
	world.set_date(10, 5, 2.0)
	world.set_time(22.0, 0.0)
	await _frames(2)
	_check("world_terminal_keys", fails.is_empty(), "%d keys checked, wrong: %s" % [WorldTerminal.KEYS.size(), fails])


## The controller ray finds every fingertip button, snaps to a key it
## passes near, can't see through walls, highlights what it points at, and
## presses like a fingertip: the world terminal's keys and XR Tools buttons
## (D-054).
func _test_ray_buttons() -> void:
	var world := _world()
	var ray: GrabRay = _main.get_node("Player/RightHand/CollisionHand/FunctionPickup/GrabRay")
	var terminal: WorldTerminal = _main.get_node("Zones/Apartment/Props/WorldTerminal")
	var targets := RayButtons.targets(get_tree())
	var noon := terminal.get_key_area("noon")
	var panel_button: XRToolsInteractableAreaButton = null
	for area in targets:
		if area is XRToolsInteractableAreaButton and str(area.get_path()).contains("LivingWindow"):
			panel_button = area
			break
	var found := targets.size() >= 20 and targets.has(noon) and panel_button != null

	var forward := -noon.global_basis.z
	var origin := noon.global_position - forward * 2.0
	var exact := ray.find_button(origin, forward)
	var side := forward.rotated(noon.global_basis.y, deg_to_rad(1.45))
	var snapped := ray.find_button(origin, side)
	var through_wall := ray.find_button(Vector3(-5.0, 1.4, -1.0), (noon.global_position - Vector3(-5.0, 1.4, -1.0)).normalized())
	var aim_ok: bool = exact.get("area") == noon and exact.get("exact", false) \
			and snapped.get("area") == noon and not snapped.get("exact", true) and through_wall.is_empty()

	ray._set_button(noon, exact["point"])
	var hovered: bool = terminal.get("_hovered") == "noon"
	ray._set_button(null, Vector3.ZERO)
	var unhovered: bool = terminal.get("_hovered") == ""
	ray.press_button(noon, exact["point"])
	ray.release_button()
	var pressed_noon := absf(world.hours - 13.03) < 0.1

	var panel_hit := ray.find_button(panel_button.global_position + panel_button.global_basis.z * 1.5, -panel_button.global_basis.z)
	var states: Array[bool] = []
	var count := [0]
	var on_press := func(_b: Variant) -> void: count[0] += 1
	panel_button.button_pressed.connect(on_press)
	ray.press_button(panel_button, panel_button.global_position)
	states.append(panel_button.pressed)
	ray.release_button()
	states.append(panel_button.pressed)
	panel_button.button_pressed.disconnect(on_press)
	await _frames(2)
	# The press moved a shade or changed the tint: put the window back.
	ray.press_button(panel_button, panel_button.global_position)
	ray.release_button()
	world.set_time(22.0, 0.0)
	await _frames(30)
	_check("ray_buttons", found and aim_ok and hovered and unhovered and pressed_noon and panel_hit.get("area") == panel_button
			and states == [true, false] and count[0] == 1,
			"%d targets (terminal keys, %s); exact %s, near miss snaps %s, through a wall %s; hover %s/%s; NOON pressed %s; panel button aimed %s, pressed/released %s" % [
			targets.size(), panel_button.get_path().get_concatenated_names().get_slice("/", 6) if panel_button else "no panel button",
			exact.get("exact", false), snapped.get("area") == noon, not through_wall.is_empty(), hovered, unhovered,
			pressed_noon, panel_hit.get("area") == panel_button, states])


## Re-capturing the probes renders them again: a few frames in UPDATE_ALWAYS
## (property changes don't re-render an UPDATE_ONCE probe), then back to ONCE.
## The GPU time of those frames is in the details.
func _test_probe_recapture() -> void:
	var daylight: InteriorDaylight = _main.get_node("Zones/Apartment/Lighting/Daylight")
	var quiet := await _gpu_ms(8)
	daylight.recapture_probes()
	var during := daylight.probes.all(func(p: ReflectionProbe) -> bool: return p.update_mode == ReflectionProbe.UPDATE_ALWAYS)
	var busy := await _gpu_ms(8)
	await _frames(4)
	var after := not daylight.is_recapturing() and not daylight.is_processing() \
			and daylight.probes.all(func(p: ReflectionProbe) -> bool: return p.update_mode == ReflectionProbe.UPDATE_ONCE)
	_check("probe_recapture", during and after, "%d probes always while re-capturing %s, back to once %s; GPU %.2f ms per frame before, %.2f during" % [
			daylight.probes.size(), during, after, quiet, busy])


## Mean GPU time of the main viewport over the next frames.
func _gpu_ms(frames: int) -> float:
	var total := 0.0
	for ms in await _gpu_frames(frames):
		total += ms
	return total / frames
