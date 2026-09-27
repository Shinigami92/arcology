class_name Seat
extends Area3D
## A place the player can sit down (sofa, bed edge, chair).
##
## The area marks where the player must stand to sit (collision_mask = Player
## Body). While the player is inside, a prompt shows and the player's
## interact button sits them down: the view moves to [member sit_point] (eye
## position, -Z = facing) and walking is disabled. Interact again, or push the
## move stick, to get up at [member stand_point] (floor position, -Z = facing).
## See ArcologyPlayer.sit()/stand().

## Eye position and facing while seated.
@export var sit_point: Marker3D
## Floor position and facing after getting up.
@export var stand_point: Marker3D
## Optional prompt shown while the player can sit here.
@export var prompt: Node3D

var occupied := false

var _player_in_range := false


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	if prompt:
		prompt.visible = false


func set_occupied(value: bool) -> void:
	occupied = value
	_update_prompt()


func _player_of(body: Node3D) -> ArcologyPlayer:
	if body is XRToolsPlayerBody:
		return body.get_parent() as ArcologyPlayer
	return null


func _on_body_entered(body: Node3D) -> void:
	var player := _player_of(body)
	if player:
		player.register_seat(self, true)
		_player_in_range = true
		_update_prompt()


func _on_body_exited(body: Node3D) -> void:
	var player := _player_of(body)
	if player:
		player.register_seat(self, false)
		_player_in_range = false
		_update_prompt()


func _update_prompt() -> void:
	if prompt:
		prompt.visible = _player_in_range and not occupied
