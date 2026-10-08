extends Node
## Interaction tests on the real main scene (desktop, no XR). Started by
## main.gd:
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --test=interaction
##
## Prints one line per check ("TEST PASS/FAIL <name>: <details>") and quits
## with the number of failures (2 for a bad --only). Runs through main.gd (not
## --script) so the XR Tools autoloads exist.
##
## Subsets (see _registry()):
##   --only=<a,b>   groups, or tests whose name contains the word
##                  (--only=avatar, --only=doors_fridge,windows, --only=arm_ik)
##   --list         print the groups and their tests, run nothing
## Before each test the rig is put back (nothing held, pickups at their hands,
## player at HOME), so a test or group run alone sees what it sees in a full run.

const DOORS := ["DoorLiving", "DoorBedroom", "DoorBathroom", "DoorEntrance"]
const SIDES: Array[String] = ["Left", "Right"]
const SKELETON := "Player/Avatar/Model/Armature/Skeleton3D"
# The player body's spot (Entries/Default, facing -Z) that tests which move the
# player return to; _reset_rig() puts it there before each test.
const HOME := Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4))
const CAN_SCENE := "res://assets/props/beverage_can/beverage_can.tscn"
# Sweep start and motion through each doorway (capsule center at 0.9 m).
const DOORWAYS := {
	"DoorLiving": [Vector3(2.05, 0.9, 1.2), Vector3(0, 0, 1.7)],
	"DoorBedroom": [Vector3(-3.95, 0.9, 2.9), Vector3(0, 0, -1.7)],
	"DoorBathroom": [Vector3(0.55, 0.9, 2.9), Vector3(0, 0, 1.7)],
	"DoorEntrance": [Vector3(5.8, 0.9, 2.9), Vector3(1.6, 0, 0)],
}

var _main: Node3D
var _failures := 0
# The pickups' transforms at the start; restored before each test.
var _pickup_rest: Array[Transform3D] = []


## Every test in run order: [group, name, coroutine]. A full run goes through
## all of them in this order; --only picks groups or names, keeping the order.
## Groups follow what a change touches (a group may appear in several places).
## Adding a test is one line here.
func _registry() -> Array[Array]:
	var tests: Array[Array] = [
		["player", "doorways", _test_doorways],
		["player", "door_blocker", _test_blocker],
		["player", "pass_through", _test_pass_through],
		["player", "push_door_open", _test_push_door_open],
		["player", "jump", _test_jump],
		["player", "jump_onto_table", _test_jump_onto_table],
		["player", "ranged_grab", _test_ranged_grab],
		["doors_fridge", "fridge", _test_fridge.bind("Fridge")],
		["doors_fridge", "fridge_swing", _test_swing.bind("Fridge", 20.0, 150.0)],
		["doors_fridge", "door_swing", _test_swing.bind("DoorLiving", 20.0, 120.0)],
		["doors_fridge", "fridge_flick_shut", _test_flick_shut.bind("Fridge")],
		["doors_fridge", "fridge_door_bin", _test_fridge_door_bin],
		["doors_fridge", "door_hand_push", _test_hand_push.bind("DoorLiving")],
		["doors_fridge", "entrance_hand_push", _test_hand_push.bind("DoorEntrance")],
		["doors_fridge", "fridge_hand_push", _test_hand_push.bind("Fridge")],
		["doors_fridge", "door_edge_grab", _test_edge_grab.bind("DoorBedroom")],
		["doors_fridge", "entrance_edge_grab", _test_edge_grab.bind("DoorEntrance")],
		["doors_fridge", "entrance_lock", _test_door_lock.bind("DoorEntrance")],
		["doors_fridge", "bathroom_lock", _test_door_lock.bind("DoorBathroom")],
		["rendering", "door_viewer", _test_door_viewer],
		["furniture", "sofa", _test_sofa],
		["variants", "spare_sofa", _test_spare_sofa],
		["furniture", "bedroom", _test_bedrooms],
		["switches", "ab_panel", _test_ab_panel],
		["switches", "ab_environment", _test_ab_environment],
		["switches", "ab_panel_has_switches", _test_ab_panel_has_switches],
		["avatar", "fingertips", _test_fingertips],
		# Hand rig and arm IK share the posed hands, so they are one test.
		["avatar", "hand_rig_arm_ik", _test_hand_rig],
		["avatar", "body_ik", _test_body_ik],
		["avatar", "walk", _test_walk],
		["avatar", "sit_pose", _test_sit_pose],
		["avatar", "coat_springs", _test_coat_springs],
		["avatar", "eyes", _test_avatar_eyes],
		["avatar", "after_ssao", _test_avatar_after_ssao],
		["switches", "lamp_switch", _test_lamp_switches],
		["doors_fridge", "fridge_alarm", _test_fridge_alarm],
		["wardrobe", "wardrobe_interior", _test_wardrobe_interior],
		["furniture", "bed_bedding", _test_bed_bedding_collision],
		["variants", "spare_variants", _test_spare_variants],
		["windows", "window_vent", _test_window_vent],
		["windows", "window_shade", _test_window_shade],
		["windows", "window_tint", _test_window_tint],
		["windows", "window_hud", _test_window_hud],
		["windows", "window_glass", _test_window_glass_collision],
		["windows", "rain_wetness", _test_rain_wetness],
		["world", "world_clock", _test_world_clock],
		["world", "world_sun", _test_world_sun],
		["world", "world_seasons", _test_world_seasons],
		["world", "world_weather", _test_world_weather],
		["world", "day_night", _test_day_night],
		["world", "day_night_idle", _test_day_night_idle],
		["world", "day_night_update_cost", _test_day_night_update_cost],
		["world", "world_rain", _test_world_rain],
		["world", "world_terminal_touch", _test_world_terminal_touch],
		["world", "world_terminal_keys", _test_world_terminal_keys],
		["world", "ray_buttons", _test_ray_buttons],
		["world", "probe_recapture", _test_probe_recapture],
		["rendering", "foveation_on_xr_start", _test_foveation_on_xr_start],
		["rendering", "ab_viewport", _test_ab_viewport],
		["rendering", "reflections_warmed", _test_reflections_warmed],
		["bathroom", "bath_magnifier", _test_bath_magnifier],
		["bathroom", "bath_mirror_touch", _test_bath_mirror_touch],
		["bathroom", "toilet_lid_and_seat", _test_toilet_lid_and_seat],
		["bathroom", "toilet_soft_close", _test_toilet_soft_close],
		["bathroom", "toilet_flush", _test_toilet_flush],
		["bathroom", "toilet_roll", _test_toilet_roll],
		["bathroom", "vanity_drawers", _test_vanity_drawers],
		["bathroom", "vanity_lever", _test_vanity_lever],
		["bathroom", "vanity_dispenser", _test_vanity_dispenser],
		["bathroom", "shower_controls", _test_shower_controls],
		["bathroom", "shower_hand", _test_shower_hand],
		["bathroom", "shower_hose", _test_shower_hose],
		["bathroom", "shower_water", _test_shower_water],
		["bathroom", "shower_glass", _test_shower_glass],
		["zones", "zone_streamed", _test_zone_streamed],
		["zones", "zone_follows_player", _test_zone_follows_player],
		["zones", "zone_gate", _test_zone_gate],
		["zones", "zone_unload_far", _test_zone_unload_far],
		["zones", "zone_reflection_warm", _test_zone_reflection_warm],
		["zones", "zone_rain", _test_zone_rain],
		["zones", "zone_drawn_when_seen", _test_zone_drawn_when_seen],
	]
	return tests


func _ready() -> void:
	_main = get_parent() as Node3D
	var tests := _registry()
	var args := OS.get_cmdline_user_args()
	if args.has("--list"):
		_print_list(tests)
		get_tree().quit(0)
		return
	var only: PackedStringArray = []
	for arg in args:
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",", false)
	if not only.is_empty():
		tests = _select(tests, only)
		if tests.is_empty():
			get_tree().quit(2)
			return
		var names: Array[String] = []
		for test in tests:
			names.append(test[1])
		print("TEST ONLY %s: %s" % [",".join(only), ", ".join(names)])

	await _frames(30)
	for side in SIDES:
		_pickup_rest.append((_main.get_node("Player/%sHand/CollisionHand/FunctionPickup" % side) as Node3D).transform)
	var group_ms := {}
	for test in tests:
		var start := Time.get_ticks_msec()
		await _reset_rig()
		await (test[2] as Callable).call()
		group_ms[test[0]] = group_ms.get(test[0], 0) + Time.get_ticks_msec() - start
	var ran: Array[String] = []
	for group: String in group_ms:
		ran.append("%s %.1f s" % [group, group_ms[group] / 1000.0])
	print("TEST GROUPS: %s%s" % [", ".join(ran), "" if only.is_empty() else " (--only=%s)" % ",".join(only)])
	print("TEST DONE: %d failure(s)" % _failures)
	get_tree().quit(_failures)


## The tests a --only list picks: a token is a group name, or else part of a
## test's name. An unknown token prints the choices and returns nothing.
func _select(tests: Array[Array], only: PackedStringArray) -> Array[Array]:
	var groups: Array[String] = []
	for test in tests:
		if not groups.has(test[0]):
			groups.append(test[0])
	var picked: Array[Array] = []
	var unknown: Array[String] = []
	for token in only:
		var hit := false
		for test in tests:
			if test[0] == token or (not groups.has(token) and (test[1] as String).contains(token)):
				hit = true
				if not picked.has(test):
					picked.append(test)
		if not hit:
			unknown.append(token)
	if not unknown.is_empty():
		push_error("TEST: no group or test matches %s (groups: %s; --list shows the tests)" % [
				", ".join(unknown), ", ".join(groups)])
		return []
	# Keep the registry order.
	return tests.filter(func(test: Array) -> bool: return picked.has(test))


func _print_list(tests: Array[Array]) -> void:
	var by_group := {}
	for test in tests:
		if not by_group.has(test[0]):
			by_group[test[0]] = []
		(by_group[test[0]] as Array).append(test[1])
	print("TEST LIST: %d tests in %d groups (--only=<group or part of a test name>,...)" % [tests.size(), by_group.size()])
	for group: String in by_group:
		var names: Array = by_group[group]
		print("  %s (%d): %s" % [group, names.size(), ", ".join(names)])


## Puts the rig back: nothing held, pickups at their hands, the player body at
## HOME (waits only if it had moved; at the start the body stands 0.1 m off it).
func _reset_rig() -> void:
	for i in SIDES.size():
		var pickup: XRToolsFunctionPickup = _main.get_node("Player/%sHand/CollisionHand/FunctionPickup" % SIDES[i])
		if pickup.picked_up_object:
			pickup.drop_object()
		pickup.transform = _pickup_rest[i]
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	if body.global_position.distance_to(HOME.origin) > 0.05 or body.global_basis.z.dot(HOME.basis.z) < 0.999:
		body.teleport(HOME)
		await _frames(30)


