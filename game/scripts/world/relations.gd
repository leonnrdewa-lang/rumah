extends Node
## Friendship with the named villagers (0..100, shown as 0-5 hearts in their dialog and
## in the Warga panel). Up by chatting, gifts and small requests (bring me ...), down by
## lowballing, fraud, eviction, extortion, debt seizure and greedy oil prices.
## Best friends (4+ hearts) sell their garden at a fair "harga sahabat" and whisper
## secret tips; enemies (0-1 heart) report you to the Satgas overnight.

var hub: Node

const START := 30.0
const DEF := {"f": START, "gift": 0, "tip": 0, "wronged": 0, "req": {}}
## what each villager loves (x2 friendship) and hates (a gift that backfires)
const LIKES := {
	"kakek": ["kopi", "ikan"], "ibu": ["kue", "minyak"], "kades": ["kopi", "uang"], "nenek": ["minyak", "kue"],
	"pemuda": ["kue"], "petani": ["pupuk", "bibit_x", "kopi"], "somad": ["kopi", "ikan_mahal"], "ucok": ["ikan", "kopi"],
	"rian": ["ikan_mahal", "kue"], "wati": ["kue", "minyak"], "slamet": ["kopi", "pupuk"], "dullah": ["kopi", "ikan"],
	"lastri": ["kue"], "romlah": ["minyak", "kue"], "darsih": ["kopi", "ikan"], "yanto": ["minyak", "kopi"],
	"karta": ["pupuk", "kopi"], "bidan": ["kue", "ikan"], "rt": ["kopi", "uang"],
}
const HATES := {"pemuda": ["tbs", "bibit"], "rian": ["tbs"], "dullah": ["bibit", "tbs"], "darsih": ["tbs", "bibit"],
	"lastri": ["minyak"]}
const GIFT_KEYS := ["kopi", "kue", "minyak", "pupuk", "bibit", "tbs"]
## fetch requests: [item ("ikan" = any fish), count, text]
const REQUESTS := [
	["ikan", 1, "Bawakan saya seekor ikan buat lauk, Juragan. Apa saja, asal bukan ikan sawit."],
	["ikan", 2, "Cucu saya datang. Bisa carikan dua ekor ikan? Nanti saya bayar dengan doa."],
	["kopi", 1, "Kopi di rumah habis. Bawakan sebungkus kopi bubuk dari Koperasi, ya?"],
	["kue", 2, "Ada arisan nanti sore. Titip dua bungkus kue klepon, boleh?"],
	["minyak", 1, "Minyak goreng saya habis. Bawakan sejerigen... yang harga normal ya, hehe."],
	["pupuk", 1, "Kebun cabai saya kurus. Ada pupuk sekarung buat saya?"],
]
const LANDLESS_REQ := [["minyak", 1, "Di tenda tidak ada minyak. Bisa bawakan sejerigen? Anggap saja ganti rugi kecil."],
	["kue", 1, "Anak saya ulang tahun. Sebungkus kue klepon saja, Juragan."]]
const REPORT_LINES := ["Juragan itu pakai surat palsu, Pak! Saya lihat sendiri capnya masih basah!",
	"Lapor, Pak Satgas: kebun di desa kami 'pindah tangan' secara ajaib.",
	"Coba Bapak cek, kenapa Juragan itu kaya sekali, sementara kami makan pakai garam?",
	"Saya punya rekaman preman Bang Codet. Mau saya kirim ke grup WhatsApp Satgas?"]


func rs() -> Dictionary:
	return hub.st("rel", {})


func rec(vid: String) -> Dictionary:
	var r := rs()
	if not r.has(vid) or typeof(r[vid]) != TYPE_DICTIONARY:
		r[vid] = {}
	var d: Dictionary = r[vid]
	for k in DEF:
		if not d.has(k):
			d[k] = DEF[k].duplicate() if DEF[k] is Dictionary else DEF[k]
	if typeof(d["req"]) != TYPE_DICTIONARY:
		d["req"] = {}
	return d


func f(vid: String) -> float:
	return float(rec(vid)["f"])


