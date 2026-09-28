extends Node3D
## The inside of a house: one small cel-shaded room (kasur, table and stools, lemari,
## rug, window with a shaft of light, lamp) built from simple meshes, far off the island
## at ORIGIN. Every house shares it; each entry re-colours walls, floor, rug and blanket
## (a few variants picked from the house id), and in a villager's house the owner may
## be at home. The room has no ceiling and a low front wall (cut-away view) so the play
## camera looks in from the usual angle.

const ORIGIN := Vector3(400, 0, 400)
## inner half size of the room (x, z) in m
const HALF := Vector2(4.0, 3.0)
const WALL_H := 2.7
const DOOR_LOCAL := Vector3(0, 0, 2.35)       # where the player appears / leaves
const BED_LOCAL := Vector3(2.55, 0, -1.75)
const CUPBOARD_LOCAL := Vector3(-3.05, 0, -2.45)
const OWNER_LOCAL := Vector3(-1.2, 0, 1.25)

const WALLS := ["e3d3b0", "d3dcc2", "e0cbbd", "cad8d6", "e6dab8", "ddd3c2"]
const FLOORS := ["86684f", "7c604a", "8e7058", "735a46"]
const RUGS := ["a8584a", "4f767c", "b8904e", "6a8050", "5c7a8e"]
const BLANKETS := ["6a8eaa", "b8745e", "7a9258", "c8a458", "86789e"]

var world: Node
var _mats := {}
var _lamp: OmniLight3D
var _shaft: MeshInstance3D
var _owner_node: Node3D
var _owner_anim: CharAnim
var _t := 0.0
var house_id := ""
var owner_vid := ""   # villager at home ("" = nobody)


func _ready() -> void:
	position = ORIGIN
	_build()
	visible = false


# ------------------------------------------------------------------ building
func _mat(key: String, col: String) -> ShaderMaterial:
	## one toon material per part (re-coloured per house through its albedo)
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.resource_name = "M_Interior_" + key
		m.albedo_color = Color(col)
		_mats[key] = ModelLib.convert_material(m, false).duplicate()
		var outline: Material = (_mats[key] as ShaderMaterial).next_pass
		if outline:
			_mats[key].next_pass = outline
	return _mats[key]


