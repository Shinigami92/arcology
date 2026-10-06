class_name ABSwitch
extends Node3D
## Holds two variants of an asset as children "A" and "B" in the same spot and
## shows one at a time, for blind comparisons in the headset (see ABPanel).
## The hidden variant is also disabled, so its collision leaves the world.
## Subclasses compare something else by overriding [method _apply_variant]
## (e.g. [ABEnvironment]).

const GROUP := "ab_switch"

@export_enum("A", "B") var variant := "A":
	set = set_variant


func _ready() -> void:
	add_to_group(GROUP)
	set_variant(variant)


func set_variant(value: String) -> void:
	variant = value
	if is_inside_tree():
		_apply_variant()


func _apply_variant() -> void:
	for name in ["A", "B"]:
		var child := get_node_or_null(name) as Node3D
		if child:
			var active: bool = name == variant
			child.visible = active
			child.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED


## Flips every switch in the tree; returns the variant now shown.
static func toggle_all(tree: SceneTree) -> String:
	var shown := "A"
	for node in tree.get_nodes_in_group(GROUP):
		var sw := node as ABSwitch
		sw.set_variant("B" if sw.variant == "A" else "A")
		shown = sw.variant
	return shown
