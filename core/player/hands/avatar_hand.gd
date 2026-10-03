@tool
class_name AvatarHand
extends XRToolsHand
## XRToolsHand for the avatar's rigged hands (D-037, D-039).
##
## Each finger curls on the control it rests on, through the finger_* OpenXR
## actions (openxr_action_map.tres). Steam Frame: index on the bumper, middle
## on the trigger, ring and little on the grip, thumb on the stick and face
## buttons. Touch and Index controllers: index on the trigger, the others on
## the grip. Touching a control curls its finger part way, pressing it fully.
## Controllers without finger_* bindings fall back to XR Tools' grip/trigger.
##
## XR Tools swaps its own hand animations into the blend tree (default_pose,
## pose overrides), whose tracks use the XR Tools bone names; without a
## default_pose this hand keeps the model's "Open" and "Grip". XR Tools pose
## areas (per-object grab poses) would still swap in XR Tools animations.
##
## Scene layout (written by tools/player/avatar_hands.gd): the first child is
## an Offset node that XR Tools moves to the controller's palm offset; the glb
## model sits under it, fitted onto where the XR Tools hand used to be.

const FINGERS: Array[StringName] = [&"Index", &"Middle", &"Ring", &"Thumb"]

## Curl while a finger only touches its control (0 = open, 1 = full grip).
@export_range(0.0, 1.0) var touch_curl := 0.3
## Thumb curl while it touches the stick or a face button.
@export_range(0.0, 1.0) var thumb_touch_curl := 0.45
## How fast a finger follows its control (full curl per second).
@export var finger_speed := 14.0

var _curl: Array[float] = [0.0, 0.0, 0.0, 0.0]
var _goal: Array[float] = [0.0, 0.0, 0.0, 0.0]


func _update_pose() -> void:
	if default_pose == null and _pose_overrides.is_empty():
		return
	super()


func _physics_process(delta: float) -> void:
	super(delta)
	if Engine.is_editor_hint() or not _controller or not _anim_tree:
		return
	_read_goals()
	for i in FINGERS.size():
		_curl[i] = move_toward(_curl[i], _goal[i], finger_speed * delta)
		_anim_tree.set("parameters/%s/blend_amount" % FINGERS[i], _curl[i])


## Forces the curl as XR Tools does: trigger for the index, grip for the rest
## (-1 = follow the controller again). Applies at once, without easing.
func force_grip_trigger(grip: float = -1.0, trigger: float = -1.0) -> void:
	_force_grip = grip
	_force_trigger = trigger
	if grip >= 0.0 or trigger >= 0.0:
		_read_goals()
		_curl = _goal.duplicate()
		for i in FINGERS.size():
			_anim_tree.set("parameters/%s/blend_amount" % FINGERS[i], _curl[i])


func _read_goals() -> void:
	if _force_grip >= 0.0 or _force_trigger >= 0.0:
		var grip := maxf(_force_grip, 0.0)
		_goal = [maxf(_force_trigger, 0.0), grip, grip, grip]
		return
	var c := _controller
	var index := maxf(c.get_float("finger_index"),
			1.0 if c.is_button_pressed("finger_index_click") else touch_curl if c.is_button_pressed("finger_index_touch") else 0.0)
	var middle := maxf(c.get_float("finger_middle"), touch_curl if c.is_button_pressed("finger_middle_touch") else 0.0)
	var ring := c.get_float("finger_ring")
	var thumb := 1.0 if c.is_button_pressed("finger_thumb_click") else thumb_touch_curl if c.is_button_pressed("finger_thumb_touch") else 0.0
	if index == 0.0 and middle == 0.0 and ring == 0.0 and thumb == 0.0:
		# No finger_* bindings for this controller (or nothing touched): XR Tools' mapping.
		var grip := c.get_float(grip_action)
		index = c.get_float(trigger_action)
		middle = grip
		ring = grip
		thumb = grip
	_goal = [index, middle, ring, thumb]
