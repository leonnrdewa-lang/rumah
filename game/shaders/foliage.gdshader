// Double-sided foliage (palm fronds, leaves, grass): wind sway + see-through near the player.
shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;

global uniform vec2 occlude_center;
global uniform float occlude_depth;
global uniform float occlude_radius;
global uniform float wind_time;

uniform vec4 albedo : source_color = vec4(1.0);
uniform float sway = 1.0;
uniform float sway_base = 0.4;
uniform float fade_enabled = 1.0;
uniform float tint_strength = 0.22;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

varying vec3 world_pos;
varying float height_tint;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 origin = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float h = max(VERTEX.y - sway_base, 0.0);
	float phase = origin.x * 0.37 + origin.z * 0.23;
	float s = sin(wind_time * 1.4 + phase + wp.x * 0.15) * 0.5 + sin(wind_time * 2.3 + phase * 1.7) * 0.25;
	VERTEX.x += s * sway * h * 0.035;
	VERTEX.z += cos(wind_time * 1.1 + phase) * sway * h * 0.02;
	world_pos = wp;
	height_tint = clamp(VERTEX.y * 0.12, 0.0, 1.0);
}

void fragment() {
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
	float n = texture(noise_tex, world_pos.xz * 0.21).g;
	vec3 c = albedo.rgb * (1.0 - tint_strength * 0.5 + tint_strength * n);
	c *= 0.9 + 0.18 * height_tint;
	ALBEDO = c;
	ROUGHNESS = 1.0;
	BACKLIGHT = vec3(0.25, 0.3, 0.1);
	if (fade_enabled > 0.5) {
		vec2 d = (SCREEN_UV - occlude_center) * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0);
		float r = length(d);
		if (-VERTEX.z < occlude_depth - 1.2 && r < occlude_radius) {
			int bx = int(FRAGCOORD.x) % 4;
			int by = int(FRAGCOORD.y) % 4;
			float bayer[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
			float th = (bayer[bx + by * 4] + 0.5) / 16.0;
			float fade = smoothstep(occlude_radius, occlude_radius * 0.55, r) * 0.9;
			if (th < fade) {
				discard;
			}
		}
	}
}
