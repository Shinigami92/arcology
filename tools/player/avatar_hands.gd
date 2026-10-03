extends SceneTree
## Writes the avatar's hand scenes, core/player/hands/<character>_hand_<side>.tscn
## (D-037), from the character's rigged arm glbs (glove and sleeve; the older
## hand-only glbs if no arm glb exists):
##
##   "$GODOT4_EDITOR" --headless --path . --script res://tools/player/avatar_hands.gd
##   "$GODOT4_EDITOR" --headless --path . --script res://tools/player/avatar_hands.gd -- --check
##
## Each glb hand is fitted onto the XR Tools hand it replaces (whose placement
## on the controller was tuned in the headset in M1): the palm center (between
## the wrist and the middle knuckle), the hand's length axis (wrist to middle
## knuckle) and the palm plane (index to little knuckle) of both rest poses are
## matched; the glb keeps its own size. TUNE adds headset corrections on top.
## The scene: AvatarHand root -> Offset (XR Tools sets it to the controller's
## palm offset at runtime) -> Model (the glb, fitted) with the index Fingertip
## press area on the <Side>IndexTip bone, an AnimationTree blending the glb's
## "Open" and "Grip" per finger (Index, Middle, Ring = ring + little, Thumb),
## driven by AvatarHand from the controls each finger rests on (D-039). With an
## arm (an <Side>UpperArm bone), an ArmIK modifier places shoulder and elbow
## (D-040): its shoulder offset is the glb's upper arm head relative to AVATAR_EYE.
## Loads the glbs with GLTFDocument, so it works before the editor imports them.
## --check compares with the files on disk and quits with 1 on a difference.

const CHARACTER := "silena_vesper"
const GLB := "res://assets/characters/%s/%s_%s_%s.glb"
## The avatar's eye midpoint in the glb's coordinates (the body faces +Z there).
const AVATAR_EYE := Vector3(0.0, 1.7899, 0.1268)
## Where the right elbow points, in the body frame (x right, y up, z back); mirrored for the left.
const ELBOW_HINT := Vector3(0.35, -1.0, 0.3)
const OUT := "res://core/player/hands/%s_hand_%s.tscn"
const XR_MODEL := "res://addons/godot-xr-tools/hands/model/Hand_Nails_low_%s.gltf"
## Headset corrections in the XR Tools model frame, applied after the fit.
const TUNE := {
	"left": {"position": Vector3.ZERO, "rotation_degrees": Vector3.ZERO},
	"right": {"position": Vector3.ZERO, "rotation_degrees": Vector3.ZERO},
}
const FINGER_BONES := ["Metacarpal", "Proximal", "Intermediate", "Distal", "Tip"]
## Blend nodes in chain order and the fingers each one curls.
const BLENDS := [["Index", ["Index"]], ["Middle", ["Middle"]], ["Ring", ["Ring", "Little"]], ["Thumb", ["Thumb"]]]


func _init() -> void:
	var check := "--check" in OS.get_cmdline_user_args()
	var differences := 0
	for side: String in ["left", "right"]:
		var text := _hand_scene(side)
		var path := OUT % [CHARACTER, side]
		var old := FileAccess.get_file_as_string(path)
		if check:
			if old != text:
				print("DIFFERS %s" % path)
				differences += 1
		elif old != text:
			var file := FileAccess.open(path, FileAccess.WRITE)
			file.store_string(text)
			print("WROTE %s" % path)
		else:
			print("UNCHANGED %s" % path)
	quit(differences)


