class_name OutsideView
extends Node
## Draws each side of the city only while a window facing it can be seen
## (D-048, D-061).
##
## Windows mark their openings with a VisibleOnScreenNotifier3D in the
## [constant GROUP] group; its metadata/outside_facing (a unit Vector3 out of
## the window, (0, 0, -1) when missing) says which side of the building it
## looks out of. Notifiers honor occlusion culling, so a window behind walls
## counts as off screen. The city around the building is split by side
## (north, east, south, west: [constant NORTH] ..; a corner belongs to both
## its sides, D-061): every child of a
## [member targets] node is one part, drawn while a window onto one of its
## sides is on screen. A part's sides are its metadata/outside_sides bit mask
## (FarTowers and FlyingTraffic set it on their MultiMeshes), else
## [method sides_of] its position (the near towers). While no window is in view
## nothing is drawn. Event-driven: no per-frame cost.
##
## The city's MultiMeshes span whole sides of the horizon, and occlusion
## culling can't hide bounds that reach behind the camera, so walls alone don't
## keep them from being drawn. Notifiers added later (zones loaded at runtime)
## register themselves through the tree's node_added signal.
##
## [code]--outside=all[/code] (or n,e,s,w; also [code]--shot-outside=[/code])
## on the command line keeps those sides drawn whatever is in view: stills and
## perf runs of views onto windows that don't exist yet.

const GROUP := &"outside_view"
const META_FACING := &"outside_facing"
const META_SIDES := &"outside_sides"
## Side bits: the city beyond each facade of our building.
const NORTH := 1
const EAST := 2
const SOUTH := 4
const WEST := 8
const ALL_SIDES := 15
const SIDE_NAMES: PackedStringArray = ["North", "East", "South", "West"]
## Out of each side's facade, in side bit order.
const SIDE_DIRECTIONS: Array[Vector3] = [Vector3(0, 0, -1), Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0)]
## Our building's footprint (world x, z; floor 44, D-008): the facades are its
## edges, north z = -3.2 (the apartment's windows), east x = 21.2, south
## z = 16.7, west x = -10.5. Matches "building" in tools/city/near_towers.json.
const BUILDING := Rect2(-10.5, -3.2, 31.7, 19.9)
## A point belongs to a side once it is this far toward the building from the
## facade's line or beyond it (north: z < 0, as before D-061).
const OVERLAP := 3.2
## A window looks out of every side within 67.5° of its facing (a diagonal
## window sees two).
const FACING_MIN_DOT := 0.38

## Parents of what's drawn only through windows: towers, traffic.
@export var targets: Array[Node3D] = []
## Everything stays visible this long after start, so the first frames draw
## (and compile) the whole city whatever the player looks at.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var startup_delay := 0.5
## Sides drawn whatever is in view (bit mask; [code]--outside[/code]).
@export_flags("North", "East", "South", "West") var forced_sides := 0

var _notifiers: Array[VisibleOnScreenNotifier3D] = []
var _notifier_sides: PackedInt32Array = []
var _parts: Array[Node3D] = []
var _part_sides: PackedInt32Array = []
# Parts this node hid (others may be hidden on purpose, e.g. --perf-hide).
var _hidden: Dictionary[Node3D, bool] = {}
var _shown := ALL_SIDES
var _active := false
var _queued := false


func _ready() -> void:
	forced_sides |= _sides_from_args()
	refresh_parts()
	for node in get_tree().get_nodes_in_group(GROUP):
		_register(node)
	get_tree().node_added.connect(_on_node_added)
	await get_tree().create_timer(startup_delay).timeout
	_active = true
	_apply()


## The sides a point (world x, z) of the city belongs to: those whose facade
## it lies beyond (less [constant OVERLAP]). Corners belong to two.
static func sides_of(point: Vector2) -> int:
	var sides := 0
	if point.y < BUILDING.position.y + OVERLAP:
		sides |= NORTH
	if point.x > BUILDING.end.x - OVERLAP:
		sides |= EAST
	if point.y > BUILDING.end.y - OVERLAP:
		sides |= SOUTH
	if point.x < BUILDING.position.x + OVERLAP:
		sides |= WEST
	return sides


## The sides a window facing [param facing] looks out of.
static func facing_sides(facing: Vector3) -> int:
	var flat := Vector3(facing.x, 0.0, facing.z)
	if flat.length_squared() < 0.0001:
		return NORTH
	flat = flat.normalized()
	var sides := 0
	for i in SIDE_DIRECTIONS.size():
		if SIDE_DIRECTIONS[i].dot(flat) >= FACING_MIN_DOT:
			sides |= 1 << i
	return sides


