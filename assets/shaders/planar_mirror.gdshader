shader_type spatial;
// Mirror with a live reflection (D-049), fed by a PlanarReflection node. While
// that isn't rendering (mirror out of view), it's a polished metal surface that
// reflects the room's ReflectionProbe, like the old mirror material.
render_mode diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/planar_reflection.gdshaderinc"

// Silvered glass: reflects about 90 %, very slightly cool.
uniform float reflectance : hint_range(0.0, 1.0) = 0.9;
uniform vec3 mirror_tint : source_color = vec3(0.96, 0.98, 1.0);
// Fallback look (probe reflection): metal albedo and roughness.
uniform vec3 fallback_albedo : source_color = vec3(0.85, 0.87, 0.9);
uniform float fallback_roughness : hint_range(0.0, 1.0) = 0.03;

void fragment() {
	float live = clamp(reflection_enabled, 0.0, 1.0);
	vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	ALBEDO = fallback_albedo * (1.0 - live);
	METALLIC = 1.0;
	ROUGHNESS = fallback_roughness;
	EMISSION = live > 0.0 ? planar_reflection(world_pos, VIEW_INDEX) * mirror_tint * reflectance * live : vec3(0.0);
}
