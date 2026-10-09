extends "res://tools/tests/interaction/base.gd"
## Avatar group: fingertips, hand rig and arm IK, body IK, walking, sitting, coat springs, eyes, draw order.

const SKELETON := "Player/Avatar/Model/Armature/Skeleton3D"


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["fingertips", _test_fingertips],
		# Hand rig and arm IK share the posed hands, so they are one test.
		["hand_rig_arm_ik", _test_hand_rig],
		["body_ik", _test_body_ik],
		["walk", _test_walk],
		["sit_pose", _test_sit_pose],
		["coat_springs", _test_coat_springs],
		["eyes", _test_avatar_eyes],
		["after_ssao", _test_avatar_after_ssao],
	]


## Both hands carry a fingertip press area on the Player Hands layer, on the
## avatar's index finger tips (D-041).
func _test_fingertips() -> void:
	var found: Array[String] = []
	for side: String in ["Left", "Right"]:
		var tip := _main.get_node_or_null("Player/Avatar/Model/Armature/Skeleton3D/IndexTip%s/Fingertip" % side) as Area3D
		if tip and tip.collision_layer == 131072:
			found.append(side)
	_check("fingertip_areas", found == ["Left", "Right"], "fingertips on hands: %s" % [found])


## The eyes (D-050): straight ahead they look where the head does, converging
## in front of the face; a target far to the side turns them only to their
## limit; facing the bathroom mirror they look at their own image (eye
## contact, so the reflection looks back); the lids close on request.
## The player's own meshes draw after SSAO (transparent pass, no halos around
## the hands, D-055) and still cast shadows through a shadow-only copy each.
func _test_avatar_after_ssao() -> void:
	var skeleton := _avatar_skeleton("avatar_after_ssao")
	if skeleton == null:
		return
	var problems: Array[String] = []
	var visible := 0
	for node in skeleton.get_children():
		var mesh := node as MeshInstance3D
		if mesh == null or mesh.name in ["HeadMesh", "Collar"] or (mesh.name as String).ends_with("Shadow"):
			continue
		visible += 1
		var shadow := skeleton.get_node_or_null(NodePath(mesh.name + "Shadow")) as MeshInstance3D
		if shadow == null or shadow.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			problems.append("%s: no shadow-only copy" % mesh.name)
		if mesh.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			problems.append("%s casts shadows itself" % mesh.name)
		for i in mesh.mesh.get_surface_count():
			var mat := mesh.get_active_material(i) as BaseMaterial3D
			if mat and (mat.transparency != BaseMaterial3D.TRANSPARENCY_ALPHA or mat.depth_draw_mode != BaseMaterial3D.DEPTH_DRAW_ALWAYS):
				problems.append("%s surface %d is in the opaque pass" % [mesh.name, i])
			var cast := shadow.get_active_material(i) as BaseMaterial3D if shadow else null
			if cast and cast.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				problems.append("%sShadow surface %d is transparent (casts nothing)" % [mesh.name, i])
	_check("avatar_after_ssao", visible > 0 and problems.is_empty(),
			"%d first-person meshes; %s" % [visible, ", ".join(problems) if problems else "all after SSAO with shadow-only copies"])


