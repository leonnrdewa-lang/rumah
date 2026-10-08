extends Node
## The player's house: four levels (Rumah Mungil -> Rumah Kayu -> Rumah Bata -> Rumah
## Gedongan), each a bigger, fancier room, and furniture bought from the Koperasi's
## catalog that sits on a 0.8 m grid in the room (move / rotate / store in the gudang,
## in the "Atur Rumah" panel or at the stand inside the house). The aquarium shows the
## SR and SSR fish you have caught swimming around.
## interior.gd asks build_room() for the juragan room; everything else is here.

var hub: Node
var _it := {}          # "Atur rumah" spot inside the house
var _fish: Array = []  # aquarium sprites [Sprite3D, base Vector3, phase, span]
var _fans: Array = []
var _t := 0.0
var sel := -1          # selected placed item in the editor

const CELL := 0.8
const LEVELS := [
	{"id": "mungil", "name": "Rumah Mungil", "half": Vector2(3.6, 2.6), "cost": 0,
		"desc": "Rumah dinas pewaralaba. DP 0%, cicilan seumur hidup."},
	{"id": "kayu", "name": "Rumah Kayu", "half": Vector2(4.6, 3.3), "cost": 5000000,
		"desc": "Dinding papan, lantai kayu, kasur besar. Mulai terlihat juragan."},
	{"id": "bata", "name": "Rumah Bata", "half": Vector2(5.2, 3.6), "cost": 12000000,
		"desc": "Tembok bata, lantai keramik, dua jendela. Tetangga mulai iri."},
	{"id": "gedongan", "name": "Rumah Gedongan", "half": Vector2(6.0, 4.0), "cost": 30000000,
		"desc": "Lantai marmer, pilar Romawi, lampu kristal, potret dirimu sebesar pintu."},
]
## catalog: footprint in cells (w along x, d along z), the level it needs
const FURN := {
	"kursi_rotan": {"name": "Kursi rotan", "price": 250000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Kursi teras klasik. Cocok untuk melamun soal harga TBS."},
	"meja_tamu": {"name": "Meja tamu", "price": 400000, "w": 2, "d": 1, "icon": "icon_sofa", "desc": "Lengkap dengan toples kue Lebaran (isinya rengginang)."},
	"sofa": {"name": "Sofa empuk", "price": 1500000, "w": 3, "d": 1, "icon": "icon_sofa", "desc": "Masih ada plastik pembungkusnya. Jangan dilepas, biar awet."},
	"tv": {"name": "TV tabung 21 inci", "price": 2000000, "w": 2, "d": 1, "icon": "icon_sofa", "desc": "Sinetron azab tiap malam. Antena diputar pakai doa."},
	"kulkas": {"name": "Kulkas dua pintu", "price": 2500000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Isinya air putih dan satu pete. Tapi dua pintu."},
	"akuarium": {"name": "Akuarium kaca", "price": 3000000, "w": 2, "d": 1, "icon": "icon_akuarium", "desc": "Memamerkan ikan SR & SSR yang pernah kamu tangkap."},
	"monstera": {"name": "Tanaman monstera", "price": 300000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Tanaman hias tren. Harganya naik turun seperti TBS."},
	"karpet": {"name": "Karpet Persia (KW)", "price": 1000000, "w": 3, "d": 2, "icon": "icon_sofa", "desc": "Dari Persia, katanya. Labelnya: Tanah Abang.", "flat": true},
	"rak_buku": {"name": "Rak buku", "price": 600000, "w": 2, "d": 1, "icon": "icon_sofa", "desc": "Isinya: 'Cara Cepat Kaya Tanpa Ketahuan' jilid 1-12."},
	"kipas": {"name": "Kipas angin berdiri", "price": 350000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Tiga kecepatan: sepoi, kencang, kertas beterbangan."},
	"lampu_hias": {"name": "Lampu hias berdiri", "price": 800000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Cahaya hangat untuk menghitung uang malam-malam."},
	"karaoke": {"name": "Karaoke 'Juragan Idol'", "price": 1200000, "w": 1, "d": 1, "icon": "icon_megafon", "desc": "Speaker aktif 1000 watt. Tetangga pasti dengar."},
	"foto_juragan": {"name": "Potret diri berbingkai emas", "price": 1000000, "w": 2, "d": 1, "icon": "icon_medali", "desc": "Lukisan dirimu berpose di atas tumpukan TBS."},
	"patung_singa": {"name": "Patung singa emas", "price": 5000000, "w": 1, "d": 1, "icon": "icon_medali", "lvl": 2, "desc": "Wajib untuk orang kaya baru. Emasnya cat semprot."},
	"meja_billiar": {"name": "Meja biliar", "price": 8000000, "w": 3, "d": 2, "icon": "icon_sofa", "lvl": 3, "desc": "Untuk menjamu oknum. Stiknya juga bisa buat menggaruk punggung."},
	"dispenser": {"name": "Dispenser galon", "price": 400000, "w": 1, "d": 1, "icon": "icon_sofa", "desc": "Air panas, air dingin, dan bunyi 'blup' yang menenangkan."},
}


func hs() -> Dictionary:
	return hub.st("house", {"lvl": 0, "own": {}, "placed": [{"id": "karpet", "c": -1, "r": -1, "rot": 0}, {"id": "kursi_rotan", "c": -1, "r": -1, "rot": 0}]})


func level() -> int:
	return clampi(int(hs()["lvl"]), 0, LEVELS.size() - 1)


func level_name(l := -1) -> String:
	return LEVELS[level() if l < 0 else l]["name"]


func half() -> Vector2:
	return LEVELS[level()]["half"]


func grid_size() -> Vector2i:
	var h := half()
	return Vector2i(int(floor(h.x * 2.0 / CELL)), int(floor(h.y * 2.0 / CELL)))


func cell_center(c: int, r: int, w: int, d: int) -> Vector3:
	## room-local centre of a footprint whose top-left cell is (c, r)
	var g := grid_size()
	var ox := -g.x * CELL * 0.5
	var oz := -g.y * CELL * 0.5
	return Vector3(ox + (c + w * 0.5) * CELL, 0, oz + (r + d * 0.5) * CELL)


func footprint(p: Dictionary) -> Vector2i:
	var f: Dictionary = FURN.get(str(p["id"]), {"w": 1, "d": 1})
	var w := int(f["w"])
	var d := int(f["d"])
	return Vector2i(d, w) if int(p.get("rot", 0)) % 2 == 1 else Vector2i(w, d)


# ------------------------------------------------------------------ the grid
func fixed_rects() -> Array:
	## room-local rects [x0, z0, x1, z1] taken by the built-in furniture and the door
	var h := half()
	var out: Array = []
	out.append([-1.1, h.y - 1.5, 1.1, h.y + 1.0])   # the doorway
	var b := _bed_local()
	var bw := 1.9 if level() >= 1 else 1.6
	out.append([b.x - bw * 0.5, b.z - 1.25, b.x + bw * 0.5, b.z + 1.2])
	out.append([b.x - bw * 0.5 - 1.2, b.z + 1.15, b.x + bw * 0.5 + 0.2, b.z + 1.9])   # standing room beside the bed
	var cb := _cup_local()
	out.append([cb.x - 0.75, cb.z - 0.35, cb.x + 0.75, cb.z + 1.3])
	var dk := _desk_local()
	out.append([dk.x - 0.85, dk.z - 0.45, dk.x + 0.85, dk.z + 1.1])
	out.append([-h.x, h.y - 1.6, -h.x + 1.8, h.y])   # the decor stand by the door
	if level() >= 1:
		out.append([-h.x, -0.7, -h.x + 0.9, 0.9])   # the safe
	if level() == 3:
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				out.append([sx * (h.x - 0.6) - 0.4, sz * (h.y - 0.6) - 0.4, sx * (h.x - 0.6) + 0.4, sz * (h.y - 0.6) + 0.4])
	return out


func blocked_cells(skip := -1) -> Dictionary:
	## cell -> "fixed" or the placed index occupying it
	var g := grid_size()
	var out := {}
	var fr := fixed_rects()
	for c in g.x:
		for r in g.y:
			var p := cell_center(c, r, 1, 1)
			for q in fr:
				if p.x > q[0] and p.x < q[2] and p.z > q[1] and p.z < q[3]:
					out[Vector2i(c, r)] = "fixed"
					break
	var placed: Array = hs()["placed"]
	for k in placed.size():
		if k == skip:
			continue
		var it: Dictionary = placed[k]
		if int(it["c"]) < 0:
			continue
		var fp := footprint(it)
		for dc in fp.x:
			for dr in fp.y:
				out[Vector2i(int(it["c"]) + dc, int(it["r"]) + dr)] = k
	return out


func fits(id: String, c: int, r: int, rot: int, skip := -1) -> bool:
	var g := grid_size()
	var fp := footprint({"id": id, "rot": rot})
	if c < 0 or r < 0 or c + fp.x > g.x or r + fp.y > g.y:
		return false
	var bl := blocked_cells(skip)
	for dc in fp.x:
		for dr in fp.y:
			var cell := Vector2i(c + dc, r + dr)
			if bl.has(cell):
				# flat rugs may lie under furniture and furniture on rugs
				var o = bl[cell]
				if typeof(o) == TYPE_INT and (FURN[id].get("flat", false) or FURN[str(hs()["placed"][o]["id"])].get("flat", false)):
					continue
				return false
	return true


func find_spot(id: String, rot := 0, skip := -1) -> Vector2i:
	var g := grid_size()
	# from the middle of the room outwards
	var cells: Array = []
	for c in g.x:
		for r in g.y:
			cells.append(Vector2i(c, r))
	var mid := Vector2(g.x * 0.5, g.y * 0.5)
	cells.sort_custom(func(a, b): return Vector2(a).distance_to(mid) < Vector2(b).distance_to(mid))
	for cell in cells:
		if fits(id, cell.x, cell.y, rot, skip):
			return cell
	return Vector2i(-1, -1)


func _settle() -> void:
	## place any item still waiting for a spot (new house, after an upgrade, old saves)
	var placed: Array = hs()["placed"]
	for k in placed.size():
		var it: Dictionary = placed[k]
		if int(it["c"]) >= 0 and fits(str(it["id"]), int(it["c"]), int(it["r"]), int(it.get("rot", 0)), k):
			continue
		var at := find_spot(str(it["id"]), int(it.get("rot", 0)), k)
		it["c"] = at.x
		it["r"] = at.y
	# items that found no room go back into the gudang
	var keep: Array = []
	for it in placed:
		if int(it["c"]) >= 0:
			keep.append(it)
		else:
			_own_add(str(it["id"]), 1)
	hs()["placed"] = keep


func _own_add(id: String, n: int) -> void:
	var own: Dictionary = hs()["own"]
	own[id] = maxi(0, int(own.get(id, 0)) + n)
	if int(own[id]) == 0:
		own.erase(id)


# ------------------------------------------------------------------ actions
func buy(id: String) -> bool:
	var f: Dictionary = FURN.get(id, {})
	if f.is_empty() or level() + 1 < int(f.get("lvl", 0)) or not GS.spend(int(f["price"])):
		return false
	Sfx.play("cash")
	hub.add_stat("furniture")
	var ok := place_new(id)
	hub.ui.toast("%s %s" % [f["name"], "dikirim ke rumahmu dan sudah dipasang!" if ok else "masuk gudang (rumahmu penuh)."], "good")
	return true


func place_new(id: String) -> bool:
	var at := find_spot(id)
	if at.x < 0:
		_own_add(id, 1)
		return false
	hs()["placed"].append({"id": id, "c": at.x, "r": at.y, "rot": 0})
	rebuild()
	return true


func place_from_store(id: String) -> bool:
	var own: Dictionary = hs()["own"]
	if int(own.get(id, 0)) <= 0:
		return false
	var at := find_spot(id)
	if at.x < 0:
		hub.ui.toast("Tidak ada tempat kosong untuk %s." % FURN[id]["name"], "bad")
		return false
	_own_add(id, -1)
	hs()["placed"].append({"id": id, "c": at.x, "r": at.y, "rot": 0})
	sel = hs()["placed"].size() - 1
	rebuild()
	return true


func move(k: int, dc: int, dr: int) -> bool:
	var placed: Array = hs()["placed"]
	if k < 0 or k >= placed.size():
		return false
	var it: Dictionary = placed[k]
	var c := int(it["c"]) + dc
	var r := int(it["r"]) + dr
	if not fits(str(it["id"]), c, r, int(it.get("rot", 0)), k):
		return false
	it["c"] = c
	it["r"] = r
	rebuild()
	return true


func move_to(k: int, c: int, r: int) -> bool:
	var placed: Array = hs()["placed"]
	if k < 0 or k >= placed.size():
		return false
	var it: Dictionary = placed[k]
	return move(k, c - int(it["c"]), r - int(it["r"]))


func rotate(k: int) -> bool:
	var placed: Array = hs()["placed"]
	if k < 0 or k >= placed.size():
		return false
	var it: Dictionary = placed[k]
	var nr := (int(it.get("rot", 0)) + 1) % 4
	if not fits(str(it["id"]), int(it["c"]), int(it["r"]), nr, k):
		# try to keep it in the room: nudge left / up
		for off in [Vector2i(-1, 0), Vector2i(0, -1), Vector2i(-1, -1), Vector2i(-2, 0), Vector2i(0, -2)]:
			if fits(str(it["id"]), int(it["c"]) + off.x, int(it["r"]) + off.y, nr, k):
				it["c"] = int(it["c"]) + off.x
				it["r"] = int(it["r"]) + off.y
				it["rot"] = nr
				rebuild()
				return true
		return false
	it["rot"] = nr
	rebuild()
	return true


func store(k: int) -> bool:
	var placed: Array = hs()["placed"]
	if k < 0 or k >= placed.size():
		return false
	_own_add(str(placed[k]["id"]), 1)
	placed.remove_at(k)
	sel = -1
	rebuild()
	return true


func upgrade() -> bool:
	if level() >= LEVELS.size() - 1:
		return false
	var nxt: Dictionary = LEVELS[level() + 1]
	if not GS.spend(int(nxt["cost"])):
		return false
	hs()["lvl"] = level() + 1
	GS.add_rep(2)
	_settle()
	Sfx.play("quest")
	hub.ui.toast("Renovasi selesai! Rumahmu kini %s." % nxt["name"], "quest")
	rebuild()
	_update_plate()
	return true


func rebuild() -> void:
	## re-make the room if the player is in it
	var w: Node = hub.world
	if w.inside == "rumah_juragan":
		w.interior.setup_for("rumah_juragan", "")
		w._bed_item["pos"] = w.interior.bed_world()
		w._cup_item["pos"] = w.interior.cupboard_world()
	_update_spot()


func refresh() -> void:
	_settle()
	_update_spot()
	_update_plate()


func _update_spot() -> void:
	var w: Node = hub.world
	var h := half()
	var pos: Vector3 = w.interior.to_world(Vector3(-h.x + 0.9, 0, h.y - 0.9))
	if _it.is_empty():
		_it = hub.add_spot(pos, 1.5, func(): return "Atur rumah (dekorasi & renovasi)", func(): show_editor(),
			func(): return w.inside == "rumah_juragan")
	_it["pos"] = pos


func _update_plate() -> void:
	var node: Node3D = hub.world.building_nodes.get("rumah_juragan")
	if node == null:
		return
	for c in node.get_children():
		if c is Label3D:
			(c as Label3D).text = "Rumah Juragan" if level() == 0 else level_name()
			if level() == 3:
				(c as Label3D).modulate = Color("8a6a10")


# ------------------------------------------------------------------ the room (called by interior.gd)
func _bed_local() -> Vector3:
	var h := half()
	return Vector3(h.x - (1.0 if level() == 0 else 1.5), 0, -h.y + 1.3)


func _cup_local() -> Vector3:
	var h := half()
	return Vector3(-h.x + 0.85, 0, -h.y + 0.35)


func _desk_local() -> Vector3:
	var h := half()
	return Vector3(-h.x + 2.9, 0, -h.y + 0.6)


func build_room(it: Node3D) -> bool:
	## builds the player's room into interior.gd `it` (its primitive helpers make the
	## shell and the fixed furniture); returns true when it did
	var lv := level()
	var h := half()
	it.half = h
	it._mx = 1.0
	it.door_local = Vector3(0, 0, h.y - 0.65)
	var hx := h.x
	var hz := h.y
	match lv:
		0:
			it._shell({"wall": "c9a072", "wall_tex": "vplank", "floor": "a87c50", "floor_tex": "plank", "trim": "5a3a24", "posts": true})
			it._window(-0.2, 1.1, "5a3a24", "c89078")
		1:
			it._shell({"wall": "e8dcc0", "floor": "b08458", "floor_tex": "plank", "wainscot": "8a5a3a", "trim": "5a3a24"})
			it._window(0.6, 1.5, "5a3a24", "a8584a")
		2:
			it._shell({"wall": "c87858", "wall_tex": "brick", "floor": "8e8a84", "floor_tex": "tile", "trim": "8a8a8a"})
			it._window(0.2, 1.5, "8a8a8a", "6a8eaa")
			it._window(-0.4, 1.0, "8a8a8a", "", true)
		3:
			it._shell({"wall": "e8dcc4", "floor": "a8a096", "floor_tex": "tile", "wainscot": "c8a040", "trim": "a07820", "floor_base": "8a7a5a"})
			it._window(-1.8, 1.6, "a07820", "b8321f")
			it._window(1.8, 1.6, "a07820", "b8321f")
			it._window(0.0, 1.2, "a07820", "", true)
			for sx in [-1.0, 1.0]:
				for sz in [-1.0, 1.0]:
					var p := Vector3(sx * (hx - 0.6), 0, sz * (hz - 0.6))
					it._cyl(0.28, 0.32, 2.7, p + Vector3(0, 1.35, 0), "f4f0e4", 14)
					it._box(Vector3(0.75, 0.16, 0.75), p + Vector3(0, 0.08, 0), "c8a040")
					it._box(Vector3(0.75, 0.16, 0.75), p + Vector3(0, 2.64, 0), "c8a040")
					it._collider(Vector3(0.7, 2.7, 0.7), p + Vector3(0, 1.35, 0))
			# a red carpet from the door, a chandelier
			it._box(Vector3(1.4, 0.02, hz * 1.2), Vector3(0, 0.015, hz * 0.35), "b8321f")
			it._box(Vector3(1.2, 0.025, hz * 1.2 - 0.1), Vector3(0, 0.018, hz * 0.35), "c8402e")
			it._cyl(0.34, 0.14, 0.16, Vector3(0, 2.5, -0.4), "e8c860", 12)
			for k in 6:
				var a := k * TAU / 6.0
				it._ball(0.05, Vector3(cos(a) * 0.3, 2.38, sin(a) * 0.3 - 0.4), "e8f4ff")
	# the fixed furniture: bed, lemari, desk (+ safe), the franchise poster
	var bed := _bed_local()
	it.bed_local = bed
	it.bed_side = Vector3(-1.2, 0, 0.6) if lv >= 1 else Vector3(-1.05, 0, 0.55)
	it._bed(bed, ["9a7048", "7a4a30", "6a4a3a", "c8a040"][lv], ["6a8eaa", "5a7fa0", "7a9258", "b8321f"][lv], lv >= 1)
	it.cupboard_local = _cup_local()
	it._lemari(it.cupboard_local, ["9a7048", "7a4a30", "6a4a3a", "f4ecd8"][lv], 1.0 if lv == 0 else 1.2)
	it._desk(_desk_local())
	if lv >= 1:
		it._safe(Vector3(-hx + 0.45, 0, 0.1))
	it._box(Vector3(0.04, 1.2, 0.9), Vector3(-hx + 0.03, 1.65, -1.0 if lv == 0 else -1.4), "e0b04a")
	it._box(Vector3(0.05, 1.1, 0.8), Vector3(-hx + 0.04, 1.65, -1.0 if lv == 0 else -1.4), "c0392b")
	it._label("SAWIT\nTHE FRANCHISE™", Vector3(-hx + 0.08, 1.75, -1.0 if lv == 0 else -1.4), 26, Color("fdf3dc"), "+x")
	it._label(["JURAGAN PEMULA", "JURAGAN MADYA", "JURAGAN UTAMA", "SULTAN SAWIT"][lv], Vector3(-hx + 0.08, 1.35, -1.0 if lv == 0 else -1.4), 18, Color("f4d35e"), "+x")
	it._box(Vector3(0.9, 0.5, 0.04), Vector3(bed.x - (0.2 if lv == 0 else 0.0), 2.1, -hz + 0.03), "e0b04a")
	it._box(Vector3(0.8, 0.4, 0.045), Vector3(bed.x - (0.2 if lv == 0 else 0.0), 2.1, -hz + 0.035), "fdf3dc")
	it._label(["SURAT KONTRAK\nPEWARALABA", "SERTIFIKAT\nPENGUSAHA TELADAN", "PIAGAM\nJURAGAN BERPRESTASI", "GELAR KEHORMATAN\nSULTAN SAWIT"][lv],
		Vector3(bed.x - (0.2 if lv == 0 else 0.0), 2.1, -hz + 0.045), 13, Color("5a3a24"))
	if lv == 3:
		# a giant portrait of you over the desk
		var dk := _desk_local()
		it._box(Vector3(1.5, 1.2, 0.06), Vector3(dk.x, 1.95, -hz + 0.04), "c8a040")
		it._box(Vector3(1.3, 1.0, 0.065), Vector3(dk.x, 1.95, -hz + 0.045), "6a8eaa")
		it._ball(0.2, Vector3(dk.x, 2.08, -hz + 0.09), "f2b98a", 1.2)
		it._box(Vector3(0.6, 0.38, 0.03), Vector3(dk.x, 1.68, -hz + 0.08), "3a5a3a")
		it._box(Vector3(0.62, 0.08, 0.04), Vector3(dk.x, 2.32, -hz + 0.09), "d8a95c")
		it._label("SANG JURAGAN", Vector3(dk.x, 1.48, -hz + 0.08), 14, Color("fdf3dc"))
	if lv == 0:
		it._label("Rumah Mungil (DP 0%)", Vector3(0.9, 2.35, -hz + 0.02), 18, Color("5a3a24"))
	# the decor stand by the door (catalog on a little lectern)
	var sp := Vector3(-hx + 0.9, 0, hz - 0.9)
	it._box(Vector3(0.5, 0.9, 0.4), sp + Vector3(0, 0.45, -0.35), "7a5a3a")
	it._box(Vector3(0.6, 0.05, 0.45), sp + Vector3(0, 0.92, -0.35), "e8b030", false, Vector3(-0.35, 0, 0))
	it._label("KATALOG", sp + Vector3(0, 1.15, -0.3), 18, Color("7a3a12"))
	it._lamp.position = Vector3(0, 2.2, -0.3)
	it._lamp.omni_range = maxf(hx, hz) * 1.6
	# placed furniture
	_fish.clear()
	_fans.clear()
	var placed: Array = hs()["placed"]
	for k in placed.size():
		var p: Dictionary = placed[k]
		if int(p["c"]) < 0:
			continue
		var fp := footprint(p)
		var n := Node3D.new()
		n.name = "Furn_%d_%s" % [k, p["id"]]
		n.position = cell_center(int(p["c"]), int(p["r"]), fp.x, fp.y)
		n.rotation.y = -int(p.get("rot", 0)) * PI * 0.5
		it._room.add_child(n)
		build_item(str(p["id"]), n)
		if not FURN[str(p["id"])].get("flat", false):
			var body := StaticBody3D.new()
			var cs := CollisionShape3D.new()
			var bs := BoxShape3D.new()
			bs.size = Vector3(fp.x * CELL - 0.15, 1.2, fp.y * CELL - 0.15)
			cs.shape = bs
			cs.position.y = 0.6
			body.add_child(cs)
			body.position = n.position
			it._room.add_child(body)
	return true


func is_walkable_local(lx: float, lz: float) -> bool:
	var h := half()
	return absf(lx) < h.x - 0.25 and lz > -h.y + 0.25 and lz < h.y - 0.2


# ------------------------------------------------------------------ furniture models
func build_item(id: String, n: Node3D) -> void:
	var f: Dictionary = FURN[id]
	var W := int(f["w"]) * CELL
	var D := int(f["d"]) * CELL
	match id:
		"kursi_rotan":
			hub.box(n, Vector3(0.6, 0.12, 0.6), Vector3(0, 0.42, 0), "c89a5a")
			hub.box(n, Vector3(0.6, 0.6, 0.1), Vector3(0, 0.75, -0.26), "b8884a", Vector3(-0.15, 0, 0))
			for sx in [-1.0, 1.0]:
				hub.box(n, Vector3(0.08, 0.36, 0.56), Vector3(sx * 0.28, 0.58, 0), "a8783a")
				for sz in [-1.0, 1.0]:
					hub.cyl(n, 0.03, 0.4, Vector3(sx * 0.24, 0.2, sz * 0.24), "8a6030", 6)
			hub.box(n, Vector3(0.5, 0.1, 0.5), Vector3(0, 0.5, 0.02), "d9402a")
		"meja_tamu":
			hub.box(n, Vector3(W - 0.3, 0.07, D - 0.25), Vector3(0, 0.45, 0), "7a4a30")
			for sx in [-1.0, 1.0]:
				for sz in [-1.0, 1.0]:
					hub.box(n, Vector3(0.07, 0.42, 0.07), Vector3(sx * (W * 0.5 - 0.22), 0.21, sz * (D * 0.5 - 0.2)), "5a3a24")
			hub.cyl(n, 0.1, 0.18, Vector3(-0.25, 0.58, 0), "d8eef4", 10)
			hub.cyl(n, 0.11, 0.04, Vector3(-0.25, 0.69, 0), "d9402a", 10)
			hub.cyl(n, 0.12, 0.05, Vector3(0.3, 0.51, 0.05), "fffaf0", 12)
		"sofa":
			hub.box(n, Vector3(W - 0.1, 0.42, D - 0.1), Vector3(0, 0.21, 0), "5a3a24")
			hub.box(n, Vector3(W - 0.1, 0.62, 0.2), Vector3(0, 0.62, -D * 0.5 + 0.15), "8a4a3a")
			for sx in [-1.0, 1.0]:
				hub.box(n, Vector3(0.2, 0.55, D - 0.1), Vector3(sx * (W * 0.5 - 0.15), 0.45, 0), "8a4a3a")
			for k in 3:
				hub.box(n, Vector3(W / 3.0 - 0.15, 0.16, D - 0.35), Vector3(-W / 3.0 + k * W / 3.0, 0.5, 0.05), "a0584a")
			# still in its shop plastic ("biar awet")
			var wrap: MeshInstance3D = hub.box(n, Vector3(W - 0.05, 0.74, D - 0.05), Vector3(0, 0.5, 0), "e8f4f8", Vector3.ZERO, false)
			var pm := StandardMaterial3D.new()
			pm.albedo_color = Color(0.92, 0.97, 1.0, 0.22)
			pm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			pm.roughness = 0.15
			pm.metallic_specular = 0.9
			wrap.material_override = pm
			wrap.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		"tv":
			hub.box(n, Vector3(W - 0.2, 0.55, D - 0.3), Vector3(0, 0.275, 0), "6a4a30")
			hub.box(n, Vector3(0.8, 0.6, 0.5), Vector3(0, 0.88, -0.02), "3a3a42")
			var scr: MeshInstance3D = hub.box(n, Vector3(0.64, 0.46, 0.02), Vector3(0, 0.9, 0.24), "5a8ab8")
			scr.set_meta("screen", true)
			for s in [-1.0, 1.0]:
				hub.cyl(n, 0.008, 0.5, Vector3(s * 0.12, 1.38, -0.05), "c0c0c8", 4, Vector3(0, 0, s * 0.5))
		"kulkas":
			hub.box(n, Vector3(0.66, 1.7, 0.6), Vector3(0, 0.85, 0), "e8e8e0")
			hub.box(n, Vector3(0.02, 1.6, 0.02), Vector3(0, 0.85, 0.31), "9a9aa0")
			for s in [-1.0, 1.0]:
				hub.box(n, Vector3(0.03, 0.3, 0.04), Vector3(s * 0.06, 1.0, 0.32), "9a9aa0")
			hub.box(n, Vector3(0.12, 0.12, 0.02), Vector3(0.18, 1.3, 0.31), "d9402a")
		"akuarium":
			_aquarium(n, W, D)
		"monstera":
			hub.cyl(n, 0.2, 0.36, Vector3(0, 0.18, 0), "e8e0d0", 10, Vector3.ZERO, 0.24)
			for k in 7:
				var leaf: MeshInstance3D = hub.box(n, Vector3(0.3, 0.02, 0.42), Vector3(0, 0.62 + (k % 3) * 0.14, 0), "3f7a3a")
				leaf.rotation = Vector3(0.5 + (k % 2) * 0.3, k * TAU / 7.0, 0)
				leaf.position += Vector3(sin(k * TAU / 7.0), 0, cos(k * TAU / 7.0)) * 0.16
		"karpet":
			hub.box(n, Vector3(W - 0.1, 0.02, D - 0.1), Vector3(0, 0.012, 0), "f0dcb0", Vector3.ZERO, false)
			hub.box(n, Vector3(W - 0.35, 0.026, D - 0.35), Vector3(0, 0.016, 0), "8a2a2a", Vector3.ZERO, false)
			hub.box(n, Vector3(W - 1.0, 0.03, D - 0.9), Vector3(0, 0.02, 0), "c8a040", Vector3.ZERO, false)
			hub.box(n, Vector3(0.4, 0.034, 0.4), Vector3(0, 0.024, 0), "2a4a7a", Vector3(0, PI * 0.25, 0), false)
		"rak_buku":
			hub.box(n, Vector3(W - 0.2, 1.8, D - 0.4), Vector3(0, 0.9, -0.1), "7a4a30")
			var cols := ["d9402a", "3a74c0", "e8b030", "2f9a5a", "8e5a7a", "fffaf0"]
			for row in 4:
				hub.box(n, Vector3(W - 0.26, 0.04, D - 0.44), Vector3(0, 0.12 + row * 0.44, -0.08), "5a3a24")
				for k in 7:
					hub.box(n, Vector3(0.1, 0.32, 0.26), Vector3(-W * 0.5 + 0.3 + k * 0.15, 0.3 + row * 0.44, -0.06), cols[(k + row) % cols.size()])
		"kipas":
			hub.cyl(n, 0.22, 0.05, Vector3(0, 0.03, 0), "3a3a42", 12)
			hub.cyl(n, 0.025, 1.1, Vector3(0, 0.6, 0), "c0c0c8", 6)
			var head := Node3D.new()
			head.name = "FanHead"
			head.position = Vector3(0, 1.2, 0.05)
			n.add_child(head)
			for k in 3:
				var bl: MeshInstance3D = hub.box(head, Vector3(0.1, 0.26, 0.02), Vector3(0, 0, 0.08), "5a8ab8")
				bl.rotation.z = k * TAU / 3.0
				bl.position = Basis(Vector3.BACK, k * TAU / 3.0) * Vector3(0, 0.13, 0) + Vector3(0, 0, 0.08)
			_fans.append(head)
		"lampu_hias":
			hub.cyl(n, 0.18, 0.05, Vector3(0, 0.03, 0), "6a4a2a", 10)
			hub.cyl(n, 0.025, 1.4, Vector3(0, 0.72, 0), "c8a040", 6)
			hub.cyl(n, 0.28, 0.32, Vector3(0, 1.5, 0), "f4e2b8", 12, Vector3.ZERO, 0.16)
		"karaoke":
			hub.box(n, Vector3(0.5, 0.9, 0.45), Vector3(0, 0.45, 0), "2a2a30")
			for k in 2:
				hub.cyl(n, 0.14 - k * 0.04, 0.03, Vector3(0, 0.62 - k * 0.32, 0.23), "6a6a72", 12, Vector3(PI * 0.5, 0, 0))
			hub.cyl(n, 0.02, 1.2, Vector3(0.32, 0.6, 0.1), "8a8a90", 6)
			hub.cyl(n, 0.05, 0.16, Vector3(0.32, 1.25, 0.1), "3a3a3a", 8)
		"foto_juragan":
			for s in [-1.0, 1.0]:
				hub.box(n, Vector3(0.06, 1.5, 0.06), Vector3(s * 0.45, 0.75, 0.1), "5a3a24", Vector3(-0.12, 0, 0))
			hub.box(n, Vector3(1.2, 1.0, 0.06), Vector3(0, 1.25, -0.02), "c8a040", Vector3(-0.12, 0, 0))
			hub.box(n, Vector3(1.0, 0.8, 0.07), Vector3(0, 1.25, 0.0), "8fbf7a", Vector3(-0.12, 0, 0))
			hub.cyl(n, 0.13, 0.05, Vector3(0, 1.42, 0.06), "f2b98a", 10, Vector3(PI * 0.5 - 0.12, 0, 0))
			hub.box(n, Vector3(0.36, 0.3, 0.04), Vector3(0, 1.12, 0.05), "e8e0d0", Vector3(-0.12, 0, 0))
			hub.box(n, Vector3(0.5, 0.05, 0.04), Vector3(0, 1.58, 0.07), "d8a95c", Vector3(-0.12, 0, 0))
		"patung_singa":
			hub.box(n, Vector3(0.6, 0.4, 0.6), Vector3(0, 0.2, 0), "f4f0e4")
			hub.box(n, Vector3(0.3, 0.45, 0.5), Vector3(0, 0.62, -0.02), "e0b030")
			hub.cyl(n, 0.2, 0.2, Vector3(0, 1.0, 0.1), "e0b030", 10, Vector3(PI * 0.5, 0, 0))
			hub.cyl(n, 0.12, 0.18, Vector3(0, 1.0, 0.25), "f0c840", 10, Vector3(PI * 0.5, 0, 0))
			hub.box(n, Vector3(0.1, 0.06, 0.05), Vector3(0, 0.95, 0.35), "3a2a1a")
		"meja_billiar":
			hub.box(n, Vector3(W - 0.3, 0.18, D - 0.3), Vector3(0, 0.78, 0), "6a3a20")
			hub.box(n, Vector3(W - 0.5, 0.05, D - 0.5), Vector3(0, 0.88, 0), "2f7a4a")
			for sx in [-1.0, 1.0]:
				for sz in [-1.0, 1.0]:
					hub.box(n, Vector3(0.14, 0.7, 0.14), Vector3(sx * (W * 0.5 - 0.3), 0.35, sz * (D * 0.5 - 0.3)), "5a3020")
			var bc := ["d9402a", "e8b030", "3a74c0", "fffaf0", "2a2a2a"]
			for k in 5:
				hub.cyl(n, 0.05, 0.1, Vector3(-0.4 + k * 0.2, 0.95, (k % 2) * 0.15), bc[k], 8)
			hub.cyl(n, 0.015, 1.4, Vector3(0.1, 0.95, -0.3), "c8a060", 6, Vector3(0, 0, PI * 0.5))
		"dispenser":
			hub.box(n, Vector3(0.36, 0.95, 0.36), Vector3(0, 0.475, 0), "e8e8e0")
			hub.cyl(n, 0.16, 0.4, Vector3(0, 1.15, 0), "9ad0f0", 12)
			hub.box(n, Vector3(0.05, 0.05, 0.06), Vector3(-0.07, 0.75, 0.2), "d9402a")
			hub.box(n, Vector3(0.05, 0.05, 0.06), Vector3(0.07, 0.75, 0.2), "3a74c0")


func _aquarium(n: Node3D, W: float, D: float) -> void:
	hub.box(n, Vector3(W - 0.15, 0.7, D - 0.25), Vector3(0, 0.35, 0), "6a4a30")
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.55, 0.85, 0.95, 0.35)
	gm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	gm.roughness = 0.1
	var glass := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(W - 0.2, 0.75, D - 0.3)
	glass.mesh = bm
	glass.material_override = gm
	glass.position = Vector3(0, 1.08, 0)
	glass.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	n.add_child(glass)
	hub.box(n, Vector3(W - 0.22, 0.08, D - 0.32), Vector3(0, 0.75, 0), "e8d8a8")
	# an open rim on top (a lid would hide the fish from the play camera)
	for sz in [-1.0, 1.0]:
		hub.box(n, Vector3(W - 0.16, 0.05, 0.05), Vector3(0, 1.47, sz * (D - 0.3) * 0.5), "3a3a42")
	for sx in [-1.0, 1.0]:
		hub.box(n, Vector3(0.05, 0.05, D - 0.26), Vector3(sx * (W - 0.2) * 0.5, 1.47, 0), "3a3a42")
	for k in 3:
		var plant: MeshInstance3D = hub.box(n, Vector3(0.05, 0.35 + k * 0.08, 0.02), Vector3(-W * 0.35 + k * 0.12, 0.95, -0.1), "4a9a4a")
		plant.rotation.z = (k - 1) * 0.2
	# the rare fish you caught swim in it (icons as little sprites)
	var ids: Array = []
	for id in GS.fish_ids_sorted():
		if int(GS.fish_log.get(id, 0)) > 0 and GS.fish_rarity(id) in ["SR", "SSR"]:
			ids.append(id)
	if ids.is_empty():
		var l: Label3D = hub.label3d(n, "(kosong: tangkap ikan SR / SSR!)", Vector3(0, 1.1, D * 0.5 - 0.12), 18, Color("2f5a8a"))
		l.pixel_size = 0.004
		return
	for k in mini(ids.size(), 6):
		var sp := Sprite3D.new()
		sp.texture = load("res://assets/icons/%s.png" % ids[k])
		sp.pixel_size = 0.0028 if GS.fish_rarity(ids[k]) == "SR" else 0.0034
		sp.shaded = false
		sp.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
		sp.rotation.x = -0.5   # leaning back towards the high play camera
		sp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var base := Vector3(0, 0.95 + (k % 3) * 0.17, -0.05 + (k % 2) * 0.1)
		sp.position = base
		sp.set_meta("fish_id", ids[k])
		n.add_child(sp)
		_fish.append([sp, base, k * 1.7, (W - 0.5) * 0.5])


func _process(delta: float) -> void:
	if hub.world.inside != "rumah_juragan":
		return
	_t += delta
	for f in _fish:
		var sp: Sprite3D = f[0]
		if not is_instance_valid(sp):
			continue
		var ph: float = _t * 0.6 + f[2]
		var x := sin(ph) * float(f[3])
		sp.position = f[1] + Vector3(x, sin(ph * 2.3) * 0.04, 0)
		sp.flip_h = cos(ph) < 0.0
	for head in _fans:
		if is_instance_valid(head):
			head.rotation.z += delta * 14.0


func aquarium_fish() -> Array:
	var out: Array = []
	for f in _fish:
		if is_instance_valid(f[0]):
			out.append(f[0].get_meta("fish_id"))
	return out


# ------------------------------------------------------------------ shop & editor UI
func toko_items(items: Array) -> void:
	items.append({"icon": "icon_sofa", "text": "Katalog Mebel & Dekorasi", "desc": "%d barang untuk rumahmu (%s). Dikirim langsung & dipasang." % [FURN.size(), level_name()],
		"button": "Lihat", "cb": func():
			hub.ui.close()
			show_catalog()})
	if level() < LEVELS.size() - 1:
		var nxt: Dictionary = LEVELS[level() + 1]
		items.append({"icon": "icon_renovasi", "text": "Jasa renovasi Kang Asep: %s" % nxt["name"], "desc": str(nxt["desc"]),
			"price": GS.fmt_short(int(nxt["cost"])), "enabled": GS.money >= int(nxt["cost"]), "cb": func():
				if upgrade():
					hub.ui.refresh_menu(hub.deals.open_toko)})


func show_catalog() -> void:
	var ui: Node = hub.ui
	var items: Array = []
	for id in FURN:
		var f: Dictionary = FURN[id]
		var need := int(f.get("lvl", 0))
		var lock := level() + 1 < need
		var own := 0
		for p in hs()["placed"]:
			if str(p["id"]) == id:
				own += 1
		own += int(hs()["own"].get(id, 0))
		var fid: String = id
		items.append({"icon": str(f["icon"]), "text": str(f["name"]) + (" (punya %d)" % own if own > 0 else ""),
			"desc": ("Butuh %s. " % level_name(need - 1) if lock else "") + str(f["desc"]) + " Ukuran %dx%d petak." % [int(f["w"]), int(f["d"])],
			"price": GS.fmt_short(int(f["price"])), "enabled": not lock and GS.money >= int(f["price"]),
			"cb": func():
				buy(fid)
				ui.refresh_menu(show_catalog)})
	ui.menu("Katalog Mebel Koperasi", "Rumahmu: %s • Atur posisinya di dalam rumah (KATALOG dekat pintu)." % level_name(), items, Callable(), "portrait_petani")


func show_editor() -> void:
	var ui: Node = hub.ui
	var vp: Vector2 = ui.root.get_viewport_rect().size
	var panel := PanelContainer.new()
	panel.name = "DecorEditor"
	panel.set_meta("closable", true)
	panel.set_meta("decor", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	var title: Label = ui._title_label("Atur Rumah: " + level_name(), ui.TITLE_BROWN, 28)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_child(ui._hrow([ui._icon_rect("icon_renovasi", 40), title], 10))
	col.add_child(ui._divider())
	var body: BoxContainer = HBoxContainer.new() if vp.x >= vp.y else VBoxContainer.new()
	body.add_theme_constant_override("separation", 14)
	col.add_child(body)
	var g := grid_size()
	var cpx := clampf(minf((vp.x - 420.0) / g.x, (vp.y - 330.0) / g.y), 18.0, 34.0)
	if vp.x < vp.y:
		cpx = clampf((vp.x - 90.0) / g.x, 16.0, 30.0)
	var gv := GridView.new()
	gv.name = "Grid"
	gv.decor = self
	gv.cpx = cpx
	gv.custom_minimum_size = Vector2(g.x * cpx, g.y * cpx)
	body.add_child(gv)
	var side := VBoxContainer.new()
	side.add_theme_constant_override("separation", 6)
	side.custom_minimum_size = Vector2(260, 0)
	body.add_child(side)
	var placed: Array = hs()["placed"]
	if sel >= placed.size():
		sel = -1
	if sel >= 0:
		var p: Dictionary = placed[sel]
		side.add_child(ui._label("Dipilih: " + str(FURN[str(p["id"])]["name"]), 18, ui.BROWN, true))
		var arrows := GridContainer.new()
		arrows.columns = 3
		arrows.add_theme_constant_override("h_separation", 4)
		arrows.add_theme_constant_override("v_separation", 4)
		for cell in [["", 0, 0], ["Atas", 0, -1], ["", 0, 0], ["Kiri", -1, 0], ["Putar", 9, 9], ["Kanan", 1, 0], ["", 0, 0], ["Bawah", 0, 1], ["", 0, 0]]:
			if cell[0] == "":
				var sp := Control.new()
				sp.custom_minimum_size = Vector2(70, 40)
				arrows.add_child(sp)
				continue
			var dc: int = cell[1]
			var dr: int = cell[2]
			var b: Button = ui.button(cell[0], func():
				if dc == 9:
					if not rotate(sel):
						ui.toast("Tidak muat kalau diputar.", "bad")
				elif not move(sel, dc, dr):
					ui.toast("Tidak bisa digeser ke sana.", "bad")
				_reopen(), true, 70)
			b.add_theme_font_size_override("font_size", 16)
			arrows.add_child(b)
		side.add_child(arrows)
		side.add_child(ui.button("Simpan ke gudang", func():
			store(sel)
			_reopen(), true, 220))
	else:
		var hint: Label = ui._label("Ketuk perabot di denah untuk memilih, lalu ketuk petak kosong untuk memindahkan. Petak gelap: kasur, lemari, meja, pintu.", 15, ui.BROWN_SOFT)
		hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		hint.custom_minimum_size = Vector2(250, 0)
		side.add_child(hint)
	var own: Dictionary = hs()["own"]
	if not own.is_empty():
		side.add_child(ui._label("Gudang:", 16, ui.BROWN_SOFT, true))
		for id in own:
			var fid: String = id
			side.add_child(ui.button("Pasang %s (%d)" % [FURN[id]["name"], int(own[id])], func():
				place_from_store(fid)
				_reopen(), true, 240))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	row.add_child(ui.button("Katalog", func():
		ui.close()
		show_catalog(), true, 140))
	if level() < LEVELS.size() - 1:
		var nxt: Dictionary = LEVELS[level() + 1]
		row.add_child(ui.button("Renovasi: %s (%s)" % [nxt["name"], GS.fmt_short(int(nxt["cost"]))], func():
			if upgrade():
				_reopen(), GS.money >= int(nxt["cost"]), 200, true))
	row.add_child(ui.button("Tutup", ui.close, true, 120))
	col.add_child(row)
	ui._open_modal(panel, true)


func _reopen() -> void:
	var ui: Node = hub.ui
	if ui.modal and ui.modal.has_meta("decor"):
		ui._on_modal_close = Callable()
	show_editor()


func click_cell(c: int, r: int) -> void:
	var bl := blocked_cells()
	var o = bl.get(Vector2i(c, r))
	if typeof(o) == TYPE_INT:
		# prefer a non-rug item when a rug is under it
		var placed: Array = hs()["placed"]
		for k in placed.size():
			var fp := footprint(placed[k])
			if c >= int(placed[k]["c"]) and c < int(placed[k]["c"]) + fp.x and r >= int(placed[k]["r"]) and r < int(placed[k]["r"]) + fp.y \
					and not FURN[str(placed[k]["id"])].get("flat", false):
				o = k
		sel = o
	elif sel >= 0 and o == null:
		if not move_to(sel, c, r):
			hub.ui.toast("Tidak muat di sana.", "bad")
	_reopen()


class GridView extends Control:
	## top view of the room: grey = fixed furniture, coloured blocks = your furniture
	var decor: Node
	var cpx := 28.0

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP

	func _gui_input(e: InputEvent) -> void:
		var pos := Vector2(-1, -1)
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			pos = e.position
		elif e is InputEventScreenTouch and e.pressed:
			pos = e.position
		if pos.x >= 0.0:
			accept_event()
			decor.click_cell(int(pos.x / cpx), int(pos.y / cpx))

	func _draw() -> void:
		var g: Vector2i = decor.grid_size()
		var bl: Dictionary = decor.blocked_cells()
		draw_rect(Rect2(Vector2.ZERO, size), Color("e8d8b8"))
		for c in g.x:
			for r in g.y:
				var rc := Rect2(c * cpx + 1, r * cpx + 1, cpx - 2, cpx - 2)
				var o = bl.get(Vector2i(c, r))
				if typeof(o) == TYPE_STRING:
					draw_rect(rc, Color("8a7a66"))
				else:
					draw_rect(rc, Color("f6ecd6"))
		var placed: Array = decor.hs()["placed"]
		var font: Font = ThemeDB.fallback_font
		for flat_pass in [true, false]:
			for k in placed.size():
				var p: Dictionary = placed[k]
				var is_flat: bool = decor.FURN[str(p["id"])].get("flat", false)
				if is_flat != flat_pass:
					continue
				var fp: Vector2i = decor.footprint(p)
				var rc := Rect2(int(p["c"]) * cpx + 3, int(p["r"]) * cpx + 3, fp.x * cpx - 6, fp.y * cpx - 6)
				var col := Color.from_hsv(fmod(hash(str(p["id"])) / 1000.0, 1.0), 0.45, 0.85)
				if is_flat:
					col = Color(0.65, 0.25, 0.25, 0.55)
				draw_rect(rc, col)
				draw_rect(rc, Color("4a2f1d") if k != decor.sel else Color("e8953a"), false, 3.0 if k == decor.sel else 1.5)
				var nm := str(decor.FURN[str(p["id"])]["name"]).substr(0, int(rc.size.x / 8.0))
				draw_string(font, rc.position + Vector2(3, 13), nm, HORIZONTAL_ALIGNMENT_LEFT, rc.size.x - 4, 11, Color("2a1a10"))
		# the door
		var dx: float = g.x * cpx * 0.5
		draw_rect(Rect2(dx - cpx, size.y - 5, cpx * 2, 5), Color("6a3a18"))
