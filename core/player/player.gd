class_name ArcologyPlayer
extends XROrigin3D
## XR rig: hands, locomotion, comfort options, seated height calibration,
## jump/crouch, sitting on Seats.
##
## Defaults follow docs/decisions.md D-009: smooth movement and smooth turning,
## teleport, snap turn and vignette off. Comfort options can be changed at
## runtime by setting the properties below. Button layout: CLAUDE.md
## "Controls".

signal seated_changed(seated: bool)

enum TurnStyle { SMOOTH, SNAP }

## Seconds after XR starts before the first height calibration, so the
## headset pose has settled.
const CALIBRATION_DELAY := 0.5
## Fade time for sitting, standing and recentering.
const FADE_TIME := 0.15

@export_group("Movement")
## Walking speed with the left stick.
@export_custom(PROPERTY_HINT_NONE, "suffix:m/s") var move_speed := 2.0: set = set_move_speed
## Speed multiplier when the left stick is pushed fully forward.
@export_range(1.0, 4.0, 0.1) var sprint_multiplier := 2.0: set = set_sprint_multiplier

@export_group("Comfort")
@export var turn_style := TurnStyle.SMOOTH: set = set_turn_style
@export_custom(PROPERTY_HINT_NONE, "suffix:rad/s") var smooth_turn_speed := 2.0: set = set_smooth_turn_speed
@export_range(10, 90, 5, "degrees") var snap_turn_angle := 30.0: set = set_snap_turn_angle
## Teleport with the right trigger. Smooth movement stays available.
@export var teleport_enabled := false: set = set_teleport_enabled
## Darkens the view edges while moving or turning.
@export var vignette_enabled := false: set = set_vignette_enabled

@export_group("Buttons")
## Left controller button, held: recenter view and recalibrate eye height.
@export var recenter_action := "by_button"
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var recenter_hold_time := 1.0
## Left controller button: interact (sit down / get up).
@export var interact_action := "ax_button"
## Print every controller button press to the log (to check button mapping).
@export var log_buttons := true

var seated := false

var _recenter_held := 0.0
var _seats: Array[Seat] = []
var _seat: Seat
var _busy := false
var _stand_stick_held := 0.0

@onready var _camera: XRCamera3D = $XRCamera3D
@onready var _vignette: XRToolsVignette = $XRCamera3D/Vignette
@onready var _left: XRController3D = $LeftHand
@onready var _right: XRController3D = $RightHand
@onready var _direct: XRToolsMovementDirect = $LeftHand/CollisionHand/MovementDirect
@onready var _sprint: StickSprint = $LeftHand/CollisionHand/StickSprint
@onready var _turn: XRToolsMovementTurn = $RightHand/CollisionHand/MovementTurn
@onready var _teleport: XRToolsFunctionTeleport = $RightHand/CollisionHand/FunctionTeleport
@onready var _body: XRToolsPlayerBody = $PlayerBody


func _ready() -> void:
	_apply_all()
	var start_xr := XRToolsStartXR.get_start_xr_node()
	if start_xr:
		start_xr.xr_started.connect(_on_xr_started)
	_left.button_pressed.connect(_on_left_button)
	if log_buttons:
		_right.button_pressed.connect(func(button: String) -> void: print("XR button: right ", button))


func _physics_process(delta: float) -> void:
	if _left.get_is_active() and _left.is_button_pressed(recenter_action):
		_recenter_held += delta
		if _recenter_held >= recenter_hold_time:
			_recenter_held = -INF  # fire once per press
			recenter()
	else:
		_recenter_held = 0.0

	# Pushing the move stick while seated gets the player up.
	if seated and not _busy:
		var stick := _left.get_vector2("primary") if _left.get_is_active() else Vector2.ZERO
		_stand_stick_held = _stand_stick_held + delta if stick.length() > 0.7 else 0.0
		if _stand_stick_held > 0.25:
			stand()


## Recenters the view on the headset and recalibrates the eye height, so a
## seated player sees the world from a standing adult's height
## (godot_xr_tools/player/standard_height). While sitting on a Seat, puts the
## view back on the seat instead. Confirms with a short blink and a buzz.
func recenter() -> void:
	print("Player: recenter")
	_left.trigger_haptic_pulse("haptic", 0.0, 0.6, 0.15, 0.0)
	await _fade_to(1.0)
	if seated:
		_place_camera(_seat.sit_point)
	else:
		XRServer.center_on_hmd(XRServer.RESET_BUT_KEEP_TILT, true)
		_body.calibrate_player_height()
	await _fade_to(0.0)