func _test_avatar_eyes() -> void:
	var skeleton := _avatar_skeleton("avatar_eyes")
	if skeleton == null:
		return
	var eyes := skeleton.get_node_or_null("Eyes") as AvatarEyes
	var bones: Array[int] = [skeleton.find_bone("LeftEye"), skeleton.find_bone("RightEye")]
	if eyes == null or bones.has(-1):
		_check("avatar_eyes", false, "no Eyes modifier under the skeleton or no LeftEye/RightEye bones")
		return
	var body := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	# Back to the living room window: no reflection in view.
	body.teleport(Transform3D(Basis(Vector3.UP, PI), HOME.origin))
	await _frames(30)
	await skeleton.skeleton_updated
	var forward := -camera.global_basis.z
	var aim := _eye_aim_error(skeleton, bones, eyes.gaze_target)
	var ahead := camera.global_position + forward * eyes.focus_distance
	_check("avatar_eyes_ahead", eyes.gaze_source == &"ahead" and aim < 1.0 and eyes.gaze_target.distance_to(ahead) < 0.01,
			"source %s, eyes %.2f degrees off their target, target %.3f m from %.1f m ahead" % [eyes.gaze_source, aim, eyes.gaze_target.distance_to(ahead), eyes.focus_distance])

	eyes.look_target = camera.global_position + camera.global_basis.x * 1.0 + forward * 0.2
	await _frames(10)
	await skeleton.skeleton_updated
	var turn: Array[float] = []
	for i in bones.size():
		turn.append(rad_to_deg(_eye_dir(skeleton, bones[i]).angle_to(forward)))
	eyes.look_target = Vector3.INF
	_check("avatar_eyes_limit", absf(turn[0] - eyes.max_yaw) < 2.0 and absf(turn[1] - eyes.max_yaw) < 2.0,
			"a target 80 degrees to the side turns the eyes %.1f / %.1f degrees (limit %.0f)" % [turn[0], turn[1], eyes.max_yaw])

	# Facing the bathroom mirror (as the skyline test's reflection view).
	body.teleport(Transform3D(Basis(Vector3.UP, PI), Vector3(1.4, 0.0, 5.2)))
	await _frames(40)
	await skeleton.skeleton_updated
	var mirror := _main.get_node("Zones/Apartment/Props/BathMirror/Reflection") as PlanarReflection
	var plane := mirror.plane()
	var eye := camera.global_position
	var image := eye - plane.basis.z * (2.0 * (eye - plane.origin).dot(plane.basis.z))
	aim = _eye_aim_error(skeleton, bones, image)
	_check("avatar_eyes_mirror", eyes.gaze_source == &"contact" and eyes.gaze_target.distance_to(image) < 0.01 and aim < 1.0,
			"source %s, target %.3f m from the face's image, eyes %.2f degrees off it" % [eyes.gaze_source, eyes.gaze_target.distance_to(image), aim])

	var mesh := skeleton.find_child("HeadMesh", true, false) as MeshInstance3D
	var shapes: Array[int] = [-1, -1]
	if mesh:
		shapes = [mesh.find_blend_shape_by_name(&"BlinkLeft"), mesh.find_blend_shape_by_name(&"BlinkRight")]
	eyes.set_lids(1.0, 0.25)
	await skeleton.skeleton_updated
	var lids: Array[float] = [-1.0, -1.0]
	for i in 2:
		if shapes[i] >= 0:
			lids[i] = mesh.get_blend_shape_value(shapes[i])
	eyes.set_lids(0.0, 0.0)
	await skeleton.skeleton_updated
	var reopened := shapes[0] >= 0 and mesh.get_blend_shape_value(shapes[0]) == 0.0
	_check("avatar_eyes_lids", is_equal_approx(lids[0], 1.0) and is_equal_approx(lids[1], 0.25) and reopened,
			"BlinkLeft %.2f (want 1), BlinkRight %.2f (want 0.25), open again %s" % [lids[0], lids[1], reopened])
	camera.position = saved_camera
	await _frames(2)


## An eye bone's gaze (world space): its rest gaze is the glb's forward, +Z.
func _eye_dir(skeleton: Skeleton3D, bone: int) -> Vector3:
	var local := skeleton.get_bone_global_rest(bone).basis.inverse() * Vector3.BACK
	return (skeleton.global_basis * skeleton.get_bone_global_pose(bone).basis * local).normalized()


## The larger angle (degrees) between an eye's gaze and the line to `target`.
func _eye_aim_error(skeleton: Skeleton3D, bones: Array[int], target: Vector3) -> float:
	var worst := 0.0
	for bone in bones:
		var origin := skeleton.global_transform * skeleton.get_bone_global_pose(bone).origin
		worst = maxf(worst, rad_to_deg(_eye_dir(skeleton, bone).angle_to(target - origin)))
	return worst


