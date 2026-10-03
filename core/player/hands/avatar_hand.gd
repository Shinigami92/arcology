@tool
class_name AvatarHand
extends XRToolsHand
## XRToolsHand for the avatar's rigged hands (D-037). XR Tools swaps its own
## hand animations into the blend tree (default_pose, pose overrides), whose
## tracks use the XR Tools bone names; without a default_pose this hand keeps
## the animations its blend tree names (the model's "Open" and "Grip"), so the
## grip and trigger drive the avatar's bones. XR Tools pose areas (per-object
## grab poses) would still swap in XR Tools animations: not used yet.
##
## Scene layout (written by tools/player/avatar_hands.gd): the first child is
## an Offset node that XR Tools moves to the controller's palm offset; the glb
## model sits under it, fitted onto where the XR Tools hand used to be.


func _update_pose() -> void:
	if default_pose == null and _pose_overrides.is_empty():
		return
	super()
