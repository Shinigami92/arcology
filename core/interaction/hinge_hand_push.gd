class_name HingeHandPush
extends Node
## Lets bare hands move an open [XRToolsInteractableHinge] (a door, D-058): a
## palm pressing into either face pushes the leaf away, and [member edge_handle]
## follows the nearest hand along the leaf's free edge so the edge can be
## grabbed anywhere to pull it. Both only while the hinge isn't closed: a
## closed door opens by its handle (the latch holds it).
##
## The hand is the avatar's (D-041): its palm, knuckles and finger bones, each
## with its thickness ([constant HAND_BONES]), where the controller wants them,
## not where they are: the visible hand follows the collision hand, and the
## leaf (static geometry) stops that one. The leaf turns until no bone sinks
## into its face, so a push with the fingertips moves it as soon as they touch.
## Without an avatar, the collision hand's palm stands in.
## A shove hands its speed to [member swing], so the door swings on.
##
## An Area3D around the hinge's sweep (built at start) wakes this up only
## while a collision hand is near.

## Hinge axis = the hinge's local X; closed = [member XRToolsInteractableHinge.hinge_limit_min].
@export var hinge: XRToolsInteractableHinge
## The leaf body (a [KinematicFollower]): its box shapes give the faces and edges.
@export var leaf: CollisionObject3D
## Gets the push speed when a shove ends (optional).
@export var swing: HingeSwing
## Grabbable along the free edge while open (optional): its HandleOrigin slides
## along the hinge axis to the hand.
@export var edge_handle: XRToolsInteractableHandle
## Half the palm's thickness when there's no avatar hand (only the palm point).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var palm_radius := 0.03
## Margin around the leaf's sweep in which hands are tracked.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var reach := 0.25
## Within this of closed the hinge counts as closed (no push, no edge grab).
@export_custom(PROPERTY_HINT_NONE, "suffix:°") var closed_angle := 0.5
## How far the edge handle stays from the leaf's ends along the axis.
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var edge_inset := 0.12

## Avatar hand bones (without the "Left"/"Right" prefix) and their radius (m).
const HAND_BONES := {
	&"Palm": 0.016, &"Hand": 0.02,
	&"ThumbProximal": 0.011, &"ThumbDistal": 0.009, &"ThumbTip": 0.008,
	&"IndexProximal": 0.01, &"IndexIntermediate": 0.009, &"IndexDistal": 0.008, &"IndexTip": 0.007,
	&"MiddleProximal": 0.01, &"MiddleIntermediate": 0.009, &"MiddleDistal": 0.008, &"MiddleTip": 0.007,
	&"RingProximal": 0.01, &"RingIntermediate": 0.009, &"RingDistal": 0.008, &"RingTip": 0.007,
	&"LittleProximal": 0.009, &"LittleIntermediate": 0.008, &"LittleDistal": 0.007, &"LittleTip": 0.006,
}

# The leaf's box shapes as one AABB in the leaf frame (the Leaf node's frame).
var _bounds := AABB()
# Leaf frame -> hinge frame at angle 0, and its inverse.
var _leaf_in_hinge := Transform3D.IDENTITY
var _hinge_in_leaf := Transform3D.IDENTITY
# The hinge axis in the leaf frame (unit).
var _axis := Vector3.UP
# Hands in reach -> which face they're on (+1 = +Z face, -1 = -Z face).
var _hands: Dictionary[XRToolsCollisionHand, int] = {}
var _velocity := 0.0
var _edge_origin: Node3D
# The edge handle's travel along the axis (leaf frame).
var _edge_lo := 0.0
var _edge_hi := 0.0
# Collision hand -> [skeleton, hand target, hand bone, PackedInt32Array bones, PackedFloat32Array radii]
# (empty: no avatar).
var _bones: Dictionary[XRToolsCollisionHand, Array] = {}
var _area: Area3D
var _points := PackedVector3Array()
var _radii := PackedFloat32Array()


func _ready() -> void:
	if not hinge or not leaf:
		push_error("HingeHandPush needs hinge and leaf: %s" % get_path())
		return
	var leaf_node := leaf as Node3D
	if leaf is KinematicFollower:
		leaf_node = (leaf as KinematicFollower).follow
		if not leaf_node:
			leaf_node = leaf.get_parent() as Node3D
	# The Leaf node turns with the hinge: its transform in the hinge's own frame is fixed.
	_leaf_in_hinge = hinge.global_transform.affine_inverse() * leaf_node.global_transform
	_hinge_in_leaf = _leaf_in_hinge.affine_inverse()
	_axis = (_hinge_in_leaf.basis * Vector3.RIGHT).normalized()
	var first := true
	for child in leaf.get_children():
		var shape := child as CollisionShape3D
		if not shape or not shape.shape is BoxShape3D:
			continue
		var size := (shape.shape as BoxShape3D).size
		var box := shape.transform * AABB(-size / 2.0, size)
		_bounds = box if first else _bounds.merge(box)
		first = false
	if edge_handle:
		_edge_origin = edge_handle.get_parent() as Node3D
		_edge_lo = INF
		_edge_hi = -INF
		for i in 8:
			var along := _bounds.get_endpoint(i).dot(_axis)
			_edge_lo = minf(_edge_lo, along + edge_inset)
			_edge_hi = maxf(_edge_hi, along - edge_inset)
	_build_area()
	hinge.hinge_moved.connect(_on_hinge_moved)
	_on_hinge_moved(hinge.hinge_position)
	set_physics_process(false)


