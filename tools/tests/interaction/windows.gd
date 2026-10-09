extends "res://tools/tests/interaction/base.gd"
## Windows group: vent, shades, tint, HUD, glass collision, rain on the glass.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["window_vent", _test_window_vent],
		["window_shade", _test_window_shade],
		["window_tint", _test_window_tint],
		["window_hud", _test_window_hud],
		["window_glass", _test_window_glass_collision],
		["rain_wetness", _test_rain_wetness],
	]


## Waits (up to 300 physics frames) until the shade stops.
func _wait_shade(shade: MotorizedShade) -> void:
	for i in 300:
		if not shade.is_moving():
			return
		await get_tree().physics_frame


## The bedroom tilt vent: stops at its limits, its collision follows it,
## the latch pulls it shut near closed, and the city gets louder with the angle.
func _test_window_vent() -> void:
	var win: Node3D = _main.get_node(WINDOWS + "BedroomWindow")
	var hinge: XRToolsInteractableHinge = win.get_node("Vent/HingeOrigin/InteractableHinge")
	var leaf: Node3D = win.get_node("Vent/HingeOrigin/InteractableHinge/Leaf")
	var body: PhysicsBody3D = win.get_node("Vent/HingeOrigin/InteractableHinge/Leaf/DoorBody")
	var ambience: HingeAmbience = win.get_node("Ambience")
	var space := _main.get_world_3d().direct_space_state

	_move_hinge(hinge, 30.0)
	var at_max := hinge.hinge_position
	_move_hinge(hinge, -20.0)
	var at_min := hinge.hinge_position
	_check("window_vent_limits", absf(at_max - hinge.hinge_limit_max) < 0.01 and absf(at_min) < 0.01,
			"pushed to 30° stops at %.1f° (limit %.1f°), to -20° at %.1f°" % [at_max, hinge.hinge_limit_max, at_min])

	# Near the sash top, inside its collision box.
	var top := Vector3(0, 1.75, -0.035)
	await _frames(3)
	var query := PhysicsPointQueryParameters3D.new()
	var hits := func(p: Vector3) -> bool:
		query.position = p
		return space.intersect_point(query).any(func(hit: Dictionary) -> bool: return hit.collider == body)
	var closed_spot := leaf.global_transform * top
	var closed_hit: bool = hits.call(closed_spot)
	_move_hinge(hinge, hinge.hinge_limit_max)
	await _frames(3)
	var open_spot := leaf.global_transform * top
	var open_hit: bool = hits.call(open_spot)
	var left_closed: bool = not hits.call(closed_spot)
	_check("window_vent_collision", closed_hit and open_hit and left_closed and open_spot.z > closed_spot.z + 0.2,
			"sash top collision closed %s, follows the tilt %s (%.2f m into the room), left its closed spot %s" % [
				closed_hit, open_hit, open_spot.z - closed_spot.z, left_closed])

	var loud_open := ambience.volume_db
	var playing_open := ambience.playing
	_move_hinge(hinge, 2.0)
	var quiet := ambience.volume_db
	# Released at 2° the latch pulls it shut; at 6° it stays.
	hinge.released.emit(hinge)
	await _frames(60)
	var latched := hinge.hinge_position
	var silent := not ambience.playing
	_move_hinge(hinge, 6.0)
	hinge.released.emit(hinge)
	await _frames(60)
	var stayed := hinge.hinge_position
	_move_hinge(hinge, 0.0)
	await _frames(2)
	_check("window_vent_latch", latched < 0.01 and absf(stayed - 6.0) < 0.5,
			"released at 2° ends at %.2f°, at 6° stays at %.2f°" % [latched, stayed])
	_check("window_vent_ambience", playing_open and loud_open > quiet + 6.0 and silent,
			"city noise open %.1f dB (playing %s), at 2° %.1f dB, silent once latched %s" % [loud_open, playing_open, quiet, silent])


