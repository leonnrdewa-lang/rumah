extends Node3D
## Cheap ambient life around the camera, added by world.gd:
##   * a small flock of egrets flying over now and then (casting moving shadows)
##   * butterflies fluttering around flowers near the player (daytime)
##   * smoke from the pabrik chimney and steam from its front tank (in frame at its door)
##   * a few leaves drifting down
##   * fireflies around the player at night
##   * dust puffs at the player's feet when running
## Birds and butterflies are one MultiMesh each (wings flap in critter.gdshader);
## everything else is CPUParticles3D. About 8 draw calls in total.

const CRITTER_SHADER := preload("res://shaders/critter.gdshader")
const BUTTERFLY_COLORS := [Color("f08a3a"), Color("f4c542"), Color("fcf2dd"), Color("e0572a"), Color("b8c75e")]
const N_BUTTERFLIES := 7

var world: Node
var _t := 0.0
var _high := true
var _night := 0.0

var _flock: MultiMeshInstance3D
var _flock_vel := Vector3.ZERO
var _flock_life := 0.0
var _bird_timer := 1.0
var _bird_offsets: Array[Vector3] = []

var _flies: MultiMeshInstance3D
var _fly_state: Array = []     # [base: Vector3, phase: float, speed: float, goal: Vector3]
var _flowers := {}             # Vector2i(8 m cell) -> PackedVector3Array

var _smoke: Array[CPUParticles3D] = []
var _smoke_mat: StandardMaterial3D
var _steam_mat: StandardMaterial3D
var _leaves: CPUParticles3D
var _fireflies: CPUParticles3D
var _dust: CPUParticles3D
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.seed = 2024
	_index_flowers()
	_build_flock()
	_build_butterflies()
	_build_smoke()
	_build_leaves()
	_build_fireflies()
	_build_dust()


func set_quality(high: bool) -> void:
	_high = high
	if _leaves:
		_leaves.amount = 10 if high else 5
	if _fireflies:
		_fireflies.amount = 28 if high else 14


# ------------------------------------------------------------------ helpers
static func _soft_dot(size := 64, hard := 0.0) -> Texture2D:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	if hard > 0.0:
		g.add_point(hard, Color(1, 1, 1, 0.9))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = size
	t.height = size
	return t


static func _particle_material(tex: Texture2D, col: Color, unshaded := true, additive := false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = col
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED if unshaded else BaseMaterial3D.SHADING_MODE_PER_VERTEX
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if additive:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	return m


func _quad(size: float, mat: Material) -> QuadMesh:
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	q.material = mat
	return q


func _fade_ramp(c: Color, peak := 0.2) -> Gradient:
	var g := Gradient.new()
	g.set_color(0, Color(c.r, c.g, c.b, 0.0))
	g.set_color(1, Color(c.r, c.g, c.b, 0.0))
	g.add_point(peak, c)
	return g


func _focus() -> Vector3:
	if world == null:
		return Vector3.ZERO
	if world.state != "title" and world.player:
		return world.player.global_position
	return world.cam_rig.global_position


# ------------------------------------------------------------------ birds
func _bird_mesh() -> ArrayMesh:
	## A stylised egret: slim body (rigid, COLOR.a = 0) + two long wings (COLOR.a = 1).
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var body := Color(1, 1, 1, 0)
	var wing := Color(1, 1, 1, 1)
	var tris := [
		# body (a flattened diamond), nose +z
		[body, Vector3(0, 0.03, 0.34), Vector3(-0.06, 0, 0.0), Vector3(0.06, 0, 0.0)],
		[body, Vector3(0, 0.03, -0.3), Vector3(0.06, 0, 0.0), Vector3(-0.06, 0, 0.0)],
		[body, Vector3(0, 0.06, 0.05), Vector3(-0.06, 0, 0.0), Vector3(0, 0.03, 0.34)],
		[body, Vector3(0, 0.06, 0.05), Vector3(0, 0.03, 0.34), Vector3(0.06, 0, 0.0)],
		# tail fan
		[body, Vector3(0, 0.02, -0.22), Vector3(-0.08, 0, -0.4), Vector3(0.08, 0, -0.4)],
		# wings: inner + outer panel each side
		[wing, Vector3(-0.05, 0, 0.1), Vector3(-0.05, 0, -0.1), Vector3(-0.28, 0, 0.06)],
		[wing, Vector3(-0.28, 0, 0.06), Vector3(-0.05, 0, -0.1), Vector3(-0.5, 0, -0.08)],
		[wing, Vector3(0.05, 0, 0.1), Vector3(0.28, 0, 0.06), Vector3(0.05, 0, -0.1)],
		[wing, Vector3(0.28, 0, 0.06), Vector3(0.5, 0, -0.08), Vector3(0.05, 0, -0.1)],
	]
	for t in tris:
		st.set_color(t[0])
		st.set_normal(Vector3.UP)
		for k in range(1, 4):
			st.add_vertex(t[k])
	return st.commit()


func _build_flock() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CRITTER_SHADER
	mat.set_shader_parameter("flap_speed", 7.0)
	mat.set_shader_parameter("flap_amp", 0.75)
	mat.set_shader_parameter("flap_bias", 0.1)
	mat.set_shader_parameter("body_color", Color("f6f1e7"))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _bird_mesh()
	mm.instance_count = 5
	for i in 5:
		var row := ceilf(i / 2.0)
		var off := Vector3(((i % 2) * 2.0 - 1.0) * 0.9 * row, _rng.randf_range(-0.3, 0.3), -0.9 * row)
		_bird_offsets.append(off)
		mm.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ONE * 0.65), off))
		mm.set_instance_color(i, Color("f4efe4"))
	_flock = MultiMeshInstance3D.new()
	_flock.name = "Birds"
	_flock.multimesh = mm
	_flock.material_override = mat
	_flock.visible = false
	add_child(_flock)


