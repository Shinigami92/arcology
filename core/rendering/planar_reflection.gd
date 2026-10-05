class_name PlanarReflection
extends Node3D
## Live reflection for a flat surface (a mirror, window glass, a glass screen),
## rendered per eye (D-049). This node is the surface's rectangle: origin at its
## center, local X right, Y up, +Z the reflecting side, [member size] meters.
##
## For each eye a SubViewport renders the scene from the eye mirrored at the
## plane, through an off-axis frustum that ends exactly at the rectangle: the
## near plane is the surface, so nothing behind it is drawn, and the texture
## maps 1:1 onto the rectangle. [member materials] (shaders including
## planar_reflection.gdshaderinc) get both textures and the rectangle.
##
## Surfaces in one plane (the apartment's windows) share one renderer: its
## frustum covers the visible ones together, so a whole facade costs two scene
## passes. A plane renders while one of its surfaces faces the viewer, lies
## within [constant VIEW_CONE] of where they look and can be seen: a ray from the
## head to one of 3x3 points on it hits nothing in [constant SIGHT_MASK] (walls,
## closed doors, furniture) short of it. Not a VisibleOnScreenNotifier3D: the
## reflection cameras count for those too, so reflections that see each other
## would keep each other rendering. At most [member max_active] planes at once,
## the largest on screen first. Starting and stopping fades over [constant FADE_TIME], to and from the
## ReflectionProbe the materials fall back to (reflection_enabled 0).
##
## The cameras are placed on the RenderingServer right before drawing: a node
## transform set then would only reach the renderer a frame later, while the
## frustum (near plane on the surface) applies at once, and while the viewer
## moves the two would disagree (the wall behind the mirror showing through).
##
## Render layers: reflective surfaces and in-world HUD sit on
## [constant LAYER_UNREFLECTED], which reflection cameras skip (no surface sees
## its own texture, prompts don't show mirrored); the player's head sits on
## [constant LAYER_THIRD_PERSON], which only reflections show.

## Render layer 11 "Third Person": seen in reflections, hidden from the player's camera.
const LAYER_THIRD_PERSON := 1 << 10
## Render layer 12 "Unreflected": never drawn in reflections.
const LAYER_UNREFLECTED := 1 << 11
const ALL_LAYERS := (1 << 20) - 1
## Eye offset for [member simulate_stereo] (m).
const DESKTOP_IPD := 0.064
## Seconds a reflection takes to fade in or out.
const FADE_TIME := 0.2
## Surfaces closer than this to one plane (m, and in angle) share its renderer.
const COPLANAR_DISTANCE := 0.01
const COPLANAR_DOT := 0.9999
## Half-angle of the view cone (degrees): generous, so rendering starts before
## the surface turns into view (the Steam Frame shows about 55 degrees each side).
const VIEW_CONE := 75.0
## Physics layers that block the view of a surface: Static World (walls,
## furniture, doors).
const SIGHT_MASK := 1
## A ray that hits this close to its target hit the surface itself (its glass's
## collision box), not something in front of it (m).
const SIGHT_SLACK := 0.06
## Eyes closer to the plane than this (m) render from this distance: an eye on
## or behind the surface (leaning in, one eye past a glass edge) would collapse
## the frustum.
const MIN_EYE_DISTANCE := 0.01
## Environment properties [method sync_environment] copies.
const SYNCED_ENVIRONMENT: Array[StringName] = [&"ambient_light_color", &"ambient_light_energy",
		&"ambient_light_sky_contribution", &"fog_light_color", &"fog_light_energy", &"fog_density"]

## The camera that renders when not in XR. Tools that render through their own
## SubViewport (perf flythrough, stills) set it; otherwise the viewport's camera.
static var view_camera: Camera3D
## Render the second eye outside XR too (offset by [constant DESKTOP_IPD]), so a
## desktop perf run costs what the headset does. Set by the perf flythrough.
static var simulate_stereo := false
## Planes rendering at the same time (two scene passes each), largest on screen first.
static var max_active := 3
static var _instances: Array[PlanarReflection] = []
## One environment for every reflection camera (see _reflection_environment).
static var _reflection_env: Environment
static var _frame := -1
static var _last_usec := 0

