extends Node
## Four endings and the Buku Prestasi.
##   * Raja Sawit        the franchise licence (deals._buy_license -> ui.show_ending)
##   * Ditangkap KPK     the third Satgas raid / a fine you cannot pay (ui.show_game_over),
##                       or an Operasi Tangkap Tangan when you bribe a lot and the heat is up
##   * Tobat & Jadi Petani Organik   at the Kantor once you have done enough good (truth to
##                       the journalist, ganti rugi, tree planting, pengajian...)
##   * Kabur ke Luar Negeri          Bang Jeki's passport + ship ticket, when the heat is on
## The ending screen is an illustrated summary with your stats; "Simpan kartu hasil"
## renders it to a PNG (downloaded / shared through the browser on the web).
## Badges are kept per save and in a profile file (user://sawit_prestasi.json) so they
## carry over to new games.

var hub: Node
var screen: Control
var last_card: Image
var _profile := {}
var _path := PROFILE_PATH

const PROFILE_PATH := "user://sawit_prestasi.json"
const KABUR_COST := 15000000
const ENDINGS := {
	"raja": {"title": "RAJA SAWIT", "sub": "Seluruh desa hijau... hijau sawit.", "col": "e0a820",
		"text": ["Kantor pusat mengirim piagam: 'Pewaralaba Terbaik Sawit The Franchise™'.",
			"Warga desa? Mereka kini membeli minyak goreng darimu... dengan harga spesial."]},
	"kpk": {"title": "DITANGKAP KPK", "sub": "Rompi oranye ternyata cocok dengan warna TBS.", "col": "d9572c",
		"text": ["Kamu digiring ke mobil tahanan sambil melambai ke kamera. Senyummu tetap senyum juragan.",
			"Kebun-kebunmu disita negara. Bang Codet jadi saksi mahkota. Bang Jeki sudah ganti nomor."]},
	"tobat": {"title": "TOBAT & JADI PETANI ORGANIK", "sub": "Cuannya tipis, tidurnya nyenyak.", "col": "5c9a3a",
		"text": ["Kebun rampasan kamu kembalikan. Lahanmu kini sayur, buah, dan hutan kecil tempat rangkong pulang.",
			"Kamu jualan sayur organik di pasar dusun. Harganya mahal, tapi kali ini warga rela."]},
	"kabur": {"title": "KABUR KE LUAR NEGERI", "sub": "Kini 'konsultan agribisnis' di Singapura.", "col": "3a74c0",
		"text": ["Tengah malam kamu naik kapal ikan dari dermaga dengan koper penuh uang dan paspor buatan Bang Jeki.",
			"Fotomu kini terpajang di situs Interpol. Di desa, warga mulai menanam kembali kebunnya."]},
}
const BADGES := [
	["panen_perdana", "Panen Perdana", "Panen tandan sawit pertamamu.", "icon_tbs"],
	["tandan_200", "Tandan Berlimpah", "Panen 200 tandan TBS.", "icon_tbs"],
	["tanah_7", "Juragan Tujuh Petak", "Kuasai 7 lahan.", "icon_rumah"],
	["tanah_20", "Tanah 20 Petak", "Kuasai SEMUA 20 lahan desa.", "icon_kunci"],
	["tak_menipu", "Tak Pernah Menipu", "Kuasai 5 lahan tanpa tipu, gusur, atau palak.", "ui_good"],
	["mancing_100", "Mancing 100 Ikan", "Tangkap 100 ikan.", "icon_pancing"],
	["kolektor_ssr", "Kolektor SSR", "Tangkap Arwana Emas dan Ikan Raja Sawit.", "ikan_raja_sawit"],
	["ensiklopedia", "Ensiklopedia Ikan", "Lengkapi 20 spesies di Koleksi Ikan.", "ikan_arwana"],
	["dermawan", "Juragan Dermawan", "Sumbang & sponsori total Rp 10 juta.", "icon_hadiah"],
	["raja_minyak", "Raja Minyak Goreng", "Jual 50 jerigen minyak ke warga.", "icon_minyak"],
	["sahabat_desa", "Sahabat Desa", "Punya 5 warga sahabat (4 hati).", "icon_hati"],
	["musuh_bersama", "Musuh Bersama", "5 warga membencimu (0 hati).", "ui_bad"],
	["masuk_koran", "Masuk Koran", "Jadi headline Koran Sukamakmur.", "icon_koran"],
	["lolos_wartawan", "Lolos dari Wartawan", "Bungkam wartawan dengan amplop atau tur palsu.", "icon_koran"],
	["diplomat", "Diplomat Kampung", "Bubarkan demo lewat negosiasi.", "icon_megafon"],
	["juara_pinang", "Juara Panjat Pinang", "Sampai di puncak pinang saat Tujuhbelasan.", "icon_panjat"],
	["raja_kondangan", "Raja Kondangan", "Datang ke 3 kondangan.", "icon_hadiah"],
	["gedongan", "Rumah Gedongan", "Renovasi rumah sampai Rumah Gedongan.", "icon_renovasi"],
	["desainer", "Desainer Interior", "Pasang 10 perabot di rumahmu.", "icon_sofa"],
	["amplop_berjalan", "Amplop Berjalan", "Menyuap 5 kali.", "icon_uang"],
	["sultan", "Sultan Sukamakmur", "Pegang uang Rp 50 juta.", "ui_coins"],
	["tamat", "Tamat!", "Capai salah satu ending.", "ui_star"],
	["multiverse", "Multiverse Juragan", "Lihat keempat ending.", "icon_medali"],
]


