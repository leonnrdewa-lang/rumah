class_name Fx
extends RefCounted
## Short-lived visual effects. Everything is spawned under `Fx.layer` (the current
## area's effect node) and frees itself. Painted VFX sprites (slash, beam, impact,
## magic circle, fire, splash, shockwave, lightning, wind, danger ring, smoke,
## shards) come from the Higgsfield pack (`Hf.fx_tex`); without it a procedural
## stand-in of the same shape is generated once.

const TEX_SHADER := preload("res://shaders/fx_tex.gdshader")
const GOLD := Color(1.0, 0.82, 0.42)

static var layer: Node3D
static var _arc_cache := {}
static var _quad: QuadMesh
static var _flat_q: QuadMesh
static var _bill_q: QuadMesh
static var _tex_cache := {}
static var _box: BoxMesh


static func _add(n: Node3D, pos: Vector3) -> void:
	if layer == null or not is_instance_valid(layer):
		n.queue_free()
		return
	layer.add_child(n)
	n.global_position = pos


static func _flat_quad() -> QuadMesh:
	if _quad == null:
		_quad = QuadMesh.new()
		_quad.size = Vector2(2, 2)
		_quad.orientation = PlaneMesh.FACE_Y
	return _quad


static func _flat_unit() -> QuadMesh:
	if _flat_q == null:
		_flat_q = QuadMesh.new()
		_flat_q.size = Vector2(1, 1)
		_flat_q.orientation = PlaneMesh.FACE_Y
	return _flat_q


static func _bill_unit() -> QuadMesh:
	if _bill_q == null:
		_bill_q = QuadMesh.new()
		_bill_q.size = Vector2(1, 1)
	return _bill_q


# --- painted sprites --------------------------------------------------------------

static func tex(name: String) -> Texture2D:
	var t: Texture2D = Hf.fx_tex(name)
	if t:
		return t
	if not _tex_cache.has(name):
		_tex_cache[name] = _make_tex(name)
	return _tex_cache[name]


static func tex_mat(name: String, color := Color.WHITE, intensity := 1.6, tint := 0.3, billboard := 0.0) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = TEX_SHADER
	m.set_shader_parameter("tex", tex(name))
	m.set_shader_parameter("color", color)
	m.set_shader_parameter("intensity", intensity)
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("billboard", billboard)
	return m


## Animated painted sprite. Options: flat (lie on the ground, else face the camera),
## dir (flat: image top points along dir), yaw, from/grow (start/end scale),
## spin (radians over life), stretch (Vector2), tint, intensity, hold (0..1 of life
## at full brightness), billboard (1 camera, 2 upright), parent (attach instead of
## the effect layer, local position).
static func sprite(name: String, pos: Vector3, size: float, color := Color.WHITE, life := 0.4, o := {}) -> MeshInstance3D:
	var flat: bool = o.get("flat", false)
	var mi := MeshInstance3D.new()
	mi.mesh = _flat_unit() if flat else _bill_unit()
	var m := tex_mat(name, color, float(o.get("intensity", 1.7)), float(o.get("tint", 0.3)), 0.0 if flat else float(o.get("billboard", 1.0)))
	m.set_shader_parameter("alpha", 0.0)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var parent: Node3D = o.get("parent", null)
	if parent:
		parent.add_child(mi)
		mi.position = pos
	else:
		_add(mi, pos)
	if not mi.is_inside_tree():
		return mi
	var base := Basis.IDENTITY
	if flat:
		var dir: Vector3 = o.get("dir", Vector3.ZERO)
		dir.y = 0
		if dir.length() > 0.01:
			base = Basis.looking_at(dir.normalized(), Vector3.UP)
		else:
			base = Basis(Vector3.UP, float(o.get("yaw", randf() * TAU)))
	var st: Vector2 = o.get("stretch", Vector2.ONE)
	var s0: float = o.get("from", 0.6)
	var s1: float = o.get("grow", 1.0)
	var spin: float = o.get("spin", 0.0)
	var hold: float = o.get("hold", 0.25)
	var fade_in: float = o.get("fade_in", 0.08)
	var upd := func(t: float):
		var k := s0 + (s1 - s0) * (1.0 - pow(1.0 - t, 3.0))
		if flat:
			mi.basis = Basis(Vector3.UP, spin * t) * base * Basis.from_scale(Vector3(size * st.x * k, 1.0, size * st.y * k))
		else:
			mi.scale = Vector3(size * st.x * k, size * st.y * k, 1.0)
			m.set_shader_parameter("uv_rot", spin * t)
		var a := clampf(t / max(fade_in, 0.001), 0.0, 1.0) * (1.0 - smoothstep(hold, 1.0, t))
		m.set_shader_parameter("alpha", a)
	upd.call(0.0)
	var tw := mi.create_tween()
	tw.tween_method(upd, 0.0, 1.0, life)
	tw.tween_callback(mi.queue_free)
	return mi


