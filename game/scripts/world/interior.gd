extends Node3D
## The inside of a house, far off the island at ORIGIN. Each house gets its own room,
## built on entry and freed on exit:
##   * the room TYPE follows the house model (layout.json): rumah_a "kayu" (plank house),
##     rumah_b "jahit" (tailor's plank house), rumah_c "dapur" (big kitchen-living room),
##     rumah_d "panggung" (stilt house: woven bamboo walls, tikar, kasur on the floor),
##     rumah_e "limas" (big family room: sofa, TV, bufet with plates, family photos),
##     rumah_f "bata" (brick: tiled floor, plastic chairs, fridge, kitchen corner),
##     rumah_g "pondok" (tiny hut: hammock, fishing gear, sacks) and the player's
##     rumah_juragan (bed, desk with ledger and money, franchise poster, fan).
##   * each type has its own size / shape, and a seed from the house id varies it:
##     mirrored layout, wall / floor / rug / blanket colours, optional furniture, wall
##     decorations, plants and clutter, so no two houses look the same.
## All parts use the ModelLib toon materials (cel light + ink outlines). No ceiling and a
## low front wall with the door gap in the middle (cut-away view for the play camera).

const ORIGIN := Vector3(400, 0, 400)
const WALL_H := 2.7
const WOOD_DARK := "6e5040"

const TYPE_BY_MODEL := {"rumah_a": "kayu", "rumah_b": "jahit", "rumah_c": "dapur", "rumah_d": "panggung",
	"rumah_e": "limas", "rumah_f": "bata", "rumah_g": "pondok"}
## inner half size (x, z) of each room type
const SIZES := {"juragan": Vector2(4.6, 3.3), "kayu": Vector2(4.0, 3.0), "jahit": Vector2(3.7, 2.9),
	"dapur": Vector2(4.4, 3.1), "panggung": Vector2(4.3, 2.7), "limas": Vector2(5.0, 3.5),
	"bata": Vector2(3.9, 3.0), "pondok": Vector2(2.7, 2.1)}
const TYPE_NAMES := {"juragan": "Rumah Juragan", "kayu": "rumah kayu", "jahit": "rumah kayu (penjahit)",
	"dapur": "rumah limas kayu", "panggung": "rumah panggung", "limas": "rumah limas",
	"bata": "rumah bata", "pondok": "pondok"}

const PLASTER := ["e3d3b0", "d3dcc2", "e0cbbd", "cad8d6", "e6dab8", "ddd3c2", "c8d4e0", "e8c9a8"]
const WOODS := ["b0804e", "a47650", "c09060", "9a7048", "b88a58"]
const BAMBOO := ["d8bc84", "ccb078", "e0c690", "c4a46c"]
const RUGS := ["a8584a", "4f767c", "b8904e", "6a8050", "5c7a8e", "8e5a7a", "c07a48"]
const BLANKETS := ["6a8eaa", "b8745e", "7a9258", "c8a458", "86789e", "d08a8a", "5f9a92"]
const CURTAINS := ["d8b070", "c89078", "98b09a", "b0a0b8", "e0a0a0", "90b0c8"]
const SOFAS := ["8a4a3a", "5a6e8a", "6e7a4a", "a0703a", "7a5a7a"]
const PLASTIC := ["d9402a", "3a74c0", "2f9a5a", "e8b030", "e8e0d0"]

var world: Node
var house_id := ""
var owner_vid := ""   # villager at home ("" = nobody)
var kind := ""        # room type (see TYPE_BY_MODEL)
var half := Vector2(4.0, 3.0)
var door_local := Vector3(0, 0, 2.35)
var bed_local := Vector3(2.55, 0, -1.75)
var bed_side := Vector3(-1.05, 0, 0.55)   # where the player stands / wakes beside the bed
var cupboard_local := Vector3(-3.05, 0, -2.45)
var owner_local := Vector3(-1.2, 0, 1.25)

var _room: Node3D
var _lamp: OmniLight3D
var _shaft: MeshInstance3D
var _pane_mat: ShaderMaterial
var _fan: Node3D
var _has_back_window := false
var _owner_node: Node3D
var _owner_anim: CharAnim
var _t := 0.0
var _mx := 1.0        # layout mirror (x sign) while placing furniture
var _rng := RandomNumberGenerator.new()
var _free_spots: Array = []   # floor spots left for clutter
static var _models := {}      # house id -> model (from layout.json)
static var _tex_cache := {}


func _ready() -> void:
	position = ORIGIN
	_build_static()
	visible = false


# ------------------------------------------------------------------ materials / primitives
func _mat(col: String, outline := true, tag := "") -> Material:
	var m := StandardMaterial3D.new()
	m.resource_name = "M_Interior" + tag
	m.albedo_color = Color(col)
	return ModelLib.convert_material(m, false, 0.0, outline)


func _tmat(col: String, tex: Texture2D) -> Material:
	var m := StandardMaterial3D.new()
	m.resource_name = "M_InteriorTex"
	m.albedo_color = Color(col)
	m.albedo_texture = tex
	return ModelLib.convert_material(m, false, 0.0, false)


func _P(v: Vector3) -> Vector3:
	return Vector3(v.x * _mx, v.y, v.z)


func _R(r: Vector3) -> Vector3:
	return Vector3(r.x, r.y * _mx, r.z * _mx)


func _box(size: Vector3, pos: Vector3, col: String, collide := false, rot := Vector3.ZERO, tag := "") -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = _mat(col, true, tag)
	mi.position = _P(pos)
	mi.rotation = _R(rot)
	_room.add_child(mi)
	if collide:
		_collider(size, pos, rot.y)
	return mi


func _collider(size: Vector3, pos: Vector3, rot_y := 0.0) -> void:
	var b := StaticBody3D.new()
	b.collision_layer = 1
	b.collision_mask = 0
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	var h := maxf(size.y, 1.2)
	sh.size = Vector3(size.x, h, size.z)
	cs.shape = sh
	b.add_child(cs)
	b.position = _P(pos + Vector3(0, h * 0.5 - size.y * 0.5, 0))
	b.rotation.y = rot_y * _mx
	_room.add_child(b)


func _cyl(r_top: float, r_bot: float, h: float, pos: Vector3, col: String, sides := 12, rot := Vector3.ZERO, tag := "") -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r_top
	cm.bottom_radius = r_bot
	cm.height = h
	cm.radial_segments = sides
	cm.rings = 1
	mi.mesh = cm
	mi.material_override = _mat(col, true, tag)
	mi.position = _P(pos)
	mi.rotation = _R(rot)
	_room.add_child(mi)
	return mi


