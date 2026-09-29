extends Node
## Renders still images of the running world from given views and quits.
## For visual checks of assets and zones without the headset or editor.
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --shots="4.6,1.6,-0.6,-60,-10;4.4,1.5,0.2,120,-8" --shot-hinge=Fridge:80
##
## Each view is x,y,z,yaw,pitch[,fov] (degrees; yaw 0 looks along -Z, 90
## along -X). --shot-hinge opens hinged props (Props/<path>:<degrees>, e.g.
## Fridge:80 or Wardrobe/A/DoorLeft:80) and --shot-ab=B shows the B variant of
## every ABSwitch first. Writes tools/shots/results/shot-<n>.png (gitignored) at
## [constant SIZE] and quits.

const SIZE := Vector2i(1920, 1080)
const OUT_DIR := "res://tools/shots/results"
## Frames to render before capturing (reflection probes and lights settle).
const SETTLE_FRAMES := 30

var zone: Node3D
var views: PackedStringArray = []
var hinges: PackedStringArray = []
var ab := ""


func _ready() -> void:
	var sub := SubViewport.new()
	sub.size = SIZE
	sub.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	sub.msaa_3d = Viewport.MSAA_4X
	sub.world_3d = get_viewport().world_3d
	var cam := Camera3D.new()
	cam.near = 0.03
	cam.far = 3000.0
	sub.add_child(cam)
	add_child(sub)
	cam.current = true
	get_viewport().disable_3d = true

	if ab == "B":
		ABSwitch.toggle_all(get_tree())
	for spec in hinges:
		var parts := spec.split(":")
		var hinge := zone.get_node_or_null("Props/%s/HingeOrigin/InteractableHinge" % parts[0]) as XRToolsInteractableHinge
		if hinge:
			hinge.hinge_position = float(parts[1])
			hinge.hinge_moved.emit(hinge.hinge_position)
		else:
			push_warning("SHOTS: no hinge on Props/%s" % parts[0])

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	for i in views.size():
		var v := views[i].split_floats(",")
		cam.position = Vector3(v[0], v[1], v[2])
		cam.rotation_degrees = Vector3(v[4], v[3], 0)
		cam.fov = v[5] if v.size() > 5 else 70.0
		for f in SETTLE_FRAMES:
			await RenderingServer.frame_post_draw
		var path := "%s/shot-%d.png" % [OUT_DIR, i]
		sub.get_texture().get_image().save_png(path)
		print("SHOTS: wrote ", ProjectSettings.globalize_path(path))
	get_tree().quit()