func es() -> Dictionary:
	return hub.st("end", {"ach": {}, "seen": []})


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--autotest"):
			_path = "user://sawit_prestasi_autotest.json"   # tests never touch the player's badges
	_load_profile()


# ------------------------------------------------------------------ profile (across games)
func _load_profile() -> void:
	_profile = {"ach": {}, "endings": []}
	if not FileAccess.file_exists(_path):
		return
	var f := FileAccess.open(_path, FileAccess.READ)
	if f == null:
		return
	var d = JSON.parse_string(f.get_as_text())
	if d is Dictionary:
		if d.get("ach") is Dictionary:
			_profile["ach"] = d["ach"]
		if d.get("endings") is Array:
			_profile["endings"] = d["endings"]


func _save_profile() -> void:
	var f := FileAccess.open(_path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_profile))


func endings_seen() -> Array:
	var out: Array = []
	for e in ENDINGS:
		if e in _profile["endings"] or e in es()["seen"]:
			out.append(e)
	return out


# ------------------------------------------------------------------ badges
func unlocked(id: String) -> bool:
	return es()["ach"].has(id) or _profile["ach"].has(id)


func unlocked_count() -> int:
	var n := 0
	for b in BADGES:
		if unlocked(b[0]):
			n += 1
	return n


func _met(id: String) -> bool:
	var st: Dictionary = GS.stats
	match id:
		"panen_perdana": return int(st["harvested"]) >= 1
		"tandan_200": return int(st["harvested"]) >= 200
		"tanah_7": return GS.controlled_parcels() >= 7
		"tanah_20": return GS.controlled_parcels() >= GS.parcels.size()
		"tak_menipu": return GS.controlled_parcels() >= 5 and hub.stat("cheats") == 0 and int(st["land_fraud"]) == 0 \
				and int(st["land_seized"]) == 0 and hub.stat("extort") == 0
		"mancing_100": return int(st.get("fish_caught", 0)) >= 100
		"kolektor_ssr": return int(GS.fish_log.get("ikan_arwana", 0)) > 0 and int(GS.fish_log.get("ikan_raja_sawit", 0)) > 0
		"ensiklopedia": return GS.fish_caught_species() >= GS.FISH.size()
		"dermawan": return hub.stat("donated") >= 10000000
		"raja_minyak": return int(st["oil_villager"]) >= 50
		"sahabat_desa": return _count_hearts(4, 5) >= 5
		"musuh_bersama": return _count_hearts(0, 0) >= 5
		"masuk_koran": return hub.stat("headlines") >= 1
		"lolos_wartawan": return int(hub.jour.s()["hushed"]) + int(hub.jour.s()["fooled"]) >= 1
		"diplomat": return int(hub.prot.ps()["nego"]) >= 1
		"juara_pinang": return int(hub.fest.fs()["pinang"]) >= 1
		"raja_kondangan": return int(hub.fest.fs()["kondangan"]) >= 3
		"gedongan": return hub.decor.level() >= 3
		"desainer": return hub.decor.hs()["placed"].size() >= 10
		"amplop_berjalan": return int(st["bribes"]) >= 5
		"sultan": return GS.money >= 50000000
		"tamat": return not es()["seen"].is_empty()
		"multiverse": return endings_seen().size() >= ENDINGS.size()
	return false


func _count_hearts(lo: int, hi: int) -> int:
	var n := 0
	for vid in GS.VILLAGERS:
		var h: int = hub.rel.hearts(vid)
		if h >= lo and h <= hi:
			n += 1
	return n


func check_badges(quiet := false) -> Array:
	## unlocks every badge whose condition holds now; returns the new ones
	var got: Array = []
	if GS.parcels.is_empty():
		return got
	for b in BADGES:
		var id: String = b[0]
		if es()["ach"].has(id):
			continue
		if _met(id):
			es()["ach"][id] = GS.day
			var fresh: bool = not _profile["ach"].has(id)
			_profile["ach"][id] = true
			got.append(id)
			if fresh and not quiet:
				GS.toast.emit("Prestasi baru: %s!" % b[1], "quest")
	if not got.is_empty():
		_save_profile()
	return got


func badge(id: String) -> Array:
	for b in BADGES:
		if b[0] == id:
			return b
	return []