## Rectangle size (m): local X, Y.
@export var size := Vector2(1.0, 1.0)
## Materials fed with the textures and the rectangle (planar_reflection.gdshaderinc).
@export var materials: Array[ShaderMaterial] = []
## Texture resolution per meter of the rectangle, capped at [member max_resolution].
@export var pixels_per_meter := 900.0
@export var max_resolution := 2048
## Layers the reflection shows.
@export_flags_3d_render var cull_mask := ALL_LAYERS & ~LAYER_UNREFLECTED
## Shadows in the reflection (a shadow atlas per eye; off is cheaper).
@export var shadows := false
## Multisampling in the reflection (a faint one, like window glass, needs none).
@export var msaa := true
## How far the reflection reaches beyond the surface (m): the far plane. Cuts
## what lies behind the room's back walls, nearly for free (occlusion culling
## in the reflection costs more CPU than it saves, D-049).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var reach := 7.0
## Both faces reflect (a glass screen seen from either side).
@export var two_sided := false
## Magnifying mirror: shows the middle 1/magnification of the plain reflection,
## enlarged (a concave cosmetic mirror, roughly). Never shares a renderer.
@export_range(1.0, 10.0) var magnification := 1.0
# This surface's renderer, created the first time it leads a plane.
var _viewports: Array[SubViewport] = []
var _cameras: Array[Camera3D] = []
var _rendering := false
var _fade := 0.0
var _live := false
var _score := 0.0
var _plane := Transform3D()   # orthonormal, +Z toward the viewer


func _ready() -> void:
	for mat in materials:
		mat.set_shader_parameter(&"reflection_enabled", 0.0)
	_instances.append(self)
	RenderingServer.frame_pre_draw.connect(_on_pre_draw)


func _exit_tree() -> void:
	_instances.erase(self)
	if RenderingServer.frame_pre_draw.is_connected(_on_pre_draw):
		RenderingServer.frame_pre_draw.disconnect(_on_pre_draw)


## True while this surface shows its live reflection (selected this frame).
func is_active() -> bool:
	return _live


## True while this surface's renderer draws (it leads a plane being shown).
func is_rendering() -> bool:
	return _rendering


## Surfaces showing their live reflection (last drawn frame).
static func live_surfaces() -> Array[PlanarReflection]:
	var out: Array[PlanarReflection] = []
	for r in _instances:
		if r._live:
			out.append(r)
	return out


## The surface's plane as of the last drawn frame: origin at its center, +Z
## toward the viewer (a two-sided surface turned to the side they're on).
func plane() -> Transform3D:
	return _plane


## The SubViewports drawing this frame (perf tools add up their render time).
static func rendering_viewports() -> Array[SubViewport]:
	var out: Array[SubViewport] = []
	for r in _instances:
		for vp in r._viewports:
			if vp.render_target_update_mode != SubViewport.UPDATE_DISABLED:
				out.append(vp)
	return out


## The first surface's call each frame updates them all, after every script
## moved its camera.
func _on_pre_draw() -> void:
	if _frame == Engine.get_frames_drawn():
		return
	_frame = Engine.get_frames_drawn()
	var now := Time.get_ticks_usec()
	var dt := clampf((now - _last_usec) / 1e6, 0.0, 0.1) if _last_usec else 0.0
	_last_usec = now
	var cam := _view_camera()
	var forward := -cam.global_basis.z if cam else Vector3.FORWARD
	_update_all(_eye_positions(), forward, get_world_3d().direct_space_state, dt)


static func _update_all(eyes: PackedVector3Array, forward: Vector3, space: PhysicsDirectSpaceState3D,
		dt: float) -> void:
	var head := Vector3.ZERO
	for e in eyes:
		head += e / eyes.size()
	# Planes (two-sided ones turned toward the eye) and each surface's size on screen.
	for r in _instances:
		r._live = false
		r._score = 0.0
		var xf := r.global_transform.orthonormalized()
		if not eyes.is_empty() and r.two_sided and (head - xf.origin).dot(xf.basis.z) < 0.0:
			xf = Transform3D(Basis(-xf.basis.x, xf.basis.y, -xf.basis.z), xf.origin)
		r._plane = xf
		if not eyes.is_empty():
			r._score = r._screen_size(head, forward, space)

	# Group coplanar surfaces; the first one (in creation order) leads.
	var groups: Array[Array] = []
	for r in _instances:
		var joined := false
		if r.magnification == 1.0:
			for g in groups:
				var lead: PlanarReflection = g[0]
				if lead.magnification == 1.0 and lead._coplanar(r):
					g.append(r)
					joined = true
					break
		if not joined:
			groups.append([r])
	var scored: Array[Array] = []
	for g in groups:
		var score := 0.0
		for r: PlanarReflection in g:
			score += r._score
		if score > 0.0:
			scored.append([score, g])
	scored.sort_custom(func(a: Array, b: Array) -> bool: return a[0] > b[0])

	var leads: Array[PlanarReflection] = []
	for i in mini(scored.size(), max_active):
		var g: Array = scored[i][1]
		var seen: Array[PlanarReflection] = []
		for r: PlanarReflection in g:
			if r._score > 0.0:
				seen.append(r)
		var lead: PlanarReflection = g[0]
		lead._render(g, seen, eyes)
		leads.append(lead)
	for r in _instances:
		if r._rendering and r not in leads:
			r._set_rendering(false, 0)
		var target := 1.0 if r._live else 0.0
		r._fade = move_toward(r._fade, target, dt / FADE_TIME) if dt > 0.0 else target
		var shown := r._fade * r._fade * (3.0 - 2.0 * r._fade)
		for mat in r.materials:
			mat.set_shader_parameter(&"reflection_enabled", shown)


