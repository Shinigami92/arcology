@tool
class_name StickSprint
extends XRToolsMovementProvider
## Sprint by pushing the move stick fully forward, no button needed.
##
## Holding the stick past [member threshold] (mostly forward) for
## [member hold_time] ramps the sibling [XRToolsMovementDirect] speed up to
## [member sprint_multiplier]. Easing off the stick ramps it back down.
## Runs before direct movement (lower [member order]) so the boosted
## max speed applies in the same physics frame.


## Movement provider order; must be lower than XRToolsMovementDirect's (10).
@export var order: int = 9

## Stick deflection (0..1) that counts as "fully pushed".
@export_range(0.5, 1.0, 0.01) var threshold := 0.92

## Minimum forward share of the deflection; prevents sprinting sideways.
@export_range(0.0, 1.0, 0.01) var min_forward := 0.7

## Seconds the stick must stay past the threshold before sprint starts.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var hold_time := 0.25

## Speed multiplier at full sprint.
@export_range(1.0, 4.0, 0.1) var sprint_multiplier := 2.0

## Seconds to ramp between walk and sprint speed (both directions).
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var ramp_time := 0.4

## Stick action, same as the direct movement it boosts.
@export var input_action := "primary"

var _controller: XRController3D
var _direct: XRToolsMovementDirect
var _base_speed := 0.0
var _held := 0.0
var _blend := 0.0


func _ready() -> void:
	super()
	if Engine.is_editor_hint():
		return
	_controller = XRHelpers.get_xr_controller(self)
	_direct = XRTools.find_xr_child(_controller, "*", "XRToolsMovementDirect") as XRToolsMovementDirect
	if _direct:
		_base_speed = _direct.max_speed


func is_xr_class(xr_name: String) -> bool:
	return xr_name == "StickSprint" or super(xr_name)


## Re-reads the walk speed after it was changed at runtime (comfort settings).
func set_base_speed(speed: float) -> void:
	_base_speed = speed
	_apply()


func physics_movement(delta: float, _player_body: XRToolsPlayerBody, disabled: bool) -> bool:
	if not _direct:
		return false

	var pushing := false
	if enabled and not disabled and _controller and _controller.get_is_active():
		var stick := _controller.get_vector2(input_action)
		var length := stick.length()
		pushing = length >= threshold and stick.y / length >= min_forward

	_held = _held + delta if pushing else 0.0
	var target := 1.0 if _held >= hold_time else 0.0
	_blend = move_toward(_blend, target, delta / maxf(ramp_time, 0.001))
	is_active = _blend > 0.0
	_apply()
	return false


func _apply() -> void:
	_direct.max_speed = lerpf(_base_speed, _base_speed * sprint_multiplier, _blend)
