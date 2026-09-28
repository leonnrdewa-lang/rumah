class_name Arena
extends Node3D
## One room of the journey (or the Pancawati hub): builds the painted floor,
## surrounding scenery, invisible walls and exits, then runs its encounter:
## enemy waves -> room clear -> reward -> gates open.

signal cleared
signal exit_chosen(reward: Dictionary)

const FLOOR := preload("res://shaders/floor.gdshader")
const WATER := preload("res://shaders/water.gdshader")
const NOISE := preload("res://assets/textures/noise.png")
const VEIL := preload("res://assets/textures/veil.png")
const TEX := {
	"dandaka": preload("res://assets/textures/floor_dandaka.png"),
	"muara": preload("res://assets/textures/floor_muara.png"),
	"hub": preload("res://assets/textures/floor_hub.png"),
}
const REWARD_ICON := {
	"kepeng": "res://assets/icons/rw_kepeng.png", "tirta": "res://assets/icons/rw_tirta.png",
	"bunga": "res://assets/icons/rw_bunga.png", "palu": "res://assets/icons/rw_palu.png",
}

var biome := "dandaka"
var kind := "combat"        # combat | miniboss | boss | rest | hub
var half := Vector2(11, 8)
var corner := 3.0
var depth := 1
var reward := {}             # what clearing this room gives
var exits: Array = []       # reward dicts for the next rooms
var waves: Array = []
var wave_i := -1
var alive: Array = []
var fx_layer: Node3D
var actors: Node3D
var is_clear := false
var gates: Array = []
var _wave_delay := 0.0
var _started := false
var _rng := RandomNumberGenerator.new()
var obstacles: Array = []   # [Vector2 pos, radius] kept clear of spawns


func _ready() -> void:
	_rng.randomize()
	fx_layer = Node3D.new()
	fx_layer.name = "Fx"
	add_child(fx_layer)
	actors = Node3D.new()
	actors.name = "Actors"
	add_child(actors)


func sd(p: Vector2) -> float:
	var q := p.abs() - half + Vector2(corner, corner)
	return Vector2(max(q.x, 0.0), max(q.y, 0.0)).length() + min(max(q.x, q.y), 0.0) - corner


func build() -> void:
	_build_ground()
	_build_walls()
	_build_scenery()
	if kind != "hub":
		_build_entrance()


# --- floor / ground / water -------------------------------------------------

