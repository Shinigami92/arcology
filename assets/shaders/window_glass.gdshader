shader_type spatial;
// Window glass (D-033): one transparent layer per pane, nearly clear, with
// reflections (the room's ReflectionProbe at night), low-frequency smudges,
// smart-glass tint and an optional HUD readout. Style guide: a single pane,
// no stacked transparent layers.
//
// Premultiplied alpha: ALBEDO is premultiplied by the coverage here, so
// reflections (specular) and the HUD (emission) stay at full strength on an
// almost clear pane, and ALPHA only says how much of the view behind is kept.
// Expects a QuadMesh (local XY plane, meters, centered): the HUD and the
// smudges are laid out in the pane's own meters.
render_mode blend_premul_alpha, cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

// ---- glass
uniform vec3 glass_color : source_color = vec3(0.78, 0.85, 0.9);
// Share of the view behind that the clear glass takes away (dust, absorption).
uniform float clear_alpha : hint_range(0.0, 0.3) = 0.035;
// Specular level (0.5 = F0 0.04, real float glass); a little more reads better in VR.
uniform float reflectivity : hint_range(0.0, 1.0) = 0.6;
uniform float roughness : hint_range(0.0, 0.5) = 0.025;

// ---- smudges: large, soft wipes only (no high-frequency noise: it shimmers in stereo)
uniform float smudge_amount : hint_range(0.0, 1.0) = 0.5;
uniform float smudge_scale = 1.6;  // features per meter (about 0.3-0.6 m blobs)

// ---- smart glass (electrochromic)
// 0 = clear, 1 = fully tinted. Driven by SmartGlass.
uniform float tint : hint_range(0.0, 1.0) = 0.0;
uniform vec3 tint_color : source_color = vec3(0.1, 0.13, 0.17);
// Coverage at tint 1 (0.96 keeps 4% of the view behind, like dark electrochromic glass).
uniform float tint_alpha : hint_range(0.0, 1.0) = 0.96;
// Faint cool glow of the tinted layer (city light coming through it).
uniform float tint_glow : hint_range(0.0, 0.2) = 0.1;
uniform float tint_reflectivity : hint_range(0.0, 1.0) = 0.25;

// ---- rain (reserved; the rain-on-glass step fills rain() in)
uniform float rain_amount : hint_range(0.0, 1.0) = 0.0;

// ---- HUD readout, driven by WindowHud. Shown on panes with hud_enabled.
instance uniform bool hud_enabled = false;
// Lower right corner of the readout in the pane's local meters (+X = right seen from the room).
instance uniform vec2 hud_anchor = vec2(0.0);
uniform vec3 hud_color : source_color = vec3(0.02, 0.85, 0.91);
uniform float hud_energy = 1.6;
uniform float hud_height = 0.075;  // time digits (m); the second line is 0.8 of that
// Hours and minutes as digits (h1, h2, m1, m2), -1 = blank.
uniform ivec4 hud_time = ivec4(1, 2, 0, 0);
uniform int hud_temperature = 14;  // °C, -99..99
uniform int hud_weather = 1;       // 0 clear night, 1 cloudy, 2 rain

varying vec2 v_local;
varying float v_seed;

// 7-segment bits: a (top), b (top right), c (bottom right), d (bottom), e (bottom left), f (top left), g (middle).
const int SEGMENTS[10] = { 63, 6, 91, 79, 102, 109, 125, 7, 127, 111 };
const int SEG_MINUS = 64;
const float DIGIT_W = 0.5;      // in digit heights
const float DIGIT_ADV = 0.74;
const float STROKE = 0.11;      // stroke width in digit heights
const float SLANT = 0.08;
// The glow around the glyphs fades out within this distance (m); shapes are evaluated that far out.
const float HALO = 0.025;

void vertex() {
	v_local = VERTEX.xy;
	v_seed = dot(MODEL_MATRIX[3].xyz, vec3(1.7, 0.3, 2.9));
}