func _ball(r: float, pos: Vector3, col: String, squash := 1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = r
	s.height = r * 2.0 * squash
	s.radial_segments = 12
	s.rings = 6
	mi.mesh = s
	mi.material_override = _mat(col)
	mi.position = _P(pos)
	_room.add_child(mi)
	return mi


func _plane(size: Vector2, pos: Vector3, col: String, tex: Texture2D, facing := "up") -> MeshInstance3D:
	## a flat textured surface (floors, woven walls, mats); no outline
	var mi := MeshInstance3D.new()
	if facing == "up":
		var pm := PlaneMesh.new()
		pm.size = size
		mi.mesh = pm
	else:
		var qm := QuadMesh.new()
		qm.size = size
		mi.mesh = qm
		match facing:
			"+x": mi.rotation.y = PI * 0.5 * _mx
			"-x": mi.rotation.y = -PI * 0.5 * _mx
	mi.material_override = _tmat(col, tex) if tex else _mat(col, false)
	mi.position = _P(pos)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_room.add_child(mi)
	return mi


func _label(text: String, pos: Vector3, size: int, col: Color, facing := "+z") -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font = ModelLib.label_font()
	l.font_size = size
	l.pixel_size = 0.004
	l.modulate = col
	l.outline_size = 0
	l.double_sided = false
	l.position = _P(pos) + Vector3(0, 0, 0.01 if facing == "+z" else 0.0)
	if facing == "+x":
		l.rotation.y = PI * 0.5 * _mx
		l.position.x += 0.01 * _mx
	elif facing == "-x":
		l.rotation.y = -PI * 0.5 * _mx
		l.position.x -= 0.01 * _mx
	_room.add_child(l)
	return l


func _pick(a: Array):
	return a[_rng.randi() % a.size()]


# ------------------------------------------------------------------ procedural textures
func _tex(kind_t: String, cols: int, rows: int, seed_v := 0) -> Texture2D:
	var key := "%s|%d|%d|%d" % [kind_t, cols, rows, seed_v]
	if _tex_cache.has(key):
		return _tex_cache[key]
	var r := RandomNumberGenerator.new()
	r.seed = seed_v + 7
	var img: Image
	match kind_t:
		"plank":   # floor planks running along x, `rows` planks across the depth
			var cw := 32
			img = Image.create(cols * cw, rows * 16, false, Image.FORMAT_RGB8)
			for j in rows:
				var tone := 0.86 + r.randf() * 0.14
				img.fill_rect(Rect2i(0, j * 16, cols * cw, 16), Color(tone, tone, tone))
				img.fill_rect(Rect2i(0, j * 16, cols * cw, 1), Color(0.55, 0.55, 0.55))
				var x := r.randi_range(10, cols * cw / 2)
				while x < cols * cw:
					img.fill_rect(Rect2i(x, j * 16, 1, 16), Color(0.6, 0.6, 0.6))
					x += r.randi_range(cols * cw / 3, cols * cw)
		"tile":
			var tp := 16
			img = Image.create(cols * tp, rows * tp, false, Image.FORMAT_RGB8)
			for i in cols:
				for j in rows:
					var c := 1.0 if (seed_v % 2 == 0 or (i + j) % 2 == 0) else 0.82
					img.fill_rect(Rect2i(i * tp, j * tp, tp, tp), Color(c, c, c))
					img.fill_rect(Rect2i(i * tp, j * tp, tp, 1), Color(0.7, 0.7, 0.7))
					img.fill_rect(Rect2i(i * tp, j * tp, 1, tp), Color(0.7, 0.7, 0.7))
		"slat":    # bamboo floor slats along z with dark gaps
			img = Image.create(cols * 8, 64, false, Image.FORMAT_RGB8)
			for i in cols:
				var tone := 0.85 + r.randf() * 0.15
				img.fill_rect(Rect2i(i * 8, 0, 8, 64), Color(tone, tone, tone))
				img.fill_rect(Rect2i(i * 8, 0, 1, 64), Color(0.35, 0.3, 0.28))
				img.fill_rect(Rect2i(i * 8, r.randi_range(0, 60), 8, 2), Color(tone * 0.8, tone * 0.8, tone * 0.8))
		"weave":   # anyaman bambu (bilik)
			var c8 := 8
			img = Image.create(cols * c8, rows * c8, false, Image.FORMAT_RGB8)
			for i in cols:
				for j in rows:
					var hor := (i + j) % 2 == 0
					var base := 0.95 if hor else 0.8
					img.fill_rect(Rect2i(i * c8, j * c8, c8, c8), Color(base, base, base))
					for s in 3:
						var o := 1 + s * 3
						if hor:
							img.fill_rect(Rect2i(i * c8, j * c8 + o, c8, 1), Color(base * 0.8, base * 0.8, base * 0.8))
						else:
							img.fill_rect(Rect2i(i * c8 + o, j * c8, 1, c8), Color(base * 0.8, base * 0.8, base * 0.8))
		"vplank":  # vertical wall planks
			img = Image.create(cols * 12, 64, false, Image.FORMAT_RGB8)
			for i in cols:
				var tone := 0.86 + r.randf() * 0.14
				img.fill_rect(Rect2i(i * 12, 0, 12, 64), Color(tone, tone, tone))
				img.fill_rect(Rect2i(i * 12, 0, 1, 64), Color(0.5, 0.5, 0.5))
		"brick":
			img = Image.create(cols * 16, rows * 8, false, Image.FORMAT_RGB8)
			img.fill(Color(0.78, 0.76, 0.72))
			for j in rows:
				var off := 8 if j % 2 == 1 else 0
				for i in cols + 1:
					var t := 0.85 + r.randf() * 0.15
					img.fill_rect(Rect2i(i * 16 - off + 1, j * 8 + 1, 14, 6), Color(t, t * 0.97, t * 0.95))
		"tikar":   # woven mat with coloured bands
			img = Image.create(64, 64, false, Image.FORMAT_RGB8)
			for y in 64:
				var band := (y / 8) % 4
				var c: Color = [Color(1, 1, 1), Color(0.85, 0.35, 0.3), Color(1, 1, 1), Color(0.35, 0.55, 0.45)][band]
				for x in 64:
					var k := 0.92 if (x + y) % 4 < 2 else 1.0
					img.set_pixel(x, y, Color(c.r * k, c.g * k, c.b * k))
		_:
			img = Image.create(4, 4, false, Image.FORMAT_RGB8)
			img.fill(Color.WHITE)
	img.generate_mipmaps()
	var t := ImageTexture.create_from_image(img)
	_tex_cache[key] = t
	return t


# ------------------------------------------------------------------ static parts
func _build_static() -> void:
	# dark void around the room (the background colour would read as sky)
	var void_mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	void_mi.mesh = pm
	var vm := StandardMaterial3D.new()
	vm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	vm.albedo_color = Color("2a1d14")
	void_mi.material_override = vm
	void_mi.position.y = -0.3
	void_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(void_mi)
	_shaft = MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2(1.4, 1.9)
	_shaft.mesh = qm
	var sm := StandardMaterial3D.new()
	sm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	sm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	sm.albedo_color = Color(1.0, 0.9, 0.6, 0.1)
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill_from = Vector2(0.5, 0.0)
	gt.fill_to = Vector2(0.5, 1.0)
	sm.albedo_texture = gt
	_shaft.material_override = sm
	_shaft.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_shaft.rotation = Vector3(deg_to_rad(-62), 0, 0)
	add_child(_shaft)
	_lamp = OmniLight3D.new()
	_lamp.light_color = Color(1.0, 0.8, 0.5)
	_lamp.omni_range = 5.5
	_lamp.shadow_enabled = false
	add_child(_lamp)
	var pmat := StandardMaterial3D.new()
	pmat.resource_name = "M_Interior_Pane"
	pmat.albedo_color = Color("cfe8f0")
	_pane_mat = ModelLib.convert_material(pmat, false)


# ------------------------------------------------------------------ room type
static func room_type(hid: String) -> String:
	if hid == "rumah_juragan":
		return "juragan"
	if _models.is_empty():
		for b in GS.load_layout().get("buildings", []):
			_models[str(b["id"])] = str(b.get("model", ""))
	return TYPE_BY_MODEL.get(_models.get(hid, ""), "kayu")


# ------------------------------------------------------------------ shell
func _shell(style: Dictionary) -> void:
	## floor, walls (back / sides full, front low with the door gap), trims, window
	var hx := half.x
	var hz := half.y
	var t := 0.2
	var wall: String = style["wall"]
	var trim: String = style.get("trim", WOOD_DARK)
	# floor: a base slab, then the textured surface
	_box(Vector3(hx * 2 + 0.6, 0.3, hz * 2 + 0.6), Vector3(0, -0.15, 0), style.get("floor_base", "5a4430"))
	var ft: String = style["floor_tex"]
	var ftex: Texture2D
	match ft:
		"plank": ftex = _tex("plank", int(hx), int(hz * 2 / 0.4), _rng.randi() % 5)
		"tile": ftex = _tex("tile", int(hx * 2 / 0.5), int(hz * 2 / 0.5), _rng.randi() % 2)
		"slat": ftex = _tex("slat", int(hx * 2 / 0.12), 1, _rng.randi() % 5)
		_: ftex = null
	_plane(Vector2(hx * 2, hz * 2), Vector3(0, 0.005, 0), style["floor"], ftex)
	# walls
	_box(Vector3(hx * 2 + t * 2, WALL_H, t), Vector3(0, WALL_H * 0.5, -hz - t * 0.5), wall, true)
	_box(Vector3(t, WALL_H, hz * 2), Vector3(-hx - t * 0.5, WALL_H * 0.5, 0), wall, true)
	_box(Vector3(t, WALL_H, hz * 2), Vector3(hx + t * 0.5, WALL_H * 0.5, 0), wall, true)
	var wt: String = style.get("wall_tex", "")
	if wt != "":
		var wtex: Texture2D
		match wt:
			"weave": wtex = _tex("weave", int(hx * 2 / 0.14), int(WALL_H / 0.14))
			"vplank": wtex = _tex("vplank", int(hx * 2 / 0.22), 1, _rng.randi() % 5)
			"brick": wtex = _tex("brick", int(hx * 2 / 0.25), int(WALL_H / 0.09))
		var wtex_s: Texture2D = wtex
		match wt:
			"weave": wtex_s = _tex("weave", int(hz * 2 / 0.14), int(WALL_H / 0.14))
			"vplank": wtex_s = _tex("vplank", int(hz * 2 / 0.22), 1, 3)
			"brick": wtex_s = _tex("brick", int(hz * 2 / 0.25), int(WALL_H / 0.09))
		_plane(Vector2(hx * 2, WALL_H), Vector3(0, WALL_H * 0.5, -hz + 0.004), wall, wtex, "+z")
		_plane(Vector2(hz * 2, WALL_H), Vector3(-hx + 0.004, WALL_H * 0.5, 0), wall, wtex_s, "+x")
		_plane(Vector2(hz * 2, WALL_H), Vector3(hx - 0.004, WALL_H * 0.5, 0), wall, wtex_s, "-x")
	if style.get("wainscot", "") != "":
		# a painted / tiled lower band on plaster walls
		var wc: String = style["wainscot"]
		_box(Vector3(hx * 2, 0.9, 0.03), Vector3(0, 0.45, -hz + 0.015), wc)
		_box(Vector3(0.03, 0.9, hz * 2), Vector3(-hx + 0.015, 0.45, 0), wc)
		_box(Vector3(0.03, 0.9, hz * 2), Vector3(hx - 0.015, 0.45, 0), wc)
		_box(Vector3(hx * 2, 0.05, 0.05), Vector3(0, 0.92, -hz + 0.025), trim)
	var seg := hx - 0.75
	for s in [-1.0, 1.0]:
		_box(Vector3(seg + t, 0.55, t), Vector3(s * (0.75 + seg * 0.5 + t * 0.5), 0.275, hz + t * 0.5), wall, true)
		_box(Vector3(seg + t, 0.07, t + 0.06), Vector3(s * (0.75 + seg * 0.5 + t * 0.5), 0.58, hz + t * 0.5), trim)
		_box(Vector3(0.14, 0.9, 0.26), Vector3(s * 0.8, 0.45, hz + t * 0.5), trim, true)
	# skirting + top trims
	_box(Vector3(hx * 2, 0.14, 0.05), Vector3(0, 0.07, -hz + 0.02), trim)
	_box(Vector3(hx * 2 + t * 2, 0.1, t + 0.06), Vector3(0, WALL_H + 0.05, -hz - t * 0.5), trim)
	_box(Vector3(t + 0.06, 0.1, hz * 2), Vector3(-hx - t * 0.5, WALL_H + 0.05, 0), trim)
	_box(Vector3(t + 0.06, 0.1, hz * 2), Vector3(hx + t * 0.5, WALL_H + 0.05, 0), trim)
	if style.get("posts", false):
		# corner / mid posts of the timber frame
		for px in [-hx + 0.08, hx - 0.08]:
			_box(Vector3(0.16, WALL_H, 0.16), Vector3(px, WALL_H * 0.5, -hz + 0.08), trim)
		_box(Vector3(0.14, WALL_H, 0.12), Vector3(0, WALL_H * 0.5, -hz + 0.06), trim)
	# door mat
	_box(Vector3(1.1, 0.03, 0.6), Vector3(0, 0.02, hz - 0.4), _pick(["b89a5a", "8a6a9a", "5a8a6a", "c0704a"]))


func _window(x: float, width: float, trim: String, curtain: String, side := false) -> void:
	## a window on the back wall (or the left wall when side) with a shaft of light
	var hz := half.y
	var hx := half.x
	if side:
		_box(Vector3(0.06, 1.0, width), Vector3(-hx + 0.01, 1.55, x), "cfe8f0").material_override = _pane_mat
		_box(Vector3(0.12, 0.1, width + 0.16), Vector3(-hx + 0.05, 2.08, x), trim)
		_box(Vector3(0.2, 0.1, width + 0.16), Vector3(-hx + 0.08, 1.02, x), trim)
		_box(Vector3(0.1, 1.0, 0.08), Vector3(-hx + 0.05, 1.55, x), trim)
		return
	_box(Vector3(width, 1.1, 0.06), Vector3(x, 1.55, -hz + 0.01), "cfe8f0").material_override = _pane_mat
	_box(Vector3(width + 0.16, 0.1, 0.12), Vector3(x, 2.13, -hz + 0.05), trim)
	_box(Vector3(width + 0.16, 0.1, 0.2), Vector3(x, 0.97, -hz + 0.08), trim)
	_box(Vector3(0.08, 1.1, 0.1), Vector3(x, 1.55, -hz + 0.05), trim)
	_box(Vector3(width, 0.06, 0.08), Vector3(x, 1.55, -hz + 0.05), trim)
	if curtain != "":
		for s in [-1.0, 1.0]:
			_box(Vector3(0.34, 1.3, 0.05), Vector3(x + s * (width * 0.5 + 0.1), 1.5, -hz + 0.1), curtain)
	_shaft.position = _P(Vector3(x + 0.25, 0.8, -hz + 0.95))
	_shaft.visible = true
	_has_back_window = true


# ------------------------------------------------------------------ furniture
func _bed(p: Vector3, wood: String, blanket: String, fancy := false) -> void:
	## frame bed, head against the back (-z)
	var w := 1.8 if fancy else 1.5
	_box(Vector3(w, 0.34, 2.2), p + Vector3(0, 0.25, 0), wood, true)
	_box(Vector3(w, 1.2 if fancy else 0.95, 0.12), p + Vector3(0, 0.6 if fancy else 0.48, -1.1), wood)
	_box(Vector3(w + 0.1, 0.08, 0.16), p + Vector3(0, 1.22 if fancy else 0.98, -1.1), WOOD_DARK)
	if fancy:
		_box(Vector3(w, 0.55, 0.1), p + Vector3(0, 0.4, 1.1), wood)
		for s in [-1.0, 1.0]:
			_cyl(0.06, 0.06, 1.35, p + Vector3(s * (w * 0.5), 0.67, -1.1), WOOD_DARK, 8)
	_box(Vector3(w - 0.1, 0.18, 2.06), p + Vector3(0, 0.5, 0.02), "f6efe0")
	var pillows := 2 if fancy else 1
	for i in pillows:
		var px := 0.0 if pillows == 1 else (i - 0.5) * 0.8
		_box(Vector3(0.7 if fancy else 0.95, 0.16, 0.42), p + Vector3(px, 0.66, -0.78), "fffaf0")
	_box(Vector3(w - 0.04, 0.1, 1.3), p + Vector3(0, 0.62, 0.4), blanket)
	_box(Vector3(w - 0.02, 0.14, 0.1), p + Vector3(0, 0.6, -0.26), "fffaf0")
	if fancy:
		# guling (bolster), a batik runner
		_cyl(0.1, 0.1, 0.8, p + Vector3(w * 0.3, 0.72, 0.1), "f0e6d0", 10, Vector3(PI * 0.5, 0, 0))
		_box(Vector3(w, 0.04, 0.4), p + Vector3(0, 0.68, 0.85), "b8703a")


func _floor_kasur(p: Vector3, blanket: String) -> void:
	## a kasur kapuk straight on the floor
	_box(Vector3(1.3, 0.2, 2.0), p + Vector3(0, 0.1, 0), "f0e4c8", true)
	_box(Vector3(1.32, 0.04, 2.02), p + Vector3(0, 0.03, 0), "c8a070")
	_box(Vector3(0.8, 0.14, 0.38), p + Vector3(0, 0.27, -0.72), "fffaf0")
	_box(Vector3(1.26, 0.08, 1.1), p + Vector3(0, 0.24, 0.35), blanket)
	_cyl(0.09, 0.09, 0.7, p + Vector3(0.5, 0.29, -0.1), "e8d8b8", 10, Vector3(PI * 0.5, 0, 0))


func _nightstand(p: Vector3, wood: String, lamp := true) -> void:
	_box(Vector3(0.5, 0.55, 0.45), p + Vector3(0, 0.275, 0), wood, true)
	_box(Vector3(0.52, 0.04, 0.47), p + Vector3(0, 0.57, 0), WOOD_DARK)
	if lamp:
		_cyl(0.07, 0.09, 0.2, p + Vector3(0, 0.68, 0), "6a4a2a")
		_cyl(0.12, 0.19, 0.2, p + Vector3(0, 0.87, 0), "f4e2b8", 12, Vector3.ZERO, "_Lamp")


func _lemari(p: Vector3, wood: String, w := 1.3) -> void:
	_box(Vector3(w, 2.0, 0.58), p + Vector3(0, 1.0, 0), wood, true)
	for s in [-1.0, 1.0]:
		_box(Vector3(w * 0.45, 1.7, 0.04), p + Vector3(s * w * 0.245, 1.05, 0.3), Color(wood).lightened(0.1).to_html(false))
		_cyl(0.035, 0.035, 0.05, p + Vector3(s * 0.08, 1.05, 0.33), "e0b04a", 8, Vector3(PI * 0.5, 0, 0))
	_box(Vector3(w + 0.1, 0.08, 0.64), p + Vector3(0, 2.04, 0), WOOD_DARK)
	if _rng.randf() < 0.6:
		_cyl(0.2, 0.16, 0.2, p + Vector3(0.25, 2.18, 0), "c9a95e", 10)
	if _rng.randf() < 0.5:
		_box(Vector3(0.4, 0.26, 0.4), p + Vector3(-0.3, 2.21, 0), _pick(["c8a070", "b86a4a", "7a8ab0"]))


func _table(p: Vector3, wood: String, stools := 2, chair_col := "") -> void:
	_box(Vector3(1.3, 0.08, 0.85), p + Vector3(0, 0.74, 0), wood, true)
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_box(Vector3(0.08, 0.7, 0.08), p + Vector3(sx * 0.55, 0.35, sz * 0.34), WOOD_DARK)
	var seats := [Vector3(-1.0, 0, 0.05), Vector3(1.0, 0, 0.05), Vector3(0, 0, 0.75)]
	for i in mini(stools, 3):
		var s: Vector3 = p + seats[i]
		if chair_col != "":
			_plastic_chair(s, chair_col, [PI * 0.5, -PI * 0.5, PI][i])
		else:
			_cyl(0.2, 0.18, 0.08, s + Vector3(0, 0.46, 0), "947050")
			_cyl(0.04, 0.05, 0.42, s + Vector3(0, 0.21, 0), WOOD_DARK, 6)
	# things on the table
	var top := p + Vector3(0, 0.78, 0)
	match _rng.randi() % 4:
		0:
			_cyl(0.1, 0.13, 0.18, top + Vector3(0.1, 0.09, -0.05), _pick(["4f8a8a", "c05a3a", "e8e0d0"]))
			for i in 2:
				_cyl(0.05, 0.04, 0.09, top + Vector3(-0.3 + i * 0.7, 0.045, 0.18), "fffaf0", 8)
		1:
			_cyl(0.22, 0.2, 0.05, top + Vector3(0, 0.025, 0), "e8e0d0", 14)   # tudung saji base
			_ball(0.24, top + Vector3(0, 0.06, 0), _pick(["d9402a", "3a74c0", "e8b030"]), 0.55)
		2:
			_cyl(0.16, 0.12, 0.12, top + Vector3(0.2, 0.06, 0), "c9a95e", 10)
			for i in 3:
				_ball(0.06, top + Vector3(0.14 + i * 0.07, 0.14, 0.02 * i), ["e8b030", "d9402a", "6a9a3a"][i])
		3:
			_box(Vector3(0.9, 0.01, 0.5), top + Vector3(0, 0.005, 0), "f0e6d0")
			_cyl(0.07, 0.06, 0.22, top + Vector3(-0.2, 0.11, 0), "7ab0c8", 8)


func _low_table(p: Vector3, wood: String) -> void:
	_box(Vector3(1.2, 0.07, 0.75), p + Vector3(0, 0.33, 0), wood, true)
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_box(Vector3(0.08, 0.3, 0.08), p + Vector3(sx * 0.52, 0.15, sz * 0.3), WOOD_DARK)
	_cyl(0.16, 0.12, 0.08, p + Vector3(-0.2, 0.41, 0), "fffaf0", 12)
	_cyl(0.09, 0.11, 0.16, p + Vector3(0.25, 0.44, -0.08), "8a5a3a", 10)
	_cyl(0.05, 0.04, 0.08, p + Vector3(0.1, 0.41, 0.2), "fffaf0", 8)


func _rug(p: Vector3, size: Vector2, col: String) -> void:
	_box(Vector3(size.x, 0.02, size.y), p + Vector3(0, 0.012, 0), "f0dcb0")
	_box(Vector3(size.x - 0.28, 0.026, size.y - 0.28), p + Vector3(0, 0.016, 0), col)
	_box(Vector3(size.x - 0.9, 0.03, 0.1), p + Vector3(0, 0.018, 0), "f0dcb0")


func _tikar(p: Vector3, size: Vector2, col: String) -> void:
	_plane(size, p + Vector3(0, 0.02, 0), col, _tex("tikar", 1, 1))
	_box(Vector3(size.x + 0.06, 0.012, size.y + 0.06), p + Vector3(0, 0.01, 0), Color(col).darkened(0.35).to_html(false))


func _sofa(p: Vector3, col: String, rot := 0.0, seats := 3) -> void:
	## rot 0: facing +z (back against -z)
	var w := 0.7 * seats + 0.3
	var b := Basis(Vector3.UP, rot)
	var parts := [
		[Vector3(w, 0.4, 0.85), Vector3(0, 0.2, 0), WOOD_DARK],
		[Vector3(w, 0.7, 0.2), Vector3(0, 0.6, -0.34), col],
		[Vector3(0.18, 0.62, 0.85), Vector3(-w * 0.5 + 0.09, 0.44, 0), col],
		[Vector3(0.18, 0.62, 0.85), Vector3(w * 0.5 - 0.09, 0.44, 0), col],
	]
	for pr in parts:
		_box(pr[0], p + b * pr[1], pr[2], false, Vector3(0, rot, 0))
	for i in seats:
		var off := Vector3((i - (seats - 1) * 0.5) * 0.7, 0.47, 0.06)
		_box(Vector3(0.66, 0.16, 0.66), p + b * off, Color(col).lightened(0.12).to_html(false), false, Vector3(0, rot, 0))
	var sz := Vector3(w, 0.8, 0.85) if absf(sin(rot)) < 0.5 else Vector3(0.85, 0.8, w)
	_collider(sz, p + Vector3(0, 0.4, 0))
	if _rng.randf() < 0.7:
		_box(Vector3(0.36, 0.34, 0.12), p + b * Vector3(-w * 0.5 + 0.4, 0.68, -0.18), _pick(["e8b030", "fffaf0", "d08a8a"]), false, Vector3(-0.3, rot, 0))


func _tv(p: Vector3, wood: String, rot := 0.0) -> void:
	## low cabinet with a boxy TV (screen towards +z before rot), a remote and an antenna
	var bs := Basis(Vector3.UP, rot)
	var r := Vector3(0, rot, 0)
	_box(Vector3(1.5, 0.6, 0.5), p + Vector3(0, 0.3, 0), wood, false, r)
	_collider(Vector3(1.5, 0.6, 0.5) if absf(sin(rot)) < 0.5 else Vector3(0.5, 0.6, 1.5), p + Vector3(0, 0.3, 0))
	for s in [-1.0, 1.0]:
		_box(Vector3(0.66, 0.46, 0.03), p + bs * Vector3(s * 0.36, 0.3, 0.26), Color(wood).lightened(0.12).to_html(false), false, r)
	_box(Vector3(0.9, 0.62, 0.5), p + bs * Vector3(0, 0.92, -0.02), "3a3a42", false, r)
	_box(Vector3(0.74, 0.5, 0.02), p + bs * Vector3(0, 0.93, 0.24), "4a6a8a", false, r, "_Glass")
	_box(Vector3(0.2, 0.2, 0.1), p + bs * Vector3(0.52, 0.7, 0.1), "6a6a70", false, r)
	for s in [-1.0, 1.0]:
		_cyl(0.008, 0.008, 0.5, p + bs * Vector3(s * 0.12, 1.4, -0.1), "c0c0c8", 4, Vector3(0, rot, s * 0.5))
	_box(Vector3(0.16, 0.03, 0.05), p + bs * Vector3(-0.5, 0.62, 0.1), "2a2a2a", false, r)


func _bufet(p: Vector3, wood: String) -> void:
	## a glass-front cabinet with plates standing on edge and glasses
	_box(Vector3(1.4, 1.8, 0.5), p + Vector3(0, 0.9, 0), wood, true)
	_box(Vector3(1.24, 0.9, 0.02), p + Vector3(0, 1.3, 0.25), "d8eef4", false, Vector3.ZERO, "_Glass")
	_box(Vector3(1.24, 0.05, 0.4), p + Vector3(0, 1.3, 0.05), WOOD_DARK)
	for i in 5:
		_cyl(0.13, 0.13, 0.02, p + Vector3(-0.48 + i * 0.24, 1.49, 0.02), _pick(["fffaf0", "f0e0c0", "c8e0e8"]), 14, Vector3(PI * 0.5, 0, 0))
	for i in 4:
		_cyl(0.04, 0.035, 0.12, p + Vector3(-0.42 + i * 0.28, 0.96 + 0.06, 0.05), "c8e8f0", 8)
	_box(Vector3(1.46, 0.07, 0.56), p + Vector3(0, 1.83, 0), WOOD_DARK)
	_cyl(0.1, 0.07, 0.26, p + Vector3(0.4, 1.99, 0), "c05a3a", 10)   # a vase
	_box(Vector3(0.06, 0.34, 0.24), p + Vector3(-0.4, 2.03, 0), _pick(["d9402a", "3a74c0"]))


func _fridge(p: Vector3) -> void:
	_box(Vector3(0.68, 1.55, 0.62), p + Vector3(0, 0.78, 0), _pick(["e8e8e0", "c8d8e0", "e8d0d0"]), true)
	_box(Vector3(0.66, 0.02, 0.02), p + Vector3(0, 1.1, 0.32), "9a9aa0")
	_box(Vector3(0.04, 0.3, 0.05), p + Vector3(-0.26, 1.3, 0.33), "9a9aa0")
	_box(Vector3(0.04, 0.3, 0.05), p + Vector3(-0.26, 0.8, 0.33), "9a9aa0")
	for i in 3:   # magnets
		_box(Vector3(0.08, 0.08, 0.02), p + Vector3(0.05 + i * 0.1, 1.35 - i * 0.07, 0.32), ["d9402a", "e8b030", "3a74c0"][i])
	_box(Vector3(0.3, 0.14, 0.24), p + Vector3(0, 1.62, 0), "c9a95e")


func _kitchen(p: Vector3, w := 2.0) -> void:
	## counter along the back wall: kompor with a wajan, gas tank, dish rack, jerigen of minyak
	_box(Vector3(w, 0.85, 0.6), p + Vector3(0, 0.425, 0), _pick(["b8b0a0", "c0a080", "a8b8b0"]), true)
	_box(Vector3(w + 0.04, 0.05, 0.64), p + Vector3(0, 0.87, 0), _pick(["e8e0d0", "d0d8d0"]))
	_box(Vector3(0.6, 0.1, 0.4), p + Vector3(-w * 0.5 + 0.45, 0.94, 0), "3a3a3a")
	_cyl(0.2, 0.12, 0.08, p + Vector3(-w * 0.5 + 0.45, 1.03, 0), "4a4a4a", 12)
	_cyl(0.16, 0.16, 0.42, p + Vector3(-w * 0.5 + 0.35, 0.21, 0.5), "3a8a3a", 12)   # tabung gas melon
	_box(Vector3(0.6, 0.3, 0.3), p + Vector3(w * 0.5 - 0.4, 1.05, -0.05), "c0c0c8")
	for i in 4:
		_cyl(0.12, 0.12, 0.015, p + Vector3(w * 0.5 - 0.6 + i * 0.12, 1.2, -0.05), "fffaf0", 12, Vector3(PI * 0.5, 0, 0))
	_box(Vector3(0.2, 0.3, 0.14), p + Vector3(0.1, 1.04, 0.05), "e8c040")   # minyak goreng
	_box(Vector3(w, 0.05, 0.28), p + Vector3(0, 1.75, -0.14), WOOD_DARK)   # shelf
	for i in 4:
		_cyl(0.07, 0.07, 0.16, p + Vector3(-w * 0.5 + 0.3 + i * 0.45, 1.86, -0.14), _pick(["d9402a", "e8b030", "8a5a3a", "fffaf0"]), 8)


func _tungku(p: Vector3) -> void:
	## a clay wood stove with a pot, firewood and a gentong (water jar)
	_box(Vector3(1.1, 0.55, 0.6), p + Vector3(0, 0.275, 0), "a0643a", true)
	_box(Vector3(0.3, 0.22, 0.05), p + Vector3(0, 0.2, 0.3), "2a1a10")
	_cyl(0.22, 0.18, 0.26, p + Vector3(-0.22, 0.68, 0), "4a4a4a", 12)
	_cyl(0.18, 0.14, 0.1, p + Vector3(0.3, 0.6, 0), "6a6a6a", 12)
	for i in 4:
		_cyl(0.045, 0.045, 0.7, p + Vector3(0.8 + (i % 2) * 0.1, 0.06 + (i / 2) * 0.09, 0.1 + (i % 2) * 0.08), "7a5a3a", 6, Vector3(PI * 0.5, 0.3, 0))
	_cyl(0.26, 0.2, 0.55, p + Vector3(-0.9, 0.28, 0.1), "b0603a", 12)
	_cyl(0.2, 0.26, 0.08, p + Vector3(-0.9, 0.59, 0.1), "b0603a", 12)


func _plastic_chair(p: Vector3, col: String, rot := 0.0) -> void:
	var b := Basis(Vector3.UP, rot)
	_box(Vector3(0.46, 0.05, 0.44), p + Vector3(0, 0.44, 0), col, false, Vector3(0, rot, 0))
	_box(Vector3(0.46, 0.46, 0.05), p + b * Vector3(0, 0.7, -0.21), col, false, Vector3(-0.12, rot, 0))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_box(Vector3(0.05, 0.44, 0.05), p + b * Vector3(sx * 0.19, 0.22, sz * 0.18), col, false, Vector3(0, rot, 0))


func _hammock(a: Vector3, b: Vector3, col: String) -> void:
	## a sagging net between two posts
	for q in [a, b]:
		_cyl(0.06, 0.07, 1.5, q + Vector3(0, 0.75, 0), "8a6a4a", 8)
	var n := 7
	for i in n:
		var u0 := float(i) / n
		var u1 := float(i + 1) / n
		var p0 := a.lerp(b, u0) + Vector3(0, 1.25 - sin(u0 * PI) * 0.7, 0)
		var p1 := a.lerp(b, u1) + Vector3(0, 1.25 - sin(u1 * PI) * 0.7, 0)
		var mid := (p0 + p1) * 0.5
		var d := p1 - p0
		var ang := atan2(d.y, Vector2(d.x, d.z).length())
		var yaw := atan2(-d.z, d.x)
		var seg := _box(Vector3(d.length() + 0.02, 0.04, 0.7), mid, col if i % 2 == 0 else Color(col).lightened(0.2).to_html(false))
		seg.rotation = _R(Vector3(0, yaw, ang))


func _fishing_gear(p: Vector3) -> void:
	for i in 3:
		_cyl(0.012, 0.02, 2.0, p + Vector3(-0.2 + i * 0.18, 1.0, -0.05), "c9a95e", 6, Vector3(-0.18, 0, -0.1 + i * 0.1))
	_cyl(0.2, 0.16, 0.34, p + Vector3(0.45, 0.17, 0.25), "3a74c0", 12)   # bucket
	_box(Vector3(0.8, 0.12, 0.5), p + Vector3(-0.2, 0.06, 0.45), "4f8a7a")  # folded net
	for i in 4:
		_ball(0.05, p + Vector3(-0.5 + i * 0.2, 0.15, 0.45), "e8b030", 0.7)  # floats


func _sacks(p: Vector3, n: int) -> void:
	for i in n:
		var q := p + Vector3((i % 3) * 0.5 - 0.5, (i / 3) * 0.42, (i % 2) * 0.12)
		_cyl(0.24, 0.27, 0.46, q + Vector3(0, 0.23, 0), _pick(["b8a878", "a89868", "c0ac80"]), 10)
		_cyl(0.1, 0.24, 0.1, q + Vector3(0, 0.5, 0), "a89060", 10)
	_collider(Vector3(1.5, 0.8, 0.7), p + Vector3(0, 0.4, 0.05))


func _desk(p: Vector3) -> void:
	## the juragan's desk: ledger, stacks of money, a calculator and a desk lamp
	_box(Vector3(1.6, 0.08, 0.75), p + Vector3(0, 0.76, 0), "5a3a24", true)
	_box(Vector3(0.5, 0.72, 0.72), p + Vector3(-0.52, 0.36, 0), "6a4630")
	for sx in [1.0]:
		for sz in [-1.0, 1.0]:
			_box(Vector3(0.07, 0.72, 0.07), p + Vector3(sx * 0.74, 0.36, sz * 0.32), "5a3a24")
	_box(Vector3(0.56, 0.04, 0.4), p + Vector3(-0.1, 0.82, 0.08), "7a2a22")   # ledger
	_box(Vector3(0.52, 0.045, 0.36), p + Vector3(-0.1, 0.84, 0.08), "f6efe0")
	for i in 3:
		_box(Vector3(0.24, 0.05 + i * 0.03, 0.12), p + Vector3(0.45, 0.83 + i * 0.015, -0.18 + i * 0.13), ["d0605a", "6aa060", "d0605a"][i])
	_box(Vector3(0.16, 0.03, 0.22), p + Vector3(0.3, 0.815, 0.18), "3a3a3a")
	_cyl(0.06, 0.08, 0.04, p + Vector3(0.62, 0.82, -0.2), "3a3a3a", 10)
	_cyl(0.015, 0.015, 0.35, p + Vector3(0.62, 0.99, -0.2), "3a3a3a", 6)
	_cyl(0.06, 0.12, 0.12, p + Vector3(0.58, 1.16, -0.15), "2f6d4a", 10, Vector3(0.5, 0, 0), "_Lamp")
	# chair
	_box(Vector3(0.5, 0.06, 0.5), p + Vector3(0, 0.48, 0.7), "7a2a22")
	_box(Vector3(0.5, 0.6, 0.08), p + Vector3(0, 0.8, 0.95), "7a2a22")
	_cyl(0.04, 0.04, 0.45, p + Vector3(0, 0.23, 0.7), "3a3a3a", 6)


func _safe(p: Vector3) -> void:
	_box(Vector3(0.6, 0.7, 0.55), p + Vector3(0, 0.35, 0), "4a5058", true)
	_cyl(0.08, 0.08, 0.04, p + Vector3(0.05, 0.4, 0.28), "e0b04a", 12, Vector3(PI * 0.5, 0, 0))


func _standing_fan(p: Vector3) -> void:
	_cyl(0.22, 0.24, 0.05, p + Vector3(0, 0.03, 0), "3a3a42", 12)
	_cyl(0.025, 0.025, 1.1, p + Vector3(0, 0.6, 0), "c0c0c8", 6)
	_fan = Node3D.new()
	_fan.position = _P(p + Vector3(0, 1.2, 0.05))
	_room.add_child(_fan)
	var cage := _cyl(0.3, 0.3, 0.14, p + Vector3(0, 1.2, 0), "c8d8e0", 14, Vector3(PI * 0.5, 0, 0))
	cage.transparency = 0.5
	for i in 3:
		var bl := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.1, 0.25, 0.02)
		bl.mesh = bm
		bl.material_override = _mat("5a8ab8")
		bl.rotation.z = i * TAU / 3.0
		bl.position = Vector3(0, 0, 0.09) + Basis(Vector3.BACK, i * TAU / 3.0) * Vector3(0, 0.13, 0)
		_fan.add_child(bl)