## Short-lived point light that fades out (muzzle flash, explosions, laser).
static func light(pos: Vector3, color: Color, energy := 3.0, rng := 6.0, time := 0.25) -> void:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = rng
	l.shadow_enabled = false
	_add(l, pos)
	if not l.is_inside_tree():
		return
	var tw := l.create_tween()
	tw.tween_property(l, "light_energy", 0.0, time).set_ease(Tween.EASE_IN)
	tw.tween_callback(l.queue_free)


## Ground disc used for telegraphs (fill grows over `time`) and effect rings.
## `danger` adds the painted demonic danger ring spinning on top.
static func ring(pos: Vector3, radius: float, color: Color, time: float, fill := true, arc := TAU, facing := 0.0, danger := false) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _flat_quad()
	var m := Art.ring_mat(color)
	m.set_shader_parameter("arc", arc)
	mi.material_override = m
	mi.scale = Vector3(radius, 1, radius)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_add(mi, pos + Vector3(0, 0.04, 0))
	if not mi.is_inside_tree():
		return mi
	mi.rotation.y = facing
	if danger and arc >= TAU - 0.01:
		var d := MeshInstance3D.new()
		d.mesh = _flat_unit()
		var dm := tex_mat("danger", color, 1.3, 0.35)
		dm.set_shader_parameter("spin_speed", 0.9)
		d.material_override = dm
		d.scale = Vector3(2.15, 1, 2.15)
		d.position.y = 0.01
		d.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.add_child(d)
		dm.set_shader_parameter("alpha", 0.0)
		d.create_tween().tween_method(func(v): dm.set_shader_parameter("alpha", v), 0.2, 1.2, time)
	var tw := mi.create_tween()
	if fill:
		tw.tween_method(func(v): m.set_shader_parameter("fill", v), 0.0, 1.0, time)
	else:
		m.set_shader_parameter("fill", 1.0)
		tw.tween_method(func(v): m.set_shader_parameter("alpha", v), 1.0, 0.0, time)
	tw.tween_callback(mi.queue_free)
	return mi


static func _arc_mesh(inner: float, outer: float, arc: float) -> ArrayMesh:
	var key := "%s|%s|%s" % [inner, outer, arc]
	if _arc_cache.has(key):
		return _arc_cache[key]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 18
	for i in n:
		var a0 := -arc * 0.5 + arc * i / n
		var a1 := -arc * 0.5 + arc * (i + 1) / n
		var f0 := float(i) / n
		var f1 := float(i + 1) / n
		var c0 := Color(1, 1, 1, sin(f0 * PI) * (0.4 + 0.6 * f0))
		var c1 := Color(1, 1, 1, sin(f1 * PI) * (0.4 + 0.6 * f1))
		var pi0 := Vector3(sin(a0) * inner, 0, cos(a0) * inner)
		var po0 := Vector3(sin(a0) * outer, 0, cos(a0) * outer)
		var pi1 := Vector3(sin(a1) * inner, 0, cos(a1) * inner)
		var po1 := Vector3(sin(a1) * outer, 0, cos(a1) * outer)
		for v in [[pi0, c0 * Color(1, 1, 1, 0.2)], [po0, c0], [po1, c1], [pi0, c0 * Color(1, 1, 1, 0.2)], [po1, c1], [pi1, c1 * Color(1, 1, 1, 0.2)]]:
			st.set_color(v[1])
			st.add_vertex(v[0])
	var m := st.commit()
	_arc_cache[key] = m
	return m


