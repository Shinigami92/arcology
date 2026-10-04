class_name AvatarBody
extends Node3D
## Root of the avatar's body scene (D-041), a child of the player's XROrigin3D.
## Connects BodyIK to the headset, the floor (XR Tools' PlayerBody, which
## stands on the ground under the camera; the origin is raised by the seated
## height calibration) and the AvatarHand targets, receives the finger curls
## from the hands, and renders the meshes in [member shadow_only_meshes] as
## shadows only (first person: the head, and the collar, which crowds the view
## when looking down).
##
## Scene (written by tools/player/avatar.gd): AvatarBody -> Model (the glb) with
## BodyIK, the AvatarSprings (coat, belt items) and the Fingertip press areas on
## the skeleton, and an AnimationTree blending "Open" to "Grip" per finger group
## and side (parameters <Side><Finger>/blend_amount).

const FINGERS: Array[StringName] = [&"Index", &"Middle", &"Ring", &"Thumb"]

## Meshes (node names under the skeleton) drawn as shadows only.
@export var shadow_only_meshes: PackedStringArray = ["HeadMesh", "Collar"]

var _tree: AnimationTree
var _ik: BodyIK
var _springs: AvatarSprings


func _ready() -> void:
	add_to_group(&"avatar_body")
	_tree = get_node_or_null("AnimationTree") as AnimationTree
	var found := find_children("*", "BodyIK", true, false)
	_ik = found[0] as BodyIK if found else null
	found = find_children("*", "AvatarSprings", true, false)
	_springs = found[0] as AvatarSprings if found else null
	for mesh_name in shadow_only_meshes:
		for node in find_children(mesh_name, "MeshInstance3D", true, false):
			(node as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	_connect.call_deferred()


## Finds the headset, the origin and the hand targets (they may be ready after us).
func _connect() -> void:
	if not _ik:
		return
	var origin := _find_origin()
	if origin:
		var cameras := origin.find_children("*", "XRCamera3D", true, false)
		_ik.camera = cameras[0] as Node3D if cameras else null
		for node in origin.find_children("*", "CharacterBody3D", true, false):
			if node is XRToolsPlayerBody:
				_ik.ground = node as Node3D
		if origin.has_signal(&"seated_changed"):
			origin.connect(&"seated_changed", _on_seated_changed)
	for hand in get_tree().get_nodes_in_group(&"avatar_hands"):
		_ik.hand_targets[hand.get(&"side")] = hand.get(&"target")


## Sets one hand's finger curls (Index, Middle, Ring + Little, Thumb; 0 open, 1 grip).
func set_finger_curls(side: String, curls: Array[float]) -> void:
	if not _tree:
		return
	for i in FINGERS.size():
		_tree.set("parameters/%s%s/blend_amount" % [side, FINGERS[i]], curls[i])


func _on_seated_changed(seated: bool) -> void:
	_ik.seated = seated
	_ik.reset()
	if _springs:
		_springs.set_seated(seated)
		_springs.reset()


## Snaps the body's facing to the head (after a teleport or recenter).
func reset() -> void:
	if _ik:
		_ik.reset()
	if _springs:
		_springs.reset()


func _find_origin() -> Node3D:
	var node := get_parent()
	while node and not node is XROrigin3D:
		node = node.get_parent()
	return node as Node3D