func _launch_flock() -> void:
	var c := _focus()
	var dir := Vector3(_rng.randf_range(-1.0, 1.0), 0, _rng.randf_range(-1.0, 1.0))
	if dir.length() < 0.2:
		dir = Vector3(1, 0, -0.3)
	dir = dir.normalized()
	var speed := _rng.randf_range(5.0, 6.5)
	# (env fix round: the flock starts ~15 m out and passes a little north of the player,
	# in the upper half of the frame, so it shows up in most gameplay minutes, not once
	# every ~40 s far off screen)
	var start := c - dir * 15.0 + Vector3(dir.z, 0, -dir.x) * _rng.randf_range(-3.0, 3.0) + Vector3(0, 0, -3.0)
	# low over the fields: high birds pass right in front of the camera and look huge
	start.y = c.y + _rng.randf_range(3.2, 4.4)
	_flock.global_position = start
	_flock.look_at(start + dir, Vector3.UP, true)
	_flock_vel = dir * speed
	_flock_life = 32.0 / speed
	var n := _rng.randi_range(2, 5)
	_flock.multimesh.visible_instance_count = n
	_flock.visible = true


func _update_flock(delta: float) -> void:
	if _flock.visible and _flock.global_position.distance_to(_focus()) > 40.0:
		# the player jumped far away (sleep / teleport): send a new flock there soon
		_flock.visible = false
		_bird_timer = 0.8
	if _flock.visible:
		_flock_life -= delta
		_flock.global_position += _flock_vel * delta
		_flock.global_position.y += sin(_t * 0.8) * 0.15 * delta
		if _flock_life <= 0.0:
			_flock.visible = false
		return
	_bird_timer -= delta
	if _bird_timer <= 0.0:
		_bird_timer = _rng.randf_range(7.0, 13.0)
		if _night < 0.5:
			_launch_flock()


# ------------------------------------------------------------------ butterflies
func _index_flowers() -> void:
	if world == null:
		return
	var ug: Dictionary = world.layout.get("undergrowth", {})
	for m in ["flowers_white", "flowers_yellow"]:
		var arr: Array = ug.get(m, [])
		for k in range(0, arr.size() - 4, 5):
			var p := Vector3(arr[k], arr[k + 1], arr[k + 2])
			var key := Vector2i(floori(p.x / 8.0), floori(p.z / 8.0))
			if not _flowers.has(key):
				_flowers[key] = PackedVector3Array()
			_flowers[key].append(p)


