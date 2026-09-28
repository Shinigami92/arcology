extends Node
## Interaction tests on the real main scene (desktop, no XR). Started by
## main.gd:
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --test=interaction
##
## Prints one line per check ("TEST PASS/FAIL <name>: <details>") and quits
## with the number of failures. Runs through main.gd (not --script) so the
## XR Tools autoloads exist.

const DOORS := ["DoorLiving", "DoorBedroom", "DoorBathroom", "DoorEntrance"]
# Sweep start and motion through each doorway (capsule center at 0.9 m).
const DOORWAYS := {
	"DoorLiving": [Vector3(2.05, 0.9, 1.2), Vector3(0, 0, 1.7)],
	"DoorBedroom": [Vector3(-3.95, 0.9, 2.9), Vector3(0, 0, -1.7)],
	"DoorBathroom": [Vector3(0.55, 0.9, 2.9), Vector3(0, 0, 1.7)],
	"DoorEntrance": [Vector3(5.8, 0.9, 2.9), Vector3(1.6, 0, 0)],
}

var _main: Node3D
var _failures := 0


func _ready() -> void:
	_main = get_parent() as Node3D
	await _frames(30)
	await _test_doorways()
	await _test_blocker()
	await _test_pass_through()
	await _test_push_door_open()
	await _test_jump()
	await _test_jump_onto_table()
	await _test_ranged_grab()
	print("TEST DONE: %d failure(s)" % _failures)
	get_tree().quit(_failures)


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
