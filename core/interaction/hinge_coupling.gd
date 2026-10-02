class_name HingeCoupling
extends Node
## Keeps two hinges on one axis in order, like a toilet seat under its lid:
## [member inner] (the seat) can't open past [member outer] (the lid), so
## the outer one can't close while the inner one is up. Optionally the inner
## hinge's handles only work while the outer one is open past
## [member unlock_angle] (the seat's grip lies under the closed lid).
##
## Both hinges open toward hinge_limit_max (closed = hinge_limit_min, 0).
## Signal-driven: it never processes. Place it after both hinges (and after
## their HingeBodyBlocker / HingeSwing) so its correction has the last word.

@export var outer: XRToolsInteractableHinge
@export var inner: XRToolsInteractableHinge
## Every XRToolsPickable below this node (the inner hinge's handles) is only
## grabbable while [member outer] is open more than [member unlock_angle].
## Empty: always grabbable.
@export var inner_handles: Node
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var unlock_angle := 60.0

var _handles: Array[XRToolsPickable] = []
var _unlocked := false


func _ready() -> void:
	if not outer or not inner:
		push_error("HingeCoupling needs outer and inner: %s" % get_path())
		return
	if inner_handles:
		for node in inner_handles.find_children("*", "", true, false):
			var handle := node as XRToolsPickable
			if handle:
				_handles.append(handle)
	outer.hinge_moved.connect(_on_outer_moved)
	inner.hinge_moved.connect(_on_inner_moved)
	_unlocked = not _should_unlock()
	_update_handles()


## Whether the inner hinge's handles can be grabbed now.
func is_unlocked() -> bool:
	return _unlocked


func _on_outer_moved(angle: float) -> void:
	# The outer one rests on the inner one: it can't close below it.
	if angle < inner.hinge_position:
		outer.hinge_position = inner.hinge_position
	_update_handles()


func _on_inner_moved(angle: float) -> void:
	# The inner one stops at the outer one's underside.
	if angle > outer.hinge_position:
		inner.hinge_position = outer.hinge_position


func _should_unlock() -> bool:
	return _handles.is_empty() or outer.hinge_position > unlock_angle


func _update_handles() -> void:
	var unlocked := _should_unlock()
	if unlocked == _unlocked:
		return
	_unlocked = unlocked
	# A handle held while it locks stays in the hand (enabled only gates new grabs).
	for handle in _handles:
		handle.enabled = unlocked
