// Floor guide light (D-060): a thin LED line set in the floor. A soft glow with
// pulses running along the instance's flow direction (world space), so the line
// leads somewhere (the elevators). Unshaded, opaque: it's the LED itself.
shader_type spatial;
render_mode unshaded, shadows_disabled;

uniform vec3 tint : source_color = vec3(0.02, 0.85, 0.91);
uniform float base_energy = 0.35;
uniform float pulse_energy = 1.4;
uniform float spacing = 3.0;     // m between pulses
uniform float pulse_length = 0.8; // m, the pulse's soft length
uniform float speed = 0.9;        // m/s
// Where the pulses run (world XZ, unit length); zero: no pulses.
instance uniform vec3 flow = vec3(0.0);

varying vec3 v_world;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float along = dot(v_world, flow);
	float phase = fract((along - TIME * speed) / spacing) * spacing;
	// A pulse with a bright head and a tail behind it (the head leads along the flow).
	float tail = smoothstep(pulse_length, 0.0, spacing - phase) * step(0.001, dot(flow, flow));
	ALBEDO = tint * (base_energy + pulse_energy * tail * tail);
}
