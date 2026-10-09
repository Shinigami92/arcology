extends "res://tools/tests/interaction/base.gd"
## Bathroom group: mirror and magnifier, toilet, vanity, shower (controls, hand shower, hose, water, glass).


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["bath_magnifier", _test_bath_magnifier],
		["bath_mirror_touch", _test_bath_mirror_touch],
		["toilet_lid_and_seat", _test_toilet_lid_and_seat],
		["toilet_soft_close", _test_toilet_soft_close],
		["toilet_flush", _test_toilet_flush],
		["toilet_roll", _test_toilet_roll],
		["vanity_drawers", _test_vanity_drawers],
		["vanity_lever", _test_vanity_lever],
		["vanity_dispenser", _test_vanity_dispenser],
		["shower_controls", _test_shower_controls],
		["shower_hand", _test_shower_hand],
		["shower_hose", _test_shower_hose],
		["shower_water", _test_shower_water],
		["shower_glass", _test_shower_glass],
	]


## Whether a point query at `p` hits `body`.
func _hits_body(body: PhysicsBody3D, p: Vector3) -> bool:
	var query := PhysicsPointQueryParameters3D.new()
	query.position = p
	var hits := _main.get_world_3d().direct_space_state.intersect_point(query)
	return hits.any(func(hit: Dictionary) -> bool: return hit.collider == body)


## Grabs `pickable` with the left hand, carries it by `offset` over 30 frames,
## and returns how far it ended from where it started. Leaves it held.
func _carry(pickable: XRToolsPickable, offset: Vector3) -> float:
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var start := pickable.global_position
	pickup.global_transform = Transform3D(Basis.IDENTITY, start)
	pickup._pick_up_object(pickable)
	for i in 30:
		pickup.global_transform = Transform3D(Basis.IDENTITY, start + offset * (i + 1) / 30.0)
		await get_tree().physics_frame
	await _frames(10)
	return pickable.global_position.distance_to(start)


func _drop_left() -> void:
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	pickup.drop_object()


## Magnifier: swings out on its vertical pivot (0..170°), its collision
## follows, and it stays where it's let go (no momentum).
func _test_bath_magnifier() -> void:
	var root: Node3D = _main.get_node(PROPS + "BathMagnifier")
	var hinge: XRToolsInteractableHinge = root.get_node("HingeOrigin/InteractableHinge")
	var leaf: Node3D = root.get_node("HingeOrigin/InteractableHinge/Leaf")
	var body: PhysicsBody3D = leaf.get_node("DoorBody")
	var head := Vector3(0.315, 0, -0.0035)
	_move_hinge(hinge, 0.0)
	await _frames(3)
	var closed_spot := leaf.global_transform * head
	var closed_hit := _hits_body(body, closed_spot)
	_move_hinge(hinge, 90.0)
	await _frames(3)
	var open_spot := leaf.global_transform * head
	var open_hit := _hits_body(body, open_spot)
	var left_closed := not _hits_body(body, closed_spot)
	var into_room := (open_spot - closed_spot).dot(root.global_basis.z)
	hinge.released.emit(hinge)
	await _frames(30)
	var stayed := hinge.hinge_position
	_move_hinge(hinge, 200.0)
	var at_max := hinge.hinge_position
	_move_hinge(hinge, 0.0)
	await _frames(2)
	_check("bath_magnifier_swing", closed_hit and open_hit and left_closed and into_room > 0.25
			and absf(stayed - 90.0) < 0.01 and absf(at_max - 170.0) < 0.01,
			"head collision closed %s, at 90° %s (%.2f m into the room, left its folded spot %s); let go at 90° stays %.1f°, pushed past the stop %.1f°" % [
				closed_hit, open_hit, into_room, left_closed, stayed, at_max])