## Staff swipe: a painted crescent sweeping across `arc`, a bright ink-sharp arc
## on top and sparks flying off the tip. `sweep` flips the direction.
static func slash(pos: Vector3, dir: Vector3, radius: float, arc: float, color: Color, sweep := 1.0) -> void:
	dir.y = 0
	dir = dir.normalized()
	sprite("slash", pos + Vector3(0, 0.95, 0) + dir * radius * 0.2, radius * 2.3, color, 0.24,
		{"flat": true, "dir": dir, "from": 0.8, "grow": 1.08, "stretch": Vector2(sweep, 1.0), "spin": -0.5 * sweep, "tint": 0.3, "intensity": 2.1, "hold": 0.3})
	var mi := MeshInstance3D.new()
	mi.mesh = _arc_mesh(radius * 0.72, radius, arc)
	var m := Art.fx_mat(color.lerp(Color.WHITE, 0.55), 3.4)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_add(mi, pos + Vector3(0, 1.0, 0))
	if mi.is_inside_tree():
		var yaw := atan2(dir.x, dir.z)
		mi.rotation.y = yaw - 0.45 * sweep
		mi.scale = Vector3(1, 1, sweep)
		var tw := mi.create_tween().set_parallel(true)
		tw.tween_property(mi, "rotation:y", yaw + 0.45 * sweep, 0.12)
		tw.tween_method(func(v): m.set_shader_parameter("alpha", v), 1.0, 0.0, 0.18)
		tw.chain().tween_callback(mi.queue_free)
	var side := dir.cross(Vector3.UP) * sweep
	sparks(pos + Vector3(0, 1.0, 0) + dir * radius * 0.8 - side * radius * 0.5, color, 10, 7.0, dir + side * 0.6)


## Hit spark: painted starburst, flying shards and a quick light.
static func impact(pos: Vector3, color: Color, big := false) -> void:
	var s := 2.6 if big else 1.5
	sprite("impact", pos, s, color, 0.16 if not big else 0.24, {"from": 0.45, "grow": 1.15, "spin": randf_range(-0.8, 0.8), "tint": 0.25, "intensity": 2.4, "hold": 0.2})
	sprite("shards", pos, s * 1.4, color, 0.32, {"from": 0.4, "grow": 1.2, "tint": 0.35, "intensity": 1.8, "hold": 0.1})
	burst(pos, color, 12 if big else 7, 7.0 if big else 5.0, 0.13, 0.35)
	if big:
		light(pos, color, 3.0, 5.0, 0.2)


## Directional spark spray.
static func sparks(pos: Vector3, color: Color, amount := 10, speed := 6.0, dir := Vector3.UP) -> void:
	var p := _particles(color, amount, 0.35, 0.1, "shards")
	p.direction = dir.normalized() if dir.length() > 0.01 else Vector3.UP
	p.spread = 35.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, -6, 0)
	_fire_particles(p, pos, 0.35)


static func _particles(color: Color, amount: int, life: float, size: float, tex_name := "") -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = false
	p.amount = amount
	p.lifetime = life
	p.explosiveness = 0.95
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.3
	var curve := Curve.new()
	curve.add_point(Vector2(0, 1))
	curve.add_point(Vector2(1, 0))
	p.scale_amount_curve = curve
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	bm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	bm.albedo_color = color * 2.0
	if tex_name != "":
		bm.albedo_texture = tex(tex_name)
		bm.albedo_color = color.lerp(Color.WHITE, 0.3) * 2.2
	q.material = bm
	p.mesh = q
	return p


static func _fire_particles(p: CPUParticles3D, pos: Vector3, life: float) -> void:
	_add(p, pos)
	if not p.is_inside_tree():
		return
	p.emitting = true
	p.get_tree().create_timer(life + 0.3).timeout.connect(p.queue_free)


static func burst(pos: Vector3, color: Color, amount := 14, speed := 5.0, size := 0.12, life := 0.45) -> void:
	var p := _particles(color, amount, life, size * 2.2, "impact")
	p.direction = Vector3(0, 1, 0)
	p.spread = 80.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, -9, 0)
	_fire_particles(p, pos, life)


## Chunks of earth/stone thrown up by slams (lit, not additive).
static func debris(pos: Vector3, color := Color(0.42, 0.34, 0.28), amount := 14, speed := 8.0) -> void:
	if _box == null:
		_box = BoxMesh.new()
		_box.size = Vector3(0.16, 0.12, 0.14)
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = false
	p.amount = amount
	p.lifetime = 0.9
	p.explosiveness = 1.0
	p.mesh = _box
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_box.material = mat
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 0.8
	p.direction = Vector3.UP
	p.spread = 55.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, -24, 0)
	p.angular_velocity_min = -400.0
	p.angular_velocity_max = 400.0
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.8
	_fire_particles(p, pos + Vector3(0, 0.2, 0), 0.9)