func _check(name: String, ok: bool, details: String) -> void:
	print("TEST %s %s: %s" % ["PASS" if ok else "FAIL", name, details])
	if not ok:
		_failures += 1


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func _hinge(door: String) -> XRToolsInteractableHinge:
	return _main.get_node("Zones/Apartment/Props/%s/HingeOrigin/InteractableHinge" % door)


func _set_hinge(door: String, angle: float) -> void:
	var hinge := _hinge(door)
	hinge.hinge_position = angle
	hinge.hinge_moved.emit(angle)


## Doors block a body-sized capsule when closed and let it through when open,
## measured against the physics server (not node transforms).
func _test_doorways() -> void:
	var space := _main.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.2
	capsule.height = 1.6
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule
	query.collision_mask = 1
	for door: String in DOORS:
		query.transform = Transform3D(Basis.IDENTITY, DOORWAYS[door][0])
		query.motion = DOORWAYS[door][1]
		_set_hinge(door, 0.0)
		await _frames(3)
		var closed := space.cast_motion(query)[0]
		_set_hinge(door, 90.0)
		await _frames(3)
		var opened := space.cast_motion(query)[0]
		_set_hinge(door, 0.0)
		await _frames(3)
		_check("doorway_" + door, closed < 0.9 and opened > 0.99,
				"free fraction closed %.2f, open %.2f" % [closed, opened])


## A door swung toward a body standing in its path stops at the body.
func _test_blocker() -> void:
	var dummy := _dummy_body(Vector3(2.2, 0.9, 1.55))
	await _frames(3)
	_set_hinge("DoorLiving", 90.0)
	var blocked := _hinge("DoorLiving").hinge_position
	dummy.global_position = Vector3(-2, 0.9, -1)
	await _frames(3)
	_set_hinge("DoorLiving", 90.0)
	var free := _hinge("DoorLiving").hinge_position
	_set_hinge("DoorLiving", 0.0)
	dummy.queue_free()
	_check("door_blocker", blocked < 40.0 and free > 89.0,
			"with body in path %.1f°, without %.1f°" % [blocked, free])


## Grabbing a door handle lets that hand pass through the door leaf, so the
## door can be pushed open.
func _test_pass_through() -> void:
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var hand: PhysicsBody3D = _main.get_node("Player/LeftHand/CollisionHand")
	var leaf: PhysicsBody3D = _main.get_node(
			"Zones/Apartment/Props/DoorBedroom/HingeOrigin/InteractableHinge/Leaf/DoorBody")
	var handle: XRToolsPickable = _main.get_node(
			"Zones/Apartment/Props/DoorBedroom/HingeOrigin/InteractableHinge/Leaf/HandleOriginBack/InteractableHandle")
	var before := hand.get_collision_exceptions().has(leaf)
	pickup.global_position = handle.global_position
	pickup._pick_up_object(handle)
	await _frames(2)
	var during := hand.get_collision_exceptions().has(leaf)
	pickup.drop_object()
	await _frames(2)
	var after := hand.get_collision_exceptions().has(leaf)
	_check("door_grab_pass_through", not before and during and not after,
			"hand ignores leaf: before %s, while held %s, after release %s" % [before, during, after])


## From the hallway, a hand pressing into the bedroom door is blocked by the
## leaf, until it holds the door's handle: then it can move into the leaf,
## so pushing the handle swings the door (pulling always worked).
func _test_push_door_open() -> void:
	var hand: PhysicsBody3D = _main.get_node("Player/LeftHand/CollisionHand")
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var handle: XRToolsPickable = _main.get_node(
			"Zones/Apartment/Props/DoorBedroom/HingeOrigin/InteractableHinge/Leaf/HandleOriginBack/InteractableHandle")
	# Hallway side of the closed door, hand 5 cm in front of the leaf.
	var at := Transform3D(hand.global_basis, Vector3(-3.64, 1.1, 2.08))
	var push := Vector3(0, 0, -0.3)
	var blocked_free := hand.test_move(at, push)
	pickup.global_position = handle.global_position
	pickup._pick_up_object(handle)
	await _frames(1)
	var blocked_held := hand.test_move(at, push)
	pickup.drop_object()
	await _frames(2)
	_check("push_door_open", blocked_free and not blocked_held,
			"hand blocked by leaf: empty hand %s, holding the handle %s" % [blocked_free, blocked_held])


## Standing jump height; must clear the 0.75 m tables.
func _test_jump() -> void:
	var player: XROrigin3D = _main.get_node("Player")
	var body: XRToolsPlayerBody = player.get_node("PlayerBody")
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4)))
	await _frames(30)
	var y0 := body.global_position.y
	body.request_jump()
	var peak := y0
	for i in 135:
		await get_tree().physics_frame
		peak = maxf(peak, body.global_position.y)
	_check("jump_height", peak - y0 > 0.85, "feet lift %.2f m (table 0.75 m)" % (peak - y0))
	await _frames(60)
	_check_eye_height("jump_eye_height_after_landing", body)


## Walking at the living room table and jumping lands the player on top,
## right where a can stands (the body must not collide with pickables, or the
## can launches it).
func _test_jump_onto_table() -> void:
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	# Face -Z, 0.9 m in front of the table edge (table top 0.75 m, z -1.6..-1.0).
	# Forward from the head only (XR Tools mixes in hand positions, which
	# other tests move around).
	var mix: float = body.body_forward_mix
	body.body_forward_mix = 0.0
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(1.1, 0, -0.1)))
	await _frames(30)
	var start := body.global_position
	var walker := _ForwardInput.new()
	walker.add_to_group("movement_providers")
	body.add_child(walker)
	# XR Tools collects providers once at startup; register this test one.
	body._movement_providers.append(walker)
	for i in 155:
		if i == 20:
			body.request_jump()
		if i == 65:
			walker.speed = 0.0
		await get_tree().physics_frame
	body._movement_providers.erase(walker)
	walker.queue_free()
	var pos := body.global_position
	body.body_forward_mix = mix
	var on_table := pos.y > 0.7 and pos.z < -0.95 and pos.z > -1.65
	_check("jump_onto_table", on_table, "from %s ended at %s (table top y 0.75)" % [
			start.snappedf(0.01), pos.snappedf(0.01)])
	_check_eye_height("jump_onto_table_eye_height", body)
	body.teleport(Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4)))
	await _frames(30)


## Test-only movement provider: pushes the player forward like a held stick.
class _ForwardInput extends XRToolsMovementProvider:
	var order := 10
	var speed := 1.5

	func physics_movement(_delta: float, player_body: XRToolsPlayerBody, _disabled: bool) -> bool:
		player_body.ground_control_velocity.y += speed
		return false


## Pointing at a can from 2 m and gripping pulls it into the hand; nothing is
## targeted through walls.
func _test_ranged_grab() -> void:
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var ray: GrabRay = pickup.get_node("GrabRay")
	var can: Node3D = _main.get_node("Zones/Apartment/Props/CanLivingTable")
	var from := Vector3(1.25, 1.2, 0.7)
	pickup.global_transform = Transform3D(Basis.IDENTITY, from).looking_at(can.global_position, Vector3.UP)
	var found := ray._find_target()
	var dist_to_hand := -1.0
	if found:
		pickup._pick_up_object(found)
		for i in 60:
			pickup.global_transform = Transform3D(Basis.IDENTITY, from)
			await get_tree().physics_frame
		dist_to_hand = can.global_position.distance_to(pickup.global_position)
		pickup.drop_object()
	_check("ranged_grab_pull", found == can and dist_to_hand >= 0.0 and dist_to_hand < 0.1,
			"target %s, distance to hand after 60 frames %.2f m" % [found, dist_to_hand])
	var other: Node3D = _main.get_node("Zones/Apartment/Props/CanNightstand")
	pickup.global_transform = Transform3D(Basis.IDENTITY, Vector3(-2.5, 0.8, 0.35)).looking_at(
			other.global_position, Vector3.UP)
	var through_wall := ray._find_target()
	_check("ranged_grab_line_of_sight", through_wall == null, "target through wall: %s" % through_wall)


## After landing, the eyes are back at standing height above the feet.
func _check_eye_height(name: String, body: XRToolsPlayerBody) -> void:
	var camera: Node3D = _main.get_node("Player/XRCamera3D")
	var eye := camera.global_position.y - body.global_position.y
	var expected := camera.transform.origin.y + body.player_height_offset
	_check(name, absf(eye - expected) < 0.05, "eye %.2f m above feet (expected %.2f)" % [eye, expected])


func _dummy_body(pos: Vector3) -> CharacterBody3D:
	var dummy := CharacterBody3D.new()
	dummy.collision_layer = 1 << 19  # Player Body
	dummy.collision_mask = 0
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.2
	capsule.height = 1.8
	shape.shape = capsule
	dummy.add_child(shape)
	_main.add_child(dummy)
	dummy.global_position = pos
	return dummy


## Fridge: the door's collision follows the door, the interior light is on
## only while open, the seal pulls a nearly closed door shut, and a can
## dropped inside stays on a shelf.
func _test_fridge(fridge: String) -> void:
	var root: Node3D = _main.get_node("Zones/Apartment/Props/" + fridge)
	var hinge: XRToolsInteractableHinge = root.get_node("HingeOrigin/InteractableHinge")
	var door_body: PhysicsBody3D = root.get_node("HingeOrigin/InteractableHinge/Leaf/DoorBody")
	var light: Light3D = root.get_node("InteriorLight")
	var space := _main.get_world_3d().direct_space_state
	# Just in front of the cabinet, in the middle of the closed door.
	var query := PhysicsPointQueryParameters3D.new()
	query.position = root.to_global(Vector3(0, 1.0, 0.35))
	var hits_door := func() -> bool:
		return space.intersect_point(query).any(func(hit: Dictionary) -> bool: return hit.collider == door_body)

	_set_hinge(fridge, 0.0)
	await _frames(3)
	var closed_hit: bool = hits_door.call()
	var closed_light := light.visible
	_set_hinge(fridge, 90.0)
	await _frames(3)
	var open_hit: bool = hits_door.call()
	var open_light := light.visible
	_check(fridge + "_door_collision", closed_hit and not open_hit,
			"door body at the closed door's spot: closed %s, open %s" % [closed_hit, open_hit])
	_check(fridge + "_light", not closed_light and open_light,
			"interior light closed %s, open %s" % [closed_light, open_light])

	# A can dropped into the middle of the cabinet lands on a shelf.
	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	can.global_position = root.to_global(Vector3(0, 1.3, 0.05))
	await _frames(120)
	var local := root.to_local(can.global_position)
	can.queue_free()
	_check(fridge + "_can_on_shelf", local.y > 0.6 and absf(local.x) < 0.26 and local.z > -0.33 and local.z < 0.33,
			"can at local %s after dropping from y 1.3" % local.snappedf(0.01))

	# Released 10° open: the seal pulls it shut. Released 40° open: it stays.
	_set_hinge(fridge, 10.0)
	hinge.released.emit(hinge)
	await _frames(30)
	var snapped := hinge.hinge_position
	_set_hinge(fridge, 40.0)
	hinge.released.emit(hinge)
	await _frames(30)
	var stayed := hinge.hinge_position
	_set_hinge(fridge, 0.0)
	await _frames(2)
	_check(fridge + "_latch", snapped < 0.01 and absf(stayed - 40.0) < 0.5 and not light.visible,
			"released at 10° ends at %.1f°, at 40° stays %.1f°, light off after closing %s" % [snapped, stayed, not light.visible])


