// Anime cel-shading light model shared by every lit material (world, foliage,
// terrain, critters, decals). The sun gives two flat bands (lit / shade) with a
// thin soft edge, cast shadows snap to the shade band, and the shade side keeps
// a cool blue-violet tint; lamps (omni/spot) give warm, soft-edged pools.
// Define TOON_BACKLIGHT before including to let BACKLIGHT glow through leaves.

uniform float toon_edge = 0.035;
uniform float toon_lit = 0.92;

void light() {
	float ndl = dot(NORMAL, LIGHT);
	if (LIGHT_IS_DIRECTIONAL) {
		float lit = smoothstep(-toon_edge, toon_edge, ndl - 0.02);
		lit *= smoothstep(0.42, 0.58, ATTENUATION);
		// a narrow brighter band on faces turned right at the sun
		float hi = smoothstep(0.62, 0.62 + toon_edge, ndl) * lit;
		vec3 c = LIGHT_COLOR / PI;
		DIFFUSE_LIGHT += c * (lit * (toon_lit + 0.12 * hi));
		// cool fill in the shade band (anime shadows are blue, never grey)
		DIFFUSE_LIGHT += c * (1.0 - lit) * vec3(0.03, 0.05, 0.13);
#ifdef TOON_BACKLIGHT
		DIFFUSE_LIGHT += c * BACKLIGHT * smoothstep(0.0, 0.25, -ndl) * smoothstep(0.42, 0.58, ATTENUATION);
#endif
	} else {
		float wrap = smoothstep(-0.1, 0.15, ndl);
		float pool = smoothstep(0.0, 0.18, ATTENUATION) * 0.55 + ATTENUATION * 0.6;
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * wrap * pool;
	}
}
