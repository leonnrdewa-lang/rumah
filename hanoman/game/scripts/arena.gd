class_name Arena
extends Node3D
## One room of the journey (or the Pancawati hub). A combat stage is three
## chambers (each with its own theme: sunken pond, pillar ring, ruins, grove,
## shrine...) joined by corridors sealed with a spirit veil. Clearing a chamber's
## waves opens the way on; clearing the last one gives the reward and opens the
## exit gates. Boss, mini-boss and rest rooms are one large chamber. The playable
## shape is a smooth union of rounded boxes minus pits, shared with the floor and
## water shaders (room_sdf.gdshaderinc).

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
## Painted Higgsfield floors a biome's chambers draw from.
const PAINTS := {
	"dandaka": ["dandaka", "dandaka2", "bambu", "candi"],
	"muara": ["muara", "rawa", "pasir"],
}
const THEMES := {
	"dandaka": ["pond", "pillars", "ruins", "grove", "shrine", "open"],
	"muara": ["pond", "piers", "rocks", "mangrove", "open"],
}

var biome := "dandaka"
var kind := "combat"        # combat | miniboss | boss | rest | hub
var half := Vector2(11, 8)   # half size of the bounding box (single rooms: the room)
var corner := 3.0
var depth := 1
var reward := {}             # what clearing this room gives
var exits: Array = []       # reward dicts for the next rooms
var waves: Array = []       # combat: per chamber, a list of waves
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

var boxes: Array = []       # {c, h, r, paint, open, chamber (-1 = corridor), theme}
var holes: Array = []       # {c, h, r}
var chambers: Array = []    # {box, corridor, waves, wave_i, state}
var cur := 0
var bounds := Rect2()
var _pending := 0            # enemies summoned but not yet in the arena
var _hint: Node3D


func _ready() -> void:
	_rng.randomize()
	fx_layer = Node3D.new()
	fx_layer.name = "Fx"
	add_child(fx_layer)
	actors = Node3D.new()
	actors.name = "Actors"
	add_child(actors)


# --- shape ------------------------------------------------------------------------

static func sd_box(p: Vector2, c: Vector2, h: Vector2, r: float) -> float:
	var q := (p - c).abs() - h + Vector2(r, r)
	return Vector2(maxf(q.x, 0.0), maxf(q.y, 0.0)).length() + minf(maxf(q.x, q.y), 0.0) - r


