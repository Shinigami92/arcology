extends "res://tools/tests/interaction/base.gd"
## Zones group: streaming, gates, unloading, visibility, rain and reflections in streamed zones, wayfinding, units.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["zone_streamed", _test_zone_streamed],
		["zone_follows_player", _test_zone_follows_player],
		["zone_gate", _test_zone_gate],
		["zone_unload_far", _test_zone_unload_far],
		["zone_reflection_warm", _test_zone_reflection_warm],
		["zone_rain", _test_zone_rain],
		["zone_drawn_when_seen", _test_zone_drawn_when_seen],
		["corridor_wayfinding", _test_corridor_wayfinding],
		["unit_approach", _test_unit_approach],
		["unit_plates", _test_unit_plates],
		["unit_scenes", _test_unit_scenes],
		["unit_unload_ray", _test_unit_unload_ray],
	]


## The corridor streams in next to the apartment (D-059): under Zones, named
## after its id, one connection from the player's zone (the apartment).
func _test_zone_streamed() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var corridor := streamer.get_zone(&"corridor")
	_check("zone_streamed", streamer.current == &"apartment" and corridor != null and corridor.get_parent() == streamer
			and corridor.name == "Corridor" and streamer.distance_to(&"corridor") == 1 and streamer.is_settled(),
			"current %s, corridor %s, distance %d, settled %s, loaded in %.0f ms" % [streamer.current,
				corridor.get_path() if corridor else ^"", streamer.distance_to(&"corridor"), streamer.is_settled(),
				streamer.get_load_ms(&"corridor")])


## The zones' Bounds follow the player body: in the corridor the player's
## zone is the corridor, back home the apartment.
func _test_zone_follows_player() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(7.7, 0, 0.0)))
	await _frames(30)
	var in_corridor := streamer.current
	var apartment_kept := streamer.is_ready(&"apartment")
	# Against the closed entrance door: the capsule reaches into the apartment's bounds, the
	# player is still in the corridor (headset bug 2026-10-08: the corridor vanished).
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(6.72, 0, 2.9)))
	await _frames(30)
	var at_door := streamer.current
	var corridor_drawn := streamer.is_shown(&"corridor")
	body.teleport(HOME)
	await _frames(30)
	var home := streamer.current
	_check("zone_follows_player", in_corridor == &"corridor" and apartment_kept and at_door == &"corridor"
			and corridor_drawn and home == &"apartment",
			"in the corridor: %s (apartment still loaded %s); against the closed door: %s, corridor drawn %s; home: %s" % [
				in_corridor, apartment_kept, at_door, corridor_drawn, home])


## While the corridor loads, the entrance door's ZoneGate holds the door shut
## through its DoorLock (lever rattles, LED pulses amber); loaded, it opens.
func _test_zone_gate() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var gate: ZoneGate = _main.get_node(PROPS + "DoorEntrance/ZoneGate")
	var lock: DoorLock = _main.get_node(PROPS + "DoorEntrance/Lock")
	var door := _hinge("DoorEntrance")
	var open_before := not gate.is_holding()
	streamer.reload(&"corridor")
	await get_tree().process_frame
	await get_tree().process_frame
	var holding := gate.is_holding() and lock.is_held()
	_set_hinge("DoorEntrance", 40.0)
	var held_at := door.hinge_position
	var led: BaseMaterial3D = lock._leds[0]
	var pulse := led.emission
	var amber := pulse.r > 3.0 * pulse.b and pulse.g > 2.0 * pulse.b
	await streamer.wait_settled()
	await get_tree().process_frame
	var released := not gate.is_holding() and not lock.is_held()
	_set_hinge("DoorEntrance", 40.0)
	var opens := door.hinge_position
	_set_hinge("DoorEntrance", 0.0)
	var cyan := led.emission.b > 0.5 and led.emission.r < 0.2
	await _frames(3)
	_check("zone_gate", open_before and holding and held_at == 0.0 and amber and released and opens == 40.0 and cyan,
			"open before %s; reloading: held %s, pulled to 40° stays at %.1f°, LED amber %s (%s); loaded: released %s, opens to %.1f°, LED cyan %s" % [
				open_before, holding, held_at, amber, pulse, released, opens, cyan])


