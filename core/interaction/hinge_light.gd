class_name HingeLight
extends Node
## Switches a light and an emissive material on while an
## [XRToolsInteractableHinge] is open (a fridge's interior light).
##
## The material is found by name on the meshes under [member emissive_root]
## (e.g. an imported glb) and duplicated per instance, so two fridges don't
## share one light. Only the emission energy changes, never
## [code]emission_enabled[/code], which would compile a new shader variant on
## first open.

@export var hinge: XRToolsInteractableHinge
@export var light: Light3D
@export var emissive_root: Node
@export var material_name := "FridgeLight"
@export var emission_energy := 2.0
## Open wider than this (from the closed limit) turns the light on.
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var on_angle := 3.0

var _materials: Array[BaseMaterial3D] = []
var _on := false


func _ready() -> void:
	if not hinge:
		push_error("HingeLight needs a hinge: %s" % get_path())
		return
	if emissive_root:
		_collect(emissive_root)
		if _materials.is_empty():
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
	for mat in _materials:
		mat.emission_energy_multiplier = emission_energy if on else 0.0


func _collect(node: Node) -> void:
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		for i in mesh_instance.mesh.get_surface_count():
			var mat := mesh_instance.get_active_material(i) as BaseMaterial3D
			if mat and mat.resource_name == material_name:
				var own := mat.duplicate() as BaseMaterial3D
				own.emission_enabled = true
				mesh_instance.set_surface_override_material(i, own)
				_materials.append(own)
	for child in node.get_children():
		_collect(child)