## The living room shade button runs all three shades down and back up, a
## press mid-travel stops them and the next one reverses; the city spill
## light dims while they are down.
func _test_window_shade() -> void:
	var win: Node3D = _main.get_node(WINDOWS + "LivingWindow")
	var shade: MotorizedShade = win.get_node("Shade")
	var button: Node3D = win.get_node("Panel/ShadeButton")
	var spill: Light3D = _main.get_node("Zones/Apartment/Lighting/LivingCitySpill")
	var window_light: WindowLight = _main.get_node("Zones/Apartment/Lighting/LivingWindowLight")
	var fabric: MeshInstance3D = win.get_node("Shade1/Fabric")
	var bars: Array[Node3D] = []
	for i in 3:
		bars.append(win.get_node("Shade%d/Bar" % i))
	var saved_travel := shade.travel_time
	var saved_ramp := shade.ramp_time
	shade.travel_time = 1.5
	shade.ramp_time = 0.3
	var base := window_light.get_base_energy()

	await _press(button)
	await _frames(45)
	var mid := shade.get_closure()
	var moving := shade.is_moving()
	await _wait_shade(shade)
	var down := shade.get_closure()
	var bar_drops: Array[String] = []
	var bars_ok := true
	for i in bars.size():
		bars_ok = bars_ok and absf(-bars[i].position.y - shade.drops[i]) < 0.005
		bar_drops.append("%.2f" % -bars[i].position.y)
	var dark := spill.light_energy
	_check("window_shade_down", moving and mid > 0.02 and mid < 0.98 and down == 1.0 and bars_ok and fabric.visible
			and absf(fabric.scale.y - shade.drops[1]) < 0.005,
			"after 0.5 s closure %.2f (moving %s), ended at %.2f, bars down %s m, fabric %.2f m" % [
				mid, moving, down, ", ".join(bar_drops), fabric.scale.y])
	_check("window_shade_dims_spill", dark < base * 0.1, "spill light %.2f with the shades down (open %.2f)" % [dark, base])

	# Up, stopped mid-travel; the next press sends it back down, then all the way up.
	await _press(button)
	await _frames(45)
	await _press(button)
	await _frames(60)
	var stopped_at := shade.get_closure()
	var stopped := not shade.is_moving()
	await _press(button)
	await _wait_shade(shade)
	var reversed := shade.get_closure()
	await _press(button)
	await _wait_shade(shade)
	var up := shade.get_closure()
	_check("window_shade_stop_reverse", stopped and stopped_at > 0.05 and stopped_at < 0.95 and reversed == 1.0
			and up == 0.0 and not fabric.visible and absf(spill.light_energy - base) < 0.001,
			"stopped at %.2f (%s), next press went down to %.2f, then up to %.2f; spill back to %.2f" % [
				stopped_at, stopped, reversed, up, spill.light_energy])
	shade.travel_time = saved_travel
	shade.ramp_time = saved_ramp


## The living room tint button steps its glass clear -> 0.5 -> 0.9 -> clear
## with a fade, only in that room, and dims the spill light with it.
func _test_window_tint() -> void:
	var win: Node3D = _main.get_node(WINDOWS + "LivingWindow")
	var glass: SmartGlass = win.get_node("SmartGlass")
	var button: Node3D = win.get_node("Panel/TintButton")
	var pane: GeometryInstance3D = win.get_node("Glass0")
	var bedroom_pane: GeometryInstance3D = _main.get_node(WINDOWS + "BedroomWindow/Glass0")
	var spill: Light3D = _main.get_node("Zones/Apartment/Lighting/LivingCitySpill")
	var base := (_main.get_node("Zones/Apartment/Lighting/LivingWindowLight") as WindowLight).get_base_energy()
	var mat := pane.material_override as ShaderMaterial
	var steps: Array[String] = []
	var energies: Array[float] = []
	await _press(button)
	await _frames(20)
	var fading := glass.tint > 0.01 and glass.tint < 0.49
	for i in 3:
		if i > 0:
			await _press(button)
		await _frames(150)
		var value: float = mat.get_shader_parameter("tint")
		steps.append("%.2f" % value)
		energies.append(spill.light_energy)
	var bedroom_tint: Variant = (bedroom_pane.material_override as ShaderMaterial).get_shader_parameter("tint")
	var others_clear := bedroom_tint == null or absf(float(bedroom_tint)) < 0.001
	var energy_text: Array[String] = []
	for e in energies:
		energy_text.append("%.2f" % e)
	_check("window_tint_steps", fading and steps == ["0.50", "0.90", "0.00"] and others_clear
			and bedroom_pane.material_override != pane.material_override,
			"fading after 0.2 s %s, tint after each press %s, bedroom glass still clear %s" % [fading, steps, others_clear])
	_check("window_tint_dims_spill", energies[0] < base * 0.7 and energies[1] < energies[0] * 0.6
			and absf(energies[2] - base) < 0.001,
			"spill light %.2f clear, %s at 0.5 / 0.9 / clear" % [base, ", ".join(energy_text)])


