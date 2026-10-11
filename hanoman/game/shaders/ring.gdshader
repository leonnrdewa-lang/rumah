// Ground decal disc: enemy attack telegraphs (filling red circle) and the Ajian
// Bayu binding circle (rotating runes). Drawn on a flat quad just above the floor.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.2, 0.2, 1.0);
uniform float fill = 0.0;
uniform float alpha = 1.0;
uniform float runes = 0.0;
uniform float arc = 6.2832;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	if (r > 1.0) { discard; }
	float ang = atan(p.x, p.y);
	if (abs(ang) > arc * 0.5) { discard; }
	float edge = smoothstep(0.88, 0.94, r) * (1.0 - smoothstep(0.97, 1.0, r));
	float inner = (1.0 - smoothstep(fill - 0.03, fill, r)) * 0.35;
	float a = edge + inner + 0.08;
	if (runes > 0.5) {
		float a2 = ang + TIME * 0.8;
		float ring2 = smoothstep(0.66, 0.69, r) * (1.0 - smoothstep(0.71, 0.74, r));
		float ticks = step(0.5, fract(a2 * 24.0 / 6.2832)) * smoothstep(0.76, 0.78, r) * (1.0 - smoothstep(0.84, 0.86, r));
		float spokes = smoothstep(0.97, 1.0, cos(a2 * 6.0)) * step(r, 0.66) * step(0.2, r);
		a = edge * 1.1 + ring2 * 0.8 + ticks * 0.6 + spokes * 0.45 + 0.05;
	}
	ALBEDO = color.rgb * a * alpha * 0.9;
}