func _plant(p: Vector3, big := false) -> void:
	var s := 1.3 if big else 1.0
	_cyl(0.2 * s, 0.15 * s, 0.36 * s, p + Vector3(0, 0.18 * s, 0), _pick(["b8653a", "3a74c0", "e8e0d0", "7a5a3a"]))
	var green: String = _pick(["5c8a3a", "4a7a3a", "6a9a44"])
	for i in 6:
		var leaf := _box(Vector3(0.12 * s, 0.55 * s, 0.04), p + Vector3(0, 0.6 * s, 0), green)
		leaf.rotation = _R(Vector3(deg_to_rad(20 + (i % 2) * 10), i * TAU / 6.0, 0))


func _sewing(p: Vector3) -> void:
	## a treadle sewing machine table, cloth rolls and a dress form
	_box(Vector3(1.0, 0.06, 0.5), p + Vector3(0, 0.76, 0), "7a5a44", true)
	for sx in [-1.0, 1.0]:
		_box(Vector3(0.06, 0.74, 0.44), p + Vector3(sx * 0.45, 0.37, 0), "3a3a3a")
	_box(Vector3(0.6, 0.05, 0.3), p + Vector3(0, 0.1, 0.05), "3a3a3a")
	_box(Vector3(0.5, 0.12, 0.18), p + Vector3(0, 0.85, 0), "2a2a2a")
	_box(Vector3(0.12, 0.26, 0.16), p + Vector3(0.2, 0.98, 0), "2a2a2a")
	_box(Vector3(0.44, 0.1, 0.14), p + Vector3(0, 1.12, 0), "2a2a2a")
	_box(Vector3(0.1, 0.04, 0.14), p + Vector3(-0.1, 1.08, 0), "d0b040")
	for i in 3:
		_cyl(0.07, 0.07, 0.8, p + Vector3(0.9 + i * 0.16, 0.07 + (i % 2) * 0.13, 0.1), _pick(["d9402a", "3a74c0", "e8b030", "8e5a7a", "2f9a5a"]), 10, Vector3(PI * 0.5, 0, 0))
	# dress form
	_cyl(0.03, 0.03, 1.0, p + Vector3(-0.95, 0.5, 0.2), "3a3a3a", 6)
	_ball(0.22, p + Vector3(-0.95, 1.2, 0.2), _pick(["d0b8a0", "e8d8c8"]), 1.6)
	_cyl(0.2, 0.26, 0.05, p + Vector3(-0.95, 0.03, 0.2), "3a3a3a", 10)


