class_name ArmIK
extends SkeletonModifier3D
## Two-bone IK for the avatar's arm (D-040). The skeleton belongs to the hand
## scene, which XR Tools moves with the controller, so the hand bone already
## sits where the hand is; this places the shoulder from the headset, solves
## the elbow, and spreads the wrist roll along the forearm:
##
## - Shoulder: [member shoulder_offset] from the eyes in a body frame that
##   turns with the head once it looks more than [member body_follow_angle]
##   away. If the hand is farther than the arm reaches, the shoulder slides
##   toward it (the hand always stays on the controller).
## - Elbow: in the plane of shoulder, wrist and [member elbow_hint] (towards
##   the body's back when the arm points along the hint, e.g. hanging down).
## - Both bones keep the frame they have in the rest pose relative to the arm
##   line and the elbow's bend direction, so their roll follows the elbow and
##   never flips when the wrist rolls (D-040).
## - Twist: the hand's roll about the forearm goes [member twist_share] into
##   the twist bone (sleeve and cuff), none into the forearm itself. The roll
##   is tracked continuously (no jump at half a turn) and kept within
##   [member twist_limit] of [member twist_center].
##
## Bone names come from [member side] (D-037). Written by
## tools/player/avatar_hands.gd.

## "Left" or "Right" (bone name prefix).
@export var side := "Left"
## Shoulder joint relative to the eyes in the body frame (x right, y up, z back), meters.
@export var shoulder_offset := Vector3(-0.18, -0.24, 0.05)
## Direction the elbow points to in the body frame (x right, y up, z back).
@export var elbow_hint := Vector3(-0.35, -1.0, 0.3)
## Share of the hand's roll that the twist bone takes.
@export_range(0.0, 1.0) var twist_share := 0.7
## Middle of the hand's roll range against the forearm (degrees).
@export_range(-180.0, 180.0) var twist_center := -20.0
## How far the tracked roll may leave [member twist_center] (degrees).
@export_range(90.0, 270.0) var twist_limit := 200.0
## How far the head can turn (degrees) before the shoulders turn with it.
@export_range(0.0, 90.0) var body_follow_angle := 35.0

var _upper := -1
var _lower := -1
var _twist := -1
var _hand := -1
var _upper_len := 0.0
var _lower_len := 0.0
var _upper_rest: Transform3D
var _lower_rest: Transform3D
var _hand_rest: Transform3D
var _twist_rest_rotation: Quaternion
## Each bone's rest basis in its rest arm frame (see _arm_frame).
var _upper_in_frame: Basis
var _lower_in_frame: Basis
var _body_yaw := NAN
var _roll_tracked := NAN


func _ready() -> void:
	var skeleton := get_skeleton()
	if not skeleton:
		return
	_upper = skeleton.find_bone("%sUpperArm" % side)
	_lower = skeleton.find_bone("%sLowerArm" % side)
	_twist = skeleton.find_bone("%sLowerArmTwist" % side)
	_hand = skeleton.find_bone("%sHand" % side)
	if _upper < 0 or _lower < 0 or _hand < 0:
		push_warning("ArmIK %s: missing arm bones" % side)
		active = false
		return
	_upper_rest = skeleton.get_bone_global_rest(_upper)
	_lower_rest = skeleton.get_bone_global_rest(_lower)
	_hand_rest = skeleton.get_bone_global_rest(_hand)
	_upper_len = _upper_rest.origin.distance_to(_lower_rest.origin)
	_lower_len = _lower_rest.origin.distance_to(_hand_rest.origin)
	if _twist >= 0:
		_twist_rest_rotation = skeleton.get_bone_rest(_twist).basis.get_rotation_quaternion()
	# Rest bend: the elbow's offset from the shoulder-wrist line (the rest arm is slightly bent).
	var line := (_hand_rest.origin - _upper_rest.origin).normalized()
	var bend := _lower_rest.origin - _upper_rest.origin
	bend -= line * bend.dot(line)
	if bend.length_squared() < 0.000001:
		bend = _upper_rest.basis.z
	var hinge := line.cross(bend.normalized())
	_upper_in_frame = _arm_frame((_lower_rest.origin - _upper_rest.origin).normalized(), hinge).inverse() * _upper_rest.basis
	_lower_in_frame = _arm_frame((_hand_rest.origin - _lower_rest.origin).normalized(), hinge).inverse() * _lower_rest.basis


