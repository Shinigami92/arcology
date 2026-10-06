class_name ABViewport
extends ABSwitch
## An A/B switch for render settings of the player's viewport: MSAA samples and
## foveation (D-056). Each variant is a Dictionary of
##   "msaa": 0, 2, 4 or 8 samples,
##   "foveation_radius": the full-rate radius in percent (0 = foveation off),
##   "foveation_strength": how fast the rate drops past it;
## keys left out keep the current value. Flipped by the ABPanel with every other
## switch. Switching MSAA rebuilds the render buffers: one hitch, then the
## variant's real cost.

## Setting -> value while A is shown.
@export var a: Dictionary = {}
## Setting -> value while B is shown.
@export var b: Dictionary = {}

const MSAA_MODES := {0: Viewport.MSAA_DISABLED, 2: Viewport.MSAA_2X, 4: Viewport.MSAA_4X, 8: Viewport.MSAA_8X}


func _apply_variant() -> void:
	var values: Dictionary = a if variant == "A" else b
	if values.has("msaa"):
		var samples := int(values["msaa"])
		if MSAA_MODES.has(samples):
			get_viewport().msaa_3d = MSAA_MODES[samples]
		else:
			push_warning("ABViewport %s: msaa must be 0, 2, 4 or 8, got %d" % [name, samples])
	if values.has("foveation_radius") or values.has("foveation_strength"):
		var foveation := Foveation.find(get_tree())
		if not foveation:
			push_warning("ABViewport %s: no Foveation node" % name)
			return
		var radius: float = values.get("foveation_radius", foveation.min_radius if foveation.enabled else 0.0)
		var strength: float = values.get("foveation_strength", foveation.strength)
		foveation.set_foveation(radius > 0.0, maxf(radius, 1.0), strength)
