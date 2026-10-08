class_name ZoneStreamer
extends Node3D
## Loads zones in the background and frees them again (roadmap phase 0, D-059).
##
## The zone graph ([member graph]) lists each zone's scene and the connections
## between zones (a door now; later an elevator or a station). The player is in
## one zone at a time: the zone whose [constant BOUNDS] Area3D (Player Body)
## holds the body's center (its capsule may touch two at a doorway). Every zone within [member load_depth] connections of it is loaded,
## every other one is freed, so a zone two connections away is gone. Zones are
## children of this node, named after their id in PascalCase (zone "corridor"
## is Zones/Corridor), at their world position (D-008: never offset).
##
## The scene loads on ResourceLoader's threads; instantiating it and adding it
## to the tree (its _ready calls) run on the main thread, in the frame it's ready
## ([member threaded_instantiate] would move the first off it, unsafely). A connection's door is held shut
## by a [ZoneGate] until the zones on both sides are in, so nobody opens a door
## onto nothing. Zones already under this node at start (main.tscn's apartment)
## count as loaded. Processing runs only while something loads.
##
## A loaded zone the player isn't in is drawn only while it can be seen: a
## connection to the player's zone has no door, or its door is open, or an eye
## is at its peephole ([method ZoneGate.is_open]). Hidden (everything but its
## connection doors, which the other side sees too), it costs nothing to
## draw, its lights' shadow maps included (occlusion culling doesn't cover
## those, nor objects reaching behind the camera). A zone that just loaded
## stays drawn for [constant REVEAL_FRAMES] frames (or one more than it has
## reflection probes, which show and capture one per frame), so its pipelines
## compile and the reflections' and the peephole's warm-ups see it.
##
## A connection can have an approach range (the units, D-062): its zone loads
## from the other side only while the player is within that many meters of
## the door, checked 4 times a second.

## A wanted zone was added to the tree.
signal zone_loaded(id: StringName, root: Node3D)
## A zone is about to be freed (still in the tree).
signal zone_unloading(id: StringName, root: Node3D)
## The player entered another zone.
signal current_changed(id: StringName)
## Every wanted zone is loaded and nothing is loading.
signal settled

const GROUP := &"zone_streamer"
## The Area3D in a zone's root that covers where the player can be in it.
const BOUNDS := "Bounds"
## The gate's node name under a connection's door.
const GATE := "ZoneGate"
## Frames a newly loaded zone is drawn before it may hide.
const REVEAL_FRAMES := 3
## Seconds between checks of the player's distance to approach-range doors (D-062).
const APPROACH_CHECK := 0.25
## Meters past a connection's approach range before a zone it brought in is freed again.
const APPROACH_HYSTERESIS := 2.0
## The point above the player body's origin (its feet) that says which zone it's in.
const BODY_PROBE_HEIGHT := 0.5
## While the body touches two zones' bounds, its zone is checked every this many physics frames.
const BODY_CHECK_FRAMES := 9

@export_file("*.json") var graph := "res://zones/zone_graph.json"
## Zones up to this many connections from the player's are kept loaded.
@export_range(0, 4) var load_depth := 1
## The zone the player starts in; empty: the first zone already under this node.
@export var start_zone: StringName = &""
## Instantiate loaded scenes on a worker thread. Off by default: a zone's nodes create rendering
## resources as they're built, and the RenderingServer isn't safe to call from another thread in the
## default thread model (units crashed Godot now and then, D-062). Loading stays threaded.
@export var threaded_instantiate := false

## The zone the player is in.
var current: StringName = &""

var _scenes: Dictionary[StringName, String] = {}
var _links: Dictionary[StringName, Array] = {}
# {"zones": [a, b], "door": [zone, path] or []}
var _connections: Array[Dictionary] = []
var _loaded: Dictionary[StringName, Node3D] = {}
# id -> {"path": String, "task": int (-1 while ResourceLoader loads), "started": usec}
var _requests: Dictionary[StringName, Dictionary] = {}
# Roots instantiated by worker tasks, picked up on the main thread.
var _instanced: Dictionary[StringName, Node3D] = {}
var _instanced_lock := Mutex.new()
# Times the player body is inside each zone's bounds (overlapping bounds at doorways).
var _inside: Dictionary[StringName, int] = {}
var _body: Node3D
var _approach_timer: Timer
var _load_ms: Dictionary[StringName, float] = {}
# Zones drawn for their first frames after loading.
var _revealing: Dictionary[StringName, bool] = {}
# Whether each loaded zone is drawn, and the nodes hiding it hid (re-shown, and only those).
var _shown: Dictionary[StringName, bool] = {}
var _hidden: Dictionary[StringName, Array] = {}


