// Procedural fallback for the piringan (cleared mulch circle around a palm) when
// the piringan model is missing: a lit, alpha-blended soft disc of reddish-brown
// mulch with noisy edges and a few darker frond bits.
shader_type spatial;
render_mode cull_disabled, depth_draw_never, blend_mix, diffuse_lambert_wrap, specular_disabled;

uniform vec3 mulch : source_color = vec3(0.47, 0.33, 0.22);
uniform vec3 mulch_dark : source_color = vec3(0.30, 0.20, 0.13);
uniform vec3 litter : source_color = vec3(0.62, 0.50, 0.30);
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D mulch_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float has_tex = 0.0;
uniform float opacity = 0.92;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 c = (UV - 0.5) * 2.0;
	float r = length(c);
	float n = texture(noise_tex, wpos.xz * 0.35).r;
	float n2 = texture(noise_tex, wpos.xz * 1.3).g;
	float edge = 1.0 - smoothstep(0.62, 0.98, r + (n - 0.5) * 0.35 + (n2 - 0.5) * 0.15);
	vec3 col = mix(mulch_dark, mulch, smoothstep(0.3, 0.7, n2));
	col = mix(col, litter, smoothstep(0.72, 0.8, texture(noise_tex, wpos.xz * 2.1 + 0.3).b) * 0.7);
	if (has_tex > 0.5) {
		col = texture(mulch_tex, wpos.xz / 2.5).rgb * mix(0.85, 1.05, n2);
	}
	col *= mix(0.7, 1.0, smoothstep(0.0, 0.5, r));   // darker right at the trunk
	ALBEDO = col;
	ROUGHNESS = 1.0;
	ALPHA = edge * opacity;
}