## Seat calls this when the player enters or leaves its area.
func register_seat(seat: Seat, in_range: bool) -> void:
	if in_range:
		if not _seats.has(seat):
			_seats.append(seat)
	else:
		_seats.erase(seat)


## Sits down on [param seat]: fades, moves the view to its sit point and
## disables walking (turning with the head still works).
func sit(seat: Seat) -> void:
	if _busy or seated or not seat.sit_point:
		return
	_busy = true
	await _fade_to(1.0)
	_body.enabled = false
	_place_camera(seat.sit_point)
	_seat = seat
	seat.set_occupied(true)
	seated = true
	_stand_stick_held = 0.0
	await _fade_to(0.0)
	_busy = false
	seated_changed.emit(true)


## Gets up from the current seat at its stand point.
func stand() -> void:
	if _busy or not seated:
		return
	_busy = true
	await _fade_to(1.0)
	var target: Node3D = _seat.stand_point
	if not target:
		target = _seat
	_place_camera(target)
	# The body stands player_height_offset below the origin (seated height
	# calibration), so put the origin that far above the floor.
	var pos := global_position
	pos.y = target.global_position.y + _body.player_height_offset
	global_position = pos
	_body.enabled = true
	_seat.set_occupied(false)
	_seat = null
	seated = false
	await _fade_to(0.0)
	_busy = false
	seated_changed.emit(false)


func set_move_speed(value: float) -> void:
	move_speed = value
	if is_node_ready():
		_direct.max_speed = move_speed
		_sprint.set_base_speed(move_speed)


func set_sprint_multiplier(value: float) -> void:
	sprint_multiplier = value
	if is_node_ready():
		_sprint.sprint_multiplier = sprint_multiplier


func set_turn_style(value: TurnStyle) -> void:
	turn_style = value
	if is_node_ready():
		_turn.turn_mode = (
				XRToolsMovementTurn.TurnMode.SNAP
				if turn_style == TurnStyle.SNAP
				else XRToolsMovementTurn.TurnMode.SMOOTH
		)


func set_smooth_turn_speed(value: float) -> void:
	smooth_turn_speed = value
	if is_node_ready():
		_turn.smooth_turn_speed = smooth_turn_speed


func set_snap_turn_angle(value: float) -> void:
	snap_turn_angle = value
	if is_node_ready():
		_turn.step_turn_angle = snap_turn_angle


func set_teleport_enabled(value: bool) -> void:
	teleport_enabled = value
	if is_node_ready():
		_teleport.enabled = teleport_enabled


func set_vignette_enabled(value: bool) -> void:
	vignette_enabled = value
	if is_node_ready():
		_vignette.visible = vignette_enabled
		_vignette.set_process(vignette_enabled)


func _apply_all() -> void:
	set_move_speed(move_speed)
	set_sprint_multiplier(sprint_multiplier)
	set_turn_style(turn_style)
	set_smooth_turn_speed(smooth_turn_speed)
	set_snap_turn_angle(snap_turn_angle)
	set_teleport_enabled(teleport_enabled)
	set_vignette_enabled(vignette_enabled)


## Moves and turns the origin so the camera ends up at [param target]'s
## position (x/z, and y when seated) looking along its -Z.
func _place_camera(target: Node3D) -> void:
	var cam := _camera.transform
	var cam_yaw := _yaw_of(-cam.basis.z)
	var target_yaw := _yaw_of(-target.global_basis.z)
	var rot := Basis(Vector3.UP, target_yaw - cam_yaw)
	global_transform = Transform3D(rot, target.global_position - rot * cam.origin)


static func _yaw_of(forward: Vector3) -> float:
	return atan2(-forward.x, -forward.z)


func _fade_to(alpha: float) -> void:
	var from := 1.0 - alpha
	var tween := create_tween()
	tween.tween_method(
			func(a: float) -> void: XRToolsFade.set_fade(self, Color(0, 0, 0, a)),
			from, alpha, FADE_TIME)
	await tween.finished


func _nearest_seat() -> Seat:
	var best: Seat
	var best_dist := INF
	for seat in _seats:
		if not is_instance_valid(seat) or seat.occupied:
			continue
		var d := seat.global_position.distance_squared_to(_camera.global_position)
		if d < best_dist:
			best = seat
			best_dist = d
	return best


func _on_left_button(button: String) -> void:
	if log_buttons:
		print("XR button: left ", button)
	if button != interact_action:
		return
	if seated:
		stand()
	else:
		var seat := _nearest_seat()
		if seat:
			sit(seat)


func _on_xr_started() -> void:
	await get_tree().create_timer(CALIBRATION_DELAY).timeout
	_body.calibrate_player_height()