## The living room HUD shows the world's time (tests: fixed at 22:00), on its east pane only.
func _test_window_hud() -> void:
	var hud: WindowHud = _main.get_node(WINDOWS + "LivingWindow/Hud")
	var pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var other: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass0")
	hud.refresh()
	var state := _world().get_hud_state()
	var shown: Vector4i = (pane.material_override as ShaderMaterial).get_shader_parameter("hud_time")
	var hour: int = state.hour
	var minute: int = state.minute
	var expect := Vector4i(hour / 10, hour % 10, minute / 10, minute % 10)
	var enabled: bool = pane.get_instance_shader_parameter("hud_enabled")
	var other_value: Variant = other.get_instance_shader_parameter("hud_enabled")
	var other_off := other_value == null or not bool(other_value)
	_check("window_hud_time", shown == expect and expect == Vector4i(2, 2, 0, 0) and enabled and other_off,
			"hud_time %s, world %s, on the east pane only %s" % [shown, expect, enabled and other_off])


## Window glass is solid: a ball thrown at each pane bounces back, a body-sized
## capsule stops at the glass, and the player walking into the living room
## floor-to-ceiling window stays inside.
func _test_window_glass_collision() -> void:
	var space := _main.get_world_3d().direct_space_state
	var results: Array[String] = []
	var ok := true
	# Pane centers (x, y) per window; the bedroom bay 1 is the closed vent.
	for target: Array in [["LivingWindow", Vector2(-1.65, 1.2)], ["LivingWindow", Vector2(1.65, 1.2)],
			["BedroomWindow", Vector2(-5.64, 1.4)], ["BedroomWindow", Vector2(-4.36, 1.4)],
			["KitchenWindow", Vector2(4.55, 1.6)]]:
		var xy: Vector2 = target[1]
		var ball: RigidBody3D = (load("res://assets/props/ball/ball.tscn") as PackedScene).instantiate()
		_main.add_child(ball)
		ball.global_position = Vector3(xy.x, xy.y, -2.4)
		ball.linear_velocity = Vector3(0, 0, -12.0)
		await _frames(45)
		var z := ball.global_position.z
		ball.queue_free()
		ok = ok and z > -3.1
		results.append("%s x %.2f: z %.2f" % [target[0], xy.x, z])
	_check("window_glass_stops_balls", ok, "thrown at 12 m/s, balls end at " + ", ".join(results))

	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.2
	capsule.height = 1.6
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = 1
	query.transform = Transform3D(Basis.IDENTITY, Vector3(1.65, 0.95, -2.6))
	query.motion = Vector3(0, 0, -1.2)
	var fraction := space.cast_motion(query)[0]
	var stop_z := -2.6 - 1.2 * fraction - capsule.radius
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	var mix: float = body.body_forward_mix
	body.body_forward_mix = 0.0
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(1.65, 0, -2.2)))
	await _frames(30)
	var walker := _ForwardInput.new()
	walker.add_to_group("movement_providers")
	body.add_child(walker)
	body._movement_providers.append(walker)
	await _frames(120)
	body._movement_providers.erase(walker)
	walker.queue_free()
	var player_z := body.global_position.z
	body.body_forward_mix = mix
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4)))
	await _frames(30)
	_check("window_glass_stops_player", fraction < 1.0 and stop_z > -3.17 and player_z > -3.1,
			"capsule front stops at z %.2f (glass -3.15), player walking into the window ends at z %.2f" % [
				stop_z, player_z])


func _rain_materials() -> Array[ShaderMaterial]:
	var out: Array[ShaderMaterial] = []
	for node in get_tree().get_nodes_in_group(RainOnGlass.GROUP_GLASS):
		var mat := (node as GeometryInstance3D).material_override as ShaderMaterial
		if mat and not out.has(mat):
			out.append(mat)
	return out


## Every window material is in the shader's early-out state (rain 0, dry).
func _rain_uniforms_dry() -> bool:
	for mat in _rain_materials():
		var amount: Variant = mat.get_shader_parameter("rain_amount")
		var wet: Variant = mat.get_shader_parameter("rain_wet")
		if (amount != null and float(amount) != 0.0) or (wet != null and float(wet) != 0.0):
			return false
	return true