## Roughly the solid angle the rectangle covers from [param eye] (0 = seen
## from behind, outside the view cone or hidden).
func _screen_size(eye: Vector3, forward: Vector3, space: PhysicsDirectSpaceState3D) -> float:
	var to_eye := eye - _plane.origin
	var d := to_eye.dot(_plane.basis.z)
	if d < 0.02 or not _in_sight(eye, forward, space):
		return 0.0
	return size.x * size.y * d / maxf(to_eye.length(), 0.01) / maxf(to_eye.length_squared(), 0.01)


## A point on the rectangle (3x3 grid) inside the view cone with nothing in front of it.
func _in_sight(eye: Vector3, forward: Vector3, space: PhysicsDirectSpaceState3D) -> bool:
	var cone := cos(deg_to_rad(VIEW_CONE))
	var query := PhysicsRayQueryParameters3D.new()
	query.collision_mask = SIGHT_MASK
	query.from = eye
	for iy in 3:
		for ix in 3:
			var target := _plane * Vector3((ix - 1) * 0.42 * size.x, (iy - 1) * 0.42 * size.y, 0.0)
			var dir := target - eye
			var dist := dir.length()
			if dist < 0.001 or dir.dot(forward) < cone * dist:
				continue
			query.to = target
			var hit := space.intersect_ray(query)
			if hit.is_empty() or (hit["position"] as Vector3).distance_to(target) < SIGHT_SLACK:
				return true
	return false


func _coplanar(other: PlanarReflection) -> bool:
	var n := _plane.basis.z
	return n.dot(other._plane.basis.z) > COPLANAR_DOT \
			and absf((other._plane.origin - _plane.origin).dot(n)) < COPLANAR_DISTANCE


## Renders this plane's reflection for the [param seen] members of [param group].
func _render(group: Array, seen: Array[PlanarReflection], eyes: PackedVector3Array) -> void:
	if _viewports.is_empty():
		_create_renderer(group)
	var xf := _plane
	# The visible rectangles in this plane's coordinates.
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for r in seen:
		for corner: Vector2 in [Vector2(-0.5, -0.5), Vector2(0.5, -0.5), Vector2(-0.5, 0.5), Vector2(0.5, 0.5)]:
			var p := r._plane * Vector3(corner.x * r.size.x, corner.y * r.size.y, 0.0) - xf.origin
			var q := Vector2(p.dot(xf.basis.x), p.dot(xf.basis.y))
			lo = lo.min(q)
			hi = hi.max(q)
	var center := (lo + hi) / 2.0
	var extent := hi - lo
	# Grow the short side to the texture's aspect (the frustum has the viewport's).
	var aspect := float(_viewports[0].size.x) / _viewports[0].size.y
	if extent.x / extent.y < aspect:
		extent.x = extent.y * aspect
	else:
		extent.y = extent.x / aspect
	var origin := xf.origin + xf.basis.x * center.x + xf.basis.y * center.y
	var right := _viewports[1 if eyes.size() > 1 and _xr_active() else 0].get_texture()
	for r in seen:
		r._live = true
		for mat in r.materials:
			mat.set_shader_parameter(&"reflection_left", _viewports[0].get_texture())
			mat.set_shader_parameter(&"reflection_right", right)
			mat.set_shader_parameter(&"reflection_origin", origin)
			mat.set_shader_parameter(&"reflection_u", xf.basis.x / extent.x)
			mat.set_shader_parameter(&"reflection_v", xf.basis.y / extent.y)
			mat.set_shader_parameter(&"reflection_normal", xf.basis.z)
	_set_rendering(true, eyes.size())
	for i in mini(eyes.size(), 2):
		_place_camera(_cameras[i], eyes[i], origin, extent / magnification)


