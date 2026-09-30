class_name HingeAmbience
extends AudioStreamPlayer3D
## A looping sound that gets louder the wider an [XRToolsInteractableHinge]
## opens: the city (or the rain, see [RainOnGlass]) outside a tilted window
## vent. Stopped while closed or while [member gain] is 0. Event driven
## (hinge_moved, gain changes), no processing.
##
## Assign [member hinge], or place as a direct child of the hinge. The loop
## itself comes from the stream's import settings (loop mode Forward).

@export var hinge: XRToolsInteractableHinge
## Volume at the open limit (at gain 1).
@export_custom(PROPERTY_HINT_NONE, "suffix:dB") var open_db := -4.0
## Opened less than this (from the closed limit) counts as closed.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var closed_angle := 0.2
## Scales the sound (linear, 0..1), e.g. by how hard it rains.
@export_range(0.0, 1.0) var gain := 1.0:
	set(value):
		gain = value
		if is_node_ready():
			_update()


func _ready() -> void:
	if not hinge:
		hinge = get_parent() as XRToolsInteractableHinge
	if not hinge:
		push_error("HingeAmbience needs a hinge: %s" % get_path())
		return
	hinge.hinge_moved.connect(_on_hinge_moved)
	_update()


## 0 = closed .. 1 = fully open.
func get_opening() -> float:
	var span := hinge.hinge_limit_max - hinge.hinge_limit_min
	return clampf((hinge.hinge_position - hinge.hinge_limit_min) / span, 0.0, 1.0) if span > 0.0 else 0.0


func _on_hinge_moved(_angle: float) -> void:
	_update()


func _update() -> void:
	if not hinge:
		return
	if hinge.hinge_position - hinge.hinge_limit_min <= closed_angle or gain <= 0.001:
		stop()
		return
	# The gap (and the sound through it) grows about linearly with the angle.
	volume_db = open_db + linear_to_db(maxf(get_opening() * gain, 0.01))
	if not playing:
		play()