func hearts(vid: String) -> int:
	return clampi(int(floor((f(vid) + 4.0) / 20.0)), 0, 5)


func add(vid: String, amount: float, show := true) -> void:
	if not GS.VILLAGERS.has(vid):
		return
	var d := rec(vid)
	var before := hearts(vid)
	d["f"] = clampf(float(d["f"]) + amount, 0.0, 100.0)
	var after := hearts(vid)
	if show and after != before and hub.world.npcs.has(vid):
		hub.world.npcs[vid].emote("<3" if after > before else "</3", 2.5)
		if after > before:
			GS.toast.emit("%s makin akrab denganmu (%d hati)" % [GS.vname(vid), after], "good")
		else:
			GS.toast.emit("%s makin benci padamu (%d hati)" % [GS.vname(vid), after], "bad")


func wrong(vid: String, amount: float) -> void:
	var d := rec(vid)
	d["wronged"] = int(d["wronged"]) + 1
	add(vid, -amount)


# ------------------------------------------------------------------ events from deals.gd
func on_event(ev: String, vid: String) -> void:
	match ev:
		"chat":
			add(vid, 5.0)
		"buy_fair":
			add(vid, 8.0)
			for o in GS.VILLAGERS:
				if o != vid:
					add(o, 2.0, false)
		"lowball_ok":
			wrong(vid, 18.0)
		"lowball_fail":
			add(vid, -10.0)
		"fraud_ok":
			# they find out the 'surat bantuan pemerintah' was a sale a few days later
			wrong(vid, 40.0)
			hub.add_stat("cheats")
		"fraud_fail":
			wrong(vid, 35.0)
			hub.add_stat("cheats")
		"evict":
			wrong(vid, 70.0)
			for o in GS.VILLAGERS:
				if o != vid:
					add(o, -8.0, false)
			hub.add_stat("cheats")
		"extort":
			wrong(vid, 55.0)
			hub.add_stat("extort")
			hub.add_stat("cheats")
		"seize_debt":
			wrong(vid, 45.0)
		"bribe_land":
			add(vid, 10.0)
		"franchise":
			add(vid, 3.0)
		"oil0":
			add(vid, 2.0, false)
		"oil1":
			add(vid, -2.0, false)
		"oil2":
			add(vid, -6.0, false)
		"hire":
			add(vid, 6.0)


# ------------------------------------------------------------------ day roll
func day_roll(report: Array) -> void:
	var reporters: Array = []
	for vid in GS.VILLAGERS:
		var d := rec(vid)
		var v: Dictionary = GS.villagers[vid]
		# long friendships cool off a little when you never visit
		if float(d["f"]) > 60.0 and int(v.get("talk_day", 0)) < GS.day - 3:
			d["f"] = float(d["f"]) - 1.0
		# requests expire
		var rq: Dictionary = d["req"]
		if not rq.is_empty() and int(rq.get("due", 0)) < GS.day:
			report.append("%s kecewa: permintaannya tidak kamu penuhi." % GS.vname(vid))
			d["f"] = maxf(0.0, float(d["f"]) - 6.0)
			d["req"] = {}
		# enemies talk to the Satgas
		if hearts(vid) <= 1 and float(d["f"]) <= 22.0 and hub.rng.randf() < 0.3:
			reporters.append(vid)
	for vid in reporters.slice(0, 2):
		GS.heat = clampf(GS.heat + 6.0, 0.0, 100.0)
		hub.add_stat("reported")
		report.append("[LAPOR] %s melapor ke Satgas: \"%s\" (Kecurigaan +6)" % [GS.vname(vid), REPORT_LINES[hub.rng.randi() % REPORT_LINES.size()]])
	# a couple of new small requests in the village
	var free: Array = []
	for vid in GS.VILLAGERS:
		if rec(vid)["req"].is_empty() and hearts(vid) >= 1 and not GS.villagers[vid].get("evicted", false):
			free.append(vid)
	free.shuffle()
	var made := 0
	for vid in free:
		if made >= 2 or hub.rng.randf() > 0.35:
			continue
		make_request(vid)
		made += 1
	if made > 0:
		report.append("Ada %d warga yang butuh bantuan kecil. Lihat daftar Warga (tombol H / Menu)." % made)


