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
const RING_SHADER := preload("res://shaders/ring.gdshader")
const FISHING_SCRIPT := preload("res://scripts/world/fishing.gd")
const INTERIOR_SCRIPT := preload("res://scripts/world/interior.gd")
const AMBIENCE_SCRIPT := preload("res://scripts/world/ambience.gd")
const ANIMALS_SCRIPT := preload("res://scripts/world/animals.gd")
## x beyond this is the house interior (interior.gd ORIGIN), off the island
const INTERIOR_X := 300.0
const SHADE_TEX_PATH := "res://assets/textures/world_shade.png"
const GROUND_DIR := "res://assets/textures/ground/"
const GROUND_TEX := ["grass", "grass_dry", "dirt", "sand", "mulch"]
## Day light, tuned against the target at 08:30 (sunlit lawn V ~0.75 hue ~65, dirt V
## ~0.88, cast shadows ~0.65x as bright): a warm sun from the upper left and a teal
## sky/foliage bounce, so sunlit ground reads warm yellow-green and shade olive-teal.
## Fix round: the sky light is bluer (was a8ccb8) and the sun a little stronger. The
## green-tinted bounce multiplied the green albedos into saturated dark greens (S 0.63 in
## shade against the target's 0.52, hue 83 against 89); with the teal sky the shade
## reads cool and soft, and the post saturation (1.06) gives the sunlit mids back.
## Fix round 2: the shade greens still measured S 0.56 against the target's 0.52 and the
## sunlit mids / highlights 0.50 / 0.48 against 0.55 / 0.53. A bluer sky light and a
## yellower sun pull the two apart (shade cooler and softer, sunlit greens richer and
## warmer), a little more of both keeps the frame's brightness.
## Cel-shading pass (anime look): the toon light() in shaders/toon_light.gdshaderinc
## gives flat lit / shade bands, so the sun is warmer and the sky fill a cooler, lower
## blue for crisp anime contrast, and the post pass saturates more.
const SUN_DAY := Color("fff1cf")
const SUN_ENERGY := 1.38
const AMBIENT_DAY := Color("86a8e8")
const AMBIENT_ENERGY := 0.66
## Fix round 3 (closer camera): the hero frame measured V 0.51 / S 0.55 against the
## target's 0.57 / 0.50 (the palm row's crowns and their shade fill more of it now). A
## little post brightness, less post saturation and slightly lighter cast shadows lift it
## to ~0.55 / 0.51; the crowns get their own saturation back in model_lib.gd.
const POST_SATURATION := 1.1
const POST_BRIGHTNESS := 1.04
const SHADOW_OPACITY := 0.72
## "Hemat baterai" turns the sun's shadows off. In the Compatibility renderer that
## moves the sun from its own additive pass into the base pass, where our custom-shader
## materials receive far less of it (measured 0.43x on a 0.5 albedo), so the sun is
## boosted back. With nothing in shade the boosted warm sun turned the whole frame
## khaki (hue 64-67 against 74-78 at full quality), so it is boosted less, made a
## little cooler, and the green-teal sky light makes up the difference.
## Fix round 2: the fix round's frames still sat 7-11 hue steps yellower than full
## quality (mid greens 68-76 against 79-85), because every pixel gets the warm sun.
## The sun is now close to neutral here and the sky light a touch bluer; the lost
## saturation comes back in the post pass (x1.25 instead of x1.1).
const LQ_SUN_BOOST := 1.8
const LQ_SUN_TINT := Color(0.92, 1.0, 1.22)
const LQ_AMBIENT := 1.3
const LQ_AMBIENT_TINT := Color(0.95, 0.98, 1.03)
const LQ_SATURATION := 1.25

const DECOR_COLLIDE := {"tree_big": 0.55, "coconut": 0.35, "banana": 0.3, "rock_b": -1.0, "rock_c": -1.0,
	"cliff_a": -1.0, "bush_a": 0.45, "bush_b": 0.45, "sawit_wild": 0.45}
## hamlet yard life (map v3 dense round) collides as boxes (model -> footprint shrink)
const DECOR_BOX := {"kios": 0.92, "motor": 0.8, "jemuran": 0.9, "pot_tanaman": 0.85}
## decor that has no model of its own: [model, only_under, exclude_under]
const DECOR_ALIAS := {"sawit_wild": ["sawit_3", "", "Fruits"]}
## small decor that should not cast shadows
const DECOR_NO_SHADOW := ["grass_tuft", "flowers", "rock_a", "rock_b"]
const PROP_COLLIDE := ["sumur", "truck", "crate", "gerobak", "tumpukan_tbs", "meja", "bangku", "lampu", "perahu", "pagar", "jerigen", "karung_pupuk", "drum", "karung_tumpuk"]
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
## map v3 bridges: [cx, cz, along_x, half_len, half_w, base_y, deck_h, ramp] - walkable,
## the deck rises over the ramps at both ends (height_at)
var bridges: Array = []
var fence_nodes: Array = []
var _free_grid := {}          # 8 m cell -> [circles, rects] near it (is_free)
var _free_counts := Vector2i(-1, -1)
const FREE_CELL := 8.0
## named villagers who own no land (talk_extra) and the walking passers-by (map v3)
var walkers: Array = []
var _walker_t: Array = []
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
## adaptive resolution (holds ~60 fps): measured frame time -> 3D render scale
var _fps_acc := 0.0
var _fps_frames := 0
var _res_scale := 1.0
var _slow_secs := 0.0
var _t := 0.0
var night_k := 0.0   # 0 = day, 1 = night (read by ambient_life.gd)
## The target's three-quarter view: 44 deg pitch, 12 m (about 13.5 m of ground across
## a 16:9 screen at the player: the character is ~1/7.5 of the screen height and a grown
## palm crown ~1/3 of its width, as in the target; v2 used 45 deg / 16.5 m, where the
## character was ~1/11). The look point sits `cam_lead` m up-screen (north) of the
## player, so the player stands just below the centre and the crowns of the palms
## behind them stay in frame.
## Env fix round: the 12 m camera framed ~13.5 m of ground and the crowns filled half
## the frame as one canopy; the target shows ~5 separate palms plus the shed, truck and
## road. 46 deg / 15.5 m with FOV 35 frames ~17.5 m across at the player (the character
## is ~1/10 of the screen height, as in the target) and more above them.
var cam_distance := 15.5
var cam_pitch := 46.0
var cam_lead := 0.8
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
var _tile_grid := {}   # 4 m cell -> planting spots (xz) in it and its neighbours
## fishing (fishing.gd) and house interiors (interior.gd)
var fishing: Node3D
var interior: Node3D
var ambience: Node3D           # nature sounds by place and hour (ambience.gd)
var animals: Node3D            # cattle, goats, chickens, ducks, frogs, cats, dogs (animals.gd)
var inside := ""               # house id the player is in ("" = outdoors)
var _inside_vid := ""
var _fish_spot := {}           # {"pos", "water"} in front of the player, or {}
var _fish_probe_t := 0.0
var _bed_item := {}
var _cup_item := {}
var _house_items: Array = []   # interactables that only exist inside
var _fading := false


