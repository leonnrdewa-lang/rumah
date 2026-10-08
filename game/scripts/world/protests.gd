extends Node
## Demonstrations and the LSM lingkungan.
## Villagers you seized or cheated (and who no longer like you) gather in front of the
## Kantor with cardboard signs and a banner and chant. Meet them: negotiate (works when
## they still half-like you), pay ganti rugi, call Bang Codet's preman (risky: a video
## can go viral) or ignore them (Kecurigaan and reputation suffer overnight).
## The LSM (Mbak Laras, LSM Hijau Lestari) comes when the forest goes: banners at the
## Kantor and the Pabrik and a petition that adds Kecurigaan every day until addressed.

var hub: Node
var crowd: Array = []        # extra demonstrators (temp NPCs)
var signs: Array = []        # sign nodes on villager NPCs
var banners: Array = []
var lsm_npc: Npc
var lsm_banners: Array = []
var _spot := {}
var _chant_t := 6.0

const CHANTS := ["Ta-nah! Ka-mi! Bu-kan! Fran-chise!", "Kembalikan kebun kami! Kembalikan!", "Minyak mahal, kebun hilang, juragan senang!",
	"Hidup warga! Hidup warga! Turunkan harga minyak!", "Sawit boleh, tipu jangan!", "Juragan keluar! Juragan keluar! (Dia sedang di dalam, kok.)"]
const SIGNS := ["KEMBALIKAN KEBUN KAMI!", "TANAH KAMI BUKAN FRANCHISE", "MINYAK MAHAL, KEBUN HILANG", "#SAVE SUKAMAKMUR",
	"STOP SURAT PALSU!", "PREMAN PULANG!", "KAMI BUKAN BURUH DI TANAH SENDIRI", "BUNGA 5%/HARI = RIBA!"]
const CROWD_MODELS := ["char_petani", "char_ibu", "char_pemuda", "char_buruh", "char_nenek", "char_kakek"]
const LSM_NAME := "Mbak Laras (LSM Hijau Lestari)"


func ps() -> Dictionary:
	return hub.st("prot", {"active": false, "day": 0, "who": [], "count": 0, "nego": 0, "comp": 0, "preman": 0, "ignored": 0, "last": -9})


func ls() -> Dictionary:
	return hub.st("lsm", {"active": false, "day": 0, "sign": 0, "count": 0, "done": 0, "last": -9, "sued": 0})


func active() -> bool:
	return bool(ps()["active"])


func lsm_active() -> bool:
	return bool(ls()["active"])


func grievers() -> Array:
	## villagers angry enough to march: wronged (or landless) and at most 2 hearts
	var out: Array = []
	for vid in GS.VILLAGERS:
		var r: Dictionary = hub.rel.rec(vid)
		if (int(r["wronged"]) > 0 or GS.villagers[vid]["status"] == "landless") and hub.rel.hearts(vid) <= 2:
			out.append(vid)
	return out


# ------------------------------------------------------------------ day roll
func day_roll(report: Array) -> void:
	var p := ps()
	if active():
		# ignored all day: they go home angrier, and tell everyone
		p["active"] = false
		p["ignored"] = int(p["ignored"]) + 1
		GS.heat = clampf(GS.heat + 8.0, 0.0, 100.0)
		GS.rep = clampf(GS.rep - 6.0, -100.0, 100.0)
		report.append("Demo kemarin tidak kamu tanggapi. Videonya beredar di grup WhatsApp desa (Kecurigaan +8, Reputasi -6).")
	var idx: int = GS.pending_events.find("demo")
	var g := grievers()
	var want: bool = g.size() >= 2 and GS.day - int(p["last"]) >= 3 and (GS.rep <= -15.0 or hub.rng.randf() < 0.35)
	if idx >= 0 and g.size() < 1:
		GS.pending_events.remove_at(idx)
	elif idx < 0 and want:
		GS.pending_events.append("demo")
	# the LSM campaign
	var l := ls()
	if lsm_active():
		var add: int = hub.rng.randi_range(300, 1500)
		l["sign"] = int(l["sign"]) + add
		var h := clampf(4.0 + float(l["sign"]) / 2500.0, 4.0, 10.0)
		GS.heat = clampf(GS.heat + h, 0.0, 100.0)
		report.append("[LSM] Petisi 'Selamatkan Hutan Sukamakmur' kini %s tanda tangan (+%d). Kecurigaan +%d." % [_num(int(l["sign"])), add, int(h)])
	elif GS.day - int(l["last"]) >= 5 and GS.day >= 4 and _forest_gone() and hub.rng.randf() < 0.45 and not "lsm" in GS.pending_events:
		GS.pending_events.append("lsm")


