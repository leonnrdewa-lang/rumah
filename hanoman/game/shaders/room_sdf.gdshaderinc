// Room shape shared by the floor and water shaders: a smooth union of rounded
// boxes (chambers and the corridors between them) minus rounded-box pits.
// Must match Arena.sd() in scripts/arena.gd. With box_count 0 the room is the
// single box half_size/corner.
uniform vec4 boxes[8];        // xy centre, zw half size
uniform vec4 box_info[8];     // x corner radius, y painting index (-1 = plain)
uniform int box_count = 0;
uniform vec4 holes[4];        // xy centre, zw half size
uniform vec4 hole_info[4];    // x corner radius
uniform int hole_count = 0;
uniform vec2 half_size = vec2(11.0, 8.0);
uniform float corner = 3.0;

float sd_round_box(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float smin_k(float a, float b, float k) {
	float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
	return mix(b, a, h) - k * h * (1.0 - h);
}

float room_sd(vec2 p) {
	if (box_count == 0) {
		return sd_round_box(p, half_size, corner);
	}
	float d = 1e5;
	for (int i = 0; i < 8; i++) {
		if (i >= box_count) { break; }
		d = smin_k(d, sd_round_box(p - boxes[i].xy, boxes[i].zw, box_info[i].x), 1.5);
	}
	for (int j = 0; j < 4; j++) {
		if (j >= hole_count) { break; }
		d = max(d, -sd_round_box(p - holes[j].xy, holes[j].zw, hole_info[j].x));
	}
	return d;
}