func _flower_near(c: Vector3) -> Vector3:
	## a flower 3–12 m from c (or a random spot when there are none)
	for attempt in 6:
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(3.0, 12.0)
		var q := c + Vector3(cos(a) * r, 0, sin(a) * r)
		var list: PackedVector3Array = _flowers.get(Vector2i(floori(q.x / 8.0), floori(q.z / 8.0)), PackedVector3Array())
		if list.size() > 0:
			return list[_rng.randi_range(0, list.size() - 1)]
	var a2 := _rng.randf() * TAU
	var p := c + Vector3(cos(a2), 0, sin(a2)) * _rng.randf_range(3.0, 10.0)
	if world:
		p.y = world.height_at(p.x, p.z)
	return p


func _butterfly_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var body := Color(1, 1, 1, 0)
	var wing := Color(1, 1, 1, 1)
	var tris := [
		[body, Vector3(0, 0.01, 0.06), Vector3(-0.012, 0, -0.06), Vector3(0.012, 0, -0.06)],
		[wing, Vector3(-0.01, 0, 0.03), Vector3(-0.1, 0, 0.08), Vector3(-0.11, 0, -0.01)],
		[wing, Vector3(-0.01, 0, 0.03), Vector3(-0.11, 0, -0.01), Vector3(-0.01, 0, -0.02)],
		[wing, Vector3(-0.01, 0, -0.01), Vector3(-0.08, 0, -0.03), Vector3(-0.05, 0, -0.09)],
		[wing, Vector3(0.01, 0, 0.03), Vector3(0.11, 0, -0.01), Vector3(0.1, 0, 0.08)],
		[wing, Vector3(0.01, 0, 0.03), Vector3(0.01, 0, -0.02), Vector3(0.11, 0, -0.01)],
		[wing, Vector3(0.01, 0, -0.01), Vector3(0.05, 0, -0.09), Vector3(0.08, 0, -0.03)],
	]
	for t in tris:
		st.set_color(t[0])
		st.set_normal(Vector3.UP)
		for k in range(1, 4):
			st.add_vertex(t[k])
	return st.commit()


func _build_butterflies() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CRITTER_SHADER
	mat.set_shader_parameter("flap_speed", 22.0)
	mat.set_shader_parameter("flap_amp", 1.0)
	mat.set_shader_parameter("flap_bias", 0.45)
	mat.set_shader_parameter("body_color", Color("3a2a20"))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = _butterfly_mesh()
	mm.instance_count = N_BUTTERFLIES
	for i in N_BUTTERFLIES:
		mm.set_instance_color(i, BUTTERFLY_COLORS[i % BUTTERFLY_COLORS.size()])
		_fly_state.append([Vector3(1e6, 0, 1e6), _rng.randf() * TAU, _rng.randf_range(0.7, 1.3), Vector3(1e6, 0, 1e6)])
	_flies = MultiMeshInstance3D.new()
	_flies.name = "Butterflies"
	_flies.multimesh = mm
	_flies.material_override = mat
	_flies.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# instances move around the player, so never cull the whole set by its old AABB
	_flies.custom_aabb = AABB(Vector3(-500, -50, -500), Vector3(1000, 100, 1000))
	add_child(_flies)