# ------------------------------------------------------------------ day roll: Operasi Tangkap Tangan
func day_roll(report: Array) -> void:
	check_badges()
	if int(GS.stats["bribes"]) >= 4 and GS.heat >= 90.0 and hub.rng.randf() < 0.5:
		GS.game_active = false
		report.append("[SIDAK] OTT! Operasi Tangkap Tangan di kantormu.")
		call_deferred("finish", "kpk", "Operasi Tangkap Tangan: amplop ke-%d kamu ternyata diserahkan ke penyidik yang menyamar jadi oknum." % (int(GS.stats["bribes"]) + 1))


# ------------------------------------------------------------------ menu hooks
func tobat_ready() -> bool:
	return hub.stat("tobat_pts") + hub.stat("honest") >= 2 and GS.rep >= 20.0


func kantor_items(items: Array) -> void:
	var ok := tobat_ready()
	items.append({"icon": "icon_bibit", "text": "Tobat: kembalikan lahan & jadi petani organik",
		"desc": ("Kembalikan semua kebun rampasan ke warga, ganti sawit dengan kebun organik. ENDING." if ok else
			"Belum siap tobat. Butuh reputasi 20+ dan beberapa perbuatan baik (jujur ke wartawan, ganti rugi, tanam pohon, rajin mengaji...). Poin: %d/2." % (hub.stat("tobat_pts") + hub.stat("honest"))),
		"button": "Tobat", "enabled": ok, "cb": func():
			hub.ui.close()
			confirm_tobat()})


func calo_items(items: Array) -> void:
	var hot := GS.heat >= 60.0 or int(GS.stats["sidak"]) >= 1
	items.append({"icon": "icon_surat", "text": "Paspor + tiket kapal ke Singapura",
		"desc": "Berangkat tengah malam dari dermaga. Tidak bisa kembali. ENDING." if hot else "Bang Jeki: 'Belum perlu, Bos. Satgas belum mengendus.' (Butuh Kecurigaan 60+ atau pernah disidak.)",
		"price": GS.fmt_short(KABUR_COST), "button": "Kabur", "enabled": hot and GS.money >= KABUR_COST, "cb": func():
			hub.ui.close()
			confirm_kabur()})


func confirm_tobat() -> void:
	hub.ui.dialog("portrait_player", "Kamu", "Semua kebun rampasan dikembalikan, sawit diganti sayur dan pohon buah. Tidak ada jalan kembali. Yakin?",
		[{"text": "Ya, saya tobat", "cb": func(): do_tobat()}, {"text": "Nanti dulu", "cb": Callable()}])


func do_tobat() -> void:
	for vid in GS.villagers:
		var v: Dictionary = GS.villagers[vid]
		if v["status"] == "landless":
			var p: Dictionary = GS.parcel_of(vid)
			p["owner"] = vid
			p["plasma"] = false
			v["status"] = "owner"
			v["evicted"] = false
			v["debt"] = 0
	finish("tobat")


func confirm_kabur() -> void:
	hub.ui.dialog("portrait_calo", "Bang Jeki", "Paspor atas nama 'Budi Santoso', tiket kapal ikan jam 2 pagi. Koper muat %s. Jangan tengok ke belakang, Bos." % GS.fmt_short(maxi(0, GS.money - KABUR_COST)),
		[{"text": "Berangkat!", "cb": func():
			if GS.spend(KABUR_COST):
				finish("kabur")},
		 {"text": "Tidak jadi", "cb": Callable()}])


# ------------------------------------------------------------------ the ending
func finish(id: String, reason := "") -> void:
	var w: Node = hub.world
	w.state = "over"
	GS.game_active = false
	if not id in es()["seen"]:
		es()["seen"].append(id)
	if not id in _profile["endings"]:
		_profile["endings"].append(id)
	_save_profile()
	check_badges(true)
	if id == "raja":
		GS.save_game()
	else:
		GS.delete_save()
	Sfx.play("quest" if id in ["raja", "tobat"] else "bad")
	show_screen(id, reason)


func stats_lines() -> Array:
	var st: Dictionary = GS.stats
	var friends := _count_hearts(4, 5)
	return [
		["Hari", str(GS.day)],
		["Pendapatan", GS.fmt_short(int(st["earned"]))],
		["Uang akhir", GS.fmt_short(GS.money)],
		["Lahan dikuasai", "%d / %d" % [GS.controlled_parcels(), GS.parcels.size()]],
		["Pohon sawit", str(GS.palm_count())],
		["Reputasi", str(int(GS.rep))],
		["Kecurigaan", "%d / 100" % int(GS.heat)],
		["Ikan ditangkap", str(int(st.get("fish_caught", 0)))],
		["Warga sahabat", str(friends)],
		["Masuk koran", "%dx" % hub.stat("headlines")],
		["Tipu / gusur", "%d / %d" % [int(st["land_fraud"]), int(st["land_seized"])]],
		["Prestasi", "%d / %d" % [unlocked_count(), BADGES.size()]],
	]