func make_request(vid: String) -> Dictionary:
	var pool: Array = LANDLESS_REQ if GS.villagers[vid]["status"] == "landless" else REQUESTS
	var r: Array = pool[hub.rng.randi() % pool.size()]
	var reward: int = 50000 * int(r[1]) + hub.rng.randi_range(0, 3) * 25000
	var q := {"item": r[0], "n": int(r[1]), "text": r[2], "due": GS.day + 3, "reward": reward}
	rec(vid)["req"] = q
	return q


func item_have(key: String) -> int:
	if key == "ikan":
		return GS.fish_count()
	return int(GS.inv.get(key, 0))


func item_name(key: String) -> String:
	if key == "ikan":
		return "ikan"
	var info: Dictionary = GS.item_info(key)
	return str(info.get("name", key))


func _take(key: String, n: int) -> bool:
	if item_have(key) < n:
		return false
	if key != "ikan":
		return GS.take_item(key, n)
	# cheapest fish first (nobody gives away the arwana for a lauk)
	var ids: Array = GS.FISH.keys()
	ids.sort_custom(func(a, b): return int(GS.FISH[a]["price"]) < int(GS.FISH[b]["price"]))
	var left := n
	for id in ids:
		while left > 0 and int(GS.inv.get(id, 0)) > 0:
			GS.take_item(id, 1)
			left -= 1
	return left == 0


# ------------------------------------------------------------------ talking
func talk_choices(vid: String, choices: Array) -> void:
	var at := choices.size()   # (deals.talk calls this right before adding "Pamit")
	var d := rec(vid)
	var extra: Array = []
	extra.append({"text": "Kasih hadiah", "hint": "sudah hari ini" if int(d["gift"]) == GS.day else "%d hati" % hearts(vid),
		"enabled": int(d["gift"]) != GS.day, "cb": func(): gift_menu(vid)})
	var rq: Dictionary = d["req"]
	if not rq.is_empty():
		var have := item_have(str(rq["item"]))
		extra.append({"text": "Soal permintaanmu...", "hint": "%s %d/%d" % [item_name(str(rq["item"])), mini(have, int(rq["n"])), int(rq["n"])],
			"cb": func(): request_dialog(vid)})
	if hearts(vid) >= 4:
		extra.append({"text": "Minta info rahasia", "hint": "sahabat", "enabled": int(d["tip"]) != GS.day, "cb": func(): give_tip(vid)})
	for k in extra.size():
		choices.insert(at + k, extra[k])


func land_choices(vid: String, choices: Array) -> void:
	if hearts(vid) < 4:
		return
	var value := int(GS.VILLAGERS[vid]["value"] * 0.7)
	choices.insert(0, {"text": "Beli harga sahabat", "hint": GS.fmt_short(value) + " • ikhlas", "enabled": GS.money >= value,
		"cb": func(): buy_friend(vid, value)})


func buy_friend(vid: String, value: int) -> void:
	if not GS.spend(value):
		return
	GS.villagers[vid]["money"] += value
	GS.add_rep(5)
	Sfx.play("cash")
	hub.deals._acquire(vid, "fair")
	hub.add_stat("friend_buy")
	hub.deals.say(hub.deals.vp(vid), GS.vname(vid),
		"Karena Juragan sudah seperti keluarga sendiri, kebun ini saya lepas dengan harga sahabat. Rawat baik-baik, ya. Jangan dijadikan tempat parkir truk.")


