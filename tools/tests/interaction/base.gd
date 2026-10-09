extends Node
## Shared by the interaction test groups (one file per group next to this one,
## each extending it): the main scene, checks, frame waits and the helpers more
## than one group uses. A helper only one group needs lives in that group's file.

## Each check's outcome; the runner (interaction_tests.gd) counts the failures.
signal checked(ok: bool)

const SIDES: Array[String] = ["Left", "Right"]
# The player body's spot (Entries/Default, facing -Z) that tests which move the
# player return to; _reset_rig() puts it there before each test.
const HOME := Transform3D(Basis.IDENTITY, Vector3(0.4, 0, -0.4))
const CAN_SCENE := "res://assets/props/beverage_can/beverage_can.tscn"
const WINDOWS := "Zones/Apartment/Windows/"
const PROPS := "Zones/Apartment/Props/"

## The main scene (main.tscn's root), set by the runner.
var _main: Node3D


func _check(name: String, ok: bool, details: String) -> void:
	print("TEST %s %s: %s" % ["PASS" if ok else "FAIL", name, details])
	checked.emit(ok)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


## One physics frame in engine seconds: throws move by engine time, not the
## wall clock, so they hold with --fixed-fps.
func _step() -> float:
	return 1.0 / Engine.physics_ticks_per_second


func _hinge(door: String) -> XRToolsInteractableHinge:
	return _main.get_node("Zones/Apartment/Props/%s/HingeOrigin/InteractableHinge" % door)


func _set_hinge(door: String, angle: float) -> void:
	var hinge := _hinge(door)
	hinge.hinge_position = angle
	hinge.hinge_moved.emit(angle)


## Test-only movement provider: pushes the player forward like a held stick.
class _ForwardInput extends XRToolsMovementProvider:
	var order := 10
	var speed := 1.5

	func physics_movement(_delta: float, player_body: XRToolsPlayerBody, _disabled: bool) -> bool:
		player_body.ground_control_velocity.y += speed
		return false


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


func _world() -> WorldState:
	return _main.get_node("WorldState")