func _shelf_radio(p: Vector3, wood: String) -> void:
	## a wall shelf with a radio, books and a jar
	_box(Vector3(1.0, 0.05, 0.26), p + Vector3(0, 1.5, 0), wood)
	_box(Vector3(0.42, 0.26, 0.18), p + Vector3(-0.2, 1.66, 0), _pick(["8a3a2a", "3a5a7a", "c0a040"]))
	_cyl(0.07, 0.07, 0.02, p + Vector3(-0.28, 1.66, 0.1), "3a3a3a", 10, Vector3(PI * 0.5, 0, 0))
	_cyl(0.006, 0.006, 0.4, p + Vector3(-0.05, 1.95, 0), "c0c0c8", 4, Vector3(0, 0, -0.4))
	for i in 3:
		_box(Vector3(0.06, 0.24, 0.18), p + Vector3(0.18 + i * 0.07, 1.645, 0), ["3a74c0", "d9402a", "e8b030"][i])


# ------------------------------------------------------------------ wall decorations / clutter
func _wall_decor(x: float, y := 1.75) -> void:
	## one random decoration on the back wall at x
	var z := -half.y + 0.03
	match _rng.randi() % 7:
		0:   # landscape picture
			_box(Vector3(0.8, 0.6, 0.04), Vector3(x, y, z), WOOD_DARK)
			_box(Vector3(0.68, 0.48, 0.045), Vector3(x, y, z + 0.005), _pick(["8fbf7a", "8ab8d8", "e8c080"]))
			_box(Vector3(0.3, 0.14, 0.05), Vector3(x + 0.1, y - 0.1, z + 0.01), "5c8a3a")
			_cyl(0.06, 0.06, 0.05, Vector3(x - 0.2, y + 0.12, z + 0.01), "e9b949", 10, Vector3(PI * 0.5, 0, 0))
		1:   # wall clock
			_cyl(0.23, 0.23, 0.04, Vector3(x, y + 0.2, z), WOOD_DARK, 16, Vector3(PI * 0.5, 0, 0))
			_cyl(0.2, 0.2, 0.05, Vector3(x, y + 0.2, z + 0.01), "fffaf0", 16, Vector3(PI * 0.5, 0, 0))
			_box(Vector3(0.02, 0.14, 0.02), Vector3(x, y + 0.26, z + 0.04), "3a3a3a")
			_box(Vector3(0.1, 0.02, 0.02), Vector3(x + 0.05, y + 0.2, z + 0.04), "3a3a3a")
		2:   # calendar (kalender toko)
			_box(Vector3(0.44, 0.62, 0.02), Vector3(x, y, z), "fffaf0")
			_box(Vector3(0.44, 0.24, 0.025), Vector3(x, y + 0.19, z + 0.002), _pick(["d9402a", "3a74c0", "2f9a5a"]))
			for r in 3:
				_box(Vector3(0.36, 0.02, 0.026), Vector3(x, y - 0.02 - r * 0.08, z + 0.002), "b0a090")
		3:   # family photos (three small frames)
			for i in 3:
				var fx := x - 0.34 + i * 0.34
				var fy := y + (0.08 if i == 1 else -0.04)
				_box(Vector3(0.26, 0.32, 0.03), Vector3(fx, fy, z), _pick(["e0b04a", WOOD_DARK, "3a3a3a"]))
				_box(Vector3(0.2, 0.26, 0.035), Vector3(fx, fy, z + 0.003), _pick(["c8b8a0", "b8a890", "d0c0a8"]))
				_ball(0.045, Vector3(fx, fy + 0.03, z + 0.03), "6a4a3a", 0.3)
		4:   # kaligrafi
			_box(Vector3(0.9, 0.4, 0.03), Vector3(x, y, z), "e0b04a")
			_box(Vector3(0.82, 0.32, 0.035), Vector3(x, y, z + 0.003), "2f5a3a")
			_box(Vector3(0.6, 0.05, 0.04), Vector3(x, y + 0.03, z + 0.006), "e0c060", false, Vector3(0, 0, 0.12))
		5:   # mirror
			_box(Vector3(0.5, 0.7, 0.03), Vector3(x, y, z), WOOD_DARK)
			_box(Vector3(0.42, 0.62, 0.035), Vector3(x, y, z + 0.004), "c8e0e8", false, Vector3.ZERO, "_Glass")
		6:   # a shelf with the radio
			_shelf_radio(Vector3(x, 0, z + 0.12), WOOD_DARK)


