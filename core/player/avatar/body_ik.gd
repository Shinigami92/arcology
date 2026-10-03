class_name BodyIK
extends SkeletonModifier3D
## Full-body pose of the avatar from the headset and both hands (D-041).
## Runs after the finger animation; poses, in order:
##
## 1. Body frame: yaw only, following the head lazily (it turns once the head
##    looks more than [member body_follow_angle] away).
## 2. Head: the eyes at the camera, the head bone turned with it (shadow only
##    in first person). The neck sits where the head puts it.
## 3. Hips under the neck at their rest offset; height from the head (crouching
##    lowers them, never higher than standing), moved so the torso keeps its
##    length. The torso's swing from rest to hips-to-neck is spread over Hips,
##    Spine, Chest and UpperChest.
## 4. Legs: the feet at their rest place under the hips on the floor (the
##    PlayerBody's height), knees towards the body's front (stepping: D-041 3b).
## 5. Arms: shoulders ride the chest, the hands go to the AvatarHand targets
##    (LimbIK, with forearm twist and a little stretch when out of reach).
##
## The glb's rest pose faces +Z; the body frame faces -Z like the player.
## Set up by AvatarBody (camera, ground, hand targets).

## Eye midpoint in the skeleton's rest space (glb coordinates).
@export var eye_rest := Vector3(0.0, 1.79, 0.127)
## How far the head can turn (degrees) before the body turns with it.
@export_range(0.0, 90.0) var body_follow_angle := 35.0
## Height of the soles' lowest point in the rest pose (glb y); the body is
## lifted by its negative so the soles touch the floor.
@export var sole_height := 0.0
## Share of the arm's swing (from its rest direction) the shoulder (clavicle) follows.
@export_range(0.0, 1.0) var clavicle_share := 0.3
## Most the clavicle turns (degrees).
@export_range(0.0, 60.0) var clavicle_max := 25.0
## Lowest hip height while crouching, as a share of the standing hip height.
@export_range(0.2, 1.0) var min_hip_share := 0.45
## Where the elbows point, in the body frame (x right, y up, z back), right arm; mirrored for the left.
@export var elbow_hint := Vector3(0.35, -1.0, 0.3)
## Where the knees point, in the body frame, right leg; mirrored for the left.
@export var knee_hint := Vector3(0.1, 0.0, -1.0)
## Share of the torso's swing taken by Hips, Spine, Chest and UpperChest (sums to 1).
@export var spine_shares := PackedFloat32Array([0.2, 0.25, 0.25, 0.3])

## Set by AvatarBody.
var camera: Node3D
## Stands on the floor (XR Tools' PlayerBody).
var ground: Node3D
var hand_targets := {}

const TORSO := ["Hips", "Spine", "Chest", "UpperChest"]
const FLIP := Basis(Vector3.UP, PI)

var _torso: Array[int] = []
var _torso_rest: Array[Transform3D] = []
var _neck := -1
var _head := -1
var _neck_rest: Transform3D
var _head_rest: Transform3D
var _shoulders := {}
var _arms := {}
var _legs := {}
var _feet_rest := {}
var _body_yaw := NAN


func _ready() -> void:
	var skeleton := get_skeleton()
	if not skeleton:
		return
	for bone_name: String in TORSO:
		var bone := skeleton.find_bone(bone_name)
		_torso.append(bone)
		_torso_rest.append(skeleton.get_bone_global_rest(bone) if bone >= 0 else Transform3D())
	_neck = skeleton.find_bone("Neck")
	_head = skeleton.find_bone("Head")
	if _torso.has(-1) or _neck < 0 or _head < 0:
		push_warning("BodyIK: missing torso bones")
		active = false
		return
	_neck_rest = skeleton.get_bone_global_rest(_neck)
	_head_rest = skeleton.get_bone_global_rest(_head)
	for side: String in ["Left", "Right"]:
		_shoulders[side] = skeleton.find_bone("%sShoulder" % side)
		var arm := LimbIK.new()
		if arm.setup(skeleton, "%sUpperArm" % side, "%sLowerArm" % side, "%sHand" % side, "%sLowerArmTwist" % side):
			_arms[side] = arm
		var leg := LimbIK.new()
		leg.max_stretch = 1.0
		if leg.setup(skeleton, "%sUpperLeg" % side, "%sLowerLeg" % side, "%sFoot" % side):
			_legs[side] = leg
			_feet_rest[side] = skeleton.get_bone_global_rest(leg.end)


