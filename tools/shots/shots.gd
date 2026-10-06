extends Node
## Renders still images of the running world from given views and quits.
## For visual checks of assets and zones without the headset or editor.
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --shots="4.6,1.6,-0.6,-60,-10;4.4,1.5,0.2,120,-8" --shot-hinge=Fridge:80
##
## Each view is x,y,z,yaw,pitch[,fov] (degrees; yaw 0 looks along -Z, 90
## along -X). --shot-hinge opens hinged props (Props/<path>:<degrees>, e.g.
## Fridge:80 or Wardrobe/A/DoorLeft:80, or a zone path such as
## Windows/BedroomWindow/Vent:10) and --shot-ab=B shows the B variant of
## every ABSwitch first. --shot-call=<zone path>:<method>:<number>[,...] calls
## a method first, e.g. Windows/LivingWindow/Shade:set_closure:0.6 or
## Windows/LivingWindow/SmartGlass:set_tint:0.9. --shot-player=x,z,yaw stands the
## player there first (their eyes at x, 1.8 m, z) (e.g. in front of a mirror, D-049); a view written
## eye,dx,dy,dz,yaw,pitch[,fov] is relative to the player's camera (offset in
## its frame, angles added to its own): "eye,0,0,0,0,0,12" zooms in on what the
## player sees, such as their face in a mirror (their own head hidden while the
## camera is within 25 cm of the eyes), "eye,0,0,-0.5,180,0,30" looks back at
## their face (D-050). Writes
## tools/shots/results/shot-<n>.png (gitignored) at [constant SIZE] and quits.
## --shot-foveation renders with the headset's shading rate map (one eye, D-056).

const SIZE := Vector2i(1920, 1080)
const OUT_DIR := "res://tools/shots/results"
## Frames to render before capturing (reflection probes and lights settle).
const SETTLE_FRAMES := 30
## The player's eye height with --shot-player (XR Tools' standard_height, what the
## headset is calibrated to).
const STANDING_EYE := 1.8

var zone: Node3D
var views: PackedStringArray = []
var hinges: PackedStringArray = []
var ab := ""
var calls: PackedStringArray = []
## "x,z,yaw" to stand the player at (the avatar shows in mirrors), or "".
var player_at := ""
var player: Node3D
## Foveation to render with (--shot-foveation), or null.
var foveation: Foveation


func _ready() -> void:
	var sub := SubViewport.new()
	sub.size = SIZE
	sub.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	sub.msaa_3d = Viewport.MSAA_4X
	sub.use_occlusion_culling = get_viewport().use_occlusion_culling
	if foveation and foveation.enabled:
		sub.vrs_mode = Viewport.VRS_TEXTURE
		sub.vrs_texture = foveation.desktop_texture(SIZE, 1)
	sub.world_3d = get_viewport().world_3d
	var cam := Camera3D.new()
	cam.near = 0.03
	cam.far = 3000.0
	sub.add_child(cam)
	add_child(sub)
	cam.current = true
	get_viewport().disable_3d = true
	PlanarReflection.view_camera = cam

	if player_at and player:
		var p := player_at.split_floats(",")
		var body := player.get_node_or_null("PlayerBody")
		if body and p.size() >= 2:
			var yaw := deg_to_rad(p[2]) if p.size() > 2 else 0.0
			var target := Vector3(p[0], 0.0, p[1])
			body.call("teleport", Transform3D(Basis(Vector3.UP, yaw), target))
			# The eyes at the spot, at the calibrated headset's standing height
			# (the desktop camera sits off the body's center).
			var cams := player.find_children("*", "XRCamera3D", true, false)
			if cams:
				var eyes := cams[0] as Node3D
				eyes.position.y = STANDING_EYE
				for f in 3:
					await get_tree().physics_frame
				var off := eyes.global_position - target
				body.call("teleport", Transform3D(Basis(Vector3.UP, yaw), target - Vector3(off.x, 0.0, off.z)))
				for f in 60:   # the body settles (eye height, body facing)
					await get_tree().physics_frame
		else:
			push_warning("SHOTS: can't place the player at %s" % player_at)

	if ab == "B":
		ABSwitch.toggle_all(get_tree())
	for spec in hinges:
		var parts := spec.split(":")
		var hinge := zone.get_node_or_null("Props/%s/HingeOrigin/InteractableHinge" % parts[0]) as XRToolsInteractableHinge
		if not hinge:
			hinge = zone.get_node_or_null("%s/HingeOrigin/InteractableHinge" % parts[0]) as XRToolsInteractableHinge
		if hinge:
			hinge.hinge_position = float(parts[1])
			hinge.hinge_moved.emit(hinge.hinge_position)
		else:
			push_warning("SHOTS: no hinge on Props/%s" % parts[0])

	for spec in calls:
		var parts := spec.split(":")
		var target := zone.get_node_or_null(parts[0])
		if target and parts.size() == 3 and target.has_method(parts[1]):
			target.call(parts[1], float(parts[2]))
		else:
			push_warning("SHOTS: can't call %s" % spec)

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	for i in views.size():
		var relative := views[i].begins_with("eye,")
		var v := views[i].trim_prefix("eye,").split_floats(",")
		cam.position = Vector3(v[0], v[1], v[2])
		cam.rotation_degrees = Vector3(v[4], v[3], 0)
		cam.fov = v[5] if v.size() > 5 else 70.0
		# From (near) the player's eyes, skip their own head as their camera does.
		var inside := relative and cam.position.length() < 0.25
		cam.cull_mask = PlanarReflection.ALL_LAYERS & ~PlanarReflection.LAYER_THIRD_PERSON if inside else PlanarReflection.ALL_LAYERS
		if relative or (player_at and i == 0):
			var cams := player.find_children("*", "XRCamera3D", true, false) if player else []
			if cams:
				print("SHOTS: player eyes at ", (cams[0] as Node3D).global_position)
		if relative:
			var eyes := player.find_children("*", "XRCamera3D", true, false) if player else []
			if eyes:
				var view := (eyes[0] as Node3D).global_transform
				cam.global_transform = Transform3D(view.basis * cam.basis, view * cam.position)
			else:
				push_warning("SHOTS: no player camera for %s" % views[i])
		for f in SETTLE_FRAMES:
			await RenderingServer.frame_post_draw
		var path := "%s/shot-%d.png" % [OUT_DIR, i]
		sub.get_texture().get_image().save_png(path)
		print("SHOTS: wrote ", ProjectSettings.globalize_path(path))
	get_tree().quit()