## Moves the hinge like a hand would (while "grabbed"), then lets go.
func _throw_hinge(door: String, from: float, speed: float) -> void:
	var hinge := _hinge(door)
	_set_hinge(door, from)
	hinge.grabbed.emit(hinge)
	var start := Time.get_ticks_usec()
	for i in 10:
		await get_tree().physics_frame
		_set_hinge(door, from + speed * (Time.get_ticks_usec() - start) / 1e6)
	hinge.released.emit(hinge)


## Let go while opening: the hinge swings on, then friction stops it short
## of the open limit.
func _test_swing(door: String, from: float, speed: float) -> void:
	var hinge := _hinge(door)
	await _throw_hinge(door, from, speed)
	var released_at := hinge.hinge_position
	await _frames(180)
	var ended := hinge.hinge_position
	var swing: HingeSwing = _main.get_node("Zones/Apartment/Props/%s/Swing" % door)
	var resting := swing.get_velocity() == 0.0
	_set_hinge(door, 0.0)
	await _frames(2)
	_check(door + "_swing", ended > released_at + 10.0 and ended < hinge.hinge_limit_max and resting,
			"released at %.1f° going %.0f°/s, came to rest at %.1f° (resting %s)" % [released_at, speed, ended, resting])


## Flicked shut from wide open: it swings closed and the seal holds it.
func _test_flick_shut(door: String) -> void:
	var hinge := _hinge(door)
	await _throw_hinge(door, 70.0, -250.0)
	await _frames(180)
	var ended := hinge.hinge_position
	_set_hinge(door, 0.0)
	await _frames(2)
	_check(door + "_flick_shut", ended < 0.01, "flicked shut from 70° at 250°/s, ended at %.1f°" % ended)


## Puts the left controller where its palm (HingeHandPush.palm_target) lands on `world`.
func _place_palm(world: Vector3) -> void:
	var controller: XRController3D = _main.get_node("Player/LeftHand")
	var hand: XRToolsCollisionHand = controller.get_node("CollisionHand")
	var offset := HingeHandPush.palm_target(hand) - controller.global_position
	controller.global_position = world - offset


## A bare palm pushes an open door: pressed into the face it opens toward,
## the leaf turns away until the palm rests on it, and the shove swings on.
## Closed, the same push from the other side does nothing (the latch holds).
func _test_hand_push(door: String) -> void:
	var hinge := _hinge(door)
	var push: HingeHandPush = _main.get_node(PROPS + door + "/HandPush")
	var leaf: Node3D = hinge.get_node("Leaf")
	var controller: XRController3D = _main.get_node("Player/LeftHand")
	var saved := controller.global_transform
	var x := push._bounds.end.x * 0.7
	var front := push._bounds.end.z + push.palm_radius
	var back := push._bounds.position.z - push.palm_radius
	_set_hinge(door, 45.0)
	await _frames(3)
	# 70 % out from the hinge at 1.2 m, from 12 cm off the open-side face to 15 cm past it, fixed in the world.
	var from := leaf.to_global(Vector3(x, 1.2, front + 0.12))
	var to := leaf.to_global(Vector3(x, 1.2, front - 0.15))
	_place_palm(from)
	await _frames(10)
	for i in 30:
		_place_palm(from.lerp(to, (i + 1) / 30.0))
		await get_tree().physics_frame
	var pushed_to := hinge.hinge_position
	# No bone of the (wanted) hand sinks into the face it pushes.
	var hand: XRToolsCollisionHand = controller.get_node("CollisionHand")
	var points := PackedVector3Array()
	var radii := PackedFloat32Array()
	push.hand_points(hand, points, radii)
	var sunk := 0.0
	for k in points.size():
		var b := leaf.to_local(points[k])
		var on_face := b.x > push._bounds.position.x and b.x < push._bounds.end.x
		on_face = on_face and b.y > push._bounds.position.y and b.y < push._bounds.end.y
		if on_face and b.z > push._bounds.position.z - 0.1:
			sunk = maxf(sunk, push._bounds.end.z + radii[k] - b.z)
	_place_palm(from)
	await _frames(60)
	var coasted := hinge.hinge_position
	# Closed: the palm pushes into the other face; the door stays shut.
	_set_hinge(door, 0.0)
	await _frames(3)
	from = leaf.to_global(Vector3(x, 1.2, back - 0.12))
	to = leaf.to_global(Vector3(x, 1.2, back + 0.15))
	_place_palm(from)
	await _frames(10)
	for i in 20:
		_place_palm(from.lerp(to, (i + 1) / 20.0))
		await get_tree().physics_frame
	var closed_push := hinge.hinge_position
	controller.global_transform = saved
	await _frames(10)
	_set_hinge(door, 0.0)
	await _frames(2)
	_check(door + "_hand_push", pushed_to < 35.0 and points.size() > 10 and sunk < 0.01 and coasted <= pushed_to
			and closed_push == 0.0,
			"open 45°, palm pushed 27 cm into the face: door at %.1f°, %d hand bones, deepest %.3f m into the face; coasted to %.1f°; closed, pushed from the other side: %.1f°" % [
				pushed_to, points.size(), sunk, coasted, closed_push])

## A door's thumb-turn deadbolt: it locks the closed door (its lever only
## rattles it; the entrance's LED turns red, the bathroom's knob turns with
## it), unlocks it again, and doesn't move while the door is open; the turn
## rides the leaf.
func _test_door_lock(door_name: String) -> void:
	var root: Node3D = _main.get_node(PROPS + door_name)
	var door := _hinge(door_name)
	var turn: XRToolsInteractableHinge = root.get_node("ThumbTurn/HingeOrigin/InteractableHinge")
	var lock: DoorLock = root.get_node("Lock")
	var rattle: AudioStreamPlayer3D = root.get_node("HingeOrigin/InteractableHinge/Leaf/Rattle")
	var led: BaseMaterial3D = lock._leds[0] if not lock._leds.is_empty() else null
	var has_led := door_name == "DoorEntrance"
	var cyan := not has_led or (led != null and led.emission.b > 0.5 and led.emission.r < 0.2)
	var knob := lock.turn_visual
	var knob_rest := knob.global_basis if knob else Basis.IDENTITY
	_move_hinge(turn, 90.0)
	var locked := lock.is_locked()
	var red := not has_led or (led != null and led.emission.r > 0.5 and led.emission.b < 0.2)
	# The knob turned 90° about the leaf normal (its blade now horizontal).
	var knob_turned := knob == null or absf(rad_to_deg(knob.global_basis.y.angle_to(knob_rest.y)) - 90.0) < 1.0
	_set_hinge(door_name, 40.0)
	var held_shut := door.hinge_position
	door.grabbed.emit(door)
	var rattled := rattle.playing
	door.released.emit(door)
	_move_hinge(turn, 0.0)
	var unlocked := not lock.is_locked()
	_set_hinge(door_name, 40.0)
	var opens := door.hinge_position
	await _frames(3)
	var mount: Node3D = root.get_node("HingeOrigin/InteractableHinge/Leaf/ThumbTurnMount")
	var rides := (root.get_node("ThumbTurn") as Node3D).global_position.distance_to(mount.global_position)
	_move_hinge(turn, 90.0)
	var turned_open := turn.hinge_position
	_set_hinge(door_name, 0.0)
	await _frames(3)
	_check(door_name + "_lock", cyan and locked and red and knob_turned and held_shut == 0.0 and rattled
			and unlocked and opens == 40.0 and rides < 0.001 and turned_open == 0.0,
			"LED cyan %s; turned 90°: locked %s, LED red %s, knob turned %s, door pulled to 40° stays at %.1f°, rattles %s; turned back: unlocked %s, opens to %.1f°; turn %.4f m off its mount on the open leaf; turning it while open: %.1f°" % [
				cyan, locked, red, knob_turned, held_shut, rattled, unlocked, opens, rides, turned_open])

## The entrance door's peephole renders its corridor camera only while an eye
## is at the lens on the apartment side, and keeps the image afterwards.
func _test_door_viewer() -> void:
	var viewer: DoorViewer = _main.get_node(PROPS + "DoorEntrance/HingeOrigin/InteractableHinge/Leaf/Peephole")
	var cam := Camera3D.new()
	_main.add_child(cam)
	var saved := PlanarReflection.view_camera
	PlanarReflection.view_camera = cam
	var awake: Array[bool] = []
	# Far, 4 cm in front, 4 cm behind (corridor side), far again.
	for z: float in [1.5, 0.04, -0.12, 1.5]:
		cam.global_position = viewer.to_global(Vector3(0, 0, z))
		viewer.check_eye()
		awake.append(viewer.is_awake())
	PlanarReflection.view_camera = saved
	cam.queue_free()
	# The lens shader compiles (a parse error leaves no uniforms; the lens then isn't drawn).
	var uniforms := DoorViewer.SHADER.get_shader_uniform_list().map(func(u: Dictionary) -> String: return u.name)
	_check("door_viewer", str(awake) == "[false, true, false, false]" and uniforms.has("shown_view"),
			"camera renders far %s, eye at the lens %s, behind the door %s, far again %s; lens shader uniforms %s" % (
				awake + [uniforms]))
	# One eye looks through: centered, the dominant (left) one; the right one when clearly nearer the axis.
	var eyes: Array[int] = [DoorViewer.choose_eye(0.032, 0.032), DoorViewer.choose_eye(0.0, 0.063),
			DoorViewer.choose_eye(0.063, 0.0), DoorViewer.choose_eye(0.03, 0.02)]
	_check("door_viewer_one_eye", str(eyes) == "[0, 0, 1, 0]",
			"eye looking through (0 left, 1 right): centered %d, left at the lens %d, right at the lens %d, right 1 cm nearer %d" % eyes)