func _forest_gone() -> bool:
	return GS.palm_count() >= 30 or int(GS.stats["cleared"]) >= 25 or int(GS.stats["land_seized"]) + int(GS.stats["land_fraud"]) >= 2


static func _num(n: int) -> String:
	return GS.fmt_rp(n).trim_prefix("Rp ")


# ------------------------------------------------------------------ visuals
func refresh() -> void:
	_clear_protest()
	_clear_lsm()
	if active():
		_build_protest()
	if lsm_active():
		_build_lsm()


func _kantor() -> Vector3:
	return hub.world.door_points.get("kantor", Vector3(-3, 0, 33))


func _clear_protest() -> void:
	for n in crowd:
		hub.despawn(n)
	crowd.clear()
	for sg in signs:
		if is_instance_valid(sg):
			sg.queue_free()
	signs.clear()
	for b in banners:
		if is_instance_valid(b):
			b.queue_free()
	banners.clear()
	hub.remove_spot(_spot)
	_spot = {}


func _build_protest() -> void:
	var w: Node = hub.world
	var kd := _kantor()
	var who: Array = ps()["who"]
	var slots: Array = []
	for row in 3:
		for k in 6:
			slots.append(kd + Vector3(-4.0 + k * 1.6 + (0.8 if row % 2 == 1 else 0.0), 0, 3.2 + row * 1.3))
	var si := 0
	for vid in who:
		if not w.npcs.has(vid) or si >= slots.size():
			continue
		var n: Npc = w.npcs[vid]
		n.set_anchor(slots[si], 0.5, true)
		_add_sign(n, SIGNS[(si + GS.day) % SIGNS.size()])
		si += 1
	var extra := clampi(6 - who.size(), 2, 5)
	for k in extra:
		if si >= slots.size():
			break
		var m: String = CROWD_MODELS[k % CROWD_MODELS.size()]
		var n: Npc = hub.spawn_npc(m, "Warga Demo", slots[si], 0.5, "demo%d" % k)
		crowd.append(n)
		_add_sign(n, SIGNS[(si + GS.day) % SIGNS.size()])
		si += 1
	banners.append(_banner(kd + Vector3(-1.0, 0, 7.4), "KEMBALIKAN\nTANAH KAMI!", "b8321f"))
	_spot = hub.add_spot(kd + Vector3(0, 0, 2.2), 2.6, func(): return "Temui pendemo (%d warga)" % (who.size() + crowd.size()),
		func(): meet())


func _add_sign(n: Node3D, text: String) -> void:
	var sg: Node3D = hub.protest_sign(text)
	sg.position = Vector3(0.32, 0.3, 0.05)
	sg.rotation.z = -0.08
	n.add_child(sg)
	signs.append(sg)


func _banner(pos: Vector3, text: String, col: String) -> Node3D:
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLib.merged_mesh("spanduk", true)
	pos.y = hub.world.height_at(pos.x, pos.z)
	mi.position = pos
	hub.world.add_child(mi)
	var l := Label3D.new()
	l.text = text
	l.font = ModelLib.label_font()
	l.font_size = 40
	l.outline_size = 0
	l.modulate = Color(col)
	l.pixel_size = 0.008
	var ab := mi.mesh.get_aabb()
	l.position = Vector3(0, ab.get_center().y + 0.1, ab.end.z + 0.03)
	mi.add_child(l)
	return mi