func _process_modification_with_delta(_delta: float) -> void:
	var skeleton := get_skeleton()
	var camera := get_viewport().get_camera_3d() if is_inside_tree() else null
	if not skeleton or not camera or _hand < 0:
		return
	var body := _body_basis(camera.global_transform.basis)
	var to_skeleton := skeleton.global_transform.affine_inverse()
	var shoulder := to_skeleton * (camera.global_position + body * shoulder_offset)
	var hint := (to_skeleton.basis * (body * elbow_hint)).normalized()
	var fallback := (to_skeleton.basis * (body * Vector3(elbow_hint.x, 0.0, absf(elbow_hint.z) + 1.0))).normalized()
	var hand := _hand_rest
	var wrist := hand.origin

	# Keep the wrist within reach: the shoulder gives way, never the hand.
	var reach := (_upper_len + _lower_len) * 0.999
	var closest := absf(_upper_len - _lower_len) + 0.01
	var d := shoulder.distance_to(wrist)
	if d > reach or d < closest:
		var away := (shoulder - wrist).normalized() if d > 0.0001 else -hint
		d = clampf(d, closest, reach)
		shoulder = wrist + away * d
	var along := (wrist - shoulder) / d
	var a := (_upper_len * _upper_len - _lower_len * _lower_len + d * d) / (2.0 * d)
	# Bend direction: from the hint, blending to the fallback (back) as the arm
	# lines up with the hint, so it never degenerates.
	var primary := hint - along * hint.dot(along)
	var secondary := fallback - along * fallback.dot(along)
	var weight := clampf(primary.length() / 0.35, 0.0, 1.0)
	var bend := (primary.normalized() * weight if primary.length_squared() > 0.000001 else Vector3.ZERO) 			+ (secondary.normalized() * (1.0 - weight) if secondary.length_squared() > 0.000001 else Vector3.ZERO)
	if bend.length_squared() < 0.000001:
		bend = along.cross(Vector3.RIGHT if absf(along.x) < 0.9 else Vector3.UP)
	bend = bend.normalized()
	var elbow := shoulder + along * a + bend * sqrt(maxf(_upper_len * _upper_len - a * a, 0.0))

	var hinge := along.cross(bend)
	var upper_basis := (_arm_frame((elbow - shoulder).normalized(), hinge) * _upper_in_frame).orthonormalized()
	var lower_basis := (_arm_frame((wrist - elbow).normalized(), hinge) * _lower_in_frame).orthonormalized()
	skeleton.set_bone_global_pose(_upper, Transform3D(upper_basis, shoulder))
	skeleton.set_bone_global_pose(_lower, Transform3D(lower_basis, elbow))
	skeleton.set_bone_global_pose(_hand, hand)
	if _twist >= 0:
		var center := deg_to_rad(twist_center)
		var raw := _roll(lower_basis.inverse() * hand.basis, _lower_rest.basis.inverse() * _hand_rest.basis)
		if is_nan(_roll_tracked):
			_roll_tracked = wrapf(raw - center, -PI, PI) + center
		else:
			_roll_tracked += wrapf(raw - _roll_tracked, -PI, PI)
		var limit := deg_to_rad(twist_limit)
		_roll_tracked = clampf(_roll_tracked, center - limit, center + limit)
		var roll := _roll_tracked
		skeleton.set_bone_pose_rotation(_twist, _twist_rest_rotation * Quaternion(Vector3.UP, roll * twist_share))


## Body orientation from the head: yaw only, following the head lazily.
func _body_basis(head: Basis) -> Basis:
	var forward := -head.z
	var yaw := atan2(-forward.x, -forward.z) if Vector2(forward.x, forward.z).length() > 0.1 else _body_yaw
	if is_nan(_body_yaw):
		_body_yaw = yaw if not is_nan(yaw) else 0.0
	elif not is_nan(yaw):
		var off := angle_difference(_body_yaw, yaw)
		var limit := deg_to_rad(body_follow_angle)
		if absf(off) > limit:
			_body_yaw = wrapf(_body_yaw + off - signf(off) * limit, -PI, PI)
	return Basis(Vector3.UP, _body_yaw)


## Orthonormal frame with Y along [param y] and X on the elbow hinge (the
## hinge's part perpendicular to Y).
static func _arm_frame(y: Vector3, hinge: Vector3) -> Basis:
	var x := (hinge - y * hinge.dot(y)).normalized()
	return Basis(x, y, x.cross(y))


## Roll of [param relation] (hand in forearm space) relative to [param rest_relation] about the forearm's Y.
static func _roll(relation: Basis, rest_relation: Basis) -> float:
	var q := (relation * rest_relation.inverse()).get_rotation_quaternion()
	return wrapf(2.0 * atan2(q.y, q.w), -PI, PI)