// ---------------------------------------------------------------- noise
float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 0..1, mostly 0 with a few soft wipes and a hazier band low on the pane (hands, cleaning).
float smudges(vec2 p, float seed) {
	vec2 q = p * smudge_scale + vec2(seed, seed * 0.37);
	float n = value_noise(q) * 0.65 + value_noise(q * 2.3 + 7.1) * 0.35;
	float wipe = smoothstep(0.55, 0.85, n);
	float low = smoothstep(0.6, -0.4, p.y) * 0.35 * value_noise(q * 0.7 + 3.0);
	return clamp(wipe + low, 0.0, 1.0);
}

// ---------------------------------------------------------------- rain (reserved)
// The rain step adds drops and streaks here: `wet` raises the haze, `normal`
// tilts the reflection per drop, and `offset` will shift a screen-texture read
// for the refraction through each drop (the only screen read the pane will need).
struct Rain {
	float wet;
	vec3 normal;
	vec2 offset;
};

Rain rain(vec2 p, float amount) {
	Rain r;
	r.wet = amount * 0.3;
	r.normal = vec3(0.0, 0.0, 1.0);
	r.offset = vec2(0.0);
	return r;
}

// ---------------------------------------------------------------- HUD shapes (units: meters)
float sd_segment(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

float sd_round_box(vec2 p, vec2 half_size, float r) {
	vec2 d = abs(p) - half_size + r;
	return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}

// Distance to the stroke centerlines of a 7-segment glyph (bits), p in digit heights, centered.
float sd_seven(vec2 p, int bits) {
	p.x -= p.y * SLANT;
	float w = DIGIT_W * 0.5;
	float g = 0.07;
	float d = 1e5;
	if ((bits & 1) != 0) d = min(d, sd_segment(p, vec2(-w + g, 0.5), vec2(w - g, 0.5)));
	if ((bits & 2) != 0) d = min(d, sd_segment(p, vec2(w, 0.5 - g), vec2(w, g)));
	if ((bits & 4) != 0) d = min(d, sd_segment(p, vec2(w, -g), vec2(w, -0.5 + g)));
	if ((bits & 8) != 0) d = min(d, sd_segment(p, vec2(-w + g, -0.5), vec2(w - g, -0.5)));
	if ((bits & 16) != 0) d = min(d, sd_segment(p, vec2(-w, -g), vec2(-w, -0.5 + g)));
	if ((bits & 32) != 0) d = min(d, sd_segment(p, vec2(-w, 0.5 - g), vec2(-w, g)));
	if ((bits & 64) != 0) d = min(d, sd_segment(p, vec2(-w + g, 0.0), vec2(w - g, 0.0)));
	return d - STROKE * 0.5;
}

float sd_digit(vec2 p, int digit) {
	if (digit < 0 || digit > 9) {
		return 1e5;
	}
	return sd_seven(p, SEGMENTS[digit]);
}

float sd_cloud(vec2 p) {
	float d = length(p - vec2(-0.2, -0.04)) - 0.19;
	d = min(d, length(p - vec2(0.04, 0.08)) - 0.25);
	d = min(d, length(p - vec2(0.26, -0.06)) - 0.17);
	d = min(d, sd_round_box(p - vec2(0.03, -0.15), vec2(0.36, 0.08), 0.08));
	return d;
}

// Filled weather glyph, p in glyph heights, centered.
float sd_weather(vec2 p, int kind) {
	if (kind == 0) {
		// Crescent moon.
		float outer = length(p) - 0.38;
		float inner = length(p - vec2(0.2, 0.14)) - 0.32;
		return max(outer, -inner);
	}
	if (kind == 2) {
		float d = sd_cloud((p - vec2(0.0, 0.16)) / 0.8) * 0.8;
		for (int i = 0; i < 3; i++) {
			float x = -0.2 + float(i) * 0.2;
			d = min(d, sd_segment(p, vec2(x + 0.05, -0.12), vec2(x - 0.03, -0.38)) - 0.045);
		}
		return d;
	}
	return sd_cloud(p);
}

// Signed distance (m) to the readout: time on top, weather and temperature below, right-aligned at the anchor.
float sd_hud(vec2 p) {
	float h1 = hud_height;
	float h2 = hud_height * 0.8;
	float gap = hud_height * 0.35;
	float d = 1e5;
	// Line 1, HH:MM, digits from the right.
	vec2 q = p - vec2(0.0, h2 + gap + h1 * 0.5);
	float x = -DIGIT_ADV * h1 * 0.5;
	if (abs(q.y) < h1 * 0.6 + HALO) {
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.w) * h1);
		x -= DIGIT_ADV * h1;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.z) * h1);
		x -= DIGIT_ADV * h1 * 0.5 + 0.2 * h1;
		// Colon.
		d = min(d, length(q - vec2(x + 0.03 * h1, 0.2 * h1)) - STROKE * 0.6 * h1);
		d = min(d, length(q - vec2(x - 0.03 * h1, -0.2 * h1)) - STROKE * 0.6 * h1);
		x -= 0.2 * h1 + DIGIT_ADV * h1 * 0.5;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.y) * h1);
		x -= DIGIT_ADV * h1;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.x) * h1);
	}
	// Line 2: [glyph] [-]DD°
	q = p - vec2(0.0, h2 * 0.5);
	if (abs(q.y) < h2 * 0.6 + HALO) {
		x = -0.16 * h2;
		// Degree ring.
		d = min(d, abs(length(q - vec2(x, 0.34 * h2)) - 0.09 * h2) - STROKE * 0.35 * h2);
		x -= 0.2 * h2 + DIGIT_ADV * h2 * 0.5;
		int t = clamp(hud_temperature, -99, 99);
		int a = abs(t);
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h2, a % 10) * h2);
		if (a >= 10) {
			x -= DIGIT_ADV * h2;
			d = min(d, sd_digit((q - vec2(x, 0.0)) / h2, a / 10) * h2);
		}
		if (t < 0) {
			x -= DIGIT_ADV * h2;
			d = min(d, sd_seven((q - vec2(x, 0.0)) / h2, SEG_MINUS) * h2);
		}
		x -= DIGIT_ADV * h2 * 0.5 + 0.55 * h2;
		d = min(d, sd_weather((q - vec2(x, 0.0)) / h2, hud_weather) * h2);
	}
	return d;
}

