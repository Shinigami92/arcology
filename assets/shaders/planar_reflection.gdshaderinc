// Live planar reflection (D-049): what a PlanarReflection node renders for its
// surface, one texture per eye. The node sets these uniforms on the materials it
// feeds; reflection_enabled is 0 while it isn't rendering (surface out of view),
// so the material falls back to the room's ReflectionProbe then.
//
// Each texture covers exactly the node's rectangle (its frustum is clipped at
// the surface), mirrored: the left edge of the texture is the rectangle's right
// edge. The textures are linear HDR (the reflection renders with a linear tone
// mapper and no glow), so write them to EMISSION: the main pass tone maps once.

uniform sampler2D reflection_left : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D reflection_right : hint_default_black, filter_linear, repeat_disable;
uniform float reflection_enabled = 0.0;
// The rectangle in world space: center, right / width, up / height, and its normal.
uniform vec3 reflection_origin = vec3(0.0);
uniform vec3 reflection_u = vec3(1.0, 0.0, 0.0);
uniform vec3 reflection_v = vec3(0.0, 1.0, 0.0);
uniform vec3 reflection_normal = vec3(0.0, 0.0, 1.0);

// The reflected scene at world_pos, for the eye that is rendering (VIEW_INDEX:
// built-ins aren't visible in helper functions, so the caller passes it).
vec3 planar_reflection(vec3 world_pos, int view_index) {
	vec3 d = world_pos - reflection_origin;
	vec2 uv = vec2(0.5 - dot(d, reflection_u), 0.5 - dot(d, reflection_v));
	if (view_index == 1) {
		return texture(reflection_right, uv).rgb;
	}
	return texture(reflection_left, uv).rgb;
}
