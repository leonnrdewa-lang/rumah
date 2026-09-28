class_name Fx
extends RefCounted
## Short-lived visual effects. Everything is spawned under `Fx.layer` (the current
## area's effect node) and frees itself.

static var layer: Node3D
static var _arc_cache := {}
static var _quad: QuadMesh


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


## Ground disc used for telegraphs (fill grows over `time`) and effect rings.
static func ring(pos: Vector3, radius: float, color: Color, time: float, fill := true, arc := TAU, facing := 0.0) -> MeshInstance3D:
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


## Crescent swipe of the gada. `dir` is the world facing, `sweep` flips direction.
static func slash(pos: Vector3, dir: Vector3, radius: float, arc: float, color: Color, sweep := 1.0) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = _arc_mesh(radius * 0.35, radius, arc)
	var m := Art.fx_mat(color.lerp(Color.WHITE, 0.25), 2.8)
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_add(mi, pos + Vector3(0, 0.9, 0))
	if not mi.is_inside_tree():
		return
	var yaw := atan2(dir.x, dir.z)
	mi.rotation.y = yaw - 0.35 * sweep
	mi.scale = Vector3(1, 1, sweep)
	var tw := mi.create_tween().set_parallel(true)
	tw.tween_property(mi, "rotation:y", yaw + 0.35 * sweep, 0.14)
	tw.tween_method(func(v): m.set_shader_parameter("alpha", v), 1.0, 0.0, 0.2)
	tw.chain().tween_callback(mi.queue_free)


static func burst(pos: Vector3, color: Color, amount := 14, speed := 5.0, size := 0.12, life := 0.45) -> void:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = false
	p.amount = amount
	p.lifetime = life
	p.explosiveness = 0.95
	p.direction = Vector3(0, 1, 0)
	p.spread = 80.0
	p.initial_velocity_min = speed * 0.5
	p.initial_velocity_max = speed
	p.gravity = Vector3(0, -9, 0)
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.2
	var curve := Curve.new()
	curve.add_point(Vector2(0, 1))
	curve.add_point(Vector2(1, 0))
	p.scale_amount_curve = curve
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	p.mesh = q
	p.particle_flag_align_y = false
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	bm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	bm.albedo_color = color * 2.0
	bm.vertex_color_use_as_albedo = false
	q.material = bm
	_add(p, pos)
	if not p.is_inside_tree():
		return
	p.emitting = true
	p.get_tree().create_timer(life + 0.2).timeout.connect(p.queue_free)


static func number(pos: Vector3, value: float, color := Color(1, 0.95, 0.8), big := false) -> void:
	var l := Label3D.new()
	l.text = str(int(round(value)))
	l.font = preload("res://assets/fonts/Cinzel.ttf")
	l.font_size = 64 if big else 44
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
	var tw := l.create_tween().set_parallel(true)
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


## Jagged lightning bolt between two points.
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


## Expanding shock ring (explosions, slams, waves).
static func shock(pos: Vector3, radius: float, color: Color, time := 0.35) -> void:
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


## A glowing orb mesh (projectile visual / pickups).
static func orb(color: Color, radius := 0.25) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = radius
	s.height = radius * 2.0
	s.radial_segments = 12
	s.rings = 6
	mi.mesh = s
	mi.material_override = Art.fx_mat(color, 2.4)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


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
	q.size = Vector2(size, size)
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	bm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	bm.albedo_color = color * 1.6
	q.material = bm
	p.mesh = q
	return p
