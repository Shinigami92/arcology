class_name Foveation
extends Node
## Fixed (or eye-tracked) foveated rendering through variable rate shading:
## the middle of each eye renders at full rate, farther out 2x2, the corners
## 4x4. Only the shading rate drops: geometry, depth, MSAA edges and SSAO stay
## at full resolution (D-056).
##
## The headset's viewport switches to VRS_XR once XR runs: Godot builds the
## shading rate map from the OpenXR projection and centers it on the eye gaze
## where the runtime offers XR_EXT_eye_gaze_interaction (already enabled for
## AvatarEyes, D-050). Desktop perf runs get the same map as a texture
## (`desktop_texture()`), so the flythrough measures what the headset saves.

## Full rate inside this radius, in percent of half the eye's width (Godot's
## XRVRS: 1..100). Shading drops to 2x2 at about min + 45 % of the rest of the
## way to the edge, to 4x4 near the edge.
const MIN_RADIUS := 35.0
## How fast the rate drops past MIN_RADIUS (XRVRS: 0.1..10; 1 = linear to the edge).
const STRENGTH := 1.0
## Eye gaze tracker (AvatarEyes.GAZE_TRACKER): present while the runtime tracks the eyes.
const GAZE_TRACKER := &"/user/eyes_ext"
const GROUP := &"foveation"

var enabled := true
var min_radius := MIN_RADIUS
var strength := STRENGTH


func _ready() -> void:
	add_to_group(GROUP)
	if not enabled:
		print("Foveation: off")
	var start_xr := XRToolsStartXR.get_start_xr_node()
	if start_xr:
		start_xr.xr_started.connect(_on_xr_started)
	if get_viewport().use_xr:
		_on_xr_started()


## The scene's Foveation (main.gd creates one), or null.
static func find(tree: SceneTree) -> Foveation:
	return tree.get_first_node_in_group(GROUP) as Foveation


## Turns foveation on or off or changes its shape at runtime (ABViewport).
func set_foveation(on: bool, radius: float, rate_strength: float) -> void:
	enabled = on
	min_radius = clampf(radius, 1.0, 100.0)
	strength = clampf(rate_strength, 0.1, 10.0)
	if get_viewport().use_xr:
		_on_xr_started()


## `--foveation=off`, or `<min_radius>[,<strength>]` to try other values.
func configure(arg: String) -> void:
	if arg == "off":
		enabled = false
		return
	var parts := arg.split(",", false)
	if parts.size() > 0 and parts[0].is_valid_float():
		min_radius = clampf(parts[0].to_float(), 1.0, 100.0)
	if parts.size() > 1 and parts[1].is_valid_float():
		strength = clampf(parts[1].to_float(), 0.1, 10.0)


func _on_xr_started() -> void:
	var xr := XRServer.find_interface("OpenXR") as OpenXRInterface
	if not xr:
		return
	var viewport := get_viewport()
	if not enabled:
		viewport.vrs_mode = Viewport.VRS_DISABLED
		print("Foveation: off")
		return
	viewport.vrs_mode = Viewport.VRS_XR
	# Godot's default copies the map into the render buffers once; XR's buffers
	# come after the first desktop frames, and a never-filled map renders black
	# on NVIDIA (godotengine/godot#119523). Always also follows the eye gaze.
	viewport.vrs_update_mode = Viewport.VRS_UPDATE_ALWAYS
	xr.vrs_min_radius = min_radius
	xr.vrs_strength = strength
	print("Foveation: VRS min_radius=%.0f strength=%.1f target=%s" % [min_radius, strength, xr.get_render_target_size()])
	# The gaze tracker shows up with the first valid gaze pose.
	get_tree().create_timer(5.0).timeout.connect(func() -> void:
		print("Foveation: eye-tracked=%s" % (XRServer.get_tracker(GAZE_TRACKER) != null)))


## The shading rate map Godot's XRVRS builds for `views` eyes of `eye_size`
## pixels, looking straight ahead, laid side by side: for a desktop SubViewport
## that renders the eyes next to each other (the perf flythrough).
func desktop_texture(eye_size: Vector2i, views: int) -> ImageTexture:
	# One texel per 16x16 tile (NVIDIA's shading rate tile); the conversion
	# samples by UV, so only the tile count matters.
	var tiles := Vector2i(roundi(eye_size.x / 16.0), roundi(eye_size.y / 16.0))
	var max_radius := 0.5 * mini(tiles.x, tiles.y)
	var inner := min_radius * max_radius / 100.0
	var outer := maxf(1.0, (max_radius - inner) / strength)
	var center := Vector2(tiles) * 0.5
	var data := PackedByteArray()
	data.resize(tiles.x * views * tiles.y * 2)
	var i := 0
	for y in tiles.y:
		for v in views:
			for x in tiles.x:
				var density := maxf(Vector2(x, y).distance_to(center) - inner, 0.0) / outer
				var value := clampi(int(255.0 * density), 0, 255)
				data[i] = value
				data[i + 1] = value
				i += 2
	return ImageTexture.create_from_image(Image.create_from_data(tiles.x * views, tiles.y, false, Image.FORMAT_RG8, data))