func _hand_scene(side: String) -> String:
	var cap := side.capitalize()
	var s := cap.left(1)
	var glb := GLB % [CHARACTER, CHARACTER, "arm", side]
	if not FileAccess.file_exists(glb):
		glb = GLB % [CHARACTER, CHARACTER, "hand", side]
	var ours := _load(glb)
	var arm_ik: PackedStringArray = []
	if _has_bone(ours, "%sUpperArm" % cap):
		# The glb faces +Z, the player's body frame -Z: turn the offset half around.
		var offset := Basis(Vector3.UP, PI) * (_bone(ours, "%sUpperArm" % cap) - AVATAR_EYE)
		var hint := ELBOW_HINT * Vector3(-1.0 if side == "left" else 1.0, 1.0, 1.0)
		arm_ik = [
			"[node name=\"ArmIK\" type=\"SkeletonModifier3D\" parent=\"Offset/Model/Armature/Skeleton3D\"]",
			"script = ExtResource(\"3_arm_ik\")",
			"side = \"%s\"" % cap,
			"shoulder_offset = %s" % _vec(offset),
			"elbow_hint = %s" % _vec(hint),
			"",
		]
		print("%s: shoulder %s from the eyes (body frame)" % [side, _vec(offset)])
	var xr := _load(XR_MODEL % s)
	var ours_frame := _palm_frame(ours, "%sHand" % cap, "%sMiddleProximal" % cap, "%sIndexProximal" % cap, "%sLittleProximal" % cap)
	var xr_frame := _palm_frame(xr, "Wrist_%s" % s, "Middle_Proximal_%s" % s, "Index_Proximal_%s" % s, "Little_Proximal_%s" % s)
	var tune: Dictionary = TUNE[side]
	var tuning := Transform3D(Basis.from_euler((tune["rotation_degrees"] as Vector3) * PI / 180.0), tune["position"])
	var fit := tuning * xr_frame * ours_frame.affine_inverse()
	var ours_len := _bone(ours, "%sHand" % cap).distance_to(_bone(ours, "%sMiddleProximal" % cap))
	var xr_len := _bone(xr, "Wrist_%s" % s).distance_to(_bone(xr, "Middle_Proximal_%s" % s))
	var residuals: PackedStringArray = []
	for pair: Array in [["Hand", "Wrist"], ["IndexProximal", "Index_Proximal"], ["LittleProximal", "Little_Proximal"], ["IndexTip", "Index_Tip"]]:
		var moved := fit * _bone(ours, "%s%s" % [cap, pair[0]])
		residuals.append("%s %.1f mm" % [pair[1], moved.distance_to(_bone(xr, "%s_%s" % [pair[1], s])) * 1000.0])
	print("%s: wrist to middle knuckle %.3f m (XR Tools hand %.3f m); off the XR Tools hand: %s" % [side, ours_len, xr_len, ", ".join(residuals)])
	ours.free()
	xr.free()

	var euler := fit.basis.get_euler() * 180.0 / PI
	var lines: PackedStringArray = [
		"[gd_scene format=3]",
		"",
		"[ext_resource type=\"Script\" path=\"res://core/player/hands/avatar_hand.gd\" id=\"1_hand\"]",
		"[ext_resource type=\"PackedScene\" path=\"%s\" id=\"2_model\"]" % glb,
	]
	if arm_ik:
		lines.append("[ext_resource type=\"Script\" path=\"res://core/player/hands/arm_ik.gd\" id=\"3_arm_ik\"]")
	lines.append("")
	lines.append_array(_blend_tree(cap))
	lines.append_array([
		"[sub_resource type=\"SphereShape3D\" id=\"SphereShape3D_fingertip\"]",
		"radius = 0.012",
		"",
		"[node name=\"%sHand\" type=\"Node3D\"]" % cap,
		"script = ExtResource(\"1_hand\")",
		"hand_blend_tree = SubResource(\"AnimationNodeBlendTree_hand\")",
		"metadata/_doc = \"Player's visible %s hand: %s's glove (D-037), each finger curled by the control it rests on (D-039), with the index Fingertip press area. Generated by tools/player/avatar_hands.gd; don't edit.\"" % [side, CHARACTER.capitalize()],
		"",
		"[node name=\"Offset\" type=\"Node3D\" parent=\".\"]",
		"metadata/_doc = \"Moved to the controller's palm offset by XR Tools at runtime.\"",
		"",
		"[node name=\"Model\" parent=\"Offset\" instance=ExtResource(\"2_model\")]",
		"position = %s" % _vec(fit.origin),
		"rotation_degrees = %s" % _vec(euler),
		"",
		"[node name=\"IndexTip\" type=\"BoneAttachment3D\" parent=\"Offset/Model/Armature/Skeleton3D\"]",
		"bone_name = \"%sIndexTip\"" % cap,
		"",
		"[node name=\"Fingertip\" type=\"Area3D\" parent=\"Offset/Model/Armature/Skeleton3D/IndexTip\"]",
		"collision_layer = 131072",
		"collision_mask = 0",
		"monitoring = false",
		"metadata/_doc = \"Detection-only fingertip on the Player Hands layer: presses XR Tools area buttons (ABPanel, switches) without adding finger collision.\"",
		"",
		"[node name=\"CollisionShape3D\" type=\"CollisionShape3D\" parent=\"Offset/Model/Armature/Skeleton3D/IndexTip/Fingertip\"]",
		"shape = SubResource(\"SphereShape3D_fingertip\")",
		"",
	])
	lines.append_array(arm_ik)
	lines.append_array([
		"[node name=\"AnimationTree\" type=\"AnimationTree\" parent=\".\"]",
		"root_node = NodePath(\"../Offset/Model\")",
		"tree_root = SubResource(\"AnimationNodeBlendTree_hand\")",
		"anim_player = NodePath(\"../Offset/Model/AnimationPlayer\")",
	])
	for blend: Array in BLENDS:
		lines.append("parameters/%s/blend_amount = 0.0" % blend[0])
	lines.append_array(["", "[editable path=\"Offset/Model\"]", ""])
	return "\n".join(lines)


