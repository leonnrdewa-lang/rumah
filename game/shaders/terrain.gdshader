// Painterly island ground: grass blotches, sand, wet sand and dirt roads from the
// world_data mask (R height, G sand, B road, A grass tone) plus tileable noise.
shader_type spatial;
render_mode cull_back, diffuse_lambert_wrap, specular_disabled;

uniform sampler2D data_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform float world_size = 200.0;
uniform float water_level = -0.3;
uniform vec3 grass_dark : source_color = vec3(0.30, 0.45, 0.235);
uniform vec3 grass_mid : source_color = vec3(0.43, 0.57, 0.28);
uniform vec3 grass_light : source_color = vec3(0.64, 0.73, 0.36);
uniform vec3 sand_col : source_color = vec3(0.94, 0.875, 0.69);
uniform vec3 wet_sand : source_color = vec3(0.80, 0.745, 0.56);
uniform vec3 road_col : source_color = vec3(0.72, 0.60, 0.42);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = (wpos.xz + world_size * 0.5) / world_size;
	vec4 d = texture(data_tex, uv);
	vec3 n1 = texture(noise_tex, wpos.xz * 0.018).rgb;
	vec3 n2 = texture(noise_tex, wpos.xz * 0.075).rgb;
	float n3 = texture(noise_tex, wpos.xz * 0.37).g;
	float n4 = texture(noise_tex, vec2(wpos.x * 0.9, wpos.z * 0.25)).r; // stretched "brush strokes"

	float tone = d.a * 0.55 + n1.r * 0.45;
	vec3 g = mix(grass_dark, grass_mid, smoothstep(0.22, 0.48, tone + (n2.g - 0.5) * 0.2));
	g = mix(g, grass_light, smoothstep(0.58, 0.82, tone + (n2.b - 0.5) * 0.35));
	g *= 0.92 + 0.1 * n3 + 0.06 * n4;

	float sandm = smoothstep(0.35, 0.65, d.g + (n2.b - 0.5) * 0.4);
	vec3 s = sand_col * (0.95 + 0.07 * n3);
	float wet = 1.0 - smoothstep(water_level - 0.02, water_level + 0.3, wpos.y);
	s = mix(s, wet_sand, wet * 0.85);
	vec3 col = mix(g, s, sandm);

	float roadm = smoothstep(0.3, 0.7, d.b + (n2.r - 0.5) * 0.3);
	vec3 r = road_col * (0.9 + 0.14 * n3 + 0.06 * n4);
	col = mix(col, r, roadm);

	ALBEDO = col;
	ROUGHNESS = 1.0;
}
