// Far-city facade: dark concrete with procedural lit windows and rare neon bands.
// Windows are placed in world space so scaled box instances get consistent
// floor heights. Per-instance variety comes from INSTANCE_CUSTOM.x (0..1 seed).
shader_type spatial;
render_mode cull_back, specular_disabled;

uniform vec3 wall_color : source_color = vec3(0.035, 0.04, 0.05);
uniform vec3 warm_light : source_color = vec3(1.0, 0.72, 0.42);
uniform vec3 cold_light : source_color = vec3(0.55, 0.8, 1.0);
uniform vec3 neon_a : source_color = vec3(1.0, 0.165, 0.427);
uniform vec3 neon_b : source_color = vec3(0.02, 0.851, 0.91);
uniform float floor_height = 3.4;
uniform float window_spacing = 2.6;
uniform float lit_fraction : hint_range(0.0, 1.0) = 0.38;
uniform float window_energy = 2.2;
uniform float neon_energy = 7.0;

varying vec3 world_pos;
varying vec3 world_normal;
varying float seed;

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	seed = INSTANCE_CUSTOM.x;
}

void fragment() {
	ALBEDO = wall_color;
	ROUGHNESS = 0.9;

	if (abs(world_normal.y) < 0.5) {
		// Horizontal coordinate along the face.
		float u = abs(world_normal.x) > 0.5 ? world_pos.z : world_pos.x;
		vec2 cell = vec2(u / window_spacing, world_pos.y / floor_height);
		vec2 id = floor(cell);
		vec2 f = fract(cell);
		// Window pane inside each cell.
		float pane = step(0.18, f.x) * step(f.x, 0.82) * step(0.25, f.y) * step(f.y, 0.8);
		float h = hash(vec3(id, seed * 97.0));
		float lit = step(1.0 - lit_fraction, h);
		vec3 tint = mix(warm_light, cold_light, step(0.72, hash(vec3(id.yx, seed * 13.0))));
		float flicker = 0.75 + 0.25 * hash(vec3(id, 5.0));
		vec3 emission = tint * pane * lit * flicker * window_energy;

		// Rare horizontal neon band on some buildings.
		float band_floor = floor(seed * 40.0) + 6.0;
		float band = step(0.6, seed) * step(abs(world_pos.y / floor_height - band_floor), 0.08);
		emission += mix(neon_a, neon_b, step(0.8, seed)) * band * neon_energy;

		EMISSION = emission;
	}
}