## Soft painted dust clouds rolling outward (slams, landings, dashes).
static func dust(pos: Vector3, radius := 1.5, color := Color(0.75, 0.65, 0.55)) -> void:
	for i in 4:
		var a := randf() * TAU
		var off := Vector3(cos(a), 0, sin(a)) * radius * randf_range(0.3, 0.8)
		sprite("smoke", pos + off + Vector3(0, 0.5, 0), radius * randf_range(0.9, 1.3), color, randf_range(0.5, 0.8),
			{"from": 0.5, "grow": 1.5, "tint": 0.85, "intensity": 0.55, "spin": randf_range(-1, 1), "hold": 0.1})


static func number(pos: Vector3, value: float, color := Color(1, 0.95, 0.8), big := false) -> void:
	var l := Label3D.new()
	l.text = str(int(round(value)))
	l.font = preload("res://assets/fonts/Cinzel.ttf")
	l.font_size = 72 if big else 44
	l.outline_size = 14
	l.outline_modulate = Color(0.05, 0.03, 0.05)
	l.modulate = color
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.pixel_size = 0.008
	l.fixed_size = false
	_add(l, pos + Vector3(randf_range(-0.3, 0.3), 2.0, 0))
	if not l.is_inside_tree():
		return
	l.scale = Vector3.ONE * (1.8 if big else 1.4)
	var tw := l.create_tween().set_parallel(true)
	tw.tween_property(l, "scale", Vector3.ONE, 0.12).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "position:y", l.position.y + 0.9, 0.6).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tw.tween_property(l, "modulate:a", 0.0, 0.25).set_delay(0.4)
	tw.chain().tween_callback(l.queue_free)


static func text(pos: Vector3, s: String, color := Color(1, 0.95, 0.8)) -> void:
	var l := Label3D.new()
	l.text = s
	l.font = preload("res://assets/fonts/Cinzel.ttf")
	l.font_size = 40
	l.outline_size = 12
	l.outline_modulate = Color(0.05, 0.03, 0.05)
	l.modulate = color
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.pixel_size = 0.008
	_add(l, pos + Vector3(0, 2.4, 0))
	if not l.is_inside_tree():
		return
	var tw := l.create_tween().set_parallel(true)
	tw.tween_property(l, "position:y", l.position.y + 0.7, 0.9)
	tw.tween_property(l, "modulate:a", 0.0, 0.3).set_delay(0.7)
	tw.chain().tween_callback(l.queue_free)


## Jagged lightning bolt between two points, with a painted bolt and flash.
static func bolt(a: Vector3, b: Vector3, color := Color("b784ff")) -> void:
	var im := ImmediateMesh.new()
	var mi := MeshInstance3D.new()
	mi.mesh = im
	var m := Art.fx_mat(color, 3.0)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var segs := 8
	var pts: Array[Vector3] = []
	for i in segs + 1:
		var f := float(i) / segs
		var q := a.lerp(b, f)
		if i > 0 and i < segs:
			q += Vector3(randf_range(-0.35, 0.35), randf_range(-0.2, 0.3), randf_range(-0.35, 0.35))
		pts.append(q)
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in segs:
		var p0 := pts[i]
		var p1 := pts[i + 1]
		var side := (p1 - p0).cross(Vector3.UP).normalized() * 0.09
		var up := Vector3(0, 0.09, 0)
		for off in [side, up]:
			im.surface_set_color(Color(1, 1, 1, 1))
			im.surface_add_vertex(p0 - off)
			im.surface_add_vertex(p0 + off)
			im.surface_add_vertex(p1 + off)
			im.surface_add_vertex(p0 - off)
			im.surface_add_vertex(p1 + off)
			im.surface_add_vertex(p1 - off)
	im.surface_end()
	if layer == null or not is_instance_valid(layer):
		return
	layer.add_child(mi)
	var tw := mi.create_tween()
	tw.tween_method(func(v): m.set_shader_parameter("alpha", v), 1.0, 0.0, 0.25)
	tw.tween_callback(mi.queue_free)
	if absf(a.y - b.y) > 3.0:
		lightning(b, absf(a.y - b.y), color)
	else:
		impact(b, color)


