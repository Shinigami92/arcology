class_name HingeDetents
extends Node
## Detents for an [XRToolsInteractableHinge] (a mixer lever, a dial): let go
## within [member capture] of a detent and it settles into it. Elsewhere it
## stays where it was left. [member click] plays whenever the hinge arrives in
## a detent (moved by hand or settling). Processes only while settling.

@export var hinge: XRToolsInteractableHinge
## Detent angles in degrees.
@export var detents := PackedFloat32Array([0.0])
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var capture := 12.0
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s") var speed := 240.0
## Played when the hinge arrives in a detent.
@export var click: AudioStreamPlayer3D
## Within this of a detent the hinge counts as in it (for the click).
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var click_zone := 0.75

var _target := 0.0
var _in_detent := false


func _ready() -> void:
	if not hinge:
		push_error("HingeDetents needs a hinge: %s" % get_path())
		return
	_in_detent = _detent_at(hinge.hinge_position)
	hinge.grabbed.connect(_on_grabbed)
	hinge.released.connect(_on_released)
	hinge.hinge_moved.connect(_on_hinge_moved)
	set_process(false)


func _detent_at(angle: float) -> bool:
	for detent in detents:
		if absf(detent - angle) <= click_zone:
			return true
	return false


func _on_hinge_moved(angle: float) -> void:
	var inside := _detent_at(angle)
	if inside and not _in_detent and click:
		click.play()
	_in_detent = inside


## The detent within capture of `angle`, or NAN.
func nearest(angle: float) -> float:
	var best := NAN
	var best_distance := capture
	for detent in detents:
		var distance := absf(detent - angle)
		if distance <= best_distance:
			best = detent
			best_distance = distance
	return best


func _on_grabbed(_hinge: XRToolsInteractableHinge) -> void:
	set_process(false)


func _on_released(_hinge: XRToolsInteractableHinge) -> void:
	var detent := nearest(hinge.hinge_position)
	if is_nan(detent):
		return
	_target = detent
	if is_equal_approx(detent, hinge.hinge_position):
		return
	set_process(true)


func _process(delta: float) -> void:
	var angle := move_toward(hinge.hinge_position, _target, speed * delta)
	hinge.move_hinge(deg_to_rad(angle))
	# Arrived, or held back (limits, a body in the way).
	if is_equal_approx(hinge.hinge_position, _target) or not is_equal_approx(hinge.hinge_position, angle):
		set_process(false)