// ---------------------------------------------------------------- main
void fragment() {
	// Meters per pixel on the pane, taken before any branch (derivatives).
	float px = length(fwidth(v_local));

	float m = smudges(v_local, v_seed) * smudge_amount;
	Rain r = rain(v_local, rain_amount);

	float t = clamp(tint, 0.0, 1.0);
	float coverage = mix(clear_alpha, tint_alpha, t) + m * 0.02 + r.wet * 0.05;
	vec3 color = mix(glass_color, tint_color, t);

	// Fresnel: at grazing angles glass reflects more and lets less through.
	float n_dot_v = clamp(abs(dot(normalize(NORMAL), normalize(VIEW))), 0.0, 1.0);
	float fresnel = pow(1.0 - n_dot_v, 5.0);
	coverage = clamp(coverage + (1.0 - coverage) * fresnel * 0.9, 0.0, 1.0);

	vec3 emission = tint_color * tint_glow * t;

	if (hud_enabled) {
		vec2 hp = v_local - hud_anchor;
		// Bounds of the readout (about 0.25 x 0.17 m plus the glow) before the shapes are evaluated.
		float pad = HALO + px * 3.0;
		if (hp.x < pad && hp.x > -hud_height * 3.6 - pad && hp.y > -pad && hp.y < hud_height * 2.2 + pad) {
			float d = sd_hud(hp);
			// Soft edges: at least 1.5 mm, or a pixel and a half far away (no aliasing).
			float aa = max(px * 1.5, 0.0015);
			float glyph = 1.0 - smoothstep(-aa, aa, d);
			float halo = (1.0 - smoothstep(0.0, HALO, d)) * 0.1;
			emission += hud_color * hud_energy * (glyph + halo);
			coverage = max(coverage, glyph * 0.25);
		}
	}

	ALBEDO = color * coverage;
	ALPHA = coverage;
	PREMUL_ALPHA_FACTOR = 1.0;
	METALLIC = 0.0;
	SPECULAR = clamp(reflectivity + tint_reflectivity * t, 0.0, 1.0);
	ROUGHNESS = clamp(roughness + m * 0.18 + r.wet * 0.1, 0.0, 1.0);
	EMISSION = emission;
}
