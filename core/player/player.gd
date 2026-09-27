class_name ArcologyPlayer
extends XROrigin3D
## XR rig: hands, locomotion, comfort options, seated height calibration.
##
## Defaults follow docs/decisions.md D-009: smooth movement and smooth turning,
## teleport, snap turn and vignette off. Comfort options can be changed at
## runtime by setting the properties below.

enum TurnStyle { SMOOTH, SNAP }

## Seconds after XR starts before the first height calibration, so the
## headset pose has settled.
const CALIBRATION_DELAY := 0.5

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

@export_group("Recenter")
## Button on the left controller that recenters and recalibrates height when held.
@export var recenter_action := "by_button"
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var recenter_hold_time := 1.0

var _recenter_held := 0.0

@onready var _vignette: XRToolsVignette = $XRCamera3D/Vignette
@onready var _left: XRController3D = $LeftHand
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


func _physics_process(delta: float) -> void:
	if _left.get_is_active() and _left.is_button_pressed(recenter_action):
		_recenter_held += delta
		if _recenter_held >= recenter_hold_time:
			_recenter_held = -INF  # fire once per press
			recenter()
	else:
		_recenter_held = 0.0


## Recenters the view on the headset and recalibrates the eye height, so a
## seated player sees the world from a standing adult's height
## (godot_xr_tools/player/standard_height).
func recenter() -> void:
	XRServer.center_on_hmd(XRServer.RESET_BUT_KEEP_TILT, true)
	_body.calibrate_player_height()


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


func _on_xr_started() -> void:
	await get_tree().create_timer(CALIBRATION_DELAY).timeout
	_body.calibrate_player_height()
