class_name HingeStopSound
extends AudioStreamPlayer3D
## Plays [member stream] when an [XRToolsInteractableHinge] swings into one of
## its limits (a door closing into its frame or hitting its stop).
##
## Assign [member hinge], or place as a direct child of the hinge.

@export var hinge: XRToolsInteractableHinge
## Angular speed at the limit that plays at full volume.
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s") var full_volume_speed := 180.0
## Slower than this at the limit is silent.
@export_custom(PROPERTY_HINT_NONE, "suffix:°/s") var min_speed := 20.0
## Angle distance from a limit that counts as "at the limit".
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var limit_tolerance := 0.5

var _last_angle := 0.0
var _last_msec := 0
var _at_limit := true


func _ready() -> void:
	if not hinge:
		hinge = get_parent() as XRToolsInteractableHinge
	if not hinge:
		push_error("HingeStopSound needs a hinge: %s" % get_path())
		return
	_last_angle = hinge.hinge_position
	_last_msec = Time.get_ticks_msec()
	hinge.hinge_moved.connect(_on_hinge_moved)


func _on_hinge_moved(angle: float) -> void:
	var now := Time.get_ticks_msec()
	var dt := maxf((now - _last_msec) / 1000.0, 0.001)
	var speed := absf(angle - _last_angle) / dt
	_last_angle = angle
	_last_msec = now

	var at_limit := (
			angle <= hinge.hinge_limit_min + limit_tolerance
			or angle >= hinge.hinge_limit_max - limit_tolerance
	)
	if at_limit and not _at_limit and speed >= min_speed:
		volume_db = linear_to_db(clampf(speed / full_volume_speed, 0.05, 1.0))
		pitch_scale = randf_range(0.95, 1.05)
		play()
	_at_limit = at_limit