func _clutter(n: int) -> void:
	## small things on some of the free floor spots
	_free_spots.shuffle()
	for i in mini(n, _free_spots.size()):
		var p: Vector3 = _free_spots[i]
		match _rng.randi() % 7:
			0: _plant(p, _rng.randf() < 0.4)
			1:   # ember + gayung
				_cyl(0.2, 0.16, 0.32, p + Vector3(0, 0.16, 0), _pick(["3a74c0", "d9402a", "2f9a5a"]), 12)
				_cyl(0.07, 0.07, 0.1, p + Vector3(0.05, 0.36, 0), "e8b030", 8)
			2:   # basket of laundry
				_cyl(0.28, 0.22, 0.3, p + Vector3(0, 0.15, 0), "c9a95e", 12)
				_ball(0.22, p + Vector3(0, 0.3, 0), _pick(["d08a8a", "8ab8d8", "fffaf0"]), 0.5)
			3:   # stack of books / papers
				for k in 3:
					_box(Vector3(0.34, 0.07, 0.26), p + Vector3(0, 0.035 + k * 0.07, 0), _pick(["d9402a", "3a74c0", "e8b030", "fffaf0"]), false, Vector3(0, k * 0.2, 0))
			4:   # a ball and a toy car
				_ball(0.13, p + Vector3(0, 0.13, 0), _pick(["d9402a", "e8b030", "3a74c0"]))
				_box(Vector3(0.22, 0.1, 0.12), p + Vector3(0.3, 0.08, 0.1), "2f9a5a")
			5:   # a cat asleep (a curled ball)
				_ball(0.2, p + Vector3(0, 0.1, 0), _pick(["e8a050", "fffaf0", "4a4a4a"]), 0.5)
				_ball(0.09, p + Vector3(0.16, 0.14, 0.05), "e8a050" if _rng.randf() < 0.5 else "fffaf0", 0.9)
			6:   # termos and a stack of glasses
				_cyl(0.08, 0.08, 0.34, p + Vector3(0, 0.17, 0), _pick(["d9402a", "3a74c0", "e8e0d0"]), 10)
				_cyl(0.05, 0.04, 0.1, p + Vector3(0.18, 0.05, 0), "c8e8f0", 8)


