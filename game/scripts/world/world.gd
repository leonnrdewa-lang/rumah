extends Node3D
## Builds the island from data/layout.json (terrain, sea, decoration, buildings,
## parcels, villagers), runs the day/night cycle, the camera and interaction.

const TERRAIN_SHADER := preload("res://shaders/terrain.gdshader")
const WATER_SHADER := preload("res://shaders/water.gdshader")
const DATA_TEX := preload("res://assets/textures/world_data.png")
const NOISE_TEX := preload("res://assets/textures/noise.png")
const UI_SCRIPT := preload("res://scripts/ui/ui.gd")
const DEALS_SCRIPT := preload("res://scripts/world/deals.gd")
const AMBIENT_SCRIPT := preload("res://scripts/world/ambient_life.gd")
const SHADE_TEX_PATH := "res://assets/textures/world_shade.png"
const GROUND_DIR := "res://assets/textures/ground/"
const GROUND_TEX := ["grass", "grass_dry", "dirt", "sand", "mulch"]
## Day light, tuned against the target at 08:30 (sunlit ground V ~0.77 H ~57, cast
## shadows ~0.55x): a warm sun from the upper left and a green-teal sky/foliage bounce,
## so sunlit ground reads warm yellow-green and shade olive-teal
const SUN_DAY := Color(1.0, 0.93, 0.74)
const SUN_ENERGY := 1.25
const AMBIENT_DAY := Color("a8ccb8")
const AMBIENT_ENERGY := 0.67
## "Hemat baterai" turns the sun's shadows off. In the Compatibility renderer that
## moves the sun from its own additive pass into the base pass, where our custom-shader
## materials receive far less of it (measured 0.43x on a 0.5 albedo), so the sun is
## boosted back. With nothing in shade the boosted warm sun turned the whole frame
## khaki (hue 64-67 against 74-78 at full quality), so it is boosted less, made a
## little cooler, and the green-teal sky light makes up the difference.
const LQ_SUN_BOOST := 1.8
const LQ_SUN_TINT := Color(0.96, 1.0, 1.1)
const LQ_AMBIENT := 1.3

const DECOR_COLLIDE := {"tree_big": 0.55, "coconut": 0.35, "banana": 0.3, "rock_b": -1.0, "rock_c": -1.0,
	"cliff_a": -1.0, "bush_a": 0.45, "bush_b": 0.45, "sawit_wild": 0.45}
## decor that has no model of its own: [model, only_under, exclude_under]
const DECOR_ALIAS := {"sawit_wild": ["sawit_3", "", "Fruits"]}
## small decor that should not cast shadows
const DECOR_NO_SHADOW := ["grass_tuft", "flowers", "rock_a", "rock_b"]
const PROP_COLLIDE := ["sumur", "truck", "crate", "gerobak", "tumpukan_tbs", "meja", "bangku", "lampu", "perahu", "pagar", "jerigen", "karung_pupuk"]
const SERVICE := {"kantor": "Masuk Kantor Sawit", "toko": "Belanja di Koperasi Desa", "warung": "Mampir ke Warung Mak Inah",
	"pabrik": "Ke Pabrik Kelapa Sawit (PKS)", "calo": "Bisik-bisik dengan Bang Jeki"}

var layout: Dictionary
var data_img: Image
var height_img: Image
var height_tex: ImageTexture
var world_size := 200.0
var water_level := -0.3
var tile_size := 3.2
var obstacles: Array = []     # circles [x, z, r]
var rects: Array = []         # [x0, z0, x1, z1]
var walk_rects: Array = []    # walkable areas over water (jetty)
var interactables: Array = []
var tile_views := {}
var parcel_signs := {}
var building_nodes := {}
var door_points := {}
var npcs := {}
var extras := {}
var worker_npcs: Array = []
var temp_nodes: Array = []
var boats: Array = []
var player_light: OmniLight3D
var tents: Array = []
var lamps: Array[OmniLight3D] = []
var player: Player
var cam_rig: Node3D
var camera: Camera3D
var sun: DirectionalLight3D
var env: Environment
var ui: Node
var deals: Node
var state := "title"
var target: Dictionary = {}
var _ring: MeshInstance3D
var _title_t := 0.0
var _t := 0.0
var night_k := 0.0   # 0 = day, 1 = night (read by ambient_life.gd)
## The target's three-quarter view: ~45 deg pitch, 16.5 m (about 19 m of ground across a
## 16:9 screen at the player), so palms show their full crowns from the side and the
## ground recedes with depth. The look point sits `cam_lead` m up-screen (north) of the
## player: the player stands a little below the centre, and the crowns of the palms
## just behind them, which rise up the screen, stay in frame (at 45 deg without the
## lead they left the top edge).
var cam_distance := 16.5
var cam_pitch := 45.0
var cam_lead := 1.6
## extra look-ahead in the walking direction (s of travel): about cancels the follow lag,
## so the scene ahead of a walking player is in view
const CAM_MOVE_LEAD := 0.3
var _move_lead := Vector3.ZERO
var quality_high := true
var undergrowth: Undergrowth
var ambient: Node3D
var terrain_mat: ShaderMaterial
var _plant_mask := PackedByteArray()
var _pm_n := 0
const PM_RES := 0.5