func _enter_tree() -> void:
	add_to_group(GROUP)


func _ready() -> void:
	set_process(false)
	set_physics_process(false)
	_read_graph()
	for child in get_children():
		var id := id_for(child.name)
		if not id.is_empty() and child is Node3D:
			_adopt(id, child as Node3D)
	if start_zone.is_empty() and not _loaded.is_empty():
		start_zone = _loaded.keys()[0]
	current = start_zone
	_refresh()
	_update_visibility()


## The scene's ZoneStreamer, or null.
static func find(tree: SceneTree) -> ZoneStreamer:
	return tree.get_first_node_in_group(GROUP) as ZoneStreamer


## The zone id for a node name ("Corridor" -> &"corridor"), or empty.
func id_for(node_name: String) -> StringName:
	for id in _scenes:
		if _node_name(id) == node_name:
			return id
	return &""


## The zone's root while it's loaded, else null.
func get_zone(id: StringName) -> Node3D:
	return _loaded.get(id)


func is_ready(id: StringName) -> bool:
	return _loaded.has(id)


func is_loading(id: StringName) -> bool:
	return _requests.has(id)


## Every zone the player's zone wants is loaded and nothing is loading.
func is_settled() -> bool:
	return _requests.is_empty() and _wanted().keys().all(func(id: StringName) -> bool: return _loaded.has(id))


## Waits (await it) until [method is_settled].
func wait_settled() -> void:
	while not is_settled():
		await settled


## Milliseconds the zone's last load took, from request to in the tree (-1 if never loaded here).
func get_load_ms(id: StringName) -> float:
	return _load_ms.get(id, -1.0)


## Zones loaded now.
func loaded_zones() -> Array[StringName]:
	var out: Array[StringName] = []
	out.assign(_loaded.keys())
	return out


## True while the zone is loaded and drawn.
func is_shown(id: StringName) -> bool:
	return _loaded.has(id) and _shown.get(id, true)


## The loaded zone whose Bounds contain [param point], or empty.
func zone_at(point: Vector3) -> StringName:
	for id in _loaded:
		var bounds := _loaded[id].get_node_or_null(BOUNDS) as Area3D
		if not bounds:
			continue
		for shape: CollisionShape3D in bounds.find_children("*", "CollisionShape3D", false, false):
			var box := shape.shape as BoxShape3D
			if box and AABB(-box.size / 2.0, box.size).has_point(shape.global_transform.affine_inverse() * point):
				return id
	return &""


## Connections from the player's zone to [param id] (-1: not connected).
func distance_to(id: StringName) -> int:
	return _distances().get(id, -1)


## Keeps zones up to [param depth] connections away loaded (--load-depth; 0: only the player's).
func set_load_depth(depth: int) -> void:
	load_depth = depth
	_refresh()


## Makes [param id] the player's zone (the bounds do this; tests and tools may too).
func set_current(id: StringName) -> void:
	if id == current or not _scenes.has(id):
		return
	current = id
	current_changed.emit(id)
	_refresh()
	_update_visibility()


## Frees a loaded zone and loads it again (perf: the cost of a zone load, D-059).
func reload(id: StringName) -> void:
	if _loaded.has(id):
		_unload(id)
	_refresh()


## Adds a zone to the graph at runtime (tests).
func add_zone(id: StringName, scene: String) -> void:
	_scenes[id] = scene
	if not _links.has(id):
		_links[id] = []
	_refresh()


## Removes a zone from the graph (and frees it) at runtime (tests).
func remove_zone(id: StringName) -> void:
	if _loaded.has(id):
		_unload(id)
	if _requests.has(id) and _requests[id]["task"] >= 0:
		WorkerThreadPool.wait_for_task_completion(_requests[id]["task"])
		_instanced_lock.lock()
		var orphan: Node3D = _instanced.get(id)
		_instanced.erase(id)
		_instanced_lock.unlock()
		if orphan:
			orphan.free()
	_requests.erase(id)
	_scenes.erase(id)
	for other in _links:
		_links[other].erase(id)
	_links.erase(id)
	_connections = _connections.filter(func(c: Dictionary) -> bool: return id not in c["zones"])
	_refresh()


