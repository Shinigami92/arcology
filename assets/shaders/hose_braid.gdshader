shader_type spatial;
// Braided steel hose (ShowerHose, D-058): two sets of diagonal strands woven
// over and under, from the tube's UV (x around, y the length in meters). The
// weave fades to its average where it gets finer than a pixel, so the shiny
// strands don't shimmer at a distance.
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec3 base_color : source_color = vec3(0.23, 0.24, 0.26);
// Strand crossings per meter along the hose, and around it.
uniform float along = 260.0;
uniform float around = 10.0;
uniform float roughness_crown : hint_range(0.0, 1.0) = 0.3;
uniform float roughness_gap : hint_range(0.0, 1.0) = 0.65;

void fragment() {
	float a = UV.x * around;
	float l = UV.y * along;
	float p1 = a + l;
	float p2 = a - l;
	// Each strand's height across its width, and which set lies on top.
	float h1 = sin(fract(p1) * PI);
	float h2 = sin(fract(p2) * PI);
	float top = step(0.5, fract((floor(p1) + floor(p2)) * 0.5));
	float h = mix(h1, h2, top);
	float detail = clamp(1.5 - fwidth(l) * 1.5, 0.0, 1.0);
	h = mix(0.6, h, detail);
	ALBEDO = base_color * (0.55 + 0.45 * h);
	METALLIC = 1.0;
	ROUGHNESS = mix(roughness_gap, roughness_crown, h);
	AO = mix(1.0, 0.6 + 0.4 * h, detail);
}
