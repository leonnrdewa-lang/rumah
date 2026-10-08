extends Node
## The investigative journalist (Dimas, Koran Sukamakmur). When Kecurigaan is high he
## comes to town, picks the juiciest of your sins as his story and follows leads (he
## stands at a victim's tent, a cheated garden, the warung...): every day you let him
## dig is one more piece of evidence, at 3 the story runs. Talk to him to
##   * suap        an envelope (pricier per lead; idealists may refuse = worse story)
##   * hindari     walk away (he keeps digging)
##   * tur palsu   a staged garden tour: three quick choices, fool him for an advertorial
##   * jujur       tell the truth: a clean record gets praise, a dirty one a confession
## A story that runs is a Koran Sukamakmur headline popup: reputation down, Kecurigaan up.

var hub: Node
var npc: Npc

const NAME := "Wartawan Investigasi"
const PORTRAIT := "portrait_petugas"   # voice bank "wartawan"
const NPC_NAME := "Dimas (Wartawan)"
const TOPICS := {
	"gusur": {"name": "penggusuran warga", "head": "SKANDAL! Juragan Sawit Gusur Warga Pakai Preman, Disebut 'Relokasi Sukarela'",
		"sub": "Keluarga korban kini tinggal di tenda biru. 'Sukarela dari Hongkong,' kata warga.",
		"cap": "Tenda biru di dekat warung. Dulu ini kebun."},
	"surat": {"name": "surat tanah palsu", "head": "Surat Tanah Palsu Beredar di Sukamakmur, Capnya Masih Basah",
		"sub": "Warga lansia mengaku cap jempol untuk 'bantuan pemerintah'. Ternyata akta jual beli.",
		"cap": "Barang bukti: surat bercap basah. Tintanya belum kering."},
	"palak": {"name": "pemalakan warga", "head": "Preman Juragan Rampas Tabungan Sekolah Anak",
		"sub": "Bang Codet: 'Kami cuma bantu warga berhemat.'",
		"cap": "Celengan ayam korban. Isinya kini nol."},
	"minyak": {"name": "harga minyak goreng", "head": "Minyak Goreng Rp 95 Ribu Sejerigen, Warga Kini Goreng Pakai Air",
		"sub": "Juragan sawit jual minyak ke warga yang kebunnya ia ambil. Lingkaran setan atau model bisnis?",
		"cap": "Ibu-ibu antre minyak goreng. Antreannya lebih panjang dari jalan desa."},
	"utang": {"name": "jerat utang franchise", "head": "Bunga 5% Per Hari: Kemitraan Franchise atau Lintah Darat?",
		"sub": "Petani plasma: 'Saya pemilik kebun, tapi yang kaya kok dia?'",
		"cap": "Buku utang warga. Halamannya sudah habis."},
	"amplop": {"name": "amplop untuk oknum", "head": "Amplop Tebal Beredar, Laporan Warga Mendadak Hilang",
		"sub": "Oknum mengaku amplop berisi 'dokumen'. Dokumennya bergambar Soekarno-Hatta.",
		"cap": "Amplop cokelat. Isinya bukan surat cinta."},
	"sawit": {"name": "asal-usul kebun sawit", "head": "Kebun Sawit Tumbuh Secepat Kilat, Hutan Desa Hilang Secepat Kilat",
		"sub": "Burung rangkong terakhir terlihat pindah ke kabupaten sebelah.",
		"cap": "Dulu hutan. Sekarang barisan sawit rapi sekali."},
	"suap": {"name": "upaya suap", "head": "Juragan Sawit Coba Suap Wartawan, Amplopnya Kini Jadi Barang Bukti",
		"sub": "'Saya kira itu undangan kondangan,' kilah sang juragan.",
		"cap": "Amplop yang ditolak. Difoto dengan penggaris."},
	"tur": {"name": "tur kebun palsu", "head": "Tur 'Kebun Ramah Lingkungan' Ternyata Pakai Bunga Pinjaman",
		"sub": "Buruh yang 'bahagia' ternyata dibayar Rp 20 ribu untuk tersenyum.",
		"cap": "Pot bunga pinjaman Bu Tini, dipasang di depan kebun sawit."},
}


func s() -> Dictionary:
	return hub.st("jour", {"active": false, "lead": 0, "topic": "", "day": 0, "left": -9, "pending": "",
		"hushed": 0, "exposed": 0, "fooled": 0, "truth": 0, "spot": []})


func active() -> bool:
	return bool(s()["active"])


func lead() -> int:
	return int(s()["lead"])