## Connects two zones at runtime (tests); [param door] as in the graph ("zone:path") or empty.
func add_connection(a: StringName, b: StringName, door := "") -> void:
	_connect(a, b, door)
	_attach_gates()
	_refresh()


func _read_graph() -> void:
	var file := FileAccess.open(graph, FileAccess.READ)
	if not file:
		push_error("ZoneStreamer: can't read %s" % graph)
		return
	var data: Variant = JSON.parse_string(file.get_as_text())
	if not data is Dictionary:
		push_error("ZoneStreamer: %s isn't a JSON object" % graph)
		return
	var zones: Dictionary = data.get("zones", {})
	for id: String in zones:
		var zone: Dictionary = zones[id]
		_scenes[StringName(id)] = zone["scene"]
		_links[StringName(id)] = []
	for c: Dictionary in data.get("connections", []):
		var pair: Array = c["zones"]
		var approach: Dictionary = c.get("approach", {})
		_connect(StringName(pair[0]), StringName(pair[1]), c.get("door", ""),
				StringName(approach.get("zone", "")), float(approach.get("within", 0.0)))


func _connect(a: StringName, b: StringName, door: String, approach_zone := &"", within := 0.0) -> void:
	if not _scenes.has(a) or not _scenes.has(b):
		push_error("ZoneStreamer: connection %s-%s names an unknown zone" % [a, b])
		return
	_links[a].append(b)
	_links[b].append(a)
	var door_ref: Array = []
	if not door.is_empty():
		var parts := door.split(":", true, 1)
		door_ref = [StringName(parts[0]), parts[1]]
	# approach: [zone, meters]: that zone loads from the other side only while the player is near the door.
	var approach: Array = [approach_zone, within] if not approach_zone.is_empty() and not door_ref.is_empty() else []
	_connections.append({"zones": [a, b], "door": door_ref, "approach": approach})
	if not approach.is_empty() and not _approach_timer:
		_approach_timer = Timer.new()
		_approach_timer.wait_time = APPROACH_CHECK
		_approach_timer.autostart = true
		_approach_timer.timeout.connect(_refresh)
		add_child.call_deferred(_approach_timer)


# Breadth-first connection counts from the player's zone.
func _distances() -> Dictionary[StringName, int]:
	var dist: Dictionary[StringName, int] = {}
	if current.is_empty():
		return dist
	dist[current] = 0
	var queue: Array[StringName] = [current]
	while not queue.is_empty():
		var id: StringName = queue.pop_front()
		for next: StringName in _links.get(id, []):
			if not dist.has(next):
				dist[next] = dist[id] + 1
				queue.append(next)
	return dist


func _wanted() -> Dictionary[StringName, int]:
	# Breadth-first like _distances(), but a connection with an approach range only leads into its
	# zone while the player is near the door (the player's own zone is always wanted).
	var out: Dictionary[StringName, int] = {}
	if current.is_empty():
		return out
	out[current] = 0
	var queue: Array[StringName] = [current]
	while not queue.is_empty():
		var id: StringName = queue.pop_front()
		if out[id] >= load_depth:
			continue
		for c in _connections:
			var pair: Array = c["zones"]
			if id not in pair:
				continue
			var next: StringName = pair[1] if pair[0] == id else pair[0]
			if out.has(next) or not _approached(c, next):
				continue
			out[next] = out[id] + 1
			queue.append(next)
	return out


# False while [param zone] is behind an approach-range connection and the player is farther from its door.
func _approached(connection: Dictionary, zone: StringName) -> bool:
	var approach: Array = connection["approach"]
	if approach.is_empty() or approach[0] != zone or zone == current:
		return true
	var door_ref: Array = connection["door"]
	var owner_zone: Node3D = _loaded.get(door_ref[0])
	var door := owner_zone.get_node_or_null(NodePath(door_ref[1])) as Node3D if owner_zone else null
	if not door or not is_instance_valid(_body):
		return false
	# Hysteresis: a zone that's in (or coming) stays until the player is a bit farther away.
	var reach: float = approach[1] + (APPROACH_HYSTERESIS if _loaded.has(zone) or _requests.has(zone) else 0.0)
	var to_door := door.global_position - _body.global_position
	return Vector2(to_door.x, to_door.z).length() < reach