## The free edge of an open door can be grabbed at any height: its handle is
## off while closed, follows the hand along the edge while open, and holding
## it holds the hinge (XR Tools turns the hinge with it, as with the levers)
## and lets the hand through the leaf.
func _test_edge_grab(door: String) -> void:
	var hinge := _hinge(door)
	var leaf: Node3D = hinge.get_node("Leaf")
	var origin: Node3D = leaf.get_node("HandleOriginEdge")
	var handle: XRToolsInteractableHandle = origin.get_node("InteractableHandle")
	var body: PhysicsBody3D = leaf.get_node("DoorBody")
	var pickup: XRToolsFunctionPickup = _main.get_node("Player/LeftHand/CollisionHand/FunctionPickup")
	var controller: XRController3D = _main.get_node("Player/LeftHand")
	var hand: PhysicsBody3D = controller.get_node("CollisionHand")
	var saved := controller.global_transform
	var off_closed := not handle.enabled
	_set_hinge(door, 40.0)
	await _frames(3)
	var on_open := handle.enabled
	var edge := origin.position
	# The hand 12 cm off the open-side face, near the edge (closer would push the leaf).
	_place_palm(leaf.to_global(Vector3(edge.x, 1.75, edge.z + 0.12)))
	await _frames(10)
	var followed := origin.position.y
	pickup.global_transform = Transform3D(Basis.IDENTITY, handle.global_position)
	pickup._pick_up_object(handle)
	await _frames(1)
	var holds := hinge.grabbed_handles.has(handle) and hand.get_collision_exceptions().has(body)
	pickup.drop_object()
	controller.global_transform = saved
	await _frames(10)
	_set_hinge(door, 0.0)
	await _frames(2)
	var off_again := not handle.enabled
	_check(door + "_edge_grab", off_closed and on_open and absf(followed - 1.75) < 0.03 and holds and off_again,
			"edge handle off while closed %s, on while open %s; follows the hand to %.2f m (1.75); held, it holds the hinge and the hand passes the leaf %s; off again when closed %s" % [
				off_closed, on_open, followed, holds, off_again])


## A can dropped into a door bin of the open fridge stays in the bin.
func _test_fridge_door_bin() -> void:
	var door_body: Node3D = _main.get_node("Zones/Apartment/Props/Fridge/HingeOrigin/InteractableHinge/Leaf/DoorBody")
	_set_hinge("Fridge", 90.0)
	await _frames(3)
	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	# Middle bin (floor top at 0.866), in door-local coordinates.
	can.global_position = door_body.to_global(Vector3(0.3, 0.98, -0.045))
	await _frames(120)
	var local := door_body.to_local(can.global_position)
	can.queue_free()
	_set_hinge("Fridge", 0.0)
	await _frames(2)
	_check("Fridge_can_in_door_bin", local.y > 0.86 and local.y < 1.0 and local.z < 0.0 and local.z > -0.09,
			"can at door-local %s (bin floor 0.866, bin z -0.09..0)" % local.snappedf(0.01))


## A can dropped on the middle seat rests on the seat surface (0.44 m), and the
## throw pillows have settled on the sofa, not on the floor.
func _test_sofa() -> void:
	var root: Node3D = _main.get_node("Zones/Apartment/Props/Sofa")
	var local := await _drop_can_on_seat(root)
	_check("sofa_can_on_seat", absf(local.y - 0.50) < 0.05,
			"can center at local y %.2f (seat 0.44 + half can)" % local.y)
	var settled: Array[String] = []
	var ok := true
	for i in [1, 2]:
		var pillow: RigidBody3D = _main.get_node("Zones/Apartment/Props/SofaPillow%d" % i)
		var p := root.to_local(pillow.global_position)
		ok = ok and p.y > 0.45 and absf(p.x) < 1.05 and absf(p.z) < 0.5 and pillow.linear_velocity.length() < 0.05
		settled.append("%s at %s" % [pillow.name, p.snappedf(0.01)])
	_check("sofa_pillows_settled", ok, ", ".join(settled))


## The spare boucle sofa (kept for other apartments) isn't placed anywhere:
## spawn it away from the apartment and check its seat collision.
func _test_spare_sofa() -> void:
	var sofa: Node3D = (load("res://assets/props/sofa/sofa_boucle.tscn") as PackedScene).instantiate()
	_main.add_child(sofa)
	sofa.global_position = Vector3(30, 0, 30)
	await _frames(2)
	var local := await _drop_can_on_seat(sofa)
	sofa.queue_free()
	_check("sofa_boucle_can_on_seat", absf(local.y - 0.50) < 0.05,
			"can center at local y %.2f (seat 0.44 + half can)" % local.y)


func _drop_can_on_seat(root: Node3D) -> Vector3:
	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	can.global_position = root.to_global(Vector3(0, 0.7, 0.15))
	await _frames(120)
	var local := root.to_local(can.global_position)
	can.queue_free()
	return local


## The variants of a bedroom piece to test: ["A", "B"] while it's an A/B
## pair (ABSwitch), else [""] for the single placed piece.
func _variants(piece: String) -> Array[String]:
	if _main.get_node("Zones/Apartment/Props/" + piece) is ABSwitch:
		return ["A", "B"]
	return [""]


## The placed piece, or variant `v` of an A/B pair (switched to it).
func _piece(piece: String, v := "") -> Node3D:
	var node: Node3D = _main.get_node("Zones/Apartment/Props/" + piece)
	var sw := node as ABSwitch
	if not sw:
		return node
	if sw.variant != v:
		ABSwitch.toggle_all(get_tree())
	return sw.get_node(v)


## Test name suffix for variant `v` ("" for a single placed piece).
func _suffix(v: String) -> String:
	return "" if v.is_empty() else "_" + v


func _test_bedrooms() -> void:
	for variant in _variants("Bed"):
		await _test_bedroom(variant)


## Bedroom set (bed, wardrobe, nightstand), for variant `v` of an A/B pair or
## the placed pieces: the hidden variant has no collision, a can rests on the
## bed, the wardrobe doors' collision follows them, and the nightstand drawer
## slides, slides on after release, soft-closes and holds a can.
func _test_bedroom(v: String) -> void:
	var bed := _piece("Bed", v)
	await _frames(3)
	var space := _main.get_world_3d().direct_space_state
	var sw := _main.get_node("Zones/Apartment/Props/Bed") as ABSwitch
	if sw:
		# Only the shown bed collides.
		var hidden: Node3D = sw.get_node("B" if v == "A" else "A")
		var probe := PhysicsPointQueryParameters3D.new()
		probe.position = bed.to_global(Vector3(0, 0.25, 0.2))
		var owners: Array[String] = []
		for hit in space.intersect_point(probe):
			var collider := hit.collider as Node
			owners.append("shown" if bed.is_ancestor_of(collider) else ("hidden" if hidden.is_ancestor_of(collider) else collider.name))
		_check("bed%s_only_shown_collides" % _suffix(v), owners.has("shown") and not owners.has("hidden"), "colliders at the bed center: %s" % [owners])
	var q := PhysicsPointQueryParameters3D.new()

	var local := await _drop_can_on_seat(bed)
	_check("bed%s_can_on_bed" % _suffix(v), absf(local.y - 0.56) < 0.05, "can center at local y %.2f (sleeping surface 0.50 + half can)" % local.y)

	# Wardrobe doors: collision in front of the closed doors follows them.
	var wardrobe := _piece("Wardrobe", v)
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = wardrobe.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		var body: PhysicsBody3D = wardrobe.get_node("Door%s/HingeOrigin/InteractableHinge/Leaf/DoorBody" % side)
		q.position = wardrobe.to_global(Vector3(-0.4 if side == "Left" else 0.4, 1.0, 0.31))
		var hits_door := func() -> bool:
			return space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		var closed: bool = hits_door.call()
		hinge.hinge_position = 90.0
		hinge.hinge_moved.emit(90.0)
		await _frames(3)
		var opened: bool = hits_door.call()
		hinge.hinge_position = 0.0
		hinge.hinge_moved.emit(0.0)
		await _frames(2)
		_check("wardrobe%s_door_%s" % [_suffix(v), side.to_lower()], closed and not opened, "door body in front of the carcass: closed %s, open %s" % [closed, opened])

	# Nightstand drawer.
	var stand := _piece("Nightstand", v)
	var slider: XRToolsInteractableSlider = stand.get_node("Drawer/SliderOrigin/InteractableSlider")
	var drawer: PhysicsBody3D = stand.get_node("Drawer/SliderOrigin/InteractableSlider/Leaf/DrawerBody")
	var swing: SliderSwing = stand.get_node("Drawer/Swing")
	q.position = stand.to_global(Vector3(0, 0.45, 0.19))
	var drawer_hit := func() -> bool:
		return space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == drawer)
	var closed_hit: bool = drawer_hit.call()
	slider.move_slider(0.25)
	await _frames(3)
	var open_hit: bool = drawer_hit.call()
	_check("nightstand%s_drawer_collision" % _suffix(v), closed_hit and not open_hit, "drawer front at the closed spot: closed %s, open %s" % [closed_hit, open_hit])

	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	can.global_position = drawer.to_global(Vector3(0, 0.12, -0.19))
	await _frames(120)
	var in_drawer := drawer.to_local(can.global_position)
	can.queue_free()
	_check("nightstand%s_can_in_drawer" % _suffix(v), in_drawer.y > 0.0 and in_drawer.y < 0.12 and in_drawer.z < -0.03 and in_drawer.z > -0.36,
			"can at drawer-local %s" % in_drawer.snappedf(0.01))

	# Pushed shut at 0.6 m/s from 0.25 m it slides on and closes; a slow
	# release at 1 cm soft-closes; pulled out at 0.4 m/s it slides on.
	slider.move_slider(0.10)
	slider.grabbed.emit(slider)
	var start := Time.get_ticks_usec()
	for i in 10:
		await get_tree().physics_frame
		slider.move_slider(0.10 + 0.4 * (Time.get_ticks_usec() - start) / 1e6)
	var released_at := slider.slider_position
	slider.released.emit(slider)
	await _frames(120)
	var coasted := slider.slider_position
	slider.move_slider(0.01)
	slider.released.emit(slider)
	await _frames(90)
	var soft_closed := slider.slider_position
	_check("nightstand%s_drawer_swing" % _suffix(v), coasted > released_at + 0.02 and swing.get_velocity() == 0.0 and soft_closed < 0.001,
			"released at %.3f m going 0.4 m/s, rested at %.3f m; let go at 1 cm, ended at %.4f m" % [released_at, coasted, soft_closed])