func topic_name() -> String:
	return str(TOPICS.get(str(s()["topic"]), TOPICS["sawit"])["name"])


func sins() -> int:
	var st: Dictionary = GS.stats
	return int(st["land_fraud"]) + int(st["land_seized"]) * 2 + int(st["land_debt"]) + hub.stat("extort") * 2 + int(st["bribes"])


func pick_topic() -> String:
	var st: Dictionary = GS.stats
	if int(st["land_seized"]) > 0:
		return "gusur"
	if int(st["land_fraud"]) > 0:
		return "surat"
	if hub.stat("extort") > 0:
		return "palak"
	if GS.oil_price_level == 2 and int(st["oil_villager"]) > 0:
		return "minyak"
	if int(st["land_debt"]) > 0 or int(st["franchise"]) > 0:
		return "utang"
	if int(st["bribes"]) > 0:
		return "amplop"
	return "sawit"


# ------------------------------------------------------------------ day roll
func day_roll(report: Array) -> void:
	var j := s()
	if active():
		j["lead"] = lead() + (2 if GS.heat >= 85.0 else 1)
		if lead() >= 3:
			j["pending"] = str(j["topic"])
			_insert_event("koran")
			report.append("Wartawan Dimas sudah mengantongi cukup bukti. Koran pagi ini... siap terbit.")
		else:
			report.append("Wartawan Dimas terus menggali soal %s (bukti %d/3). Temui dia sebelum beritanya terbit!" % [topic_name(), lead()])
		return
	# the journalist arrives: the generic "wartawan" morning event becomes his visit
	var idx: int = GS.pending_events.find("wartawan")
	var want: bool = GS.heat >= 55.0 and GS.day - int(j["left"]) >= 2 and (GS.heat >= 75.0 or hub.rng.randf() < 0.5)
	if idx >= 0 or want:
		if idx >= 0:
			GS.pending_events.remove_at(idx)
		_insert_event("jurnalis")


func _insert_event(ev: String) -> void:
	if not ev in GS.pending_events:
		GS.pending_events.push_front(ev)


# ------------------------------------------------------------------ visuals
func refresh() -> void:
	hub.despawn(npc)
	npc = null
	if not active():
		return
	var p := _lead_spot()
	npc = hub.spawn_npc("char_pemuda", NPC_NAME, p, 2.5, "wartawan_dimas",
		func(): return "Hadapi wartawan Dimas (bukti %d/3)" % lead(), func(): talk())
	# a press card and a notebook: the PERS label over his head
	var tag: Label3D = hub.label3d(npc, "PERS", Vector3(0, 1.95, 0), 44, Color("c0392b"), true)
	tag.pixel_size = 0.009
	tag.outline_size = 12
	# a camera hanging at his chest
	var body: Node3D = npc.model if npc.model else npc
	hub.box(body, Vector3(0.2, 0.13, 0.1), Vector3(0.0, 0.85, 0.19), "2a2a30")
	hub.cyl(body, 0.045, 0.08, Vector3(0.0, 0.85, 0.26), "5a5a62", 8, Vector3(PI * 0.5, 0, 0))


func _lead_spot() -> Vector3:
	## where he digs today: a victim's tent / house, a cheated garden, the warung...
	var w: Node = hub.world
	var t := str(s()["topic"])
	var cand: Array = []
	for vid in GS.villagers:
		var v: Dictionary = GS.villagers[vid]
		if v["status"] == "landless" and w.npcs.has(vid):
			cand.append(w.npcs[vid].home + Vector3(1.6, 0, 1.4))
	var d: Vector3 = w.door_points.get("warung", Vector3.ZERO) + Vector3(2.5, 0, 2.0)
	if t in ["minyak", "amplop", "sawit"] or cand.is_empty():
		var keys := ["warung", "kantor", "pabrik", "toko"]
		d = w.door_points.get(keys[(GS.day + lead()) % keys.size()], d) + Vector3(2.2, 0, 1.8)
	else:
		d = cand[(GS.day + lead()) % cand.size()]
	return hub.free_spot_near(d, 0.8, 10.0)


# ------------------------------------------------------------------ the visit
func arrive() -> void:
	var j := s()
	j["active"] = true
	j["lead"] = 0
	j["topic"] = pick_topic()
	j["day"] = GS.day
	refresh()
	hub.ui.dialog(PORTRAIT, NAME, "Selamat pagi, Juragan. Saya Dimas, dari Koran Sukamakmur. Saya sedang menulis soal %s di desa ini. Boleh saya wawancara sebentar?" % topic_name(),
		_choices(true))


