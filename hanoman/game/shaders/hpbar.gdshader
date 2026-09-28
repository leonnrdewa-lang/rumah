// Small billboarded health bar above enemies.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, shadows_disabled;

uniform float ratio = 1.0;
uniform float lag = 1.0;
uniform vec4 fill_color : source_color = vec4(0.85, 0.15, 0.2, 1.0);

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
	vec2 uv = UV;
	float border = step(uv.x, 0.02) + step(0.98, uv.x) + step(uv.y, 0.12) + step(0.88, uv.y);
	vec3 c = vec3(0.06, 0.04, 0.05);
	if (uv.x < lag) { c = vec3(0.95, 0.85, 0.7); }
	if (uv.x < ratio) { c = fill_color.rgb; }
	if (border > 0.0) { c = vec3(0.02); }
	ALBEDO = c;
}