## A zone two connections away isn't loaded; it streams in when the player's
## zone moves next to it and is freed when it moves away again.
func _test_zone_unload_far() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	streamer.add_zone(&"probe", "res://tools/tests/zones/test_zone.tscn")
	streamer.add_connection(&"corridor", &"probe")
	await get_tree().process_frame
	var far := streamer.is_ready(&"probe") or streamer.is_loading(&"probe")
	streamer.set_current(&"corridor")
	await streamer.wait_settled()
	var probe := streamer.get_zone(&"probe")
	var near := probe != null and probe.get_parent() == streamer and probe.name == "Probe"
	var kept := streamer.is_ready(&"apartment")
	streamer.set_current(&"apartment")
	await get_tree().process_frame
	await get_tree().process_frame
	var freed := not streamer.is_ready(&"probe") and not is_instance_valid(probe)
	var corridor_kept := streamer.is_ready(&"corridor")
	streamer.remove_zone(&"probe")
	_check("zone_unload_far", not far and near and kept and freed and corridor_kept,
			"2 away: loaded %s; 1 away: loaded %s (apartment kept %s); 2 away again: freed %s (corridor kept %s)" % [
				far, near, kept, freed, corridor_kept])


## A window in a streamed zone warms its reflection plane once it's loaded
## (D-057, D-059), here with the player looking away from the windows.
func _test_zone_reflection_warm() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	body.teleport(Transform3D(Basis(Vector3.UP, PI), HOME.origin))
	await _frames(10)
	streamer.reload(&"corridor")
	await streamer.wait_settled()
	var reflection: PlanarReflection = streamer.get_zone(&"corridor").get_node("Windows/EndWindow/Reflection")
	var pending_at_load := reflection._warm_pending
	for i in 5:
		await get_tree().process_frame
	_check("zone_reflection_warm", pending_at_load and not reflection._warm_pending,
			"pending when loaded %s, after 5 frames %s" % [pending_at_load, reflection._warm_pending])


## A zone the player isn't in is drawn only while it can be seen: through the
## open entrance door or the peephole. From the corridor, the apartment.
func _test_zone_drawn_when_seen() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var viewer: DoorViewer = _main.get_node(PROPS + "DoorEntrance/HingeOrigin/InteractableHinge/Leaf/Peephole")
	# Past a fresh load's reveal frames (earlier tests reload the corridor).
	for i in ZoneStreamer.REVEAL_FRAMES + 1:
		await RenderingServer.frame_post_draw
	var hidden := not streamer.is_shown(&"corridor") and streamer.is_ready(&"corridor")
	_set_hinge("DoorEntrance", 30.0)
	var open_shows := streamer.is_shown(&"corridor")
	_set_hinge("DoorEntrance", 0.0)
	var closed_hides := not streamer.is_shown(&"corridor")
	# An eye at the lens (apartment side, 10 cm in front).
	var cam := Camera3D.new()
	_main.add_child(cam)
	var saved := PlanarReflection.view_camera
	PlanarReflection.view_camera = cam
	cam.global_position = viewer.to_global(Vector3(0, 0, 0.1))
	viewer.check_eye()
	var peek_shows := streamer.is_shown(&"corridor")
	cam.global_position = viewer.to_global(Vector3(0, 0, 1.5))
	viewer.check_eye()
	var peek_ends := not streamer.is_shown(&"corridor")
	PlanarReflection.view_camera = saved
	cam.queue_free()
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(7.7, 0, 0.0)))
	await _frames(30)
	var from_corridor := streamer.is_shown(&"corridor") and not streamer.is_shown(&"apartment")
	# The apartment's door stays: the corridor sees it too (headset bug 2026-10-08: it vanished).
	var door_drawn := (_main.get_node(PROPS + "DoorEntrance") as Node3D).is_visible_in_tree()
	var rest_hidden := not (_main.get_node(PROPS + "Fridge") as Node3D).is_visible_in_tree() \
			and not (_main.get_node("Zones/Apartment/Lighting") as Node3D).is_visible_in_tree()
	body.teleport(HOME)
	await _frames(30)
	var home := streamer.is_shown(&"apartment") and not streamer.is_shown(&"corridor")
	var all_back := (_main.get_node(PROPS + "Fridge") as Node3D).is_visible_in_tree()
	_check("zone_drawn_when_seen", hidden and open_shows and closed_hides and peek_shows and peek_ends and from_corridor
			and door_drawn and rest_hidden and home and all_back,
			"door closed: corridor hidden %s; open: shown %s; closed: hidden %s; peephole: shown %s, after: hidden %s; in the corridor: apartment hidden %s, its entrance door still drawn %s, the rest hidden %s; home: corridor hidden %s, apartment all back %s" % [
				hidden, open_shows, closed_hides, peek_shows, peek_ends, from_corridor, door_drawn, rest_hidden, home, all_back])