func _ready() -> void:
	# physics interpolation only for the player (moves on the physics tick); the
	# camera, NPCs and props move per frame and must not be interpolated
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
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
	_build_bridges()
	_build_fences()
	_build_parcels()
	_build_undergrowth()
	_build_player()
	_build_npcs()
	_build_ring()
	ambient = AMBIENT_SCRIPT.new()
	ambient.name = "AmbientLife"
	ambient.set("world", self)
	add_child(ambient)
	fishing = FISHING_SCRIPT.new()
	fishing.name = "Fishing"
	fishing.world = self
	add_child(fishing)
	interior = INTERIOR_SCRIPT.new()
	interior.name = "Interior"
	interior.world = self
	add_child(interior)
	ambience = AMBIENCE_SCRIPT.new()
	ambience.name = "Ambience"
	ambience.world = self
	add_child(ambience)
	animals = ANIMALS_SCRIPT.new()
	animals.name = "Animals"
	animals.world = self
	add_child(animals)
	deals = DEALS_SCRIPT.new()
	deals.name = "Deals"
	deals.world = self
	add_child(deals)
	ui = UI_SCRIPT.new()
	ui.name = "UI"
	ui.world = self
	add_child(ui)
	deals.ui = ui
	fishing.ui = ui
	_build_interior_items()
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
	if x > INTERIOR_X:
		return 0.0   # the house interior's floor
	var h := terrain_height(x, z)
	for r in walk_rects:
		if x > r[0] and x < r[2] and z > r[1] and z < r[3]:
			return maxf(h, r[4])
	for br in bridges:
		var d := _bridge_deck(br, x, z)
		if d > -INF:
			return maxf(h, d)
	return h


func terrain_height(x: float, z: float) -> float:
	## the ground itself (no jetty or bridge decks)
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
	return lerpf(a, b, tz)


func _bridge_deck(br: Array, x: float, z: float) -> float:
	## deck height of a bridge at (x, z), or -INF off it
	var u: float = (x - br[0]) if br[2] else (z - br[1])
	var v: float = (z - br[1]) if br[2] else (x - br[0])
	if absf(u) > br[3] or absf(v) > br[4]:
		return -INF
	var k := clampf((br[3] - absf(u)) / br[7], 0.0, 1.0)
	return br[5] + br[6] * k


func is_walkable(x: float, z: float) -> bool:
	if x > INTERIOR_X:
		return interior.is_walkable(x, z)
	for r in walk_rects:
		if x > r[0] and x < r[2] and z > r[1] and z < r[3]:
			return true
	for br in bridges:
		if _bridge_deck(br, x, z) > -INF:
			return true
	return height_at(x, z) > water_level + 0.1


func is_free(x: float, z: float, pad := 0.0) -> bool:
	## (map v3: hundreds of obstacles; they are looked up in an 8 m grid, see _free_cell)
	if _free_counts != Vector2i(obstacles.size(), rects.size()):
		_rebuild_free_grid()
	var cell: Array = _free_grid.get(Vector2i(floori(x / FREE_CELL), floori(z / FREE_CELL)), [])
	if cell.is_empty():
		return true
	for c in cell[0]:
		var dx: float = x - c[0]
		var dz: float = z - c[1]
		if dx * dx + dz * dz < (c[2] + pad) * (c[2] + pad):
			return false
	for r in cell[1]:
		if x > r[0] - pad and x < r[2] + pad and z > r[1] - pad and z < r[3] + pad:
			return false
	return true


func _rebuild_free_grid() -> void:
	## every circle / rect is listed in each 8 m cell within its extent + 2 m (the pad
	## callers use is <= 1 m)
	_free_grid.clear()
	_free_counts = Vector2i(obstacles.size(), rects.size())
	for c in obstacles:
		var r: float = c[2] + 2.0
		_grid_add(c[0] - r, c[1] - r, c[0] + r, c[1] + r, 0, c)
	for q in rects:
		_grid_add(q[0] - 2.0, q[1] - 2.0, q[2] + 2.0, q[3] + 2.0, 1, q)


