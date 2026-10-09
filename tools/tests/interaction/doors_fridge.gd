extends "res://tools/tests/interaction/base.gd"
## Doors and fridge group: hinges, swing, latch, hand push, edge grab, locks, the fridge door bin and alarm.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["fridge", _test_fridge.bind("Fridge")],
		["fridge_swing", _test_swing.bind("Fridge", 20.0, 150.0)],
		["door_swing", _test_swing.bind("DoorLiving", 20.0, 120.0)],
		["fridge_flick_shut", _test_flick_shut.bind("Fridge")],
		["fridge_door_bin", _test_fridge_door_bin],
		["door_hand_push", _test_hand_push.bind("DoorLiving")],
		["entrance_hand_push", _test_hand_push.bind("DoorEntrance")],
		["fridge_hand_push", _test_hand_push.bind("Fridge")],
		["door_edge_grab", _test_edge_grab.bind("DoorBedroom")],
		["entrance_edge_grab", _test_edge_grab.bind("DoorEntrance")],
		["entrance_lock", _test_door_lock.bind("DoorEntrance")],
		["bathroom_lock", _test_door_lock.bind("DoorBathroom")],
		["fridge_alarm", _test_fridge_alarm],
	]


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
	for i in 10:
		await get_tree().physics_frame
		_set_hinge(door, from + speed * (i + 1) * _step())
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