## The avatar skeleton, or null after failing check `name`.
func _avatar_skeleton(name: String) -> Skeleton3D:
	var skeleton := _main.get_node_or_null(SKELETON) as Skeleton3D
	if skeleton == null:
		_check(name, false, "no avatar skeleton at " + SKELETON)
	return skeleton


## Hands where a seated player holds them: in reach, in front of the chest.
## Returns the controllers' transforms for _restore_hands().
func _hands_forward() -> Array[Transform3D]:
	var camera := get_viewport().get_camera_3d()
	var saved: Array[Transform3D] = []
	for side in SIDES:
		var controller := _main.get_node("Player/%sHand" % side) as Node3D
		saved.append(controller.global_transform)
		var x := -0.2 if side == "Left" else 0.2
		controller.global_transform = Transform3D(controller.global_basis, camera.global_transform * Vector3(x, -0.45, -0.3))
	await _frames(5)
	return saved


func _restore_hands(saved: Array[Transform3D]) -> void:
	for i in SIDES.size():
		(_main.get_node("Player/%sHand" % SIDES[i]) as Node3D).global_transform = saved[i]
	await _frames(2)


## The avatar's hand bones follow the AvatarHand targets, and each hand's
## controls curl its own fingers, each finger on its own (D-039, D-041); then
## the arm IK for that hand (same posed hands).
func _test_hand_rig() -> void:
	var skeleton := _avatar_skeleton("hand_rig")
	if skeleton == null:
		return
	var saved: Array[Transform3D] = await _hands_forward()
	for side: String in ["Left", "Right"]:
		var hand := _main.get_node_or_null("Player/%sHand/CollisionHand/Hand" % side) as AvatarHand
		if hand == null or hand.target == null:
			_check("hand_rig_%s" % side.to_lower(), false, "no AvatarHand with a target at Player/%sHand/CollisionHand/Hand" % side)
			continue
		var bone := skeleton.find_bone("%sHand" % side)
		var index := skeleton.find_bone("%sIndexTip" % side)
		var middle := skeleton.find_bone("%sMiddleTip" % side)
		# x: index tip, y: middle tip travel from the open pose, in the hand bone's frame
		var open: Array[Vector3] = []
		var moves: Array[Vector2] = []
		var drift := 0.0
		for forced: Vector2 in [Vector2(0, 0), Vector2(0, 1), Vector2(1, 0)]:
			hand.force_grip_trigger(forced.x, forced.y)
			await _frames(3)
			await skeleton.skeleton_updated
			var h := skeleton.get_bone_global_pose(bone)
			var tips: Array[Vector3] = [h.affine_inverse() * skeleton.get_bone_global_pose(index).origin, h.affine_inverse() * skeleton.get_bone_global_pose(middle).origin]
			if open.is_empty():
				open = tips
				drift = (skeleton.global_transform * h.origin).distance_to(hand.target.global_position)
			moves.append(Vector2(tips[0].distance_to(open[0]), tips[1].distance_to(open[1])))
		hand.force_grip_trigger()
		_check("hand_rig_%s_follows" % side.to_lower(), drift < 0.001, "hand bone %.4f m from its target" % drift)
		_check("hand_rig_%s_fingers_independent" % side.to_lower(),
				moves[1].x > 0.02 and moves[1].y < 0.002 and moves[2].x < 0.002 and moves[2].y > 0.02,
				"index / middle tip travel: trigger %s, grip %s" % [moves[1].snappedf(0.001), moves[2].snappedf(0.001)])
		await _test_arm_ik(side, skeleton)
	await _restore_hands(saved)


