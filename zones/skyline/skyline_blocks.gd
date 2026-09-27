@tool
class_name SkylineBlocks
extends MultiMeshInstance3D
## Procedural far-city skyline: box towers around the arcology, one draw call.
##
## Deterministic (fixed seed) so the view from the window is the same every
## run. Towers stand on the street plane and rise past the apartment. Cells
## inside [member keep_out] (our own building) stay empty. The generated
## MultiMesh is never saved into the scene; it is rebuilt on load. Set the
## material via material_override.

@export var seed_value := 92
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var cell_size := 70.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var inner_radius := 110.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var outer_radius := 1400.0
## World Y of the street (docs/decisions.md D-008).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var street_y := -180.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var min_height := 60.0
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var max_height := 520.0
## Area (x/z, in world meters) kept free for the apartment's own building.
@export var keep_out := Rect2(-60.0, -25.0, 120.0, 200.0)
@export_tool_button("Regenerate") var regenerate_action := generate


func _ready() -> void:
	generate()


func _validate_property(property: Dictionary) -> void:
	if property.name == "multimesh":
		property.usage &= ~PROPERTY_USAGE_STORAGE


func generate() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var transforms: Array[Transform3D] = []
	var seeds: PackedFloat32Array = []

	var n := int(ceil(outer_radius / cell_size))
	for ix in range(-n, n + 1):
		for iz in range(-n, n + 1):
			var center := Vector2(ix, iz) * cell_size
			center += Vector2(rng.randf_range(-0.25, 0.25), rng.randf_range(-0.25, 0.25)) * cell_size
			var dist := center.length()
			if dist < inner_radius or dist > outer_radius or keep_out.has_point(center):
				continue
			# Thin out the far ring a little; the fog hides it anyway.
			if rng.randf() < clampf((dist - 600.0) / 1600.0, 0.0, 0.5):
				continue
			var width := rng.randf_range(0.35, 0.8) * cell_size
			var depth := rng.randf_range(0.35, 0.8) * cell_size
			var height := lerpf(min_height, max_height, pow(rng.randf(), 2.2))
			var shape := Basis(Vector3.UP, rng.randf_range(-0.08, 0.08)) * Basis.from_scale(Vector3(width, height, depth))
			transforms.append(Transform3D(shape, Vector3(center.x, street_y + height * 0.5, center.y)))
			seeds.append(rng.randf())

	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = BoxMesh.new()
	mm.instance_count = transforms.size()
	for i in transforms.size():
		mm.set_instance_transform(i, transforms[i])
		mm.set_instance_custom_data(i, Color(seeds[i], 0.0, 0.0, 0.0))
	multimesh = mm