## The A/B panel: a fingertip pressing its button flips an ABSwitch (and the
## hidden variant is disabled); a second press flips back. Built away from the
## apartment, so it runs with or without A/B pairs placed.
## An ABPanel in the zone has something to flip: a panel without any ABSwitch
## clicks but stays on "A" (the first viewport A/B was generated that way).
func _test_ab_panel_has_switches() -> void:
	var zones := _main.get_node("Zones")
	var panels := 0
	var switches := 0
	for node in zones.find_children("*", "Node3D", true, false):
		if node is ABPanel:
			panels += 1
		elif node is ABSwitch:
			switches += 1
	_check("ab_panel_has_switches", panels == 0 or switches > 0, "%d panel(s), %d switch(es)" % [panels, switches])


func _test_ab_panel() -> void:
	var sw := ABSwitch.new()
	for name in ["A", "B"]:
		var body := StaticBody3D.new()
		body.name = name
		var shape := CollisionShape3D.new()
		shape.shape = BoxShape3D.new()
		body.add_child(shape)
		sw.add_child(body)
	_main.add_child(sw)
	sw.global_position = Vector3(40, 1, 40)
	var panel: Node3D = (load("res://assets/props/ab_panel/ab_panel.tscn") as PackedScene).instantiate()
	_main.add_child(panel)
	panel.global_position = Vector3(40, 1.25, 44)
	var hand := _dummy_fingertip()
	var away := panel.to_global(Vector3(0, -0.04, 0.3))
	var press := panel.to_global(Vector3(0, -0.04, 0.05))
	hand.global_position = away
	await _frames(3)
	var before := sw.variant
	hand.global_position = press
	await _frames(5)
	var first := sw.variant
	var old_disabled := sw.get_node(before).process_mode == Node.PROCESS_MODE_DISABLED
	hand.global_position = away
	await _frames(5)
	hand.global_position = press
	await _frames(5)
	var second := sw.variant
	for node: Node in [hand, panel, sw]:
		node.queue_free()
	_check("ab_panel_press", first != before and second == before and old_disabled,
			"variant before %s, after one press %s (old one disabled %s), after a second press %s" % [before, first, old_disabled, second])


## An Environment A/B: flipping every switch applies the other variant's
## properties to the world's environment; flipping back restores them.
func _test_ab_environment() -> void:
	var env: Environment = (_main.get_node("Skyline/WorldEnvironment") as WorldEnvironment).environment
	var sw := ABEnvironment.new()
	sw.a = {"ssr_enabled": false, "ssr_max_steps": 64.0}
	sw.b = {"ssr_enabled": true, "ssr_max_steps": 8.0}
	_main.add_child(sw)
	var on_a := not env.ssr_enabled and env.ssr_max_steps == 64
	ABSwitch.toggle_all(get_tree())
	var on_b := env.ssr_enabled and env.ssr_max_steps == 8 and sw.variant == "B"
	ABSwitch.toggle_all(get_tree())
	var back := not env.ssr_enabled and env.ssr_max_steps == 64 and sw.variant == "A"
	sw.free()
	_check("ab_environment", on_a and on_b and back,
			"A applied %s, B applied %s, back to A %s" % [on_a, on_b, back])


## A small area on the Player Hands layer, like the rig's fingertips.
func _dummy_fingertip() -> Area3D:
	var tip := Area3D.new()
	tip.collision_layer = 131072
	tip.collision_mask = 0
	tip.monitoring = false
	var shape := CollisionShape3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.012
	shape.shape = sphere
	tip.add_child(shape)
	_main.add_child(tip)
	return tip


## Both hands carry a fingertip press area on the Player Hands layer, on the
## avatar's index finger tips (D-041).
func _test_fingertips() -> void:
	var found: Array[String] = []
	for side: String in ["Left", "Right"]:
		var tip := _main.get_node_or_null("Player/Avatar/Model/Armature/Skeleton3D/IndexTip%s/Fingertip" % side) as Area3D
		if tip and tip.collision_layer == 131072:
			found.append(side)
	_check("fingertip_areas", found == ["Left", "Right"], "fingertips on hands: %s" % [found])


## The eyes (D-050): straight ahead they look where the head does, converging
## in front of the face; a target far to the side turns them only to their
## limit; facing the bathroom mirror they look at their own image (eye
## contact, so the reflection looks back); the lids close on request.
## The player's own meshes draw after SSAO (transparent pass, no halos around
## the hands, D-055) and still cast shadows through a shadow-only copy each.
func _test_avatar_after_ssao() -> void:
	var skeleton := _avatar_skeleton("avatar_after_ssao")
	if skeleton == null:
		return
	var problems: Array[String] = []
	var visible := 0
	for node in skeleton.get_children():
		var mesh := node as MeshInstance3D
		if mesh == null or mesh.name in ["HeadMesh", "Collar"] or (mesh.name as String).ends_with("Shadow"):
			continue
		visible += 1
		var shadow := skeleton.get_node_or_null(NodePath(mesh.name + "Shadow")) as MeshInstance3D
		if shadow == null or shadow.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			problems.append("%s: no shadow-only copy" % mesh.name)
		if mesh.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			problems.append("%s casts shadows itself" % mesh.name)
		for i in mesh.mesh.get_surface_count():
			var mat := mesh.get_active_material(i) as BaseMaterial3D
			if mat and (mat.transparency != BaseMaterial3D.TRANSPARENCY_ALPHA or mat.depth_draw_mode != BaseMaterial3D.DEPTH_DRAW_ALWAYS):
				problems.append("%s surface %d is in the opaque pass" % [mesh.name, i])
			var cast := shadow.get_active_material(i) as BaseMaterial3D if shadow else null
			if cast and cast.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				problems.append("%sShadow surface %d is transparent (casts nothing)" % [mesh.name, i])
	_check("avatar_after_ssao", visible > 0 and problems.is_empty(),
			"%d first-person meshes; %s" % [visible, ", ".join(problems) if problems else "all after SSAO with shadow-only copies"])


func _test_avatar_eyes() -> void:
	var skeleton := _avatar_skeleton("avatar_eyes")
	if skeleton == null:
		return
	var eyes := skeleton.get_node_or_null("Eyes") as AvatarEyes
	var bones: Array[int] = [skeleton.find_bone("LeftEye"), skeleton.find_bone("RightEye")]
	if eyes == null or bones.has(-1):
		_check("avatar_eyes", false, "no Eyes modifier under the skeleton or no LeftEye/RightEye bones")
		return
	var body := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	# Back to the living room window: no reflection in view.
	body.teleport(Transform3D(Basis(Vector3.UP, PI), HOME.origin))
	await _frames(30)
	await skeleton.skeleton_updated
	var forward := -camera.global_basis.z
	var aim := _eye_aim_error(skeleton, bones, eyes.gaze_target)
	var ahead := camera.global_position + forward * eyes.focus_distance
	_check("avatar_eyes_ahead", eyes.gaze_source == &"ahead" and aim < 1.0 and eyes.gaze_target.distance_to(ahead) < 0.01,
			"source %s, eyes %.2f degrees off their target, target %.3f m from %.1f m ahead" % [eyes.gaze_source, aim, eyes.gaze_target.distance_to(ahead), eyes.focus_distance])

	eyes.look_target = camera.global_position + camera.global_basis.x * 1.0 + forward * 0.2
	await _frames(10)
	await skeleton.skeleton_updated
	var turn: Array[float] = []
	for i in bones.size():
		turn.append(rad_to_deg(_eye_dir(skeleton, bones[i]).angle_to(forward)))
	eyes.look_target = Vector3.INF
	_check("avatar_eyes_limit", absf(turn[0] - eyes.max_yaw) < 2.0 and absf(turn[1] - eyes.max_yaw) < 2.0,
			"a target 80 degrees to the side turns the eyes %.1f / %.1f degrees (limit %.0f)" % [turn[0], turn[1], eyes.max_yaw])

	# Facing the bathroom mirror (as the skyline test's reflection view).
	body.teleport(Transform3D(Basis(Vector3.UP, PI), Vector3(1.4, 0.0, 5.2)))
	await _frames(40)
	await skeleton.skeleton_updated
	var mirror := _main.get_node("Zones/Apartment/Props/BathMirror/Reflection") as PlanarReflection
	var plane := mirror.plane()
	var eye := camera.global_position
	var image := eye - plane.basis.z * (2.0 * (eye - plane.origin).dot(plane.basis.z))
	aim = _eye_aim_error(skeleton, bones, image)
	_check("avatar_eyes_mirror", eyes.gaze_source == &"contact" and eyes.gaze_target.distance_to(image) < 0.01 and aim < 1.0,
			"source %s, target %.3f m from the face's image, eyes %.2f degrees off it" % [eyes.gaze_source, eyes.gaze_target.distance_to(image), aim])

	var mesh := skeleton.find_child("HeadMesh", true, false) as MeshInstance3D
	var shapes: Array[int] = [-1, -1]
	if mesh:
		shapes = [mesh.find_blend_shape_by_name(&"BlinkLeft"), mesh.find_blend_shape_by_name(&"BlinkRight")]
	eyes.set_lids(1.0, 0.25)
	await skeleton.skeleton_updated
	var lids: Array[float] = [-1.0, -1.0]
	for i in 2:
		if shapes[i] >= 0:
			lids[i] = mesh.get_blend_shape_value(shapes[i])
	eyes.set_lids(0.0, 0.0)
	await skeleton.skeleton_updated
	var reopened := shapes[0] >= 0 and mesh.get_blend_shape_value(shapes[0]) == 0.0
	_check("avatar_eyes_lids", is_equal_approx(lids[0], 1.0) and is_equal_approx(lids[1], 0.25) and reopened,
			"BlinkLeft %.2f (want 1), BlinkRight %.2f (want 0.25), open again %s" % [lids[0], lids[1], reopened])
	camera.position = saved_camera
	await _frames(2)


## An eye bone's gaze (world space): its rest gaze is the glb's forward, +Z.
func _eye_dir(skeleton: Skeleton3D, bone: int) -> Vector3:
	var local := skeleton.get_bone_global_rest(bone).basis.inverse() * Vector3.BACK
	return (skeleton.global_basis * skeleton.get_bone_global_pose(bone).basis * local).normalized()


## The larger angle (degrees) between an eye's gaze and the line to `target`.
func _eye_aim_error(skeleton: Skeleton3D, bones: Array[int], target: Vector3) -> float:
	var worst := 0.0
	for bone in bones:
		var origin := skeleton.global_transform * skeleton.get_bone_global_pose(bone).origin
		worst = maxf(worst, rad_to_deg(_eye_dir(skeleton, bone).angle_to(target - origin)))
	return worst


## The avatar skeleton, or null after failing check `name`.
func _avatar_skeleton(name: String) -> Skeleton3D:
	var skeleton := _main.get_node_or_null(SKELETON) as Skeleton3D
	if skeleton == null:
		_check(name, false, "no avatar skeleton at " + SKELETON)
	return skeleton