func _grid_add(x0: float, z0: float, x1: float, z1: float, slot: int, item: Array) -> void:
	for gx in range(floori(x0 / FREE_CELL), floori(x1 / FREE_CELL) + 1):
		for gz in range(floori(z0 / FREE_CELL), floori(z1 / FREE_CELL) + 1):
			var k := Vector2i(gx, gz)
			if not _free_grid.has(k):
				_free_grid[k] = [[], []]
			_free_grid[k][slot].append(item)


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
	env.adjustment_brightness = POST_BRIGHTNESS
	env.adjustment_contrast = 1.1
	env.adjustment_saturation = POST_SATURATION
	we.environment = env
	add_child(we)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.shadow_opacity = SHADOW_OPACITY
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
	_res_scale = 1.0 if quality_high else 0.75
	get_viewport().scaling_3d_scale = _res_scale
	env.glow_enabled = quality_high
	ModelLib.set_outlines(quality_high)
	# the additive glow brightens the frame a little; keep "Hemat baterai" as bright
	env.tonemap_exposure = 1.0 if quality_high else 1.07
	# without shadows the frame is flatter and read greyer (S 0.45 against 0.52 at full
	# quality); a little more post saturation costs nothing
	env.adjustment_saturation = POST_SATURATION * (1.0 if quality_high else LQ_SATURATION)
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
		elif DECOR_BOX.has(m):
			mesh = ModelLib.flat_mesh(m, true)   # many-coloured yard props: one draw each chunk
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
			if DECOR_BOX.has(m):
				_add_box(Transform3D(basis, p), aabb, DECOR_BOX[m])
			elif DECOR_COLLIDE.has(m):
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
	# planting spots: terrain.py keeps the ferns / leafy cover 1.5 m and taller plants
	# 1.6-2.3 m away (a ~2 m weeded circle); undergrowth.gd also keeps every plant's
	# leaves out of a TILE_CLEAR disc (tile_dist below); the bitmap is the coarse backstop
	for key in tile_views:
		var tp: Vector3 = tile_views[key].position
		_mask_circle(tp.x, tp.z, 0.8)
		var cell := Vector2i(floori(tp.x / 4.0), floori(tp.z / 4.0))
		for cx in range(cell.x - 1, cell.x + 2):
			for cz in range(cell.y - 1, cell.y + 2):
				var ck := Vector2i(cx, cz)
				if not _tile_grid.has(ck):
					_tile_grid[ck] = []
				_tile_grid[ck].append(Vector2(tp.x, tp.z))
	for it in interactables:
		if it.has("pos") and not it.has("tile"):
			var ip: Vector3 = it["pos"]
			_mask_circle(ip.x, ip.z, 1.4)
	for c in obstacles:
		_mask_circle(c[0], c[1], float(c[2]) + 0.15)
	for r in walk_rects:
		_mask_rect(r[0] - 1.0, r[1] - 1.0, r[2] + 1.0, r[3] + 1.0)
	for br in bridges:
		var hx: float = (br[3] if br[2] else br[4]) + 0.8
		var hz: float = (br[4] if br[2] else br[3]) + 0.8
		_mask_rect(br[0] - hx, br[1] - hz, br[0] + hx, br[1] + hz)
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


func tile_dist(x: float, z: float) -> float:
	## distance (xz) to the nearest parcel planting spot, up to ~4 m (INF beyond)
	var best := INF
	for tp in _tile_grid.get(Vector2i(floori(x / 4.0), floori(z / 4.0)), []):
		best = minf(best, Vector2(x, z).distance_to(tp))
	return best


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
	undergrowth.build(layout.get("undergrowth", {}), plant_blocked, tile_dist)


func _build_buildings() -> void:
	for b in layout.get("buildings", []):
		# one merged mesh per building keeps draw calls low on phones
		var node := MeshInstance3D.new()
		node.mesh = ModelLib.merged_mesh(b["model"], true)
		node.position = v3(b["pos"])
		node.rotation.y = deg_to_rad(b["rot"])
		add_child(node)
		building_nodes[b["id"]] = node
		if b.has("wall") or b.has("roof"):
			_recolour(node, b.get("wall", ""), b.get("roof", ""))
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
		elif id == "gudang":
			_decorate_sign(node, "gudang", "Kebun Sawit", Color("4a3322"))
		if id.begins_with("rumah"):
			var hid := id
			interactables.append({"pos": door, "r": 2.0, "door": true, "prompt": func(): return house_prompt(hid),
				"act": func(): enter_house(hid)})
		if id == "rumah_juragan":
			# a name plate over the door of the player's own house
			var plate := Label3D.new()
			plate.text = "Rumah Juragan"
			plate.font = ModelLib.label_font()
			plate.font_size = 56
			plate.outline_size = 12
			plate.modulate = Color("6a3a18")
			plate.outline_modulate = Color("fdf3dc")
			plate.pixel_size = 0.006
			plate.position = Vector3(0, minf(aabb.end.y * 0.62, 2.6), aabb.end.z + 0.08)
			node.add_child(plate)


func _recolour(node: MeshInstance3D, wall: String, roof: String) -> void:
	## map v3: the hamlets' houses share a few shapes; each gets its own wall and roof
	## colour (the albedo of its M_Wall / M_Roof surfaces; baked AO and weathering stay)
	for i in node.mesh.get_surface_count():
		var m := node.mesh.surface_get_material(i)
		if m == null:
			continue
		var col := ""
		if m.resource_name.begins_with("M_Wall") and wall != "":
			col = wall
		elif m.resource_name.begins_with("M_Roof") and roof != "":
			col = roof
		if col != "":
			var c := Color(col)
			node.set_surface_override_material(i, ModelLib.retuned(m, "tint" + col, {"albedo": c}))


func _build_bridges() -> void:
	## Wooden and concrete bridges over the rivers (map v3): the model runs along its X,
	## ramps down to the banks at both ends; walking on it is done by height_at().
	for b in layout.get("bridges", []):
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh(b["model"], true)
		if mi.mesh.get_surface_count() == 0:
			continue
		var p := v3(b["pos"])
		var half: float = float(b.get("len", 14.0)) * 0.5
		var rot := deg_to_rad(float(b.get("rot", 0.0)))
		var along_x := absf(sin(rot)) < 0.5
		var e1 := p + (Vector3(half, 0, 0) if along_x else Vector3(0, 0, half))
		var e2 := p - (Vector3(half, 0, 0) if along_x else Vector3(0, 0, half))
		var base := maxf(height_at(e1.x, e1.z), height_at(e2.x, e2.z))
		base = maxf(base, water_level + 0.15)
		p.y = base
		mi.position = p
		mi.rotation.y = rot
		add_child(mi)
		bridges.append([p.x, p.z, along_x, half - 0.1, float(b.get("width", 3.2)) * 0.5 - 0.35, base, 0.55, 2.5])


