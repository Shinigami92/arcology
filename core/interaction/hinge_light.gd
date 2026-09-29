class_name HingeLight
extends Node
## Switches a light and an emissive material on while an
## [XRToolsInteractableHinge] is open (a fridge's interior light).
## See [EmissiveMaterials] for how the material is found and switched.

@export var hinge: XRToolsInteractableHinge
@export var light: Light3D
@export var emissive_root: Node
@export var material_name := "FridgeLight"
@export var emission_energy := 2.0
## Open wider than this (from the closed limit) turns the light on.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var on_angle := 3.0

var _materials: EmissiveMaterials
var _on := false


func _ready() -> void:
	if not hinge:
		push_error("HingeLight needs a hinge: %s" % get_path())
		return
	_materials = EmissiveMaterials.new(emissive_root, material_name, emission_energy)
	if emissive_root and _materials.is_empty():
		push_warning("HingeLight: no material named '%s' under %s" % [material_name, emissive_root.get_path()])
	hinge.hinge_moved.connect(_on_hinge_moved)
	_set_on(absf(hinge.hinge_position - hinge.hinge_limit_min) > on_angle, true)


func _on_hinge_moved(angle: float) -> void:
	_set_on(absf(angle - hinge.hinge_limit_min) > on_angle)


func _set_on(on: bool, force := false) -> void:
	if on == _on and not force:
		return
	_on = on
	if light:
		light.visible = on
	_materials.set_on(on)