## Wetness lags behind the rain; after the rain stops the runners stop first,
## then the beads dry off; patter and the vent rain follow; fully dry, every
## window material is back at the early-out state and RainOnGlass idles.
## Runs 10x faster (time_scale).
func _test_rain_wetness() -> void:
	var rain: RainOnGlass = _main.get_node("Weather/RainOnGlass")
	var hinge: XRToolsInteractableHinge = _main.get_node(WINDOWS + "BedroomWindow/Vent/HingeOrigin/InteractableHinge")
	var patter: AudioStreamPlayer3D = _main.get_node(WINDOWS + "LivingWindow/RainPatter")
	var outside: HingeAmbience = _main.get_node(WINDOWS + "BedroomWindow/RainAmbience")
	var mats := _rain_materials()
	rain.set_rain(0.0, true)
	await _frames(2)
	var dry_at_start := _rain_uniforms_dry() and not rain.is_processing() and not rain.is_wet_shader()
	var living_glass: SmartGlass = _main.get_node(WINDOWS + "LivingWindow/SmartGlass")
	living_glass.set_tint(0.5)
	var saved := rain.time_scale
	rain.time_scale = 10.0
	_move_hinge(hinge, hinge.hinge_limit_max)

	rain.set_rain(1.0)
	await _frames(3)
	var early := "amount %.2f wet %.2f" % [rain.amount, rain.wetness]
	var early_ok := rain.amount < 0.3 and rain.wetness < 0.2
	await _frames(270)
	var full_ok := rain.amount > 0.99 and rain.wetness > 0.95 and rain.slide > 0.9
	var shader_wet: float = mats[0].get_shader_parameter("rain_wet")
	# Three apartment windows and the corridor's (streamed in, D-059).
	var shader_ok := mats.size() == 4 and absf(shader_wet - rain.wetness) < 0.001
	var full := "amount %.2f wet %.2f slide %.2f" % [rain.amount, rain.wetness, rain.slide]
	var hud_pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var hud_mat := hud_pane.material_override as ShaderMaterial
	var kept_tint: float = hud_mat.get_shader_parameter("tint")
	var kept_hud: bool = hud_pane.get_instance_shader_parameter("hud_enabled")
	var swap_ok := rain.is_wet_shader() and hud_mat.shader == RainOnGlass.WET_SHADER and absf(kept_tint - 0.5) < 0.001 			and kept_hud and hud_mat.get_shader_parameter("hud_time") != null
	living_glass.set_tint(0.0)
	_check("rain_wetness_lags", dry_at_start and early_ok and full_ok and shader_ok,
			"dry at start %s; 0.3 s of rain: %s; 30 s: %s; %d window materials, rain_wet %.2f" % [
				dry_at_start, early, full, mats.size(), shader_wet])
	_check("rain_wet_shader", swap_ok, "wet shader while raining %s; tint %.2f and the HUD kept across the swap" % [
			rain.is_wet_shader(), kept_tint])
	var patter_db := patter.volume_db
	var sounds_on := patter.playing and outside.playing
	var outside_open_db := outside.volume_db
	_move_hinge(hinge, 2.0)
	var outside_tilted_db := outside.volume_db

	rain.set_rain(0.0)
	await _frames(90)
	var after := "slide %.2f wet %.2f, patter %.1f dB (full %.1f)" % [rain.slide, rain.wetness, patter.volume_db, patter_db]
	var stops_first := rain.slide < 0.01 and rain.wetness > 0.5 and patter.volume_db < patter_db - 12.0
	for i in 1200:
		if not rain.is_processing():
			break
		await get_tree().physics_frame
	var dried := rain.is_dry() and not rain.is_processing() and _rain_uniforms_dry() and not rain.is_wet_shader() 			and mats[0].shader == RainOnGlass.DRY_SHADER
	var sounds_off := not patter.playing and not outside.playing
	rain.time_scale = saved
	_move_hinge(hinge, 0.0)
	await _frames(2)
	_check("rain_dries_after", stops_first and dried,
			"10 s after the rain: %s; later dry, idle and every material at the early-out state %s" % [after, dried])
	_check("rain_sounds_follow", sounds_on and outside_open_db > outside_tilted_db + 6.0 and sounds_off,
			"raining: patter and vent rain playing %s, vent rain open %.1f dB, nearly shut %.1f dB; dry: silent %s" % [
				sounds_on, outside_open_db, outside_tilted_db, sounds_off])
