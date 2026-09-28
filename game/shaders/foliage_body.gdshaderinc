// Shared body of the double-sided foliage material (palm fronds, leaves, ferns,
// grass, flowers). Included by foliage.gdshader (solid) and foliage_cutout.gdshader
// (defines ALPHA_CUT for alpha-card leaves exported as glTF alphaMode MASK).
//
// wind sway + optional albedo texture + vertex-colour AO (COLOR) + normals bent
// towards the sky for small plants (so cards shade like the ground) + translucency
// + the see-through hole near the player + low plants bending away from the player
// and thinning out on its camera side.

global uniform vec2 occlude_center;
global uniform float occlude_depth;
global uniform float occlude_radius;
global uniform float wind_time;
// the player's feet (world.gd; far below the island when nobody walks)
global uniform vec3 player_pos;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float alpha_cut = 0.5;
uniform float vcol_strength = 1.0;
uniform float sway = 1.0;
uniform float sway_base = 0.4;
uniform float normal_up = 0.0;
uniform float fade_enabled = 1.0;
uniform float tint_strength = 0.22;
uniform float tip_light = 0.18;
// green leaves are pulled towards the target's soft olive palette (the textures and
// the post saturation make them read neon otherwise); yellow/white petals keep colour
uniform float green_sat = 0.9;
uniform float green_warm = -0.05;
// overall albedo scale (palm crowns are toned down a little)
uniform float tone = 1.0;
// translucency of the leaves when lit from behind
uniform vec3 backlight = vec3(0.26, 0.28, 0.14);
// low ground plants (grass, ferns, leafy clumps) bend down and away around the player,
// so the knee-high carpet never hides the character's legs (0 = off)
uniform float trample = 0.0;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

varying vec3 world_pos;
varying float height_tint;
// where the vertex ends up after the trample (for the thinning near the player below)
varying vec3 bent_pos;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 origin = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float h = max(VERTEX.y - sway_base, 0.0);
	float phase = origin.x * 0.37 + origin.z * 0.23;
	float gust = 0.75 + 0.25 * sin(wind_time * 0.35 + origin.x * 0.05);
	float s = sin(wind_time * 1.4 + phase + wp.x * 0.15) * 0.5 + sin(wind_time * 2.3 + phase * 1.7) * 0.25;
	VERTEX.x += s * sway * gust * h * 0.035;
	VERTEX.z += cos(wind_time * 1.1 + phase) * sway * gust * h * 0.02;
	// leaf tips flutter a little on their own
	VERTEX.y += sin(wind_time * 3.1 + wp.x * 1.3 + wp.z * 1.1) * sway * h * 0.006;
	if (trample > 0.0) {
		// Fix round 2: the whole plant tips over as a rigid body (a rotation about its
		// base, away from the player) instead of the lower leaves being sheared sideways,
		// which stretched shrub and keladi leaves at close range. The amount depends on
		// where the plant stands, not on each vertex, so nothing tears or stretches.
		vec2 d = origin.xz - player_pos.xz;
		// reaches further on the camera side (+z), where the leaves would cover the legs
		float dist = length(vec2(d.x, d.y * (d.y > 0.0 ? 0.7 : 1.4)));
		float k = trample * (1.0 - smoothstep(0.35, 1.3, dist)) * step(abs(origin.y - player_pos.y), 1.5);
		if (k > 0.001) {
			// a plant right under the player falls away from the camera (behind the legs)
			vec2 dir = normalize(d + vec2(0.0, -0.08));
			vec3 ax = vec3(dir.y, 0.0, -dir.x);   // horizontal axis: the top moves along +dir
			float th = k * 1.05;
			vec3 r = wp - origin;
			vec3 rr = r * cos(th) + cross(ax, r) * sin(th) + ax * dot(ax, r) * (1.0 - cos(th));
			// a plant the player stands in is also pressed down (a bush thicket otherwise
			// buried the character up to the hat)
			rr.y *= 1.0 - 0.6 * (1.0 - smoothstep(0.25, 0.95, dist));
			// world offset -> local (instances are rotated and ~uniformly scaled)
			mat3 m = mat3(MODEL_MATRIX);
			VERTEX += transpose(m) * (rr - r) / max(dot(m[0], m[0]), 1e-4);
		}
	}
	world_pos = wp;
	bent_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	height_tint = clamp(VERTEX.y * 0.12, 0.0, 1.0);
}

void fragment() {
	vec4 tex = texture(albedo_tex, UV);
#ifdef ALPHA_CUT
	ALPHA = tex.a * albedo.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
#endif
	vec3 nrm = FRONT_FACING ? NORMAL : -NORMAL;
	if (normal_up > 0.0) {
		vec3 up = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
		nrm = normalize(mix(nrm, up, normal_up));
	}
	NORMAL = nrm;
	float n = texture(noise_tex, world_pos.xz * 0.21).g;
	vec3 c = albedo.rgb * tex.rgb * (1.0 - tint_strength * 0.5 + tint_strength * n);
	c *= mix(vec3(1.0), COLOR.rgb, vcol_strength);
	c *= 1.0 - tip_light * 0.5 + tip_light * height_tint;
	float gdom = smoothstep(0.0, 0.06, c.g - max(c.r, c.b));
	float lum = dot(c, vec3(0.299, 0.587, 0.114));
	vec3 cs = mix(vec3(lum), c, green_sat);
	cs.r += green_warm * cs.g;
	c = mix(c, cs, gdom);
	ALBEDO = c * tone;
	ROUGHNESS = 1.0;
	BACKLIGHT = backlight;
	if (trample > 0.0) {
		// The low plants on the camera side of the player thin out (dithered) within ~1.2 m
		// of their feet, leaving only the lowest leaves as a trampled ring, so the
		// character always stands visibly in the carpet as in the target (v2 fix round 3:
		// the knee-high carpet hid them to the waist at the closer camera). Plants behind
		// the player stay whole.
		vec2 dp = bent_pos.xz - player_pos.xz;
		float dd = length(vec2(dp.x, dp.y * (dp.y > 0.0 ? 0.75 : 1.3)));
		float hgt = bent_pos.y - player_pos.y;
		float fade = (1.0 - smoothstep(0.7, 1.25, dd)) * smoothstep(0.06, 0.22, hgt)
			* smoothstep(-0.45, 0.0, dp.y) * (1.0 - smoothstep(1.4, 1.8, hgt));
		if (fade > 0.0) {
			float ign = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
			if (ign < fade * 0.9) {
				discard;
			}
		}
	}
	if (fade_enabled > 0.5) {
		// see-through hole around the player (env fix round: interleaved-gradient noise
		// per pixel instead of the coarse 4x4 Bayer screen door, and a tighter radius)
		vec2 d = (SCREEN_UV - occlude_center) * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0);
		float r = length(d);
		if (-VERTEX.z < occlude_depth - 1.2 && r < occlude_radius) {
			float th = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
			float fade = smoothstep(occlude_radius, occlude_radius * 0.5, r) * 0.9;
			if (th < fade) {
				discard;
			}
		}
	}
}