func gift_menu(vid: String) -> void:
	var choices: Array = []
	for key in GIFT_KEYS:
		var n := int(GS.inv.get(key, 0))
		if n > 0:
			choices.append({"text": item_name(key), "hint": "punya %d" % n, "cb": func(): give(vid, key)})
	var best := ""
	for id in GS.fish_ids_sorted():
		if int(GS.inv.get(id, 0)) > 0:
			best = id   # the rarest fish in the bag is offered last
	var cheap := ""
	for id in GS.fish_ids_sorted():
		if int(GS.inv.get(id, 0)) > 0:
			cheap = id
			break
	if cheap != "":
		choices.append({"text": GS.FISH[cheap]["name"], "hint": GS.RARITY[GS.fish_rarity(cheap)]["name"], "cb": func(): give(vid, cheap)})
	if best != "" and best != cheap:
		choices.append({"text": GS.FISH[best]["name"], "hint": GS.RARITY[GS.fish_rarity(best)]["name"], "cb": func(): give(vid, best)})
	if choices.is_empty():
		hub.deals.say(hub.deals.vp(vid), GS.vname(vid), "Tasmu kosong, Juragan. Hadiah itu dari hati... tapi biasanya juga dari Koperasi. (Beli kopi bubuk atau kue klepon di Koperasi.)")
		return
	choices.append({"text": "Tidak jadi", "cb": Callable()})
	hub.ui.dialog(hub.deals.vp(vid), GS.vname(vid), "Hadiah? Untuk saya? Wah, jangan repot-repot... (matanya melirik tasmu)", choices,
		func(): hub.deals._end_talk(vid))


func gift_value(vid: String, key: String) -> float:
	var likes: Array = LIKES.get(vid, [])
	var hates: Array = HATES.get(vid, [])
	if key in hates:
		return -12.0
	var base := 8.0
	if GS.FISH.has(key):
		var rar := GS.fish_rarity(key)
		base = {"N": 8.0, "R": 12.0, "SR": 20.0, "SSR": 30.0}[rar]
		if "ikan" in likes or ("ikan_mahal" in likes and rar != "N"):
			base *= 2.0
		return base
	if key == "tbs":
		return 1.0
	if key in likes:
		base *= 2.0
	return base


func give(vid: String, key: String) -> void:
	if int(GS.inv.get(key, 0)) <= 0:
		return
	GS.take_item(key, 1)
	var d := rec(vid)
	d["gift"] = GS.day
	var v := gift_value(vid, key)
	add(vid, v)
	hub.add_stat("gifts")
	Sfx.play("pop")
	var line: String
	if v < 0:
		line = "%s? Untuk saya? Juragan sedang menyindir saya, ya? (Dia tersinggung.)" % item_name(key)
		if key == "tbs":
			line = "Buah sawit?! Saya ini manusia, bukan pabrik! (Dia tersinggung berat.)"
	elif v >= 16.0:
		line = "Wah! %s! Ini kesukaan saya! Juragan kok tahu? Terima kasih banyak!" % item_name(key)
	elif key == "tbs":
		line = "...Sebutir tandan sawit. Terima kasih. Akan saya pajang. Mungkin."
	else:
		line = "Terima kasih, Juragan. %s ini pasti berguna." % item_name(key)
	hub.deals.say(hub.deals.vp(vid), GS.vname(vid), line + "\n(Pertemanan %+d)" % int(v))


func request_dialog(vid: String) -> void:
	var rq: Dictionary = rec(vid)["req"]
	if rq.is_empty():
		return
	var key := str(rq["item"])
	var n := int(rq["n"])
	var have := item_have(key)
	var choices: Array = []
	choices.append({"text": "Serahkan %d %s" % [n, item_name(key)], "hint": "punya %d" % have, "enabled": have >= n,
		"cb": func(): fulfil(vid)})
	choices.append({"text": "Nanti saya bawakan", "cb": Callable()})
	hub.ui.dialog(hub.deals.vp(vid), GS.vname(vid), "%s (Batas: hari ke-%d, imbalan %s)" % [str(rq["text"]), int(rq["due"]), GS.fmt_short(int(rq["reward"]))],
		choices, func(): hub.deals._end_talk(vid))


