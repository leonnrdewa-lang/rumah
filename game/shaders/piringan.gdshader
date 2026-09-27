// Piringan (the weeded mulch circle around a palm) as a soft, alpha-blended ground
// decal. The Blender texture (reddish mulch + dead frond bits) is toned towards the
// target's warm cream-tan dirt, and the disc fades out over a noisy rim instead of
// ending in a hard alpha-scissor edge, so it reads as bare earth under the palm rather
// than a brown sticker on the lawn.
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, diffuse_lambert_wrap, specular_disabled;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 tint : source_color = vec3(1.0, 0.97, 0.9);
uniform float desat = 0.3;
uniform float lift = 0.12;       // mixes towards warm dirt: lighter, less red
uniform vec3 dirt : source_color = vec3(0.62, 0.52, 0.36);
uniform float opacity = 0.9;
uniform float edge = 0.45;       // radius (0-1 of the disc) where the fade starts

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 t = texture(albedo_tex, UV);
	float r = length((UV - 0.5) * 2.0);
	float n = texture(noise_tex, wpos.xz * 0.7).r;
	float fade = 1.0 - smoothstep(edge, 1.0, r + (n - 0.5) * 0.35);
	vec3 col = t.rgb;
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(mix(col, vec3(l), desat), dirt, lift) * tint;
	ALBEDO = col * COLOR.rgb;
	ROUGHNESS = 1.0;
	ALPHA = smoothstep(0.1, 0.7, t.a) * fade * opacity;
}
