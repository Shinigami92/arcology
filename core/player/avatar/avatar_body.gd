class_name AvatarBody
extends Node3D
## Root of the avatar's body scene (D-041), a child of the player's XROrigin3D.
## Connects BodyIK to the headset, the floor (XR Tools' PlayerBody, which
## stands on the ground under the camera; the origin is raised by the seated
## height calibration) and the AvatarHand targets, receives the finger curls
## from the hands, and puts the meshes in [member third_person_meshes] on the
## Third Person render layer, which the player's camera skips and reflections
## show (D-049): the head, and the collar, which crowds the view when looking
## down. They still cast shadows. The other meshes (what the player sees of
## themself: arms, hands, coat, legs) draw after SSAO (D-055), see
## [method _draw_after_ssao].
##
## Scene (written by tools/player/avatar.gd): AvatarBody -> Model (the glb) with
## BodyIK, AvatarEyes (gaze and lids, D-050), the AvatarSprings (coat, belt
## items) and the Fingertip press areas on the skeleton, and an AnimationTree blending "Open" to "Grip" per finger group
## and side (parameters <Side><Finger>/blend_amount).

const FINGERS: Array[StringName] = [&"Index", &"Middle", &"Ring", &"Thumb"]

## Meshes (node names under the skeleton) hidden from the player's own camera.
@export var third_person_meshes: PackedStringArray = ["HeadMesh", "Collar"]
## Draw the player's own meshes after SSAO, so the hands don't ring the wall
## behind them with ambient occlusion halos (D-055).
@export var draw_after_ssao := true
## The lashes' and brows' material among them, and its alpha cutoff.
@export var lash_material := "SilenaLashes"
@export var lash_alpha_threshold := 0.3

var _tree: AnimationTree
var _ik: BodyIK
var _springs: AvatarSprings
var _eyes: AvatarEyes


func _ready() -> void:
	add_to_group(&"avatar_body")
	_tree = get_node_or_null("AnimationTree") as AnimationTree
	var found := find_children("*", "BodyIK", true, false)
	_ik = found[0] as BodyIK if found else null
	found = find_children("*", "AvatarSprings", true, false)
	_springs = found[0] as AvatarSprings if found else null
	found = find_children("*", "AvatarEyes", true, false)
	_eyes = found[0] as AvatarEyes if found else null
	for mesh_name in third_person_meshes:
		for node in find_children(mesh_name, "MeshInstance3D", true, false):
			(node as MeshInstance3D).layers = PlanarReflection.LAYER_THIRD_PERSON
			_soften_cards(node as MeshInstance3D)
	if draw_after_ssao:
		for node in find_children("*", "MeshInstance3D", true, false):
			if not (node.name as String) in third_person_meshes:
				_draw_after_ssao(node as MeshInstance3D)
	_connect.call_deferred()


## SSAO reads the depth prepass, which holds only opaque geometry: the player's
## hands, always close to the eyes, darkened the wall half a meter behind them
## in a ring. The visible mesh draws in the transparent pass (after SSAO) with
## depth writes and stays solid (its textures carry no alpha), but transparent
## materials cast no shadows: a shadow-only copy with the opaque materials casts
## them (shadow-only meshes stay out of the depth prepass too). The body just
## gets no SSAO of its own and doesn't occlude the room's.
func _draw_after_ssao(mesh: MeshInstance3D) -> void:
	var shadow := mesh.duplicate() as MeshInstance3D
	shadow.name = mesh.name + "Shadow"
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	mesh.add_sibling(shadow)
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for i in mesh.mesh.get_surface_count():
		var mat := mesh.get_active_material(i) as BaseMaterial3D
		if mat:
			mat = mat.duplicate() as BaseMaterial3D
			mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			mat.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_ALWAYS
			mesh.set_surface_override_material(i, mat)


## Lashes and brows are alpha-scissor cards: thin strands lose their coverage
## in the smaller mipmaps and break up into dots. Alpha to coverage (the mirror
## renders with MSAA) keeps them as soft strands (D-050).
func _soften_cards(mesh: MeshInstance3D) -> void:
	for i in mesh.get_surface_override_material_count():
		var mat := mesh.mesh.surface_get_material(i) as BaseMaterial3D
		if mat and mat.resource_name == lash_material:
			mat.alpha_antialiasing_mode = BaseMaterial3D.ALPHA_ANTIALIASING_ALPHA_TO_COVERAGE_AND_TO_ONE
			mat.alpha_antialiasing_edge = 0.3
			mat.alpha_scissor_threshold = lash_alpha_threshold


## Finds the headset, the origin and the hand targets (they may be ready after us).
func _connect() -> void:
	if not _ik:
		return
	var origin := _find_origin()
	if origin:
		var cameras := origin.find_children("*", "XRCamera3D", true, false)
		_ik.camera = cameras[0] as Node3D if cameras else null
		if _eyes:
			_eyes.camera = _ik.camera
			_eyes.origin = origin
		for cam: Camera3D in cameras:
			cam.cull_mask &= ~PlanarReflection.LAYER_THIRD_PERSON
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
