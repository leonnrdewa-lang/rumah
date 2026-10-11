class_name Atmos
extends RefCounted
## Living atmosphere for every arena: drifting fireflies / embers / spray,
## falling leaves, ground mist, slanted light shafts and a coloured key light
## per chamber. "Rendah" graphics keep only the lights.

const THEME_LIGHT := {
	"pond": Color(0.45, 0.85, 1.0), "pillars": Color(1.0, 0.72, 0.45), "ruins": Color(1.0, 0.6, 0.35),
	"rocks": Color(0.8, 0.75, 1.0), "grove": Color(0.55, 1.0, 0.55), "mangrove": Color(0.45, 0.95, 0.8),
	"shrine": Color(0.4, 1.0, 0.9), "piers": Color(0.55, 0.8, 1.0), "open": Color(0.95, 0.85, 0.7),
}

static var _leaf_tex: Texture2D
static var _ray_tex: Texture2D
static var _dot_tex: Texture2D


static func build(a: Arena) -> void:
	var root := Node3D.new()
	root.name = "Atmos"
	a.add_child(root)
	var b: Rect2 = a.bounds if a.bounds.has_area() else Rect2(-a.half, a.half * 2.0)
	var centre := Vector3(b.get_center().x, 0, b.get_center().y)
	var ext := Vector3(b.size.x * 0.5, 0, b.size.y * 0.5)
	# key light per chamber, tinted by its theme
	for ch in a.chambers:
		var box: Dictionary = a.boxes[ch.box]
		var col: Color = THEME_LIGHT.get(String(box.get("theme", "open")), Color(0.95, 0.85, 0.7))
		if a.kind == "boss":
			col = Color(0.4, 0.75, 1.0)
		elif a.kind == "miniboss":
			col = Color(1.0, 0.8, 0.35)
		var l := OmniLight3D.new()
		l.light_color = col
		l.light_energy = 1.1
		l.omni_range = maxf(box.h.x, box.h.y) * 1.6
		l.omni_attenuation = 1.6
		l.position = Vector3(box.c.x, 4.5, box.c.y)
		root.add_child(l)
	if not G.high_quality():
		return
	var muara := a.biome in Arena.WATERY
	var hub := a.kind == "hub"
	# floating motes: fireflies in the forest, sea spray on the estuary, embers at bosses
	var mote_col := Color(0.75, 1.0, 0.45)
	if muara:
		mote_col = Color(0.6, 0.9, 1.0)
	if a.kind == "boss" or a.kind == "miniboss":
		mote_col = Color(1.0, 0.6, 0.25)
	if hub:
		mote_col = Color(1.0, 0.85, 0.5)
	root.add_child(_motes(centre, ext, mote_col, int(clamp(ext.x * ext.z * 0.18, 30, 140))))
	# falling leaves (forest and camp)
	if not muara:
		root.add_child(_leaves(centre, ext, int(clamp(ext.x * ext.z * 0.08, 14, 70))))
	# low ground mist banks
	var rng := RandomNumberGenerator.new()
	rng.seed = a.depth * 977 + 13
	var mists := int(clamp(ext.x * ext.z * 0.02, 6, 22))
	for i in mists:
		var p := centre + Vector3(rng.randf_range(-ext.x, ext.x), 0.25, rng.randf_range(-ext.z, ext.z))
		if a.sd_all(Vector2(p.x, p.z)) > 0.5:
			continue
		root.add_child(_mist(p, rng.randf_range(5.0, 9.0), Color(0.55, 0.7, 0.8) if muara else Color(0.6, 0.75, 0.6)))
	# moonlight and torch glints shimmering on the open water
	if muara:
		for i in int(clamp(ext.x * ext.z * 0.03, 8, 40)):
			var p := centre + Vector3(rng.randf_range(-ext.x - 6, ext.x + 6), -0.3, rng.randf_range(-ext.z - 6, ext.z + 6))
			if a.sd_all(Vector2(p.x, p.z)) < 0.8:
				continue
			root.add_child(_glint(p, rng.randf_range(1.2, 3.2)))
	# slanted light shafts falling through the canopy
	var rays := int(clamp(ext.x * 0.4, 3, 10))
	for i in rays:
		var p := centre + Vector3(rng.randf_range(-ext.x * 0.9, ext.x * 0.9), 0, rng.randf_range(-ext.z * 0.9, ext.z * 0.6))
		root.add_child(_ray(p, rng.randf_range(1.6, 3.0), mote_col.lerp(Color(1, 0.95, 0.8), 0.6)))


static func _additive(tex: Texture2D, col: Color, size: float) -> QuadMesh:
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.albedo_texture = tex
	m.albedo_color = col
	m.vertex_color_use_as_albedo = true
	q.material = m
	return q


static func _motes(c: Vector3, ext: Vector3, col: Color, n: int) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = n
	p.lifetime = 6.0
	p.preprocess = 6.0
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(ext.x, 1.2, ext.z)
	p.position = c + Vector3(0, 1.4, 0)
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 0.1
	p.initial_velocity_max = 0.45
	p.gravity = Vector3(0, 0.04, 0)
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.2
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0))
	fade.add_point(0.25, Color(1, 1, 1, 1))
	fade.add_point(0.75, Color(1, 1, 1, 1))
	fade.set_color(fade.get_point_count() - 1, Color(1, 1, 1, 0))
	p.color_ramp = fade
	p.mesh = _additive(_dot(), col * 2.4, 0.16)
	return p