func _update_butterflies(delta: float) -> void:
	_flies.visible = _night < 0.35
	if not _flies.visible:
		return
	var c := _focus()
	var mm := _flies.multimesh
	for i in N_BUTTERFLIES:
		var s: Array = _fly_state[i]
		var base: Vector3 = s[0]
		if Vector2(base.x - c.x, base.z - c.z).length() > 15.0:
			# left behind (off screen): jump to a flower near the player
			base = _flower_near(c)
			s[3] = base
		else:
			# otherwise drift over to the flower it picked
			base = base.move_toward(s[3], delta * 1.6)
		s[0] = base
		var ph: float = s[1]
		var sp: float = s[2]
		var tt := _t * sp + ph
		# lazy figure-eight loops over the flower with little hops
		var p := base + Vector3(sin(tt * 0.9) * 0.9 + sin(tt * 2.3) * 0.2, 0.35 + 0.25 * sin(tt * 1.7) + 0.12 * absf(sin(tt * 5.0)),
			sin(tt * 1.8) * 0.6 + cos(tt * 0.7) * 0.3)
		var vel := Vector3(cos(tt * 0.9) * 0.81 + cos(tt * 2.3) * 0.46, 0, cos(tt * 1.8) * 1.08 - sin(tt * 0.7) * 0.21)
		var yaw := atan2(vel.x, vel.z)
		var b := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * 1.6)
		mm.set_instance_transform(i, Transform3D(b, p))
		# every now and then fly off to another flower nearby
		if _rng.randf() < delta * 0.05:
			s[3] = _flower_near(base)


# ------------------------------------------------------------------ smoke
func _chimney_tops() -> Array[Vector3]:
	var out: Array[Vector3] = []
	if world == null or not world.building_nodes.has("pabrik"):
		return out
	var node: MeshInstance3D = world.building_nodes["pabrik"]
	if node.mesh == null:
		return out
	var faces := node.mesh.get_faces()
	if faces.is_empty():
		return out
	var top := -INF
	for v in faces:
		top = maxf(top, v.y)
	# cluster the highest vertices horizontally: one cluster per chimney
	var clusters: Array = []
	for v in faces:
		if v.y < top - 0.35:
			continue
		var found := false
		for cl in clusters:
			if Vector2(cl[0].x / cl[1] - v.x, cl[0].z / cl[1] - v.z).length() < 1.2:
				cl[0] += v
				cl[1] += 1
				found = true
				break
		if not found:
			clusters.append([v, 1])
	for cl in clusters:
		var p: Vector3 = cl[0] / float(cl[1])
		p.y = top
		out.append(node.global_transform * p)
		if out.size() >= 2:
			break
	# the chimney top is far above the gameplay camera (44 deg, 12 m), so the mill also
	# vents steam low at the front, which is in frame at the mill's door: from the
	# highest point (<= 5.5 m) within 2.5 m of the facade (the sterilizer tank top) and
	# from the highest point of the front centre (the fruit hopper), which the HUD's
	# corner pills never cover
	var stacks: Array[Vector2] = []
	for cl in clusters:
		stacks.append(Vector2(cl[0].x, cl[0].z) / float(cl[1]))
	var aabb := node.mesh.get_aabb()
	for centre_only in [false, true]:
		var v: Vector3 = _front_vent(faces, aabb, stacks, centre_only)
		if v.y > 2.0 and (out.is_empty() or (node.global_transform * v).distance_to(out[out.size() - 1]) > 1.5):
			out.append(node.global_transform * v)
	return out


func _front_vent(faces: PackedVector3Array, aabb: AABB, stacks: Array[Vector2], centre_only: bool) -> Vector3:
	## centre of the highest top (<= 5.5 m) within 2.5 m of the building's front face
	var front_z := aabb.end.z - 2.5
	var mid_x := aabb.get_center().x
	var best := Vector3(0, -INF, 0)
	for v in faces:
		if v.z < front_z or v.y > 5.5 or (centre_only and absf(v.x - mid_x) > 2.5):
			continue
		var near_stack := false
		for st in stacks:
			if Vector2(v.x, v.z).distance_to(st) < 2.0:
				near_stack = true
				break
		if not near_stack and v.y > best.y:
			best = v
	if best.y == -INF:
		return best
	var acc := Vector3.ZERO
	var n := 0
	for v in faces:
		if absf(v.y - best.y) < 0.05 and Vector2(v.x - best.x, v.z - best.z).length() < 1.6:
			acc += v
			n += 1
	return acc / float(n) if n > 0 else best