func show_screen(id: String, reason := "") -> void:
	var ui: Node = hub.ui
	var es_ := EndScreen.new()
	es_.name = "EndingScreen"
	es_.set_meta("self_layout", true)
	es_.set_meta("ending", id)
	es_.endings = self
	es_.ending = id
	es_.reason = reason
	es_.build(ui)
	screen = es_
	ui._open_modal(es_, true)


func share_card(id: String) -> void:
	var img: Image = await render_card(id)
	if img == null or img.is_empty():
		hub.ui.toast("Kartu hasil tidak bisa dibuat di perangkat ini.", "bad")
		return
	last_card = img
	var png := img.save_png_to_buffer()
	if OS.has_feature("web"):
		var b64 := Marshalls.raw_to_base64(png)
		JavaScriptBridge.eval(SHARE_JS % [b64, "Aku dapat ending %s di Sawit The Franchise!" % ENDINGS[id]["title"]], true)
		hub.ui.toast("Kartu hasil siap dibagikan / diunduh!", "good")
	else:
		var path := "user://sawit_hasil_%s.png" % id
		img.save_png(path)
		hub.ui.toast("Kartu hasil disimpan: %s" % ProjectSettings.globalize_path(path), "good")


const SHARE_JS := """(async function(b64, text){
	var bin = atob(b64), arr = new Uint8Array(bin.length);
	for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
	var blob = new Blob([arr], {type: 'image/png'});
	try {
		var file = new File([blob], 'sawit_the_franchise.png', {type: 'image/png'});
		if (navigator.canShare && navigator.canShare({files: [file]})) {
			await navigator.share({files: [file], title: 'Sawit The Franchise', text: text});
			return;
		}
	} catch (e) {}
	var a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = 'sawit_the_franchise.png';
	document.body.appendChild(a);
	a.click();
	setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 2000);
})('%s', '%s');"""


func render_card(id: String) -> Image:
	## draws the result card (illustration + title + stats) in an offscreen viewport
	var sv := SubViewport.new()
	sv.size = Vector2i(1080, 1350)
	sv.transparent_bg = false
	sv.disable_3d = true
	sv.gui_disable_input = true
	sv.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(sv)
	var card := Card.new()
	card.endings = self
	card.ending = id
	card.ui = hub.ui
	card.size = Vector2(sv.size)
	sv.add_child(card)
	card.build()
	for k in 3:
		await RenderingServer.frame_post_draw
	var img: Image = null
	var tex := sv.get_texture()
	if tex:
		img = tex.get_image()
	sv.queue_free()
	return img


# ------------------------------------------------------------------ Buku Prestasi
func show_book() -> void:
	var ui: Node = hub.ui
	if ui.modal and not ui.modal.has_meta("ending"):
		return
	var back_to: String = str(ui.modal.get_meta("ending")) if ui.modal else ""
	check_badges(true)
	var vp: Vector2 = ui.root.get_viewport_rect().size
	var panel := PanelContainer.new()
	panel.name = "BukuPrestasi"
	panel.set_meta("closable", true)
	panel.set_meta("book", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	var title: Label = ui._title_label("Buku Prestasi", ui.TITLE_BROWN, 30)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_child(ui._hrow([ui._icon_rect("icon_medali", 44), title, ui._chip("icon_medali", "%d / %d" % [unlocked_count(), BADGES.size()])], 12))
	col.add_child(ui._divider())
	var cols := 4 if vp.x >= vp.y else 2
	var cw := clampf((minf(900.0, vp.x - 80.0)) / cols - 8.0, 150.0, 210.0)
	var grid := GridContainer.new()
	grid.columns = cols
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	for b in BADGES:
		grid.add_child(_badge_card(b, cw))
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(cols * (cw + 8.0), minf(ceilf(BADGES.size() / float(cols)) * 92.0, vp.y - 280.0))
	scroll.add_child(grid)
	col.add_child(scroll)
	ui._fit_scroll_later(scroll, grid, vp.y - 280.0)
	var seen := endings_seen()
	var names: Array = []
	for e in ENDINGS:
		names.append(ENDINGS[e]["title"] if e in seen else "???")
	var el: Label = ui._label("Ending: " + "  •  ".join(names), 16, ui.BROWN_SOFT, true)
	el.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	el.custom_minimum_size = Vector2(cols * (cw + 8.0), 0)
	col.add_child(el)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	if back_to != "":
		row.add_child(ui.button("Kembali", func(): show_screen(back_to), true, 160))
	else:
		row.add_child(ui.button("Tutup", ui.close, true, 160))
	col.add_child(row)
	if ui.modal:
		ui._on_modal_close = Callable()
	ui._open_modal(panel, true)


func _badge_card(b: Array, w: float) -> Control:
	var ui: Node = hub.ui
	var on := unlocked(b[0])
	var p := PanelContainer.new()
	p.name = "badge_" + str(b[0])
	var stb: StyleBoxFlat = ui._box(Color("fff4d8") if on else Color("eadfca"), 14, Color("e0a820") if on else ui.LINE, 3 if on else 2)
	ui._margins(stb, 8, 6, 8, 6)
	p.add_theme_stylebox_override("panel", stb)
	p.custom_minimum_size = Vector2(w, 84)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 8)
	p.add_child(h)
	var ic: Control = ui._icon_rect(str(b[3]), 44)
	if not on:
		ic.modulate = Color(0.25, 0.2, 0.16, 0.55)
	h.add_child(ic)
	var tc := VBoxContainer.new()
	tc.add_theme_constant_override("separation", 0)
	tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var nl: Label = ui._label(str(b[1]) if on else str(b[1]), 15, ui.BROWN if on else ui.BROWN_SOFT, true)
	nl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	nl.custom_minimum_size = Vector2(w - 70.0, 0)
	tc.add_child(nl)
	var dl: Label = ui._label(str(b[2]), 12, ui.BROWN_SOFT)
	dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dl.custom_minimum_size = Vector2(w - 70.0, 0)
	tc.add_child(dl)
	h.add_child(tc)
	return p