## The corridor's holographic signs are built (panel and text, chevrons where
## they point) and their shader compiled; the floor guide lights pulse toward
## the elevators (D-060).
func _test_corridor_wayfinding() -> void:
	var corridor := ZoneStreamer.find(get_tree()).get_zone(&"corridor")
	var signs: Array[Node] = corridor.find_children("*", "HoloSign", true, false)
	var broken: Array[String] = []
	var arrows := 0
	for node in signs:
		var sign := node as HoloSign
		var panel := sign.get_child(0, true) as MeshInstance3D
		var label := sign.get_child(1, true) as Label3D
		var mat := panel.material_override as ShaderMaterial if panel else null
		# A shader that fails to compile has no uniforms (door_viewer learned this the hard way).
		if not panel or not label or label.text.is_empty() or not mat or mat.shader.get_shader_uniform_list().is_empty():
			broken.append(str(sign.name))
		elif mat.get_shader_parameter("arrow") != 0.0:
			arrows += 1
	var strips: Array[Node] = corridor.get_node("Guidance").get_children()
	var toward := 0
	for strip: MeshInstance3D in strips:
		var flow: Vector3 = strip.get_instance_shader_parameter("flow")
		var to_lobby := Vector3(13.0, 0, 10.8) - strip.global_position
		if flow.length() > 0.99 and flow.dot(Vector3(to_lobby.x, 0, to_lobby.z)) > 0.0:
			toward += 1
	var guide_mat := (strips[0] as MeshInstance3D).mesh.surface_get_material(0) as ShaderMaterial
	var guide_ok := not guide_mat.shader.get_shader_uniform_list().is_empty()
	_check("corridor_wayfinding", signs.size() >= 8 and broken.is_empty() and arrows >= 6 and strips.size() >= 7
			and toward == strips.size() and guide_ok,
			"%d holo signs (broken: %s), %d with chevrons; %d guide strips, %d pulse toward the elevators, shader ok %s" % [
				signs.size(), broken, arrows, strips.size(), toward, guide_ok])


## A unit streams in only while the player is near its door (D-062): far down
## the corridor it isn't loaded; at the door it loads while the door shows the
## ID scan, then opens onto it; walking away frees it again.
func _test_unit_approach() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	var door_root: Node3D = streamer.get_zone(&"corridor").get_node("Props/Door4421")
	var hinge: XRToolsInteractableHinge = door_root.get_node("HingeOrigin/InteractableHinge")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(-5.0, 0, 8.2)))
	await _frames(40)
	var far := not streamer.is_ready(&"unit_4421") and not streamer.is_loading(&"unit_4421")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(6.2, 0, 8.4)))
	await _frames(25)
	var asked := streamer.is_loading(&"unit_4421") or streamer.is_ready(&"unit_4421")
	var gate: ZoneGate = door_root.get_node("ZoneGate")
	var held_while_loading := streamer.is_ready(&"unit_4421") or gate.is_holding()
	await streamer.wait_settled()
	await get_tree().process_frame
	var loaded := streamer.is_ready(&"unit_4421") and not gate.is_holding()
	# As a hand does: move_hinge() emits hinge_moved, which the ZoneGate listens to (the setter doesn't).
	hinge.hinge_position = 40.0
	hinge.hinge_moved.emit(hinge.hinge_position)
	var opens := hinge.hinge_position
	# Past the unit's reveal frames, so only the open door can keep it drawn.
	for i in 6:
		await RenderingServer.frame_post_draw
	var seen := streamer.is_shown(&"unit_4421")
	hinge.hinge_position = 0.0
	hinge.hinge_moved.emit(0.0)
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(-5.0, 0, 8.2)))
	await _frames(40)
	var freed := not streamer.is_ready(&"unit_4421")
	body.teleport(HOME)
	await _frames(30)
	_check("unit_approach", far and asked and held_while_loading and loaded and opens == 40.0 and seen and freed,
			"11 m away: not loaded %s; at the door: asked %s, held until in %s, loaded %s (%.0f ms); door opens to %.0f°, unit drawn %s; walked away: freed %s" % [
				far, asked, held_while_loading, loaded, streamer.get_load_ms(&"unit_4421"), opens, seen, freed])