## The arm reaches the hand target from the shoulder without stretching, the
## elbow below the arm line, and wrist roll moves only the twist bone (headset
## bug: upper arm and forearm flipped half a turn at about -110 degrees, D-040).
func _test_arm_ik(side: String, skeleton: Skeleton3D) -> void:
	await skeleton.skeleton_updated
	var bones: Array[Transform3D] = []
	var rests: Array[Transform3D] = []
	for part: String in ["UpperArm", "LowerArm", "Hand"]:
		var bone := skeleton.find_bone("%s%s" % [side, part])
		bones.append(skeleton.get_bone_global_pose(bone))
		rests.append(skeleton.get_bone_global_rest(bone))
	var to_world := skeleton.global_transform
	var stretch := absf(bones[0].origin.distance_to(bones[1].origin) - rests[0].origin.distance_to(rests[1].origin)) \
			+ absf(bones[1].origin.distance_to(bones[2].origin) - rests[1].origin.distance_to(rests[2].origin))
	var sag := ((to_world * bones[0].origin + to_world * bones[2].origin) * 0.5).y - (to_world * bones[1].origin).y
	_check("arm_ik_%s" % side.to_lower(), stretch < 0.001 and sag > 0.0,
			"bone stretch %.4f m, elbow %.3f m below the arm line" % [stretch, sag])

	var controller := _main.get_node("Player/%sHand" % side) as Node3D
	var saved := controller.global_transform
	var axis := (to_world * bones[2].origin - to_world * bones[1].origin).normalized()
	var pivot := to_world * bones[2].origin
	var parts: Array[int] = [skeleton.find_bone("%sUpperArm" % side), skeleton.find_bone("%sLowerArm" % side), skeleton.find_bone("%sLowerArmTwist" % side)]
	var worst: Array[float] = [0.0, 0.0, 0.0]
	var last: Array[Quaternion] = []
	for step in range(-30, 31):
		controller.global_transform = Transform3D(Basis(axis, deg_to_rad(step * 5.0)), Vector3.ZERO).translated_local(-pivot).translated(pivot) * saved
		await get_tree().physics_frame
		await skeleton.skeleton_updated
		var now: Array[Quaternion] = []
		for i in parts.size():
			now.append((to_world * skeleton.get_bone_global_pose(parts[i])).basis.get_rotation_quaternion())
			if last:
				worst[i] = maxf(worst[i], rad_to_deg(now[i].angle_to(last[i])))
		last = now
	controller.global_transform = saved
	await _frames(2)
	_check("arm_ik_%s_roll" % side.to_lower(), worst[0] < 2.0 and worst[1] < 2.0 and worst[2] < 6.0,
			"largest change per 5 degrees of wrist roll: upper arm %.1f, forearm %.1f, twist %.1f degrees" % worst)


## The body stands under the headset: eyes at the camera, feet on the floor,
## and crouching (a lower head) bends the knees instead of sinking the feet.
## (Hands posed in front, as for the hand rig.)
func _test_body_ik() -> void:
	var skeleton := _avatar_skeleton("body_ik")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var ik := skeleton.get_node("BodyIK") as BodyIK
	var camera := get_viewport().get_camera_3d()
	var ground := _main.get_node("Player/PlayerBody") as Node3D
	var head := skeleton.find_bone("Head")
	var feet: Array[int] = [skeleton.find_bone("LeftFoot"), skeleton.find_bone("RightFoot")]
	var foot_rest := skeleton.get_bone_global_rest(feet[0]).origin.y
	var eye_in_head := skeleton.get_bone_global_rest(head).affine_inverse() * ik.eye_rest
	var saved := camera.position
	for case: Array in [["standing", 0.0], ["crouching", -0.5]]:
		camera.position = saved + Vector3(0.0, case[1], 0.0)
		await _frames(90)
		await skeleton.skeleton_updated
		var to_world := skeleton.global_transform
		var eye := to_world * skeleton.get_bone_global_pose(head) * eye_in_head
		var floor_y := ground.global_position.y
		var foot_y: Array[float] = []
		for foot in feet:
			foot_y.append((to_world * skeleton.get_bone_global_pose(foot).origin).y - floor_y - foot_rest + ik.sole_height)
		var thigh := skeleton.get_bone_global_pose(skeleton.find_bone("LeftUpperLeg")).basis.y
		var shin := skeleton.get_bone_global_pose(skeleton.find_bone("LeftLowerLeg")).basis.y
		var bend := rad_to_deg(thigh.angle_to(shin))
		var eye_off := eye.distance_to(camera.global_position)
		_check("body_ik_%s" % case[0], eye_off < 0.03 and absf(foot_y[0]) < 0.01 and absf(foot_y[1]) < 0.01 and (case[1] == 0.0 or bend > 30.0),
				"eyes %.3f m from the camera, feet %.3f / %.3f m off the floor, knee bent %.0f degrees" % [eye_off, foot_y[0], foot_y[1], bend])
	camera.position = saved
	await _frames(2)
	await _restore_hands(hands)


