class_name AvatarSprings
extends SpringBoneSimulator3D
## Spring bones for the avatar's coat skirt and belt items (D-044). Runs after
## BodyIK (a later child of the skeleton), so the chains hang from the posed
## hips. Their inertia is relative to the player's XROrigin, which stick
## locomotion and turning move but never tilt: real body movement, stepping
## and the leg colliders swing them, and walking adds an air drag against the
## body's velocity ([member air_drag]), so the hem trails a little instead of
## streaming like a cape (world inertia did that; hip-relative inertia pulled
## gravity along the tilted hips). Chains the glb doesn't have are skipped.
##
## Colliders, created here and following their bones: a capsule per thigh and
## shin pushes the skirt off the legs; a fuller capsule on the right thigh (the
## trousers' surface, ~9.5 cm) keeps the dangling belt items out of it, and
## only they use it; a seat plane at cushion height, active only while seated,
## keeps the skirt's sides and back on the seat (the front panels hang past
## the knees, so they ignore it).

## One row per chain: root bone, end bone, tail length past the end bone (m),
## collision radius (m), stiffness, drag, gravity, coat (true: leg capsules and
## the seat plane; false: belt item: leg capsules and the belt thigh capsule).
const CHAINS := [
	["CoatFrontLeft1", "CoatFrontLeft4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["CoatFrontRight1", "CoatFrontRight4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["CoatSideLeft1", "CoatSideLeft4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["CoatSideRight1", "CoatSideRight4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["CoatBackLeft1", "CoatBackLeft4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["CoatBackRight1", "CoatBackRight4", 0.35, 0.03, 0.8, 0.5, 0.4, true],
	["BeltCuffs1", "BeltCuffs2", 0.07, 0.015, 0.5, 0.3, 0.5, false],
	["BeltPasskey1", "BeltPasskey1", 0.09, 0.013, 0.6, 0.3, 0.5, false],
]
## Leg colliders: bone, capsule radius (m).
const LEGS := [
	["LeftUpperLeg", 0.07], ["LeftLowerLeg", 0.055],
	["RightUpperLeg", 0.07], ["RightLowerLeg", 0.055],
]
## Air drag on the chains per m/s of the body's horizontal velocity.
@export var air_drag := 0.08

## The belt items' thigh capsule: bone and radius (m).
const BELT_THIGH := ["RightUpperLeg", 0.095]
## Coat chains that hang past the knees when seated, so ignore the seat plane.
const FRONT_CHAINS := ["CoatFrontLeft1", "CoatFrontRight1"]
## The seat plane's height below the hip joint while seated (m): the cushion.
const SEAT_BELOW_HIPS := 0.08
## Where the seat plane waits while standing (m below the hips): out of reach.
const SEAT_AWAY := 100.0

var _seat: SpringBoneCollisionPlane3D
var _belt_thigh: SpringBoneCollisionCapsule3D
var _ik: BodyIK
var _hips_rest_basis := Basis.IDENTITY


func _ready() -> void:
	var skeleton := get_skeleton()
	if not skeleton:
		return
	_ik = skeleton.get_node_or_null("BodyIK") as BodyIK
	var origin: Node = get_parent()
	while origin and not origin is XROrigin3D:
		origin = origin.get_parent()
	for leg: Array in LEGS:
		var bone := skeleton.find_bone(leg[0])
		var child := skeleton.find_bone(leg[0].replace("Upper", "Lower") if "Upper" in leg[0] else leg[0].replace("LowerLeg", "Foot"))
		if bone < 0 or child < 0:
			continue
		var length := skeleton.get_bone_rest(child).origin.length()
		var capsule := SpringBoneCollisionCapsule3D.new()
		capsule.name = "%sCollider" % leg[0]
		capsule.bone_name = leg[0]
		capsule.radius = leg[1]
		capsule.height = length + 2.0 * float(leg[1])
		capsule.position_offset = Vector3(0.0, length * 0.5, 0.0)
		add_child(capsule)
	var thigh := skeleton.find_bone(BELT_THIGH[0])
	var knee := skeleton.find_bone(BELT_THIGH[0].replace("Upper", "Lower"))
	if thigh >= 0 and knee >= 0:
		var length := skeleton.get_bone_rest(knee).origin.length()
		_belt_thigh = SpringBoneCollisionCapsule3D.new()
		_belt_thigh.name = "BeltThighCollider"
		_belt_thigh.bone_name = BELT_THIGH[0]
		_belt_thigh.radius = BELT_THIGH[1]
		_belt_thigh.height = length + 2.0 * float(BELT_THIGH[1])
		_belt_thigh.position_offset = Vector3(0.0, length * 0.5, 0.0)
		add_child(_belt_thigh)
	var hips := skeleton.find_bone("Hips")
	if hips >= 0:
		_hips_rest_basis = skeleton.get_bone_global_rest(hips).basis.orthonormalized()
		_seat = SpringBoneCollisionPlane3D.new()
		_seat.name = "SeatCollider"
		_seat.bone_name = "Hips"
		# The plane's normal is its local +Y: make it the skeleton's up.
		_seat.rotation_offset = Quaternion(Vector3.UP, _hips_rest_basis.inverse() * Vector3.UP)
		add_child(_seat)
		set_seated(false)

	var rows: Array = []
	for chain: Array in CHAINS:
		if skeleton.find_bone(chain[0]) >= 0 and skeleton.find_bone(chain[1]) >= 0:
			rows.append(chain)
	setting_count = rows.size()
	for i in rows.size():
		var chain: Array = rows[i]
		set_root_bone_name(i, chain[0])
		set_end_bone_name(i, chain[1])
		set_extend_end_bone(i, true)
		set_end_bone_direction(i, BONE_DIRECTION_FROM_PARENT if chain[0] != chain[1] else BONE_DIRECTION_PLUS_Y)
		set_end_bone_length(i, chain[2])
		if origin:
			set_center_from(i, CENTER_FROM_NODE)
			set_center_node(i, get_path_to(origin))
		else:
			set_center_from(i, CENTER_FROM_WORLD_ORIGIN)
		set_radius(i, chain[3])
		set_stiffness(i, chain[4])
		set_drag(i, chain[5])
		set_gravity(i, chain[6])
		set_gravity_direction(i, Vector3.DOWN)
		set_enable_all_child_collisions(i, true)
		var excluded: Array[Node] = []
		for node: Node in ([_belt_thigh, _seat if FRONT_CHAINS.has(chain[0]) else null] if chain[7] else [_seat]):
			if node:
				excluded.append(node)
		set_exclude_collision_count(i, excluded.size())
		for j in excluded.size():
			set_exclude_collision_path(i, j, NodePath(excluded[j].name))


func _process(_delta: float) -> void:
	if _ik:
		var velocity := _ik.velocity()
		external_force = Vector3(-velocity.x, 0.0, -velocity.z) * air_drag


## Moves the seat plane to cushion height (seated) or out of reach.
func set_seated(seated: bool) -> void:
	if _seat:
		var below := SEAT_BELOW_HIPS if seated else SEAT_AWAY
		_seat.position_offset = _hips_rest_basis.inverse() * (Vector3.DOWN * below)
