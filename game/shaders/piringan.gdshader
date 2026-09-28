// Piringan (the weeded mulch circle around a palm) as a soft, alpha-blended ground
// decal. The Blender texture (reddish mulch + dead frond bits) is toned towards the
// target's warm cream-tan dirt, and the disc fades out over a noisy rim instead of
// ending in a hard alpha-scissor edge, so it reads as bare earth under the palm rather
// than a brown sticker on the lawn.
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, specular_disabled;

#include "res://shaders/toon_light.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 tint : source_color = vec3(1.0, 0.97, 0.9);
uniform float desat = 0.36;
uniform float lift = 0.2;        // mixes towards warm dirt: lighter, less red
uniform vec3 dirt : source_color = vec3(0.62, 0.52, 0.36);
uniform float opacity = 0.86;
// radius (0-1 of the disc) where the fade starts: a clear weeded disc with a soft,
// noisy rim (the polish round's 0.45 left only a faint smudge around seedlings)
// (env fix round: the circle read as a bald disc with a crisp rim; the fade starts
// nearer the middle and the rim is broken into lobes by two octaves of noise)
uniform float edge = 0.42;
// 0 day .. 1 night (world.gd). The reddish mulch under the blue night light read as
// saturated maroon / purple discs (HSV hue 0.77, S 0.30) on the grey-teal night ground:
// at night the disc turns a neutral, slightly yellow brown-grey (which the blue light
// greys out) and blends a little more into the ground
global uniform float night;
uniform vec3 night_tone = vec3(1.0, 0.86, 0.6);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 t = texture(albedo_tex, UV);
	float r = length((UV - 0.5) * 2.0);
	float n = texture(noise_tex, wpos.xz * 0.55).r;
	float n2 = texture(noise_tex, wpos.xz * 1.9 + vec2(0.3, 0.7)).g;
	float fade = 1.0 - smoothstep(edge, 1.0, r + (n - 0.5) * 0.5 + (n2 - 0.5) * 0.22);
	vec3 col = t.rgb;
	float l = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(mix(col, vec3(l), desat), dirt, lift) * tint;
	col = mix(col, vec3(dot(col, vec3(0.299, 0.587, 0.114))) * night_tone, night * 0.9);
	ALBEDO = col * COLOR.rgb;
	ROUGHNESS = 1.0;
	ALPHA = smoothstep(0.1, 0.7, t.a) * fade * opacity * (1.0 - 0.3 * night);
}
