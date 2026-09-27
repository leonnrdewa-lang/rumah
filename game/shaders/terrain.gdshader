// Painterly island ground. Tileable textures from game/assets/textures/ground/
// (grass, grass_dry, dirt, sand, mulch) are sampled in world space (~5.5 m per
// tile), with a second rotated grass sample and macro colour variation to hide
// the tiling. Masks:
//   data_tex  (world_data.png)  R height, G sand, B road, A grass tone
//   shade_tex (world_shade.png) R contact shade under canopies/plants/buildings,
//                               G dryness, B forest-floor litter, A road direction
//                               (1 = road runs along x, 0 = along z)
// Any missing texture falls back to the v1 procedural colours (has_* uniforms).
//
// Cost: high quality ~11 fetches on grass (+ mulch / sand / 2 dirt where those
// show), "Hemat baterai" (hq = 0) ~7 (no rotated grass sample, no very-fine
// noise, one dirt sample). Samples inside the per-pixel branches use
// textureGrad with derivatives taken outside them (implicit derivatives are
// undefined in non-uniform control flow).
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
// 1 = full quality, 0 = "Hemat baterai" (set by world.gd set_quality)
uniform float hq = 1.0;
uniform float tile_m = 5.5;
uniform float world_size = 200.0;
uniform float water_level = -0.3;
uniform float shade_strength = 1.0;
uniform float tex_saturation = 0.85;
uniform vec3 grass_tint = vec3(1.28, 1.04, 1.6);   // linear multiplier: texture -> target olive
// average colour of grass_tex (linear), set by world.gd; detail is scaled around it
uniform vec3 grass_avg = vec3(0.27, 0.39, 0.065);
// < 1 flattens the texture's fine blade noise into a smoother, painterly ground
uniform float detail_contrast = 0.85;
// mip bias (as a gradient scale) for the grass: > 1 = softer
uniform float grass_blur = 1.5;
// v1 procedural palette (fallbacks) + tints anchored to the target palette
uniform vec3 grass_dark : source_color = vec3(0.30, 0.45, 0.235);
uniform vec3 grass_mid : source_color = vec3(0.43, 0.57, 0.28);
uniform vec3 grass_light : source_color = vec3(0.64, 0.73, 0.36);
uniform vec3 sand_col : source_color = vec3(0.94, 0.875, 0.69);
uniform vec3 wet_sand : source_color = vec3(0.80, 0.745, 0.56);
uniform vec3 road_col : source_color = vec3(0.79, 0.69, 0.50);
uniform vec3 dry_col : source_color = vec3(0.78, 0.73, 0.42);
uniform vec3 mulch_col : source_color = vec3(0.45, 0.35, 0.24);
uniform vec3 shade_tint : source_color = vec3(0.78, 0.95, 0.82);
// macro variation: shady olive <-> sunlit yellow-green (linear multipliers)
uniform vec3 macro_shady = vec3(0.6, 0.64, 0.6);
uniform vec3 macro_sunny = vec3(1.12, 1.16, 1.02);
uniform float shade_depth = 0.4;
// warm tan roads like the target's (the dirt texture lights up rather yellow)
uniform vec3 road_tint = vec3(0.965, 0.92, 1.18);
uniform vec3 dry_tint = vec3(0.97, 0.92, 1.08);

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
	float n4 = 0.5;
	if (hq > 0.5) {
		n4 = texture(noise_tex, vec2(wpos.x * 0.9, wpos.z * 0.9) + 0.5).r; // very fine
	}
	vec2 tuv = wpos.xz / tile_m;
	// derivatives for the samples inside the per-pixel branches below
	vec2 tdx = dFdx(tuv);
	vec2 tdy = dFdy(tuv);

	// ---------------------------------------------------------------- grass
	float tone = d.a * 0.55 + n1.r * 0.45;
	vec3 g;
	float gdetail = 0.5;
	if (has_grass > 0.5) {
		vec3 ga = textureGrad(grass_tex, tuv, tdx * grass_blur, tdy * grass_blur).rgb;
		g = ga;
		if (hq > 0.5) {
			vec2 ruv = rot2(tuv, 1.13) * 0.71 + vec2(0.37, 0.71);
			vec3 gb = textureGrad(grass_tex, ruv, rot2(tdx, 1.13) * 0.71 * grass_blur, rot2(tdy, 1.13) * 0.71 * grass_blur).rgb;
			g = mix(ga, gb, smoothstep(0.3, 0.7, n2.g));
		}
		g = max(grass_avg + (g - grass_avg) * detail_contrast, vec3(0.0));
		gdetail = clamp(dot(ga, vec3(0.9)) * 1.2, 0.0, 1.0);
		g = sat(g, tex_saturation) * grass_tint;
		// shady olive <-> sunny yellow-green macro variation
		float t = smoothstep(0.25, 0.85, tone + (n2.b - 0.5) * 0.35);
		g *= mix(macro_shady, macro_sunny, t);
	} else {
		g = mix(grass_dark, grass_mid, smoothstep(0.22, 0.48, tone + (n2.g - 0.5) * 0.2));
		g = mix(g, grass_light, smoothstep(0.58, 0.82, tone + (n2.b - 0.5) * 0.35));
		g *= 0.92 + 0.1 * n3 + 0.06 * n4;
	}

	// ---------------------------------------------------------------- dry grass
	vec3 gd;
	if (has_grass_dry > 0.5) {
		vec2 duv = rot2(tuv, 0.6) * 0.93 + vec2(0.21, 0.13);
		gd = textureGrad(grass_dry_tex, duv, rot2(tdx, 0.6) * 0.93, rot2(tdy, 0.6) * 0.93).rgb * dry_tint;
	} else {
		gd = dry_col * (0.88 + 0.16 * n3 + 0.06 * n4);
	}
	float dry = sh.g + (n2.r - 0.5) * 0.55 + (n3 - 0.5) * 0.2;
	vec3 col = mix(g, gd * 0.9, smoothstep(0.6, 0.9, dry) * 0.55);

	// ---------------------------------------------------------------- forest-floor litter
	if (sh.b > 0.01) {
		vec3 m;
		if (has_mulch > 0.5) {
			m = textureGrad(mulch_tex, tuv * 1.6 + vec2(0.5, 0.2), tdx * 1.6, tdy * 1.6).rgb;
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
			s = textureGrad(sand_tex, tuv * 0.8, tdx * 0.8, tdy * 0.8).rgb * (0.96 + 0.08 * n3);
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
		col = mix(col, mix(col, gd, 0.6), verge * (1.0 - roadm) * 0.6);
		vec3 r;
		if (has_dirt > 0.5) {
			// tyre tracks run along the road: rotate the texture for roads along x
			vec2 xuv = tuv.yx * 1.3 + vec2(0.13, 0.0);
			float along_x = smoothstep(0.3, 0.7, sh.a);
			if (hq > 0.5) {
				vec3 rx = textureGrad(dirt_tex, xuv, tdx.yx * 1.3, tdy.yx * 1.3).rgb;
				vec3 rz = textureGrad(dirt_tex, tuv * 1.3, tdx * 1.3, tdy * 1.3).rgb;
				r = mix(rz, rx, along_x);
			} else {
				// one sample in the dominant direction
				bool ax = along_x > 0.5;
				r = textureGrad(dirt_tex, ax ? xuv : tuv * 1.3, (ax ? tdx.yx : tdx) * 1.3, (ax ? tdy.yx : tdy) * 1.3).rgb;
			}
			r *= (0.95 + 0.08 * n2.g) * road_tint;
		} else {
			r = road_col * (0.9 + 0.14 * n3 + 0.06 * n4);
		}
		// slightly lighter, dusty centre; darker, grassier rim
		r *= 0.88 + 0.12 * smoothstep(0.6, 1.0, d.b);
		col = mix(col, r, roadm);
	}

	// ---------------------------------------------------------------- contact shade
	float shade = clamp(sh.r * shade_strength, 0.0, 1.0);
	col = mix(col, col * shade_tint * shade_depth, shade);

	ALBEDO = col;
	ROUGHNESS = 1.0;
}