func fulfil(vid: String) -> bool:
	var d := rec(vid)
	var rq: Dictionary = d["req"]
	if rq.is_empty() or not _take(str(rq["item"]), int(rq["n"])):
		return false
	d["req"] = {}
	add(vid, 15.0)
	GS.add_money(int(rq["reward"]))
	GS.add_rep(2)
	hub.add_stat("requests")
	Sfx.play("quest")
	hub.deals.say(hub.deals.vp(vid), GS.vname(vid), "Alhamdulillah, Juragan baik sekali! Ini sedikit ucapan terima kasih: %s. (Pertemanan +15)" % GS.fmt_short(int(rq["reward"])))
	return true


func give_tip(vid: String) -> String:
	var d := rec(vid)
	d["tip"] = GS.day
	var kinds: Array = ["harga", "ikan", "heat", "makan"]
	if hub.jour.active():
		kinds.append("jurnal")
	var kind: String = kinds[hub.rng.randi() % kinds.size()]
	var line := ""
	match kind:
		"harga":
			GS.tbs_trend = 1 if hub.rng.randf() < 0.7 else -1
			line = "Psst... sopir truk pabrik bilang harga TBS besok %s. Jangan bilang siapa-siapa." % ("NAIK" if GS.tbs_trend > 0 else "TURUN")
		"ikan":
			line = "Rahasia nelayan: Arwana Emas muncul subuh (05-08) dan magrib (17.30-20) di sungai. Ikan Raja Sawit cuma tengah malam."
		"heat":
			GS.add_heat(-8)
			line = "Nama Juragan ada di laporan RT minggu ini. Tenang, kertasnya sudah saya pakai bungkus gorengan. (Kecurigaan -8)"
		"makan":
			GS.energy = minf(GS.max_energy, GS.energy + 25.0)
			GS.stats_changed.emit()
			line = "Info rahasia? Ini: pisang goreng buatan saya paling enak se-dusun. Makan dulu, Juragan. (Energi +25)"
		"jurnal":
			line = "Wartawan Dimas tadi tanya-tanya soal %s. Buktinya sudah %d dari 3. Hati-hati, Juragan." % [hub.jour.topic_name(), hub.jour.lead()]
	hub.add_stat("tips")
	hub.deals.say(hub.deals.vp(vid), GS.vname(vid), line)
	return kind


# ------------------------------------------------------------------ shops
func toko_items(items: Array) -> void:
	items.append({"icon": "icon_kopi", "text": "Kopi bubuk (oleh-oleh)", "desc": "Hadiah untuk warga. Bapak-bapak suka. Punya: %d." % int(GS.inv.get("kopi", 0)),
		"price": GS.fmt_short(20000), "cb": func(): hub.deals._buy("kopi", 1, 20000, hub.deals.open_toko)})
	items.append({"icon": "icon_kue", "text": "Kue klepon (oleh-oleh)", "desc": "Hadiah manis untuk warga. Punya: %d." % int(GS.inv.get("kue", 0)),
		"price": GS.fmt_short(15000), "cb": func(): hub.deals._buy("kue", 1, 15000, hub.deals.open_toko)})


# ------------------------------------------------------------------ UI
func attach_hearts(name_label: Label, vid: String) -> void:
	if name_label == null or not is_instance_valid(name_label):
		return
	var parent := name_label.get_parent()
	if parent == null or parent.has_node("HeartsRow"):
		return
	var row := HBoxContainer.new()
	row.name = "HeartsRow"
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 10)
	var idx := name_label.get_index()
	parent.remove_child(name_label)
	row.add_child(name_label)
	var h := Hearts.new()
	h.value = hearts(vid)
	h.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(h)
	parent.add_child(row)
	parent.move_child(row, idx)