func _process_modification_with_delta(_delta: float) -> void:
	var skeleton := get_skeleton()
	if not skeleton or not camera or not is_instance_valid(camera):
		return
	var to_skeleton := skeleton.global_transform.affine_inverse()
	var head_view := to_skeleton * camera.global_transform
	var floor_y := (to_skeleton * ground.global_position).y if ground and is_instance_valid(ground) else 0.0
	floor_y -= sole_height
	var body := _body_basis(head_view.basis)
	var rest_to_body := body * FLIP

	# Head: eyes on the camera, turned with it.
	var head_basis := head_view.basis.orthonormalized() * FLIP * _head_rest.basis
	var eye_in_head := _head_rest.basis.inverse() * (eye_rest - _head_rest.origin)
	var head := Transform3D(head_basis, head_view.origin - head_basis * eye_in_head)
	var neck_target := head * (_head_rest.affine_inverse() * _neck_rest.origin)

	# Hips: under the neck, lowered when crouching, torso length kept.
	var hips_rest := _torso_rest[0]
	var torso_rest := _neck_rest.origin - hips_rest.origin
	var torso_len := torso_rest.length()
	var hips := neck_target - rest_to_body * torso_rest
	hips.y = clampf(neck_target.y - torso_rest.y, floor_y + hips_rest.origin.y * min_hip_share, floor_y + hips_rest.origin.y)
	var dy := neck_target.y - hips.y
	if absf(dy) > torso_len:
		hips.y = neck_target.y - signf(dy) * torso_len
		dy = signf(dy) * torso_len
	# Horizontal hips offset from the neck: the rest offset, plus a move back
	# (sitting back) when the torso has to lean because the hips went down.
	var reach := sqrt(maxf(torso_len * torso_len - dy * dy, 0.0))
	var rest_flat := rest_to_body * Vector3(-torso_rest.x, 0.0, -torso_rest.z)
	var back := body * Vector3.BACK
	var flat := rest_flat.limit_length(reach)
	if reach > rest_flat.length():
		var b := rest_flat.dot(back)
		flat = rest_flat + back * (-b + sqrt(maxf(b * b - rest_flat.length_squared() + reach * reach, 0.0)))
	hips = Vector3(neck_target.x + flat.x, hips.y, neck_target.z + flat.z)

	# Torso: swing from the rest direction to hips-to-neck, spread along the
	# spine. The curved chain ends a little off the neck target: the hips take
	# up the rest, so the neck (and the eyes) land exactly.
	var swing := Quaternion((rest_to_body * torso_rest).normalized(), (neck_target - hips).normalized())
	var bases: Array[Basis] = []
	var share := 0.0
	for i in _torso.size():
		share += spine_shares[i] if i < spine_shares.size() else 0.0
		bases.append((Basis(Quaternion.IDENTITY.slerp(swing, clampf(share, 0.0, 1.0))) * rest_to_body * _torso_rest[i].basis).orthonormalized())
	var upper_chest_rest := _torso_rest[_torso_rest.size() - 1]
	var torso_now: Array[Transform3D] = []
	for attempt in 2:
		torso_now.clear()
		var parent := Transform3D()
		for i in _torso.size():
			var position := hips if i == 0 else parent * (_torso_rest[i - 1].affine_inverse() * _torso_rest[i].origin)
			parent = Transform3D(bases[i], position)
			torso_now.append(parent)
		hips += neck_target - parent * (upper_chest_rest.affine_inverse() * _neck_rest.origin)
	for i in _torso.size():
		skeleton.set_bone_global_pose(_torso[i], torso_now[i])
	# Neck between chest and head; the head exactly where the camera says.
	var chest := torso_now[torso_now.size() - 1]
	var neck_pos := chest * (upper_chest_rest.affine_inverse() * _neck_rest.origin)
	var neck_basis := Basis(chest.basis.get_rotation_quaternion().slerp(head_basis.get_rotation_quaternion() * (_head_rest.basis.inverse() * _neck_rest.basis).get_rotation_quaternion(), 0.5))
	skeleton.set_bone_global_pose(_neck, Transform3D(neck_basis, neck_pos))
	skeleton.set_bone_global_pose(_head, head)
	hips = torso_now[0].origin

	# Legs: feet at their rest place under the hips, on the floor.
	var hips_pose := torso_now[0]
	var stand := Transform3D(rest_to_body, Vector3(hips.x, floor_y, hips.z) - rest_to_body * Vector3(hips_rest.origin.x, 0.0, hips_rest.origin.z))
	for side: String in _legs:
		var leg: LimbIK = _legs[side]
		var foot: Transform3D = stand * (_feet_rest[side] as Transform3D)
		var root := hips_pose * (hips_rest.affine_inverse() * skeleton.get_bone_global_rest(leg.upper).origin)
		var mirror := -1.0 if side == "Left" else 1.0
		var hint := body * (knee_hint * Vector3(mirror, 1.0, 1.0))
		leg.solve(skeleton, root, foot, hint, body * Vector3(0.0, 0.0, -1.0))

	# Arms: shoulders ride the chest and follow the arm a little (the clavicle
	# takes a share of the arm's swing from its rest direction, so the coat
	# doesn't pinch at the armhole); hands to their targets.
	var chest_pose := torso_now[torso_now.size() - 1]
	for side: String in _arms:
		var arm: LimbIK = _arms[side]
		var target: Node3D = hand_targets.get(side)
		var hand: Transform3D
		if target and is_instance_valid(target) and target.is_visible_in_tree():
			hand = to_skeleton * target.global_transform
		else:
			# No hand: let the arm hang at the side.
			hand = Transform3D(rest_to_body, Vector3(hips.x, floor_y, hips.z) - rest_to_body * Vector3(hips_rest.origin.x, 0.0, hips_rest.origin.z)) * skeleton.get_bone_global_rest(arm.end)
		var upper_rest := skeleton.get_bone_global_rest(arm.upper)
		var root: Vector3
		var shoulder_bone: int = _shoulders[side]
		if shoulder_bone >= 0:
			var shoulder_rest := skeleton.get_bone_global_rest(shoulder_bone)
			var shoulder_pose := chest_pose * (upper_chest_rest.affine_inverse() * shoulder_rest)
			var joint := shoulder_rest.affine_inverse() * upper_rest.origin
			var rest_dir := chest_pose.basis * (upper_chest_rest.basis.inverse() * (skeleton.get_bone_global_rest(arm.end).origin - upper_rest.origin))
			var arm_swing := Quaternion(rest_dir.normalized(), (hand.origin - shoulder_pose * joint).normalized())
			var follow := Quaternion.IDENTITY.slerp(arm_swing, clavicle_share)
			var limit := deg_to_rad(clavicle_max)
			if follow.get_angle() > limit:
				follow = Quaternion.IDENTITY.slerp(arm_swing, limit / maxf(arm_swing.get_angle(), 0.0001))
			shoulder_pose.basis = Basis(follow) * shoulder_pose.basis
			skeleton.set_bone_global_pose(shoulder_bone, shoulder_pose)
			root = shoulder_pose * joint
		else:
			root = chest_pose * (upper_chest_rest.affine_inverse() * upper_rest.origin)
		var mirror := -1.0 if side == "Left" else 1.0
		var hint := body * (elbow_hint * Vector3(mirror, 1.0, 1.0))
		arm.solve(skeleton, root, hand, hint, body * Vector3(elbow_hint.x * mirror, 0.0, absf(elbow_hint.z) + 1.0))


## Body orientation (yaw only, facing -Z at yaw 0) following the head lazily.
func _body_basis(head: Basis) -> Basis:
	var forward := -head.z
	var flat := Vector2(forward.x, forward.z)
	if flat.length() > 0.1:
		var yaw := atan2(-forward.x, -forward.z)
		if is_nan(_body_yaw):
			_body_yaw = yaw
		else:
			var off := angle_difference(_body_yaw, yaw)
			var limit := deg_to_rad(body_follow_angle)
			if absf(off) > limit:
				_body_yaw = wrapf(_body_yaw + off - signf(off) * limit, -PI, PI)
	elif is_nan(_body_yaw):
		_body_yaw = 0.0
	return Basis(Vector3.UP, _body_yaw)


## Snaps the body to the head's current facing (after a teleport or recenter).
func reset() -> void:
	_body_yaw = NAN
	for side: String in _arms:
		(_arms[side] as LimbIK).reset_twist()