func talk() -> void:
	if not active():
		return
	if npc:
		npc.talking = true
		npc.talk_target = hub.world.player
	var lines := ["Juragan lagi. Bukti saya sudah %d dari 3. Masih mau bilang tidak ada apa-apa?",
		"Warga cerita banyak hal menarik soal Juragan. Bukti saya: %d dari 3.",
		"Saya cuma butuh satu jawaban jujur, Juragan. Bukti saya sudah %d dari 3."]
	hub.ui.dialog(PORTRAIT, NAME, lines[lead() % lines.size()] % lead(), _choices(false))


func bribe_cost() -> int:
	return 1000000 + 500000 * lead()


func _choices(morning: bool) -> Array:
	var after := func():
		if morning:
			hub.next_event()
	var cost := bribe_cost()
	return [
		{"text": "Suap: selipkan amplop", "hint": GS.fmt_short(cost), "enabled": GS.money >= cost, "cb": func():
			if bribe():
				after.call()},
		{"text": "Hindari: 'Maaf, saya sibuk'", "hint": "dia terus menggali", "cb": func():
			dodge()
			after.call()},
		{"text": "Ajak tur kebun 'ramah lingkungan'", "hint": "modal Rp 300rb", "enabled": GS.money >= 300000, "cb": func(): tour_start(morning)},
		{"text": "Ceritakan yang sebenarnya", "hint": "dosa: %d" % sins(), "cb": func(): truth()},
	]


func bribe() -> bool:
	var cost := bribe_cost()
	if not GS.spend(cost):
		return false
	GS.stats["bribes"] += 1
	Sfx.play("cash")
	var chance := clampf(0.8 - 0.15 * lead(), 0.3, 0.8)
	if hub.rng.randf() < chance:
		GS.add_heat(-10)
		GS.add_rep(-2)
		_leave("hushed")
		hub.ui.toast("Dimas mengantongi amplopnya. Beritanya berubah jadi 'Juragan Dermawan Bagi-bagi THR'.", "good")
		return true
	s()["topic"] = "suap"
	_leave("")
	publish("suap")
	return false


func dodge() -> void:
	GS.add_heat(2)
	hub.ui.toast("Kamu pura-pura ditelepon pusat. Dimas mencatat sesuatu di bukunya...", "info")


func truth() -> void:
	var j := s()
	j["truth"] = int(j["truth"]) + 1
	hub.add_stat("honest")
	var dirty := sins()
	_leave("")
	if dirty <= 0:
		GS.add_rep(15)
		GS.add_heat(-20)
		headline({"head": "Langka! Juragan Sawit Jujur Ditemukan di Sukamakmur", "sub": "Para ahli menyebutnya lebih langka dari Arwana Emas.",
			"cap": "Sang juragan tersenyum. Tidak ada preman di foto ini.",
			"fx": "Reputasi +15 • Kecurigaan -20"}, true)
	else:
		GS.add_rep(4)
		GS.add_heat(15)
		hub.add_stat("tobat_pts")
		headline({"head": "Juragan Sawit Ngaku Dosa di Koran: 'Saya Khilaf... %d Kali'" % dirty,
			"sub": "Warga terharu, Satgas mencatat. Pengacara sang juragan pingsan.",
			"cap": "Sang juragan saat wawancara. Matanya berkaca-kaca, dompetnya juga.",
			"fx": "Reputasi +4 • Kecurigaan +15 • (Langkah pertama menuju tobat?)"}, false)


func _leave(how: String) -> void:
	var j := s()
	j["active"] = false
	j["lead"] = 0
	j["left"] = GS.day
	if how != "":
		j[how] = int(j.get(how, 0)) + 1
	hub.despawn(npc)
	npc = null


# ------------------------------------------------------------------ tur kebun palsu (mini-choice)
var _tour_score := 0
var _tour_morning := false


func tour_start(morning: bool) -> void:
	if not GS.spend(300000):
		return
	_tour_score = 0
	_tour_morning = morning
	var evicted := false
	for vid in GS.villagers:
		if GS.villagers[vid].get("evicted", false):
			evicted = true
	hub.ui.dialog(PORTRAIT, NAME, "Tur kebun? Menarik. (Kamu sudah pinjam pot bunga dan memasang spanduk 'SAWIT RAMAH LINGKUNGAN'.) Kita mulai dari mana, Juragan?", [
		{"text": "Kebun paling rapi (pot bunga di tiap pohon)", "cb": func(): tour_step(1, 1)},
		{"text": "Tenda biru warga: 'ini konsep glamping'" if evicted else "Gudang pupuk: 'ini wangi alami'", "cb": func(): tour_step(1, -1)},
		{"text": "Pabrik minyak: 'mesinnya hemat energi'", "cb": func(): tour_step(1, 0)},
	])