# ------------------------------------------------------------------ drawing
class Scene extends Control:
	## the ending illustration, drawn with shapes in the game's warm cel palette
	var ending := "raja"
	var t := 0.0
	var art := Vector2.ZERO   # the part of the picture left free for the drawing (0 = all)

	func _process(delta: float) -> void:
		t += delta
		queue_redraw()

	func _draw() -> void:
		draw_scene(self, ending, size, t)

	func draw_scene(c: CanvasItem, eid: String, sz: Vector2, tt: float) -> void:
		var sky_top := Color("8fd0e8")
		var sky_bot := Color("fdf0c8")
		var ground := Color("7fae4a")
		match eid:
			"raja":
				sky_top = Color("f6b347")
				sky_bot = Color("fff0b8")
			"kpk":
				sky_top = Color("1c2140")
				sky_bot = Color("4a3a6a")
				ground = Color("3a4a3a")
			"tobat":
				sky_top = Color("8fd0e8")
				sky_bot = Color("eaf6d8")
				ground = Color("6aa84a")
			"kabur":
				sky_top = Color("e86a4a")
				sky_bot = Color("ffd59a")
				ground = Color("3a7ab0")
		var full := sz
		sz = Vector2(art.x if art.x > 0.0 else full.x, art.y if art.y > 0.0 else full.y)
		var n := 24
		for k in n:
			var y0 := full.y * k / n
			c.draw_rect(Rect2(0, y0, full.x, full.y / n + 1), sky_top.lerp(sky_bot, float(k) / n))
		var hy := sz.y * 0.62
		# sun / moon
		if eid == "kpk":
			c.draw_circle(Vector2(sz.x * 0.8, sz.y * 0.18), sz.y * 0.07, Color("f4ecd0"))
			c.draw_circle(Vector2(sz.x * 0.83, sz.y * 0.16), sz.y * 0.065, sky_top)
		else:
			c.draw_circle(Vector2(sz.x * 0.78, sz.y * 0.2), sz.y * 0.09, Color("fff6d0"))
			c.draw_circle(Vector2(sz.x * 0.78, sz.y * 0.2), sz.y * 0.075, Color("ffe08a") if eid != "kabur" else Color("ffb070"))
		c.draw_rect(Rect2(0, hy, full.x, full.y - hy), ground)
		var ink := Color("3e2617")
		match eid:
			"raja":
				# blue tents of the evicted on the horizon, endless palm rows
				for k in 4:
					var tx := sz.x * (0.08 + k * 0.07)
					c.draw_colored_polygon(PackedVector2Array([Vector2(tx - 22, hy + 4), Vector2(tx, hy - 22), Vector2(tx + 22, hy + 4)]), Color("3a74c0"))
				for row in 3:
					var yy := hy + row * sz.y * 0.07
					for k in 9:
						_palm(c, Vector2(sz.x * (0.04 + k * 0.12) + row * 20, yy + 10), sz.y * (0.12 + row * 0.03))
				# money sacks
				for k in 3:
					var mp := Vector2(sz.x * (0.72 + k * 0.08), sz.y * 0.9)
					c.draw_circle(mp, 34, Color("c8a060"))
					c.draw_arc(mp, 34, 0, TAU, 24, ink, 3.0)
					c.draw_rect(Rect2(mp.x - 10, mp.y - 46, 20, 14), Color("a88040"))
					c.draw_string(ThemeDB.fallback_font, mp + Vector2(-16, 10), "Rp", HORIZONTAL_ALIGNMENT_LEFT, -1, 26, ink)
				# a throne of TBS and a crown
				var cx := sz.x * 0.5
				var by := sz.y * 0.9
				for k in 5:
					c.draw_circle(Vector2(cx - 90 + k * 45, by), 30, Color("c9401f"))
					c.draw_circle(Vector2(cx - 90 + k * 45, by), 30, ink, false, 3.0)
				for k in 3:
					c.draw_circle(Vector2(cx - 45 + k * 45, by - 45), 28, Color("b8401f"))
				_figure(c, Vector2(cx, by - 70), sz.y * 0.16, Color("e0b030"), true)
				var crown := PackedVector2Array([Vector2(cx - 30, by - 70 - sz.y * 0.16 - 6), Vector2(cx - 30, by - 70 - sz.y * 0.16 - 40),
					Vector2(cx - 15, by - 70 - sz.y * 0.16 - 22), Vector2(cx, by - 70 - sz.y * 0.16 - 46), Vector2(cx + 15, by - 70 - sz.y * 0.16 - 22),
					Vector2(cx + 30, by - 70 - sz.y * 0.16 - 40), Vector2(cx + 30, by - 70 - sz.y * 0.16 - 6)])
				c.draw_colored_polygon(crown, Color("ffd040"))
				c.draw_polyline(crown + PackedVector2Array([crown[0]]), ink, 3.0)
			"kpk":
				for k in 6:
					_palm(c, Vector2(sz.x * (0.05 + k * 0.18), hy + 8), sz.y * 0.13, Color("1e2a1e"))
				# the van with flashing lights
				var vx := sz.x * 0.62
				var vy := sz.y * 0.82
				c.draw_rect(Rect2(vx - 160, vy - 90, 320, 90), Color("e8e8e0"))
				c.draw_rect(Rect2(vx - 160, vy - 90, 320, 90), ink, false, 4.0)
				c.draw_rect(Rect2(vx - 150, vy - 55, 300, 14), Color("2a5aa0"))
				c.draw_circle(Vector2(vx - 100, vy), 26, ink)
				c.draw_circle(Vector2(vx + 100, vy), 26, ink)
				var on := int(tt * 4.0) % 2 == 0
				c.draw_circle(Vector2(vx - 30, vy - 100), 16, Color("ff3a3a") if on else Color("6a2020"))
				c.draw_circle(Vector2(vx + 30, vy - 100), 16, Color("3a6aff") if not on else Color("20306a"))
				c.draw_string(ThemeDB.fallback_font, Vector2(vx - 60, vy - 62), "TAHANAN", HORIZONTAL_ALIGNMENT_LEFT, -1, 28, ink)
				_figure(c, Vector2(sz.x * 0.28, sz.y * 0.88), sz.y * 0.18, Color("f07a20"), true)
				for k in 7:
					c.draw_rect(Rect2(sz.x * 0.15 + k * 34, sz.y * 0.5, 7, sz.y * 0.42), Color(0.2, 0.2, 0.24, 0.85))
			"tobat":
				for k in 4:
					_tree(c, Vector2(sz.x * (0.1 + k * 0.26), hy + 6), sz.y * 0.2)
				for row in 4:
					var yy := hy + 40 + row * sz.y * 0.06
					c.draw_rect(Rect2(0, yy, sz.x, 10), Color("5a3a24").lerp(ground, 0.3))
					for k in 14:
						c.draw_circle(Vector2(k * sz.x / 14.0 + 20 + row * 9, yy - 6), 11, Color("4a9a3a") if (k + row) % 3 else Color("d9402a"))
				_figure(c, Vector2(sz.x * 0.5, sz.y * 0.93), sz.y * 0.17, Color("6cbf5a"), false)
				for k in 3:
					var bx := sz.x * (0.2 + k * 0.15) + sin(tt + k) * 20.0
					var byy := sz.y * (0.25 + k * 0.04)
					c.draw_polyline(PackedVector2Array([Vector2(bx - 12, byy), Vector2(bx, byy + 6), Vector2(bx + 12, byy)]), ink, 3.0)
			"kabur":
				# the sea, a skyline over the horizon and a little ship sailing away
				for k in 10:
					var bw := sz.x * 0.05
					var bh := sz.y * (0.05 + fmod(k * 0.37, 0.12))
					c.draw_rect(Rect2(sz.x * 0.45 + k * bw * 1.05, hy - bh, bw, bh), Color("8a5a6a"))
				for k in 8:
					var wy := hy + 20 + k * 30
					c.draw_line(Vector2(sin(tt + k) * 30.0, wy), Vector2(sz.x, wy + 4), Color(1, 1, 1, 0.18), 3.0)
				var sx := sz.x * 0.35 + sin(tt * 0.5) * 10.0
				var sy := sz.y * 0.8
				var hull := PackedVector2Array([Vector2(sx - 150, sy - 40), Vector2(sx + 150, sy - 40), Vector2(sx + 110, sy + 10), Vector2(sx - 110, sy + 10)])
				c.draw_colored_polygon(hull, Color("e8e0d0"))
				c.draw_polyline(hull + PackedVector2Array([hull[0]]), ink, 4.0)
				c.draw_rect(Rect2(sx - 50, sy - 110, 100, 70), Color("d9572c"))
				c.draw_rect(Rect2(sx - 50, sy - 110, 100, 70), ink, false, 3.0)
				_figure(c, Vector2(sx + 90, sy - 40), sz.y * 0.13, Color("3a3a42"), true)
				c.draw_rect(Rect2(sx + 40, sy - 75, 40, 30), Color("6a4a2a"))
				c.draw_string(ThemeDB.fallback_font, Vector2(sx + 44, sy - 52), "Rp", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("ffe08a"))


	func _palm(c: CanvasItem, base: Vector2, h: float, col := Color("3f6f2a")) -> void:
		var top := base + Vector2(4, -h)
		c.draw_line(base, top, Color("6a4a2a") if col.v > 0.25 else col, h * 0.09)
		for k in 7:
			var a := -PI + k * PI / 6.0
			var tip := top + Vector2(cos(a) * h * 0.55, sin(a) * h * 0.3 + h * 0.12)
			c.draw_line(top, (top + tip) * 0.5 + Vector2(0, -h * 0.06), col, h * 0.07)
			c.draw_line((top + tip) * 0.5 + Vector2(0, -h * 0.06), tip, col, h * 0.05)


	func _tree(c: CanvasItem, base: Vector2, h: float) -> void:
		c.draw_line(base, base + Vector2(0, -h * 0.6), Color("6a4a2a"), h * 0.1)
		c.draw_circle(base + Vector2(0, -h * 0.75), h * 0.32, Color("3f8a3a"))
		c.draw_circle(base + Vector2(-h * 0.22, -h * 0.6), h * 0.22, Color("4a9a44"))
		c.draw_circle(base + Vector2(h * 0.22, -h * 0.62), h * 0.24, Color("4a9a44"))


	func _figure(c: CanvasItem, feet: Vector2, h: float, shirt: Color, hat: bool) -> void:
		var ink := Color("3e2617")
		var head := feet + Vector2(0, -h * 0.82)
		c.draw_rect(Rect2(feet.x - h * 0.16, feet.y - h * 0.62, h * 0.32, h * 0.42), shirt)
		c.draw_rect(Rect2(feet.x - h * 0.16, feet.y - h * 0.62, h * 0.32, h * 0.42), ink, false, 3.0)
		c.draw_rect(Rect2(feet.x - h * 0.13, feet.y - h * 0.2, h * 0.1, h * 0.2), Color("3b4155"))
		c.draw_rect(Rect2(feet.x + h * 0.03, feet.y - h * 0.2, h * 0.1, h * 0.2), Color("3b4155"))
		c.draw_circle(head, h * 0.15, Color("f2b98a"))
		c.draw_arc(head, h * 0.15, 0, TAU, 20, ink, 3.0)
		c.draw_circle(head + Vector2(-h * 0.05, -h * 0.01), h * 0.018, ink)
		c.draw_circle(head + Vector2(h * 0.05, -h * 0.01), h * 0.018, ink)
		c.draw_arc(head + Vector2(0, h * 0.04), h * 0.05, 0.2, PI - 0.2, 8, ink, 2.0)
		if hat:
			c.draw_rect(Rect2(head.x - h * 0.22, head.y - h * 0.15, h * 0.44, h * 0.05), Color("4a3020"))
			c.draw_rect(Rect2(head.x - h * 0.12, head.y - h * 0.27, h * 0.24, h * 0.13), Color("4a3020"))
		else:
			var cap := PackedVector2Array([head + Vector2(-h * 0.3, -h * 0.08), head + Vector2(0, -h * 0.3), head + Vector2(h * 0.3, -h * 0.08)])
			c.draw_colored_polygon(cap, Color("e2be7a"))


