// Stylised lagoon water: turquoise depth gradient, drifting caustic lines,
// white foam hugging the shore and wave lines rolling in (like the reference shot).
shader_type spatial;
render_mode blend_mix, cull_back, unshaded, depth_draw_never;

global uniform float wind_time;
global uniform float night;

uniform sampler2D height_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform float world_size = 200.0;
uniform float water_level = -0.3;
// env fix round: the sea read a flat pale mint-white (light colours, a half-transparent
// shallow band over bright sand, glow). Saturated turquoise -> teal-blue now, reaching
// the deep colour sooner, more opaque, with a view-angle (fresnel) sheen towards the
// horizon; the white foam stays on the shoreline.
uniform vec3 shallow : source_color = vec3(0.36, 0.82, 0.76);
uniform vec3 mid_col : source_color = vec3(0.12, 0.64, 0.68);
uniform vec3 deep : source_color = vec3(0.05, 0.40, 0.56);
uniform vec3 sheen : source_color = vec3(0.55, 0.80, 0.86);
uniform vec3 foam : source_color = vec3(0.99, 0.99, 0.95);
uniform vec3 night_tint : source_color = vec3(0.10, 0.16, 0.30);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float t = wind_time;
	vec2 uv = (wpos.xz + world_size * 0.5) / world_size;
	float ground = texture(height_tex, clamp(uv, vec2(0.001), vec2(0.999))).r;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		ground = -5.0;
	}
	float depth = water_level - ground;
	float n = texture(noise_tex, wpos.xz * 0.045 + vec2(t * 0.012, t * 0.009)).g;
	float dn = depth + (n - 0.5) * 0.25;

	vec3 col = mix(shallow, mid_col, smoothstep(0.0, 0.6, dn));
	col = mix(col, deep, smoothstep(0.8, 3.0, dn));
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	col = mix(col, sheen, fres * 0.5);

	// caustic lines
	float c1 = texture(noise_tex, wpos.xz * 0.035 + vec2(t * 0.012, -t * 0.008)).r;
	float c2 = texture(noise_tex, wpos.xz * 0.042 - vec2(t * 0.009, t * 0.011)).r;
	float caust = 1.0 - smoothstep(0.0, 0.022, abs(c1 - c2));
	col += vec3(0.10, 0.13, 0.12) * caust * smoothstep(0.08, 0.5, depth) * (1.0 - smoothstep(0.6, 3.0, depth));

	// shore foam + incoming wave lines
	float edge = 1.0 - smoothstep(0.0, 0.03 + n * 0.035, depth);
	float fringe = (1.0 - smoothstep(0.0, 0.2 + n * 0.1, depth)) * 0.32;
	float wave = sin(depth * 16.0 - t * 1.7 + n * 5.0);
	float wline = smoothstep(0.9, 0.985, wave) * (1.0 - smoothstep(0.12, 0.55, depth)) * step(0.02, depth);
	float wave2 = sin(depth * 5.0 - t * 0.9 + n * 3.0);
	float wline2 = smoothstep(0.96, 0.995, wave2) * (1.0 - smoothstep(0.5, 1.4, depth)) * step(0.2, depth) * 0.5;
	float f = clamp(max(max(edge, fringe), max(wline * 0.85, wline2)), 0.0, 1.0);
	col = mix(col, foam, f);

	col = mix(col, col * night_tint * 3.0, night * 0.75);
	ALBEDO = col;
	float a = mix(0.62, 0.97, smoothstep(0.0, 1.0, depth));
	ALPHA = clamp(max(a, f), 0.0, 1.0) * step(-0.02, depth);
}