func _build_smoke() -> void:
	var tops := _chimney_tops()
	var tex := _soft_dot(64, 0.25)
	# unshaded, so both are tinted by the time of day every frame (v2 showed glowing
	# white orbs over the dark mill at night). The low steam gets its own, fainter
	# material: in daylight a full-white unshaded puff is brighter than anything around
	# it and read as a white blob in front of the hopper (fix round)
	_smoke_mat = _particle_material(tex, Color(1, 1, 1, 1))
	_steam_mat = _particle_material(_soft_dot(64), Color(1, 1, 1, 1))
	for top in tops:
		# the breeze blows south, towards the camera, so both the chimney plume and
		# the low steam drift into the gameplay frame
		var low: bool = top.y < 6.0
		var mat: StandardMaterial3D = _steam_mat if low else _smoke_mat
		var p := CPUParticles3D.new()
		p.name = "MillSteam" if low else "ChimneySmoke"
		p.amount = 11 if low else 24
		p.lifetime = 4.5 if low else 7.5
		p.mesh = _quad(1.1 if low else 1.0, mat)
		p.direction = Vector3.UP
		p.spread = 14.0
		p.initial_velocity_min = 0.7 if low else 1.0
		p.initial_velocity_max = 1.0 if low else 1.5
		# the low steam is bent over by the breeze, so it trails across the top of the frame
		# (westwards too: the tank sits right of the door, under the HUD's top-right pills)
		# (env fix round: the chimney plume bends over harder, so from the pulled-back camera
		# it trails over the mill into the top of the frame instead of rising out of it)
		p.gravity = Vector3(-0.45, 0.05, 1.3) if low else Vector3(0.35, 0.0, 1.3)
		p.damping_min = 0.1
		p.damping_max = 0.25
		p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		p.emission_sphere_radius = 0.3 if low else 0.25
		p.scale_amount_min = 1.0
		p.scale_amount_max = 1.4
		var curve := Curve.new()
		curve.add_point(Vector2(0, 0.45))
		curve.add_point(Vector2(1, 2.4 if low else 3.4))
		p.scale_amount_curve = curve
		p.color_ramp = _fade_ramp(Color(0.97, 0.96, 0.93, 0.45) if low else Color(0.93, 0.92, 0.88, 0.85), 0.2 if low else 0.14)
		p.local_coords = false
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(p)
		p.global_position = top + Vector3(0, 0.2, 0)
		# simulate ahead only once it sits on the chimney, so no puffs start at the origin
		p.preprocess = 5.0
		p.restart()
		_smoke.append(p)


# ------------------------------------------------------------------ leaves / fireflies / dust
func _leaf_texture() -> Texture2D:
	var img := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for y in 32:
		for x in 32:
			# a pointed leaf shape along the diagonal
			var u := (float(x) + 0.5) / 32.0 - 0.5
			var v := (float(y) + 0.5) / 32.0 - 0.5
			var a := (u + v) * 0.7071
			var b := (u - v) * 0.7071
			var w := 0.2 * (1.0 - pow(absf(a) / 0.48, 2.0))
			var inside := absf(b) < w and absf(a) < 0.48
			var vein := absf(b) < 0.018
			img.set_pixel(x, y, Color(0.85, 0.85, 0.8, 1.0) if vein and inside else (Color(1, 1, 1, 1) if inside else Color(1, 1, 1, 0)))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _build_leaves() -> void:
	_leaves = CPUParticles3D.new()
	_leaves.name = "FallingLeaves"
	var mat := _particle_material(_leaf_texture(), Color(1, 1, 1, 1), false)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	mat.alpha_scissor_threshold = 0.5
	_leaves.mesh = _quad(0.26, mat)
	_leaves.amount = 10
	_leaves.lifetime = 8.0
	_leaves.preprocess = 8.0
	_leaves.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	_leaves.emission_box_extents = Vector3(13, 0.5, 10)
	_leaves.direction = Vector3(1, -0.2, 0.3)
	_leaves.spread = 40.0
	_leaves.initial_velocity_min = 0.2
	_leaves.initial_velocity_max = 0.6
	_leaves.gravity = Vector3(0.25, -0.75, 0.1)
	_leaves.damping_min = 0.2
	_leaves.damping_max = 0.5
	_leaves.angular_velocity_min = -160.0
	_leaves.angular_velocity_max = 160.0
	_leaves.angle_min = 0.0
	_leaves.angle_max = 360.0
	var g := Gradient.new()
	g.set_color(0, Color("b8c75e"))
	g.set_color(1, Color("97865c"))
	g.add_point(0.5, Color("c7ba6b"))
	_leaves.color_initial_ramp = g
	_leaves.local_coords = false
	_leaves.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_leaves)


