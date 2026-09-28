// Textured additive VFX sprite (Higgsfield-painted slashes, beams, impacts,
// magic circles). Sprites are painted on black, so additive blending needs no
// alpha. `billboard` 1 = face the camera, 2 = face it but stay upright (bolts).
// `tint` recolours the painting toward `color` (god boon colours).
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec4 color : source_color = vec4(1.0);
uniform float intensity = 1.6;
uniform float alpha = 1.0;
uniform float tint = 0.3;
uniform float billboard = 0.0;
uniform float uv_rot = 0.0;
uniform float spin_speed = 0.0;
uniform vec2 uv_scale = vec2(1.0);
uniform vec2 uv_offset = vec2(0.0);
uniform float wrap_u = 0.0;
uniform float edge_fade = 0.0;

void vertex() {
	if (billboard > 0.5) {
		float sx = length(MODEL_MATRIX[0].xyz);
		float sy = length(MODEL_MATRIX[1].xyz);
		vec3 right = INV_VIEW_MATRIX[0].xyz;
		vec3 up = INV_VIEW_MATRIX[1].xyz;
		vec3 fwd = INV_VIEW_MATRIX[2].xyz;
		if (billboard > 1.5) {
			right = normalize(vec3(right.x, 0.0, right.z));
			up = vec3(0.0, 1.0, 0.0);
			fwd = cross(right, up);
		}
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(right * sx, 0.0), vec4(up * sy, 0.0), vec4(fwd, 0.0), MODEL_MATRIX[3]);
	}
}

void fragment() {
	vec2 uv = UV - 0.5;
	float ang = uv_rot + TIME * spin_speed;
	float cs = cos(ang);
	float sn = sin(ang);
	uv = vec2(cs * uv.x - sn * uv.y, sn * uv.x + cs * uv.y) + 0.5;
	vec2 tuv = uv * uv_scale + uv_offset;
	if (wrap_u > 0.5) {
		tuv.x = fract(tuv.x);
	}
	vec3 t = texture(tex, tuv).rgb;
	// painted on black: lift the black floor so JPEG noise never shows as a box
	t = max(t - vec3(0.035), vec3(0.0)) * 1.04;
	if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
		t = vec3(0.0);
	}
	float lum = max(t.r, max(t.g, t.b));
	vec3 c = mix(t, color.rgb * lum * 1.15, tint);
	float e = 1.0;
	if (edge_fade > 0.0) {
		e = smoothstep(0.0, edge_fade, UV.x) * smoothstep(0.0, edge_fade * 0.5, 1.0 - UV.x);
	}
	ALBEDO = c * intensity * alpha * e * COLOR.rgb;
}