static func _smin(a: float, b: float, k: float) -> float:
	var h := clampf(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
	return lerpf(b, a, h) - k * h * (1.0 - h)


## Signed distance to the walkable edge (negative inside). Sealed chambers and
## corridors are not walkable yet.
func sd(p: Vector2) -> float:
	return _sd(p, true)


## The whole map, sealed parts included (scenery, floor).
func sd_all(p: Vector2) -> float:
	return _sd(p, false)


func _sd(p: Vector2, only_open: bool) -> float:
	if boxes.is_empty():
		return sd_box(p, Vector2.ZERO, half, corner)
	var d := 1e5
	for b in boxes:
		if only_open and not b.open:
			continue
		d = _smin(d, sd_box(p, b.c, b.h, b.r), 1.5)
	for hl in holes:
		d = maxf(d, -sd_box(p, hl.c, hl.h, hl.r))
	return d


## Keep a body of radius `margin` on the walkable floor (replaces wall colliders).
func push_inside(p: Vector3, margin: float) -> Vector3:
	var q := Vector2(p.x, p.z)
	for i in 3:
		var d := sd(q)
		if d <= -margin:
			break
		var e := 0.05
		var g := Vector2(sd(q + Vector2(e, 0)) - sd(q - Vector2(e, 0)), sd(q + Vector2(0, e)) - sd(q - Vector2(0, e)))
		if g.length() < 1e-5:
			break
		q -= g.normalized() * (d + margin)
	return Vector3(q.x, p.y, q.y)


func _add_box(c: Vector2, h: Vector2, r: float, chamber: int, theme := "", paint := -1) -> int:
	boxes.append({"c": c, "h": h, "r": minf(r, minf(h.x, h.y) - 0.1), "paint": paint, "open": false, "chamber": chamber, "theme": theme})
	return boxes.size() - 1


func _add_chamber(c: Vector2, h: Vector2, r: float, theme: String, corridor := -1) -> void:
	var idx := chambers.size()
	var b := _add_box(c, h, r, idx, theme, idx % 3)
	chambers.append({"box": b, "corridor": corridor, "waves": [], "wave_i": -1, "state": "sealed"})


func _overlaps(c: Vector2, h: Vector2) -> bool:
	for b in boxes:
		var bc: Vector2 = b.c
		var bh: Vector2 = b.h
		if absf(bc.x - c.x) < bh.x + h.x and absf(bc.y - c.y) < bh.y + h.y:
			return true
	return false


## Lay out the room's chambers and corridors.
func plan_layout() -> void:
	boxes.clear()
	holes.clear()
	chambers.clear()
	match kind:
		"combat":
			_plan_chain(3)
		"miniboss":
			_add_chamber(Vector2.ZERO, Vector2(15, 10.5), 4.5, "shrine")
		"boss":
			_add_chamber(Vector2.ZERO, Vector2(17, 12), 5.0, "arena")
		"rest":
			_add_chamber(Vector2.ZERO, Vector2(10, 7.5), 3.5, "rest")
		_:
			_add_chamber(Vector2.ZERO, half, corner, "hub")
	boxes[chambers[0].box].open = true
	chambers[0].state = "waiting"
	var lo := Vector2(1e5, 1e5)
	var hi := Vector2(-1e5, -1e5)
	for b in boxes:
		lo = lo.min(b.c - b.h)
		hi = hi.max(b.c + b.h)
	bounds = Rect2(lo, hi - lo)
	if chambers.size() == 1:
		half = boxes[0].h
		corner = boxes[0].r
	else:
		half = bounds.size * 0.5


func _plan_chain(n: int) -> void:
	var themes: Array = THEMES.get(biome, THEMES.dandaka).duplicate()
	themes.shuffle()
	var h := Vector2(_rng.randf_range(9.5, 11.5), _rng.randf_range(7.0, 8.5))
	_add_chamber(Vector2.ZERO, h, _rng.randf_range(2.5, 4.0), themes[0])
	var last_dir := Vector2.ZERO
	var dirs := [Vector2(0, -1), Vector2(0, -1), Vector2(1, 0), Vector2(-1, 0)]
	for i in range(1, n):
		var placed := false
		for attempt in 40:
			var dir: Vector2 = dirs[_rng.randi() % dirs.size()]
			if attempt > 25:
				dir = Vector2(0, -1)
			if dir == -last_dir or (dir.x != 0.0 and dir.x == -last_dir.x):
				continue
			var prev: Dictionary = boxes[chambers[-1].box]
			var pc: Vector2 = prev.c
			var ph: Vector2 = prev.h
			var nh := Vector2(_rng.randf_range(9.0, 12.5), _rng.randf_range(6.8, 9.0))
			var gap := _rng.randf_range(4.5, 7.0)
			var nc: Vector2
			if dir.y != 0.0:
				nc = pc + Vector2(_rng.randf_range(-6.0, 6.0), -(ph.y + gap + nh.y))
			else:
				nc = pc + Vector2(dir.x * (ph.x + gap + nh.x), _rng.randf_range(-3.5, 3.5))
			if _overlaps(nc, nh + Vector2(2.5, 2.5)):
				continue
			# the last chamber needs a clear north side for the exit gates
			if i == n - 1 and _overlaps(nc + Vector2(0, -nh.y - 5.0), Vector2(nh.x, 4.5)):
				continue
			var cc: Vector2
			var chh: Vector2
			var w := _rng.randf_range(2.3, 3.0)
			if dir.y != 0.0:
				var lo := maxf(pc.x - ph.x, nc.x - nh.x) + w + 1.5
				var hi := minf(pc.x + ph.x, nc.x + nh.x) - w - 1.5
				if lo > hi:
					continue
				var cx := _rng.randf_range(lo, hi)
				var y0 := pc.y - ph.y + 1.2
				var y1 := nc.y + nh.y - 1.2
				cc = Vector2(cx, (y0 + y1) * 0.5)
				chh = Vector2(w, absf(y0 - y1) * 0.5)
			else:
				var lo2 := maxf(pc.y - ph.y, nc.y - nh.y) + w + 1.5
				var hi2 := minf(pc.y + ph.y, nc.y + nh.y) - w - 1.5
				if lo2 > hi2:
					continue
				var cy := _rng.randf_range(lo2, hi2)
				var x0 := pc.x + dir.x * (ph.x - 1.2)
				var x1 := nc.x - dir.x * (nh.x - 1.2)
				cc = Vector2((x0 + x1) * 0.5, cy)
				chh = Vector2(absf(x1 - x0) * 0.5, w)
			var cor := _add_box(cc, chh, 1.0, -1)
			boxes[cor]["dir"] = dir
			_add_chamber(nc, nh, _rng.randf_range(2.5, 4.5), themes[i % themes.size()], cor)
			last_dir = dir
			placed = true
			break
		if not placed:
			break


func first_box() -> Dictionary:
	return boxes[chambers[0].box] if not boxes.is_empty() else {"c": Vector2.ZERO, "h": half, "r": corner}


func last_box() -> Dictionary:
	return boxes[chambers[-1].box] if not boxes.is_empty() else {"c": Vector2.ZERO, "h": half, "r": corner}


func build() -> void:
	if boxes.is_empty():
		plan_layout()
	for i in chambers.size():
		_decorate_chamber(i)
	_build_ground()
	_build_scenery()
	_build_veils()
	if kind != "hub":
		_build_entrance()
	Atmos.build(self)


# --- floor / ground / water -------------------------------------------------

func _room_params(m: ShaderMaterial) -> void:
	var bx := PackedVector4Array()
	var bi := PackedVector4Array()
	for b in boxes:
		bx.append(Vector4(b.c.x, b.c.y, b.h.x, b.h.y))
		bi.append(Vector4(b.r, float(b.paint), 0, 0))
	while bx.size() < 8:
		bx.append(Vector4.ZERO)
		bi.append(Vector4.ZERO)
	var hx := PackedVector4Array()
	var hi := PackedVector4Array()
	for hl in holes:
		hx.append(Vector4(hl.c.x, hl.c.y, hl.h.x, hl.h.y))
		hi.append(Vector4(hl.r, 0, 0, 0))
	while hx.size() < 4:
		hx.append(Vector4.ZERO)
		hi.append(Vector4.ZERO)
	m.set_shader_parameter("boxes", bx)
	m.set_shader_parameter("box_info", bi)
	m.set_shader_parameter("box_count", boxes.size())
	m.set_shader_parameter("holes", hx)
	m.set_shader_parameter("hole_info", hi)
	m.set_shader_parameter("hole_count", holes.size())


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


func _plane(size: Vector2, mat: Material, y: float, at := Vector2.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = size
	pm.subdivide_width = 0
	pm.subdivide_depth = 0
	mi.mesh = pm
	mi.material_override = mat
	mi.position = Vector3(at.x, y, at.y)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


## Which painted Higgsfield floors this room's chambers use (up to three).
func paint_keys() -> Array:
	var pool: Array = PAINTS.get(biome, PAINTS.dandaka).duplicate()
	match kind:
		"hub":
			pool = ["hub"]
		"boss":
			pool = ["boss"]
		"miniboss":
			pool = ["candi", "dandaka2"]
	var out := []
	# keep the original floors in rotation, add the newer ones for variety
	var start := depth % pool.size()
	for i in pool.size():
		var k: String = pool[(start + i) % pool.size()]
		if Hf.floor_tex(k):
			out.append(k)
		if out.size() == 3:
			break
	return out


func paint_key() -> String:
	var k := paint_keys()
	return k[0] if not k.is_empty() else ""


func _build_ground() -> void:
	var center := bounds.get_center()
	var big := bounds.size + Vector2(70, 70)
	if biome == "muara":
		var wm := ShaderMaterial.new()
		wm.shader = WATER
		wm.set_shader_parameter("noise", NOISE)
		_room_params(wm)
		_plane(big, wm, -0.35, center)
	else:
		var tint := Color(0.3, 0.36, 0.34) if biome == "dandaka" else Color(0.3, 0.27, 0.28)
		var gtex: Texture2D = TEX.dandaka
		var gm := _floor_mat(gtex, big * 0.5 + center.abs(), 1.0, tint, 0.09)
		_plane(big, gm, -0.02, center)
		# ponds sunk into the stone
		for hl in holes:
			var pm := ShaderMaterial.new()
			pm.shader = WATER
			pm.set_shader_parameter("noise", NOISE)
			_room_params(pm)
			_plane(hl.h * 2.0 + Vector2(3, 3), pm, -0.01, hl.c)
	var ftex: Texture2D = TEX.get(biome, TEX.dandaka)
	var ftint: Color = {"dandaka": Color(0.8, 0.86, 0.84), "muara": Color(0.72, 0.68, 0.64), "hub": Color(0.55, 0.5, 0.54)}.get(biome, Color.WHITE)
	var fm := _floor_mat(ftex, half, corner, ftint, 0.16)
	_room_params(fm)
	var keys := paint_keys()
	if not keys.is_empty():
		var slots := ["paint_tex", "paint_tex2", "paint_tex3"]
		for i in 3:
			fm.set_shader_parameter(slots[i], Hf.floor_tex(keys[i % keys.size()]))
		fm.set_shader_parameter("use_paint", 1.0)
		fm.set_shader_parameter("paint_half", half + Vector2(2.0, 1.6))
		fm.set_shader_parameter("tint", Vector3(0.95, 0.95, 0.95))
	_plane(bounds.size + Vector2(6, 6), fm, 0.0, center)


# --- scenery ------------------------------------------------------------------------

## Points around a rounded box's edge at distance `offset`, every `step` metres.
func _perimeter(offset: float, step: float, c := Vector2.ZERO, h := Vector2.ZERO, r := -1.0) -> Array:
	if h == Vector2.ZERO:
		h = half
		r = corner
	var pts := []
	var hh := h + Vector2(offset, offset)
	var cr := r + offset
	var straight_x := hh.x - cr
	var straight_y := hh.y - cr
	var per := 4.0 * (straight_x + straight_y) + TAU * cr
	var n := int(ceil(per / step))
	for i in n:
		var t := per * i / n
		pts.append(c + _perim_point(t, straight_x, straight_y, cr))
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


func _near_corridor(p: Vector2, margin: float) -> bool:
	for b in boxes:
		if b.chamber < 0 and sd_box(p, b.c, b.h, b.r) < margin:
			return true
	return false


func _free_spot(p: Vector2, r: float) -> bool:
	if sd_all(p) > -r - 1.5 or _near_corridor(p, 3.0):
		return false
	for o in obstacles:
		if (o[0] as Vector2).distance_to(p) < float(o[1]) + r + 2.2:
			return false
	var fb := first_box()
	if Vector2(fb.c.x, fb.c.y + fb.h.y).distance_to(p) < 4.0:
		return false
	return true


## Theme set pieces inside a chamber: pond, pillar ring, ruins, grove, shrine...
func _decorate_chamber(i: int) -> void:
	var b: Dictionary = boxes[chambers[i].box]
	var c: Vector2 = b.c
	var h: Vector2 = b.h
	var theme: String = b.theme
	if kind != "combat":
		if kind == "miniboss":
			for k in 6:
				var a := TAU * k / 6.0 + 0.3
				add_obstacle("candi_pilar", c + Vector2(cos(a) * h.x * 0.72, sin(a) * h.y * 0.72), 0.7, _rng.randf() * TAU)
		elif kind == "boss":
			for k in 4:
				var a2 := TAU * k / 4.0 + PI / 4
				var hp := c + Vector2(cos(a2) * h.x * 0.62, sin(a2) * h.y * 0.62)
				holes.append({"c": hp, "h": Vector2(2.4, 1.9), "r": 1.6})
		return
	var inside := ["candi_pilar", "arca", "batu_besar"] if biome != "muara" else ["batu_besar", "candi_pilar"]
	_add_breakables(c, h)
	match theme:
		"pond":
			var ph := Vector2(h.x * _rng.randf_range(0.28, 0.36), h.y * _rng.randf_range(0.28, 0.38))
			holes.append({"c": c, "h": ph, "r": minf(ph.x, ph.y) * 0.85})
			for k in 4:
				var a := TAU * k / 4.0 + PI / 4
				var tp := c + Vector2(cos(a) * (ph.x + 1.6), sin(a) * (ph.y + 1.6))
				add_prop("teratai" if biome == "muara" else "bunga_glow", tp, _rng.randf() * TAU)
			obstacles.append([c, maxf(ph.x, ph.y)])
		"pillars":
			var n := _rng.randi_range(5, 7)
			for k in n:
				var a := TAU * k / n + _rng.randf() * 0.3
				var p := c + Vector2(cos(a) * h.x * 0.55, sin(a) * h.y * 0.55)
				if _free_spot(p, 0.7):
					add_obstacle("candi_pilar", p, 0.7, _rng.randf() * TAU)
		"ruins", "rocks":
			for k in _rng.randi_range(3, 5):
				for attempt in 12:
					var p := c + Vector2(_rng.randf_range(-h.x + 3, h.x - 3), _rng.randf_range(-h.y + 3, h.y - 3))
					if p.distance_to(c) > 2.5 and _free_spot(p, 1.1):
						var id := "candi_reruntuhan" if theme == "ruins" and _rng.randf() < 0.6 else "batu_besar"
						add_obstacle(id, p, 1.1, _rng.randf() * TAU, _rng.randf_range(0.8, 1.1))
						break
		"grove", "mangrove":
			for k in _rng.randi_range(3, 4):
				for attempt in 12:
					var p := c + Vector2(_rng.randf_range(-h.x + 3, h.x - 3), _rng.randf_range(-h.y + 3, h.y - 3))
					if _free_spot(p, 0.9):
						add_obstacle("bakau" if theme == "mangrove" else "pohon_mati", p, 0.9, _rng.randf() * TAU, _rng.randf_range(0.7, 0.9))
						break
			for k in 6:
				var p := c + Vector2(_rng.randf_range(-h.x + 2, h.x - 2), _rng.randf_range(-h.y + 2, h.y - 2))
				if _free_spot(p, 0.5):
					add_prop("semak" if theme == "grove" else "teratai", p, _rng.randf() * TAU, _rng.randf_range(0.7, 1.0), -0.05 if theme == "mangrove" else 0.0)
		"shrine":
			add_obstacle("arca", c, 0.9, PI)
			for k in 4:
				var a := TAU * k / 4.0 + PI / 4
				add_torch(c + Vector2(cos(a), sin(a)) * 3.2)
			var l := OmniLight3D.new()
			l.light_color = Color("5fe0c8")
			l.light_energy = 1.4
			l.omni_range = 6.0
			l.position = Vector3(c.x, 1.5, c.y)
			add_child(l)
		"piers":
			for k in 3:
				var p := c + Vector2(_rng.randf_range(-h.x + 3, h.x - 3), _rng.randf_range(-h.y + 3, h.y - 3))
				if _free_spot(p, 1.2):
					add_obstacle("perahu", p, 1.2, _rng.randf() * TAU, 0.9)
		_:
			for k in _rng.randi_range(1, 2):
				for attempt in 12:
					var p := c + Vector2(_rng.randf_range(-h.x + 3, h.x - 3), _rng.randf_range(-h.y + 3, h.y - 3))
					if p.distance_to(c) > 3.0 and _free_spot(p, 0.8):
						add_obstacle(inside[_rng.randi() % inside.size()], p, 0.8, _rng.randf() * TAU)
						break


## Clusters of gentong / peti near the chamber walls.
func _add_breakables(c: Vector2, h: Vector2) -> void:
	var groups := _rng.randi_range(1, 3)
	for g in groups:
		for attempt in 16:
			var side := _rng.randi() % 4
			var p := c
			match side:
				0: p += Vector2(_rng.randf_range(-h.x + 2, h.x - 2), -h.y + 1.6)
				1: p += Vector2(_rng.randf_range(-h.x + 2, h.x - 2), h.y - 1.6)
				2: p += Vector2(-h.x + 1.6, _rng.randf_range(-h.y + 2, h.y - 2))
				_: p += Vector2(h.x - 1.6, _rng.randf_range(-h.y + 2, h.y - 2))
			if sd_all(p) > -1.0 or not _free_spot(p, 1.4) or _near_corridor(p, 3.0):
				continue
			for k in _rng.randi_range(1, 3):
				var q := p + Vector2(_rng.randf_range(-0.9, 0.9), _rng.randf_range(-0.9, 0.9))
				var b := Breakable.make("peti" if biome == "muara" and _rng.randf() < 0.6 else "gentong")
				add_child(b)
				b.position = Vector3(q.x, 0, q.y)
			obstacles.append([p, 1.2])
			break


## Scenery bands hugging the whole map's edge (outside the walkable floor).
func _build_scenery() -> void:
	var ring_props: Array
	match biome:
		"muara":
			ring_props = [["bakau", 0.35], ["batu_besar", 0.2], ["teratai", 0.25], ["perahu", 0.08], ["batu", 0.12]]
		"hub":
			ring_props = [["beringin", 0.2], ["semak", 0.35], ["pakis", 0.25], ["candi_pilar", 0.1], ["batu", 0.1]]
		_:
			ring_props = [["beringin", 0.2], ["pohon_mati", 0.12], ["semak", 0.22], ["pakis", 0.22], ["candi_reruntuhan", 0.1], ["batu_besar", 0.08], ["candi_pilar", 0.06]]
	var fb := first_box()
	var lb := last_box()
	var gate_y: float = lb.c.y - lb.h.y
	var entry_y: float = fb.c.y + fb.h.y
	# [min dist, max dist, grid step, scale]
	for band in [[0.9, 2.0, 1.7, 0.8], [2.0, 4.2, 2.8, 1.0], [4.2, 8.5, 4.2, 1.25]]:
		var step: float = band[2]
		var x := bounds.position.x - 9.0
		while x < bounds.end.x + 9.0:
			var y := bounds.position.y - 9.0
			while y < bounds.end.y + 9.0:
				var pos := Vector2(x, y) + Vector2(_rng.randf_range(-0.45, 0.45), _rng.randf_range(-0.45, 0.45)) * step
				y += step
				var d := sd_all(pos)
				if d < band[0] or d > band[1] or _in_hole(pos):
					continue
				if kind != "hub" and pos.y < gate_y + 0.5 and pos.y > gate_y - 6.0 and absf(pos.x - lb.c.x) < 7.5:
					continue   # keep the gates' approach open
				if pos.y > entry_y - 1.0 and pos.y < entry_y + 5.0 and absf(pos.x - fb.c.x) < 2.8:
					continue   # entrance
				# is this on the camera (south) side of the floor?
				var south: bool = sd_all(pos + Vector2(0, -3.0)) < d - 1.8
				if south and band[0] < 1.5:
					continue   # keep the camera side low so it doesn't hide the arena
				var id := _pick(ring_props)
				if (south or _near_corridor(pos, 5.5)) and (id == "beringin" or id == "bakau" or id == "pohon_mati" or id == "candi_reruntuhan"):
					id = "semak" if biome != "muara" else "teratai"
				var yy := -0.3 if biome == "muara" and id == "teratai" else 0.0
				add_prop(id, pos, _rng.randf() * TAU, band[3] * _rng.randf_range(0.8, 1.2), yy)
			x += step
	# torches and glowing flowers along every chamber's edge
	for ch in chambers:
		var b: Dictionary = boxes[ch.box]
		var tp := _perimeter(0.6, 9.0, b.c, b.h, b.r)
		for i in tp.size():
			var p: Vector2 = tp[i]
			if absf(sd_all(p) - 0.6) > 0.35 or _near_corridor(p, 2.0):
				continue
			if sd_all(p + Vector2(0, -3.0)) < sd_all(p) - 1.8:
				continue
			if i % 2 == 0:
				add_torch(p)
			elif biome != "hub":
				add_glow(p, Color("e0508f") if _rng.randf() < 0.5 else Color("5fe0c8"))


func _in_hole(p: Vector2) -> bool:
	for hl in holes:
		if sd_box(p, hl.c, hl.h, hl.r) < 1.0:
			return true
	return false


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
	var fb := first_box()
	add_prop("gapura", Vector2(fb.c.x, fb.c.y + fb.h.y + 1.4), PI, 0.9)


func player_start() -> Vector3:
	if kind == "hub":
		return Vector3(0, 0, 2.0)
	var fb := first_box()
	return Vector3(fb.c.x, 0, fb.c.y + fb.h.y - 1.6)


# --- sealed corridors ------------------------------------------------------------

## A spirit veil across each corridor mouth, flanked by candi pillars.
func _build_veils() -> void:
	for i in range(1, chambers.size()):
		var cor: int = chambers[i].corridor
		if cor < 0:
			continue
		var b: Dictionary = boxes[cor]
		var dir: Vector2 = b.get("dir", Vector2(0, -1))
		var prev: Dictionary = boxes[chambers[i - 1].box]
		var mouth: Vector2
		var across: Vector2
		if dir.y != 0.0:
			mouth = Vector2(b.c.x, prev.c.y - prev.h.y - 0.3)
			across = Vector2(1, 0)
		else:
			mouth = Vector2(prev.c.x + dir.x * (prev.h.x + 0.3), b.c.y)
			across = Vector2(0, 1)
		var w: float = b.h.x if dir.y != 0.0 else b.h.y
		for s in [-1.0, 1.0]:
			var pp: Vector2 = mouth + across * s * (w + 0.4)
			add_prop("candi_pilar", pp, 0.0, 0.9)
		var veil := MeshInstance3D.new()
		var q := QuadMesh.new()
		q.size = Vector2(w * 2.0 + 0.4, 3.6)
		veil.mesh = q
		var vm := Art.fx_mat(Color(0.6, 0.2, 0.9), 0.5)
		vm.set_shader_parameter("use_mask", 1.0)
		vm.set_shader_parameter("mask", VEIL)
		veil.material_override = vm
		veil.position = Vector3(mouth.x, 1.8, mouth.y)
		veil.rotation.y = 0.0 if dir.y != 0.0 else PI / 2
		veil.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(veil)
		chambers[i]["veil"] = veil
		chambers[i]["mouth"] = mouth


func _open_chamber(i: int) -> void:
	var ch: Dictionary = chambers[i]
	boxes[ch.box].open = true
	if ch.corridor >= 0:
		boxes[ch.corridor].open = true
	ch.state = "waiting"
	var veil: MeshInstance3D = ch.get("veil")
	if veil and is_instance_valid(veil):
		var m := veil.material_override as ShaderMaterial
		m.set_shader_parameter("color", Color(1.0, 0.8, 0.4))
		var tw := veil.create_tween()
		tw.tween_method(func(v): m.set_shader_parameter("intensity", v), 1.2, 0.0, 0.8)
		tw.tween_callback(veil.queue_free)
	var mouth: Vector2 = ch.get("mouth", boxes[ch.box].c)
	Fx.magic_circle(Vector3(mouth.x, 0, mouth.y), 2.6, Color(1.0, 0.82, 0.4), 1.4, 2.0)
	Au.sfx("sfx_gate", -2.0)
	G.say("Jalan terbuka! Terus maju, Hanoman.", Color(1, 0.9, 0.6))
	# a beacon so the way on is easy to find in the larger maps
	_hint = Node3D.new()
	add_child(_hint)
	_hint.position = Vector3(mouth.x, 0, mouth.y)
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.8, 0.4)
	l.light_energy = 2.5
	l.omni_range = 6.0
	l.position.y = 1.5
	_hint.add_child(l)
	var ring := Fx.sprite("circle", Vector3(0, 0.08, 0), 3.0, Color(1.0, 0.82, 0.4), 999.0,
		{"parent": _hint, "flat": true, "from": 1.0, "grow": 1.0, "spin": 600.0, "tint": 0.5, "intensity": 1.4, "hold": 0.99, "fade_in": 0.0005})
	ring.name = "beacon"


func _player_in_chamber(i: int) -> bool:
	var pl: Vector3 = G.main.player.global_position
	var b: Dictionary = boxes[chambers[i].box]
	return sd_box(Vector2(pl.x, pl.z), b.c, b.h, b.r) < -1.2


# --- exits ---------------------------------------------------------------------

func build_exits() -> void:
	var n := exits.size()
	var lb := last_box()
	var xs := [0.0] if n == 1 else [-4.5, 4.5] if n == 2 else [-6.0, 0.0, 6.0]
	for i in n:
		var rw: Dictionary = exits[i]
		var pos := Vector2(lb.c.x + xs[i], lb.c.y - lb.h.y - 0.4)
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
		Au.sfx("sfx_gate", -3.0)


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
		_combat_tick(delta)
	elif kind == "miniboss" or kind == "boss":
		if wave_i < 0:
			_wave_delay -= delta
			if _wave_delay <= 0.0:
				_spawn_boss()
		elif alive.is_empty():
			_on_clear()


func _combat_tick(delta: float) -> void:
	var ch: Dictionary = chambers[cur]
	var cw: Array = waves[cur] if cur < waves.size() else []
	match ch.state:
		"waiting":
			if cur == 0 or _player_in_chamber(cur):
				ch.state = "fight"
				_wave_delay = 0.9 if cur == 0 else 0.4
				if _hint and is_instance_valid(_hint):
					_hint.queue_free()
					_hint = null
		"fight":
			Au.intensity(true)
			if alive.size() + _pending <= (1 if ch.wave_i < cw.size() - 1 else 0):
				if ch.wave_i + 1 < cw.size():
					_wave_delay -= delta
					if _wave_delay <= 0.0:
						ch.wave_i += 1
						wave_i = ch.wave_i
						_spawn_wave(cw[ch.wave_i], cur)
				elif alive.is_empty() and _pending == 0:
					ch.state = "clear"
					Au.intensity(false)
					if cur + 1 < chambers.size():
						cur += 1
						_open_chamber(cur)
					else:
						_on_clear()


func _spawn_wave(list: Array, chamber: int) -> void:
	_wave_delay = 1.0
	var pl: Vector3 = G.main.player.global_position
	for i in list.size():
		var pos := _spawn_point(pl, chamber)
		var kind_i: String = list[i]
		Fx.ring(pos, 1.0, Color(0.7, 0.2, 0.9), 0.6)
		var e := Enemy.new()
		e.setup(kind_i, depth)
		# elite chance grows with depth and in later chambers
		if i == 0 and _rng.randf() < 0.08 + depth * 0.03 + chamber * 0.06:
			e.make_elite()
		_pending += 1
		var t := get_tree().create_timer(0.55 + i * 0.12)
		t.timeout.connect(func():
			_pending -= 1
			if is_instance_valid(self) and not is_clear:
				G.main.spawn_actor(e, pos)
				alive.append(e)
			else:
				e.free())


func _spawn_point(avoid: Vector3, chamber := 0) -> Vector3:
	var b: Dictionary = boxes[chambers[chamber].box] if not chambers.is_empty() else {"c": Vector2.ZERO, "h": half, "r": corner}
	for attempt in 40:
		var p := Vector2(_rng.randf_range(b.c.x - b.h.x + 1.5, b.c.x + b.h.x - 1.5), _rng.randf_range(b.c.y - b.h.y + 1.5, b.c.y + b.h.y - 1.5))
		if sd(p) > -1.2 or sd_box(p, b.c, b.h, b.r) > -1.2:
			continue
		if Vector2(avoid.x, avoid.z).distance_to(p) < 5.5:
			continue
		var ok := true
		for o in obstacles:
			if (o[0] as Vector2).distance_to(p) < float(o[1]) + 1.2:
				ok = false
		if ok:
			return Vector3(p.x, 0, p.y)
	return Vector3(b.c.x, 0, b.c.y - b.h.y * 0.5)


func _spawn_boss() -> void:
	wave_i = 0
	if kind == "miniboss":
		var b := Boss.new()
		b.setup_boss("kijang")
		G.main.spawn_actor(b, Vector3(0, 0, -half.y * 0.45))
		alive.append(b)
		G.main.ui.set_bosses([b])
		_add_hazards([b])
		G.main.boss_intro(b, b.boss_name, b.boss_title)
	else:
		var s := Boss.new()
		s.setup_boss("sura")
		var y := Boss.new()
		y.setup_boss("baya")
		s.rival = y
		y.rival = s
		G.main.spawn_actor(s, Vector3(-4.5, 0, -half.y * 0.3))
		G.main.spawn_actor(y, Vector3(4.5, 0, -half.y * 0.3))
		alive.append(s)
		alive.append(y)
		G.main.ui.set_bosses([s, y])
		_add_hazards([s, y])
		G.main.boss_intro(s, "Sura & Baya", "Penguasa Muara Kalimas")


func _add_hazards(list: Array) -> void:
	var hz := Hazards.new()
	hz.arena = self
	hz.bosses = list
	add_child(hz)


func _on_clear() -> void:
	if is_clear:
		return
	is_clear = true
	Au.intensity(false)
	if kind != "rest" and kind != "hub":
		Au.sfx("sfx_room_clear", -2.0)
		G.main.ui.room_clear_banner()
		G.main.slowmo(0.25, 0.6)
	cleared.emit()
	G.main.on_room_cleared(self)