func _sandals() -> void:
	## sandals by the door (the host's)
	var z := half.y - 0.35
	for s in [-1.0, 1.0]:
		var c: String = _pick(["3a74c0", "d9402a", "2f9a5a", "3a3a3a"])
		_box(Vector3(0.12, 0.03, 0.28), Vector3(1.05 + s * 0.08, 0.02, z), c)


# ------------------------------------------------------------------ layouts
func _build_room() -> void:
	_room = Node3D.new()
	_room.name = "Room"
	add_child(_room)
	_fan = null
	_free_spots = []
	var hx := half.x
	var hz := half.y
	_mx = 1.0
	door_local = Vector3(0, 0, hz - 0.65)
	owner_local = Vector3(-1.2, 0, 1.2)
	var wood: String = _pick(WOODS)
	var blanket: String = _pick(BLANKETS)
	var rug: String = _pick(RUGS)
	var curtain: String = _pick(CURTAINS)
	_shaft.visible = false
	_has_back_window = false
	match kind:
		"juragan":
			_shell({"wall": "e8dcc0", "floor": "b08458", "floor_tex": "plank", "wainscot": "8a5a3a", "trim": "5a3a24"})
			_window(0.9, 1.5, "5a3a24", "a8584a")
			_bed(Vector3(3.1, 0, -2.0), "7a4a30", "5a7fa0", true)
			bed_local = Vector3(3.1, 0, -2.0)
			bed_side = Vector3(-1.25, 0, 0.6)
			_nightstand(Vector3(1.85, 0, -2.9), "7a4a30")
			_lamp.position = _P(Vector3(1.85, 1.0, -2.6))
			cupboard_local = Vector3(-3.8, 0, -2.95)
			_lemari(cupboard_local, "7a4a30", 1.2)
			_desk(Vector3(-1.9, 0, -2.75))
			_safe(Vector3(-4.2, 0, -1.7))
			# the franchise poster on the left wall
			_box(Vector3(0.04, 1.2, 0.9), Vector3(-hx + 0.03, 1.65, 0.2), "e0b04a")
			_box(Vector3(0.05, 1.1, 0.8), Vector3(-hx + 0.04, 1.65, 0.2), "c0392b")
			_box(Vector3(0.055, 0.35, 0.35), Vector3(-hx + 0.045, 1.9, 0.2), "3a8a3a")
			_label("SAWIT\nTHE FRANCHISE™", Vector3(-hx + 0.08, 1.45, 0.2), 30, Color("fdf3dc"), "+x")
			_label("JURAGAN NO.1", Vector3(-hx + 0.08, 1.2, 0.2), 20, Color("f4d35e"), "+x")
			_standing_fan(Vector3(-3.9, 0, 1.5))
			_rug(Vector3(0.6, 0, 0.3), Vector2(3.4, 2.2), "a8584a")
			_sofa(Vector3(0.4, 0, 1.55), "8a4a3a", PI, 2)
			_plant(Vector3(4.2, 0, 2.8), true)
			_wall_decor(-0.6, 1.9)
			_box(Vector3(0.9, 0.5, 0.04), Vector3(3.1, 2.1, -hz + 0.03), "e0b04a")   # a certificate
			_box(Vector3(0.8, 0.4, 0.045), Vector3(3.1, 2.1, -hz + 0.035), "fdf3dc")
			_label("SERTIFIKAT\nPENGUSAHA TELADAN", Vector3(3.1, 2.1, -hz + 0.045), 14, Color("5a3a24"))
			_box(Vector3(0.9, 0.03, 0.4), Vector3(-2.6, 0.02, 2.6), "5a7fa0")
			owner_local = Vector3(-1.5, 0, 1.0)
		"kayu":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			_shell({"wall": _pick(PLASTER), "floor": wood, "floor_tex": "plank", "posts": _rng.randf() < 0.5})
			var wx := _rng.randf_range(-1.0, 0.2)
			_window(wx, 1.4, WOOD_DARK, curtain)
			bed_local = Vector3(2.55, 0, -1.75)
			bed_side = Vector3(-1.05, 0, 0.55)
			_bed(bed_local, wood, blanket)
			_nightstand(bed_local + Vector3(-1.2, 0, -0.95), wood)
			_lamp.position = _P(bed_local + Vector3(-1.2, 1.0, -0.75))
			cupboard_local = Vector3(-3.05, 0, -2.45)
			_lemari(cupboard_local, wood)
			_rug(Vector3(0.3, 0, 0.45), Vector2(3.0, 2.0), rug)
			_table(Vector3(-1.3, 0, 0.1), wood, 2)
			_wall_decor(-1.9 if wx > -0.5 else 1.0)
			_box(Vector3(0.05, 0.7, 0.9), Vector3(-hx + 0.03, 1.7, -0.2), WOOD_DARK)
			_box(Vector3(0.06, 0.56, 0.76), Vector3(-hx + 0.04, 1.7, -0.2), _pick(["8fbf7a", "8ab8d8", "e8c080"]))
			_free_spots = [Vector3(hx - 0.35, 0, 1.9), Vector3(-hx + 0.4, 0, 2.2), Vector3(-hx + 0.4, 0, -1.2), Vector3(1.6, 0, 2.2)]
			_clutter(_rng.randi_range(2, 3))
			owner_local = Vector3(-1.3, 0, 1.3)
		"jahit":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			_shell({"wall": _pick(["b08a60", "a07a54", "c09a6a"]), "wall_tex": "vplank", "floor": _pick(WOODS), "floor_tex": "plank", "trim": "5a3a24"})
			_window(0.0, 1.2, "5a3a24", curtain)
			bed_local = Vector3(2.4, 0, -1.6)
			bed_side = Vector3(-1.0, 0, 0.6)
			_bed(bed_local, wood, blanket)
			_lamp.position = _P(Vector3(0.5, 2.0, -1.0))
			cupboard_local = Vector3(-2.9, 0, -2.4)
			_lemari(cupboard_local, wood, 1.1)
			_sewing(Vector3(-2.3, 0, 0.2))
			_rug(Vector3(0.7, 0, 0.9), Vector2(2.4, 1.6), rug)
			_box(Vector3(1.4, 0.44, 0.5), Vector3(0.5, 0.22, 2.1), wood, true)   # a bench by the door wall
			_shelf_radio(Vector3(-1.4, 0, -half.y + 0.14), WOOD_DARK)
			# cloth hanging on a line along the left wall
			_cyl(0.01, 0.01, 2.4, Vector3(-hx + 0.25, 2.1, 0.4), "c0c0c8", 4, Vector3(PI * 0.5, 0, 0))
			for i in 4:
				_box(Vector3(0.03, 0.6, 0.4), Vector3(-hx + 0.25, 1.78, -0.4 + i * 0.52), _pick(["d9402a", "3a74c0", "e8b030", "8e5a7a", "fffaf0"]))
			_free_spots = [Vector3(hx - 0.35, 0, 1.9), Vector3(-hx + 0.4, 0, 2.0), Vector3(1.8, 0, 0.3)]
			_clutter(_rng.randi_range(1, 2))
			owner_local = Vector3(-0.6, 0, 1.2)
		"dapur":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			_shell({"wall": _pick(["d6a867", "c89a5a", "dcb070"]), "wall_tex": "vplank", "floor": _pick(WOODS), "floor_tex": "plank", "posts": true})
			_window(-0.2, 1.3, WOOD_DARK, curtain)
			bed_local = Vector3(3.0, 0, -1.8)
			bed_side = Vector3(-1.05, 0, 0.6)
			_bed(bed_local, wood, blanket)
			_lamp.position = _P(Vector3(-1.5, 2.0, -0.5))
			cupboard_local = Vector3(1.2, 0, -2.75)
			_bufet(cupboard_local, wood)
			_tungku(Vector3(-3.0, 0, -2.6))
			_sacks(Vector3(-3.6, 0, -0.9), 3)
			_tikar(Vector3(-1.2, 0, 0.8), Vector2(2.6, 1.8), _pick(["e8d8a8", "d8c898"]))
			_low_table(Vector3(-1.2, 0, 0.8), wood)
			_wall_decor(-1.4, 2.0)
			_free_spots = [Vector3(hx - 0.35, 0, 2.2), Vector3(1.3, 0, 0.9), Vector3(-hx + 0.4, 0, 2.3)]
			_clutter(_rng.randi_range(1, 3))
			owner_local = Vector3(0.6, 0, 1.4)
		"panggung":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			var bam: String = _pick(BAMBOO)
			_shell({"wall": bam, "wall_tex": "weave", "floor": _pick(["c8a068", "b89060", "d0a870"]), "floor_tex": "slat",
				"trim": "7a5a38", "posts": true, "floor_base": "3a2a1c"})
			var wx := _rng.randf_range(-0.6, 0.6)
			_window(wx, 1.1, "7a5a38", "")
			bed_local = Vector3(2.7, 0, -1.4)
			bed_side = Vector3(-1.0, 0, 0.5)
			_floor_kasur(bed_local, blanket)
			_lamp.position = _P(Vector3(0.0, 2.1, -0.4))
			# a hanging lamp (lampu teplok) on the back post
			_cyl(0.06, 0.08, 0.16, Vector3(0.0, 1.9, -half.y + 0.16), "e8c060", 8, Vector3.ZERO, "_Lamp")
			_tikar(Vector3(-0.9, 0, 0.5), Vector2(3.0, 2.0), _pick(["f0e0b0", "e8d0a0"]))
			_low_table(Vector3(-0.9, 0, 0.5), "7a5a38")
			for s in [-1.0, 1.0]:   # floor cushions
				_box(Vector3(0.5, 0.08, 0.5), Vector3(-0.9 + s * 1.0, 0.06, 0.6), _pick(RUGS))
			cupboard_local = Vector3(-3.3, 0, -2.2)
			_box(Vector3(1.0, 0.7, 0.5), cupboard_local + Vector3(0, 0.35, 0), "7a5a38", true)   # a peti (chest)
			_box(Vector3(1.04, 0.08, 0.54), cupboard_local + Vector3(0, 0.72, 0), "5a3a24")
			_box(Vector3(0.12, 0.1, 0.04), cupboard_local + Vector3(0, 0.55, 0.26), "e0b04a")
			_cyl(0.28, 0.22, 0.5, Vector3(-hx + 0.4, 0.25, 1.4), "b0603a", 12)   # gentong
			# sarong and clothes hanging on nails
			for i in 3:
				_box(Vector3(0.4, 0.8, 0.03), Vector3(1.1 + i * 0.5, 1.55, -half.y + 0.04), _pick(["8e5a7a", "3a74c0", "2f9a5a", "c05a3a"]))
			_free_spots = [Vector3(hx - 0.35, 0, 1.8), Vector3(-hx + 0.4, 0, -0.8), Vector3(1.4, 0, 1.9)]
			_clutter(_rng.randi_range(1, 2))
			owner_local = Vector3(-0.9, 0, 1.75)
		"limas":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			_shell({"wall": _pick(PLASTER), "floor": _pick(["a89c88", "a0a4a0", "b0a08c"]), "floor_tex": "tile",
				"wainscot": _pick(["a07050", "7a8a6a", "6a7a9a"]), "posts": false})
			_window(-3.0, 1.2, WOOD_DARK, curtain)
			_window(-1.8, 1.0, WOOD_DARK, "", true)
			bed_local = Vector3(3.6, 0, -2.0)
			bed_side = Vector3(-1.1, 0, 0.6)
			_bed(bed_local, wood, blanket)
			# a room divider screen between the bed and the living room
			_box(Vector3(0.06, 1.8, 1.6), Vector3(2.35, 0.9, -2.6), _pick(["c8a070", "8e5a7a", "6a8050"]), true)
			_lamp.position = _P(Vector3(0.0, 2.2, 0.0))
			_rug(Vector3(-0.6, 0, 0.2), Vector2(3.6, 2.4), rug)
			var sofa_col: String = _pick(SOFAS)
			_sofa(Vector3(-0.6, 0, -1.4), sofa_col, 0.0, 3)
			_sofa(Vector3(-3.3, 0, 0.3), sofa_col, PI * 0.5, 2)
			_box(Vector3(1.2, 0.4, 0.7), Vector3(-0.6, 0.2, 0.25), wood, true)   # coffee table
			_cyl(0.12, 0.08, 0.2, Vector3(-0.4, 0.5, 0.25), "fffaf0", 10)
			_box(Vector3(0.3, 0.05, 0.2), Vector3(-0.9, 0.42, 0.3), "e8b030")
			_tv(Vector3(-0.6, 0, 1.9), wood, PI)
			cupboard_local = Vector3(1.3, 0, -3.1)
			_bufet(cupboard_local, wood)
			_mx_decor([-1.6, -0.2], 2.05)
			_plant(Vector3(hx - 0.4, 0, 2.9), true)
			_free_spots = [Vector3(-hx + 0.4, 0, 2.9), Vector3(2.0, 0, 2.6), Vector3(-hx + 0.4, 0, -2.9), Vector3(3.3, 0, 0.6)]
			_clutter(_rng.randi_range(2, 3))
			_sandals()
			owner_local = Vector3(1.4, 0, 0.6)
		"bata":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			var brick := _rng.randf() < 0.5
			_shell({"wall": "c87858" if brick else _pick(PLASTER), "wall_tex": "brick" if brick else "", "floor": _pick(["b4aca0", "a4acb4", "b8a89c"]),
				"floor_tex": "tile", "wainscot": "" if brick else _pick(["7a9aa8", "8a9a7a", "b08a6a"]), "trim": "8a8a8a"})
			_window(0.3, 1.4, "8a8a8a", curtain)
			bed_local = Vector3(2.6, 0, -1.7)
			bed_side = Vector3(-1.05, 0, 0.6)
			_bed(bed_local, _pick(["8a8a90", "a07050"]), blanket)
			_lamp.position = _P(Vector3(-1.0, 2.2, -0.5))
			_kitchen(Vector3(-2.2, 0, -2.65), 2.6)
			_fridge(Vector3(-3.45, 0, -1.2))
			cupboard_local = Vector3(-3.45, 0, -1.2)
			var pc: String = _pick(PLASTIC)
			_box(Vector3(1.1, 0.05, 0.75), Vector3(-1.1, 0.72, 0.6), pc, true)   # plastic table
			for sx in [-1.0, 1.0]:
				for sz in [-1.0, 1.0]:
					_box(Vector3(0.05, 0.7, 0.05), Vector3(-1.1 + sx * 0.48, 0.35, 0.6 + sz * 0.3), pc)
			_box(Vector3(0.9, 0.01, 0.55), Vector3(-1.1, 0.75, 0.6), "f0e0e0")
			var pc2: String = _pick(PLASTIC)
			_plastic_chair(Vector3(-2.1, 0, 0.6), pc2, PI * 0.5)
			_plastic_chair(Vector3(-0.1, 0, 0.6), pc2, -PI * 0.5)
			if _rng.randf() < 0.6:
				_plastic_chair(Vector3(-1.1, 0, 1.55), _pick(PLASTIC), PI)
			_cyl(0.12, 0.1, 0.1, Vector3(-1.2, 0.8, 0.6), "d8e8f0", 10)   # rice bowl
			_wall_decor(1.9, 2.0)
			_free_spots = [Vector3(hx - 0.35, 0, 2.0), Vector3(1.4, 0, 2.2), Vector3(-hx + 0.4, 0, 2.3)]
			_clutter(_rng.randi_range(1, 3))
			_sandals()
			owner_local = Vector3(0.9, 0, 0.9)
		"pondok":
			_mx = -1.0 if _rng.randf() < 0.5 else 1.0
			_shell({"wall": _pick(["a08a68", "988060", "a89070"]), "wall_tex": "vplank", "floor": _pick(["a08058", "907050"]),
				"floor_tex": "slat", "trim": "5a4030", "posts": true, "floor_base": "3a2a1c"})
			_window(0.8, 0.8, "5a4030", "")
			bed_local = Vector3(1.8, 0, -1.25)
			bed_side = Vector3(-0.95, 0, 0.5)
			_box(Vector3(1.1, 0.1, 1.9), bed_local + Vector3(0, 0.05, 0), "c8b078", true)   # a pandan sleeping mat
			_box(Vector3(0.6, 0.1, 0.3), bed_local + Vector3(0, 0.14, -0.7), "e8dcc0")
			_box(Vector3(1.0, 0.05, 0.8), bed_local + Vector3(0, 0.13, 0.4), blanket)
			_hammock(Vector3(-2.3, 0, -1.5), Vector3(-0.3, 0, -1.2), _pick(["d08a5a", "5a8a9a", "c8a040"]))
			_fishing_gear(Vector3(-2.2, 0, 0.1))
			_sacks(Vector3(-1.9, 0, 1.2), 3)
			_lamp.position = _P(Vector3(0.0, 1.9, 0.0))
			_lamp.omni_range = 4.5
			_cyl(0.05, 0.07, 0.15, Vector3(0.25, 0.08, -1.85), "8a8a8a", 8)   # pelita
			_cyl(0.02, 0.02, 0.06, Vector3(0.25, 0.19, -1.85), "e8a040", 6, Vector3.ZERO, "_Lamp")
			cupboard_local = Vector3(0.3, 0, -1.8)
			_box(Vector3(0.7, 0.3, 0.3), Vector3(0.3, 1.5, -half.y + 0.16), "7a5a3a")   # a small shelf box
			_free_spots = [Vector3(hx - 0.35, 0, 1.5), Vector3(0.6, 0, 1.5)]
			_clutter(1)
			owner_local = Vector3(0.9, 0, 0.6)
	if kind != "pondok":
		_lamp.omni_range = maxf(half.x, half.y) * 1.5


