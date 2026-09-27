// Birds and butterflies (MultiMesh): the wings flap in the vertex shader by
// rotating every vertex around the body axis (z) by an angle that grows with |x|.
// Instance colour tints each critter; COLOR.a of the mesh marks the wing (1) vs
// body (0) so the body stays rigid.
shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;

uniform float flap_speed = 9.0;
uniform float flap_amp = 0.9;
uniform float flap_bias = 0.15;
uniform vec3 body_color : source_color = vec3(0.25, 0.2, 0.18);

varying float wing;
varying vec3 tint;

void vertex() {
	wing = COLOR.a;
	tint = COLOR.rgb;
	float phase = float(INSTANCE_ID) * 1.73 + MODEL_MATRIX[3].x * 0.3;
	float a = (sin(TIME * flap_speed + phase) * flap_amp + flap_bias) * wing;
	float side = VERTEX.x;
	float r = abs(side);
	VERTEX.x = sign(side) * r * cos(a);
	VERTEX.y += r * sin(a);
	NORMAL = normalize(vec3(-sign(side) * sin(a) * wing, cos(a), 0.0) + NORMAL * (1.0 - wing));
}

void fragment() {
	ALBEDO = mix(body_color, tint, wing);
	ROUGHNESS = 1.0;
	BACKLIGHT = vec3(0.3) * wing;
}