func show_panel() -> void:
	var ui: Node = hub.ui
	if ui.modal:
		return
	var panel := PanelContainer.new()
	panel.name = "WargaPanel"
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var vp: Vector2 = ui.root.get_viewport_rect().size
	var w := minf(720.0, vp.x - 60.0)
	var title: Label = ui._title_label("Warga Sukamakmur", ui.TITLE_BROWN, 30)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var friends := 0
	for vid in GS.VILLAGERS:
		if hearts(vid) >= 4:
			friends += 1
	col.add_child(ui._hrow([ui._icon_rect("icon_hati", 44), title, ui._chip("icon_hati", "%d sahabat" % friends)], 12))
	col.add_child(ui._divider())
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 6)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var ids: Array = GS.VILLAGERS.keys()
	ids.sort_custom(func(a, b): return f(a) > f(b))
	for vid in ids:
		list.add_child(_row(vid, w))
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(w, minf(ids.size() * 70.0, vp.y - 250.0))
	scroll.add_child(list)
	col.add_child(scroll)
	var hint: Label = ui._label("Naikkan pertemanan: ngobrol tiap hari, kasih hadiah (kopi, kue, ikan...), penuhi permintaan kecil. Sahabat (4 hati) mau jual kebun harga sahabat & kasih info rahasia. Musuh (0-1 hati) melapor ke Satgas.", 15, ui.BROWN_SOFT)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size = Vector2(w, 0)
	col.add_child(hint)
	var close_b: Button = ui.button("Tutup", ui.close, true, 180)
	close_b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(close_b)
	ui._open_modal(panel, true)


func _row(vid: String, w: float) -> Control:
	var ui: Node = hub.ui
	var row := PanelContainer.new()
	row.name = "warga_" + vid
	var rs_box: StyleBoxFlat = ui._box(ui.CREAM_LIGHT, 16, ui.LINE, 2)
	ui._margins(rs_box, 8, 5, 12, 5)
	row.add_theme_stylebox_override("panel", rs_box)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 10)
	row.add_child(h)
	var model := str(GS.VILLAGERS[vid]["model"]).replace("char_", "")
	h.add_child(ui._icon_rect("portrait_" + model, 46))
	var tc := VBoxContainer.new()
	tc.add_theme_constant_override("separation", 0)
	tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v: Dictionary = GS.villagers[vid]
	var stt := "punya kebun"
	if v["status"] == "landless":
		stt = "digusur, tinggal di tenda" if v.get("evicted", false) else "tanpa lahan"
	elif GS.parcel_of(vid)["plasma"]:
		stt = "mitra franchise"
	var hrow := HBoxContainer.new()
	hrow.add_theme_constant_override("separation", 10)
	hrow.add_child(ui._label(GS.vname(vid), 19, ui.BROWN, true))
	var hs := Hearts.new()
	hs.value = hearts(vid)
	hs.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hrow.add_child(hs)
	tc.add_child(hrow)
	var rq: Dictionary = rec(vid)["req"]
	var sub := stt + " • pertemanan %d" % int(f(vid))
	if not rq.is_empty():
		sub += " • minta: %d %s (hari ke-%d)" % [int(rq["n"]), item_name(str(rq["item"])), int(rq["due"])]
	if int(rec(vid)["wronged"]) > 0:
		sub += " • pernah kamu rugikan"
	var sl: Label = ui._label(sub, 14, ui.BROWN_SOFT)
	sl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	sl.custom_minimum_size = Vector2(w - 120.0, 0)
	tc.add_child(sl)
	h.add_child(tc)
	return row


class Hearts extends Control:
	## 5 little hearts, `value` of them filled
	var value := 0
	var hs := 16.0

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		custom_minimum_size = Vector2(5 * hs + 4 * 3.0, hs)

	func _draw() -> void:
		for k in 5:
			var c := Vector2(k * (hs + 3.0) + hs * 0.5, hs * 0.52)
			_heart(c, hs * 0.5 + 1.5, Color("6a3a18"))
			_heart(c, hs * 0.5, Color("e64c5c") if k < value else Color("ead9c0"))

	func _heart(c: Vector2, r: float, col: Color) -> void:
		var pts := PackedVector2Array()
		for n in 28:
			var t := n / 28.0 * TAU
			var x := 16.0 * pow(sin(t), 3)
			var y := 13.0 * cos(t) - 5.0 * cos(2.0 * t) - 2.0 * cos(3.0 * t) - cos(4.0 * t)
			pts.append(c + Vector2(x, -y) * (r / 16.0))
		draw_colored_polygon(pts, col)