static func _leaves(c: Vector3, ext: Vector3, n: int) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = n
	p.lifetime = 7.0
	p.preprocess = 7.0
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(ext.x, 0.5, ext.z)
	p.position = c + Vector3(0, 7.0, 0)
	p.direction = Vector3(1, -0.3, 0.2)
	p.spread = 25.0
	p.initial_velocity_min = 0.4
	p.initial_velocity_max = 1.0
	p.gravity = Vector3(0.3, -0.9, 0.1)
	p.angular_velocity_min = -160.0
	p.angular_velocity_max = 160.0
	p.angle_min = 0.0
	p.angle_max = 360.0
	p.scale_amount_min = 0.7
	p.scale_amount_max = 1.3
	p.color = Color(0.85, 0.55, 0.2)
	var q := QuadMesh.new()
	q.size = Vector2(0.22, 0.13)
	var m := StandardMaterial3D.new()
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.albedo_texture = _leaf()
	m.vertex_color_use_as_albedo = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	q.material = m
	p.mesh = q
	return p


static func _mist(pos: Vector3, size: float, col: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = Fx._flat_unit()
	var m := Fx.tex_mat("smoke", col, 0.12, 0.8, 0.0)
	m.set_shader_parameter("spin_speed", randf_range(-0.05, 0.05))
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos
	mi.basis = Basis(Vector3.UP, randf() * TAU) * Basis.from_scale(Vector3(size, 1, size * 0.7))
	return mi


static func _glint(pos: Vector3, size: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = Fx._flat_unit()
	var m := Fx.tex_mat("k_light", Color(0.75, 0.9, 1.0), 0.0, 0.6, 0.0)
	m.set_shader_parameter("spin_speed", randf_range(-0.3, 0.3))
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos
	mi.basis = Basis.from_scale(Vector3(size, 1, size * 0.45))
	var tw := mi.create_tween().set_loops()
	var peak := randf_range(0.35, 0.8)
	tw.tween_interval(randf_range(0.0, 2.0))
	tw.tween_method(func(v): m.set_shader_parameter("intensity", v), 0.0, peak, randf_range(0.8, 1.6)).set_trans(Tween.TRANS_SINE)
	tw.tween_method(func(v): m.set_shader_parameter("intensity", v), peak, 0.0, randf_range(0.8, 1.6)).set_trans(Tween.TRANS_SINE)
	return mi


static func _ray(pos: Vector3, width: float, col: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(width, 9.0)
	mi.mesh = q
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	m.albedo_texture = _ray_t()
	m.albedo_color = Color(col.r, col.g, col.b) * 0.28
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.no_depth_test = false
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos + Vector3(0, 4.3, 0)
	mi.rotation.z = deg_to_rad(randf_range(14.0, 24.0))
	# slow breathing so the shafts feel alive
	var tw := mi.create_tween().set_loops()
	var base := m.albedo_color
	tw.tween_property(m, "albedo_color", base * 0.45, randf_range(2.5, 4.0)).set_trans(Tween.TRANS_SINE)
	tw.tween_property(m, "albedo_color", base, randf_range(2.5, 4.0)).set_trans(Tween.TRANS_SINE)
	return mi


# --- tiny procedural textures --------------------------------------------------

static func _dot() -> Texture2D:
	if _dot_tex == null:
		var n := 32
		var img := Image.create(n, n, false, Image.FORMAT_RGB8)
		for y in n:
			for x in n:
				var r := Vector2(x + 0.5 - n * 0.5, y + 0.5 - n * 0.5).length() / (n * 0.5)
				var k := pow(clampf(1.0 - r, 0.0, 1.0), 2.2)
				img.set_pixel(x, y, Color(k, k, k))
		_dot_tex = ImageTexture.create_from_image(img)
	return _dot_tex


static func _leaf() -> Texture2D:
	if _leaf_tex == null:
		var w := 32
		var h := 20
		var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
		for y in h:
			for x in w:
				var u := (x + 0.5) / w * 2.0 - 1.0
				var v := (y + 0.5) / h * 2.0 - 1.0
				var inside := u * u + v * v * (1.0 + 0.6 * u) < 0.85
				var vein := absf(v) < 0.08 and absf(u) < 0.8
				var c := Color(1, 1, 1) * (0.75 if vein else 1.0) * (0.85 + 0.15 * (1.0 - absf(v)))
				img.set_pixel(x, y, Color(c.r, c.g, c.b, 1.0 if inside else 0.0))
		_leaf_tex = ImageTexture.create_from_image(img)
	return _leaf_tex


static func _ray_t() -> Texture2D:
	if _ray_tex == null:
		var w := 32
		var h := 64
		var img := Image.create(w, h, false, Image.FORMAT_RGB8)
		for y in h:
			for x in w:
				var u := absf((x + 0.5) / w * 2.0 - 1.0)
				var v := (y + 0.5) / h
				var k := pow(clampf(1.0 - u, 0.0, 1.0), 1.6) * smoothstep(0.0, 0.35, v) * smoothstep(1.0, 0.7, v)
				img.set_pixel(x, y, Color(k, k, k))
		img.generate_mipmaps()
		_ray_tex = ImageTexture.create_from_image(img)
	return _ray_tex