func _refresh() -> void:
	if current.is_empty():
		return
	var wanted := _wanted()
	for id: StringName in _loaded.keys():
		if not wanted.has(id):
			_unload(id)
	# Nearest first: the zones behind the player's doors before the ones beyond.
	var order := wanted.keys()
	order.sort_custom(func(a: StringName, b: StringName) -> bool: return wanted[a] < wanted[b])
	for id: StringName in order:
		if not _loaded.has(id) and not _requests.has(id):
			_request(id)
	if is_settled():
		settled.emit.call_deferred()


func _request(id: StringName) -> void:
	var path := _scenes[id]
	var err := ResourceLoader.load_threaded_request(path, "PackedScene", true)
	if err != OK:
		push_error("ZoneStreamer: can't load %s (%s)" % [path, error_string(err)])
		return
	_requests[id] = {"path": path, "task": -1, "started": Time.get_ticks_usec()}
	set_process(true)


func _process(_delta: float) -> void:
	for id: StringName in _requests.keys():
		var req := _requests[id]
		if req["task"] < 0:
			var status := ResourceLoader.load_threaded_get_status(req["path"])
			if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				continue
			if status != ResourceLoader.THREAD_LOAD_LOADED:
				push_error("ZoneStreamer: loading %s failed" % req["path"])
				_requests.erase(id)
				continue
			var scene := ResourceLoader.load_threaded_get(req["path"]) as PackedScene
			if threaded_instantiate:
				req["task"] = WorkerThreadPool.add_task(_instantiate.bind(id, scene), false, "zone %s" % id)
				continue
			_finish(id, scene.instantiate() as Node3D)
		elif WorkerThreadPool.is_task_completed(req["task"]):
			WorkerThreadPool.wait_for_task_completion(req["task"])
			_instanced_lock.lock()
			var root: Node3D = _instanced.get(id)
			_instanced.erase(id)
			_instanced_lock.unlock()
			_finish(id, root)
	if _requests.is_empty():
		set_process(false)
		if is_settled():
			settled.emit()


# Worker thread: builds the zone's nodes outside the tree.
func _instantiate(id: StringName, scene: PackedScene) -> void:
	var root := scene.instantiate() as Node3D
	# Probes capture (six scene passes each) when they first show: _finish shows them one per frame.
	for probe in root.find_children("*", "ReflectionProbe", true, false):
		if (probe as ReflectionProbe).visible:
			(probe as ReflectionProbe).visible = false
			probe.set_meta(&"zone_streamer_probe", true)
	_instanced_lock.lock()
	_instanced[id] = root
	_instanced_lock.unlock()


func _finish(id: StringName, root: Node3D) -> void:
	var req: Dictionary = _requests[id]
	_requests.erase(id)
	if not root:
		push_error("ZoneStreamer: %s has no Node3D root" % req["path"])
		return
	if not _wanted().has(id):
		# The player moved on while it loaded.
		root.free()
		return
	root.name = _node_name(id)
	add_child(root)
	_load_ms[id] = (Time.get_ticks_usec() - int(req["started"])) / 1000.0
	_revealing[id] = true
	_adopt(id, root)
	print("ZoneStreamer: %s loaded in %.0f ms" % [id, _load_ms[id]])
	zone_loaded.emit(id, root)
	var probes := root.find_children("*", "ReflectionProbe", true, false).filter(
			func(n: Node) -> bool: return n.has_meta(&"zone_streamer_probe"))
	for i in maxi(REVEAL_FRAMES, probes.size() + 1):
		await RenderingServer.frame_post_draw
		if not is_instance_valid(root):
			return
		if i < probes.size():
			(probes[i] as ReflectionProbe).visible = true
			probes[i].remove_meta(&"zone_streamer_probe")
	_revealing.erase(id)
	_update_visibility()


func _adopt(id: StringName, root: Node3D) -> void:
	_loaded[id] = root
	var bounds := root.get_node_or_null(BOUNDS) as Area3D
	if bounds:
		bounds.body_entered.connect(_on_body_entered.bind(id))
		bounds.body_exited.connect(_on_body_exited.bind(id))
	_attach_gates()
	_update_visibility()


func _unload(id: StringName) -> void:
	var root: Node3D = _loaded[id]
	zone_unloading.emit(id, root)
	_loaded.erase(id)
	_inside.erase(id)
	_revealing.erase(id)
	_shown.erase(id)
	_hidden.erase(id)
	root.queue_free()
	print("ZoneStreamer: %s unloaded" % id)


