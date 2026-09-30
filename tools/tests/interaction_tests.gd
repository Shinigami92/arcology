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
	await _test_fridge("Fridge")
	await _test_swing("Fridge", 20.0, 150.0)
	await _test_swing("DoorLiving", 20.0, 120.0)
	await _test_flick_shut("Fridge")
	await _test_fridge_door_bin()
	await _test_sofa()
	await _test_spare_sofa()
	for variant in _variants("Bed"):
		await _test_bedroom(variant)
	await _test_ab_panel()
	await _test_fingertips()
	for variant in _variants("Nightstand"):
		await _test_lamp_switch(variant)
	await _test_fridge_alarm()
	await _test_wardrobe_interior()
	await _test_bed_bedding_collision()
	await _test_spare_variants()
	await _test_window_vent()
	await _test_window_shade()
	await _test_window_tint()
	await _test_window_hud()
	await _test_window_glass_collision()
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


## Both hands carry a fingertip press area on the Player Hands layer.
func _test_fingertips() -> void:
	var found: Array[String] = []
	for side in ["Left", "Right"]:
		for node in _main.get_node("Player/%sHand" % side).find_children("Fingertip", "Area3D", true, false):
			if (node as Area3D).collision_layer == 131072:
				found.append(side)
	_check("fingertip_areas", found == ["Left", "Right"], "fingertips on hands: %s" % [found])


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


## The living room HUD shows the system time (placeholder source), on its east pane only.
func _test_window_hud() -> void:
	var hud: WindowHud = _main.get_node(WINDOWS + "LivingWindow/Hud")
	var pane: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass2")
	var other: GeometryInstance3D = _main.get_node(WINDOWS + "LivingWindow/Glass0")
	hud.refresh()
	var now := Time.get_time_dict_from_system()
	var shown: Vector4i = (pane.material_override as ShaderMaterial).get_shader_parameter("hud_time")
	var hour: int = now.hour
	var minute: int = now.minute
	var expect := Vector4i(hour / 10, hour % 10, minute / 10, minute % 10)
	var enabled: bool = pane.get_instance_shader_parameter("hud_enabled")
	var other_value: Variant = other.get_instance_shader_parameter("hud_enabled")
	var other_off := other_value == null or not bool(other_value)
	_check("window_hud_time", shown == expect and enabled and other_off,
			"hud_time %s, clock %s, on the east pane only %s" % [shown, expect, enabled and other_off])


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
