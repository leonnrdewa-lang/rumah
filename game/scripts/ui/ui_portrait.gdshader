// Portrait clip / fade for the dialog + shop speaker portraits (ui_portrait.gd):
// soft fade at the waist cut of half-body art, rounded-card clip for art that
// came with an opaque background, and the round badge clip for 3D head
// renders (clipped below the circle's centre only, so a hat can pop out).
shader_type canvas_item;
uniform float fade_bottom = 0.0;
uniform bool badge = false;
uniform vec2 circle_center = vec2(0.5, 0.58);
uniform float circle_radius = 0.41;
uniform float corner_px = 0.0;
uniform vec2 size_px = vec2(1.0);

void fragment() {
	float a = 1.0;
	if (corner_px > 0.0) {
		vec2 p = UV * size_px;
		vec2 q = min(p, size_px - p);
		if (q.x < corner_px && q.y < corner_px) {
			float d = length(vec2(corner_px) - q);
			a *= 1.0 - smoothstep(corner_px - 1.2, corner_px, d);
		}
	}
	if (badge) {
		float d = length(UV - circle_center);
		a = 1.0 - smoothstep(circle_radius - 0.01, circle_radius, d);
		if (UV.y < circle_center.y) {
			a = 1.0;
		}
	}
	if (fade_bottom > 0.0) {
		a *= smoothstep(0.0, fade_bottom, 1.0 - UV.y);
	}
	COLOR.a *= a;
}