func is_closed() -> bool:
	return hinge.hinge_position - hinge.hinge_limit_min < closed_angle


## An Area3D (Player Hands) around the hinge axis covering the leaf's sweep,
## in the hinge's parent (it doesn't turn with the leaf).
func _build_area() -> void:
	var radius := 0.0
	var lo := INF
	var hi := -INF
	for i in 8:
		var corner := _leaf_in_hinge * _bounds.get_endpoint(i)
		radius = maxf(radius, Vector2(corner.y, corner.z).length())
		lo = minf(lo, corner.x)
		hi = maxf(hi, corner.x)
	var cylinder := CylinderShape3D.new()
	cylinder.radius = radius + reach
	cylinder.height = hi - lo + 2.0 * reach
	var shape := CollisionShape3D.new()
	shape.shape = cylinder
	# The cylinder's axis is its Y; the hinge axis is X.
	shape.transform = Transform3D(Basis(Vector3.FORWARD, PI / 2.0), hinge.position + Vector3((lo + hi) / 2.0, 0, 0))
	_area = Area3D.new()
	_area.name = "HandPushArea"
	_area.collision_layer = 0
	_area.collision_mask = 1 << 17  # 18 Player Hands
	_area.monitorable = false
	_area.add_child(shape)
	_area.body_entered.connect(_on_body_entered)
	_area.body_exited.connect(_on_body_exited)
	hinge.get_parent().add_child.call_deferred(_area)


func _on_body_entered(body: Node3D) -> void:
	var hand := body as XRToolsCollisionHand
	if not hand:
		return
	_hands[hand] = 0
	if not _bones.has(hand):
		_bones[hand] = _find_bones(hand)
	set_physics_process(true)


func _on_body_exited(body: Node3D) -> void:
	var hand := body as XRToolsCollisionHand
	if not hand:
		return
	_hands.erase(hand)
	if _hands.is_empty():
		set_physics_process(false)


func _on_hinge_moved(_angle: float) -> void:
	if edge_handle:
		var open := not is_closed()
		if edge_handle.enabled != open and not edge_handle.is_picked_up():
			edge_handle.enabled = open


## The avatar skeleton's bones of `hand`'s side (see [constant HAND_BONES]).
func _find_bones(hand: XRToolsCollisionHand) -> Array:
	var avatar_hand: AvatarHand
	for child in hand.get_children():
		if child is AvatarHand:
			avatar_hand = child
	var body := get_tree().get_first_node_in_group(&"avatar_body")
	if not avatar_hand or not body:
		return []
	var found := body.find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		return []
	var skeleton := found[0] as Skeleton3D
	var hand_bone := skeleton.find_bone(avatar_hand.side + "Hand")
	if hand_bone < 0 or not avatar_hand.target:
		return []
	var indices := PackedInt32Array()
	var radii := PackedFloat32Array()
	for bone: StringName in HAND_BONES:
		var i := skeleton.find_bone(avatar_hand.side + bone)
		if i >= 0:
			indices.append(i)
			radii.append(HAND_BONES[bone])
	return [skeleton, avatar_hand.target, hand_bone, indices, radii]


## Where the controller wants `hand`'s avatar bones (world), into `points`,
## their radii into `radii`; the palm target alone without an avatar.
func hand_points(hand: XRToolsCollisionHand, points: PackedVector3Array, radii: PackedFloat32Array) -> void:
	points.clear()
	radii.clear()
	var bones: Array = _bones.get(hand, [])
	var controller := hand.get_parent() as Node3D
	if bones.is_empty() or not controller:
		points.append(palm_target(hand))
		radii.append(palm_radius)
		return
	var skeleton: Skeleton3D = bones[0]
	var target: Node3D = bones[1]
	var indices: PackedInt32Array = bones[3]
	# The fingers as posed, relative to the hand bone, put where the hand bone
	# goes (its target rides the collision hand), moved to where the controller is.
	var wrist := skeleton.get_bone_global_pose(bones[2]).affine_inverse()
	var to_wanted := controller.global_transform * hand.global_transform.affine_inverse() \
			* target.global_transform * wrist
	for k in indices.size():
		points.append(to_wanted * skeleton.get_bone_global_pose(indices[k]).origin)
	radii.append_array(bones[4])


