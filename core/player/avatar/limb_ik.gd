class_name LimbIK
extends RefCounted
## Analytic two-bone IK for one limb of the avatar (arm or leg, D-040, D-041).
## Works in skeleton space and writes global bone poses.
##
## - The middle joint (elbow, knee) bends in the plane of root, end and a hint
##   direction; when the limb lines up with the hint, the bend blends towards
##   a fallback hint so it never degenerates.
## - Both bones keep their rest frame relative to the limb line and the bend
##   direction, so their roll follows the joint and never flips.
## - The end bone (hand, foot) takes the target transform exactly. If the
##   target is out of reach, the joints move apart up to [member max_stretch]
##   (the skin between them stretches; bones are never scaled, which would
##   shear the hand's children), beyond that the end lags behind the target.
## - An optional twist bone takes [member twist_share] of the end's roll about
##   the lower bone, tracked continuously around [member twist_center].

var max_stretch := 1.08
var twist_share := 0.7
var twist_center := deg_to_rad(-20.0)
var twist_limit := deg_to_rad(200.0)

var upper := -1
var lower := -1
var end := -1
var twist := -1
var upper_len := 0.0
var lower_len := 0.0

var _upper_in_frame: Basis
var _lower_in_frame: Basis
var _end_in_lower_rest: Basis
var _twist_rest_rotation: Quaternion
var _roll_tracked := NAN


## Reads the rest pose; returns false if a bone is missing.
func setup(skeleton: Skeleton3D, upper_name: String, lower_name: String, end_name: String, twist_name := "") -> bool:
	upper = skeleton.find_bone(upper_name)
	lower = skeleton.find_bone(lower_name)
	end = skeleton.find_bone(end_name)
	twist = skeleton.find_bone(twist_name) if twist_name else -1
	if upper < 0 or lower < 0 or end < 0:
		return false
	var u := skeleton.get_bone_global_rest(upper)
	var l := skeleton.get_bone_global_rest(lower)
	var e := skeleton.get_bone_global_rest(end)
	upper_len = u.origin.distance_to(l.origin)
	lower_len = l.origin.distance_to(e.origin)
	# Rest bend: the middle joint's offset from the root-end line.
	var line := (e.origin - u.origin).normalized()
	var bend := l.origin - u.origin
	bend -= line * bend.dot(line)
	if bend.length_squared() < 0.000001:
		bend = u.basis.z
	var hinge := line.cross(bend.normalized())
	_upper_in_frame = frame((l.origin - u.origin).normalized(), hinge).inverse() * u.basis
	_lower_in_frame = frame((e.origin - l.origin).normalized(), hinge).inverse() * l.basis
	_end_in_lower_rest = l.basis.inverse() * e.basis
	if twist >= 0:
		_twist_rest_rotation = skeleton.get_bone_rest(twist).basis.get_rotation_quaternion()
	return true


## Poses the limb from [param root] (the upper bone's head) to [param target]
## (the end bone's global pose), all in skeleton space.
func solve(skeleton: Skeleton3D, root: Vector3, target: Transform3D, hint: Vector3, fallback: Vector3) -> void:
	var wrist := target.origin
	var d := root.distance_to(wrist)
	var along := (wrist - root) / d if d > 0.0001 else -hint.normalized()
	var reach := (upper_len + lower_len) * 0.999
	var scale := 1.0
	if d > reach:
		scale = minf(d / reach, max_stretch)
		wrist = root + along * minf(d, reach * scale)
		d = root.distance_to(wrist)
	var a_len := upper_len * scale
	var b_len := lower_len * scale
	d = maxf(d, absf(a_len - b_len) + 0.01)
	var a := (a_len * a_len - b_len * b_len + d * d) / (2.0 * d)
	var primary := hint - along * hint.dot(along)
	var secondary := fallback - along * fallback.dot(along)
	var weight := clampf(primary.length() / 0.35, 0.0, 1.0)
	var bend := Vector3.ZERO
	if primary.length_squared() > 0.000001:
		bend += primary.normalized() * weight
	if secondary.length_squared() > 0.000001:
		bend += secondary.normalized() * (1.0 - weight)
	if bend.length_squared() < 0.000001:
		bend = along.cross(Vector3.RIGHT if absf(along.x) < 0.9 else Vector3.UP)
	bend = bend.normalized()
	var middle := root + along * a + bend * sqrt(maxf(a_len * a_len - a * a, 0.0))

	var hinge := along.cross(bend)
	var upper_basis := (frame((middle - root).normalized(), hinge) * _upper_in_frame).orthonormalized()
	var lower_basis := (frame((wrist - middle).normalized(), hinge) * _lower_in_frame).orthonormalized()
	skeleton.set_bone_global_pose(upper, Transform3D(upper_basis, root))
	skeleton.set_bone_global_pose(lower, Transform3D(lower_basis, middle))
	skeleton.set_bone_global_pose(end, Transform3D(target.basis, wrist))
	if twist >= 0:
		var raw := roll(lower_basis.inverse() * target.basis, _end_in_lower_rest)
		if is_nan(_roll_tracked):
			_roll_tracked = wrapf(raw - twist_center, -PI, PI) + twist_center
		else:
			_roll_tracked += wrapf(raw - _roll_tracked, -PI, PI)
		_roll_tracked = clampf(_roll_tracked, twist_center - twist_limit, twist_center + twist_limit)
		skeleton.set_bone_pose_rotation(twist, _twist_rest_rotation * Quaternion(Vector3.UP, _roll_tracked * twist_share))


## Forgets the tracked twist (after a teleport or a long pause).
func reset_twist() -> void:
	_roll_tracked = NAN


## Orthonormal frame with Y along [param y] and X on the joint hinge (its part
## perpendicular to Y).
static func frame(y: Vector3, hinge: Vector3) -> Basis:
	var x := (hinge - y * hinge.dot(y)).normalized()
	return Basis(x, y, x.cross(y))


## Roll of [param relation] against [param rest_relation] about local Y.
static func roll(relation: Basis, rest_relation: Basis) -> float:
	var q := (relation * rest_relation.inverse()).get_rotation_quaternion()
	return wrapf(2.0 * atan2(q.y, q.w), -PI, PI)