# Each connection's door gets its gate once the zone holding it is loaded.
func _attach_gates() -> void:
	for c in _connections:
		var door_ref: Array = c["door"]
		if door_ref.is_empty() or not _loaded.has(door_ref[0]):
			continue
		var door := _loaded[door_ref[0]].get_node_or_null(NodePath(door_ref[1]))
		if not door:
			push_warning("ZoneStreamer: door %s not found in zone %s" % [door_ref[1], door_ref[0]])
			continue
		if door.has_node(GATE):
			continue
		var gate := ZoneGate.new()
		gate.name = GATE
		gate.streamer = self
		var pair: Array = c["zones"]
		gate.zones.assign(pair)
		gate.open_changed.connect(func(_open: bool) -> void: _update_visibility())
		door.add_child(gate)


# Draws the player's zone, the zones seen through an open connection, and zones still revealing.
func _update_visibility() -> void:
	if current.is_empty():
		return
	for id in _loaded:
		var shown := id == current or _revealing.has(id) or _seen_from_current(id)
		if _shown.get(id, true) == shown:
			continue
		_shown[id] = shown
		if shown:
			for node: Node3D in _hidden.get(id, []):
				if is_instance_valid(node):
					node.visible = true
			_hidden.erase(id)
		else:
			var hidden: Array[Node3D] = []
			_hide_except_doors(_loaded[id], _door_paths(id), hidden)
			_hidden[id] = hidden


# The zone's connection doors (paths in the zone): they stay drawn while it hides,
# since they're seen from the other side too.
func _door_paths(id: StringName) -> Array[NodePath]:
	var out: Array[NodePath] = []
	for c in _connections:
		var door_ref: Array = c["door"]
		if not door_ref.is_empty() and door_ref[0] == id:
			out.append(NodePath(door_ref[1]))
	return out


# Hides every visible Node3D child of [param node] that isn't (and doesn't hold) a door
# in [param keep] (paths relative to the zone root); collects what it hid.
func _hide_except_doors(node: Node, keep: Array[NodePath], hidden: Array[Node3D], prefix := "") -> void:
	for child in node.get_children():
		var path := prefix + String(child.name)
		if keep.any(func(door: NodePath) -> bool: return String(door) == path):
			continue
		if keep.any(func(door: NodePath) -> bool: return String(door).begins_with(path + "/")):
			_hide_except_doors(child, keep, hidden, path + "/")
			continue
		var child3d := child as Node3D
		if child3d and child3d.visible:
			child3d.visible = false
			hidden.append(child3d)


func _seen_from_current(id: StringName) -> bool:
	for c in _connections:
		var pair: Array = c["zones"]
		if not (current in pair and id in pair):
			continue
		var door_ref: Array = c["door"]
		if door_ref.is_empty():
			return true
		var owner_zone: Node3D = _loaded.get(door_ref[0])
		if not owner_zone:
			continue
		var gate := owner_zone.get_node_or_null("%s/%s" % [door_ref[1], GATE]) as ZoneGate
		if gate and gate.is_open():
			return true
	return false


func _on_body_entered(body: Node3D, id: StringName) -> void:
	_inside[id] = _inside.get(id, 0) + 1
	_body = body
	_check_body()


func _on_body_exited(_exited: Node3D, id: StringName) -> void:
	_inside[id] = maxi(_inside.get(id, 0) - 1, 0)
	_check_body()


# The player's zone is where the body's center is, not what its capsule touches: standing
# against a closed door, the capsule reaches into the next zone's bounds (headset bug
# 2026-10-08: the corridor vanished). While it touches more than one zone, check a few
# times a second; otherwise the bounds' signals are enough.
func _check_body() -> void:
	if not is_instance_valid(_body):
		return
	var here := zone_at(_body.global_position + Vector3.UP * BODY_PROBE_HEIGHT)
	if not here.is_empty():
		set_current(here)
	var touching := _inside.values().filter(func(n: int) -> bool: return n > 0).size()
	set_physics_process(touching > 1)


func _physics_process(_delta: float) -> void:
	if Engine.get_physics_frames() % BODY_CHECK_FRAMES == 0:
		_check_body()


func _node_name(id: StringName) -> String:
	return String(id).to_pascal_case()
