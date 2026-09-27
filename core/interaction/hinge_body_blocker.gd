class_name HingeBodyBlocker
extends Node
## Stops an [XRToolsInteractableHinge] from swinging its leaf through bodies
## on [member blocking_mask] (by default the player body).
##
## The hinge is moved by the player's hand, not by physics, so without this a
## door pulled open toward the player passes straight through them and leaves
## them standing inside it. After every hinge move this checks the leaf's
## collision shapes; on overlap it puts the hinge back to the last free angle.

@export var hinge: XRToolsInteractableHinge
## The moving body whose shapes are checked (e.g. the door leaf).
@export var leaf: CollisionObject3D
## Layers that block the leaf. Default: layer 20 (Player Body).
@export_flags_3d_physics var blocking_mask := 1 << 19
## Largest angle step checked when the hinge jumps (fast hand movement), so
## the leaf can't skip past a body in one frame.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var sweep_step := 4.0

var _last_free := 0.0
var _params := PhysicsShapeQueryParameters3D.new()
var _shapes: Array[CollisionShape3D] = []


func _ready() -> void:
	if not hinge or not leaf:
		push_error("HingeBodyBlocker needs hinge and leaf: %s" % get_path())
		return
	for child in leaf.get_children():
		if child is CollisionShape3D:
			_shapes.append(child)
	_params.collision_mask = blocking_mask
	_last_free = hinge.hinge_position
	hinge.hinge_moved.connect(_on_hinge_moved)


func _on_hinge_moved(angle: float) -> void:
	# Walk from the last free angle toward the new one and stop just before
	# the first overlap.
	var steps := maxi(1, ceili(absf(angle - _last_free) / sweep_step))
	var from := _last_free
	for i in range(1, steps + 1):
		var step_angle := lerpf(from, angle, float(i) / steps)
		hinge.hinge_position = step_angle
		if _overlaps():
			hinge.hinge_position = _last_free
			return
		_last_free = step_angle


func _overlaps() -> bool:
	var space := leaf.get_world_3d().direct_space_state
	for shape in _shapes:
		_params.shape = shape.shape
		_params.transform = shape.global_transform
		if not space.intersect_shape(_params, 1).is_empty():
			return true
	return false
