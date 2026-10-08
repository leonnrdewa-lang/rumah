extends Node
## Village life: the hub for the social features, created by world.gd. It owns
##   * relations.gd   friendship (hearts) with every named villager, gifts, small
##                    requests, secret tips, the Warga panel, reports to the Satgas
##   * journalist.gd  the investigative journalist and the Koran Sukamakmur headlines
##   * protests.gd    demonstrations in front of the Kantor and the LSM lingkungan
##   * festivals.gd   the village calendar (Tujuhbelasan, pasar malam, kondangan,
##                    pengajian), sponsoring and the lomba minigames
##   * decor.gd       house upgrades (rumah mungil -> gedongan) and furniture on a grid
##   * endings.gd     the four endings, the Buku Prestasi badges and the result card
## All state lives in GS.social (one block in the save; missing keys get defaults, so
## older saves load). Shared files only call in through a few hooks:
## deals.gd (_soc events, menu/talk choices, morning events), interior.gd (the player's
## room), ui.gd (endings, pause buttons) and gs.gd (day_rolled).

const REL := preload("res://scripts/world/relations.gd")
const JOUR := preload("res://scripts/world/journalist.gd")
const PROT := preload("res://scripts/world/protests.gd")
const FEST := preload("res://scripts/world/festivals.gd")
const DECOR := preload("res://scripts/world/decor.gd")
const ENDS := preload("res://scripts/world/endings.gd")

var world: Node
var ui: Node
var deals: Node
var rel: Node
var jour: Node
var prot: Node
var fest: Node
var decor: Node
var endings: Node
var rng := RandomNumberGenerator.new()
var _state_ref = null          # the GS.social dictionary the visuals were built for
var _hearts_modal: Object = null
var _name_vid := {}
var _tick := 0.0
var _mats := {}


func _ready() -> void:
	rng.randomize()
	ui = world.ui
	deals = world.deals
	for pair in [["rel", REL], ["jour", JOUR], ["prot", PROT], ["fest", FEST], ["decor", DECOR], ["endings", ENDS]]:
		var n: Node = pair[1].new()
		n.name = String(pair[0]).capitalize()
		n.set("hub", self)
		add_child(n)
		set(pair[0], n)
	for vid in GS.VILLAGERS:
		_name_vid[GS.vname(vid)] = vid
	GS.day_rolled.connect(_on_day_rolled)
	# deferred: after world.gd has reset the villagers for the new day
	GS.day_started.connect(func(_r): refresh_visuals(), CONNECT_DEFERRED)


# ------------------------------------------------------------------ state helpers
func st(key: String, defaults: Dictionary) -> Dictionary:
	## GS.social[key] with every default key present (old saves, new games)
	if not GS.social.has(key) or typeof(GS.social[key]) != TYPE_DICTIONARY:
		GS.social[key] = {}
	var d: Dictionary = GS.social[key]
	for k in defaults:
		if not d.has(k):
			var v = defaults[k]
			d[k] = v.duplicate(true) if (v is Dictionary or v is Array) else v
	return d


func stat(key: String) -> int:
	return int(st("st", {}).get(key, 0))


func add_stat(key: String, n: int = 1) -> void:
	var s := st("st", {})
	s[key] = int(s.get(key, 0)) + n


static func iv(d: Dictionary, k: String, def := 0) -> int:
	return int(d.get(k, def))


func playing() -> bool:
	return world.state == "play" and GS.game_active


# ------------------------------------------------------------------ day / frame
func _on_day_rolled(report: Array) -> void:
	## runs inside GS.start_new_day, before the autosave and the morning panel
	rel.day_roll(report)
	jour.day_roll(report)
	prot.day_roll(report)
	fest.day_roll(report)
	endings.day_roll(report)


func refresh_visuals() -> void:
	## (re)build everything in the world that comes from GS.social (new day, load)
	_state_ref = GS.social
	jour.refresh()
	prot.refresh()
	fest.refresh()
	decor.refresh()


func _process(delta: float) -> void:
	if not is_same(_state_ref, GS.social):
		# new game, loaded save or imported code: rebuild the village-life visuals
		refresh_visuals()
	_attach_hearts()
	_tick += delta
	if _tick >= 1.0:
		_tick = 0.0
		if playing():
			endings.check_badges()


func _unhandled_input(event: InputEvent) -> void:
	if world.state != "play" or ui.is_blocking():
		return
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_H:
				rel.show_panel()
				get_viewport().set_input_as_handled()
			KEY_J:
				endings.show_book()
				get_viewport().set_input_as_handled()


func _attach_hearts() -> void:
	## every dialog line spoken by a named villager shows their hearts next to the name
	var m = ui.modal
	if m == null or m == _hearts_modal or not is_instance_valid(m):
		return
	_hearts_modal = m
	var sp = m.get("speaker")
	var nl = m.get("name_label")
	if sp == null or nl == null or not _name_vid.has(str(sp)):
		return
	rel.attach_hearts(nl as Label, _name_vid[str(sp)])


# ------------------------------------------------------------------ hooks from deals.gd / ui.gd
func on_event(ev: String, vid: String) -> void:
	rel.on_event(ev, vid)
	endings.check_badges()