## Painted lightning strike standing upright on `pos`.
static func lightning(pos: Vector3, height := 8.0, color := Color("b784ff")) -> void:
	sprite("lightning", pos + Vector3(0, height * 0.5, 0), height * 0.32, color, 0.3,
		{"billboard": 2.0, "stretch": Vector2(1.0, 3.1), "from": 1.0, "grow": 1.0, "tint": 0.3, "intensity": 2.6, "hold": 0.35, "fade_in": 0.02})
	sprite("impact", pos + Vector3(0, 0.3, 0), 2.4, color, 0.25, {"from": 0.5, "grow": 1.2, "tint": 0.4, "intensity": 2.2})
	light(pos + Vector3(0, 2, 0), color, 5.0, 8.0, 0.3)


## Expanding shockwave (explosions, slams, waves): painted ring + crisp edge.
static func shock(pos: Vector3, radius: float, color: Color, time := 0.35, heavy := false) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = _flat_quad()
	var m := Art.ring_mat(color)
	m.set_shader_parameter("fill", 0.0)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.scale = Vector3(0.2, 1, 0.2)
	_add(mi, pos + Vector3(0, 0.06, 0))
	if not mi.is_inside_tree():
		return
	var tw := mi.create_tween().set_parallel(true)
	tw.tween_property(mi, "scale", Vector3(radius, 1, radius), time).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tw.tween_method(func(v): m.set_shader_parameter("alpha", v), 1.4, 0.0, time)
	tw.chain().tween_callback(mi.queue_free)
	sprite("shock", pos + Vector3(0, 0.08, 0), radius * 2.4, color, time * 1.4,
		{"flat": true, "from": 0.15, "grow": 1.0, "tint": 0.4, "intensity": 1.9, "hold": 0.3, "spin": 0.4})
	if heavy:
		debris(pos, Color(0.4, 0.33, 0.27), int(clamp(radius * 5.0, 8, 26)), 6.0 + radius * 1.2)
		dust(pos, radius * 0.8)
		light(pos + Vector3(0, 1, 0), color, 3.5, radius * 3.0, 0.3)


## Rotating painted magic circle on the ground (Ajian, summons, boss casts).
static func magic_circle(pos: Vector3, radius: float, color: Color, life := 1.0, spin := 1.5) -> MeshInstance3D:
	return sprite("circle", pos + Vector3(0, 0.07, 0), radius * 2.1, color, life,
		{"flat": true, "from": 0.3, "grow": 1.0, "spin": spin, "tint": 0.45, "intensity": 1.8, "hold": 0.7, "fade_in": 0.12})


static func fire(pos: Vector3, size := 1.6, color := Color(1.0, 0.5, 0.15)) -> void:
	sprite("fire", pos, size, color, 0.45, {"from": 0.5, "grow": 1.3, "spin": randf_range(-1.5, 1.5), "tint": 0.15, "intensity": 2.0, "hold": 0.2})
	light(pos, color, 3.0, size * 3.5, 0.35)


static func splash(pos: Vector3, size := 2.0, color := Color(0.55, 0.85, 1.0)) -> void:
	sprite("splash", pos + Vector3(0, 0.15, 0), size, color, 0.5, {"flat": true, "from": 0.35, "grow": 1.25, "tint": 0.2, "intensity": 1.8, "hold": 0.25})
	sprite("splash", pos + Vector3(0, size * 0.35, 0), size * 0.8, color, 0.45, {"from": 0.4, "grow": 1.2, "tint": 0.2, "intensity": 1.4, "spin": 0.6})
	var p := _particles(color, 18, 0.6, 0.18, "splash")
	p.direction = Vector3.UP
	p.spread = 40.0
	p.initial_velocity_min = 5.0
	p.initial_velocity_max = 9.0
	p.gravity = Vector3(0, -20, 0)
	_fire_particles(p, pos, 0.6)


static func smoke(pos: Vector3, size := 1.6, color := Color(0.6, 0.35, 0.8)) -> void:
	sprite("smoke", pos, size, color, 0.7, {"from": 0.5, "grow": 1.5, "tint": 0.4, "intensity": 1.0, "spin": randf_range(-1, 1), "hold": 0.1})


