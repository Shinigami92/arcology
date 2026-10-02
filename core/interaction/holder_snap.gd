class_name HolderSnap
extends Node
## Put on a pickable (as its child): dropped near a holder, it sits in that
## holder (frozen, in the holder's pose) until grabbed again: a toilet roll
## on its bar, a hand shower in its cradle. Placed at a holder in the scene,
## it starts there. The pickable needs `release_mode = UNFROZEN`, so a drop
## away from holders falls normally.
##
## Holders are Node3Ds (e.g. Marker3D) in [member holder_group]; the body's
## origin goes to the holder's origin, its basis to the holder's basis.

@export var holder_group := "holder"
## Distance between [member center] and the holder's matching point that still snaps.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var snap_distance := 0.08
## Point compared with the holder, in the body's frame (e.g. a roll's middle);
## the same point in the holder's frame is where it ends up.
@export var center := Vector3.ZERO
## Played when it snaps into a holder after a drop (not at the start).
@export var snap_sound: AudioStreamPlayer3D

var _body: XRToolsPickable


func _ready() -> void:
	_body = get_parent() as XRToolsPickable
	if not _body:
		push_error("HolderSnap must be a child of a pickable: %s" % get_path())
		return
	_body.dropped.connect(_on_dropped)
	_start.call_deferred()


## Snaps into the nearest free holder within reach; returns whether it did.
func try_snap() -> bool:
	var at := _body.global_transform * center
	var best: Node3D
	var best_distance := snap_distance
	for node in get_tree().get_nodes_in_group(holder_group):
		var holder := node as Node3D
		if not holder or not holder.is_visible_in_tree():
			continue
		var distance := (holder.global_transform * center).distance_to(at)
		if distance <= best_distance:
			best = holder
			best_distance = distance
	if not best:
		return false
	_body.freeze = true
	_body.linear_velocity = Vector3.ZERO
	_body.angular_velocity = Vector3.ZERO
	_body.global_transform = best.global_transform
	return true


## Frozen in a holder (not in a hand).
func is_held() -> bool:
	return _body.freeze and not _body.is_picked_up()


func _start() -> void:
	try_snap()


func _on_dropped(_pickable: XRToolsPickable) -> void:
	if try_snap() and snap_sound:
		snap_sound.play()