## [param box] cut off at the facade of side [param side] (one bit): from
## inside the building nothing on that side lies behind it, so the bounds
## never contain or reach behind a camera inside, and occlusion can cull them.
static func clamp_to_side(box: AABB, side: int) -> AABB:
	var out := box
	match side:
		NORTH:
			out.size.z = maxf(minf(out.end.z, BUILDING.position.y) - out.position.z, 0.0)
		EAST:
			var east_end := out.end.x
			out.position.x = maxf(out.position.x, BUILDING.end.x)
			out.size.x = maxf(east_end - out.position.x, 0.0)
		SOUTH:
			var south_end := out.end.z
			out.position.z = maxf(out.position.z, BUILDING.end.y)
			out.size.z = maxf(south_end - out.position.z, 0.0)
		WEST:
			out.size.x = maxf(minf(out.end.x, BUILDING.position.x) - out.position.x, 0.0)
	return out


## True while the city is hidden because no window is in view.
func is_outside_hidden() -> bool:
	return _active and not _notifiers.is_empty() and _shown == 0


## The sides drawn now (bit mask).
func shown_sides() -> int:
	return _shown


## Re-reads the targets' parts (after a target rebuilt its children).
func refresh_parts() -> void:
	for part: Node3D in _hidden:
		if is_instance_valid(part):
			part.visible = true
	_hidden.clear()
	_parts.clear()
	_part_sides.clear()
	for target in targets:
		if not target:
			continue
		if target.has_meta(META_SIDES):
			_add_part(target)
			continue
		for child in target.get_children():
			if child is Node3D:
				_add_part(child as Node3D)
	_queue_apply()


func _add_part(part: Node3D) -> void:
	var at := part.global_position
	_parts.append(part)
	_part_sides.append(int(part.get_meta(META_SIDES, sides_of(Vector2(at.x, at.z)))))


func _on_node_added(node: Node) -> void:
	if node.is_in_group(GROUP):
		_register(node)


func _register(node: Node) -> void:
	var notifier := node as VisibleOnScreenNotifier3D
	if not notifier or notifier in _notifiers:
		return
	# World axes: zones are authored where they stand, never turned (D-008).
	var facing: Vector3 = notifier.get_meta(META_FACING, Vector3(0, 0, -1))
	_notifiers.append(notifier)
	_notifier_sides.append(facing_sides(facing))
	notifier.screen_entered.connect(_queue_apply)
	notifier.screen_exited.connect(_queue_apply)
	notifier.tree_exiting.connect(_unregister.bind(notifier), CONNECT_ONE_SHOT)
	_queue_apply()


func _unregister(notifier: VisibleOnScreenNotifier3D) -> void:
	var i := _notifiers.find(notifier)
	if i < 0:
		return
	_notifiers.remove_at(i)
	_notifier_sides.remove_at(i)
	notifier.screen_entered.disconnect(_queue_apply)
	notifier.screen_exited.disconnect(_queue_apply)
	_queue_apply()


# Several notifiers can change in one frame: apply once, at the end of it.
func _queue_apply() -> void:
	if _queued:
		return
	_queued = true
	_apply.call_deferred()


func _apply() -> void:
	_queued = false
	if not _active:
		return
	# Without any window notifier (a zone without windows) nothing is hidden.
	var shown := forced_sides
	if _notifiers.is_empty():
		shown = ALL_SIDES
	else:
		for i in _notifiers.size():
			if _notifiers[i].is_on_screen():
				shown |= _notifier_sides[i]
	_shown = shown
	for i in _parts.size():
		var part := _parts[i]
		if not is_instance_valid(part):
			continue
		if _part_sides[i] & shown:
			if _hidden.erase(part):
				part.visible = true
		elif part.visible:
			part.visible = false
			_hidden[part] = true


## --outside=<all|n,e,s,w> (or --shot-outside=...) as a side mask.
static func _sides_from_args() -> int:
	for arg in OS.get_cmdline_user_args():
		for key: String in ["--outside=", "--shot-outside="]:
			if not arg.begins_with(key):
				continue
			var value := arg.trim_prefix(key).to_lower()
			if value == "all":
				return ALL_SIDES
			var sides := 0
			for letter in value.split(",", false):
				var i := "nesw".find(letter.strip_edges().left(1))
				if i >= 0:
					sides |= 1 << i
			return sides
	return 0
