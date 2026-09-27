// Painterly island ground. Tileable textures from game/assets/textures/ground/
// (grass, grass_dry, dirt, sand, mulch) are sampled in world space (~4 m per
// tile), with a second rotated grass sample and macro colour variation to hide
// the tiling. Masks:
//   data_tex  (world_data.png)  R height, G sand, B road, A grass tone
//   shade_tex (world_shade.png) R contact shade under canopies/plants/buildings,
//                               G dryness, B forest-floor litter, A road direction
//                               (1 = road runs along x, 0 = along z)
// Any missing texture falls back to the v1 procedural colours (has_* uniforms).
shader_type spatial;
render_mode cull_back, diffuse_lambert_wrap, specular_disabled;

uniform sampler2D data_tex : filter_linear, repeat_disable;
uniform sampler2D shade_tex : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_dry_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D dirt_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D sand_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D mulch_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float has_grass = 0.0;
uniform float has_grass_dry = 0.0;
uniform float has_dirt = 0.0;
uniform float has_sand = 0.0;
uniform float has_mulch = 0.0;
uniform float has_shade = 0.0;
uniform float tile_m = 4.0;
uniform float world_size = 200.0;
uniform float water_level = -0.3;
uniform float shade_strength = 1.0;
uniform float tex_saturation = 0.9;
uniform vec3 grass_tint = vec3(0.98, 1.0, 1.3);   // linear multiplier: lime texture -> target olive
// v1 procedural palette (fallbacks) + tints anchored to the target palette
uniform vec3 grass_dark : source_color = vec3(0.30, 0.45, 0.235);
uniform vec3 grass_mid : source_color = vec3(0.43, 0.57, 0.28);
uniform vec3 grass_light : source_color = vec3(0.64, 0.73, 0.36);
uniform vec3 sand_col : source_color = vec3(0.94, 0.875, 0.69);
uniform vec3 wet_sand : source_color = vec3(0.80, 0.745, 0.56);
uniform vec3 road_col : source_color = vec3(0.79, 0.69, 0.50);
uniform vec3 dry_col : source_color = vec3(0.78, 0.73, 0.42);
uniform vec3 mulch_col : source_color = vec3(0.45, 0.35, 0.24);
uniform vec3 shade_tint : source_color = vec3(0.80, 0.93, 0.88);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec2 rot2(vec2 p, float a) {
	float c = cos(a);
	float s = sin(a);
	return vec2(c * p.x - s * p.y, s * p.x + c * p.y);
}

vec3 sat(vec3 c, float s) {
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	return mix(vec3(l), c, s);
}