func _process(delta: float) -> void:
	if not active() or not hub.playing():
		return
	_chant_t -= delta
	if _chant_t > 0.0:
		return
	_chant_t = hub.rng.randf_range(8.0, 13.0)
	if hub.ui.modal != null or not hub.near_player(_kantor(), 32.0):
		return
	hub.ui.toast("Pendemo: \"%s\"" % CHANTS[hub.rng.randi() % CHANTS.size()], "bad")
	var all: Array = crowd.duplicate()
	for vid in ps()["who"]:
		if hub.world.npcs.has(vid):
			all.append(hub.world.npcs[vid])
	for k in mini(3, all.size()):
		var n: Npc = all[hub.rng.randi() % all.size()]
		if is_instance_valid(n):
			n.emote(["TANAH!", "HIDUP!", "TOLAK!", "!!"][hub.rng.randi() % 4], 2.0)


# ------------------------------------------------------------------ the protest
func start_protest() -> void:
	var g := grievers()
	if g.is_empty():
		hub.next_event()
		return
	var p := ps()
	p["active"] = true
	p["day"] = GS.day
	p["last"] = GS.day
	p["who"] = g.slice(0, 8)
	p["count"] = int(p["count"]) + 1
	hub.add_stat("protests")
	refresh()
	var lead: String = p["who"][0]
	hub.ui.dialog(hub.deals.vp(lead), GS.vname(lead), "Juragan! Kami warga yang kebunnya kamu ambil berkumpul di depan kantormu. %d orang, lengkap dengan spanduk. Kami tidak akan pulang sebelum ada jawaban!" % (p["who"].size() + crowd.size()),
		_choices(true))


func meet() -> void:
	if not active():
		return
	var lead: String = ps()["who"][0] if not ps()["who"].is_empty() else "pemuda"
	hub.ui.dialog(hub.deals.vp(lead), GS.vname(lead), "Akhirnya Juragan keluar juga. Jadi, bagaimana nasib kami?", _choices(false))


func comp_cost() -> int:
	return 750000 * maxi(1, ps()["who"].size())


func _choices(morning: bool) -> Array:
	var after := func():
		if morning:
			hub.next_event()
	var cost := comp_cost()
	return [
		{"text": "Negosiasi baik-baik", "hint": "peluang %d%%" % int(nego_chance() * 100.0), "cb": func():
			negotiate()
			after.call()},
		{"text": "Bayar ganti rugi", "hint": GS.fmt_short(cost), "enabled": GS.money >= cost, "cb": func():
			compensate()
			after.call()},
		{"text": "Panggil preman membubarkan", "hint": "berisiko", "cb": func():
			preman()
			after.call()},
		{"text": "Abaikan, tutup gorden kantor", "cb": func():
			ignore()
			after.call()},
	]


func nego_chance() -> float:
	var who: Array = ps()["who"]
	var avg := 0.0
	for vid in who:
		avg += hub.rel.f(vid)
	avg = avg / maxf(1.0, who.size())
	return clampf(0.2 + avg / 100.0 + GS.rep / 200.0, 0.05, 0.9)


func negotiate() -> bool:
	if not active():
		return false
	if hub.rng.randf() < nego_chance():
		GS.add_rep(5)
		for vid in ps()["who"]:
			hub.rel.add(vid, 6.0, false)
		var p := ps()
		p["nego"] = int(p["nego"]) + 1
		_end("Negosiasi berhasil! Kamu janji 'akan dikaji'. Warga pulang membawa harapan (dan nasi kotak).", "good")
		return true
	GS.add_heat(5)
	GS.add_rep(-2)
	hub.ui.toast("Negosiasi buntu. 'Janji juragan itu seperti sawit muda: belum berbuah!' Demo berlanjut.", "bad")
	return false


