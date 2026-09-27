class_name TrashReceiver
extends Area3D
## Accepts rigid bodies tagged with [member accept_tag] (a node group) that
## come to rest inside this area, e.g. the opening of a trash can.
##
## A tagged body is consumed once it has stayed inside for
## [member consume_delay] seconds without being held. Untagged bodies are
## ignored and simply lie in the container.

signal accepted(body: RigidBody3D)

## Group name that marks a body as acceptable (see CLAUDE.md "Tags").
@export var accept_tag: StringName = &"trash"
## Seconds a tagged body must stay inside, not held, before it's consumed.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var consume_delay := 0.6
## Optional sound played when something is accepted.
@export var accept_sound: AudioStreamPlayer3D

# Body -> seconds spent inside, not held
var _inside: Dictionary[RigidBody3D, float] = {}


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	set_physics_process(false)


func _physics_process(delta: float) -> void:
	for body: RigidBody3D in _inside.keys():
		if not is_instance_valid(body):
			_inside.erase(body)
			continue
		if body is XRToolsPickable and (body as XRToolsPickable).is_picked_up():
			_inside[body] = 0.0
			continue
		_inside[body] += delta
		if _inside[body] >= consume_delay:
			_accept(body)
	set_physics_process(not _inside.is_empty())


func _accept(body: RigidBody3D) -> void:
	_inside.erase(body)
	if accept_sound:
		accept_sound.play()
	accepted.emit(body)
	body.queue_free()


func _on_body_entered(body: Node3D) -> void:
	if body is RigidBody3D and body.is_in_group(accept_tag):
		_inside[body as RigidBody3D] = 0.0
		set_physics_process(true)


func _on_body_exited(body: Node3D) -> void:
	if body is RigidBody3D:
		_inside.erase(body as RigidBody3D)
