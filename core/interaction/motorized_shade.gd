class_name MotorizedShade
extends Node
## A motorized roller shade, or several moved together (one per window bay),
## run by a physical [member button]: a press starts it, a press while it runs
## stops it, and the next press sends it back the other way. The motor eases
## in and out, hums while it moves, and the node idles otherwise.
##
## Each shade in [member shades] is a Node3D at its head slot (where the bar
## hangs when the shade is up) with two children: "Bar" (origin at its top
## center, moved down by up to its drop) and "Fabric" (a MeshInstance3D with a
## 1 x 1 m QuadMesh, scaled in Y to fill the space between the head slot and
## the bar). The fabric's StandardMaterial3D is copied per shade and its UVs
## follow the drop, so the weave doesn't stretch and moves with the bar
## (1 texture tile per meter).

## Emitted while moving: 0 = up (open), 1 = down (closed).
signal moved(closure: float)

@export var button: XRToolsInteractableAreaButton
@export var shades: Array[Node3D] = []
## Travel from the head slot to the sill, per shade (m).
@export var drops: PackedFloat32Array = []
## Time for a full run (s), ramps included.
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var travel_time := 6.0
## Time the motor takes to reach full speed or to stop (s).
@export_custom(PROPERTY_HINT_NONE, "suffix:s") var ramp_time := 0.6
## Start position: 0 = up, 1 = down.
@export_range(0.0, 1.0) var closure := 0.0
@export var motor: AudioStreamPlayer3D
@export var click: AudioStreamPlayer3D

const _MIN_FABRIC := 0.002

var _velocity := 0.0          # closure per second
var _direction := 0           # -1 up, +1 down, 0 stopping or stopped
var _last_direction := -1
var _bars: Array[Node3D] = []
var _fabrics: Array[MeshInstance3D] = []
var _materials: Array[StandardMaterial3D] = []
var _motor_db := 0.0


func _ready() -> void:
	if not button or shades.is_empty() or drops.size() != shades.size():
		push_error("MotorizedShade needs a button and one drop per shade: %s" % get_path())
		return
	for shade in shades:
		_bars.append(shade.get_node("Bar") as Node3D)
		var fabric := shade.get_node("Fabric") as MeshInstance3D
		_fabrics.append(fabric)
		var mat := fabric.get_active_material(0) as StandardMaterial3D
		if mat:
			mat = mat.duplicate() as StandardMaterial3D
			fabric.material_override = mat
			var quad := fabric.mesh as QuadMesh
			mat.uv1_scale.x = quad.size.x if quad else 1.0
		_materials.append(mat)
	if motor:
		_motor_db = motor.volume_db
	button.button_pressed.connect(_on_pressed)
	_last_direction = 1 if closure >= 0.5 else -1
	_apply()
	set_process(false)


## 0 = up (open), 1 = down (closed).
func get_closure() -> float:
	return closure


func is_moving() -> bool:
	return is_processing()


## Jumps to a position (0 = up, 1 = down) without running the motor.
func set_closure(value: float) -> void:
	closure = clampf(value, 0.0, 1.0)
	_velocity = 0.0
	_direction = 0
	set_process(false)
	_apply()
	moved.emit(closure)


## What a press does: stop while running, else run the other way (up from
## the bottom, down from the top).
func toggle() -> void:
	if _direction != 0:
		_direction = 0
	else:
		if closure >= 1.0:
			_direction = -1
		elif closure <= 0.0:
			_direction = 1
		else:
			_direction = -_last_direction
		_last_direction = _direction
		if motor and not motor.playing:
			motor.play()
		set_process(true)
	if click:
		click.play()


func _on_pressed(_button: XRToolsInteractableAreaButton) -> void:
	toggle()


func _process(delta: float) -> void:
	var v_max := 1.0 / maxf(travel_time - ramp_time, 0.1)
	var accel := v_max / maxf(ramp_time, 0.01)
	var target := 0.0
	if _direction != 0:
		var remaining := (1.0 - closure) if _direction > 0 else closure
		# Brake so it arrives at the end at rest.
		target = _direction * minf(v_max, sqrt(2.0 * accel * remaining) + accel * delta)
	_velocity = move_toward(_velocity, target, accel * delta)
	closure += _velocity * delta
	if closure >= 1.0 or closure <= 0.0:
		closure = clampf(closure, 0.0, 1.0)
		_velocity = 0.0
		_direction = 0
	_apply()
	moved.emit(closure)
	if motor:
		var speed := absf(_velocity) / v_max
		motor.volume_db = _motor_db + linear_to_db(clampf(speed, 0.05, 1.0))
		motor.pitch_scale = 0.85 + 0.15 * speed
	if _direction == 0 and _velocity == 0.0:
		if motor:
			motor.stop()
		set_process(false)


func _apply() -> void:
	for i in _bars.size():
		var h := drops[i] * closure
		_bars[i].position.y = -h
		var fabric := _fabrics[i]
		fabric.visible = h > _MIN_FABRIC
		if fabric.visible:
			fabric.position.y = -h * 0.5
			fabric.scale.y = h
			var mat := _materials[i]
			if mat:
				# One tile per meter, anchored at the bar: the weave moves down with it.
				mat.uv1_scale.y = h
				mat.uv1_offset.y = -h