## The mirror's touch sensor toggles the halo (additive glow, no shadow) and
## the vanity light; the sensor ring stays dimly lit while off.
func _test_bath_mirror_touch() -> void:
	var mirror: Node3D = _main.get_node(PROPS + "BathMirror")
	var button: Node3D = mirror.get_node("HaloButton")
	var light: Light3D = mirror.get_node("VanityLight")
	var halo: MeshInstance3D = mirror.find_child("MirrorLight", true, false)
	var ring: MeshInstance3D = mirror.find_child("TouchSensor", true, false)
	if not halo or not ring:
		_check("bath_mirror_touch", false, "MirrorLight / TouchSensor mesh not found in the mirror glb")
		return
	var halo_mat := halo.get_active_material(0) as BaseMaterial3D
	var ring_mat := ring.get_active_material(0) as BaseMaterial3D
	var additive := halo_mat.blend_mode == BaseMaterial3D.BLEND_MODE_ADD and halo.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var on_before := light.visible and halo_mat.emission_energy_multiplier > 2.0
	var ring_on := ring_mat.emission_energy_multiplier
	await _press(button)
	var off := not light.visible and halo_mat.emission_energy_multiplier == 0.0
	var ring_off := ring_mat.emission_energy_multiplier
	await _press(button)
	var on_again := light.visible and halo_mat.emission_energy_multiplier > 2.0
	_check("bath_mirror_touch", additive and on_before and off and on_again and ring_off > 0.0 and ring_off < ring_on,
			"halo additive without shadow %s; on at start %s, off after a touch %s, on after another %s; ring energy on %.2f, off %.2f" % [
				additive, on_before, off, on_again, ring_on, ring_off])


## Lid and seat: the lid's collision follows it; the seat's grip only works
## (and the seat only rises) once the lid is open; the seat can't rise past
## the lid, and the lid can't close while the seat is up.
func _test_toilet_lid_and_seat() -> void:
	var t: Node3D = _main.get_node(PROPS + "Toilet")
	var lid: XRToolsInteractableHinge = t.get_node("Lid/HingeOrigin/InteractableHinge")
	var seat: XRToolsInteractableHinge = t.get_node("Seat/HingeOrigin/InteractableHinge")
	var lid_leaf: Node3D = t.get_node("Lid/HingeOrigin/InteractableHinge/Leaf")
	var lid_body: PhysicsBody3D = lid_leaf.get_node("DoorBody")
	var seat_handle: XRToolsPickable = t.get_node("Seat/HingeOrigin/InteractableHinge/Leaf/HandleOrigin/InteractableHandle")
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	_move_hinge(lid, 0.0)
	_move_hinge(seat, 0.0)
	await _frames(3)
	var box_center := Vector3(0, 0.004, 0.2317)
	var closed_spot := lid_leaf.global_transform * box_center
	var closed_hit := _hits_body(lid_body, closed_spot)
	var locked := not seat_handle.can_pick_up(pickup)
	_move_hinge(seat, 45.0)
	var seat_under_closed_lid := seat.hinge_position
	_move_hinge(lid, 90.0)
	await _frames(3)
	var open_spot := lid_leaf.global_transform * box_center
	var lid_follows := _hits_body(lid_body, open_spot) and not _hits_body(lid_body, closed_spot) and open_spot.y > closed_spot.y + 0.15
	var unlocked := seat_handle.can_pick_up(pickup)
	_check("toilet_lid_opens", closed_hit and lid_follows, "lid collision closed %s, follows it up at 90° %s" % [closed_hit, lid_follows])
	_check("toilet_seat_needs_open_lid", locked and seat_under_closed_lid < 0.01 and unlocked,
			"seat grip with the lid closed: grabbable %s, seat rises to %.1f°; with the lid at 90°: grabbable %s" % [
				not locked, seat_under_closed_lid, unlocked])

	_move_hinge(seat, 45.0)
	var seat_free := seat.hinge_position
	_move_hinge(seat, 97.0)
	var seat_at_lid := seat.hinge_position
	_move_hinge(lid, 97.0)
	_move_hinge(seat, 97.0)
	_move_hinge(lid, 20.0)
	var lid_held := lid.hinge_position
	_move_hinge(seat, 0.0)
	_move_hinge(lid, 0.0)
	await _frames(3)
	var lid_closed := lid.hinge_position
	var relocked := not seat_handle.can_pick_up(pickup)
	_check("toilet_seat_lid_order", absf(seat_free - 45.0) < 0.01 and absf(seat_at_lid - 90.0) < 0.01
			and absf(lid_held - 97.0) < 0.01 and lid_closed < 0.01 and relocked,
			"seat to 45° %.1f°, to 97° under the lid at 90° stops at %.1f°; seat up, lid pushed to 20° stays %.1f°; seat down, lid closes to %.1f° (seat locked again %s)" % [
				seat_free, seat_at_lid, lid_held, lid_closed, relocked])