func _create_renderer(group: Array) -> void:
	# Sized for the whole plane (all members), at the finest resolution asked for.
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	var ppm := 0.0
	for r: PlanarReflection in group:
		ppm = maxf(ppm, r.pixels_per_meter * r.magnification)
		for corner: Vector2 in [Vector2(-0.5, -0.5), Vector2(0.5, 0.5)]:
			var p := r._plane * Vector3(corner.x * r.size.x, corner.y * r.size.y, 0.0) - _plane.origin
			var q := Vector2(p.dot(_plane.basis.x), p.dot(_plane.basis.y))
			lo = lo.min(q)
			hi = hi.max(q)
	var extent := (hi - lo).abs()
	# A wide facade gets a wide texture, but not wider than this: one window
	# alone would waste most of it.
	var aspect := clampf(extent.x / maxf(extent.y, 0.01), 0.6, 2.6)
	var res := Vector2(extent.x, extent.x / aspect) * ppm
	res *= minf(1.0, float(max_resolution) / maxf(res.x, res.y))
	var res_i := Vector2i(maxi(roundi(res.x), 16), maxi(roundi(res.y), 16))
	var root := get_tree().root
	var env := _reflection_environment()
	for eye in 2:
		var vp := SubViewport.new()
		vp.name = "Eye%d" % eye
		vp.size = res_i
		vp.msaa_3d = root.msaa_3d if msaa else Viewport.MSAA_DISABLED
		vp.use_hdr_2d = true
		vp.use_occlusion_culling = false
		vp.positional_shadow_atlas_size = 2048 if shadows else 0
		vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
		var cam := Camera3D.new()
		cam.projection = Camera3D.PROJECTION_FRUSTUM
		cam.cull_mask = cull_mask
		cam.environment = env
		vp.add_child(cam)
		add_child(vp)
		cam.current = true
		_viewports.append(vp)
		_cameras.append(cam)


func _set_rendering(on: bool, eye_count: int) -> void:
	_rendering = on
	for i in _viewports.size():
		var mode := SubViewport.UPDATE_ALWAYS if on and i < eye_count else SubViewport.UPDATE_DISABLED
		if _viewports[i].render_target_update_mode != mode:
			_viewports[i].render_target_update_mode = mode


## The mirrored eye looks through the rectangle ([param origin], [param extent]
## in this plane); the frustum's near plane lies on it.
func _place_camera(cam: Camera3D, eye: Vector3, origin: Vector3, extent: Vector2) -> void:
	var n := _plane.basis.z
	var d := (eye - origin).dot(n)
	if d < MIN_EYE_DISTANCE:
		eye += n * (MIN_EYE_DISTANCE - d)
		d = MIN_EYE_DISTANCE
	var mirrored := eye - 2.0 * d * n
	# Looking along +n (into the room); X flipped: the image is mirrored.
	var cam_basis := Basis(-_plane.basis.x, _plane.basis.y, -n)
	var xform := Transform3D(cam_basis, mirrored)
	var to_center := origin - mirrored
	var offset := Vector2(to_center.dot(cam_basis.x), to_center.dot(cam_basis.y))
	# Straight to the renderer (see the class doc); the node follows for tools.
	RenderingServer.camera_set_transform(cam.get_camera_rid(), xform)
	RenderingServer.camera_set_frustum(cam.get_camera_rid(), extent.y, offset, d, d + reach)
	cam.global_transform = xform
	cam.set_frustum(extent.y, offset, d, d + reach)


static func _xr_active() -> bool:
	var xr := XRServer.primary_interface
	return xr != null and xr.is_initialized()


## The camera the player sees through (the XR camera in the headset).
func _view_camera() -> Camera3D:
	return view_camera if is_instance_valid(view_camera) else get_viewport().get_camera_3d()


## Eye positions in world space: both eyes in XR, else the rendering camera.
func _eye_positions() -> PackedVector3Array:
	var eyes := PackedVector3Array()
	var xr := XRServer.primary_interface
	if xr and xr.is_initialized() and get_viewport().use_xr:
		for view in mini(xr.get_view_count(), 2):
			eyes.append(xr.get_transform_for_view(view, XRServer.world_origin).origin)
		return eyes
	var cam := _view_camera()
	if cam:
		eyes.append(cam.global_position)
		if simulate_stereo:
			eyes.append(cam.global_position + cam.global_basis.x * DESKTOP_IPD)
	return eyes


## The world's environment without glow and with a linear tone mapper: the
## surface's shader writes the reflection to EMISSION and the main pass tone maps
## (and glows) once.
func _reflection_environment() -> Environment:
	if _reflection_env:
		return _reflection_env
	var env := get_world_3d().environment
	env = env.duplicate() if env else Environment.new()
	_reflection_env = env
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.tonemap_exposure = 1.0
	env.glow_enabled = false
	env.adjustment_enabled = false
	env.ssr_enabled = false
	env.ssao_enabled = false
	env.ssil_enabled = false
	env.sdfgi_enabled = false
	return env


## Copies what [DayNight] changes in the world's environment (ambient light,
## fog) into the reflections' copy; the sky is shared and needs no copy.
static func sync_environment(source: Environment) -> void:
	if not _reflection_env or not source:
		return
	for property: StringName in SYNCED_ENVIRONMENT:
		_reflection_env.set(property, source.get(property))