## Sub-resources of the hand's blend tree: "Open", then per finger group a
## Blend2 (filtered to its bones) towards "Grip", chained into the output.
func _blend_tree(cap: String) -> PackedStringArray:
	var lines: PackedStringArray = [
		"[sub_resource type=\"AnimationNodeAnimation\" id=\"AnimationNodeAnimation_open\"]",
		"animation = &\"Open\"",
		"",
	]
	var nodes: PackedStringArray = [
		"[sub_resource type=\"AnimationNodeBlendTree\" id=\"AnimationNodeBlendTree_hand\"]",
		"nodes/OpenHand/node = SubResource(\"AnimationNodeAnimation_open\")",
		"nodes/OpenHand/position = Vector2(-600, 0)",
	]
	var connections: PackedStringArray = []
	var previous := "OpenHand"
	for i in BLENDS.size():
		var blend: String = BLENDS[i][0]
		var tracks: PackedStringArray = []
		for finger: String in BLENDS[i][1]:
			for part: String in FINGER_BONES:
				if not (finger == "Thumb" and part == "Intermediate"):
					tracks.append("Armature/Skeleton3D:%s%s%s" % [cap, finger, part])
		lines.append_array([
			"[sub_resource type=\"AnimationNodeAnimation\" id=\"AnimationNodeAnimation_grip_%s\"]" % blend.to_lower(),
			"animation = &\"Grip\"",
			"",
			"[sub_resource type=\"AnimationNodeBlend2\" id=\"AnimationNodeBlend2_%s\"]" % blend.to_lower(),
			"filter_enabled = true",
			"filters = %s" % _string_array(tracks),
			"",
		])
		nodes.append_array([
			"nodes/Closed%s/node = SubResource(\"AnimationNodeAnimation_grip_%s\")" % [blend, blend.to_lower()],
			"nodes/Closed%s/position = Vector2(%d, 250)" % [blend, -400 + 220 * i],
			"nodes/%s/node = SubResource(\"AnimationNodeBlend2_%s\")" % [blend, blend.to_lower()],
			"nodes/%s/position = Vector2(%d, 0)" % [blend, -300 + 220 * i],
		])
		connections.append_array(["&\"%s\", 0, &\"%s\"" % [blend, previous], "&\"%s\", 1, &\"Closed%s\"" % [blend, blend]])
		previous = blend
	connections.append("&\"output\", 0, &\"%s\"" % previous)
	nodes.append("node_connections = [%s]" % ", ".join(connections))
	lines.append_array(nodes)
	lines.append("")
	return lines


## Loads a glTF file as a scene in the tree (for global transforms).
func _load(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(ProjectSettings.globalize_path(path), state)
	assert(err == OK, "can't load %s" % path)
	var scene := doc.generate_scene(state) as Node3D
	root.add_child(scene)
	return scene


func _has_bone(scene: Node3D, bone: String) -> bool:
	var skeleton: Skeleton3D = scene.find_children("*", "Skeleton3D", true, false)[0]
	return skeleton.find_bone(bone) >= 0


## Rest position of a bone's head in the scene root's frame.
func _bone(scene: Node3D, bone: String) -> Vector3:
	var skeleton: Skeleton3D = scene.find_children("*", "Skeleton3D", true, false)[0]
	var index := skeleton.find_bone(bone)
	assert(index >= 0, "no bone %s" % bone)
	var local := Transform3D()
	var node: Node = skeleton
	while node != scene:
		local = (node as Node3D).transform * local
		node = node.get_parent()
	return local * skeleton.get_bone_global_rest(index).origin


## Palm frame: origin between wrist and middle knuckle, X along the hand,
## Y normal to the palm plane (index to little knuckle).
func _palm_frame(scene: Node3D, wrist: String, middle: String, index: String, little: String) -> Transform3D:
	var w := _bone(scene, wrist)
	var m := _bone(scene, middle)
	var x := (m - w).normalized()
	var y := x.cross(_bone(scene, index) - _bone(scene, little)).normalized()
	return Transform3D(Basis(x, y, x.cross(y)), (w + m) * 0.5)


func _vec(v: Vector3) -> String:
	return "Vector3(%s, %s, %s)" % [_num(v.x), _num(v.y), _num(v.z)]


func _num(f: float) -> String:
	var r := snappedf(f, 0.0001)
	return str(0.0 if is_zero_approx(r) else r).trim_suffix(".0")


func _string_array(items: PackedStringArray) -> String:
	var quoted: PackedStringArray = []
	for item in items:
		quoted.append("\"%s\"" % item)
	return "[%s]" % ", ".join(quoted)