## Where the controller wants the hand's palm (world).
static func palm_target(hand: XRToolsCollisionHand) -> Vector3:
	var controller := hand.get_parent() as Node3D
	var palm := hand.get_node_or_null("Palm") as Node3D
	var offset := palm.transform.origin if palm else Vector3(0, -0.05, 0.11)
	return controller.global_transform * offset if controller else hand.global_position


## A hinge-frame point (the hinge's parent at the hinge's place, angle 0) in
## the leaf frame with the hinge at `angle` (radians).
func _to_leaf(q: Vector3, angle: float) -> Vector3:
	return _hinge_in_leaf * (Basis(Vector3.RIGHT, -angle) * q)


func _physics_process(delta: float) -> void:
	var held := not hinge.grabbed_handles.is_empty()
	# World -> the hinge's frame at angle 0 (its parent, moved to the hinge).
	var parent := hinge.get_parent() as Node3D
	var to_hinge := Transform3D(Basis.IDENTITY, -hinge.position) * parent.global_transform.affine_inverse()
	var angle := deg_to_rad(hinge.hinge_position)
	var closed := is_closed()
	var pushed := false
	var start := hinge.hinge_position
	var edge_best := INF
	var edge_at := 0.0
	for hand: XRToolsCollisionHand in _hands.keys():
		var p := _to_leaf(to_hinge * palm_target(hand), angle)
		hand_points(hand, _points, _radii)
		var side: int = _hands[hand]
		var best := NAN
		var touching := false
		for k in _points.size():
			var q := to_hinge * _points[k]
			var b := _to_leaf(q, angle)
			if b.x <= _bounds.position.x or b.x >= _bounds.end.x or b.y <= _bounds.position.y or b.y >= _bounds.end.y:
				continue
			var front := _bounds.end.z + _radii[k]
			var back := _bounds.position.z - _radii[k]
			# Into the face on the hand's side (not reaching around the far one).
			var into := (b.z < front and b.z > back - 0.1) if side > 0 else (b.z > back and b.z < front + 0.1)
			if side == 0 or not into:
				continue
			touching = true
			if held or closed:
				continue
			var solved := _solve(q, front if side > 0 else back, angle)
			if is_nan(solved):
				continue
			# The bone that needs the leaf furthest away wins.
			if is_nan(best) or (solved < best if side > 0 else solved > best):
				best = solved
		if not touching:
			# Not touching: remember which side the palm is on.
			_hands[hand] = 1 if p.z > _bounds.get_center().z else -1
		elif not is_nan(best):
			hinge.move_hinge(best)
			angle = deg_to_rad(hinge.hinge_position)
			pushed = true
		if _edge_origin and p.y > _bounds.position.y and p.y < _bounds.end.y:
			var distance := Vector2(p.x - _edge_origin.position.x, p.z - _edge_origin.position.z).length()
			if distance < edge_best:
				edge_best = distance
				edge_at = p.dot(_axis)
	if pushed:
		var v := (hinge.hinge_position - start) / delta
		_velocity = lerpf(_velocity, v, 0.5)
		if swing:
			swing.coast(_velocity)
	else:
		_velocity = 0.0
	if _edge_origin and edge_best < INF and not edge_handle.is_picked_up():
		var now := _edge_origin.position.dot(_axis)
		_edge_origin.position += _axis * (clampf(edge_at, _edge_lo, _edge_hi) - now)


## The hinge angle (radians) nearest `current` at which the hinge-frame point
## `q` lies on the leaf-frame plane z = `target`; NAN if none.
func _solve(q: Vector3, target: float, current: float) -> float:
	# Leaf z of q at angle t: a + b cos t + c sin t (the hinge turns about X).
	var row := Vector3(_hinge_in_leaf.basis.x.z, _hinge_in_leaf.basis.y.z, _hinge_in_leaf.basis.z.z)
	var a := row.x * q.x + _hinge_in_leaf.origin.z
	var b := row.y * q.y + row.z * q.z
	var c := row.y * q.z - row.z * q.y
	var r := Vector2(b, c).length()
	var k := target - a
	if r < 1e-4 or absf(k) > r:
		return NAN
	var phase := atan2(c, b)
	var spread := acos(k / r)
	var best := NAN
	for t: float in [phase + spread, phase - spread]:
		var wrapped := current + wrapf(t - current, -PI, PI)
		if is_nan(best) or absf(wrapped - current) < absf(best - current):
			best = wrapped
	return best