func _ready() -> void:
	layout = GS.load_layout()
	world_size = layout.get("world_size", 200.0)
	water_level = layout.get("water_level", -0.3)
	tile_size = layout.get("tile", 3.2)
	data_img = DATA_TEX.get_image()
	if data_img.is_compressed():
		data_img.decompress()
	var hb := FileAccess.get_file_as_bytes("res://data/height.bin")
	var side := int(sqrt(hb.size() / 2))
	height_img = Image.create_from_data(side, side, false, Image.FORMAT_RH, hb)
	height_tex = ImageTexture.create_from_image(height_img)
	_build_environment()
	_build_terrain()
	_build_water()
	_build_decor()
	_build_buildings()
	_build_props()
	_build_parcels()
	_build_undergrowth()
	_build_player()
	_build_npcs()
	_build_ring()
	ambient = AMBIENT_SCRIPT.new()
	ambient.name = "AmbientLife"
	ambient.set("world", self)
	add_child(ambient)
	deals = DEALS_SCRIPT.new()
	deals.name = "Deals"
	deals.world = self
	add_child(deals)
	ui = UI_SCRIPT.new()
	ui.name = "UI"
	ui.world = self
	add_child(ui)
	deals.ui = ui
	GS.parcel_changed.connect(_on_parcel_changed)
	GS.villager_changed.connect(func(vid): refresh_villager(vid))
	GS.stats_changed.connect(func(): player.update_carry(int(GS.inv.get("tbs", 0))))
	GS.day_started.connect(_on_day_started)
	GS.game_over.connect(func(reason): state = "over"; ui.show_game_over(reason))
	_apply_quality()
	enter_title()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--autotest"):
			var at: Node = load("res://scripts/debug/autotest.gd").new()
			at.world = self
			add_child(at)


# ------------------------------------------------------------------ queries
func height_at(x: float, z: float) -> float:
	var fx := (x + world_size * 0.5) / world_size * height_img.get_width() - 0.5
	var fz := (z + world_size * 0.5) / world_size * height_img.get_height() - 0.5
	var w := height_img.get_width()
	var hh := height_img.get_height()
	var x0 := clampi(int(floor(fx)), 0, w - 1)
	var z0 := clampi(int(floor(fz)), 0, hh - 1)
	var x1 := mini(x0 + 1, w - 1)
	var z1 := mini(z0 + 1, hh - 1)
	var tx := clampf(fx - x0, 0.0, 1.0)
	var tz := clampf(fz - z0, 0.0, 1.0)
	var a := lerpf(height_img.get_pixel(x0, z0).r, height_img.get_pixel(x1, z0).r, tx)
	var b := lerpf(height_img.get_pixel(x0, z1).r, height_img.get_pixel(x1, z1).r, tx)
	var h := lerpf(a, b, tz)
	for r in walk_rects:
		if x > r[0] and x < r[2] and z > r[1] and z < r[3]:
			return maxf(h, r[4])
	return h


func is_walkable(x: float, z: float) -> bool:
	for r in walk_rects:
		if x > r[0] and x < r[2] and z > r[1] and z < r[3]:
			return true
	return height_at(x, z) > water_level + 0.1


func is_free(x: float, z: float, pad := 0.0) -> bool:
	for c in obstacles:
		var dx: float = x - c[0]
		var dz: float = z - c[1]
		if dx * dx + dz * dz < (c[2] + pad) * (c[2] + pad):
			return false
	for r in rects:
		if x > r[0] - pad and x < r[2] + pad and z > r[1] - pad and z < r[3] + pad:
			return false
	return true


func v3(a: Array, y := 0.0) -> Vector3:
	if a.size() >= 3:
		return Vector3(a[0], a[1], a[2])
	return Vector3(a[0], y, a[1])


# ------------------------------------------------------------------ environment
func _build_environment() -> void:
	var we := WorldEnvironment.new()
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("3a8f94")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = AMBIENT_DAY
	env.ambient_light_energy = AMBIENT_ENERGY
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	# soft painterly post: a subtle glow on highlights, a little more saturation/contrast
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_strength = 1.0
	env.glow_bloom = 0.0
	env.glow_hdr_threshold = 0.85
	env.glow_hdr_scale = 1.5
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_ADDITIVE
	env.adjustment_enabled = true
	env.adjustment_brightness = 1.0
	env.adjustment_contrast = 1.05
	env.adjustment_saturation = 1.0
	we.environment = env
	add_child(we)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.shadow_opacity = 0.8
	sun.shadow_blur = 2.2
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	sun.directional_shadow_max_distance = 31.0   # set per frame in _place_camera
	sun.shadow_bias = 0.05
	sun.shadow_normal_bias = 1.1
	add_child(sun)
	cam_rig = Node3D.new()
	add_child(cam_rig)
	camera = Camera3D.new()
	camera.fov = 35.0
	camera.near = 0.5
	# nothing beyond the ground at the top edge of the frame can be on screen (~27 m at
	# play, ~48 m for the title fly-over, ~45 m pulled back on a portrait phone)
	camera.far = 90.0
	cam_rig.add_child(camera)
	camera.current = true


func _apply_quality() -> void:
	if OS.has_feature("web_android") or OS.has_feature("web_ios") or OS.has_feature("mobile"):
		RenderingServer.directional_shadow_atlas_set_size(1024, true)
	sun.shadow_enabled = quality_high
	get_viewport().msaa_3d = Viewport.MSAA_2X if quality_high else Viewport.MSAA_DISABLED
	get_viewport().scaling_3d_scale = 1.0 if quality_high else 0.75
	env.glow_enabled = quality_high
	# the additive glow brightens the frame a little; keep "Hemat baterai" as bright
	env.tonemap_exposure = 1.0 if quality_high else 1.07
	# "Hemat baterai" halves the undergrowth and drops its shadows
	if undergrowth:
		undergrowth.set_density(1.0 if quality_high else 0.5)
		undergrowth.set_shadows(quality_high)
	# ... and the terrain's extra texture samples; the baked contact shade was made for
	# the full undergrowth, so it is lightened to not leave bare dark patches
	if terrain_mat:
		terrain_mat.set_shader_parameter("hq", 1.0 if quality_high else 0.0)
		terrain_mat.set_shader_parameter("shade_strength", 1.0 if quality_high else 0.72)
	if ambient and ambient.has_method("set_quality"):
		ambient.call("set_quality", quality_high)


func set_quality(high: bool) -> void:
	quality_high = high
	_apply_quality()