## Let go below 80° the lid sinks shut slowly (soft-close); let go wide open it stays.
func _test_toilet_soft_close() -> void:
	var t: Node3D = _main.get_node(PROPS + "Toilet")
	var lid: XRToolsInteractableHinge = t.get_node("Lid/HingeOrigin/InteractableHinge")
	_move_hinge(lid, 60.0)
	lid.released.emit(lid)
	await _frames(30)
	var after_third := lid.hinge_position
	var frames := 30
	while lid.hinge_position > 0.01 and frames < 600:
		await get_tree().physics_frame
		frames += 1
	var closed := lid.hinge_position
	_move_hinge(lid, 92.0)
	lid.released.emit(lid)
	await _frames(60)
	var stays := lid.hinge_position
	_move_hinge(lid, 0.0)
	await _frames(2)
	_check("toilet_soft_close", after_third > 45.0 and after_third < 59.9 and closed < 0.01 and frames > 150
			and absf(stays - 92.0) < 0.5,
			"let go at 60°: %.1f° after 0.33 s, shut after %.1f s (%.1f°); let go at 92° stays at %.1f°" % [
				after_third, frames / 90.0, closed, stays])


## Each flush button presses in 4 mm and starts its flush; one flush at a time.
func _test_toilet_flush() -> void:
	var t: Node3D = _main.get_node(PROPS + "Toilet")
	var small: Node3D = t.get_node("FlushSmall")
	var large: Node3D = t.get_node("FlushLarge")
	var cap: Node3D = small.get_node("Cap")
	var small_sound: PressSound = t.get_node("FlushSmallSound")
	var large_sound: PressSound = t.get_node("FlushLargeSound")
	var tip := _dummy_fingertip()
	var away := small.global_position + small.global_basis.z * 0.2
	tip.global_position = away
	await _frames(3)
	tip.global_position = small.global_position
	await _frames(15)
	var pressed_z := cap.position.z
	var small_playing := small_sound.playing
	tip.global_position = away
	await _frames(15)
	var released_z := cap.position.z
	tip.global_position = large.global_position
	await _frames(5)
	var large_ignored := not large_sound.playing
	tip.global_position = away
	await _frames(3)
	small_sound.stop()
	tip.global_position = large.global_position
	await _frames(5)
	var large_playing := large_sound.playing
	tip.global_position = away
	await _frames(3)
	large_sound.stop()
	tip.queue_free()
	_check("toilet_flush", absf(pressed_z + 0.004) < 0.0005 and absf(released_z) < 0.0005 and small_playing
			and large_ignored and large_playing,
			"small button in %.4f m while pressed, back %.4f m; small flush playing %s, large ignored meanwhile %s, large flush after %s" % [
				pressed_z, released_z, small_playing, large_ignored, large_playing])


## The roll rests frozen on its holder, comes off with the hand, falls when
## dropped away from the bar, and hangs again when put back near it.
func _test_toilet_roll() -> void:
	var t: Node3D = _main.get_node(PROPS + "Toilet")
	var roll: XRToolsPickable = t.get_node("Roll")
	var holder: Node3D = t.get_node("RollHolder")
	var snap: HolderSnap = roll.get_node("HolderSnap")
	await _frames(10)
	var on_holder := snap.is_held() and roll.global_position.distance_to(holder.global_position) < 0.002
	# Off the open end of the bar (+X) and away from the box.
	var carried := await _carry(roll, t.global_basis.x * 0.25 + t.global_basis.z * 0.15)
	_drop_left()
	await _frames(90)
	var fell := not roll.freeze and roll.global_position.y < holder.global_position.y - 0.3
	roll.freeze = false
	roll.global_transform = holder.global_transform.translated(t.global_basis.x * 0.03 + Vector3(0, 0.02, 0))
	roll.dropped.emit(roll)
	await _frames(3)
	var rehung := snap.is_held() and roll.global_position.distance_to(holder.global_position) < 0.002
	_check("toilet_roll_holder", on_holder and carried > 0.25 and fell and rehung,
			"on the holder at start %s; carried off %.2f m; dropped away falls %s; put back near the bar hangs %s" % [
				on_holder, carried, fell, rehung])


