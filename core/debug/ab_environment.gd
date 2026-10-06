class_name ABEnvironment
extends ABSwitch
## An A/B switch for the world's Environment instead of two child scenes: each
## variant is a set of Environment properties (e.g. SSAO on or off), applied to
## the environment of this node's World3D. Flipped by the ABPanel with every
## other switch.

## Environment property -> value while A is shown.
@export var a: Dictionary = {}
## Environment property -> value while B is shown.
@export var b: Dictionary = {}


func _apply_variant() -> void:
	var env := get_world_3d().environment
	if not env:
		push_warning("ABEnvironment %s: no environment in this world" % name)
		return
	var values: Dictionary = a if variant == "A" else b
	for property: String in values:
		env.set(property, values[property])