## Hands where a seated player holds them: in reach, in front of the chest.
## Returns the controllers' transforms for _restore_hands().
func _hands_forward() -> Array[Transform3D]:
	var camera := get_viewport().get_camera_3d()
	var saved: Array[Transform3D] = []
	for side in SIDES:
		var controller := _main.get_node("Player/%sHand" % side) as Node3D
		saved.append(controller.global_transform)
		var x := -0.2 if side == "Left" else 0.2
		controller.global_transform = Transform3D(controller.global_basis, camera.global_transform * Vector3(x, -0.45, -0.3))
	await _frames(5)
	return saved


func _restore_hands(saved: Array[Transform3D]) -> void:
	for i in SIDES.size():
		(_main.get_node("Player/%sHand" % SIDES[i]) as Node3D).global_transform = saved[i]
	await _frames(2)


## The avatar's hand bones follow the AvatarHand targets, and each hand's
## controls curl its own fingers, each finger on its own (D-039, D-041); then
## the arm IK for that hand (same posed hands).
func _test_hand_rig() -> void:
	var skeleton := _avatar_skeleton("hand_rig")
	if skeleton == null:
		return
	var saved: Array[Transform3D] = await _hands_forward()
	for side: String in ["Left", "Right"]:
		var hand := _main.get_node_or_null("Player/%sHand/CollisionHand/Hand" % side) as AvatarHand
		if hand == null or hand.target == null:
			_check("hand_rig_%s" % side.to_lower(), false, "no AvatarHand with a target at Player/%sHand/CollisionHand/Hand" % side)
			continue
		var bone := skeleton.find_bone("%sHand" % side)
		var index := skeleton.find_bone("%sIndexTip" % side)
		var middle := skeleton.find_bone("%sMiddleTip" % side)
		# x: index tip, y: middle tip travel from the open pose, in the hand bone's frame
		var open: Array[Vector3] = []
		var moves: Array[Vector2] = []
		var drift := 0.0
		for forced: Vector2 in [Vector2(0, 0), Vector2(0, 1), Vector2(1, 0)]:
			hand.force_grip_trigger(forced.x, forced.y)
			await _frames(3)
			await skeleton.skeleton_updated
			var h := skeleton.get_bone_global_pose(bone)
			var tips: Array[Vector3] = [h.affine_inverse() * skeleton.get_bone_global_pose(index).origin, h.affine_inverse() * skeleton.get_bone_global_pose(middle).origin]
			if open.is_empty():
				open = tips
				drift = (skeleton.global_transform * h.origin).distance_to(hand.target.global_position)
			moves.append(Vector2(tips[0].distance_to(open[0]), tips[1].distance_to(open[1])))
		hand.force_grip_trigger()
		_check("hand_rig_%s_follows" % side.to_lower(), drift < 0.001, "hand bone %.4f m from its target" % drift)
		_check("hand_rig_%s_fingers_independent" % side.to_lower(),
				moves[1].x > 0.02 and moves[1].y < 0.002 and moves[2].x < 0.002 and moves[2].y > 0.02,
				"index / middle tip travel: trigger %s, grip %s" % [moves[1].snappedf(0.001), moves[2].snappedf(0.001)])
		await _test_arm_ik(side, skeleton)
	await _restore_hands(saved)


## The arm reaches the hand target from the shoulder without stretching, the
## elbow below the arm line, and wrist roll moves only the twist bone (headset
## bug: upper arm and forearm flipped half a turn at about -110 degrees, D-040).
func _test_arm_ik(side: String, skeleton: Skeleton3D) -> void:
	await skeleton.skeleton_updated
	var bones: Array[Transform3D] = []
	var rests: Array[Transform3D] = []
	for part: String in ["UpperArm", "LowerArm", "Hand"]:
		var bone := skeleton.find_bone("%s%s" % [side, part])
		bones.append(skeleton.get_bone_global_pose(bone))
		rests.append(skeleton.get_bone_global_rest(bone))
	var to_world := skeleton.global_transform
	var stretch := absf(bones[0].origin.distance_to(bones[1].origin) - rests[0].origin.distance_to(rests[1].origin)) \
			+ absf(bones[1].origin.distance_to(bones[2].origin) - rests[1].origin.distance_to(rests[2].origin))
	var sag := ((to_world * bones[0].origin + to_world * bones[2].origin) * 0.5).y - (to_world * bones[1].origin).y
	_check("arm_ik_%s" % side.to_lower(), stretch < 0.001 and sag > 0.0,
			"bone stretch %.4f m, elbow %.3f m below the arm line" % [stretch, sag])

	var controller := _main.get_node("Player/%sHand" % side) as Node3D
	var saved := controller.global_transform
	var axis := (to_world * bones[2].origin - to_world * bones[1].origin).normalized()
	var pivot := to_world * bones[2].origin
	var parts: Array[int] = [skeleton.find_bone("%sUpperArm" % side), skeleton.find_bone("%sLowerArm" % side), skeleton.find_bone("%sLowerArmTwist" % side)]
	var worst: Array[float] = [0.0, 0.0, 0.0]
	var last: Array[Quaternion] = []
	for step in range(-30, 31):
		controller.global_transform = Transform3D(Basis(axis, deg_to_rad(step * 5.0)), Vector3.ZERO).translated_local(-pivot).translated(pivot) * saved
		await get_tree().physics_frame
		await skeleton.skeleton_updated
		var now: Array[Quaternion] = []
		for i in parts.size():
			now.append((to_world * skeleton.get_bone_global_pose(parts[i])).basis.get_rotation_quaternion())
			if last:
				worst[i] = maxf(worst[i], rad_to_deg(now[i].angle_to(last[i])))
		last = now
	controller.global_transform = saved
	await _frames(2)
	_check("arm_ik_%s_roll" % side.to_lower(), worst[0] < 2.0 and worst[1] < 2.0 and worst[2] < 6.0,
			"largest change per 5 degrees of wrist roll: upper arm %.1f, forearm %.1f, twist %.1f degrees" % worst)


## The body stands under the headset: eyes at the camera, feet on the floor,
## and crouching (a lower head) bends the knees instead of sinking the feet.
## (Hands posed in front, as for the hand rig.)
func _test_body_ik() -> void:
	var skeleton := _avatar_skeleton("body_ik")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var ik := skeleton.get_node("BodyIK") as BodyIK
	var camera := get_viewport().get_camera_3d()
	var ground := _main.get_node("Player/PlayerBody") as Node3D
	var head := skeleton.find_bone("Head")
	var feet: Array[int] = [skeleton.find_bone("LeftFoot"), skeleton.find_bone("RightFoot")]
	var foot_rest := skeleton.get_bone_global_rest(feet[0]).origin.y
	var eye_in_head := skeleton.get_bone_global_rest(head).affine_inverse() * ik.eye_rest
	var saved := camera.position
	for case: Array in [["standing", 0.0], ["crouching", -0.5]]:
		camera.position = saved + Vector3(0.0, case[1], 0.0)
		await _frames(90)
		await skeleton.skeleton_updated
		var to_world := skeleton.global_transform
		var eye := to_world * skeleton.get_bone_global_pose(head) * eye_in_head
		var floor_y := ground.global_position.y
		var foot_y: Array[float] = []
		for foot in feet:
			foot_y.append((to_world * skeleton.get_bone_global_pose(foot).origin).y - floor_y - foot_rest + ik.sole_height)
		var thigh := skeleton.get_bone_global_pose(skeleton.find_bone("LeftUpperLeg")).basis.y
		var shin := skeleton.get_bone_global_pose(skeleton.find_bone("LeftLowerLeg")).basis.y
		var bend := rad_to_deg(thigh.angle_to(shin))
		var eye_off := eye.distance_to(camera.global_position)
		_check("body_ik_%s" % case[0], eye_off < 0.03 and absf(foot_y[0]) < 0.01 and absf(foot_y[1]) < 0.01 and (case[1] == 0.0 or bend > 30.0),
				"eyes %.3f m from the camera, feet %.3f / %.3f m off the floor, knee bent %.0f degrees" % [eye_off, foot_y[0], foot_y[1], bend])
	camera.position = saved
	await _frames(2)
	await _restore_hands(hands)


## Walking and sprinting step the feet: a planted foot never slides (a lagging
## hip drop used to drag it, D-043), the feet keep up with the body, lift on
## an arc, and settle after stopping (D-042).
## Starts at the player's start spot facing -Z (the window wall 2.6 m ahead).
func _test_walk() -> void:
	var skeleton := _avatar_skeleton("avatar_walk")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var ground := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var start := ground.global_transform
	var forward := -start.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	var feet: Array[int] = [skeleton.find_bone("LeftFoot"), skeleton.find_bone("RightFoot")]
	var rest_y := skeleton.get_bone_global_rest(feet[0]).origin.y - (skeleton.get_node("BodyIK") as BodyIK).sole_height
	var ik := skeleton.get_node("BodyIK") as BodyIK
	# Eyes at the avatar's standing height (the headset's calibrated 1.8 m):
	# straight legs, so steps need the hip drop.
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	await _frames(60)  # let the body land after the crouch test
	for case: Array in [["walk", 2.0], ["sprint", 4.0]]:
		var per_frame: float = case[1] / 90.0
		var frames := int(2.4 / per_frame)
		var floor_y := ground.global_position.y
		var last: Array[Vector3] = []
		var first: Array[Vector3] = []
		var sliding := 0
		var lift := 0.0
		var steps := [0, 0]
		var lifted := [false, false]
		var planted := [true, true]
		var worst_slip := 0.0
		for frame in frames + 90:
			if frame < frames:
				var t := ground.global_transform
				t.origin += forward * per_frame
				ground.teleport(t)
			await get_tree().physics_frame
			await skeleton.skeleton_updated
			var now: Array[Vector3] = []
			for foot in feet:
				now.append(skeleton.global_transform * skeleton.get_bone_global_pose(foot).origin)
			if first.is_empty():
				first = now
			if last:
				for i in 2:
					var height := now[i].y - floor_y - rest_y
					lift = maxf(lift, height)
					var up := height > 0.01
					if up and not lifted[i]:
						steps[i] += 1
					lifted[i] = up
					var flat := Vector2(now[i].x - last[i].x, now[i].z - last[i].z).length()
					if not ik.steps.stepping(i) and planted[i] and flat > 0.002:
						sliding += 1
						worst_slip = maxf(worst_slip, flat)
					planted[i] = not ik.steps.stepping(i)
			last = now
		var advanced: Array[float] = []
		for i in 2:
			advanced.append((last[i] - first[i]).dot(forward))
		var slip_ok := sliding == 0
		_check("avatar_%s_steps" % case[0], steps[0] >= 2 and steps[1] >= 2 and slip_ok and lift > 0.03 and absf(advanced[0] - 2.4) < 0.15 and absf(advanced[1] - 2.4) < 0.15,
				"%.1f m/s: steps %d / %d, frames a planted foot slid %d (worst %.1f mm), lift %.3f m, feet advanced %.2f / %.2f m (body 2.4 m, the window wall is 2.6 m ahead)" % [case[1], steps[0], steps[1], sliding, worst_slip * 1000.0, lift, advanced[0], advanced[1]])
		ground.teleport(start)
		await _frames(30)
	camera.position = saved_camera
	await _frames(30)
	await _restore_hands(hands)