func tour_step(step: int, gain: int) -> void:
	_tour_score += gain
	match step:
		1:
			hub.ui.dialog(PORTRAIT, NAME, "Hmm. Lalu kenapa air sungai di sana warnanya cokelat susu, Juragan?", [
				{"text": "'Itu teh tarik alami, khas Sukamakmur'", "cb": func(): tour_step(2, 1 if hub.rng.randf() < 0.55 else -1)},
				{"text": "'Ulah kambing Pak Karta'", "cb": func(): tour_step(2, 1 if hub.rng.randf() < 0.4 else 0)},
				{"text": "'...Pupuk. Banyak pupuk.'", "cb": func(): tour_step(2, -1)},
			])
		2:
			var workers := GS.workers.size()
			hub.ui.dialog(PORTRAIT, NAME, "Saya mau wawancara satu orang di sini. Siapa yang bisa saya tanya?", [
				{"text": "Buruh yang sudah dilatih bilang 'Saya bahagia'", "hint": "buruh: %d" % workers, "cb": func(): tour_step(3, 1 if workers > 0 else -1)},
				{"text": "Pak RT Bejo (sudah dapat 'uang lelah')", "hint": "Rp 300rb", "enabled": GS.money >= 300000, "cb": func():
					GS.spend(300000)
					tour_step(3, 1)},
				{"text": "Silakan pilih warga sendiri", "cb": func(): tour_step(3, 1 if _wronged_count() == 0 else -2)},
			])
		3:
			tour_finish()


func _wronged_count() -> int:
	var n := 0
	for vid in GS.VILLAGERS:
		if int(hub.rel.rec(vid)["wronged"]) > 0:
			n += 1
	return n


func tour_finish() -> bool:
	var ok := _tour_score >= 2
	if ok:
		GS.add_rep(6)
		GS.add_heat(-12)
		_leave("fooled")
		Sfx.play("quest")
		headline({"head": "ADVERTORIAL: Juragan Sawit Peduli Lingkungan, Sungai Desa Kini Rasa Teh Tarik",
			"sub": "Buruh mengaku bahagia. Bunga di kebun mekar (dalam pot).", "cap": "Sang juragan menyiram pot bunga pinjaman.",
			"fx": "Tur sukses! Reputasi +6 • Kecurigaan -12"}, true)
	else:
		s()["topic"] = "tur"
		_leave("")
		publish("tur")
	return ok


# ------------------------------------------------------------------ the newspaper
func publish_pending() -> void:
	var j := s()
	var t := str(j["pending"])
	j["pending"] = ""
	if t == "":
		t = str(j["topic"])
	_leave("")
	publish(t)


func publish(topic: String) -> void:
	var tp: Dictionary = TOPICS.get(topic, TOPICS["sawit"])
	GS.add_rep(-15)
	GS.add_heat(20)
	var j := s()
	j["exposed"] = int(j["exposed"]) + 1
	hub.add_stat("headlines")
	for vid in GS.VILLAGERS:
		hub.rel.add(vid, -4.0, false)
	Sfx.play("bad")
	headline({"head": tp["head"], "sub": tp["sub"], "cap": tp["cap"], "fx": "Reputasi -15 • Kecurigaan +20 • Warga makin tidak percaya"}, false)


