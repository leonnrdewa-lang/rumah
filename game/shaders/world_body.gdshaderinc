// Shared body of the stylised material for imported models (buildings, props,
// characters, trunks, rocks). Included by world.gdshader (opaque) and
// world_cutout.gdshader (defines ALPHA_CUT: alpha-scissored, double sided).
//
// * albedo colour x optional albedo texture (from the imported glTF material)
// * x vertex colour COLOR (baked AO from Blender; white when the mesh has none,
//   and MultiMesh instance colours multiply into it for per-instance variation)
// * soft wrap lighting + a little painterly colour noise
// * dithered see-through hole around the player so roofs never hide them

global uniform vec2 occlude_center;
global uniform float occlude_depth;
global uniform float occlude_radius;
global uniform float night;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float alpha_cut = 0.5;
uniform float vcol_strength = 1.0;
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float night_emission = 0.0;
uniform float fade_enabled = 1.0;
uniform float tint_strength = 0.14;
uniform float rim_strength = 0.0;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 tex = texture(albedo_tex, UV);
#ifdef ALPHA_CUT
	ALPHA = tex.a * albedo.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
#endif
	float n = texture(noise_tex, world_pos.xz * 0.13 + vec2(world_pos.y * 0.07)).r;
	vec3 c = albedo.rgb * tex.rgb * (1.0 - tint_strength * 0.5 + tint_strength * n);
	c *= mix(vec3(1.0), COLOR.rgb, vcol_strength);
	// soft cream rim on silhouettes (characters) so they pop off the foliage
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0) * rim_strength;
	ALBEDO = c + vec3(1.0, 0.94, 0.8) * rim * (1.0 - night * 0.8);
	ROUGHNESS = 1.0;
	EMISSION = emission_color * night_emission * night * 1.6;
	if (fade_enabled > 0.5) {
		vec2 d = (SCREEN_UV - occlude_center) * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0);
		float r = length(d);
		if (-VERTEX.z < occlude_depth - 1.2 && r < occlude_radius) {
			int bx = int(FRAGCOORD.x) % 4;
			int by = int(FRAGCOORD.y) % 4;
			float bayer[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
			float th = (bayer[bx + by * 4] + 0.5) / 16.0;
			float fade = smoothstep(occlude_radius, occlude_radius * 0.55, r) * 0.85;
			if (th < fade) {
				discard;
			}
		}
	}
}
