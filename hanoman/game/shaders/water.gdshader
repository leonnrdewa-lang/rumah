// Painted water around the Muara arenas: dark teal with drifting light strokes
// and a foam line where it meets the arena edge (distance from the rounded box).
shader_type spatial;
render_mode unshaded, cull_disabled;

uniform sampler2D noise : filter_linear_mipmap, repeat_enable;
uniform vec3 deep : source_color = vec3(0.03, 0.12, 0.16);
uniform vec3 shallow : source_color = vec3(0.1, 0.36, 0.4);
uniform vec3 foam : source_color = vec3(0.75, 0.95, 0.92);
#include "res://shaders/room_sdf.gdshaderinc"

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = wpos.xz;
	float t = TIME;
	float n1 = texture(noise, p * 0.05 + vec2(t * 0.01, t * 0.013)).r;
	float n2 = texture(noise, p * 0.13 - vec2(t * 0.02, -t * 0.011)).r;
	float d = room_sd(p);
	vec3 c = mix(shallow, deep, smoothstep(0.0, 14.0, d + (n1 - 0.5) * 4.0));
	float streak = smoothstep(0.62, 0.7, n2 * 0.6 + n1 * 0.5);
	c = mix(c, shallow * 1.8, streak * 0.35);
	float f = 1.0 - smoothstep(0.0, 1.4, abs(d - 0.6 - sin(t * 1.3 + n1 * 9.0) * 0.35));
	c = mix(c, foam, f * 0.55);
	ALBEDO = c;
}
