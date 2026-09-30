extends Node
## Measures skyline shimmer: the share of city pixels whose luminance changes
## by more than 0.1 when the view turns by half a pixel (what small head
## movements do in VR). Lower is steadier. Started by main.gd:
##
##   "$GODOT4_EDITOR" --path . --xr-mode off -- --test=skyline
##
## Prints "SHIMMER <variant>: <percent>" and fails if the default view is
## above [constant MAX_SHIMMER_PCT] (docs/decisions.md D-020).

const MAX_SHIMMER_PCT := 7.0
const TRIALS := 4

var _main: Node3D


func _ready() -> void:
	_main = get_parent() as Node3D
	var player: XROrigin3D = _main.get_node("Player")
	player.get_node("PlayerBody").enabled = false
	player.global_transform = Transform3D.IDENTITY
	await get_tree().create_timer(1.0).timeout

	var panes := _main.get_node("Zones/Apartment/Windows/LivingWindow").find_children("Glass*", "MeshInstance3D", true, false)
	var default_pct := await _shimmer()
	print("SHIMMER through_glass: %.2f %%" % default_pct)
	for pane: Node3D in panes:
		pane.visible = false
	print("SHIMMER without_glass: %.2f %%" % await _shimmer())
	for pane: Node3D in panes:
		pane.visible = true
	var env: Environment = _main.get_node("Skyline/WorldEnvironment").environment
	env.glow_enabled = false
	print("SHIMMER without_glow: %.2f %%" % await _shimmer())
	env.glow_enabled = true

	var ok := default_pct <= MAX_SHIMMER_PCT
	print("TEST %s skyline_shimmer: %.2f %% (max %.1f %%)" % ["PASS" if ok else "FAIL", default_pct, MAX_SHIMMER_PCT])
	get_tree().quit(0 if ok else 1)


func _shimmer() -> float:
	var camera: Camera3D = _main.get_node("Player/XRCamera3D")
	var viewport := camera.get_viewport()
	var half_px := deg_to_rad(camera.fov / viewport.get_visible_rect().size.x) * 0.5
	var total := 0.0
	for trial in TRIALS:
		var yaw := trial * 0.013
		camera.transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(0.0, 1.7, -2.0))
		var a := await _capture(viewport)
		camera.transform = Transform3D(Basis(Vector3.UP, yaw + half_px), Vector3(0.0, 1.7, -2.0))
		var b := await _capture(viewport)
		total += _changed_pct(a, b)
	return total / TRIALS


func _capture(viewport: Viewport) -> Image:
	for i in 3:
		await RenderingServer.frame_post_draw
	return viewport.get_texture().get_image()


## City only: two regions left and right of the window mullion.
static func _changed_pct(a: Image, b: Image) -> float:
	var w := a.get_width()
	var h := a.get_height()
	var changed := 0
	var n := 0
	for y in range(int(h * 0.35), int(h * 0.7), 2):
		for range_x: Array in [[0.18, 0.42], [0.58, 0.82]]:
			for x in range(int(w * range_x[0]), int(w * range_x[1]), 2):
				n += 1
				if absf(a.get_pixel(x, y).get_luminance() - b.get_pixel(x, y).get_luminance()) > 0.1:
					changed += 1
	return 100.0 * changed / maxi(n, 1)
