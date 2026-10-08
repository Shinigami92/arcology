class_name ZoneGate
extends Node
## A connection's door between two zones (D-059). [ZoneStreamer] adds one under
## each connection's door.
##
## Holds the door shut until the zones on both sides are loaded: with a
## [DoorLock] in the door, the lock holds it and its LED pulses amber (an ID
## scan, the diegetic cover for a load still running); without one, the hinge
## is pinned at closed. An open door is left alone and held once it closes.
##
## Also says whether the far side can be seen through it ([method is_open]:
## the door is open, or an eye is at its [DoorViewer]); ZoneStreamer draws a
## zone the player isn't in only then. Event-driven: no per-frame work.

## The door opened or closed, or the peephole woke or slept.
signal open_changed(open: bool)

## Past this the door counts as open.
const OPEN_ANGLE := 0.5

var streamer: ZoneStreamer
## The two zones the door connects.
var zones: Array[StringName] = []

var _lock: DoorLock
var _hinge: XRToolsInteractableHinge
var _hinge_max := 0.0
var _viewer: DoorViewer
var _holding := false
var _open := false


func _ready() -> void:
	var door := get_parent()
	var locks := door.find_children("*", "DoorLock", true, false)
	if not locks.is_empty():
		_lock = locks[0] as DoorLock
		_hinge = _lock.door
	else:
		var hinges := door.find_children("*", "XRToolsInteractableHinge", true, false)
		if not hinges.is_empty():
			_hinge = hinges[0] as XRToolsInteractableHinge
	if _hinge:
		_hinge_max = _hinge.hinge_limit_max
		_hinge.hinge_moved.connect(func(_angle: float) -> void: _on_moved())
	var viewers := door.find_children("*", "DoorViewer", true, false)
	if not viewers.is_empty():
		_viewer = viewers[0] as DoorViewer
		_viewer.awake_changed.connect(func(_awake: bool) -> void: _on_moved())
	streamer.zone_loaded.connect(_on_zones_changed)
	streamer.zone_unloading.connect(_on_zones_changed)
	_open = _is_open_now()
	_apply()


## True while the door is held for a zone that isn't loaded.
func is_holding() -> bool:
	return _holding


## True while the far side can be seen through the door (open, or an eye at the peephole).
func is_open() -> bool:
	return _open


func _on_zones_changed(_id: StringName, _root: Node3D) -> void:
	# zone_unloading fires before the zone leaves the loaded set.
	_apply.call_deferred()


func _on_moved() -> void:
	if not _lock:
		_apply()
	var open := _is_open_now()
	if open != _open:
		_open = open
		open_changed.emit(open)


func _is_open_now() -> bool:
	var door_open := _hinge != null and _hinge.hinge_position - _hinge.hinge_limit_min > OPEN_ANGLE
	return door_open or (_viewer != null and _viewer.is_awake())


func _apply() -> void:
	_holding = not zones.all(func(id: StringName) -> bool: return streamer.is_ready(id))
	if _lock:
		_lock.set_held(_holding)
	elif _hinge:
		var closed := _hinge.hinge_position - _hinge.hinge_limit_min < OPEN_ANGLE
		_hinge.hinge_limit_max = _hinge.hinge_limit_min if _holding and closed else _hinge_max