func _build_fireflies() -> void:
	_fireflies = CPUParticles3D.new()
	_fireflies.name = "Fireflies"
	var mat := _particle_material(_soft_dot(32, 0.25), Color(1, 1, 1, 1), true, true)
	_fireflies.mesh = _quad(0.22, mat)
	_fireflies.amount = 28
	_fireflies.lifetime = 4.0
	_fireflies.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	_fireflies.emission_box_extents = Vector3(11, 0.8, 8)
	_fireflies.direction = Vector3.UP
	_fireflies.spread = 180.0
	_fireflies.initial_velocity_min = 0.1
	_fireflies.initial_velocity_max = 0.45
	_fireflies.gravity = Vector3(0, 0.05, 0)
	_fireflies.color_ramp = _fade_ramp(Color(0.85, 1.0, 0.45, 1.0), 0.5)
	_fireflies.local_coords = false
	_fireflies.emitting = false
	_fireflies.visible = false
	_fireflies.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_fireflies)


func _build_dust() -> void:
	_dust = CPUParticles3D.new()
	_dust.name = "RunDust"
	var mat := _particle_material(_soft_dot(32, 0.2), Color(1, 1, 1, 1), false)
	_dust.mesh = _quad(0.55, mat)
	_dust.amount = 16
	_dust.lifetime = 0.7
	_dust.direction = Vector3(0, 1, 0)
	_dust.spread = 60.0
	_dust.initial_velocity_min = 0.4
	_dust.initial_velocity_max = 0.9
	_dust.gravity = Vector3(0, 0.3, 0)
	_dust.damping_min = 1.5
	_dust.damping_max = 2.5
	_dust.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	_dust.emission_sphere_radius = 0.15
	var curve := Curve.new()
	curve.add_point(Vector2(0, 0.5))
	curve.add_point(Vector2(1, 1.6))
	_dust.scale_amount_curve = curve
	_dust.color_ramp = _fade_ramp(Color(0.88, 0.8, 0.62, 0.85), 0.12)
	_dust.local_coords = false
	_dust.emitting = false
	_dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_dust)


# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	if world == null:
		return
	_t += delta
	_night = float(world.get("night_k"))
	var c := _focus()
	_update_flock(delta)
	if _night > 0.45:
		_flock.visible = false
	_update_butterflies(delta)
	if _smoke_mat:
		# day: soft cream smoke; night: a faint cool grey wisp in the dark
		_smoke_mat.albedo_color = Color(0.95, 0.95, 0.93, 0.95).lerp(Color(0.2, 0.23, 0.32, 0.45), _night)
		# the low steam in the gameplay frame: a thin haze about as bright as the sunlit
		# walls behind it (V ~0.8), not a white glow (fix round 3: fainter, fewer and
		# smaller puffs; at the closer camera it still read as a pale blob on the hopper)
		# (env fix round: at 0.34 x the ramp it was invisible in the showcase frames; a soft
		# cream haze a little brighter than the walls now, still well below a white glow)
		_steam_mat.albedo_color = Color(0.9, 0.91, 0.88, 0.6).lerp(Color(0.2, 0.23, 0.32, 0.3), _night)
	_leaves.global_position = c + Vector3(0, 7.5, -2.0)
	_leaves.emitting = _night < 0.5
	var ff := _night > 0.45
	if ff != _fireflies.emitting:
		_fireflies.emitting = ff
	_fireflies.visible = _night > 0.3
	_fireflies.global_position = c + Vector3(0, 0.9, -1.0)
	var pl: Node3D = world.player
	if pl and pl.visible and world.state == "play":
		var v: Vector3 = pl.get("velocity")
		var running := v.length() > 6.2
		_dust.emitting = running
		_dust.global_position = pl.global_position + Vector3(0, 0.1, 0) - v.normalized() * 0.2
	else:
		_dust.emitting = false