func _box(size: Vector3, pos: Vector3, key: String, col: String, collide := false, rot_y := 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = _mat(key, col)
	mi.position = pos
	mi.rotation.y = rot_y
	add_child(mi)
	if collide:
		var b := StaticBody3D.new()
		b.collision_layer = 1
		b.collision_mask = 0
		var cs := CollisionShape3D.new()
		var sh := BoxShape3D.new()
		sh.size = Vector3(size.x, maxf(size.y, 1.2), size.z)
		cs.shape = sh
		b.add_child(cs)
		b.position = pos + Vector3(0, maxf(size.y, 1.2) * 0.5 - size.y * 0.5, 0)
		b.rotation.y = rot_y
		add_child(b)
	return mi


func _cyl(r_top: float, r_bot: float, h: float, pos: Vector3, key: String, col: String, sides := 12) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r_top
	cm.bottom_radius = r_bot
	cm.height = h
	cm.radial_segments = sides
	cm.rings = 1
	mi.mesh = cm
	mi.material_override = _mat(key, col)
	mi.position = pos
	add_child(mi)
	return mi


func _build() -> void:
	var hx := HALF.x
	var hz := HALF.y
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
	# floor: planks (alternating tones) on a base
	_box(Vector3(hx * 2 + 0.6, 0.3, hz * 2 + 0.6), Vector3(0, -0.15, 0), "floor", FLOORS[0])
	for i in 8:
		var z := -hz + (i + 0.5) * (hz * 2 / 8.0)
		var p := _box(Vector3(hx * 2, 0.02, hz * 2 / 8.0 - 0.04), Vector3(0, 0.01, z), "plank%d" % (i % 2), FLOORS[0])
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# walls: back, left, right full height; front low with a door gap
	var t := 0.2
	_box(Vector3(hx * 2 + t * 2, WALL_H, t), Vector3(0, WALL_H * 0.5, -hz - t * 0.5), "wall", WALLS[0], true)
	_box(Vector3(t, WALL_H, hz * 2), Vector3(-hx - t * 0.5, WALL_H * 0.5, 0), "wall", WALLS[0], true)
	_box(Vector3(t, WALL_H, hz * 2), Vector3(hx + t * 0.5, WALL_H * 0.5, 0), "wall", WALLS[0], true)
	var seg := hx - 0.75
	for s in [-1.0, 1.0]:
		_box(Vector3(seg + t, 0.55, t), Vector3(s * (0.75 + seg * 0.5 + t * 0.5), 0.275, hz + t * 0.5), "wall", WALLS[0], true)
		_box(Vector3(seg + t, 0.07, t + 0.06), Vector3(s * (0.75 + seg * 0.5 + t * 0.5), 0.58, hz + t * 0.5), "trim", "6e5040")
		# door posts
		_box(Vector3(0.14, 0.9, 0.26), Vector3(s * 0.8, 0.45, hz + t * 0.5), "trim", "6e5040", true)
	# skirting + top trim on the walls
	_box(Vector3(hx * 2, 0.14, 0.05), Vector3(0, 0.07, -hz + 0.02), "trim", "6e5040")
	_box(Vector3(hx * 2 + t * 2, 0.1, t + 0.06), Vector3(0, WALL_H + 0.05, -hz - t * 0.5), "trim", "6e5040")
	_box(Vector3(t + 0.06, 0.1, hz * 2), Vector3(-hx - t * 0.5, WALL_H + 0.05, 0), "trim", "6e5040")
	_box(Vector3(t + 0.06, 0.1, hz * 2), Vector3(hx + t * 0.5, WALL_H + 0.05, 0), "trim", "6e5040")
	# door mat
	_box(Vector3(1.2, 0.03, 0.7), Vector3(0, 0.02, hz - 0.45), "mat", "b89a5a")
	# rug (border + field)
	_box(Vector3(3.2, 0.025, 2.2), Vector3(0.3, 0.015, 0.45), "rug_edge", "f0dcb0")
	_box(Vector3(2.9, 0.03, 1.9), Vector3(0.3, 0.02, 0.45), "rug", RUGS[0])
	_box(Vector3(2.2, 0.034, 0.12), Vector3(0.3, 0.022, 0.45), "rug_edge", "f0dcb0")
	# window on the back wall: frame, sky glass, sill, two curtains, a shaft of light
	var wx := -0.4
	_box(Vector3(1.5, 1.1, 0.06), Vector3(wx, 1.55, -hz + 0.01), "pane", "cfe8f0")
	_box(Vector3(1.66, 0.1, 0.12), Vector3(wx, 2.13, -hz + 0.05), "trim", "6e5040")
	_box(Vector3(1.66, 0.1, 0.2), Vector3(wx, 0.97, -hz + 0.08), "trim", "6e5040")
	_box(Vector3(0.08, 1.1, 0.1), Vector3(wx, 1.55, -hz + 0.05), "trim", "6e5040")
	_box(Vector3(1.5, 0.06, 0.08), Vector3(wx, 1.55, -hz + 0.05), "trim", "6e5040")
	for s in [-1.0, 1.0]:
		_box(Vector3(0.36, 1.3, 0.05), Vector3(wx + s * 0.92, 1.5, -hz + 0.1), "curtain", "d8b070")
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
	_shaft.position = Vector3(wx + 0.25, 0.8, -hz + 0.95)
	_shaft.rotation = Vector3(deg_to_rad(-62), 0, 0)
	add_child(_shaft)
	# kasur: frame, legs, headboard, mattress, pillow, blanket
	var b := BED_LOCAL
	_box(Vector3(1.6, 0.34, 2.3), b + Vector3(0, 0.25, 0), "bedwood", "7a5a44", true)
	_box(Vector3(1.6, 1.0, 0.12), b + Vector3(0, 0.5, -1.15), "bedwood", "7a5a44")
	_box(Vector3(1.7, 0.08, 0.16), b + Vector3(0, 1.02, -1.15), "trim", "6e5040")
	_box(Vector3(1.5, 0.18, 2.16), b + Vector3(0, 0.5, 0.02), "mattress", "f6efe0")
	_box(Vector3(1.05, 0.16, 0.44), b + Vector3(0, 0.66, -0.78), "pillow", "fffaf0")
	_box(Vector3(1.56, 0.1, 1.35), b + Vector3(0, 0.62, 0.42), "blanket", BLANKETS[0])
	_box(Vector3(1.58, 0.14, 0.1), b + Vector3(0, 0.6, -0.26), "blanket_fold", "fffaf0")
	# bedside table + lamp
	var nt := b + Vector3(-1.2, 0, -0.95)
	_box(Vector3(0.55, 0.55, 0.5), nt + Vector3(0, 0.275, 0), "wood", "8a6a4e", true)
	_cyl(0.08, 0.1, 0.22, nt + Vector3(0, 0.66, 0), "lampbase", "6a4a2a")
	_cyl(0.13, 0.2, 0.2, nt + Vector3(0, 0.86, 0), "shade", "f4e2b8")
	_lamp = OmniLight3D.new()
	_lamp.light_color = Color(1.0, 0.8, 0.5)
	_lamp.omni_range = 5.5
	_lamp.shadow_enabled = false
	_lamp.position = nt + Vector3(0, 1.0, 0.2)
	add_child(_lamp)
	# lemari: body, two doors, knobs, a basket on top
	var c := CUPBOARD_LOCAL
	_box(Vector3(1.4, 2.0, 0.6), c + Vector3(0, 1.0, 0), "cupboard", "7a5a44", true)
	for s in [-1.0, 1.0]:
		_box(Vector3(0.62, 1.7, 0.04), c + Vector3(s * 0.34, 1.05, 0.31), "cupboard_door", "8c6a50")
		_cyl(0.035, 0.035, 0.05, c + Vector3(s * 0.08, 1.05, 0.34), "knob", "e0b04a", 8).rotation.x = PI * 0.5
	_box(Vector3(1.5, 0.08, 0.66), c + Vector3(0, 2.04, 0), "trim", "6e5040")
	_cyl(0.22, 0.18, 0.22, c + Vector3(0.3, 2.19, 0), "basket", "c9a95e", 10)
	# table with two stools, a teapot and cups
	var tb := Vector3(-1.3, 0, 0.1)
	_box(Vector3(1.4, 0.08, 0.9), tb + Vector3(0, 0.74, 0), "table", "8e6c50", true)
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			_box(Vector3(0.08, 0.7, 0.08), tb + Vector3(sx * 0.6, 0.35, sz * 0.36), "wood", "8a6a4e")
	for sx in [-1.0, 1.0]:
		_cyl(0.2, 0.18, 0.08, tb + Vector3(sx * 1.05, 0.46, 0.05), "stool", "947050")
		_cyl(0.04, 0.05, 0.42, tb + Vector3(sx * 1.05, 0.21, 0.05), "wood", "8a6a4e", 6)
	_cyl(0.1, 0.13, 0.18, tb + Vector3(0.1, 0.87, -0.05), "teapot", "4f8a8a")
	_cyl(0.04, 0.04, 0.05, tb + Vector3(0.1, 0.98, -0.05), "teapot", "4f8a8a", 8)
	for i in 2:
		_cyl(0.05, 0.04, 0.09, tb + Vector3(-0.3 + i * 0.7, 0.82, 0.18), "cup", "fffaf0", 8)
	# a framed picture on the left wall and a potted plant in the corner
	_box(Vector3(0.05, 0.7, 0.9), Vector3(-hx + 0.03, 1.7, -0.2), "trim", "6e5040")
	_box(Vector3(0.06, 0.56, 0.76), Vector3(-hx + 0.04, 1.7, -0.2), "picture", "8fbf7a")
	_box(Vector3(0.07, 0.2, 0.3), Vector3(-hx + 0.05, 1.62, -0.25), "picture_sun", "e9b949")
	_cyl(0.2, 0.15, 0.36, Vector3(hx - 0.35, 0.18, 1.9), "pot", "b8653a")
	for i in 5:
		var leaf := _box(Vector3(0.12, 0.55, 0.04), Vector3(hx - 0.35, 0.6, 1.9), "potgreen", "5c8a3a")
		leaf.rotation = Vector3(deg_to_rad(18), i * TAU / 5.0, 0)
	# a wall clock over the table
	_cyl(0.2, 0.2, 0.05, Vector3(-1.3, 2.05, -hz + 0.04), "clock", "fffaf0", 16).rotation.x = PI * 0.5
	_cyl(0.23, 0.23, 0.04, Vector3(-1.3, 2.05, -hz + 0.02), "trim", "6e5040", 16).rotation.x = PI * 0.5


# ------------------------------------------------------------------ queries
func to_world(local: Vector3) -> Vector3:
	return ORIGIN + local


func door_pos() -> Vector3:
	return ORIGIN + DOOR_LOCAL


func bed_pos() -> Vector3:
	return ORIGIN + BED_LOCAL + Vector3(-1.05, 0, 0.55)


func cupboard_pos() -> Vector3:
	return ORIGIN + CUPBOARD_LOCAL + Vector3(0, 0, 0.9)


func is_walkable(x: float, z: float) -> bool:
	var lx := x - ORIGIN.x
	var lz := z - ORIGIN.z
	return absf(lx) < HALF.x - 0.25 and lz > -HALF.y + 0.25 and lz < HALF.y - 0.2


# ------------------------------------------------------------------ per visit
func setup_for(hid: String, vid: String) -> void:
	## re-colour the room for this house and place its owner (vid, or "")
	house_id = hid
	var h := absi(hash(hid))
	var own := hid == "rumah_juragan"
	_set_col("wall", "e8dcc0" if own else WALLS[h % WALLS.size()])
	var fl: String = FLOORS[(h / 7) % FLOORS.size()]
	_set_col("floor", fl)
	_set_col("plank0", fl)
	_set_col("plank1", Color(fl).darkened(0.1).to_html(false))
	_set_col("rug", "a8584a" if own else RUGS[(h / 13) % RUGS.size()])
	_set_col("blanket", "5a7fa0" if own else BLANKETS[(h / 29) % BLANKETS.size()])
	_set_col("curtain", "d8b070" if own else ["d8b070", "c89078", "98b09a", "b0a0b8"][(h / 5) % 4])
	visible = true
	_clear_owner()
	owner_vid = vid
	if vid != "":
		var d: Dictionary = GS.VILLAGERS[vid]
		_owner_node = ModelLib.instance(d["model"], false)
		add_child(_owner_node)
		_owner_node.position = OWNER_LOCAL
		_owner_anim = CharAnim.new(_owner_node)
		_owner_anim.idle_clip = "sad" if GS.villagers[vid]["status"] == "landless" else "idle"
		_owner_node.add_child(GroundFx.blob(0.5, 0.42))


func owner_node() -> Node3D:
	return _owner_node


func leave() -> void:
	_clear_owner()
	visible = false
	house_id = ""


func _clear_owner() -> void:
	if _owner_node:
		_owner_node.queue_free()
	_owner_node = null
	_owner_anim = null
	owner_vid = ""


func _set_col(key: String, col: String) -> void:
	if _mats.has(key):
		(_mats[key] as ShaderMaterial).set_shader_parameter("albedo", Color(col))


func _process(delta: float) -> void:
	if not visible:
		return
	_t += delta
	var night: float = world.night_k if world else 0.0
	_lamp.light_energy = 0.25 + night * 0.7
	_set_col("pane", Color("cfe8f0").lerp(Color("2c3a5a"), night).to_html(false))
	_shaft.visible = night < 0.4
	if _owner_anim and world and world.player:
		var d: Vector3 = world.player.global_position - _owner_node.global_position
		if d.length() < 5.0:
			_owner_anim.turn_towards(atan2(d.x, d.z), delta, 6.0)
			_owner_anim.look_at_point(world.player.global_position + Vector3(0, 0.9, 0))
		_owner_anim.talk_t = 0.2 if world.ui.modal != null else 0.0
		_owner_anim.update(delta, 0.0, _t)