func _mx_decor(xs: Array, y: float) -> void:
	for x in xs:
		_wall_decor(x, y)


# ------------------------------------------------------------------ queries
func to_world(local: Vector3) -> Vector3:
	return ORIGIN + local


func door_pos() -> Vector3:
	return ORIGIN + door_local


func bed_world() -> Vector3:
	return ORIGIN + _P(bed_local)


func bed_pos() -> Vector3:
	return ORIGIN + _P(bed_local + bed_side)


func cupboard_world() -> Vector3:
	return ORIGIN + _P(cupboard_local) + Vector3(0, 0, 0.5)


func cupboard_pos() -> Vector3:
	return ORIGIN + _P(cupboard_local + Vector3(0, 0, 0.9))


func cam_center() -> Vector3:
	return ORIGIN + Vector3(0, 0.3, 0.25)


func cam_dist() -> float:
	## the play camera distance that frames the whole room
	return 13.0 * maxf(half.x / 4.0, half.y / 3.0)


func is_walkable(x: float, z: float) -> bool:
	var lx := x - ORIGIN.x
	var lz := z - ORIGIN.z
	return absf(lx) < half.x - 0.25 and lz > -half.y + 0.25 and lz < half.y - 0.2


# ------------------------------------------------------------------ per visit
func setup_for(hid: String, vid: String) -> void:
	## build this house's room and place its owner (vid, or "")
	_free_room()
	house_id = hid
	kind = room_type(hid)
	half = SIZES[kind]
	_rng.seed = absi(hash(hid)) + 11
	_build_room()
	visible = true
	owner_vid = vid
	if vid != "":
		var d: Dictionary = GS.VILLAGERS[vid]
		_owner_node = ModelLib.instance(d["model"], false)
		add_child(_owner_node)
		_owner_node.position = _P(owner_local)
		_owner_anim = CharAnim.new(_owner_node)
		_owner_anim.idle_clip = "sad" if GS.villagers[vid]["status"] == "landless" else "idle"
		_owner_node.add_child(GroundFx.blob(0.5, 0.42))


