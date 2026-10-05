class_name AvatarEyes
extends SkeletonModifier3D
## The avatar's eyes (D-050): turns the LeftEye and RightEye bones toward
## where the player looks and closes the lids (HeadMesh blend shapes BlinkLeft,
## BlinkRight). Runs after BodyIK, which has turned the head with the headset.
##
## Where the eyes look, the first that applies:
## 0. [member look_target], when set (scripts, tests).
## 1. Eye tracking (OpenXR eye gaze interaction, tracker /user/eyes_ext), when
##    the runtime offers it: the player's real gaze. Looking into a live
##    reflection, the eyes focus on the image behind the glass.
## 2. Eye contact: a live reflection (PlanarReflection) shows the face within
##    [member contact_angle] of the view's middle. The eyes look at their own
##    image (the eye midpoint mirrored at the plane), so the reflection looks
##    back at the player, as real eyes do when you look yourself in the eye.
## 3. Straight ahead with the head, converging at [member focus_distance].
##
## Each eye turns at most [member max_yaw] sideways and [member max_up] /
## [member max_down] (degrees from rest, head frame) and follows its target
## within [member saccade_time]. No blinking on its own by default: nobody sees
## their own reflection blink, since their eyes are closed then
## ([member auto_blink] turns it on, e.g. for a third-person view).
## [method set_lids] closes the lids from outside. Without the eye bones (an
## older glb) the modifier turns itself off.

## Eye tracker and the pose names it may carry (the action map's eye_gaze_pose).
const GAZE_TRACKER := &"/user/eyes_ext"
const GAZE_POSES: Array[StringName] = [&"eye_gaze_pose", &"default"]
## The glb's rest pose faces +Z: the eyes' rest gaze in skeleton space.
const REST_GAZE := Vector3.BACK

## Set by AvatarBody: the player's camera (the eye midpoint) and XROrigin3D.
var camera: Node3D
var origin: Node3D
## Most an eye turns sideways, up and down (degrees).
@export_range(0.0, 60.0) var max_yaw := 30.0
@export_range(0.0, 60.0) var max_up := 25.0
@export_range(0.0, 60.0) var max_down := 30.0
## Where the eyes converge when nothing else says (m).
@export var focus_distance := 1.5
## How far from the view's middle (degrees) the face's reflection may be for eye contact.
@export_range(0.0, 90.0) var contact_angle := 30.0
## Time constant of the eyes' movement (s): small, eyes jump.
@export var saccade_time := 0.03
## Blink by themselves every few seconds (off: see the class description).
@export var auto_blink := false
## Mesh carrying the blink shapes.
@export var head_mesh := &"HeadMesh"

## When finite, the eyes look at this point (world space) whatever else says.
var look_target := Vector3.INF
## Which source aimed the eyes last frame: &"target", &"tracking", &"contact" or &"ahead".
var gaze_source := &"ahead"
## The gaze target last frame (world space).
var gaze_target := Vector3.ZERO

var _head := -1
var _head_rest: Transform3D
var _eyes: Array[int] = []
var _eye_rest: Array[Transform3D] = []   # global rest
var _angles: Array[Vector2] = [Vector2.ZERO, Vector2.ZERO]   # yaw, pitch (radians)
var _mesh: MeshInstance3D
var _blink_shapes: Array[int] = [-1, -1]
var _lids_down_shape := -1
var _lids := Vector2.ZERO   # set_lids: left, right
var _blink_wait := 3.0
var _blink_time := -1.0


func _ready() -> void:
	var skeleton := get_skeleton()
	if not skeleton:
		return
	_head = skeleton.find_bone("Head")
	for side: String in ["Left", "Right"]:
		var bone := skeleton.find_bone("%sEye" % side)
		_eyes.append(bone)
		_eye_rest.append(skeleton.get_bone_global_rest(bone) if bone >= 0 else Transform3D())
	if _head < 0 or _eyes.has(-1):
		active = false
		return
	_head_rest = skeleton.get_bone_global_rest(_head)
	var found := skeleton.find_children(head_mesh, "MeshInstance3D", true, false)
	_mesh = found[0] as MeshInstance3D if found else null
	if _mesh:
		_blink_shapes = [_mesh.find_blend_shape_by_name(&"BlinkLeft"), _mesh.find_blend_shape_by_name(&"BlinkRight")]
		_lids_down_shape = _mesh.find_blend_shape_by_name(&"LookDownLids")


## Closes the lids (0 open, 1 closed), on top of any automatic blink.
func set_lids(left: float, right: float) -> void:
	_lids = Vector2(clampf(left, 0.0, 1.0), clampf(right, 0.0, 1.0))