func _build_fences() -> void:
	## Yard fences of the hamlets: one MultiMesh per model and 48 m chunk, with collision.
	var groups := {}
	for f in layout.get("fences", []):
		var key := "%s|%d|%d" % [f["model"], floori(float(f["pos"][0]) / 48.0), floori(float(f["pos"][2]) / 48.0)]
		if not groups.has(key):
			groups[key] = []
		groups[key].append(f)
	for key in groups:
		var m: String = key.get_slice("|", 0)
		var mesh := ModelLib.merged_mesh(m, true)
		if mesh.get_surface_count() == 0:
			continue
		var list: Array = groups[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = list.size()
		var aabb := mesh.get_aabb()
		for i in list.size():
			var f: Dictionary = list[i]
			var xf := Transform3D(Basis(Vector3.UP, deg_to_rad(float(f["rot"]))), v3(f["pos"]))
			xf.origin.y = height_at(xf.origin.x, xf.origin.z)
			mm.set_instance_transform(i, xf)
			_add_box(xf, aabb, 0.95)
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		add_child(mmi)
		fence_nodes.append(mmi)


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
		if m == "tumpukan_tbs" and ModelLib.has_model("tbs"):
			# env fix round: the pile is built from the rounded harvest bunches (tbs.glb)
			# instead of the spiky low-poly placeholder model
			mi.mesh = _tbs_pile_mesh()
		elif m == "truck" and ModelLib.has_model("tbs"):
			# ... and so is the truck's load (its Cargo child was the same spiky heap)
			mi.mesh = _truck_mesh()
		else:
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


var _tbs_pile: ArrayMesh
var _truck: ArrayMesh


func _tbs_pile_mesh() -> ArrayMesh:
	## A heap of 7 fresh fruit bunches (5 on the ground, 2 on top), merged into one mesh.
	if _tbs_pile == null:
		_tbs_pile = _tbs_heap([[-0.42, -0.2, 0.0, 0.3], [0.1, -0.4, 0.0, 1.6], [0.5, 0.05, 0.0, 2.9],
			[-0.3, 0.36, 0.0, 4.1], [0.22, 0.4, 0.0, 5.2], [-0.1, 0.0, 0.3, 0.9], [0.24, -0.08, 0.26, 3.6]])
	return _tbs_pile


func _truck_mesh() -> ArrayMesh:
	## The truck without its modelled Cargo heap, loaded with rounded tbs bunches instead.
	if _truck:
		return _truck
	var cargo := ModelLib.merged_mesh("truck", true, "Cargo", "").get_aabb()
	var body := ModelLib.merged_mesh("truck", true, "", "Cargo")
	if cargo.size.length() < 0.1:
		_truck = ModelLib.merged_mesh("truck", true)
		return _truck
	var spots := []
	var nx := maxi(1, int(cargo.size.x / 0.42))
	var nz := maxi(1, int(cargo.size.z / 0.42))
	for layer in 2:
		for i in nx:
			for k in nz:
				if layer == 1 and (i + k) % 2 == 1:
					continue
				var x := cargo.position.x + (i + 0.5) * cargo.size.x / nx + (0.06 if layer == 1 else 0.0)
				var z := cargo.position.z + (k + 0.5) * cargo.size.z / nz
				var y := cargo.position.y + 0.02 + layer * 0.26
				spots.append([x, z, y, float(i * 7 + k * 3 + layer), 0.85])
	var heap := _tbs_heap(spots)
	_truck = body.duplicate() as ArrayMesh
	for i in heap.get_surface_count():
		_truck.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, heap.surface_get_arrays(i))
		_truck.surface_set_material(_truck.get_surface_count() - 1, heap.surface_get_material(i))
	return _truck


func _tbs_heap(spots: Array) -> ArrayMesh:
	## tbs.glb merged at [x, z, y, yaw] spots
	var src := ModelLib.merged_mesh("tbs", true)
	var tools := []
	for i in src.get_surface_count():
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		tools.append(st)
	for sp in spots:
		var b := Basis(Vector3.UP, sp[3]) * Basis(Vector3.RIGHT, 0.15 * sin(sp[3] * 3.0))
		var sc: float = sp[4] if sp.size() > 4 else (1.05 if sp[2] > 0.0 else 1.0)
		var xf := Transform3D(b.scaled(Vector3.ONE * sc), Vector3(sp[0], sp[2], sp[1]))
		for i in src.get_surface_count():
			(tools[i] as SurfaceTool).append_from(src, i, xf)
	var out := ArrayMesh.new()
	for i in src.get_surface_count():
		var st: SurfaceTool = tools[i]
		st.set_material(src.surface_get_material(i))
		st.commit(out)
	return out