func compensate() -> void:
	if not active():
		return
	var cost := comp_cost()
	if not GS.spend(cost):
		return
	var who: Array = ps()["who"]
	for vid in who:
		GS.villagers[vid]["money"] += 750000
		hub.rel.add(vid, 15.0, false)
		var r: Dictionary = hub.rel.rec(vid)
		r["wronged"] = maxi(0, int(r["wronged"]) - 1)
	GS.add_rep(12)
	hub.add_stat("donated", cost)
	hub.add_stat("tobat_pts")
	var p := ps()
	p["comp"] = int(p["comp"]) + 1
	Sfx.play("cash")
	_end("Ganti rugi dibayar %s. Warga pulang. Ada yang menangis, ada yang langsung beli minyak... darimu." % GS.fmt_short(cost), "good")


func preman() -> bool:
	if not active():
		return false
	var p := ps()
	p["preman"] = int(p["preman"]) + 1
	for vid in p["who"]:
		hub.rel.add(vid, -20.0, false)
	var kd := _kantor()
	hub.world.spawn_temp_actor("char_preman", "Bang Codet", kd + Vector3(2.5, 0, 2.5), 2.0)
	if hub.rng.randf() < 0.6:
		GS.add_heat(15)
		GS.add_rep(-15)
		_end("Bang Codet membubarkan demo dengan 'pendekatan persuasif'. Warga lari. (Kecurigaan +15, Reputasi -15)", "bad")
		return true
	GS.add_heat(30)
	GS.add_rep(-25)
	_end("RICUH! Video Bang Codet mendorong nenek-nenek viral: 2 juta views. (Kecurigaan +30, Reputasi -25)", "bad")
	if not hub.jour.active():
		GS.pending_events.append("jurnalis")
	return false


func ignore() -> void:
	hub.ui.toast("Kamu menutup gorden. Teriakan pendemo tetap terdengar sampai sore...", "info")


func _end(text: String, kind: String) -> void:
	var p := ps()
	p["active"] = false
	var who: Array = p["who"]
	_clear_protest()
	for vid in who:
		hub.world.refresh_villager(vid)
	hub.ui.toast(text, kind)


# ------------------------------------------------------------------ LSM lingkungan
func _clear_lsm() -> void:
	hub.despawn(lsm_npc)
	lsm_npc = null
	for b in lsm_banners:
		if is_instance_valid(b):
			b.queue_free()
	lsm_banners.clear()


func _build_lsm() -> void:
	var w: Node = hub.world
	var at: Vector3 = w.door_points.get("pabrik" if GS.day % 2 == 0 else "kantor", _kantor()) + Vector3(3.2, 0, 2.6)
	at = hub.free_spot_near(at, 0.8, 10.0)
	lsm_npc = hub.spawn_npc("char_ibu", "Mbak Laras (LSM)", at, 2.0, "laras_lsm",
		func(): return "Temui Mbak Laras (LSM)", func(): lsm_talk())
	var sg: Node3D = hub.protest_sign("SELAMATKAN HUTAN!", "e8f4dc", Color("2f6d2a"))
	sg.position = Vector3(0.32, 0.3, 0.05)
	lsm_npc.add_child(sg)
	var pd: Vector3 = w.door_points.get("pabrik", _kantor())
	lsm_banners.append(_banner(pd + Vector3(-3.0, 0, 3.5), "SELAMATKAN HUTAN\nSUKAMAKMUR!", "2f6d2a"))
	lsm_banners.append(_banner(_kantor() + Vector3(3.5, 0, 6.0), "#SawitBukan\nSegalanya", "2f6d2a"))


func lsm_arrive() -> void:
	var l := ls()
	l["active"] = true
	l["day"] = GS.day
	l["last"] = GS.day
	l["count"] = int(l["count"]) + 1
	l["sign"] = hub.rng.randi_range(800, 1600)
	hub.add_stat("lsm")
	refresh()
	hub.ui.dialog("portrait_ibu", LSM_NAME, "Permisi, Juragan. Saya Laras dari LSM Hijau Lestari. Kami memantau hilangnya hutan di Sukamakmur. Spanduk kami sudah terpasang, petisi sudah %s tanda tangan. Kami ingin dialog." % _num(int(l["sign"])),
		_lsm_choices(true))


