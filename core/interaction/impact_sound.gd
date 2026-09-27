class_name ImpactSound
extends AudioStreamPlayer3D
## Plays [member stream] when the parent [RigidBody3D] hits something, with
## volume and pitch scaled by impact speed.
##
## Add as a direct child of a RigidBody3D (e.g. an XRToolsPickable). Enables
## contact monitoring on the parent. Rolling and resting contacts don't
## retrigger; only new contacts faster than [member min_speed] do.

## Impacts slower than this are silent.
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s") var min_speed := 0.4
## Impacts at or above this speed play at full volume.
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s") var max_speed := 6.0
## Volume of the softest audible impact.
@export_range(-60.0, 0.0, 1.0, "suffix:dB") var min_volume_db := -28.0
## Random pitch variation (±).
@export_range(0.0, 0.5, 0.01) var pitch_jitter := 0.08
## Minimum time between two impact sounds.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var cooldown := 0.06

var _body: RigidBody3D
var _last_velocity := Vector3.ZERO
var _last_play_msec := -100000


func _ready() -> void:
	_body = get_parent() as RigidBody3D
	if not _body:
		push_error("ImpactSound must be a child of a RigidBody3D: %s" % get_path())
		set_physics_process(false)
		return
	_body.contact_monitor = true
	_body.max_contacts_reported = maxi(_body.max_contacts_reported, 4)
	_body.body_entered.connect(_on_body_entered)


func _physics_process(_delta: float) -> void:
	_last_velocity = _body.linear_velocity


func _on_body_entered(other: Node) -> void:
	# Relative speed matters: a moving door hitting a resting ball is an impact too.
	var other_velocity := Vector3.ZERO
	if other is RigidBody3D:
		other_velocity = (other as RigidBody3D).linear_velocity
	var speed := (_last_velocity - other_velocity).length()
	if speed < min_speed:
		return
	var now := Time.get_ticks_msec()
	if now - _last_play_msec < int(cooldown * 1000.0):
		return
	_last_play_msec = now

	var strength := clampf(inverse_lerp(min_speed, max_speed, speed), 0.0, 1.0)
	volume_db = lerpf(min_volume_db, 0.0, sqrt(strength))
	pitch_scale = 1.0 + randf_range(-pitch_jitter, pitch_jitter) + 0.05 * strength
	play()