## Walking and sprinting step the feet: a planted foot never slides (a lagging
## hip drop used to drag it, D-043), the feet keep up with the body, lift on
## an arc, and settle after stopping (D-042).
## Starts at the player's start spot facing -Z (the window wall 2.6 m ahead).
func _test_walk() -> void:
	var skeleton := _avatar_skeleton("avatar_walk")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var ground := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var start := ground.global_transform
	var forward := -start.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	var feet: Array[int] = [skeleton.find_bone("LeftFoot"), skeleton.find_bone("RightFoot")]
	var rest_y := skeleton.get_bone_global_rest(feet[0]).origin.y - (skeleton.get_node("BodyIK") as BodyIK).sole_height
	var ik := skeleton.get_node("BodyIK") as BodyIK
	# Eyes at the avatar's standing height (the headset's calibrated 1.8 m):
	# straight legs, so steps need the hip drop.
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	await _frames(60)  # let the body land after the crouch test
	for case: Array in [["walk", 2.0], ["sprint", 4.0]]:
		var per_frame: float = case[1] / 90.0
		var frames := int(2.4 / per_frame)
		var floor_y := ground.global_position.y
		var last: Array[Vector3] = []
		var first: Array[Vector3] = []
		var sliding := 0
		var lift := 0.0
		var steps := [0, 0]
		var lifted := [false, false]
		var planted := [true, true]
		var worst_slip := 0.0
		for frame in frames + 90:
			if frame < frames:
				var t := ground.global_transform
				t.origin += forward * per_frame
				ground.teleport(t)
			await get_tree().physics_frame
			await skeleton.skeleton_updated
			var now: Array[Vector3] = []
			for foot in feet:
				now.append(skeleton.global_transform * skeleton.get_bone_global_pose(foot).origin)
			if first.is_empty():
				first = now
			if last:
				for i in 2:
					var height := now[i].y - floor_y - rest_y
					lift = maxf(lift, height)
					var up := height > 0.01
					if up and not lifted[i]:
						steps[i] += 1
					lifted[i] = up
					var flat := Vector2(now[i].x - last[i].x, now[i].z - last[i].z).length()
					if not ik.steps.stepping(i) and planted[i] and flat > 0.002:
						sliding += 1
						worst_slip = maxf(worst_slip, flat)
					planted[i] = not ik.steps.stepping(i)
			last = now
		var advanced: Array[float] = []
		for i in 2:
			advanced.append((last[i] - first[i]).dot(forward))
		var slip_ok := sliding == 0
		_check("avatar_%s_steps" % case[0], steps[0] >= 2 and steps[1] >= 2 and slip_ok and lift > 0.03 and absf(advanced[0] - 2.4) < 0.15 and absf(advanced[1] - 2.4) < 0.15,
				"%.1f m/s: steps %d / %d, frames a planted foot slid %d (worst %.1f mm), lift %.3f m, feet advanced %.2f / %.2f m (body 2.4 m, the window wall is 2.6 m ahead)" % [case[1], steps[0], steps[1], sliding, worst_slip * 1000.0, lift, advanced[0], advanced[1]])
		ground.teleport(start)
		await _frames(30)
	camera.position = saved_camera
	await _frames(30)
	await _restore_hands(hands)