## Wind swirl (dash, Bayu).
static func wind(pos: Vector3, size := 2.0, color := Color(0.75, 1.0, 0.95)) -> void:
	sprite("wind", pos + Vector3(0, 0.1, 0), size, color, 0.4, {"flat": true, "from": 0.4, "grow": 1.2, "spin": 3.0, "tint": 0.3, "intensity": 1.5, "hold": 0.2})


## The extending staff's laser: a painted beam from `from` along `dir`, shooting
## out to `length` in `extend` seconds, holding, then collapsing. Returns the
## root so callers can attach more (the staff itself).
static func laser(from: Vector3, dir: Vector3, length: float, width: float, color: Color, time := 0.45, extend := 0.09) -> Node3D:
	dir.y = 0
	dir = dir.normalized()
	var root := Node3D.new()
	_add(root, from)
	if not root.is_inside_tree():
		return root
	root.basis = Basis.looking_at(dir, Vector3.UP)
	var mats: Array[ShaderMaterial] = []
	for layer_spec in [[width, "beam", 0.25, 2.2, 1.0], [width * 0.34, "beam", 0.85, 3.2, 1.7]]:
		var mi := MeshInstance3D.new()
		mi.mesh = _flat_unit()
		var m := tex_mat(layer_spec[1], color if layer_spec[2] < 0.5 else Color(1, 0.97, 0.9), layer_spec[3], layer_spec[2])
		m.set_shader_parameter("wrap_u", 1.0)
		m.set_shader_parameter("uv_scale", Vector2(length / 7.0, 1.0))
		m.set_shader_parameter("edge_fade", 0.08)
		mi.material_override = m
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# quad lies in XZ; turn it so its U axis runs along -Z (the beam direction)
		mi.basis = Basis(Vector3.UP, PI / 2) * Basis.from_scale(Vector3(length, 1.0, layer_spec[0] * layer_spec[4]))
		mi.position = Vector3(0, 0, -length * 0.5)
		root.add_child(mi)
		mats.append(m)
	# origin flare and tip flare
	sprite("impact", Vector3.ZERO, width * 2.2, color, time, {"parent": root, "from": 0.6, "grow": 1.1, "spin": 2.0, "tint": 0.3, "intensity": 2.4, "hold": 0.6})
	var tip := sprite("impact", Vector3(0, 0, -length), width * 1.8, color, time, {"parent": root, "from": 0.8, "grow": 1.2, "spin": -2.5, "tint": 0.3, "intensity": 2.4, "hold": 0.6})
	# sparks raining off the whole length
	var p := _particles(color, 36, 0.4, 0.14, "shards")
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	p.emission_box_extents = Vector3(0.15, 0.1, length * 0.5)
	p.position = Vector3(0, 0, -length * 0.5)
	p.direction = Vector3.UP
	p.spread = 70.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 6.0
	p.gravity = Vector3(0, -8, 0)
	p.explosiveness = 0.2
	p.one_shot = false
	root.add_child(p)
	p.emitting = true
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = 4.0
	l.omni_range = length * 0.6
	l.position = Vector3(0, 0.5, -length * 0.5)
	root.add_child(l)
	root.scale = Vector3(1, 1, 0.02)
	var tw := root.create_tween()
	tw.tween_property(root, "scale", Vector3.ONE, extend).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_EXPO)
	tw.tween_method(func(v: float):
		for m in mats:
			m.set_shader_parameter("uv_offset", Vector2(-v * 3.0, 0.0))
	, 0.0, 1.0, time - extend)
	tw.tween_callback(func(): p.emitting = false)
	tw.tween_method(func(v: float):
		for m in mats:
			m.set_shader_parameter("alpha", v)
		l.light_energy = 4.0 * v
		root.scale = Vector3(maxf(v, 0.03), maxf(v, 0.03), 1.0)
	, 1.0, 0.0, 0.16)
	tw.tween_callback(root.queue_free)
	return root


## A glowing orb (projectile visual / pickups): painted, spinning.
static func orb(color: Color, radius := 0.25, tex_name := "") -> Node3D:
	var root := Node3D.new()
	var mi := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = radius * 0.6
	s.height = radius * 1.2
	s.radial_segments = 12
	s.rings = 6
	mi.mesh = s
	mi.material_override = Art.fx_mat(color, 2.4)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mi)
	var g := MeshInstance3D.new()
	g.mesh = _bill_unit()
	var gm := tex_mat(tex_name if tex_name != "" else "impact", color, 2.0, 0.3 if tex_name != "" else 0.5, 1.0)
	gm.set_shader_parameter("spin_speed", 4.0)
	g.material_override = gm
	g.scale = Vector3.ONE * radius * (5.5 if tex_name != "" else 4.0)
	g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(g)
	return root