func owner_node() -> Node3D:
	return _owner_node


func leave() -> void:
	_clear_owner()
	_free_room()
	visible = false
	house_id = ""


func _free_room() -> void:
	_clear_owner()
	if _room:
		_room.queue_free()
		# the colliders must not linger for the frame until queue_free
		remove_child(_room)
	_room = null
	_fan = null


func _clear_owner() -> void:
	if _owner_node:
		_owner_node.queue_free()
	_owner_node = null
	_owner_anim = null
	owner_vid = ""


func _process(delta: float) -> void:
	if not visible:
		return
	_t += delta
	var night: float = world.night_k if world else 0.0
	_lamp.light_energy = 0.25 + night * 0.7
	_pane_mat.set_shader_parameter("albedo", Color("cfe8f0").lerp(Color("2c3a5a"), night))
	if _shaft.visible and night >= 0.4:
		_shaft.visible = false
	elif not _shaft.visible and night < 0.4 and _room and kind != "":
		_shaft.visible = _has_back_window
	if _fan:
		_fan.rotation.z += delta * 14.0
	if _owner_anim and world and world.player:
		var d: Vector3 = world.player.global_position - _owner_node.global_position
		if d.length() < 5.0:
			_owner_anim.turn_towards(atan2(d.x, d.z), delta, 6.0)
			_owner_anim.look_at_point(world.player.global_position + Vector3(0, 0.9, 0))
		_owner_anim.talk_t = 0.2 if world.ui.modal != null else 0.0
		_owner_anim.update(delta, 0.0, _t)