func _build_parcels() -> void:
	var cols: int = layout.get("parcel_cols", 4)
	var rows: int = layout.get("parcel_rows", 3)
	# map v3: staggered planting spots from the layout (older layouts: the square grid);
	# the palms are scaled to the grid so neighbouring crowns do not run into each other
	var offs: Array = layout.get("tile_offsets", [])
	if offs.is_empty():
		for idx in cols * rows:
			offs.append([((idx % cols) - (cols - 1) * 0.5) * tile_size, ((idx / cols) - (rows - 1) * 0.5) * tile_size])
	TileView.palm_scale = clampf(tile_size / 4.6, 0.6, 1.0)
	var so: Array = layout.get("sign_offset", [-(cols * tile_size) * 0.5 - 0.6, (rows * tile_size) * 0.5 + 0.8])
	for p in GS.parcels:
		var pid: int = p["id"]
		var c := v3(p["center"])
		for idx in offs.size():
			var pos := c + Vector3(float(offs[idx][0]), 0, float(offs[idx][1]))
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
		var sp := c + Vector3(float(so[0]), 0, float(so[1]))
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
	player.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_ON
	player.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_ON
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
		npc.look_key = vid
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
	extras["mak"] = _extra("char_ibu", "Mak Inah", door_points.get("warung", Vector3(8, 0, 5)) + Vector3(1.5, 0, -0.5), 0.8, true, "mak")
	# map v3: named villagers of the hamlets who own no garden (chat only) ...
	var vill := {}
	for v in layout.get("villages", []):
		vill[v["id"]] = v
	for id in DEALS_SCRIPT.EXTRAS:
		var e: Dictionary = DEALS_SCRIPT.EXTRAS[id]
		var v: Dictionary = vill.get(e["village"], {})
		var at := v3(v.get("center", [0, 0]))
		var hs: Array = v.get("houses", [])
		if not hs.is_empty():
			var hid: String = hs[absi(hash(id)) % hs.size()]
			if door_points.has(hid):
				at = door_points[hid] + Vector3(0.6, 0, 1.4)
		if not is_walkable(at.x, at.z) or not is_free(at.x, at.z, 0.3):
			at = v3(v.get("center", [0, 0])) + Vector3(2.5, 0, 2.5)
		at.y = height_at(at.x, at.z)
		var n := _extra(e["model"], e["name"], at, float(e.get("radius", 4.0)), true, id)
		extras[id] = n
		var eid: String = id
		var ename: String = e["name"]
		interactables.append({"node": n, "r": 1.6, "npc": true, "prompt": func(): return "Ngobrol dengan " + ename,
			"act": func(): deals.talk_extra(eid)})
	# ... and passers-by walking the roads from hamlet to hamlet
	var centres: Array = []
	for v in layout.get("villages", []):
		centres.append(v3(v["center"]))
	if not centres.is_empty():
		for i in DEALS_SCRIPT.WALKER_MODELS.size():
			var c: Vector3 = centres[i % centres.size()] + Vector3(randf_range(-4, 4), 0, randf_range(2.5, 4.5))
			c.y = height_at(c.x, c.z)
			var n := _extra(DEALS_SCRIPT.WALKER_MODELS[i], "Warga", c, 4.0, true, "walker%d" % i)
			n.set_meta("walker", i)
			walkers.append(n)
			_walker_t.append(randf_range(20.0, 90.0))
			var wi := i
			interactables.append({"node": n, "r": 1.5, "npc": true, "prompt": func(): return "Sapa warga",
				"act": func(): deals.talk_walker(wi)})
	for vid in GS.VILLAGERS:
		refresh_villager(vid)


func _extra(model: String, n: String, pos: Vector3, radius: float, sleeps: bool, look := "") -> Npc:
	var npc := Npc.new()
	npc.look_key = look
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
		var a := house.lerp(pc, 0.35)
		# (map v3: some hamlet gardens lie across a river from the house; stay on this bank)
		if house.distance_to(pc) > 40.0 or not is_walkable(a.x, a.z) or not is_free(a.x, a.z, 0.3):
			a = house + Vector3(0, 0, 1.5)
		npc.set_anchor(a, 5.0)


func _worker_anchor(vid: String) -> Vector3:
	var owned: Array = []
	for p in GS.parcels:
		if p["owner"] == "player":
			owned.append(p)
	var p: Dictionary = owned[absi(hash(vid)) % owned.size()]
	var ph: Array = layout.get("parcel_half", [6.6, 4.4])
	return v3(p["center"]) + Vector3(0, 0, float(ph[1]) + 1.3)


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
		var n := _extra("char_buruh", "Buruh", Vector3.ZERO, 6.0, true, "buruh%d" % worker_npcs.size())
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
	tm.rings = 64
	tm.ring_segments = 6
	_ring.mesh = tm
	_ring.scale = Vector3(1, 0.25, 1)
	# a dashed cream ring like the target's (env fix round), slowly turning
	var m := ShaderMaterial.new()
	m.shader = RING_SHADER
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


func _govern_fps(delta: float) -> void:
	## Every second: below ~55 fps the 3D resolution steps down (to 0.55), above ~59
	## it creeps back up. Nothing else changes (same shadows, outlines, NPCs, detail).
	_fps_acc += delta
	_fps_frames += 1
	if _fps_acc < 1.0:
		return
	var fps := _fps_frames / _fps_acc
	_fps_acc = 0.0
	_fps_frames = 0
	var top := 1.0 if quality_high else 0.75
	if fps < 55.0:
		_res_scale = maxf(0.55, _res_scale - (0.1 if fps < 40.0 else 0.05))
	elif fps > 59.0:
		_res_scale = minf(top, _res_scale + 0.05)
	_res_scale = minf(_res_scale, top)
	get_viewport().scaling_3d_scale = _res_scale


func _apply_lod(n: Node) -> void:
	## Small scenery (houses, fences, props, decor) is not drawn beyond ~75 m: the play
	## camera sees ~40 m around the player, and the 5x island has thousands of pieces.
	if n is GeometryInstance3D and not (n is MultiMeshInstance3D):
		var g := n as GeometryInstance3D
		var ab := g.get_aabb()
		if ab.size.length() * g.global_transform.basis.get_scale().x < 30.0:
			g.visibility_range_end = 75.0
			g.visibility_range_end_margin = 6.0
	for c in n.get_children():
		if c == player or c is Camera3D:
			continue
		_apply_lod(c)


func start_game(load_save: bool) -> void:
	_apply_lod(self)
	if load_save:
		if not GS.load_game():
			GS.new_game()
	else:
		GS.new_game()
	# saves from before the env fix round carry the old 3.2 m-grid parcel centres; the
	# tiles are placed from the layout, so keep the (minimap's) centres in step with it
	for lp in layout.get("parcels", []):
		for p in GS.parcels:
			if int(p["id"]) == int(lp["id"]):
				p["center"] = lp["center"]
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
	for idx in GS.tile_count():
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
	fishing.cancel()
	if GS.last_slept and inside == "rumah_juragan":
		# wake up beside the bed
		player.global_position = interior.bed_pos()
		player.facing = Vector3(0, 0, 1)
		cam_rig.global_position = player.global_position
	else:
		if inside != "":
			_leave_interior()
		player.global_position = door_points.get("rumah_juragan", door_points.get("kantor", player.global_position))
		player.facing = Vector3(0, 0, 1)
		cam_rig.global_position = player.global_position
	ui.show_morning(report)