## Seated on the sofa, the hips rest on the cushion and the feet stand forward
## of it on the floor, knees bent (D-042). Leaves the player standing at the
## sofa (the next test's _reset_rig() brings it back).
func _test_sit_pose() -> void:
	var skeleton := _avatar_skeleton("avatar_sit_pose")
	if skeleton == null:
		return
	var hands: Array[Transform3D] = await _hands_forward()
	var player := _main.get_node("Player") as ArcologyPlayer
	var seat := _main.get_node("Zones/Apartment/Seats/SofaSeat") as Seat
	await player.sit(seat)
	await _frames(20)
	await skeleton.skeleton_updated
	var w := skeleton.global_transform
	var hips := w * skeleton.get_bone_global_pose(skeleton.find_bone("Hips")).origin
	var foot := w * skeleton.get_bone_global_pose(skeleton.find_bone("LeftFoot")).origin
	var thigh := skeleton.get_bone_global_pose(skeleton.find_bone("LeftUpperLeg")).basis.y
	var shin := skeleton.get_bone_global_pose(skeleton.find_bone("LeftLowerLeg")).basis.y
	var facing := -seat.sit_point.global_basis.z
	var ahead := (foot - hips).dot(facing)
	var bend := rad_to_deg(thigh.angle_to(shin))
	# The knees overhang the cushion's front edge, so the shins hang in front
	# of the sofa, not through it (headset bug: the shins clipped the front).
	var sofa := _main.get_node("Zones/Apartment/Props/Sofa") as Node3D
	var edge := sofa.global_transform * Vector3(0.0, 0.44, 0.445)
	var overhang: Array[float] = []
	for side: String in ["Left", "Right"]:
		var knee := w * skeleton.get_bone_global_pose(skeleton.find_bone("%sLowerLeg" % side)).origin
		overhang.append((knee - edge).dot(facing))
	await player.stand()
	await _frames(20)
	await _restore_hands(hands)
	_check("avatar_sit_pose", absf(hips.y - 0.52) < 0.08 and ahead > 0.3 and bend > 60.0 and bend < 120.0 and foot.y < 0.15 and overhang.min() > 0.03,
			"hips at %.2f m (cushion 0.44), feet %.2f m ahead, knee bent %.0f degrees, foot at %.2f m, knees %.2f / %.2f m past the cushion edge" % [hips.y, ahead, bend, foot.y, overhang[0], overhang[1]])


