// Arena floor: a painted tiling texture clipped to a rounded rectangle with a
// ragged, darkened cliff edge that falls away into the void (Hades-style floating
// arenas). Light is toon-banded like the models; torches add warm pools.
shader_type spatial;
render_mode cull_back, specular_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D noise : filter_linear_mipmap, repeat_enable;
uniform vec2 half_size = vec2(11.0, 8.0);
uniform float corner = 3.0;
uniform float tile = 0.16;
uniform vec3 edge_color : source_color = vec3(0.05, 0.06, 0.08);
uniform vec3 tint : source_color = vec3(1.0);
uniform vec3 shadow_tint = vec3(0.42, 0.45, 0.72);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float sd_round_box(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

void fragment() {
	vec2 p = wpos.xz;
	float n = texture(noise, p * 0.07).r;
	float n2 = texture(noise, p * 0.31 + 0.37).r;
	float d = sd_round_box(p, half_size, corner) + (n - 0.5) * 2.2 + (n2 - 0.5) * 0.6;
	if (d > 0.0) { discard; }
	vec3 c = texture(tex, p * tile).rgb * tint;
	// soft painted mottling
	c *= 0.86 + 0.28 * n2;
	// darkened rim and the cliff lip
	float rim = smoothstep(-2.6, 0.0, d);
	c = mix(c, c * 0.45 + edge_color * 0.3, rim * 0.7);
	c = mix(c, vec3(0.9, 0.8, 0.6) * c * 1.5, smoothstep(-0.25, -0.12, d) * (1.0 - smoothstep(-0.12, -0.02, d)) * 0.6);
	ALBEDO = c;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float lit = smoothstep(0.3, 0.6, ATTENUATION) * step(0.0, ndl);
	vec3 base = mix(shadow_tint * 0.4, vec3(1.0), lit);
	DIFFUSE_LIGHT += LIGHT_COLOR * base * 0.33;
}