func _tile_action(pid: int, idx: int) -> void:
	var kind := GS.do_tile_action(pid, idx)
	if kind == "":
		Sfx.play("bad", 1.0, -6.0)
		return
	var tv: TileView = tile_views["%d:%d" % [pid, idx]]
	player.do_action_anim(kind, tv.global_position)
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
			burst(tv.global_position + Vector3(0, 2.1, 0) + _to_player(tv.global_position) * 0.7, Color("c9401f"), 10)
			float_text(tv.global_position + Vector3(0, 1.0, 0), "+TBS", Color("b8401f"))
			_drop_bunches(tv.global_position)


func _to_player(at: Vector3) -> Vector3:
	## flat unit vector from a palm toward the player (camera side if on top of it)
	var d := player.global_position - at
	d.y = 0.0
	return d.normalized() if d.length() > 0.2 else Vector3(0, 0, 1)


func _drop_bunches(at: Vector3) -> void:
	## Cut fruit bunches thud down beside the harvester and lie there for a few
	## seconds: at the farmer's feet on the camera side, out from under the crown
	## (as in the target frame), one to each side so the body never hides them.
	if not ModelLib.has_model("tbs"):
		return
	var to_p := _to_player(at)
	var side := Vector3(-to_p.z, 0, to_p.x)
	var feet := player.global_position
	for i in 2:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh("tbs", false)
		var s := -1.0 if i == 0 else 1.0
		var land := feet + side * s * randf_range(0.5, 0.65) + Vector3(0, 0, randf_range(0.2, 0.4))
		land.y = height_at(land.x, land.z)
		mi.position = at + Vector3(0, 2.2, 0) + to_p * 0.6
		mi.rotation = Vector3(randf() * 0.6, randf() * TAU, randf() * 0.6)
		add_child(mi)
		var shadow := GroundFx.blob(0.32, 0.4)
		shadow.position = land + Vector3(0, 0.03, 0)
		shadow.visible = false
		add_child(shadow)
		var tw := create_tween()
		tw.tween_interval(0.25 + i * 0.15)
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


var _burst_mesh: SphereMesh
var _burst_scale: Curve


func burst(pos: Vector3, color: Color, amount := 14) -> void:
	## A puff of small soft-shaded bits (fruitlets, leaf scraps, soil, fertiliser)
	## tinted by `color` with a little per-bit variation, shrinking away at the end.
	if _burst_mesh == null:
		_burst_mesh = SphereMesh.new()
		_burst_mesh.radius = 0.5
		_burst_mesh.height = 0.9
		_burst_mesh.radial_segments = 8
		_burst_mesh.rings = 4
		var m := StandardMaterial3D.new()
		m.vertex_color_use_as_albedo = true
		m.roughness = 0.55
		m.rim_enabled = true
		m.rim = 0.3
		_burst_mesh.material = m
		_burst_scale = Curve.new()
		_burst_scale.add_point(Vector2(0.0, 0.6))
		_burst_scale.add_point(Vector2(0.15, 1.0))
		_burst_scale.add_point(Vector2(0.7, 0.9))
		_burst_scale.add_point(Vector2(1.0, 0.0))
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.amount = amount
	p.lifetime = 0.8
	p.explosiveness = 0.95
	p.direction = Vector3.UP
	p.spread = 70.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 4.0
	p.gravity = Vector3(0, -9.0, 0)
	p.angular_velocity_min = -360.0
	p.angular_velocity_max = 360.0
	p.scale_amount_min = 0.07
	p.scale_amount_max = 0.12
	p.scale_amount_curve = _burst_scale
	var g := Gradient.new()
	g.set_color(0, color.lightened(0.12))
	g.set_color(1, color.darkened(0.3))
	p.color_initial_ramp = g
	p.mesh = _burst_mesh
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
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
	_govern_fps(delta)
	RenderingServer.global_shader_parameter_set("wind_time", _t)
	if state == "play" and not ui.is_blocking():
		GS.advance(delta)
	_update_daylight()
	_update_camera(delta)
	for i in boats.size():
		var b: MeshInstance3D = boats[i]
		b.position.y = water_level - 0.08 + sin(_t * 1.3 + i * 2.0) * 0.05
		b.rotation.z = sin(_t * 0.9 + i) * 0.03
	_update_walkers(delta)
	if state == "play":
		_update_target()
	else:
		_ring.visible = false