func _process_modification_with_delta(delta: float) -> void:
	var skeleton := get_skeleton()
	if not skeleton or not camera or not is_instance_valid(camera):
		return
	var to_world := skeleton.global_transform
	var to_skeleton := to_world.affine_inverse()
	gaze_target = _gaze(camera.global_transform)
	var target := to_skeleton * gaze_target
	# The head's turn from rest (BodyIK set it this frame).
	var head := skeleton.get_bone_global_pose(_head)
	var turn := head.basis.orthonormalized() * _head_rest.basis.orthonormalized().inverse()
	var follow := 1.0 - exp(-delta / saccade_time) if delta > 0.0 else 1.0
	var pitch_sum := 0.0
	for i in _eyes.size():
		var eye_origin := head * (_head_rest.affine_inverse() * _eye_rest[i].origin)
		var dir := turn.inverse() * (target - eye_origin)
		var want := Vector2(atan2(dir.x, dir.z), atan2(dir.y, Vector2(dir.x, dir.z).length()))
		want.x = clampf(want.x, -deg_to_rad(max_yaw), deg_to_rad(max_yaw))
		want.y = clampf(want.y, -deg_to_rad(max_down), deg_to_rad(max_up))
		_angles[i] = _angles[i].lerp(want, follow)
		var look := Basis(Vector3.UP, _angles[i].x) * Basis(Vector3.RIGHT, -_angles[i].y)
		skeleton.set_bone_global_pose(_eyes[i], Transform3D(turn * look * _eye_rest[i].basis, eye_origin))
		pitch_sum += _angles[i].y
	_update_lids(delta, pitch_sum / _eyes.size())


## Where the eyes look this frame (world space), see the class description.
func _gaze(view: Transform3D) -> Vector3:
	var eye := view.origin
	var forward := -view.basis.z.normalized()
	if look_target.is_finite():
		gaze_source = &"target"
		return look_target
	var tracked := _tracked_gaze()
	if tracked != Vector3.ZERO:
		gaze_source = &"tracking"
		return eye + tracked * _focus_through_reflections(eye, tracked)
	var best := cos(deg_to_rad(contact_angle))
	var contact := Vector3.ZERO
	for r in PlanarReflection.live_surfaces():
		var plane := r.plane()
		var n := plane.basis.z
		var s := (eye - plane.origin).dot(n)
		if s < 0.05:
			continue
		# The face's image lies on the line through the plane's foot point; it
		# shows only if that point is on the rectangle.
		var foot := plane.affine_inverse() * (eye - n * s)
		if absf(foot.x) > r.size.x * 0.5 or absf(foot.y) > r.size.y * 0.5:
			continue
		var facing := forward.dot(-n)
		if facing > best:
			best = facing
			contact = eye - n * (2.0 * s)
	if contact != Vector3.ZERO:
		gaze_source = &"contact"
		return contact
	gaze_source = &"ahead"
	return eye + forward * focus_distance


## The tracked gaze direction (world space), or zero without eye tracking.
func _tracked_gaze() -> Vector3:
	if not origin or not is_instance_valid(origin):
		return Vector3.ZERO
	var tracker := XRServer.get_tracker(GAZE_TRACKER) as XRPositionalTracker
	if not tracker:
		return Vector3.ZERO
	for pose_name in GAZE_POSES:
		var pose := tracker.get_pose(pose_name)
		if pose and pose.has_tracking_data:
			return -(origin.global_basis * pose.get_adjusted_transform().basis).z.normalized()
	return Vector3.ZERO


## Focus distance along a gaze: through a live reflection the image is twice as
## far as the glass (roughly; exact for one's own face).
func _focus_through_reflections(eye: Vector3, dir: Vector3) -> float:
	for r in PlanarReflection.live_surfaces():
		var plane := r.plane()
		var n := plane.basis.z
		var along := -dir.dot(n)
		var s := (eye - plane.origin).dot(n)
		if along <= 0.01 or s <= 0.0:
			continue
		var t := s / along
		var hit := plane.affine_inverse() * (eye + dir * t)
		if absf(hit.x) <= r.size.x * 0.5 and absf(hit.y) <= r.size.y * 0.5:
			return 2.0 * t
	return focus_distance


func _update_lids(delta: float, pitch: float) -> void:
	if not _mesh:
		return
	var blink := 0.0
	if auto_blink:
		if _blink_time < 0.0:
			_blink_wait -= delta
			if _blink_wait <= 0.0:
				_blink_time = 0.0
		else:
			# Down in 70 ms, up in 110 ms.
			_blink_time += delta
			blink = clampf(_blink_time / 0.07, 0.0, 1.0) if _blink_time < 0.07 else clampf(1.0 - (_blink_time - 0.07) / 0.11, 0.0, 1.0)
			if _blink_time >= 0.18:
				_blink_time = -1.0
				_blink_wait = randf_range(2.0, 6.0)
	for i in 2:
		if _blink_shapes[i] >= 0:
			_mesh.set_blend_shape_value(_blink_shapes[i], maxf(blink, _lids[i]))
	if _lids_down_shape >= 0:
		_mesh.set_blend_shape_value(_lids_down_shape, clampf(-pitch / deg_to_rad(max_down), 0.0, 1.0))
