class_name KinematicFollower
extends AnimatableBody3D
## An AnimatableBody3D that follows [member follow] (e.g. a hinge's leaf node)
## by setting its own transform every physics frame.
##
## An AnimatableBody3D moved only by its parents (a hinge rotating above it)
## keeps its old physics transform: the door looks open, but its collision
## stays shut. Moving the body itself is what AnimatableBody3D expects; it
## then moves kinematically and pushes rigid bodies out of the way.
## The body is made top_level, so author it at identity under [member follow].

@export var follow: Node3D


func _ready() -> void:
	if not follow:
		follow = get_parent() as Node3D
	top_level = true
	global_transform = follow.global_transform


func _physics_process(_delta: float) -> void:
	var target := follow.global_transform
	if not global_transform.is_equal_approx(target):
		global_transform = target
