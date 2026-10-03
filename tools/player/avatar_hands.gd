extends SceneTree
## Writes the avatar's hand scenes, core/player/hands/<character>_hand_<side>.tscn
## (D-037), from the character's rigged hand glbs:
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
## "Open" and "Grip" (trigger: index finger, grip: the others), as XR Tools does.
## Loads the glbs with GLTFDocument, so it works before the editor imports them.
## --check compares with the files on disk and quits with 1 on a difference.

const CHARACTER := "silena_vesper"
const GLB := "res://assets/characters/%s/%s_hand_%s.glb"
const OUT := "res://core/player/hands/%s_hand_%s.tscn"
const XR_MODEL := "res://addons/godot-xr-tools/hands/model/Hand_Nails_low_%s.gltf"
## Headset corrections in the XR Tools model frame, applied after the fit.
const TUNE := {
	"left": {"position": Vector3.ZERO, "rotation_degrees": Vector3.ZERO},
	"right": {"position": Vector3.ZERO, "rotation_degrees": Vector3.ZERO},
}
const GRIP_FINGERS := ["Thumb", "Middle", "Ring", "Little"]
const FINGER_BONES := ["Metacarpal", "Proximal", "Intermediate", "Distal", "Tip"]


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
	var glb := GLB % [CHARACTER, CHARACTER, side]
	var ours := _load(glb)
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

	var grip_filters: PackedStringArray = []
	var trigger_filters: PackedStringArray = []
	for finger: String in ["Thumb", "Index", "Middle", "Ring", "Little"]:
		for part: String in FINGER_BONES:
			if finger == "Thumb" and part == "Intermediate":
				continue
			var track := "Armature/Skeleton3D:%s%s%s" % [cap, finger, part]
			if finger == "Index":
				trigger_filters.append(track)
			else:
				grip_filters.append(track)

	var euler := fit.basis.get_euler() * 180.0 / PI
	var lines: PackedStringArray = [
		"[gd_scene format=3]",
		"",
		"[ext_resource type=\"Script\" path=\"res://core/player/hands/avatar_hand.gd\" id=\"1_hand\"]",
		"[ext_resource type=\"PackedScene\" path=\"%s\" id=\"2_model\"]" % glb,
		"",
		"[sub_resource type=\"AnimationNodeAnimation\" id=\"AnimationNodeAnimation_open\"]",
		"animation = &\"Open\"",
		"",
		"[sub_resource type=\"AnimationNodeAnimation\" id=\"AnimationNodeAnimation_closed1\"]",
		"animation = &\"Grip\"",
		"",
		"[sub_resource type=\"AnimationNodeAnimation\" id=\"AnimationNodeAnimation_closed2\"]",
		"animation = &\"Grip\"",
		"",
		"[sub_resource type=\"AnimationNodeBlend2\" id=\"AnimationNodeBlend2_trigger\"]",
		"filter_enabled = true",
		"filters = %s" % _string_array(trigger_filters),
		"",
		"[sub_resource type=\"AnimationNodeBlend2\" id=\"AnimationNodeBlend2_grip\"]",
		"filter_enabled = true",
		"filters = %s" % _string_array(grip_filters),
		"",
		"[sub_resource type=\"AnimationNodeBlendTree\" id=\"AnimationNodeBlendTree_hand\"]",
		"nodes/OpenHand/node = SubResource(\"AnimationNodeAnimation_open\")",
		"nodes/OpenHand/position = Vector2(-600, 100)",
		"nodes/ClosedHand1/node = SubResource(\"AnimationNodeAnimation_closed1\")",
		"nodes/ClosedHand1/position = Vector2(-600, 300)",
		"nodes/ClosedHand2/node = SubResource(\"AnimationNodeAnimation_closed2\")",
		"nodes/ClosedHand2/position = Vector2(-360, 300)",
		"nodes/Trigger/node = SubResource(\"AnimationNodeBlend2_trigger\")",
		"nodes/Trigger/position = Vector2(-360, 20)",
		"nodes/Grip/node = SubResource(\"AnimationNodeBlend2_grip\")",
		"nodes/Grip/position = Vector2(0, 20)",
		"node_connections = [&\"Grip\", 0, &\"Trigger\", &\"Grip\", 1, &\"ClosedHand2\", &\"Trigger\", 0, &\"OpenHand\", &\"Trigger\", 1, &\"ClosedHand1\", &\"output\", 0, &\"Grip\"]",
		"",
		"[sub_resource type=\"SphereShape3D\" id=\"SphereShape3D_fingertip\"]",
		"radius = 0.012",
		"",
		"[node name=\"%sHand\" type=\"Node3D\"]" % cap,
		"script = ExtResource(\"1_hand\")",
		"hand_blend_tree = SubResource(\"AnimationNodeBlendTree_hand\")",
		"metadata/_doc = \"Player's visible %s hand: %s's glove (D-037), posed by grip/trigger, with the index Fingertip press area. Generated by tools/player/avatar_hands.gd; don't edit.\"" % [side, CHARACTER.capitalize()],
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
		"[node name=\"AnimationTree\" type=\"AnimationTree\" parent=\".\"]",
		"root_node = NodePath(\"../Offset/Model\")",
		"tree_root = SubResource(\"AnimationNodeBlendTree_hand\")",
		"anim_player = NodePath(\"../Offset/Model/AnimationPlayer\")",
		"parameters/Grip/blend_amount = 0.0",
		"parameters/Trigger/blend_amount = 0.0",
		"",
		"[editable path=\"Offset/Model\"]",
		"",
	]
	return "\n".join(lines)


## Loads a glTF file as a scene in the tree (for global transforms).
func _load(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(ProjectSettings.globalize_path(path), state)
	assert(err == OK, "can't load %s" % path)
	var scene := doc.generate_scene(state) as Node3D
	root.add_child(scene)
	return scene


## Rest position of a bone's head in the scene root's frame.
func _bone(scene: Node3D, bone: String) -> Vector3:
	var skeleton: Skeleton3D = scene.find_children("*", "Skeleton3D", true, false)[0]
	var index := skeleton.find_bone(bone)
	assert(index >= 0, "no bone %s" % bone)
	var local := scene.global_transform.affine_inverse() * skeleton.global_transform
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
