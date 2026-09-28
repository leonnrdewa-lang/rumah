// Additive unshaded glow for slashes, projectiles, sparks and magic.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.8, 0.4, 1.0);
uniform float intensity = 1.5;
uniform float alpha = 1.0;
uniform sampler2D mask : filter_linear, repeat_disable;
uniform float use_mask = 0.0;

void fragment() {
	float m = use_mask > 0.5 ? texture(mask, UV).r : 1.0;
	ALBEDO = color.rgb * intensity * m * alpha * COLOR.a;
}