## Vanity drawers: the fronts' collision follows them, and a can standing in
## the top drawer rides along when it's pulled out.
func _test_vanity_drawers() -> void:
	var v: Node3D = _main.get_node(PROPS + "Vanity")
	var results: Array[String] = []
	var ok := true
	for drawer: String in ["DrawerTop", "DrawerBottom"]:
		var slider: XRToolsInteractableSlider = v.get_node(drawer + "/SliderOrigin/InteractableSlider")
		var body: PhysicsBody3D = v.get_node(drawer + "/SliderOrigin/InteractableSlider/Leaf/DrawerBody")
		var front := body.to_global(Vector3(0, 0.07, -0.009))
		var closed_hit := _hits_body(body, front)
		slider.move_slider(0.3)
		await _frames(3)
		var moved := _hits_body(body, front + v.global_basis.z * 0.3) and not _hits_body(body, front)
		slider.move_slider(0.0)
		await _frames(3)
		ok = ok and closed_hit and moved
		results.append("%s front closed %s, followed to 0.3 m %s" % [drawer, closed_hit, moved])
	_check("vanity_drawers", ok, "; ".join(results))

	var top: XRToolsInteractableSlider = v.get_node("DrawerTop/SliderOrigin/InteractableSlider")
	var top_body: PhysicsBody3D = v.get_node("DrawerTop/SliderOrigin/InteractableSlider/Leaf/DrawerBody")
	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	# Right side compartment (|x| 0.29..0.65, floor top at 0.022).
	can.global_position = top_body.to_global(Vector3(0.46, 0.09, -0.30))
	await _frames(60)
	var before := top_body.to_local(can.global_position)
	for i in 60:
		top.move_slider(0.3 * (i + 1) / 60.0)
		await get_tree().physics_frame
	await _frames(30)
	var after := top_body.to_local(can.global_position)
	for i in 60:
		top.move_slider(0.3 * (1.0 - (i + 1) / 60.0))
		await get_tree().physics_frame
	await _frames(10)
	can.queue_free()
	_check("vanity_drawer_carries_can", before.y > 0.0 and before.y < 0.13 and after.distance_to(before) < 0.05,
			"can at drawer-local %s, after pulling the drawer out 0.3 m %s" % [before.snappedf(0.01), after.snappedf(0.01)])


## The mixer lever lifts 0..30°, stays where it's let go, and its tip rises.
func _test_vanity_lever() -> void:
	var v: Node3D = _main.get_node(PROPS + "Vanity")
	var hinge: XRToolsInteractableHinge = v.get_node("Lever/HingeOrigin/InteractableHinge")
	var grip: Node3D = v.get_node("Lever/HingeOrigin/InteractableHinge/Leaf/HandleOrigin")
	_move_hinge(hinge, 0.0)
	var low := grip.global_position.y
	_move_hinge(hinge, 20.0)
	hinge.released.emit(hinge)
	await _frames(30)
	var stayed := hinge.hinge_position
	var lifted := grip.global_position.y - low
	_move_hinge(hinge, 50.0)
	var at_max := hinge.hinge_position
	_move_hinge(hinge, 0.0)
	_check("vanity_lever", absf(stayed - 20.0) < 0.01 and lifted > 0.02 and absf(at_max - 30.0) < 0.01,
			"let go at 20° stays %.1f°, tip lifted %.3f m; pushed past the top %.1f°" % [stayed, lifted, at_max])


## The soap dispenser stands on the top, can be picked up, and lands back on the top.
func _test_vanity_dispenser() -> void:
	var v: Node3D = _main.get_node(PROPS + "Vanity")
	var dispenser: XRToolsPickable = v.get_node("SoapDispenser")
	var rest_y := v.to_local(dispenser.global_position).y
	var carried := await _carry(dispenser, Vector3(0, 0.25, 0))
	_drop_left()
	await _frames(120)
	var landed_y := v.to_local(dispenser.global_position).y
	_check("vanity_dispenser", absf(rest_y - 0.86) < 0.01 and carried > 0.2 and absf(landed_y - 0.86) < 0.02,
			"stands at %.3f (top 0.86), lifted %.2f m, dropped lands at %.3f" % [rest_y, carried, landed_y])


