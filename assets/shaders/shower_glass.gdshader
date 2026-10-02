shader_type spatial;
// Frameless shower screen: one clear, low-iron pane seen from both sides. The window
// glass approach (window_glass.gdshaderinc) without its HUD, tint, smudges and rain:
// premultiplied alpha keeps the reflections (the room's ReflectionProbe) at full
// strength on an almost clear pane, and ALPHA only says how much of the view behind
// is taken away. One transparent layer, no screen read: cheap.
render_mode blend_premul_alpha, cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

// Low-iron glass: barely tinted; the edge strip is opaque in the body texture.
uniform vec3 glass_color : source_color = vec3(0.86, 0.92, 0.91);
// Share of the view behind the clear pane takes away.
uniform float clear_alpha : hint_range(0.0, 0.3) = 0.04;
// Specular level (0.5 = F0 0.04, real glass); a little more reads better in VR.
uniform float reflectivity : hint_range(0.0, 1.0) = 0.6;
uniform float roughness : hint_range(0.0, 0.5) = 0.02;
// Glancing angles look more reflective and a little greener (the pane's thickness).
uniform float edge_alpha : hint_range(0.0, 1.0) = 0.25;

void fragment() {
	float facing = clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0);
	float coverage = clamp(clear_alpha + edge_alpha * pow(1.0 - facing, 4.0), 0.0, 1.0);
	ALBEDO = glass_color * coverage;
	ALPHA = coverage;
	METALLIC = 0.0;
	ROUGHNESS = roughness;
	SPECULAR = reflectivity;
}