func talk_choices(vid: String, choices: Array) -> void:
	rel.talk_choices(vid, choices)


func land_choices(vid: String, choices: Array) -> void:
	rel.land_choices(vid, choices)


func kantor_items(items: Array) -> void:
	prot.kantor_items(items)
	endings.kantor_items(items)


func toko_items(items: Array) -> void:
	decor.toko_items(items)
	rel.toko_items(items)


func calo_items(items: Array) -> void:
	endings.calo_items(items)


func morning_event(ev: String) -> bool:
	## the morning events this hub runs (deals.run_morning_events); true = handled
	match ev:
		"wartawan", "jurnalis":
			jour.arrive()
		"demo":
			prot.start_protest()
		"lsm":
			prot.lsm_arrive()
		"koran":
			jour.publish_pending()
		"festival":
			fest.morning_announce()
		_:
			return false
	return true


func next_event() -> void:
	## continue with the next morning event (after one of ours closes)
	deals.run_morning_events()


# ------------------------------------------------------------------ world helpers
func spawn_npc(model: String, label: String, pos: Vector3, radius: float, look: String,
		prompt: Callable = Callable(), act: Callable = Callable()) -> Npc:
	pos.y = world.height_at(pos.x, pos.z)
	var n: Npc = world._extra(model, label, pos, radius, false, look)
	if act.is_valid():
		var it := {"node": n, "r": 1.9, "npc": true, "prompt": prompt, "act": act}
		n.set_meta("social_it", it)
		world.interactables.append(it)
	return n


func despawn(n: Node) -> void:
	if n == null or not is_instance_valid(n):
		return
	if n.has_meta("social_it"):
		world.interactables.erase(n.get_meta("social_it"))
	n.queue_free()


func add_spot(pos: Vector3, r: float, prompt: Callable, act: Callable, ok := Callable()) -> Dictionary:
	var it := {"pos": pos, "r": r, "prompt": prompt, "act": act}
	if ok.is_valid():
		it["ok"] = ok
	world.interactables.append(it)
	return it


func remove_spot(it: Dictionary) -> void:
	if not it.is_empty():
		world.interactables.erase(it)


func mat(col: String, outline := true) -> Material:
	var key := col + ("o" if outline else "")
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.resource_name = "M_Social"
		m.albedo_color = Color(col)
		_mats[key] = ModelLib.convert_material(m, false, 0.0, outline)
	return _mats[key]


func box(parent: Node3D, size: Vector3, pos: Vector3, col: String, rot := Vector3.ZERO, outline := true) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat(col, outline)
	mi.position = pos
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func cyl(parent: Node3D, r: float, h: float, pos: Vector3, col: String, sides := 10, rot := Vector3.ZERO, r_top := -1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r if r_top < 0.0 else r_top
	cm.bottom_radius = r
	cm.height = h
	cm.radial_segments = sides
	cm.rings = 1
	mi.mesh = cm
	mi.material_override = mat(col)
	mi.position = pos
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func label3d(parent: Node3D, text: String, pos: Vector3, size := 40, col := Color("b8321f"), billboard := false) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font = ModelLib.label_font()
	l.font_size = size
	l.outline_size = 0 if not billboard else 8
	l.outline_modulate = Color("fdf3dc")
	l.modulate = col
	l.pixel_size = 0.006
	l.position = pos
	if billboard:
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
	parent.add_child(l)
	return l


func protest_sign(text: String, board_col := "fdf3dc", ink := Color("b8321f")) -> Node3D:
	## a hand-held cardboard sign on a stick (child of a character, held over the head)
	var s := Node3D.new()
	s.name = "ProtestSign"
	cyl(s, 0.025, 1.3, Vector3(0, 0.65, 0), "8a6a44", 6)
	box(s, Vector3(0.9, 0.55, 0.04), Vector3(0, 1.45, 0), board_col)
	var l := label3d(s, text, Vector3(0, 1.45, 0.03), 34, ink)
	l.pixel_size = 0.0045
	l.width = 190.0
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var back := label3d(s, text, Vector3(0, 1.45, -0.03), 34, ink)
	back.pixel_size = 0.0045
	back.rotation.y = PI
	back.width = 190.0
	back.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return s


func free_spot_near(center: Vector3, need := 4.0, max_r := 30.0) -> Vector3:
	## a walkable, free spot with `need` m of room around it, searched outwards
	var r := 0.0
	while r <= max_r:
		var n := maxi(1, int(r * 1.2))
		for k in n:
			var a := TAU * k / n + r
			var x := center.x + cos(a) * r
			var z := center.z + sin(a) * r
			if _room_at(x, z, need):
				return Vector3(x, world.height_at(x, z), z)
		r += 2.0
	return Vector3(center.x, world.height_at(center.x, center.z), center.z)


func _room_at(x: float, z: float, need: float) -> bool:
	for k in 9:
		var a := TAU * k / 8.0
		var rr := need if k < 8 else 0.0
		var px := x + cos(a) * rr
		var pz := z + sin(a) * rr
		if not world.is_walkable(px, pz) or not world.is_free(px, pz, 0.6):
			return false
	return true


func near_player(pos: Vector3, d: float) -> bool:
	return world.player and world.inside == "" and world.player.global_position.distance_to(pos) < d