func _update_walkers(delta: float) -> void:
	## Passers-by: after a while in one hamlet they set off along the roads to another.
	var vs: Array = layout.get("villages", [])
	if vs.size() < 2:
		return
	for i in walkers.size():
		_walker_t[i] -= delta
		if _walker_t[i] > 0.0:
			continue
		_walker_t[i] = randf_range(70.0, 150.0)
		var n: Npc = walkers[i]
		if n.talking or GS.hour > 17.5:
			continue
		var v: Dictionary = vs[randi() % vs.size()]
		var c := v3(v["center"]) + Vector3(randf_range(-5, 5), 0, randf_range(2.5, 5.0))
		if not is_walkable(c.x, c.z) or not is_free(c.x, c.z, 0.5):
			continue
		c.y = height_at(c.x, c.z)
		n.home = c
		n.set_anchor(c, 5.0)


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
		amb *= LQ_AMBIENT_TINT
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
		# the fly-over's shadows stop ~45 m out (the far half of its frame is a few pixels
		# per plant; full range cost ~100k extra shadow triangles over the 400k budget)
		_place_camera(34.0, 48.0, 45.0)
		RenderingServer.global_shader_parameter_set("player_pos", Vector3(0, -1000, 0))
		return
	# smooth, frame-rate independent follow (a touch of lag reads as "floaty" camera)
	var vel: Vector3 = player.velocity
	vel.y = 0.0
	_move_lead = _move_lead.lerp((vel * CAM_MOVE_LEAD).limit_length(2.4), 1.0 - exp(-delta * 2.0))
	# the interpolated transform: the player moves at the 60 Hz physics tick, frames can
	# come at any rate; following the raw position made the view judder ("patah-patah")
	var target_pos := player.get_global_transform_interpolated().origin + Vector3(0, 0.5, -cam_lead) + _move_lead
	var k := 1.0 - exp(-delta * 4.0)
	cam_rig.global_position = cam_rig.global_position.lerp(target_pos, k)
	var dist := cam_distance
	var fov := 35.0
	var pitch := cam_pitch
	if inside != "":
		# the room: closer and steeper, centred on the room more than on the player
		dist = interior.cam_dist()
		pitch = 57.0
		var room: Vector3 = interior.cam_center()
		cam_rig.global_position = cam_rig.global_position.lerp(room.lerp(target_pos, 0.2), k)
	if aspect < 1.0:
		# portrait phones: the camera keeps the vertical field of view, so the narrow
		# screen shows little ground across; pull back and widen a little
		# (9:19.5 -> x1.54 and 39 deg: ~8.5 m across instead of ~4.9 m)
		var a := clampf(aspect, 0.0, 1.0)
		dist *= lerpf(2.0, 1.0, a)
		fov = lerpf(42.0, 35.0, a)
	camera.fov = fov
	_place_camera(dist, pitch)
	# see-through hole around the player
	var pp := player.global_position + Vector3(0, 0.7, 0)
	# (characters fix round: while harvesting, Player.reveal 0..1, the hole widens and
	# climbs toward the bunch being cut and also takes the fronds hanging just in front
	# of the hat, so the farmer, the pole, the bunch and the fallen fruit all read)
	var rv: float = player.reveal
	var sp := camera.unproject_position(pp.lerp(player.reveal_at + Vector3(0, 2.2, 0), 0.3 * rv))
	RenderingServer.global_shader_parameter_set("occlude_center", Vector2(sp.x / vp.x, sp.y / vp.y))
	var local := camera.global_transform.affine_inverse() * pp
	RenderingServer.global_shader_parameter_set("occlude_depth", -local.z + 0.8 * rv)
	# (env fix round: a tighter hole, ~0.12 of the screen height at play distance; the
	# shaders fade it with fine interleaved-gradient noise instead of a 4x4 Bayer grid)
	RenderingServer.global_shader_parameter_set("occlude_radius", lerpf(0.075, 0.17, rv) * 24.0 / dist)
	# low plants bend away from the player's feet (foliage_body.gdshaderinc)
	RenderingServer.global_shader_parameter_set("player_pos", player.global_position if player.visible else Vector3(0, -1000, 0))


func _place_camera(dist: float, pitch_deg: float, max_shadow := 70.0) -> void:
	var pitch := deg_to_rad(pitch_deg)
	camera.position = Vector3(0, sin(pitch) * dist, cos(pitch) * dist)
	camera.rotation = Vector3(-pitch, 0, 0)
	# shadows must reach the ground at the top edge of the frame: its depth along the
	# view axis is h / sin(pitch - fov/2) * cos(fov/2) (~1.5 x dist at 45 deg); the
	# last 20% of the shadow range fades out, hence the / 0.8
	var half := deg_to_rad(camera.fov * 0.5)
	var h := sin(pitch) * dist + 1.0
	var depth := h / sin(maxf(pitch - half, 0.2)) * cos(half)
	var sd := clampf(depth / 0.8, 20.0, max_shadow)
	if absf(sd - sun.directional_shadow_max_distance) > 0.05:
		sun.directional_shadow_max_distance = sd


func _update_target() -> void:
	if fishing.active or _fading:
		_ring.visible = false
		return
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
	if best.is_empty() and inside == "":
		best = _fish_target()
	if best.is_empty() and inside == "" and animals:
		best = animals.pet_target()   # "Elus <hewan>": lowest priority, only when nothing else is in reach
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
	var ry := water_level + 0.04 if best.has("fish") else height_at(rp.x, rp.z) + 0.08
	_ring.global_position = Vector3(rp.x, ry, rp.z)
	var s := 1.0 + sin(_t * 5.0) * 0.06
	var base := 1.2 if best.has("tile") else 0.8
	_ring.scale = Vector3(base * s, 0.25, base * s)


func try_action() -> void:
	if state != "play" or ui.is_blocking() or _fading:
		return
	if fishing.active:
		fishing.press()
		return
	if target.is_empty():
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
	elif event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_B:
		if not fishing.active:
			ui.show_bag()


# ------------------------------------------------------------------ fishing
func water_kind(x: float, z: float) -> String:
	## "sea" / "river" if (x, z) is open water deep enough to fish, else ""
	if x > INTERIOR_X or terrain_height(x, z) > water_level - 0.08:
		return ""
	for rv in layout.get("rivers", []):
		var pts: Array = rv["pts"]
		var hw: float = float(rv.get("hw", 4.0)) + 3.0
		for i in pts.size() - 1:
			var a := Vector2(pts[i][0], pts[i][1])
			var b := Vector2(pts[i + 1][0], pts[i + 1][1])
			var q := Geometry2D.get_closest_point_to_segment(Vector2(x, z), a, b)
			if q.distance_squared_to(Vector2(x, z)) < hw * hw:
				return "river"
	return "sea"


func fishing_spot() -> Dictionary:
	## open water 2-4 m in front of the player: {"pos": Vector3 on the surface, "water"}
	var pp := player.global_position
	var f := Vector3(player.facing.x, 0, player.facing.z).normalized()
	if pp.x > INTERIOR_X:
		return {}
	for d in [2.4, 3.2, 4.0, 1.8]:
		var p: Vector3 = pp + f * d
		var k := water_kind(p.x, p.z)
		if k != "" and not is_walkable(p.x, p.z) and not is_walkable(p.x + f.x * 0.6, p.z + f.z * 0.6):
			return {"pos": Vector3(p.x, water_level, p.z), "water": k}
	return {}


