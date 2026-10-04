class_name OutsideView
extends Node
## Hides the city while no window onto it can be seen (D-048).
##
## Windows mark their openings with a VisibleOnScreenNotifier3D in the
## [constant GROUP] group (the apartment generator adds one per window).
## Notifiers honor occlusion culling, so a window behind walls counts as off
## screen. While none is on screen, [member targets] are hidden; they show
## again as soon as one enters. Event-driven: no per-frame cost.
##
## The city's MultiMeshes span the whole horizon, and occlusion culling can't
## hide bounds that reach behind the camera, so walls alone don't keep them
## from being drawn. Notifiers added later (zones loaded at runtime) register
## themselves through the tree's node_added signal.

const GROUP := &"outside_view"

## Nodes drawn only through windows: towers, traffic, the street glow.
@export var targets: Array[Node3D] = []
## Everything stays visible this long after start, so the first frames draw
## (and compile) the whole city whatever the player looks at.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var startup_delay := 0.5

var _notifiers: Array[VisibleOnScreenNotifier3D] = []
var _active := false
# Targets this node hid (others may be hidden on purpose, e.g. --perf-hide).
var _hidden: Array[Node3D] = []


func _ready() -> void:
	for node in get_tree().get_nodes_in_group(GROUP):
		_register(node)
	get_tree().node_added.connect(_on_node_added)
	await get_tree().create_timer(startup_delay).timeout
	_active = true
	_apply()


## True while the city is hidden because no window is in view.
func is_outside_hidden() -> bool:
	return not _hidden.is_empty()


func _on_node_added(node: Node) -> void:
	if node.is_in_group(GROUP):
		_register(node)


func _register(node: Node) -> void:
	var notifier := node as VisibleOnScreenNotifier3D
	if not notifier or notifier in _notifiers:
		return
	_notifiers.append(notifier)
	notifier.screen_entered.connect(_apply)
	notifier.screen_exited.connect(_apply)
	notifier.tree_exiting.connect(_unregister.bind(notifier), CONNECT_ONE_SHOT)
	_apply()


func _unregister(notifier: VisibleOnScreenNotifier3D) -> void:
	_notifiers.erase(notifier)
	notifier.screen_entered.disconnect(_apply)
	notifier.screen_exited.disconnect(_apply)
	_apply()


func _apply() -> void:
	if not _active:
		return
	# Without any window notifier (a zone without windows) nothing is hidden.
	var should_hide := not _notifiers.is_empty() and not _notifiers.any(
			func(n: VisibleOnScreenNotifier3D) -> bool: return n.is_on_screen())
	if should_hide and _hidden.is_empty():
		for target in targets:
			if target.visible:
				target.visible = false
				_hidden.append(target)
	elif not should_hide:
		for target in _hidden:
			target.visible = true
		_hidden.clear()
