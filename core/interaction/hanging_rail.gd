class_name HangingRail
extends Node3D
## A rail that clothes hangers ([RailHanger]) hook onto: the segment from
## [member start] to [member end] (local, on the rail's axis) with [member radius].

const GROUP := "hanging_rail"

@export var start := Vector3(-0.5, 0, 0)
@export var end := Vector3(0.5, 0, 0)
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var radius := 0.0125
## Keep hooks this far from the rail's ends (flanges, supports).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var end_margin := 0.03


func _ready() -> void:
	add_to_group(GROUP)


## World direction from start to end (unit length).
func direction() -> Vector3:
	return (to_global(end) - to_global(start)).normalized()


## Where a hook near `point` rests: on top of the rail, above the closest
## point of the axis (kept off the ends).
func rest_point(point: Vector3) -> Vector3:
	var a := to_global(start)
	var b := to_global(end)
	var ab := b - a
	var length := ab.length()
	var t := clampf((point - a).dot(ab) / (length * length), end_margin / length, 1.0 - end_margin / length)
	return a + ab * t + Vector3.UP * radius