## Shower mixer: the flow lever clicks into off and both ends (+90 points the
## tip toward +X), and stays where it's let go between them; the thermostat
## stops at ±120 and clicks into 38 °C.
func _test_shower_controls() -> void:
	var sh: Node3D = _main.get_node(PROPS + "Shower")
	var flow: XRToolsInteractableHinge = sh.get_node("FlowLever/HingeOrigin/InteractableHinge")
	var temp: XRToolsInteractableHinge = sh.get_node("TempDial/HingeOrigin/InteractableHinge")
	var tip: Node3D = sh.get_node("FlowLever/HingeOrigin/InteractableHinge/Leaf/HandleOrigin")
	var settled: Array[String] = []
	var ok := true
	for pair: Vector2 in [Vector2(80, 90), Vector2(45, 45), Vector2(-8, 0), Vector2(-80, -90)]:
		_move_hinge(flow, pair.x)
		flow.released.emit(flow)
		await _frames(30)
		ok = ok and absf(flow.hinge_position - pair.y) < 0.01
		settled.append("%d° -> %.1f°" % [int(pair.x), flow.hinge_position])
	_move_hinge(flow, 90.0)
	var tip_x := sh.to_local(tip.global_position).x - (-0.60)
	_move_hinge(flow, 0.0)
	_check("shower_flow_lever", ok and tip_x > 0.04, "let go at %s; at +90° the tip is %.3f m toward +X" % [
			", ".join(settled), tip_x])
	_move_hinge(temp, 150.0)
	var at_max := temp.hinge_position
	_move_hinge(temp, 4.0)
	temp.released.emit(temp)
	await _frames(30)
	var clicked_in := temp.hinge_position
	_move_hinge(temp, 60.0)
	temp.released.emit(temp)
	await _frames(30)
	var stayed := temp.hinge_position
	_move_hinge(temp, 0.0)
	_check("shower_thermostat", absf(at_max - 120.0) < 0.01 and absf(clicked_in) < 0.01 and absf(stayed - 60.0) < 0.01,
			"turned past the stop %.1f°, let go at 4° settles at %.1f°, at 60° stays %.1f°" % [at_max, clicked_in, stayed])


## The hand shower sits frozen in its holder, comes out with the hand, falls
## when dropped away, and clicks back in when put back near the holder.
func _test_shower_hand() -> void:
	var sh: Node3D = _main.get_node(PROPS + "Shower")
	var hand: XRToolsPickable = sh.get_node("HandShower")
	var holder: Node3D = sh.get_node("HandShowerHolder")
	var snap: HolderSnap = hand.get_node("HolderSnap")
	var in_holder := snap.is_held() and hand.global_position.distance_to(holder.global_position) < 0.002
	var carried := await _carry(hand, sh.global_basis.z * 0.35 + Vector3(0, 0.15, 0))
	_drop_left()
	await _frames(90)
	var fell := not hand.freeze and hand.global_position.y < 1.0
	hand.freeze = false
	hand.global_transform = holder.global_transform.translated(Vector3(0, 0.04, 0.02))
	hand.dropped.emit(hand)
	await _frames(3)
	var back := snap.is_held() and hand.global_position.distance_to(holder.global_position) < 0.002
	_check("shower_hand_holder", in_holder and carried > 0.3 and fell and back,
			"in the holder at start %s; carried out %.2f m; dropped away falls %s; put back clicks in %s" % [
				in_holder, carried, fell, back])


## The hand shower's hose: it runs from the wall outlet to the hand shower and
## rests (sleeps) while the hand shower sits in its holder; carried, it
## follows; pulled past its length, the hand lets go and the dropped hand
## shower hangs within the hose's reach.
func _test_shower_hose() -> void:
	var sh: Node3D = _main.get_node(PROPS + "Shower")
	var hose: ShowerHose = sh.get_node("Hose")
	var hand: XRToolsPickable = sh.get_node("HandShower")
	var outlet: Node3D = sh.get_node("HoseOutlet")
	var hose_end: Node3D = hand.get_node("HoseEnd")
	var holder: Node3D = sh.get_node("HandShowerHolder")
	var settle := 0
	while hose.is_awake() and settle < 600:
		await get_tree().physics_frame
		settle += 1
	var points := hose.get_points()
	var ends := points[0].distance_to(hose.to_local(outlet.global_position)) \
			+ points[points.size() - 1].distance_to(hose.to_local(hose_end.global_position))
	var lowest := INF
	for p in points:
		lowest = minf(lowest, p.y)
	var resting := not hose.is_awake()
	await _carry(hand, sh.global_basis.z * 0.4)
	var awake := hose.is_awake()
	points = hose.get_points()
	var follows := points[points.size() - 1].distance_to(hose.to_local(hose_end.global_position))
	# Pull it 2.5 m away from the outlet.
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var from := pickup.global_position
	var away := outlet.global_position + sh.global_basis.z * 2.5 + Vector3(0, 0.8, 0)
	for i in 30:
		pickup.global_transform = Transform3D(Basis.IDENTITY, from.lerp(away, (i + 1) / 30.0))
		await get_tree().physics_frame
	var let_go := not hand.is_picked_up()
	await _frames(90)
	var reach := outlet.global_position.distance_to(hose_end.global_position)
	_drop_left()
	hand.freeze = false
	hand.global_transform = holder.global_transform.translated(Vector3(0, 0.04, 0.02))
	hand.dropped.emit(hand)
	await _frames(3)
	_check("shower_hose", ends < 0.002 and lowest > 0.0 and resting and settle < 300 and awake and follows < 0.002 and let_go
			and reach <= hose.length + 0.01,
			"ends on outlet and hand shower %.4f m off, lowest point %.2f m, resting in the holder %s (after %d frames); carried: awake %s, end %.4f m off; pulled 2.5 m away: let go %s, hangs %.2f m from the outlet (hose %.1f m)" % [
				ends, lowest, resting, settle, awake, follows, let_go, reach, hose.length])