void fragment() {
	vec2 uv = (wpos.xz + world_size * 0.5) / world_size;
	vec4 d = texture(data_tex, uv);
	vec4 sh = has_shade > 0.5 ? texture(shade_tex, uv) : vec4(0.0, 0.3, 0.0, 1.0);
	vec3 n1 = texture(noise_tex, wpos.xz * 0.018).rgb;   // macro, ~55 m
	vec3 n2 = texture(noise_tex, wpos.xz * 0.075).rgb;   // mid, ~13 m
	float n3 = texture(noise_tex, wpos.xz * 0.37).g;      // fine, ~2.7 m
	float n4 = texture(noise_tex, vec2(wpos.x * 0.9, wpos.z * 0.9) + 0.5).r; // very fine
	vec2 tuv = wpos.xz / tile_m;

	// ---------------------------------------------------------------- grass
	float tone = d.a * 0.55 + n1.r * 0.45;
	vec3 g;
	float gdetail = 0.5;
	if (has_grass > 0.5) {
		vec3 ga = texture(grass_tex, tuv).rgb;
		vec3 gb = texture(grass_tex, rot2(tuv, 1.13) * 0.71 + vec2(0.37, 0.71)).rgb;
		g = mix(ga, gb, smoothstep(0.3, 0.7, n2.g));
		gdetail = clamp(dot(ga, vec3(0.9)) * 1.2, 0.0, 1.0);
		g = sat(g, tex_saturation) * grass_tint;
		// shady olive <-> sunny yellow-green macro variation
		float t = smoothstep(0.22, 0.8, tone + (n2.b - 0.5) * 0.35);
		g *= mix(vec3(0.62, 0.76, 0.6), vec3(1.14, 1.08, 0.9), t);
	} else {
		g = mix(grass_dark, grass_mid, smoothstep(0.22, 0.48, tone + (n2.g - 0.5) * 0.2));
		g = mix(g, grass_light, smoothstep(0.58, 0.82, tone + (n2.b - 0.5) * 0.35));
		g *= 0.92 + 0.1 * n3 + 0.06 * n4;
	}

	// ---------------------------------------------------------------- dry grass
	vec3 gd;
	if (has_grass_dry > 0.5) {
		gd = texture(grass_dry_tex, rot2(tuv, 0.6) * 0.93 + vec2(0.21, 0.13)).rgb;
	} else {
		gd = dry_col * (0.88 + 0.16 * n3 + 0.06 * n4);
	}
	float dry = sh.g + (n2.r - 0.5) * 0.55 + (n3 - 0.5) * 0.2;
	vec3 col = mix(g, gd, smoothstep(0.58, 0.88, dry) * 0.75);

	// ---------------------------------------------------------------- forest-floor litter
	if (sh.b > 0.01) {
		vec3 m;
		if (has_mulch > 0.5) {
			m = texture(mulch_tex, tuv * 1.3 + vec2(0.5, 0.2)).rgb;
		} else {
			m = mulch_col * (0.8 + 0.3 * n3 + 0.1 * n4);
		}
		col = mix(col, m, smoothstep(0.25, 0.85, sh.b + (n3 - 0.5) * 0.5 + (n4 - 0.5) * 0.2) * 0.75);
	}

	// ---------------------------------------------------------------- sand (beach)
	float sandm = smoothstep(0.35, 0.65, d.g + (n2.b - 0.5) * 0.4);
	if (sandm > 0.001) {
		vec3 s;
		if (has_sand > 0.5) {
			s = texture(sand_tex, tuv * 0.8).rgb * (0.96 + 0.08 * n3);
		} else {
			s = sand_col * (0.95 + 0.07 * n3);
		}
		float wet = 1.0 - smoothstep(water_level - 0.02, water_level + 0.3, wpos.y);
		s = mix(s, wet_sand * (has_sand > 0.5 ? 0.92 : 1.0), wet * 0.85);
		col = mix(col, s, sandm);
	}

	// ---------------------------------------------------------------- roads
	// packed dirt with a dry-grass verge; grass blades and noise eat into the edge
	if (d.b > 0.002) {
		float e = d.b + (n2.r - 0.5) * 0.3 + (n3 - 0.5) * 0.22 + (n4 - 0.5) * 0.22 + (gdetail - 0.5) * 0.25;
		float verge = smoothstep(0.12, 0.44, e);
		float roadm = smoothstep(0.44, 0.6, e);
		col = mix(col, mix(col, gd, 0.7) * 1.03, verge * (1.0 - roadm) * 0.65);
		vec3 r;
		if (has_dirt > 0.5) {
			// tyre tracks run along the road: rotate the texture for roads along z
			vec3 rx = texture(dirt_tex, tuv.yx * vec2(1.0, 1.0) + vec2(0.13, 0.0)).rgb;
			vec3 rz = texture(dirt_tex, tuv).rgb;
			r = mix(rz, rx, smoothstep(0.3, 0.7, sh.a));
			r *= 0.95 + 0.08 * n2.g;
		} else {
			r = road_col * (0.9 + 0.14 * n3 + 0.06 * n4);
		}
		// slightly lighter, dusty centre
		r *= 0.92 + 0.08 * smoothstep(0.7, 1.0, d.b);
		col = mix(col, r, roadm);
	}

	// ---------------------------------------------------------------- contact shade
	float shade = clamp(sh.r * shade_strength, 0.0, 1.0);
	col = mix(col, col * shade_tint * 0.42, shade);

	ALBEDO = col;
	ROUGHNESS = 1.0;
}