## Seated on the sofa, the hips rest on the cushion and the feet stand forward
## of it on the floor, knees bent (D-042). Leaves the player standing at the
## sofa (the next test's _reset_rig() brings it back).
func _test_sit_pose() -> void:
	var skeleton := _avatar_skeleton("avatar_sit_pose")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var player := _main.get_node("Player") as ArcologyPlayer
	var seat := _main.get_node("Zones/Apartment/Seats/SofaSeat") as Seat
	await player.sit(seat)
	await _frames(20)
	await skeleton.skeleton_updated
	var w := skeleton.global_transform
	var hips := w * skeleton.get_bone_global_pose(skeleton.find_bone("Hips")).origin
	var foot := w * skeleton.get_bone_global_pose(skeleton.find_bone("LeftFoot")).origin
	var thigh := skeleton.get_bone_global_pose(skeleton.find_bone("LeftUpperLeg")).basis.y
	var shin := skeleton.get_bone_global_pose(skeleton.find_bone("LeftLowerLeg")).basis.y
	var facing := -seat.sit_point.global_basis.z
	var ahead := (foot - hips).dot(facing)
	var bend := rad_to_deg(thigh.angle_to(shin))
	# The knees overhang the cushion's front edge, so the shins hang in front
	# of the sofa, not through it (headset bug: the shins clipped the front).
	var sofa := _main.get_node("Zones/Apartment/Props/Sofa") as Node3D
	var edge := sofa.global_transform * Vector3(0.0, 0.44, 0.445)
	var overhang: Array[float] = []
	for side: String in ["Left", "Right"]:
		var knee := w * skeleton.get_bone_global_pose(skeleton.find_bone("%sLowerLeg" % side)).origin
		overhang.append((knee - edge).dot(facing))
	await player.stand()
	await _frames(20)
	await _restore_hands(hands)
	_check("avatar_sit_pose", absf(hips.y - 0.52) < 0.08 and ahead > 0.3 and bend > 60.0 and bend < 120.0 and foot.y < 0.15 and overhang.min() > 0.03,
			"hips at %.2f m (cushion 0.44), feet %.2f m ahead, knee bent %.0f degrees, foot at %.2f m, knees %.2f / %.2f m past the cushion edge" % [hips.y, ahead, bend, foot.y, overhang[0], overhang[1]])


## The coat skirt hangs calm when standing, swings when walking without
## going through the legs or blowing up, and lies on the seat when sitting
## instead of passing through it; the belt's cuffs and passkey dangle and swing
## without sinking into the thigh (D-044).
func _test_coat_springs() -> void:
	var skeleton := _avatar_skeleton("avatar_coat")
	if skeleton == null:
		return
	if skeleton.get_node_or_null("Springs") == null:
		_check("avatar_coat", false, "no Springs under the avatar skeleton")
		return
	var hands: Array[Transform3D] = await _hands_forward()
	# Eyes at the avatar's standing height (the headset's calibrated 1.8 m).
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	var hips := skeleton.find_bone("Hips")
	var joints: Array[int] = []
	for chain: String in ["FrontLeft", "FrontRight", "SideLeft", "SideRight", "BackLeft", "BackRight"]:
		for n in [2, 3, 4]:
			joints.append(skeleton.find_bone("Coat%s%d" % [chain, n]))
	var legs: Array[Array] = []
	for side: String in SIDES:
		legs.append([skeleton.find_bone("%sUpperLeg" % side), skeleton.find_bone("%sLowerLeg" % side), 0.07])
		legs.append([skeleton.find_bone("%sLowerLeg" % side), skeleton.find_bone("%sFoot" % side), 0.055])
	# Rest relation of each joint to the hips.
	var hips_rest := skeleton.get_bone_global_rest(hips)
	var rest_local: Array[Vector3] = []
	for j in joints:
		rest_local.append(hips_rest.affine_inverse() * skeleton.get_bone_global_rest(j).origin)

	await _frames(60)
	await skeleton.skeleton_updated
	var hang := _coat_deviation(skeleton, hips, joints, rest_local)

	var ground := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var start := ground.global_transform
	var forward := -start.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	# The items' tips (bone tail: the tail lengths in AvatarSprings).
	var items: Array[int] = [skeleton.find_bone("BeltCuffs2"), skeleton.find_bone("BeltPasskey1")]
	var tips: Array[Vector3] = [Vector3(0, 0.07, 0), Vector3(0, 0.09, 0)]
	var items_rest: Array[Vector3] = []
	for i in items.size():
		items_rest.append(hips_rest.affine_inverse() * (skeleton.get_bone_global_rest(items[i]) * tips[i]))
	var thigh: Array[int] = [skeleton.find_bone("RightUpperLeg"), skeleton.find_bone("RightLowerLeg")]
	var item_swing := 0.0
	var item_depth := 0.0
	var swing := 0.0
	var trail := 0.0  # back panels only: the legs don't push them much
	var depth := 0.0
	var finite := true
	for frame in 108 + 60:
		if frame < 108:
			var t := ground.global_transform
			t.origin += forward * (2.0 / 90.0)
			ground.teleport(t)
		await get_tree().physics_frame
		await skeleton.skeleton_updated
		swing = maxf(swing, _coat_deviation(skeleton, hips, joints, rest_local))
		trail = maxf(trail, _coat_deviation(skeleton, hips, joints.slice(12), rest_local.slice(12)))
		var ta := skeleton.get_bone_global_pose(thigh[0]).origin
		var tb := skeleton.get_bone_global_pose(thigh[1]).origin
		var hips_now := skeleton.get_bone_global_pose(hips)
		for i in items.size():
			var p := skeleton.get_bone_global_pose(items[i]) * tips[i]
			finite = finite and p.is_finite()
			item_swing = maxf(item_swing, p.distance_to(hips_now * items_rest[i]))
			item_depth = maxf(item_depth, 0.095 + 0.015 - p.distance_to(Geometry3D.get_closest_point_to_segment(p, ta, tb)))
		for j in joints:
			var p := skeleton.get_bone_global_pose(j).origin
			finite = finite and p.is_finite()
			for leg: Array in legs:
				var a := skeleton.get_bone_global_pose(leg[0]).origin
				var b := skeleton.get_bone_global_pose(leg[1]).origin
				var closest := Geometry3D.get_closest_point_to_segment(p, a, b)
				depth = maxf(depth, float(leg[2]) + 0.03 - p.distance_to(closest))
	ground.teleport(start)
	await _frames(30)

	var player := _main.get_node("Player") as ArcologyPlayer
	var seat := _main.get_node("Zones/Apartment/Seats/SofaSeat") as Seat
	await player.sit(seat)
	await _frames(60)
	await skeleton.skeleton_updated
	var lowest := INF
	for i in joints.size():
		if i >= 6:  # side and back chains rest on the seat; the front hangs past the knees
			lowest = minf(lowest, (skeleton.global_transform * skeleton.get_bone_global_pose(joints[i]).origin).y)
	await player.stand()
	camera.position = saved_camera
	await _frames(30)
	await _restore_hands(hands)
	_check("avatar_belt_items", finite and item_swing > 0.005 and item_swing < 0.2 and item_depth < 0.02,
			"cuffs and passkey swing %.3f m while walking, deepest into the thigh %.3f m" % [item_swing, item_depth])
	_check("avatar_coat", finite and hang < 0.08 and swing < 0.5 and trail > 0.03 and trail < 0.25 and depth < 0.03 and lowest > 0.40,
			"standing off rest %.3f m, walking: skirt off rest %.3f m (legs push the front), back trails %.3f m, deepest into a leg %.3f m; seated side/back skirt lowest at %.2f m (cushion 0.44)" % [hang, swing, trail, depth, lowest])


## Largest distance of the coat joints from where the rest pose puts them
## relative to the hips.
func _coat_deviation(skeleton: Skeleton3D, hips: int, joints: Array[int], rest_local: Array[Vector3]) -> float:
	var hips_pose := skeleton.get_bone_global_pose(hips)
	var worst := 0.0
	for i in joints.size():
		worst = maxf(worst, (hips_pose * rest_local[i]).distance_to(skeleton.get_bone_global_pose(joints[i]).origin))
	return worst


func _test_lamp_switches() -> void:
	for variant in _variants("Nightstand"):
		await _test_lamp_switch(variant)


## Pressing the lamp's switch turns its light and glow off, pressing again on.
func _test_lamp_switch(v: String) -> void:
	var stand := _piece("Nightstand", v)
	await _frames(3)
	var button: Node3D = stand.get_node("LampSwitchButton")
	var light: Light3D = stand.get_node("LampLight")
	var tip := _dummy_fingertip()
	var away := button.global_position + Vector3(0, 0.2, 0)
	tip.global_position = away
	await _frames(3)
	var before := light.visible
	tip.global_position = button.global_position
	await _frames(4)
	var after_one := light.visible
	tip.global_position = away
	await _frames(4)
	tip.global_position = button.global_position
	await _frames(4)
	var after_two := light.visible
	tip.queue_free()
	_check("lamp%s_switch" % _suffix(v), before and not after_one and after_two,
			"lamp light: before %s, after one press %s, after two %s" % [before, after_one, after_two])


## Left open, the fridge beeps after its delay (shortened here) and stops
## when closed.
func _test_fridge_alarm() -> void:
	var alarm: OpenAlarm = _main.get_node("Zones/Apartment/Props/Fridge/OpenAlarm")
	var saved := alarm.delay
	alarm.delay = 0.3
	_set_hinge("Fridge", 45.0)
	await _frames(12)
	var early := alarm.is_ringing()
	await _frames(30)
	var ringing := alarm.is_ringing()
	_set_hinge("Fridge", 0.0)
	await _frames(2)
	var after_close := alarm.is_ringing()
	alarm.delay = saved
	_check("fridge_alarm", not early and ringing and not after_close,
			"ringing at 0.13 s %s, at 0.47 s %s, after closing %s" % [early, ringing, after_close])