func headline(h: Dictionary, good: bool) -> void:
	## the Koran Sukamakmur front page as a popup
	var ui: Node = hub.ui
	var vp: Vector2 = ui.root.get_viewport_rect().size
	var w := minf(660.0, vp.x - 50.0)
	var panel := PanelContainer.new()
	panel.name = "Koran"
	panel.set_meta("closable", true)
	panel.set_meta("koran", h["head"])
	var paper: StyleBoxFlat = ui._box(Color("f3ecdb"), 6, Color("3a2a1e"), 3, true)
	ui._margins(paper, 22, 14, 22, 16)
	panel.add_theme_stylebox_override("panel", paper)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	panel.add_child(col)
	var mast: Label = ui._label("KORAN SUKAMAKMUR", 38, Color("1e1612"), true)
	mast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(mast)
	var ed: Label = ui._label("Edisi Hari ke-%d  •  %s  •  Harga Rp 2.000 (naik, gara-gara minyak)" % [GS.day, hub.fest.date_text(GS.day)], 14, Color("5a4a3a"))
	ed.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(ed)
	var rule := ColorRect.new()
	rule.color = Color("1e1612")
	rule.custom_minimum_size = Vector2(w, 3)
	col.add_child(rule)
	var hl: Label = ui._label(str(h["head"]), 28, Color("1e1612") if not good else Color("1f4f2a"), true)
	hl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hl.custom_minimum_size = Vector2(w, 0)
	col.add_child(hl)
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 14)
	var photo := NewsPhoto.new()
	photo.good = good
	photo.custom_minimum_size = Vector2(minf(200.0, w * 0.34), 150)
	var pc := VBoxContainer.new()
	pc.add_child(photo)
	var cap: Label = ui._label(str(h["cap"]), 13, Color("5a4a3a"))
	cap.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cap.custom_minimum_size = Vector2(photo.custom_minimum_size.x, 0)
	pc.add_child(cap)
	body.add_child(pc)
	var tc := VBoxContainer.new()
	tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sub: Label = ui._label(str(h["sub"]), 18, Color("2a201a"))
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	sub.custom_minimum_size = Vector2(w - photo.custom_minimum_size.x - 20.0, 0)
	tc.add_child(sub)
	var by: Label = ui._label("Oleh: Dimas, wartawan investigasi. (Bukan advertorial... kecuali yang advertorial.)", 13, Color("7a6a5a"))
	by.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	by.custom_minimum_size = Vector2(w - photo.custom_minimum_size.x - 20.0, 0)
	tc.add_child(by)
	body.add_child(tc)
	col.add_child(body)
	var fx: Label = ui._label(str(h.get("fx", "")), 17, Color("2f6d2a") if good else ui.RED, true)
	fx.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	fx.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fx.custom_minimum_size = Vector2(w, 0)
	col.add_child(fx)
	var b: Button = ui.button("Lipat korannya", ui.close, true, 220, true)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(b)
	ui._open_modal(panel, true, func(): hub.next_event())


class NewsPhoto extends Control:
	## a grainy newspaper photo: a palm row, a figure and a crowd (or flowers), in sepia dots
	var good := false

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color("cfc4ac"))
		draw_rect(Rect2(0, size.y * 0.62, size.x, size.y * 0.38), Color("a99d84"))
		for k in 5:
			var x := size.x * (0.1 + k * 0.2)
			draw_line(Vector2(x, size.y * 0.62), Vector2(x + 2, size.y * 0.25), Color("4a4034"), 4.0)
			for a in 6:
				var ang := -PI * 0.9 + a * PI * 0.16
				draw_line(Vector2(x + 2, size.y * 0.25), Vector2(x + 2, size.y * 0.25) + Vector2(cos(ang), sin(ang) * 0.6) * 22.0, Color("3a3228"), 3.0)
		# the juragan (big hat) in front
		var c := Vector2(size.x * 0.5, size.y * 0.7)
		draw_circle(c + Vector2(0, -38), 11, Color("3a3028"))
		draw_rect(Rect2(c.x - 18, c.y - 30, 36, 44), Color("3a3028"))
		draw_rect(Rect2(c.x - 20, c.y - 52, 40, 6), Color("2a221c"))
		if good:
			for k in 6:
				var p := Vector2(size.x * (0.12 + k * 0.15), size.y * 0.9)
				draw_circle(p, 6, Color("5a4a3a"))
				draw_circle(p + Vector2(0, -7), 4, Color("8a7a6a"))
		else:
			for k in 7:
				var p := Vector2(size.x * (0.08 + k * 0.14), size.y * 0.88)
				draw_circle(p + Vector2(0, -16), 7, Color("4a4034"))
				draw_rect(Rect2(p.x - 7, p.y - 10, 14, 18), Color("4a4034"))
				if k % 2 == 0:
					draw_rect(Rect2(p.x - 12, p.y - 46, 24, 14), Color("e8e0cc"))
					draw_line(Vector2(p.x, p.y - 32), Vector2(p.x, p.y - 18), Color("4a4034"), 2.0)
		# halftone grain
		var g := 7.0
		var y := 0.0
		while y < size.y:
			var x := fmod(y, 2.0 * g) * 0.5
			while x < size.x:
				draw_circle(Vector2(x, y), 0.9, Color(0, 0, 0, 0.12))
				x += g
			y += g
		draw_rect(r, Color("3a2a1e"), false, 2.0)
