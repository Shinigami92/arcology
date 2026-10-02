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
	await _test_rain_button()
	await _test_rain_wetness()
	await _test_bath_magnifier()
	await _test_bath_mirror_touch()
	await _test_toilet_lid_and_seat()
	await _test_toilet_soft_close()
	await _test_toilet_flush()
	await _test_toilet_roll()
	await _test_vanity_drawers()
	await _test_vanity_lever()
	await _test_vanity_dispenser()
	await _test_shower_controls()
	await _test_shower_hand()
	await _test_shower_glass()
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


## The living room debug button cycles the rain 0 -> 0.4 -> 1 -> 0.
func _test_rain_button() -> void:
	var rain: RainOnGlass = _main.get_node("Weather/RainOnGlass")
	rain.set_rain(0.0, true)
	var button: Node3D = _main.get_node("Zones/Apartment/Props/RainDebugButton/Button")
	var targets: Array[String] = []
	for i in 3:
		await _press(button)
		targets.append("%.1f" % rain.target)
	rain.set_rain(0.0, true)
	await _frames(2)
	_check("rain_button_cycles", targets == ["0.4", "1.0", "0.0"], "rain after each press: %s" % [targets])


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
	var shader_ok := mats.size() == 3 and absf(shader_wet - rain.wetness) < 0.001
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