## The flow lever runs the water: hand shower at -90°, rain head at +90°,
## nothing at 0 (spray and sound).
func _test_shower_water() -> void:
	var sh: Node3D = _main.get_node(PROPS + "Shower")
	var flow: XRToolsInteractableHinge = sh.get_node("FlowLever/HingeOrigin/InteractableHinge")
	var hand: GPUParticles3D = sh.get_node("HandShower/SprayFace/HandSpray")
	var rain: GPUParticles3D = sh.get_node("RainNozzles/RainSpray")
	var hand_sound: AudioStreamPlayer3D = sh.get_node("HandShower/SprayFace/HandSpraySound")
	var rain_sound: AudioStreamPlayer3D = sh.get_node("RainNozzles/RainSpraySound")
	var states: Array[String] = []
	for angle: float in [0.0, -90.0, 90.0, -45.0, 0.0]:
		_move_hinge(flow, angle)
		await _frames(2)
		states.append("%d°: hand %s/%s rain %s/%s" % [angle, hand.emitting, hand_sound.playing, rain.emitting,
				rain_sound.playing])
	var expected: Array[String] = ["0°: hand false/false rain false/false", "-90°: hand true/true rain false/false",
			"90°: hand false/false rain true/true", "-45°: hand true/true rain false/false",
			"0°: hand false/false rain false/false"]
	_check("shower_water", states == expected and hand.amount_ratio < 1.0, ", ".join(states))


## The shower glass stops a body-sized capsule and the walking player; the
## entry at its south end lets both through.
func _test_shower_glass() -> void:
	var space := _main.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.2
	capsule.height = 1.6
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = 1
	query.transform = Transform3D(Basis.IDENTITY, Vector3(0.6, 0.95, 4.7))
	query.motion = Vector3(-1.2, 0, 0)
	var glass_fraction := space.cast_motion(query)[0]
	var stop_x := 0.6 - 1.2 * glass_fraction - capsule.radius
	query.transform = Transform3D(Basis.IDENTITY, Vector3(0.45, 0.95, 6.1))
	query.motion = Vector3(-1.25, 0, 0)
	var entry_fraction := space.cast_motion(query)[0]

	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	var mix: float = body.body_forward_mix
	body.body_forward_mix = 0.0
	var west := Basis(Vector3.UP, PI / 2.0)
	var ends: Array[float] = []
	for start: Vector3 in [Vector3(0.6, 0, 4.7), Vector3(0.45, 0, 6.1)]:
		body.teleport(Transform3D(west, start))
		await _frames(30)
		var walker := _ForwardInput.new()
		walker.add_to_group("movement_providers")
		body.add_child(walker)
		body._movement_providers.append(walker)
		await _frames(100)
		body._movement_providers.erase(walker)
		walker.queue_free()
		ends.append(body.global_position.x)
	body.body_forward_mix = mix
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4)))
	await _frames(30)
	_check("shower_glass_blocks", glass_fraction < 1.0 and stop_x > -0.25 and ends[0] > -0.25,
			"capsule front stops at x %.2f (glass -0.20); player walking at the glass ends at x %.2f" % [stop_x, ends[0]])
	_check("shower_entry_open", entry_fraction > 0.99 and ends[1] < -0.4,
			"capsule through the entry free fraction %.2f; player walking in ends at x %.2f (inside < -0.2)" % [
				entry_fraction, ends[1]])