## Every unit door shows its own number over the leaf's 4417 plate; ours keeps 4417.
func _test_unit_plates() -> void:
	var corridor := ZoneStreamer.find(get_tree()).get_zone(&"corridor")
	var wrong: Array[String] = []
	for n: String in ["4418", "4419", "4420", "4421", "4422", "4423", "SERVICE", "STAIRS"]:
		var door := corridor.get_node("Props/Door%s" % (n if n.is_valid_int() else n.capitalize()))
		var plates := door.find_children("UnitPlate", "", true, false)
		var label := plates[0].get_node_or_null("Number") as Label3D if not plates.is_empty() else null
		if not label or label.text != n:
			wrong.append(n)
	var ours := _main.get_node(PROPS + "DoorEntrance").find_children("UnitPlate", "", true, false)
	var ours_bare := not ours.is_empty() and ours[0].get_child_count() == 0
	_check("unit_plates", wrong.is_empty() and ours_bare, "wrong or missing: %s; our door keeps its own plate %s" % [wrong, ours_bare])


## The controller ray's button list drops a unit's buttons when the unit
## streams out (headset bug 2026-10-08: a freed button broke the ray's
## _process with a script error, which paused the game).
func _test_unit_unload_ray() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(6.2, 0, 8.4)))
	await _frames(25)
	await streamer.wait_settled()
	var unit := streamer.get_zone(&"unit_4421")
	var in_unit := 0
	for area: Area3D in unit.find_children("*", "Area3D", true, false) if unit else []:
		if area.collision_mask & RayButtons.FINGERTIP_LAYER:
			in_unit += 1
	var before := RayButtons.targets(get_tree()).size()
	body.teleport(HOME)
	await _frames(40)
	var after: Array[Area3D] = RayButtons.targets(get_tree())
	var all_valid := after.all(func(a: Variant) -> bool: return is_instance_valid(a))
	# At least the unit's buttons are gone (other units near the corridor may stream out with it).
	_check("unit_unload_ray", in_unit > 0 and not streamer.is_ready(&"unit_4421") and after.size() <= before - in_unit
			and all_valid, "unit 4421 had %d ray buttons; %d targets before, %d after it streamed out, all valid %s" % [
				in_unit, before, after.size(), all_valid])


## Every unit in the zone graph builds: its Bounds, a window looking out, the
## bathroom and the furniture, the front door's opening clear (D-062).
func _test_unit_scenes() -> void:
	var problems: Array[String] = []
	for n: String in ["4418", "4419", "4420", "4421", "4422", "4423"]:
		var scene := load("res://zones/units/unit_%s.tscn" % n) as PackedScene
		var unit := scene.instantiate() if scene else null
		if not unit:
			problems.append("%s: no scene" % n)
			continue
		for path: String in ["Bounds", "Props/Toilet", "Props/Vanity", "Props/Bed", "Props/Sofa", "Props/Fridge",
				"Props/Wardrobe", "Props/DoorBathroom", "Entries/Door", "Lighting/LivingCeiling"]:
			if not unit.has_node(path):
				problems.append("%s: no %s" % [n, path])
		var notifiers := unit.find_children("*", "VisibleOnScreenNotifier3D", true, false)
		if notifiers.is_empty() or not notifiers[0].has_meta(&"outside_facing"):
			problems.append("%s: no window notifier with outside_facing" % n)
		unit.free()
	_check("unit_scenes", problems.is_empty(), "%s" % [problems] if problems else "6 units: bounds, windows, bathroom, furniture, entry")


## A window that streams in while it rains gets the rain (RainOnGlass follows
## the zones, D-059), and its patter keeps its authored volume.
func _test_zone_rain() -> void:
	var streamer := ZoneStreamer.find(get_tree())
	var rain: RainOnGlass = _main.get_node("Weather/RainOnGlass")
	rain.set_rain(1.0, true)
	streamer.reload(&"corridor")
	await streamer.wait_settled()
	await get_tree().process_frame
	var window := streamer.get_zone(&"corridor").get_node("Windows/EndWindow")
	var mat := (window.get_node("Glass0") as GeometryInstance3D).material_override as ShaderMaterial
	var wet: float = mat.get_shader_parameter("rain_amount")
	var wet_shader := mat.shader == RainOnGlass.WET_SHADER
	var patter: AudioStreamPlayer3D = window.get_node("RainPatter")
	var playing := patter.playing
	var full_db: float = patter.get_meta(&"rain_full_db", 999.0)
	rain.refresh_targets()
	var db_kept: float = patter.get_meta(&"rain_full_db", 999.0)
	rain.set_rain(0.0, true)
	await get_tree().process_frame
	var dry: float = mat.get_shader_parameter("rain_amount")
	_check("zone_rain", is_equal_approx(wet, 1.0) and wet_shader and playing and full_db == db_kept and full_db < 0.0
			and dry == 0.0, "streamed-in glass: rain %.2f, wet shader %s, patter playing %s at %.1f dB (after a re-scan %.1f); dry again %.2f" % [
				wet, wet_shader, playing, full_db, db_kept, dry])