func _fish_target() -> Dictionary:
	_fish_probe_t -= get_process_delta_time()
	if _fish_probe_t <= 0.0:
		_fish_probe_t = 0.12
		_fish_spot = fishing_spot()
	if _fish_spot.is_empty():
		return {}
	var sp: Dictionary = _fish_spot
	return {"pos": sp["pos"], "r": 5.0, "fish": true, "_pos": sp["pos"],
		"prompt": func(): return ("Butuh pancing (beli di Koperasi)" if int(GS.inv.get("pancing", 0)) <= 0
			else ("Umpan habis (beli di Koperasi)" if int(GS.inv.get("umpan", 0)) <= 0 else "Mancing (umpan %d)" % int(GS.inv.get("umpan", 0)))),
		"ok": func(): return int(GS.inv.get("pancing", 0)) > 0 and int(GS.inv.get("umpan", 0)) > 0,
		"act": func(): start_fishing()}


func start_fishing() -> bool:
	var sp := fishing_spot()
	if sp.is_empty():
		return false
	return fishing.start(sp["pos"], sp["water"])


# ------------------------------------------------------------------ houses
func house_owner(hid: String) -> String:
	for vid in GS.VILLAGERS:
		if GS.VILLAGERS[vid]["home"] == hid:
			return vid
	return ""


func house_prompt(hid: String) -> String:
	if hid == "rumah_juragan":
		return "Masuk rumahmu"
	var vid := house_owner(hid)
	if vid != "":
		return "Masuk rumah " + GS.vname(vid)
	return "Masuk rumah warga"


func _owner_home(vid: String) -> bool:
	## is the villager in their house right now?
	if vid == "":
		return false
	var v: Dictionary = GS.villagers[vid]
	if v.get("evicted", false):
		return false
	if GS.hour >= 17.0 or GS.hour < 7.5:
		return true
	if v["worker"]:
		return false
	return absi(hash(vid + str(GS.day) + str(int(GS.hour / 3.0)))) % 3 != 0


func _build_interior_items() -> void:
	## interaction spots inside the room (shared by every house)
	interactables.append({"pos": interior.door_pos() + Vector3(0, 0, 0.3), "r": 1.6, "door": true,
		"prompt": func(): return "Keluar rumah", "act": func(): exit_house()})
	# (every house has its own room layout: interior.setup_for moves these two spots)
	_bed_item = {"pos": interior.to_world(interior.bed_local), "r": 2.1,
		"prompt": func(): return bed_prompt(), "ok": func(): return inside == "rumah_juragan",
		"act": func(): use_bed()}
	interactables.append(_bed_item)
	_cup_item = {"pos": interior.to_world(interior.cupboard_local) + Vector3(0, 0, 0.5), "r": 1.5,
		"prompt": func(): return "Buka lemari (Tas)" if inside == "rumah_juragan" else "Lemari milik tuan rumah",
		"ok": func(): return inside == "rumah_juragan", "act": func(): ui.show_bag()}
	interactables.append(_cup_item)


func bed_prompt() -> String:
	if inside == "rumah_juragan":
		return "Tidur di kasur"
	if _inside_vid != "":
		return "Kasur %s (jangan tidur di rumah orang!)" % GS.vname(_inside_vid)
	return "Kasur warga (bukan milikmu)"


func use_bed() -> void:
	if inside != "rumah_juragan":
		return
	deals.sleep_in_bed()


func enter_house(hid: String, instant := false) -> void:
	if inside != "" or _fading or not door_points.has(hid):
		return
	var vid := house_owner(hid)
	var v: Dictionary = GS.villagers.get(vid, {})
	if vid != "" and v.get("evicted", false):
		ui.toast("Rumah %s kosong dan digembok. Pemiliknya kini tinggal di tenda biru..." % GS.vname(vid), "bad")
		return
	Sfx.play("door", 1.0, -4.0)
	_fade(func():
		inside = hid
		_inside_vid = vid if _owner_home(vid) else ""
		interior.setup_for(hid, _inside_vid)
		_bed_item["pos"] = interior.bed_world()
		_cup_item["pos"] = interior.cupboard_world()
		if _inside_vid != "":
			var on: Node3D = interior.owner_node()
			var ovid := _inside_vid
			var it := {"node": on, "r": 1.9, "npc": true, "house": true,
				"prompt": func(): return "Ngobrol dengan " + GS.vname(ovid), "act": func(): deals.talk(ovid)}
			_house_items.append(it)
			interactables.append(it)
		player.global_position = interior.door_pos()
		player.facing = Vector3(0, 0, -1)
		player.velocity = Vector3.ZERO
		cam_rig.global_position = player.global_position
		_ring.visible = false
		ambient.visible = false   # no birds or butterflies in the living room
		ui.on_inside_changed()
		if hid == "rumah_juragan":
			ui.toast("Rumahmu. Tidur di kasur untuk lanjut hari & menyimpan.", "info")
		elif _inside_vid == "" and vid != "":
			ui.toast("%s sedang tidak di rumah." % GS.vname(vid), "info")
		elif vid == "":
			ui.toast("Rumah warga. Penghuninya sedang keluar.", "info"), instant)


func exit_house(instant := false) -> void:
	if inside == "" or _fading:
		return
	Sfx.play("door", 1.0, -4.0)
	_fade(func(): _leave_interior(), instant)


func _leave_interior() -> void:
	var hid := inside
	for it in _house_items:
		interactables.erase(it)
	_house_items.clear()
	interior.leave()
	inside = ""
	_inside_vid = ""
	var d: Vector3 = door_points.get(hid, door_points.get("kantor", Vector3.ZERO))
	var node: Node3D = building_nodes.get(hid)
	var out := Vector3(0, 0, 1)
	if node:
		out = (node.global_transform.basis * Vector3(0, 0, 1)).normalized()
	player.global_position = Vector3(d.x, height_at(d.x, d.z), d.z) + out * 0.3
	player.facing = out
	player.velocity = Vector3.ZERO
	cam_rig.global_position = player.global_position
	ui.on_inside_changed()
	ambient.visible = true


func _fade(mid: Callable, instant := false) -> void:
	## screen fades to dark, `mid` runs, fades back (instant: no fade, for tests)
	if instant:
		mid.call()
		return
	_fading = true
	player.locked = true
	ui.fade_screen(mid, func():
		_fading = false
		if state == "play" and not ui.is_blocking():
			player.locked = false)