func lsm_talk() -> void:
	if not lsm_active():
		return
	if lsm_npc:
		lsm_npc.talking = true
		lsm_npc.talk_target = hub.world.player
	hub.ui.dialog("portrait_ibu", LSM_NAME, "Petisi kami sudah %s tanda tangan, Juragan. Kampanye jalan terus sampai ada komitmen nyata." % _num(int(ls()["sign"])),
		_lsm_choices(false))


func _lsm_choices(morning: bool) -> Array:
	var after := func():
		if morning:
			hub.next_event()
	return [
		{"text": "Donasi 'CSR Hijau' (foto bareng)", "hint": GS.fmt_short(2000000), "enabled": GS.money >= 2000000, "cb": func():
			lsm_donate()
			after.call()},
		{"text": "Komitmen: tanam pohon & kebun organik", "hint": "Rp 1 jt + 30 energi", "enabled": GS.money >= 1000000 and GS.energy >= 30.0, "cb": func():
			lsm_commit()
			after.call()},
		{"text": "Laporkan balik pakai pasal karet", "hint": "berisiko", "cb": func():
			lsm_sue()
			after.call()},
		{"text": "Abaikan", "hint": "kampanye lanjut", "cb": func():
			hub.ui.toast("Mbak Laras mengangguk dan membuka live streaming. Penontonnya bertambah...", "bad")
			after.call()},
	]


func lsm_donate() -> void:
	if not GS.spend(2000000):
		return
	GS.add_rep(8)
	GS.add_heat(-5)
	hub.add_stat("donated", 2000000)
	_lsm_end("Foto serah terima cek raksasa beredar. Caption: 'Juragan Peduli Hutan'. Hutannya sendiri tetap jadi sawit.")


func lsm_commit() -> void:
	if not GS.spend(1000000):
		return
	GS.energy = maxf(0.0, GS.energy - 30.0)
	GS.add_rep(12)
	GS.add_heat(-10)
	hub.add_stat("donated", 1000000)
	hub.add_stat("tobat_pts")
	hub.add_stat("trees")
	_lsm_end("Kamu ikut menanam 50 bibit pohon hutan bersama warga. Tanganmu kotor... dengan tanah, untuk sekali ini.")


func lsm_sue() -> bool:
	GS.add_heat(10)
	GS.add_rep(-10)
	var l := ls()
	l["sued"] = int(l["sued"]) + 1
	if hub.rng.randf() < 0.5:
		_lsm_end("Mbak Laras dipanggil polisi pakai pasal karet. Kampanye berhenti... tapi tagar #BebaskanLaras trending.")
		return true
	l["sign"] = int(l["sign"]) * 2
	hub.ui.toast("Laporanmu malah bikin petisi viral: %s tanda tangan! (Kecurigaan +10)" % _num(int(l["sign"])), "bad")
	return false


func _lsm_end(text: String) -> void:
	var l := ls()
	l["active"] = false
	l["done"] = int(l["done"]) + 1
	l["last"] = GS.day
	_clear_lsm()
	hub.ui.toast(text, "good")


# ------------------------------------------------------------------ kantor menu
func kantor_items(items: Array) -> void:
	if active():
		items.push_front({"icon": "icon_megafon", "text": "Temui pendemo di depan kantor", "desc": "%d warga berdemo. Negosiasi, ganti rugi, preman... atau abaikan." % ps()["who"].size(),
			"button": "Temui", "cb": func():
				hub.ui.close()
				meet()})
	if lsm_active():
		items.push_front({"icon": "icon_bendera", "text": "Tanggapi kampanye LSM", "desc": "Petisi: %s tanda tangan. Tiap hari menambah Kecurigaan." % _num(int(ls()["sign"])),
			"button": "Temui", "cb": func():
				hub.ui.close()
				lsm_talk()})
