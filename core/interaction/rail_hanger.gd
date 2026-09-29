class_name RailHanger
extends Node
## Put on a clothes hanger pickable (as its child): when it's dropped with its
## hook near a [HangingRail], it hangs there (frozen, upright, shoulders across
## the rail); picked up again, it's a normal pickable. Hangers placed on a
## rail in the scene start hung. The pickable needs `release_mode = UNFROZEN`,
## so a drop away from rails falls normally.

## Hook contact point (where the inside of the hook touches the rail top).
@export var hook: Node3D
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var snap_distance := 0.10

var _body: XRToolsPickable


func _ready() -> void:
	_body = get_parent() as XRToolsPickable
	if not _body or not hook:
		push_error("RailHanger must be a child of a pickable and needs a hook: %s" % get_path())
		return
	_body.dropped.connect(_on_dropped)
	try_hang.call_deferred()


## Hangs the hanger on the nearest rail within reach; returns whether it did.
func try_hang() -> bool:
	var hook_pos := hook.global_position
	var best: HangingRail
	var best_point := Vector3.ZERO
	var best_distance := snap_distance
	for node in get_tree().get_nodes_in_group(HangingRail.GROUP):
		var rail := node as HangingRail
		if not rail.is_visible_in_tree():
			continue
		var point := rail.rest_point(hook_pos)
		var distance := point.distance_to(hook_pos)
		if distance <= best_distance:
			best = rail
			best_point = point
			best_distance = distance
	if not best:
		return false
	# Shoulders (local X) run across the rail, as in a wardrobe.
	var across := best.direction().cross(Vector3.UP).normalized()
	if _body.global_basis.x.dot(across) < 0.0:
		across = -across
	var basis := Basis(across, Vector3.UP, across.cross(Vector3.UP))
	var hook_local := _body.global_transform.affine_inverse() * hook_pos
	_body.freeze = true
	_body.linear_velocity = Vector3.ZERO
	_body.angular_velocity = Vector3.ZERO
	_body.global_transform = Transform3D(basis, best_point - basis * hook_local)
	return true


func is_hung() -> bool:
	return _body.freeze and not _body.is_picked_up()


func _on_dropped(_pickable: XRToolsPickable) -> void:
	try_hang()