static func trail(color: Color, size := 0.18) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = 18
	p.lifetime = 0.35
	p.local_coords = false
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 0.2
	p.initial_velocity_max = 0.8
	p.gravity = Vector3.ZERO
	var curve := Curve.new()
	curve.add_point(Vector2(0, 1))
	curve.add_point(Vector2(1, 0))
	p.scale_amount_curve = curve
	var q := QuadMesh.new()
	q.size = Vector2(size * 2.0, size * 2.0)
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	bm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	bm.albedo_texture = tex("smoke")
	bm.albedo_color = color * 2.2
	q.material = bm
	p.mesh = q
	return p


# --- procedural stand-ins for the painted sprites ----------------------------------

static func _make_tex(name: String) -> Texture2D:
	var n := 96
	var img := Image.create(n, n, false, Image.FORMAT_RGB8)
	var cols := {
		"slash": Color(1.0, 0.88, 0.55), "circle": Color(0.45, 1.0, 0.95), "beam": Color(1.0, 0.8, 0.4),
		"impact": Color(1.0, 0.92, 0.7), "fire": Color(1.0, 0.5, 0.2), "splash": Color(0.55, 0.9, 1.0),
		"shock": Color(1.0, 0.7, 0.4), "lightning": Color(0.8, 0.65, 1.0), "wind": Color(0.75, 1.0, 0.95),
		"danger": Color(1.0, 0.2, 0.15), "smoke": Color(0.6, 0.5, 0.7), "shards": Color(1.0, 0.95, 0.8),
	}
	var base: Color = cols.get(name, Color.WHITE)
	for y in n:
		for x in n:
			var u := (x + 0.5) / n * 2.0 - 1.0
			var v := (y + 0.5) / n * 2.0 - 1.0
			var r := sqrt(u * u + v * v)
			var a := atan2(u, -v)
			var k := 0.0
			match name:
				"slash":
					var band := 1.0 - absf(r - 0.72) / 0.2
					k = clampf(band, 0.0, 1.0) * clampf(1.0 - absf(a) / 1.3, 0.0, 1.0) * (0.6 + 0.4 * clampf(-v, 0.0, 1.0))
				"circle", "danger":
					k = _ringk(r, 0.9, 0.03) + _ringk(r, 0.66, 0.02) * 0.8 + (0.5 if absf(sin(a * 8.0)) > 0.97 and r > 0.68 and r < 0.88 else 0.0)
				"shock":
					k = clampf(1.0 - absf(r - 0.8) / 0.16, 0.0, 1.0)
				"beam":
					k = pow(clampf(1.0 - absf(v) / 0.5, 0.0, 1.0), 2.2) + pow(clampf(1.0 - absf(v) / 0.12, 0.0, 1.0), 2.0)
				"impact", "shards":
					var spikes := pow(absf(cos(a * 4.0)), 18.0) * clampf(1.0 - r, 0.0, 1.0)
					k = spikes + pow(clampf(1.0 - r / 0.35, 0.0, 1.0), 2.0)
				"lightning":
					var cx := sin(v * 9.0) * 0.12 + sin(v * 23.0) * 0.05
					k = pow(clampf(1.0 - absf(u - cx) / 0.12, 0.0, 1.0), 2.0)
				"wind":
					k = clampf(1.0 - absf(fmod(a + r * 7.0 + TAU * 4.0, TAU / 3.0) - 1.0) / 0.4, 0.0, 1.0) * clampf(1.0 - r, 0.0, 1.0)
				_:
					k = pow(clampf(1.0 - r, 0.0, 1.0), 1.6)
			k = clampf(k, 0.0, 1.0)
			var c := base * k + Color(1, 1, 1) * pow(k, 4.0) * 0.6
			img.set_pixel(x, y, Color(c.r, c.g, c.b))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


static func _ringk(r: float, at: float, w: float) -> float:
	return clampf(1.0 - absf(r - at) / w, 0.0, 1.0)