func _floor_mat(tex: Texture2D, hs: Vector2, c: float, tint: Color, tile: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = FLOOR
	m.set_shader_parameter("tex", tex)
	m.set_shader_parameter("noise", NOISE)
	m.set_shader_parameter("half_size", hs)
	m.set_shader_parameter("corner", c)
	m.set_shader_parameter("tint", Vector3(tint.r, tint.g, tint.b))
	m.set_shader_parameter("tile", tile)
	return m


func _plane(size: Vector2, mat: Material, y: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = size
	pm.subdivide_width = 0
	pm.subdivide_depth = 0
	mi.mesh = pm
	mi.material_override = mat
	mi.position.y = y
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


func _build_ground() -> void:
	var big := Vector2(half.x * 2 + 60, half.y * 2 + 60)
	if biome == "muara":
		var wm := ShaderMaterial.new()
		wm.shader = WATER
		wm.set_shader_parameter("noise", NOISE)
		wm.set_shader_parameter("half_size", half)
		wm.set_shader_parameter("corner", corner)
		_plane(big, wm, -0.35)
	else:
		var tint := Color(0.3, 0.36, 0.34) if biome == "dandaka" else Color(0.3, 0.27, 0.28)
		var gtex: Texture2D = TEX.dandaka
		_plane(big, _floor_mat(gtex, big * 0.5, 1.0, tint, 0.09), -0.02)
	var ftex: Texture2D = TEX.get(biome, TEX.dandaka)
	var ftint: Color = {"dandaka": Color(0.8, 0.86, 0.84), "muara": Color(0.72, 0.68, 0.64), "hub": Color(0.55, 0.5, 0.54)}.get(biome, Color.WHITE)
	_plane(half * 2.0 + Vector2(4, 4), _floor_mat(ftex, half, corner, ftint, 0.16), 0.0)


# --- walls: thin boxes around the rounded-rect edge ---------------------------

func _perimeter(offset: float, step: float) -> Array:
	var pts := []
	var h := half + Vector2(offset, offset)
	var c := corner + offset
	var straight_x := h.x - c
	var straight_y := h.y - c
	var per := 4.0 * (straight_x + straight_y) + TAU * c
	var n := int(ceil(per / step))
	for i in n:
		var t := per * i / n
		pts.append(_perim_point(t, straight_x, straight_y, c))
	return pts


func _perim_point(t: float, sx: float, sy: float, c: float) -> Vector2:
	var segs := [
		["line", Vector2(-sx, -sy - c), Vector2(sx, -sy - c)],
		["arc", Vector2(sx, -sy), -PI / 2],
		["line", Vector2(sx + c, -sy), Vector2(sx + c, sy)],
		["arc", Vector2(sx, sy), 0.0],
		["line", Vector2(sx, sy + c), Vector2(-sx, sy + c)],
		["arc", Vector2(-sx, sy), PI / 2],
		["line", Vector2(-sx - c, sy), Vector2(-sx - c, -sy)],
		["arc", Vector2(-sx, -sy), PI],
	]
	for s in segs:
		var l: float = (s[1] as Vector2).distance_to(s[2]) if s[0] == "line" else PI / 2 * c
		if t <= l:
			if s[0] == "line":
				return (s[1] as Vector2).lerp(s[2], t / max(l, 0.001))
			var a: float = s[2] + t / max(c, 0.001)
			return s[1] + Vector2(cos(a), sin(a)) * c
		t -= l
	return Vector2(-sx, -sy - c)


func _build_walls() -> void:
	var body := StaticBody3D.new()
	body.collision_layer = Actor.L_WORLD
	body.collision_mask = 0
	add_child(body)
	var pts := _perimeter(-0.4, 1.5)
	for i in pts.size():
		var a: Vector2 = pts[i]
		var b: Vector2 = pts[(i + 1) % pts.size()]
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(a.distance_to(b) + 0.4, 3.0, 0.6)
		cs.shape = box
		var mid := (a + b) * 0.5
		var dir := (b - a).normalized()
		var outward := Vector2(dir.y, -dir.x)
		mid += outward * 0.3
		cs.position = Vector3(mid.x, 1.5, mid.y)
		cs.rotation.y = -atan2(dir.y, dir.x)
		body.add_child(cs)


func add_obstacle(id: String, pos: Vector2, r: float, rot := 0.0, s := 1.0) -> Node3D:
	var m := Art.model(id)
	m.position = Vector3(pos.x, 0, pos.y)
	m.rotation.y = rot
	m.scale = Vector3.ONE * s
	add_child(m)
	var body := StaticBody3D.new()
	body.collision_layer = Actor.L_WORLD
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = r
	cyl.height = 3.0
	cs.shape = cyl
	cs.position.y = 1.5
	body.add_child(cs)
	body.position = m.position
	add_child(body)
	obstacles.append([pos, r])
	return m


func add_prop(id: String, pos: Vector2, rot := 0.0, s := 1.0, y := 0.0) -> Node3D:
	var m := Art.model(id)
	m.position = Vector3(pos.x, y, pos.y)
	m.rotation.y = rot
	m.scale = Vector3.ONE * s
	add_child(m)
	return m


func add_torch(pos: Vector2) -> void:
	add_prop("oncor", pos, _rng.randf() * TAU)
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.62, 0.3)
	l.light_energy = 2.2
	l.omni_range = 7.0
	l.omni_attenuation = 1.4
	l.position = Vector3(pos.x, 2.2, pos.y)
	l.shadow_enabled = false
	add_child(l)
	var fl := Fx.trail(Color(1.0, 0.55, 0.2), 0.22)
	fl.position = Vector3(pos.x, 1.95, pos.y)
	fl.amount = 10
	add_child(fl)
	var tw := l.create_tween().set_loops()
	tw.tween_property(l, "light_energy", 1.7, 0.13 + _rng.randf() * 0.1)
	tw.tween_property(l, "light_energy", 2.4, 0.11 + _rng.randf() * 0.1)


func add_glow(pos: Vector2, col: Color) -> void:
	add_prop("bunga_glow", pos, _rng.randf() * TAU, _rng.randf_range(0.8, 1.3))
	var l := OmniLight3D.new()
	l.light_color = col
	l.light_energy = 0.9
	l.omni_range = 3.5
	l.position = Vector3(pos.x, 0.6, pos.y)
	add_child(l)


## Scenery ring outside the playable edge; a few obstacles inside.
func _build_scenery() -> void:
	var ring_props: Array
	match biome:
		"muara":
			ring_props = [["bakau", 0.35], ["batu_besar", 0.2], ["teratai", 0.25], ["perahu", 0.08], ["batu", 0.12]]
		"hub":
			ring_props = [["beringin", 0.2], ["semak", 0.35], ["pakis", 0.25], ["candi_pilar", 0.1], ["batu", 0.1]]
		_:
			ring_props = [["beringin", 0.2], ["pohon_mati", 0.12], ["semak", 0.22], ["pakis", 0.22], ["candi_reruntuhan", 0.1], ["batu_besar", 0.08], ["candi_pilar", 0.06]]
	# dense band hugging the edge, then larger pieces further out
	for band in [[1.2, 1.6, 0.8], [3.0, 2.6, 1.0], [6.5, 4.0, 1.25]]:
		var pts := _perimeter(band[0], band[1])
		for p in pts:
			var jitter := Vector2(_rng.randf_range(-0.8, 0.8), _rng.randf_range(-0.8, 0.8))
			var pos: Vector2 = p + jitter
			if kind != "hub" and pos.y < -half.y + 0.5 and abs(pos.x) < 7.0:
				continue   # keep the gates' approach open (north)
			if pos.y > half.y - 1.0 and abs(pos.x) < 2.5:
				continue   # entrance (south)
			if pos.y > half.y + 1.0 and band[0] < 2.0:
				continue   # keep the camera side low so it doesn't hide the arena
			var id := _pick(ring_props)
			if pos.y > half.y and (id == "beringin" or id == "bakau" or id == "pohon_mati" or id == "candi_reruntuhan"):
				id = "semak" if biome != "muara" else "teratai"
			var y := -0.3 if biome == "muara" and id == "teratai" else 0.0
			add_prop(id, pos, _rng.randf() * TAU, band[2] * _rng.randf_range(0.8, 1.2), y)
	# torches and glowing flowers around the edge
	var tp := _perimeter(0.6, 9.0)
	for i in tp.size():
		var p: Vector2 = tp[i]
		if p.y > half.y - 0.5:
			continue
		if i % 2 == 0:
			add_torch(p)
		elif biome != "hub":
			add_glow(p, Color("e0508f") if _rng.randf() < 0.5 else Color("5fe0c8"))
	if kind == "combat":
		var n := _rng.randi_range(1, 3)
		var inside := ["candi_pilar", "arca", "batu_besar"] if biome != "muara" else ["batu_besar", "candi_pilar"]
		for i in n:
			for attempt in 12:
				var pos := Vector2(_rng.randf_range(-half.x + 3, half.x - 3), _rng.randf_range(-half.y + 3, half.y - 3))
				if pos.length() < 3.0 or abs(pos.x) < 2.0:
					continue
				var ok := true
				for o in obstacles:
					if (o[0] as Vector2).distance_to(pos) < 4.0:
						ok = false
				if ok:
					add_obstacle(inside[_rng.randi() % inside.size()], pos, 0.8, _rng.randf() * TAU)
					break


func _pick(table: Array) -> String:
	var total := 0.0
	for t in table:
		total += t[1]
	var r := _rng.randf() * total
	for t in table:
		r -= t[1]
		if r <= 0.0:
			return t[0]
	return table[0][0]


func _build_entrance() -> void:
	add_prop("gapura", Vector2(0, half.y + 1.4), PI, 0.9)


func player_start() -> Vector3:
	if kind == "hub":
		return Vector3(0, 0, 2.0)
	return Vector3(0, 0, half.y - 1.6)


# --- exits ---------------------------------------------------------------------

func build_exits() -> void:
	var n := exits.size()
	var xs := [0.0] if n == 1 else [-4.5, 4.5] if n == 2 else [-6.0, 0.0, 6.0]
	for i in n:
		var rw: Dictionary = exits[i]
		var pos := Vector2(xs[i], -half.y - 0.4)
		add_prop("gapura", pos, 0.0, 1.0)
		var g := Interactable.make("", _on_gate)
		g.position = Vector3(pos.x, 0, pos.y + 0.9)
		g.set_meta("reward", rw)
		g.active = false
		add_child(g)
		# barrier (glowing veil in the gate opening)
		var veil := MeshInstance3D.new()
		var q := QuadMesh.new()
		q.size = Vector2(2.6, 3.4)
		veil.mesh = q
		var vm := Art.fx_mat(Color(0.6, 0.2, 0.9), 0.35)
		vm.set_shader_parameter("use_mask", 1.0)
		vm.set_shader_parameter("mask", VEIL)
		veil.material_override = vm
		veil.position = Vector3(pos.x, 1.7, pos.y)
		add_child(veil)
		g.set_meta("veil", veil)
		# reward icon floating above the gate
		var icon := Sprite3D.new()
		icon.texture = load(_reward_icon(rw))
		icon.pixel_size = 0.009
		icon.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		icon.position = Vector3(pos.x, 4.9, pos.y)
		icon.modulate = Color(1, 1, 1, 0.45)
		icon.no_depth_test = true
		add_child(icon)
		g.set_meta("icon", icon)
		var tw := icon.create_tween().set_loops()
		tw.tween_property(icon, "position:y", 5.1, 0.9).set_trans(Tween.TRANS_SINE)
		tw.tween_property(icon, "position:y", 4.9, 0.9).set_trans(Tween.TRANS_SINE)
		g.set_prompt("Masuk: " + reward_label(rw))
		gates.append(g)


func _reward_icon(rw: Dictionary) -> String:
	match rw.get("type", ""):
		"boon":
			return "res://assets/icons/god_%s.png" % rw.god
		"boss", "miniboss":
			return "res://assets/icons/rw_bunga.png" if rw.type == "miniboss" else "res://assets/icons/app_icon.png"
	return REWARD_ICON.get(rw.get("type", "kepeng"), REWARD_ICON.kepeng)


static func reward_label(rw: Dictionary) -> String:
	match rw.get("type", ""):
		"boon":
			return "Anugerah " + G.GOD_NAMES[rw.god]
		"kepeng":
			return "Kepeng"
		"tirta":
			return "Tirta Amerta (pulih)"
		"bunga":
			return "Kembang Wijayakusuma"
		"palu":
			return "Pusaka Palu (naikkan anugerah)"
		"miniboss":
			return "Sang Kijang Kencana"
		"boss":
			return "Muara Kalimas — Sura & Baya"
		"rest":
			return "Pasar Sang Hyang & Sendang"
		"muara":
			return "Muara Kalimas"
	return "?"


func open_gates() -> void:
	for g in gates:
		g.active = true
		var veil: MeshInstance3D = g.get_meta("veil")
		var m := veil.material_override as ShaderMaterial
		m.set_shader_parameter("color", Color(1.0, 0.8, 0.4))
		m.set_shader_parameter("intensity", 0.6)
		var icon: Sprite3D = g.get_meta("icon")
		icon.modulate = Color(1, 1, 1, 1)
	if not gates.is_empty():
		Au.sfx("sfx_door_open", -3.0)


func _on_gate(g: Interactable) -> void:
	for o in gates:
		o.active = false
	exit_chosen.emit(g.get_meta("reward"))


# --- encounter -------------------------------------------------------------------

func start() -> void:
	_started = true
	if kind == "combat" or kind == "miniboss" or kind == "boss":
		_wave_delay = 0.9
	else:
		_on_clear()


func _physics_process(delta: float) -> void:
	if not _started or is_clear:
		return
	alive = alive.filter(func(a): return is_instance_valid(a) and not a.dead)
	if kind == "combat":
		if alive.size() <= (1 if wave_i < waves.size() - 1 else 0):
			if wave_i + 1 < waves.size():
				_wave_delay -= delta
				if _wave_delay <= 0.0:
					_spawn_wave()
			elif alive.is_empty():
				_on_clear()
	elif kind == "miniboss" or kind == "boss":
		if wave_i < 0:
			_wave_delay -= delta
			if _wave_delay <= 0.0:
				_spawn_boss()
		elif alive.is_empty():
			_on_clear()


func _spawn_wave() -> void:
	wave_i += 1
	_wave_delay = 1.0
	var list: Array = waves[wave_i]
	var pl: Vector3 = G.main.player.global_position
	for i in list.size():
		var pos := _spawn_point(pl)
		var kind_i: String = list[i]
		Fx.ring(pos, 1.0, Color(0.7, 0.2, 0.9), 0.6)
		var e := Enemy.new()
		e.setup(kind_i, depth)
		var t := get_tree().create_timer(0.55 + i * 0.12)
		t.timeout.connect(func():
			if is_instance_valid(self) and not is_clear:
				G.main.spawn_actor(e, pos)
				alive.append(e)
			else:
				e.free())


func _spawn_point(avoid: Vector3) -> Vector3:
	for attempt in 30:
		var p := Vector2(_rng.randf_range(-half.x + 1.5, half.x - 1.5), _rng.randf_range(-half.y + 1.5, half.y - 1.5))
		if sd(p) > -1.2:
			continue
		if Vector2(avoid.x, avoid.z).distance_to(p) < 5.5:
			continue
		var ok := true
		for o in obstacles:
			if (o[0] as Vector2).distance_to(p) < float(o[1]) + 1.2:
				ok = false
		if ok:
			return Vector3(p.x, 0, p.y)
	return Vector3(0, 0, -half.y * 0.5)


func _spawn_boss() -> void:
	wave_i = 0
	if kind == "miniboss":
		var b := Boss.new()
		b.setup_boss("kijang")
		G.main.spawn_actor(b, Vector3(0, 0, -half.y * 0.45))
		alive.append(b)
		G.main.ui.set_bosses([b])
	else:
		var s := Boss.new()
		s.setup_boss("sura")
		var y := Boss.new()
		y.setup_boss("baya")
		s.rival = y
		y.rival = s
		G.main.spawn_actor(s, Vector3(-4.5, 0, -half.y * 0.45))
		G.main.spawn_actor(y, Vector3(4.5, 0, -half.y * 0.45))
		alive.append(s)
		alive.append(y)
		G.main.ui.set_bosses([s, y])


func _on_clear() -> void:
	if is_clear:
		return
	is_clear = true
	if kind != "rest" and kind != "hub":
		Au.sfx("sfx_room_clear", -2.0)
		G.main.ui.room_clear_banner()
	cleared.emit()
	G.main.on_room_cleared(self)