func _build_terrain() -> void:
	var mat := ShaderMaterial.new()
	terrain_mat = mat
	mat.shader = TERRAIN_SHADER
	mat.set_shader_parameter("data_tex", DATA_TEX)
	mat.set_shader_parameter("noise_tex", NOISE_TEX)
	mat.set_shader_parameter("world_size", world_size)
	mat.set_shader_parameter("water_level", water_level)
	# v2 ground textures (tiled in world space) + baked shade masks; any that are
	# missing fall back to the procedural v1 colours inside the shader
	for n in GROUND_TEX:
		var tex := GroundFx.load_tiling_texture(GROUND_DIR + n + ".png")
		if tex:
			mat.set_shader_parameter(n + "_tex", tex)
			mat.set_shader_parameter("has_" + n, 1.0)
			if n == "grass":
				mat.set_shader_parameter("grass_avg", GroundFx.average_linear(tex))
	if ResourceLoader.exists(SHADE_TEX_PATH):
		mat.set_shader_parameter("shade_tex", load(SHADE_TEX_PATH))
		mat.set_shader_parameter("has_shade", 1.0)
	var t := ModelLib.scene("terrain")
	if t:
		var n: Node3D = t.instantiate()
		add_child(n)
		for mi in ModelLib.find_meshes(n):
			mi.material_override = mat
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	else:
		var mi := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(world_size, world_size)
		mi.mesh = pm
		mi.material_override = mat
		add_child(mi)


func _build_water() -> void:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(600, 600)
	mi.mesh = pm
	mi.position.y = water_level
	var mat := ShaderMaterial.new()
	mat.shader = WATER_SHADER
	mat.set_shader_parameter("height_tex", height_tex)
	mat.set_shader_parameter("noise_tex", NOISE_TEX)
	mat.set_shader_parameter("world_size", world_size)
	mat.set_shader_parameter("water_level", water_level)
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


func _static_body(pos: Vector3) -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = 1
	b.collision_mask = 0
	b.position = pos
	add_child(b)
	return b


func _add_cylinder(pos: Vector3, r: float, h := 2.0) -> void:
	var b := _static_body(pos)
	var cs := CollisionShape3D.new()
	var c := CylinderShape3D.new()
	c.radius = r
	c.height = h
	cs.shape = c
	cs.position.y = h * 0.5 - 0.5
	b.add_child(cs)
	obstacles.append([pos.x, pos.z, r])


func _add_box(xf: Transform3D, aabb: AABB, shrink := 0.9) -> void:
	var b := _static_body(Vector3.ZERO)
	b.transform = xf
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(aabb.size.x * shrink, maxf(aabb.size.y, 2.0), aabb.size.z * shrink)
	cs.shape = bs
	cs.position = aabb.get_center()
	b.add_child(cs)
	# conservative axis-aligned footprint for NPC wandering
	var corners := []
	for sx in [0, 1]:
		for sz in [0, 1]:
			var local := Vector3(aabb.position.x + aabb.size.x * sx, 0, aabb.position.z + aabb.size.z * sz)
			corners.append(xf * local)
	var x0 := INF
	var z0 := INF
	var x1 := -INF
	var z1 := -INF
	for c in corners:
		x0 = minf(x0, c.x)
		z0 = minf(z0, c.z)
		x1 = maxf(x1, c.x)
		z1 = maxf(z1, c.z)
	rects.append([x0, z0, x1, z1])


func _build_decor() -> void:
	# group by model and 24 m chunk so off-screen decoration is frustum-culled
	var groups := {}
	for d in layout.get("decor", []):
		var m: String = d["model"]
		var key := "%s|%d|%d" % [m, floori(float(d["pos"][0]) / 24.0), floori(float(d["pos"][2]) / 24.0)]
		if not groups.has(key):
			groups[key] = []
		groups[key].append(d)
	for key in groups:
		var m: String = key.get_slice("|", 0)
		var list: Array = groups[key]
		var mesh: ArrayMesh
		if DECOR_ALIAS.has(m):
			var al: Array = DECOR_ALIAS[m]
			mesh = ModelLib.merged_mesh(al[0], true, al[1], al[2])
		else:
			mesh = ModelLib.merged_mesh(m, true)
		if mesh.get_surface_count() == 0:
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = list.size()
		var aabb := mm.mesh.get_aabb()
		for i in list.size():
			var d: Dictionary = list[i]
			var p := v3(d["pos"])
			var s: float = d.get("scale", 1.0)
			var basis := Basis(Vector3.UP, deg_to_rad(d.get("rot", 0.0))).scaled(Vector3.ONE * s)
			mm.set_instance_transform(i, Transform3D(basis, p))
			if DECOR_COLLIDE.has(m):
				var r: float = DECOR_COLLIDE[m]
				if m == "cliff_a":
					_add_box(Transform3D(basis, p), aabb, 0.85)
				elif r < 0.0:
					_add_cylinder(p, maxf(aabb.size.x, aabb.size.z) * 0.42 * s)
				else:
					_add_cylinder(p, r * s)
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		if m in DECOR_NO_SHADOW:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)


func _build_plant_mask() -> void:
	## 0.5 m bitmap of places where undergrowth must not grow: building and prop
	## footprints, doors, parcel planting spots, signs and other interaction points.
	_pm_n = int(ceil(world_size / PM_RES))
	_plant_mask.resize(_pm_n * _pm_n)
	_plant_mask.fill(0)
	for r in rects:
		_mask_rect(r[0] - 0.15, r[1] - 0.15, r[2] + 0.15, r[3] + 0.15)
	for id in door_points:
		var d: Vector3 = door_points[id]
		_mask_circle(d.x, d.z, 1.4)
	# planting spots: terrain.py keeps ferns 1.2 m and taller plants 1.6 m away; low grass
	# may reach the (smaller) piringan's edge
	for key in tile_views:
		var tp: Vector3 = tile_views[key].position
		_mask_circle(tp.x, tp.z, 0.85)
	for it in interactables:
		if it.has("pos") and not it.has("tile"):
			var ip: Vector3 = it["pos"]
			_mask_circle(ip.x, ip.z, 1.4)
	for c in obstacles:
		_mask_circle(c[0], c[1], float(c[2]) + 0.15)
	for r in walk_rects:
		_mask_rect(r[0] - 1.0, r[1] - 1.0, r[2] + 1.0, r[3] + 1.0)
	var sp: Array = layout.get("player_spawn", [0, 0])
	_mask_circle(sp[0], sp[1], 1.5)


