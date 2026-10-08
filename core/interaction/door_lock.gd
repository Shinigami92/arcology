class_name DoorLock
extends Node
## A deadbolt worked by a thumb-turn ([member turn], an
## [XRToolsInteractableHinge] from 0 = open to its max = locked, D-058).
## Locked, the door's hinge can't leave closed: grabbing its lever only
## rattles it. Like a smart lock with a door sensor, the turn only moves
## while the door is closed, so the bolt never sticks out of an open door.
## The status LED (a named emissive material, optional) shows cyan unlocked,
## red locked. When the turn's knob is part of the door's model (a bathroom
## door's privacy turn), [member turn_visual] turns with the hinge.

@export var door: XRToolsInteractableHinge
@export var turn: XRToolsInteractableHinge
## A node of the door's model that shows the turn (optional), turned about its
## local [member turn_visual_axis] by the turn's angle.
@export var turn_visual: Node3D
@export var turn_visual_axis := Vector3(0, 0, 1)
## Past this the bolt is thrown.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var lock_angle := 45.0
## Within this of closed the door counts as closed.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var closed_angle := 0.5
## Where the LED material is searched (the door leaf's model).
@export var led_root: Node
@export var led_material := "door_entrance_lock_led"
@export var unlocked_color := Color(0.02, 0.85, 0.91)
@export var locked_color := Color(1.0, 0.06, 0.04)
## Played when the bolt is thrown or drawn back (locked, unlocked).
@export var beep_locked: AudioStreamPlayer3D
@export var beep_unlocked: AudioStreamPlayer3D
## Played when the door is grabbed while locked.
@export var rattle: AudioStreamPlayer3D

var _locked := false
var _door_max := 0.0
var _turn_max := 0.0
var _leds: Array[BaseMaterial3D] = []
var _visual_rest := Basis.IDENTITY


func _ready() -> void:
	if not door or not turn:
		push_error("DoorLock needs door and turn: %s" % get_path())
		return
	_door_max = door.hinge_limit_max
	_turn_max = turn.hinge_limit_max
	if led_root:
		_collect_leds(led_root)
	_locked = turn.hinge_position > lock_angle
	if turn_visual:
		_visual_rest = turn_visual.basis
		_turn_visual(turn.hinge_position)
	turn.hinge_moved.connect(_on_turn_moved)
	door.hinge_moved.connect(_on_door_moved)
	door.grabbed.connect(_on_door_grabbed)
	_apply()


func is_locked() -> bool:
	return _locked


func _on_turn_moved(angle: float) -> void:
	_turn_visual(angle)
	var locked := angle > lock_angle
	if locked == _locked:
		return
	_locked = locked
	var beep := beep_locked if locked else beep_unlocked
	if beep:
		beep.play()
	_apply()


func _turn_visual(angle: float) -> void:
	if turn_visual:
		turn_visual.basis = _visual_rest * Basis(turn_visual_axis.normalized(), deg_to_rad(angle))


func _on_door_moved(_angle: float) -> void:
	_apply()


func _on_door_grabbed(_hinge: XRToolsInteractableHinge) -> void:
	if _locked and rattle:
		rattle.play()


func _apply() -> void:
	var closed := door.hinge_position - door.hinge_limit_min < closed_angle
	door.hinge_limit_max = door.hinge_limit_min if _locked else _door_max
	# The turn stays where it is while the door is open (unlocked, at 0).
	turn.hinge_limit_max = _turn_max if closed else maxf(turn.hinge_position, turn.hinge_limit_min)
	var c := locked_color if _locked else unlocked_color
	for led in _leds:
		led.emission = c
		led.albedo_color = c * 0.15


func _collect_leds(node: Node) -> void:
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		for i in mesh_instance.mesh.get_surface_count():
			var mat := mesh_instance.get_active_material(i) as BaseMaterial3D
			if mat and mat.resource_name == led_material:
				var own := mat.duplicate() as BaseMaterial3D
				own.emission_enabled = true
				mesh_instance.set_surface_override_material(i, own)
				_leds.append(own)
	for child in node.get_children():
		_collect_leds(child)