## The coat skirt hangs calm when standing, swings when walking without
## going through the legs or blowing up, and lies on the seat when sitting
## instead of passing through it; the belt's cuffs and passkey dangle and swing
## without sinking into the thigh (D-044).
func _test_coat_springs() -> void:
	var skeleton := _avatar_skeleton("avatar_coat")
	if skeleton == null:
		return
	if skeleton.get_node_or_null("Springs") == null:
		_check("avatar_coat", false, "no Springs under the avatar skeleton")
		return
	var hands: Array[Transform3D] = await _hands_forward()
	# Eyes at the avatar's standing height (the headset's calibrated 1.8 m).
	var camera := get_viewport().get_camera_3d()
	var saved_camera := camera.position
	camera.position.y = 1.8
	var hips := skeleton.find_bone("Hips")
	var joints: Array[int] = []
	for chain: String in ["FrontLeft", "FrontRight", "SideLeft", "SideRight", "BackLeft", "BackRight"]:
		for n in [2, 3, 4]:
			joints.append(skeleton.find_bone("Coat%s%d" % [chain, n]))
	var legs: Array[Array] = []
	for side: String in SIDES:
		legs.append([skeleton.find_bone("%sUpperLeg" % side), skeleton.find_bone("%sLowerLeg" % side), 0.07])
		legs.append([skeleton.find_bone("%sLowerLeg" % side), skeleton.find_bone("%sFoot" % side), 0.055])
	# Rest relation of each joint to the hips.
	var hips_rest := skeleton.get_bone_global_rest(hips)
	var rest_local: Array[Vector3] = []
	for j in joints:
		rest_local.append(hips_rest.affine_inverse() * skeleton.get_bone_global_rest(j).origin)

	await _frames(60)
	await skeleton.skeleton_updated
	var hang := _coat_deviation(skeleton, hips, joints, rest_local)

	var ground := _main.get_node("Player/PlayerBody") as XRToolsPlayerBody
	var start := ground.global_transform
	var forward := -start.basis.z
	forward.y = 0.0
	forward = forward.normalized()
	# The items' tips (bone tail: the tail lengths in AvatarSprings).
	var items: Array[int] = [skeleton.find_bone("BeltCuffs2"), skeleton.find_bone("BeltPasskey1")]
	var tips: Array[Vector3] = [Vector3(0, 0.07, 0), Vector3(0, 0.09, 0)]
	var items_rest: Array[Vector3] = []
	for i in items.size():
		items_rest.append(hips_rest.affine_inverse() * (skeleton.get_bone_global_rest(items[i]) * tips[i]))
	var thigh: Array[int] = [skeleton.find_bone("RightUpperLeg"), skeleton.find_bone("RightLowerLeg")]
	var item_swing := 0.0
	var item_depth := 0.0
	var swing := 0.0
	var trail := 0.0  # back panels only: the legs don't push them much
	var depth := 0.0
	var finite := true
	for frame in 108 + 60:
		if frame < 108:
			var t := ground.global_transform
			t.origin += forward * (2.0 / 90.0)
			ground.teleport(t)
		await get_tree().physics_frame
		await skeleton.skeleton_updated
		swing = maxf(swing, _coat_deviation(skeleton, hips, joints, rest_local))
		trail = maxf(trail, _coat_deviation(skeleton, hips, joints.slice(12), rest_local.slice(12)))
		var ta := skeleton.get_bone_global_pose(thigh[0]).origin
		var tb := skeleton.get_bone_global_pose(thigh[1]).origin
		var hips_now := skeleton.get_bone_global_pose(hips)
		for i in items.size():
			var p := skeleton.get_bone_global_pose(items[i]) * tips[i]
			finite = finite and p.is_finite()
			item_swing = maxf(item_swing, p.distance_to(hips_now * items_rest[i]))
			item_depth = maxf(item_depth, 0.095 + 0.015 - p.distance_to(Geometry3D.get_closest_point_to_segment(p, ta, tb)))
		for j in joints:
			var p := skeleton.get_bone_global_pose(j).origin
			finite = finite and p.is_finite()
			for leg: Array in legs:
				var a := skeleton.get_bone_global_pose(leg[0]).origin
				var b := skeleton.get_bone_global_pose(leg[1]).origin
				var closest := Geometry3D.get_closest_point_to_segment(p, a, b)
				depth = maxf(depth, float(leg[2]) + 0.03 - p.distance_to(closest))
	ground.teleport(start)
	await _frames(30)

	var player := _main.get_node("Player") as ArcologyPlayer
	var seat := _main.get_node("Zones/Apartment/Seats/SofaSeat") as Seat
	await player.sit(seat)
	await _frames(60)
	await skeleton.skeleton_updated
	var lowest := INF
	for i in joints.size():
		if i >= 6:  # side and back chains rest on the seat; the front hangs past the knees
			lowest = minf(lowest, (skeleton.global_transform * skeleton.get_bone_global_pose(joints[i]).origin).y)
	await player.stand()
	camera.position = saved_camera
	await _frames(30)
	await _restore_hands(hands)
	_check("avatar_belt_items", finite and item_swing > 0.005 and item_swing < 0.2 and item_depth < 0.02,
			"cuffs and passkey swing %.3f m while walking, deepest into the thigh %.3f m" % [item_swing, item_depth])
	_check("avatar_coat", finite and hang < 0.08 and swing < 0.5 and trail > 0.03 and trail < 0.25 and depth < 0.03 and lowest > 0.40,
			"standing off rest %.3f m, walking: skirt off rest %.3f m (legs push the front), back trails %.3f m, deepest into a leg %.3f m; seated side/back skirt lowest at %.2f m (cushion 0.44)" % [hang, swing, trail, depth, lowest])


## Largest distance of the coat joints from where the rest pose puts them
## relative to the hips.
func _coat_deviation(skeleton: Skeleton3D, hips: int, joints: Array[int], rest_local: Array[Vector3]) -> float:
	var hips_pose := skeleton.get_bone_global_pose(hips)
	var worst := 0.0
	for i in joints.size():
		worst = maxf(worst, (hips_pose * rest_local[i]).distance_to(skeleton.get_bone_global_pose(joints[i]).origin))
	return worst