## The wardrobe with an interior (variant with drawers, box and hangers):
## drawers slide and carry their collision, the hangers start hung on the
## rail, a hanger dropped near the rail hangs again, and one dropped away
## from it falls; the box and lid rest on the shelf.
func _test_wardrobe_interior() -> void:
	var v := ""
	var sw := _main.get_node("Zones/Apartment/Props/Wardrobe") as ABSwitch
	if sw:
		for candidate in ["A", "B"]:
			if sw.get_node(candidate).has_node("Rail"):
				v = candidate
	var w := _piece("Wardrobe", v)
	if not w.has_node("Rail"):
		_check("wardrobe_interior", false, "the wardrobe has no interior (rail, drawers)")
		return
	await _frames(30)
	var space := _main.get_world_3d().direct_space_state

	# Doors open so the drawers can come out.
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = w.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		hinge.hinge_position = 95.0
		hinge.hinge_moved.emit(95.0)
	await _frames(3)
	for drawer_node in w.get_children().filter(func(n: Node) -> bool: return n.name.begins_with("Drawer")):
		var side := (drawer_node.name as String).trim_prefix("Drawer")
		var slider: XRToolsInteractableSlider = drawer_node.get_node("SliderOrigin/InteractableSlider")
		var body: PhysicsBody3D = drawer_node.get_node("SliderOrigin/InteractableSlider/Leaf/DrawerBody")
		var q := PhysicsPointQueryParameters3D.new()
		q.position = body.to_global(Vector3(0, 0.12, -0.009))
		var front_at := q.position
		slider.move_slider(0.3)
		await _frames(3)
		q.position = front_at
		var still_there := space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		q.position = front_at + w.global_basis.z * 0.3
		var moved_there := space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		slider.move_slider(0.0)
		await _frames(2)
		_check("wardrobe_drawer_%s" % side.to_lower(), not still_there and moved_there,
				"drawer front collision: left the closed spot %s, followed to 0.3 m %s" % [not still_there, moved_there])

	var rail: HangingRail = w.get_node("Rail")
	var hook_y := rail.start.y + rail.radius
	var hangers := w.get_children().filter(func(n: Node) -> bool: return n is XRToolsPickable and n.has_node("RailHanger"))
	var hung := 0
	for i in hangers.size():
		var hanger: XRToolsPickable = w.get_node("Hanger%d" % i)
		var hook := w.to_local(hanger.global_position)
		if hanger.freeze and absf(hook.y - hook_y) < 0.005 and absf(hook.z - rail.start.z) < 0.005:
			hung += 1
	_check("wardrobe_hangers_hung", hung == hangers.size() and hung > 0, "%d of %d hangers hang on the rail" % [hung, hangers.size()])

	var hanger0: XRToolsPickable = w.get_node("Hanger0")
	var rail_hanger: RailHanger = hanger0.get_node("RailHanger")
	hanger0.freeze = false
	hanger0.global_position = w.to_global(Vector3(rail.start.x + 0.2, hook_y - 0.04, 0.05))
	hanger0.dropped.emit(hanger0)
	await _frames(2)
	var rehung := rail_hanger.is_hung() and absf(w.to_local(hanger0.global_position).y - hook_y) < 0.005
	hanger0.freeze = false
	hanger0.global_position = w.to_global(Vector3(0.1, 1.2, 0.5))
	hanger0.dropped.emit(hanger0)
	await _frames(30)
	var fell := not hanger0.freeze and w.to_local(hanger0.global_position).y < 1.15
	_check("wardrobe_rehang", rehung and fell, "dropped near the rail hangs %s, dropped away from it falls %s" % [rehung, fell])

	var box: Node3D = w.get_node("StorageBox")
	var lid: Node3D = w.get_node("StorageBoxLid")
	var box_y := w.to_local(box.global_position).y
	var lid_above := w.to_local(lid.global_position).y - box_y
	var wall: CollisionShape3D = box.get_node("WallLeft")
	var rim := wall.position.y + (wall.shape as BoxShape3D).size.y / 2.0
	var skirt := ((lid.get_node("SkirtLeft") as CollisionShape3D).shape as BoxShape3D).size.y
	var expect_lid := rim - skirt
	_check("wardrobe_box_and_lid", absf(lid_above - expect_lid) < 0.012 and (box as RigidBody3D).linear_velocity.length() < 0.05,
			"box resting at %.3f, lid %.3f above it (skirt over the rim: %.3f)" % [box_y, lid_above, expect_lid])
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = w.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		hinge.hinge_position = 0.0
		hinge.hinge_moved.emit(0.0)


## The bed's collision follows the bedding: a small sphere swept down onto a
## pillow stops on the pillow (about 0.58-0.72 m), not on the hidden block
## (0.44 m) under the duvet. (A dropped can tips off the sloped pillow and
## rolls onto the sheet, which is fine.)
func _test_bed_bedding_collision() -> void:
	var bed := _piece("Bed")
	var space := _main.get_world_3d().direct_space_state
	var sphere := SphereShape3D.new()
	sphere.radius = 0.03
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = sphere
	query.collision_mask = 1
	var heights: Array[String] = []
	var ok := true
	for spot: Vector3 in [Vector3(0.4, 1.2, -0.7), Vector3(-0.4, 1.2, -0.7)]:
		query.transform = Transform3D(Basis.IDENTITY, bed.to_global(spot))
		query.motion = Vector3(0, -1.0, 0)
		var fraction := space.cast_motion(query)[0]
		var rest_y: float = spot.y - 1.0 * fraction - sphere.radius
		ok = ok and rest_y > 0.55
		heights.append("%.2f" % rest_y)
	_check("bed_pillow_collision", ok, "sphere stops at local y %s over the pillows (hidden block at 0.44)" % ", ".join(heights))


## The runner-up variants kept for other apartments load, and their static
## collision works (spawned away from the apartment).
func _test_spare_variants() -> void:
	var results: Array[String] = []
	var ok := true
	for path in ["res://assets/props/bed/bed_padded.tscn", "res://assets/props/wardrobe/wardrobe_lit.tscn",
			"res://assets/props/nightstand/nightstand_square.tscn"]:
		var scene := load(path) as PackedScene
		if not scene:
			ok = false
			results.append("%s: failed to load" % path.get_file())
			continue
		var node: Node3D = scene.instantiate()
		_main.add_child(node)
		node.global_position = Vector3(-30, 0, -30)
		await _frames(2)
		# A can dropped on top lands on its collision, not on the ground.
		var top := 0.50 if path.contains("bed") else (2.10 if path.contains("wardrobe") else 0.55)
		var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
		_main.add_child(can)
		can.global_position = node.to_global(Vector3(0.1, top + 0.3, 0.1))
		await _frames(120)
		var y := node.to_local(can.global_position).y
		can.queue_free()
		node.queue_free()
		var landed := absf(y - top - 0.06) < 0.08
		ok = ok and landed
		results.append("%s can at %.2f (top %.2f)" % [path.get_file().get_basename(), y, top])
	_check("spare_variants", ok, ", ".join(results))


# ---------------------------------------------------------------- windows (D-033)

const WINDOWS := "Zones/Apartment/Windows/"


func _move_hinge(hinge: XRToolsInteractableHinge, angle: float) -> void:
	hinge.hinge_position = angle
	hinge.hinge_moved.emit(hinge.hinge_position)


## A fingertip press on an area button (in, then out again).
func _press(button: Node3D) -> void:
	var tip := _dummy_fingertip()
	var away := button.global_position + button.global_basis.z * 0.2
	tip.global_position = away
	await _frames(2)
	tip.global_position = button.global_position
	await _frames(3)
	tip.global_position = away
	await _frames(2)
	tip.queue_free()


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


# ---------------------------------------------------------------- rain on the glass (D-034)

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


# ---------------------------------------------------------------- bathroom

const PROPS := "Zones/Apartment/Props/"


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


# ---------------------------------------------------------------- world state and day/night (D-051)

func _world() -> WorldState:
	return _main.get_node("WorldState")


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


## Foveation starts with XR, not before, and refills the shading rate map every
## frame: VRS from the first (desktop) frame with Godot's update-once default
## left XR's map empty, and the headset rendered black (D-056).
func _test_foveation_on_xr_start() -> void:
	var foveation := _main.get_node("Foveation") as Foveation
	var viewport := _main.get_viewport()
	var before := [viewport.vrs_mode, viewport.vrs_update_mode]
	var setting: int = ProjectSettings.get_setting("rendering/vrs/mode")
	foveation.call("_on_xr_started")
	var mode := viewport.vrs_mode
	var update := viewport.vrs_update_mode
	viewport.vrs_mode = before[0]
	viewport.vrs_update_mode = before[1]
	_check("foveation_on_xr_start", setting == Viewport.VRS_DISABLED and mode == Viewport.VRS_XR and update == Viewport.VRS_UPDATE_ALWAYS,
			"project vrs/mode %d (0), after XR start mode %d (XR=2), update %d (always=2)" % [setting, mode, update])


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


## Every live reflection rendered once at start (its own renderer or a coplanar
## lead's), so its pipelines compiled while loading: entering the bathroom used
## to compile 38 at once (a 23 ms frame, D-056).
func _test_reflections_warmed() -> void:
	var cold: Array[String] = []
	var instances: Array[PlanarReflection] = PlanarReflection._instances
	for r in instances:
		var warmed := not r._viewports.is_empty()
		for other in instances:
			if not other._viewports.is_empty() and r.magnification == 1.0 and other.magnification == 1.0 and other._coplanar(r):
				warmed = true
		if not warmed:
			cold.append(str(r.get_path()))
	_check("reflections_warmed", instances.size() > 0 and cold.is_empty(), "%d surfaces, cold: %s" % [instances.size(), cold])


## ABViewport flips MSAA and foveation with its variant and puts them back.
func _test_ab_viewport() -> void:
	var viewport := _main.get_viewport()
	var foveation := Foveation.find(_main.get_tree())
	var before := [viewport.msaa_3d, foveation.enabled, foveation.min_radius, foveation.strength]
	var ab := ABViewport.new()
	ab.a = {"msaa": 4, "foveation_radius": 35.0}
	ab.b = {"msaa": 2, "foveation_radius": 0.0}
	_main.add_child(ab)
	var a_ok := viewport.msaa_3d == Viewport.MSAA_4X and foveation.enabled and is_equal_approx(foveation.min_radius, 35.0)
	ab.set_variant("B")
	var b_ok := viewport.msaa_3d == Viewport.MSAA_2X and not foveation.enabled
	ab.set_variant("A")
	var back_ok := viewport.msaa_3d == Viewport.MSAA_4X and foveation.enabled
	ab.free()
	viewport.msaa_3d = before[0]
	foveation.set_foveation(before[1], before[2], before[3])
	_check("ab_viewport", a_ok and b_ok and back_ok, "A %s, B (2x, foveation off) %s, A again %s" % [a_ok, b_ok, back_ok])


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