class EndScreen extends Control:
	## full-screen ending: the illustration with a summary card and the buttons
	var endings: Node
	var ending := "raja"
	var reason := ""
	var choices: Array = []   # (ui._modal_hint reads it from self-laid-out modals)
	var ui: Node
	var scene: Control
	var card: PanelContainer

	func build(p_ui: Node) -> void:
		ui = p_ui
		mouse_filter = Control.MOUSE_FILTER_STOP
		var e: Dictionary = endings.ENDINGS[ending]
		scene = Scene.new()
		scene.set("ending", ending)
		scene.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(scene)
		card = PanelContainer.new()
		card.name = "EndCard"
		var st: StyleBoxFlat = ui._box(Color(0.99, 0.95, 0.87, 0.94), 22, Color(e["col"]), 4, true)
		ui._margins(st, 22, 14, 22, 16)
		card.add_theme_stylebox_override("panel", st)
		add_child(card)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 6)
		card.add_child(col)
		var tag: Label = ui._label("TAMAT", 18, ui.BROWN_SOFT, true)
		tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		col.add_child(tag)
		var t: Label = ui._label(e["title"], 34, Color(e["col"]).darkened(0.25), true)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		t.custom_minimum_size = Vector2(440, 0)
		t.name = "Title"
		col.add_child(t)
		var sub: Label = ui._label(e["sub"], 18, ui.BROWN, false)
		sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		sub.custom_minimum_size = Vector2(440, 0)
		col.add_child(sub)
		var lines: Array = []
		if reason != "":
			lines.append(reason)
		lines.append_array(e["text"])
		for s in lines:
			var l: Label = ui._label(s, 15, ui.BROWN_SOFT)
			l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			l.custom_minimum_size = Vector2(420, 0)
			col.add_child(l)
		col.add_child(ui._divider())
		var grid := GridContainer.new()
		grid.columns = 4
		grid.add_theme_constant_override("h_separation", 14)
		grid.add_theme_constant_override("v_separation", 2)
		for pair in endings.stats_lines():
			grid.add_child(ui._label(pair[0], 14, ui.BROWN_SOFT))
			grid.add_child(ui._label(pair[1], 15, ui.BROWN, true))
		col.add_child(grid)
		var row := HBoxContainer.new()
		row.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_theme_constant_override("separation", 8)
		var share: Button = ui.button("Simpan kartu hasil", func(): endings.share_card(ending), true, 0, true)
		share.name = "ShareButton"
		row.add_child(share)
		row.add_child(ui.button("Buku Prestasi", func(): endings.show_book(), true, 0))
		row.add_child(ui.button("Ke judul", func():
			ui.close()
			endings.hub.world.enter_title(), true, 0))
		col.add_child(row)

	func relayout(vp: Vector2) -> void:
		position = Vector2.ZERO
		size = vp
		scene.position = Vector2.ZERO
		scene.size = vp
		var cs := card.get_combined_minimum_size()
		cs.x = minf(maxf(cs.x, 480.0), vp.x - 24.0)
		card.size = Vector2(cs.x, minf(cs.y, vp.y - 24.0))
		if vp.x >= vp.y * 1.2:
			card.position = Vector2(vp.x - card.size.x - 32.0, (vp.y - card.size.y) * 0.5).round()
			scene.art = Vector2(card.position.x - 10.0, vp.y)
		else:
			card.position = Vector2((vp.x - card.size.x) * 0.5, vp.y - card.size.y - 16.0).round()
			scene.art = Vector2(vp.x, maxf(card.position.y + 30.0, vp.y * 0.3))

	func play_in() -> void:
		modulate.a = 0.0
		create_tween().tween_property(self, "modulate:a", 1.0, 0.5)

	func occupied_rects() -> Array:
		return [Rect2(Vector2.ZERO, size)]