func _mask_rect(x0: float, z0: float, x1: float, z1: float) -> void:
	var i0 := clampi(int((x0 + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var i1 := clampi(int((x1 + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var j0 := clampi(int((z0 + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var j1 := clampi(int((z1 + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	for j in range(j0, j1 + 1):
		for i in range(i0, i1 + 1):
			_plant_mask[j * _pm_n + i] = 1


func _mask_circle(x: float, z: float, r: float) -> void:
	var i0 := clampi(int((x - r + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var i1 := clampi(int((x + r + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var j0 := clampi(int((z - r + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	var j1 := clampi(int((z + r + world_size * 0.5) / PM_RES), 0, _pm_n - 1)
	for j in range(j0, j1 + 1):
		var cz := (j + 0.5) * PM_RES - world_size * 0.5
		for i in range(i0, i1 + 1):
			var cx := (i + 0.5) * PM_RES - world_size * 0.5
			if (cx - x) * (cx - x) + (cz - z) * (cz - z) < r * r:
				_plant_mask[j * _pm_n + i] = 1


func plant_blocked(x: float, z: float) -> bool:
	if _pm_n == 0:
		return false
	var i := int((x + world_size * 0.5) / PM_RES)
	var j := int((z + world_size * 0.5) / PM_RES)
	if i < 0 or j < 0 or i >= _pm_n or j >= _pm_n:
		return true
	return _plant_mask[j * _pm_n + i] != 0


func _build_undergrowth() -> void:
	_build_plant_mask()
	undergrowth = Undergrowth.new()
	undergrowth.name = "Undergrowth"
	add_child(undergrowth)
	undergrowth.build(layout.get("undergrowth", {}), plant_blocked)


func _build_buildings() -> void:
	for b in layout.get("buildings", []):
		# one merged mesh per building keeps draw calls low on phones
		var node := MeshInstance3D.new()
		node.mesh = ModelLib.merged_mesh(b["model"], true)
		node.position = v3(b["pos"])
		node.rotation.y = deg_to_rad(b["rot"])
		add_child(node)
		building_nodes[b["id"]] = node
		var aabb := ModelLib.mesh_aabb(b["model"])
		var xf := node.transform
		if b["model"] != "dermaga":
			node.add_child(GroundFx.rect_blob(aabb, 1.3, 0.55))
		if b["model"] == "dermaga":
			# the jetty is walkable over the water
			var p0 := xf * Vector3(aabb.position.x, 0, aabb.position.z)
			var p1 := xf * Vector3(aabb.end.x, 0, aabb.end.z)
			walk_rects.append([minf(p0.x, p1.x) + 0.2, minf(p0.z, p1.z) + 0.2, maxf(p0.x, p1.x) - 0.2,
				maxf(p0.z, p1.z) - 0.2, node.position.y + 0.3])  # deck top is 0.3 m above the origin
			continue
		_add_box(xf, aabb, 0.92)
		var door := xf * Vector3(0, 0, aabb.end.z + 1.1)
		door.y = height_at(door.x, door.z)
		door_points[b["id"]] = door
		var id: String = b["id"]
		if SERVICE.has(id):
			var prompt_text: String = SERVICE[id]
			interactables.append({"pos": door, "r": 2.4, "prompt": func(): return prompt_text,
				"act": func(): deals.open_service(id)})
		if id == "kantor":
			_decorate_sign(node, "kantor", "KANTOR SAWIT\nThe Franchise™", Color("3b5d2a"))
		elif id == "toko":
			_decorate_sign(node, "toko", "KOPERASI DESA", Color("2f5a6a"))


func _decorate_sign(node: Node3D, model: String, text: String, color: Color) -> void:
	var src := ModelLib.instance(model, true)
	var board: Node3D = src.find_child("SignBoard", true, false)
	var label := Label3D.new()
	label.text = text
	label.font = ModelLib.label_font()
	label.font_size = 64
	label.outline_size = 0
	label.modulate = color
	label.pixel_size = 0.006
	label.line_spacing = -6
	node.add_child(label)
	if board:
		# the board's origin is the centre of its front face, which faces +Z
		var meshes := ModelLib.find_meshes(board)
		var width := 2.4
		if not meshes.is_empty():
			width = meshes[0].mesh.get_aabb().size.x
		label.transform = ModelLib._rel_xform(board, src) * Transform3D(Basis(), Vector3(0, 0, 0.03))
		label.pixel_size = clampf(width / 560.0, 0.003, 0.01)
	else:
		label.position = Vector3(0, 3.2, 2.6)
	src.free()


func _build_props() -> void:
	for p in layout.get("props", []):
		var m: String = p["model"]
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh(m, true)
		if mi.mesh.get_surface_count() == 0:
			continue
		mi.position = v3(p["pos"])
		mi.rotation.y = deg_to_rad(p["rot"])
		add_child(mi)
		if m != "perahu":
			var pa := mi.mesh.get_aabb()
			if pa.size.x > 1.2 or pa.size.z > 1.2:
				mi.add_child(GroundFx.rect_blob(pa, 0.55, 0.42))
			else:
				mi.add_child(GroundFx.blob(maxf(pa.size.x, pa.size.z) * 0.75 + 0.15, 0.38))
		if m == "perahu":
			mi.position.y = maxf(mi.position.y, water_level - 0.08)
			boats.append(mi)
			continue
		if m in PROP_COLLIDE:
			var aabb := mi.mesh.get_aabb()
			if aabb.size.x > 1.6 or aabb.size.z > 1.6:
				_add_box(mi.transform, aabb, 0.9)
			else:
				_add_cylinder(mi.position, maxf(0.3, maxf(aabb.size.x, aabb.size.z) * 0.45))
		if m == "lampu":
			var l := OmniLight3D.new()
			l.light_color = Color(1.0, 0.8, 0.5)
			l.omni_range = 9.0
			l.light_energy = 0.0
			l.shadow_enabled = false
			l.position = mi.position + Vector3(0, 2.8, 0)
			add_child(l)
			lamps.append(l)


func _build_parcels() -> void:
	var cols: int = layout.get("parcel_cols", 4)
	var rows: int = layout.get("parcel_rows", 3)
	for p in GS.parcels:
		var pid: int = p["id"]
		var c := v3(p["center"])
		for idx in cols * rows:
			var col := idx % cols
			var row := idx / cols
			var pos := c + Vector3((col - (cols - 1) * 0.5) * tile_size, 0, (row - (rows - 1) * 0.5) * tile_size)
			pos.y = height_at(pos.x, pos.z)
			var tv := TileView.new()
			tv.pid = pid
			tv.idx = idx
			tv.position = pos
			add_child(tv)
			tile_views["%d:%d" % [pid, idx]] = tv
			var tpid := pid
			var tidx := idx
			interactables.append({"pos": pos, "r": 1.75, "tile": true,
				"prompt": func(): return GS.tile_action_info(tpid, tidx)["verb"],
				"ok": func(): return GS.tile_action_info(tpid, tidx)["ok"],
				"act": func(): _tile_action(tpid, tidx)})
			obstacles.append([pos.x, pos.z, 0.5])
		# parcel sign at the front-left corner
		var sp := c + Vector3(-(cols * tile_size) * 0.5 - 0.6, 0, (rows * tile_size) * 0.5 + 0.8)
		sp.y = height_at(sp.x, sp.z)
		var sign := MeshInstance3D.new()
		sign.mesh = ModelLib.merged_mesh("papan", true)
		sign.position = sp
		add_child(sign)
		var label := Label3D.new()
		label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
		label.font = ModelLib.label_font()
		label.font_size = 42
		label.outline_size = 9
		label.no_depth_test = true
		label.modulate = Color("4a3322")
		label.outline_modulate = Color("fdf3dc")
		label.pixel_size = 0.01
		label.position = sp + Vector3(0, 2.3, 0)
		add_child(label)
		parcel_signs[pid] = label
		var spid := pid
		interactables.append({"pos": sp, "r": 1.6, "prompt": func(): return "Lihat papan: " + GS.parcels[spid]["name"],
			"act": func(): deals.parcel_info(spid)})
		_update_sign(pid)


func _update_sign(pid: int) -> void:
	var p: Dictionary = GS.parcels[pid]
	var l: Label3D = parcel_signs[pid]
	if p["owner"] == "player":
		l.text = p["name"] + "\n[milikmu]"
		l.modulate = Color("2f5d2a")
	elif p["plasma"]:
		l.text = p["name"] + "\n[mitra franchise]"
		l.modulate = Color("7a4a12")
	else:
		l.text = p["name"]
		l.modulate = Color("4a3322")


func _build_player() -> void:
	player = Player.new()
	player.world = self
	var sp: Array = layout.get("player_spawn", [0, 0])
	add_child(player)
	player.add_child(GroundFx.blob(0.5, 0.45))
	player.global_position = Vector3(sp[0], height_at(sp[0], sp[1]), sp[1])
	# a warm little lantern glow around the player at night
	player_light = OmniLight3D.new()
	player_light.light_color = Color(1.0, 0.82, 0.55)
	player_light.omni_range = 7.0
	player_light.light_energy = 0.0
	player_light.position = Vector3(0, 2.2, 0.4)
	player.add_child(player_light)


func _build_npcs() -> void:
	for vid in GS.VILLAGERS:
		var d: Dictionary = GS.VILLAGERS[vid]
		var npc := Npc.new()
		npc.vid = vid
		var home: Vector3 = door_points.get(d["home"], Vector3.ZERO)
		npc.setup(self, d["model"], d["name"], home, 5.0)
		add_child(npc)
		npc.add_child(GroundFx.blob(0.5, 0.42))
		npcs[vid] = npc
		var nvid: String = vid
		interactables.append({"node": npc, "r": 1.8, "npc": true,
			"prompt": func(): return "Ngobrol dengan " + GS.vname(nvid),
			"act": func(): deals.talk(nvid)})
	# extras
	var calo_pos: Vector3 = door_points.get("calo", Vector3(56, 0, 20))
	extras["calo"] = _extra("char_calo", "Bang Jeki (Calo)", calo_pos + Vector3(0.8, 0, -1.2), 1.0, false)
	extras["anak"] = _extra("char_anak", "Dik Udin", Vector3(0, 0, 14), 9.0, true)
	interactables.append({"node": extras["anak"], "r": 1.6, "npc": true, "prompt": func(): return "Ngobrol dengan Dik Udin",
		"act": func(): deals.talk_extra("anak")})
	extras["mak"] = _extra("char_ibu", "Mak Inah", door_points.get("warung", Vector3(8, 0, 5)) + Vector3(1.5, 0, -0.5), 0.8, true)
	for vid in GS.VILLAGERS:
		refresh_villager(vid)


func _extra(model: String, n: String, pos: Vector3, radius: float, sleeps: bool) -> Npc:
	var npc := Npc.new()
	npc.setup(self, model, n, pos, radius)
	npc.sleeps_at_night = sleeps
	add_child(npc)
	npc.add_child(GroundFx.blob(0.6 if model == "char_preman" else 0.5, 0.42))
	return npc


func refresh_villager(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var npc: Npc = npcs[vid]
	var d: Dictionary = GS.VILLAGERS[vid]
	var house: Vector3 = door_points.get(d["home"], Vector3.ZERO)
	if v["status"] == "landless" and v.get("evicted", false):
		if int(v["tent"]) < 0:
			v["tent"] = _free_tent_index()
		var spots: Array = layout.get("tent_spots", [])
		var ti: int = clampi(int(v["tent"]), 0, spots.size() - 1)
		var tp := v3(spots[ti])
		tp.y = height_at(tp.x, tp.z)
		_ensure_tent(ti, tp)
		npc.home = tp + Vector3(0, 0, 1.2)
		if v["worker"]:
			npc.set_anchor(_worker_anchor(vid), 6.0)
		else:
			npc.set_anchor(tp + Vector3(0, 0, 2.0), 3.5)
	elif v["worker"]:
		npc.home = house
		npc.set_anchor(_worker_anchor(vid), 6.0)
	else:
		npc.home = house
		var pc := v3(GS.parcel_of(vid)["center"])
		npc.set_anchor(house.lerp(pc, 0.35), 5.0)


func _worker_anchor(vid: String) -> Vector3:
	var owned: Array = []
	for p in GS.parcels:
		if p["owner"] == "player":
			owned.append(p)
	var p: Dictionary = owned[hash(vid) % owned.size()]
	return v3(p["center"]) + Vector3(0, 0, 5.5)


func _free_tent_index() -> int:
	var used := []
	for vid in GS.villagers:
		used.append(int(GS.villagers[vid]["tent"]))
	for i in layout.get("tent_spots", []).size():
		if not i in used:
			return i
	return 0


func _ensure_tent(i: int, pos: Vector3) -> void:
	for t in tents:
		if t[0] == i:
			return
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLib.merged_mesh("tenda", true)
	mi.position = pos
	mi.rotation.y = randf_range(-0.4, 0.4)
	add_child(mi)
	mi.add_child(GroundFx.rect_blob(mi.mesh.get_aabb(), 0.6, 0.45))
	tents.append([i, mi])


func refresh_workers() -> void:
	## Generic hired workers (not villagers) are shown as buruh characters on your land.
	var generic := 0
	for w in GS.workers:
		if w["vid"] == "":
			generic += 1
	while worker_npcs.size() < generic:
		var n := _extra("char_buruh", "Buruh", Vector3.ZERO, 6.0, true)
		n.set_anchor(_worker_anchor("buruh%d" % worker_npcs.size()), 6.0, true)
		worker_npcs.append(n)
	while worker_npcs.size() > generic:
		worker_npcs.pop_back().queue_free()
	for vid in GS.villagers:
		refresh_villager(vid)


func _build_ring() -> void:
	_ring = MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.72
	tm.outer_radius = 0.86
	tm.rings = 24
	tm.ring_segments = 6
	_ring.mesh = tm
	_ring.scale = Vector3(1, 0.25, 1)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(1, 0.98, 0.9, 0.85)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_ring.material_override = m
	_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_ring.visible = false
	add_child(_ring)


# ------------------------------------------------------------------ game flow
func enter_title() -> void:
	state = "title"
	player.visible = false
	player.locked = true
	ui.show_title()


func start_game(load_save: bool) -> void:
	if load_save:
		if not GS.load_game():
			GS.new_game()
	else:
		GS.new_game()
	refresh_all()
	var sp: Array = layout.get("player_spawn", [0, 0])
	player.global_position = Vector3(sp[0], height_at(sp[0], sp[1]), sp[1])
	player.visible = true
	player.locked = false
	state = "play"
	cam_rig.global_position = player.global_position
	ui.show_hud()
	Sfx.start_music()
	if not load_save:
		deals.intro()


func refresh_all() -> void:
	for key in tile_views:
		tile_views[key].refresh()
	for pid in parcel_signs:
		_update_sign(pid)
	for t in tents:
		t[1].queue_free()
	tents.clear()
	refresh_workers()
	player.update_carry(int(GS.inv.get("tbs", 0)))


func _on_parcel_changed(pid: int) -> void:
	for idx in 12:
		var key := "%d:%d" % [pid, idx]
		if tile_views.has(key):
			tile_views[key].refresh()
	_update_sign(pid)


func spawn_temp_actor(model: String, label: String, pos: Vector3, radius := 2.0) -> Npc:
	## Characters that only show up for the rest of the day (preman, satgas, demonstrators).
	var n := _extra(model, label, pos, radius, false)
	temp_nodes.append(n)
	return n


func spawn_banner(pos: Vector3, text: String) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLib.merged_mesh("spanduk", true)
	mi.position = pos
	add_child(mi)
	temp_nodes.append(mi)
	var l := Label3D.new()
	l.text = text
	l.font = ModelLib.label_font()
	l.font_size = 40
	l.outline_size = 0
	l.modulate = Color("b8321f")
	l.pixel_size = 0.008
	var ab := mi.mesh.get_aabb()
	l.position = Vector3(0, ab.get_center().y + 0.1, ab.end.z + 0.03)
	mi.add_child(l)


func clear_temp() -> void:
	for n in temp_nodes:
		if is_instance_valid(n):
			n.queue_free()
	temp_nodes.clear()


func _on_day_started(report: Array) -> void:
	clear_temp()
	for line in report:
		if str(line).begins_with("[SIDAK]"):
			var d: Vector3 = door_points.get("kantor", Vector3.ZERO)
			spawn_temp_actor("char_petugas", "Petugas Satgas", d + Vector3(2.5, 0, 1.5), 1.5)
	refresh_all()
	player.global_position = door_points.get("kantor", player.global_position)
	ui.show_morning(report)


func _tile_action(pid: int, idx: int) -> void:
	var kind := GS.do_tile_action(pid, idx)
	if kind == "":
		Sfx.play("bad", 1.0, -6.0)
		return
	var tv: TileView = tile_views["%d:%d" % [pid, idx]]
	player.do_action_anim(kind)
	var dir := tv.global_position - player.global_position
	dir.y = 0
	if dir.length() > 0.1:
		player.facing = dir.normalized()
	tv.pop()
	match kind:
		"clear":
			Sfx.play("chop")
			burst(tv.global_position + Vector3(0, 0.6, 0), Color("6f9a3e"), 18)
			float_text(tv.global_position, "-%d energi" % GS.ENERGY_COST["clear"], Color("7a4a22"))
		"plant":
			Sfx.play("plant")
			burst(tv.global_position + Vector3(0, 0.2, 0), Color("7a5a3c"), 12)
			float_text(tv.global_position, "Bibit ditanam!", Color("2f6d2a"))
		"fert":
			Sfx.play("pop")
			burst(tv.global_position + Vector3(0, 0.4, 0), Color("f1f0e4"), 14)
			float_text(tv.global_position, "Dipupuk", Color("2f6d2a"))
		"harvest":
			Sfx.play("harvest")
			burst(tv.global_position + Vector3(0, 2.6, 0), Color("c9401f"), 16)
			float_text(tv.global_position + Vector3(0, 1.0, 0), "+TBS", Color("b8401f"))
			_drop_bunches(tv.global_position)


func _drop_bunches(at: Vector3) -> void:
	## Cut fruit bunches thud down beside the palm and lie there for a few seconds.
	if not ModelLib.has_model("tbs"):
		return
	for i in 2:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh("tbs", false)
		var a := randf() * TAU
		var land := at + Vector3(cos(a), 0, sin(a)) * randf_range(0.9, 1.4)
		land.y = height_at(land.x, land.z)
		mi.position = at + Vector3(0, 2.6, 0)
		mi.rotation = Vector3(randf() * 0.6, randf() * TAU, randf() * 0.6)
		add_child(mi)
		var shadow := GroundFx.blob(0.32, 0.4)
		shadow.position = land + Vector3(0, 0.03, 0)
		shadow.visible = false
		add_child(shadow)
		var tw := create_tween()
		tw.tween_interval(i * 0.12)
		tw.tween_property(mi, "position:x", land.x, 0.45)
		tw.parallel().tween_property(mi, "position:z", land.z, 0.45)
		tw.parallel().tween_property(mi, "position:y", land.y + 0.12, 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tw.tween_callback(shadow.show)
		tw.tween_property(mi, "position:y", land.y + 0.2, 0.08)
		tw.tween_property(mi, "position:y", land.y + 0.12, 0.1)
		tw.tween_interval(6.0)
		tw.tween_property(mi, "scale", Vector3.ONE * 0.01, 0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
		tw.tween_callback(mi.queue_free)
		tw.tween_callback(shadow.queue_free)


func burst(pos: Vector3, color: Color, amount := 14) -> void:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.amount = amount
	p.lifetime = 0.8
	p.explosiveness = 0.95
	p.direction = Vector3.UP
	p.spread = 70.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 4.5
	p.gravity = Vector3(0, -9.0, 0)
	p.scale_amount_min = 0.08
	p.scale_amount_max = 0.16
	var bm := BoxMesh.new()
	bm.size = Vector3.ONE
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.material = m
	p.mesh = bm
	p.position = pos
	add_child(p)
	p.emitting = true
	get_tree().create_timer(1.5).timeout.connect(p.queue_free)


func float_text(pos: Vector3, text: String, color: Color) -> void:
	var l := Label3D.new()
	l.text = text
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.font = ModelLib.label_font()
	l.font_size = 46
	l.outline_size = 10
	l.modulate = color
	l.outline_modulate = Color("fdf3dc")
	l.no_depth_test = true
	l.pixel_size = 0.01
	l.position = pos + Vector3(0, 1.8, 0)
	add_child(l)
	var tw := create_tween()
	tw.tween_property(l, "position:y", l.position.y + 1.2, 1.1)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 1.1).set_delay(0.4)
	tw.parallel().tween_property(l, "outline_modulate:a", 0.0, 1.1).set_delay(0.4)
	tw.tween_callback(l.queue_free)


# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	_t += delta
	RenderingServer.global_shader_parameter_set("wind_time", _t)
	if state == "play" and not ui.is_blocking():
		GS.advance(delta)
	_update_daylight()
	_update_camera(delta)
	for i in boats.size():
		var b: MeshInstance3D = boats[i]
		b.position.y = water_level - 0.08 + sin(_t * 1.3 + i * 2.0) * 0.05
		b.rotation.z = sin(_t * 0.9 + i) * 0.03
	if state == "play":
		_update_target()
	else:
		_ring.visible = false


func _update_daylight() -> void:
	var h := GS.hour if state != "title" else 9.5
	var day_k := clampf(sin((h - 6.0) / 13.0 * PI), 0.0, 1.0)
	# the night is over before the game's day starts (06:00), so the first frame of a
	# day is a bright, golden morning instead of murky dawn (v2 opened at V 0.42)
	var night := smoothstep(17.8, 19.6, h) + (1.0 - smoothstep(4.3, 5.7, h))
	night = clampf(night, 0.0, 1.0)
	night_k = night
	var morning := clampf(1.0 - absf(h - 6.0) / 1.6, 0.0, 1.0)
	var dusk := clampf(clampf(1.0 - absf(h - 18.0) / 1.6, 0.0, 1.0) + morning * 0.38, 0.0, 1.0)
	var elev := lerpf(33.0, 60.0, day_k)
	# warm sun from the upper left of the screen: shadows fall down-right
	sun.rotation = Vector3(deg_to_rad(-elev), deg_to_rad(-122.0 + (h - 12.0) * 2.5), 0)
	var dusk_col := Color(1.0, 0.7, 0.45)
	var night_col := Color(0.55, 0.62, 1.0)
	var col := SUN_DAY.lerp(dusk_col, dusk).lerp(night_col, night)
	var energy := lerpf(SUN_ENERGY, 0.36, night) * lerpf(0.9, 1.0, day_k) * (1.0 + 0.12 * morning)
	var amb := AMBIENT_DAY.lerp(Color("5b6fa8"), night).lerp(Color("e0b090"), dusk * 0.4)
	var amb_energy := lerpf(AMBIENT_ENERGY, 0.5, night)
	if not sun.shadow_enabled:
		col *= LQ_SUN_TINT
		energy *= LQ_SUN_BOOST
		amb_energy *= LQ_AMBIENT
	sun.light_color = col
	sun.light_energy = energy
	env.ambient_light_color = amb
	env.ambient_light_energy = amb_energy
	env.background_color = Color("3a8f94").lerp(Color("14304a"), night)
	RenderingServer.global_shader_parameter_set("night", night)
	for l in lamps:
		l.light_energy = night * 1.6
	if player_light:
		player_light.light_energy = night * 0.9


func _update_camera(delta: float) -> void:
	var vp := get_viewport().get_visible_rect().size
	var aspect := vp.x / maxf(vp.y, 1.0)
	if state == "title":
		_title_t += delta
		var a := _title_t * 0.05
		var center := Vector3(sin(a) * 18.0, 0, 6.0 + cos(a) * 10.0)
		cam_rig.global_position = cam_rig.global_position.lerp(center, clampf(delta * 0.8, 0.0, 1.0))
		_place_camera(34.0, 48.0)
		return
	# smooth, frame-rate independent follow (a touch of lag reads as "floaty" camera)
	var vel: Vector3 = player.velocity
	vel.y = 0.0
	_move_lead = _move_lead.lerp((vel * CAM_MOVE_LEAD).limit_length(2.4), 1.0 - exp(-delta * 2.0))
	var target_pos := player.global_position + Vector3(0, 0.5, -cam_lead) + _move_lead
	var k := 1.0 - exp(-delta * 4.0)
	cam_rig.global_position = cam_rig.global_position.lerp(target_pos, k)
	var dist := cam_distance
	var fov := 35.0
	if aspect < 1.0:
		# portrait phones: the camera keeps the vertical field of view, so the narrow
		# screen shows little ground across; pull back and widen a little
		# (9:19.5 -> x1.54 and 39 deg: ~8.5 m across instead of ~4.9 m)
		var a := clampf(aspect, 0.0, 1.0)
		dist *= lerpf(2.0, 1.0, a)
		fov = lerpf(42.0, 35.0, a)
	camera.fov = fov
	_place_camera(dist, cam_pitch)
	# see-through hole around the player
	var pp := player.global_position + Vector3(0, 0.7, 0)
	var sp := camera.unproject_position(pp)
	RenderingServer.global_shader_parameter_set("occlude_center", Vector2(sp.x / vp.x, sp.y / vp.y))
	var local := camera.global_transform.affine_inverse() * pp
	RenderingServer.global_shader_parameter_set("occlude_depth", -local.z)
	RenderingServer.global_shader_parameter_set("occlude_radius", 0.13 * 24.0 / dist)


func _place_camera(dist: float, pitch_deg: float) -> void:
	var pitch := deg_to_rad(pitch_deg)
	camera.position = Vector3(0, sin(pitch) * dist, cos(pitch) * dist)
	camera.rotation = Vector3(-pitch, 0, 0)
	# shadows must reach the ground at the top edge of the frame: its depth along the
	# view axis is h / sin(pitch - fov/2) * cos(fov/2) (~1.5 x dist at 45 deg); the
	# last 20% of the shadow range fades out, hence the / 0.8
	var half := deg_to_rad(camera.fov * 0.5)
	var h := sin(pitch) * dist + 1.0
	var depth := h / sin(maxf(pitch - half, 0.2)) * cos(half)
	var sd := clampf(depth / 0.8, 20.0, 70.0)
	if absf(sd - sun.directional_shadow_max_distance) > 0.05:
		sun.directional_shadow_max_distance = sd


func _update_target() -> void:
	var best := {}
	var best_score := INF
	var pp := player.global_position
	for it in interactables:
		var pos: Vector3
		if it.has("node"):
			var n: Node3D = it["node"]
			if not n.visible:
				continue
			pos = n.global_position
		else:
			pos = it["pos"]
		var d := Vector2(pos.x - pp.x, pos.z - pp.z)
		var dist := d.length()
		if dist > it["r"]:
			continue
		var facing_dot := 0.0
		if dist > 0.01:
			facing_dot = d.normalized().dot(Vector2(player.facing.x, player.facing.z))
		var score := dist - facing_dot * 0.9
		if it.has("npc"):
			score -= 0.8
		if score < best_score:
			best_score = score
			best = it
			best["_pos"] = pos
	target = best
	if best.is_empty():
		_ring.visible = false
		ui.set_prompt("", false)
		return
	var ok := true
	if best.has("ok"):
		ok = best["ok"].call()
	ui.set_prompt(best["prompt"].call(), ok)
	_ring.visible = true
	var rp: Vector3 = best["_pos"]
	_ring.global_position = Vector3(rp.x, height_at(rp.x, rp.z) + 0.08, rp.z)
	var s := 1.0 + sin(_t * 5.0) * 0.06
	var base := 1.2 if best.has("tile") else 0.8
	_ring.scale = Vector3(base * s, 0.25, base * s)


func try_action() -> void:
	if state != "play" or ui.is_blocking() or target.is_empty():
		return
	if target.has("ok") and not target["ok"].call():
		Sfx.play("bad", 1.0, -8.0)
		ui.toast(target["prompt"].call(), "info")
		return
	target["act"].call()


func _unhandled_input(event: InputEvent) -> void:
	if state != "play":
		return
	if event.is_action_pressed("action"):
		try_action()
	elif event.is_action_pressed("pause"):
		ui.toggle_pause()
	elif event.is_action_pressed("status"):
		ui.show_status()
