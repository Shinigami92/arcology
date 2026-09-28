class_name GrabPassThrough
extends Node
## While a hand holds one of the handles under [member handles_root], that
## hand's collision body ignores [member body].
##
## A collision hand stops at static geometry, and a door leaf is static
## geometry. Pushing a door by its handle therefore presses the hand into the
## leaf: the hand stops, the handle can't move, and the hinge never turns.
## Pulling works only because the hand moves away from the leaf.

## The body the holding hand must pass through (the door leaf).
@export var body: PhysicsBody3D
## Every XRToolsPickable (handle) below this node is watched.
@export var handles_root: Node

# Handle -> hand body it is held by
var _held: Dictionary[XRToolsPickable, PhysicsBody3D] = {}


func _ready() -> void:
	if not body or not handles_root:
		push_error("GrabPassThrough needs body and handles_root: %s" % get_path())
		return
	for node in handles_root.find_children("*", "", true, false):
		var handle := node as XRToolsPickable
		if handle:
			handle.grabbed.connect(_on_grabbed)
			# XR Tools 4.6 never emits `released`; `dropped` fires once the
			# last hand lets go.
			handle.dropped.connect(_on_dropped)


func _on_grabbed(handle: XRToolsPickable, by: Node3D) -> void:
	var hand := _hand_body(by)
	if not hand:
		return
	# XR Tools emits `grabbed` twice per grab, and Jolt counts exceptions, so
	# only add them the first time this hand holds any of our handles.
	var already := _held.values().has(hand)
	_held[handle] = hand
	if not already:
		hand.add_collision_exception_with(body)
		body.add_collision_exception_with(hand)


func _on_dropped(handle: XRToolsPickable) -> void:
	var hand: PhysicsBody3D = _held.get(handle)
	_held.erase(handle)
	# Keep the exception while the same hand still holds another handle.
	if not is_instance_valid(hand) or _held.values().has(hand):
		return
	hand.remove_collision_exception_with(body)
	body.remove_collision_exception_with(hand)


## The collision hand (first PhysicsBody3D ancestor) of the grabbing pickup.
static func _hand_body(by: Node) -> PhysicsBody3D:
	var node := by
	while node:
		if node is PhysicsBody3D:
			return node as PhysicsBody3D
		node = node.get_parent()
	return null