class Card extends Control:
	## the shareable result card (1080 x 1350): illustration on top, stats below
	var endings: Node
	var ending := "raja"
	var ui: Node

	func build() -> void:
		var e: Dictionary = endings.ENDINGS[ending]
		var bg := ColorRect.new()
		bg.color = Color("fcf2dd")
		bg.size = size
		add_child(bg)
		var sc := Scene.new()
		sc.set("ending", ending)
		sc.position = Vector2(40, 40)
		sc.size = Vector2(size.x - 80, 640)
		sc.set_process(false)
		add_child(sc)
		var frame := ReferenceRect.new()
		frame.border_color = Color("3e2617")
		frame.border_width = 6
		frame.editor_only = false
		frame.position = sc.position
		frame.size = sc.size
		add_child(frame)
		var y := 700.0
		y = _text("SAWIT THE FRANCHISE  •  TAMAT", 34, Color("8a6a4a"), y)
		y = _text(e["title"], 66, Color(e["col"]).darkened(0.25), y + 4)
		y = _text(e["sub"], 34, Color("4a2f1d"), y + 6)
		var st: Array = endings.stats_lines()
		var colw := (size.x - 80) / 2.0
		y += 26
		for k in st.size():
			var x := 40.0 + (k % 2) * colw
			var yy := y + (k / 2) * 58.0
			_lab(st[k][0], 30, Color("8a6a4a"), Vector2(x, yy), colw * 0.55)
			_lab(st[k][1], 34, Color("3e2617"), Vector2(x + colw * 0.5, yy - 3), colw * 0.5)
		_text("Main gratis: Sawit The Franchise by @leonrdewa  •  (Ini satir. Hormati hak tanah warga & hutan.)", 22, Color("8a6a4a"), size.y - 60)

	func _text(s: String, fs: int, col: Color, y: float) -> float:
		var l := _lab(s, fs, col, Vector2(40, y), size.x - 80)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		return y + l.get_combined_minimum_size().y

	func _lab(s: String, fs: int, col: Color, pos: Vector2, w: float) -> Label:
		var l := Label.new()
		l.text = s
		l.add_theme_font_override("font", ui._font_bold)
		l.add_theme_font_size_override("font_size", fs)
		l.add_theme_color_override("font_color", col)
		l.position = pos
		l.custom_minimum_size = Vector2(w, 0)
		l.size = Vector2(w, 0)
		add_child(l)
		return l
