extends Node
## UI for the systems round (logic in scripts/systems/): the HUD weather / TBS-price pill,
## the 14-day price chart and the "main mata" bribe in the pabrik menu, the gudang menu
## (at the shed beside your first parcel), the workers panel and the upgrade tree
## (both from the Kantor), and the systems' morning events (mogok, kabut asap, banjir,
## ikan mati). Built from ui.gd's helpers so it looks like the rest of the HUD.

const BLUE := Color("3a74c0")

var world: Node
var ui: Node
var pill: PanelContainer
var wx_icon: WeatherIcon
var wx_label: Label
var price_label: Label
var _sig := ""


func _ready() -> void:
	_build_pill()
	_add_gudang_spot()
	GS.stats_changed.connect(_refresh)
	GS.day_started.connect(func(_r): _refresh())
	_refresh()


# ------------------------------------------------------------------ HUD pill
class WeatherIcon extends Control:
	## a small hand-drawn weather glyph (no icon art needed): sun, cloud, rain, storm, smoke
	var kind := "cerah"
	var smoke := false
	var night := false

	func _draw() -> void:
		var s := minf(size.x, size.y)
		var o := (size - Vector2(s, s)) * 0.5
		var ink := Color("4a2f1d")
		match kind:
			"cerah":
				_sun(o + Vector2(s * 0.5, s * 0.5), s * 0.24, ink)
			"berawan":
				_sun(o + Vector2(s * 0.64, s * 0.36), s * 0.17, ink)
				_cloud(o + Vector2(s * 0.44, s * 0.6), s * 0.34, Color("fffaf0"), ink)
			"hujan":
				_cloud(o + Vector2(s * 0.5, s * 0.42), s * 0.36, Color("dfe6ee"), ink)
				for i in 3:
					var x := o.x + s * (0.3 + 0.2 * i)
					draw_line(Vector2(x, o.y + s * 0.66), Vector2(x - s * 0.07, o.y + s * 0.9), Color("3a74c0"), maxf(2.0, s * 0.07), true)
			"badai":
				_cloud(o + Vector2(s * 0.5, s * 0.4), s * 0.38, Color("8d97a5"), ink)
				var b := PackedVector2Array([o + Vector2(s * 0.52, s * 0.52), o + Vector2(s * 0.36, s * 0.76),
					o + Vector2(s * 0.5, s * 0.76), o + Vector2(s * 0.42, s * 0.98), o + Vector2(s * 0.68, s * 0.68),
					o + Vector2(s * 0.54, s * 0.68), o + Vector2(s * 0.62, s * 0.52)])
				draw_colored_polygon(b, Color("f2b43e"))
				draw_polyline(b + PackedVector2Array([b[0]]), ink, 1.5, true)
		if smoke:
			for i in 3:
				draw_circle(o + Vector2(s * (0.2 + 0.3 * i), s * (0.88 - 0.05 * i)), s * 0.13, Color(0.55, 0.5, 0.42, 0.75))

	func _sun(c: Vector2, r: float, ink: Color) -> void:
		var col := Color("f2b43e") if not night else Color("f4e6b0")
		for i in 8:
			var a := TAU * i / 8.0
			draw_line(c + Vector2(cos(a), sin(a)) * r * 1.35, c + Vector2(cos(a), sin(a)) * r * 1.8, col.darkened(0.15), maxf(2.0, r * 0.28), true)
		draw_circle(c, r + 1.5, ink)
		draw_circle(c, r, col)

	func _cloud(c: Vector2, w: float, fill: Color, ink: Color) -> void:
		var parts := [[Vector2(-0.45, 0.12), 0.38], [Vector2(0.0, -0.1), 0.52], [Vector2(0.45, 0.1), 0.4]]
		for p in parts:
			draw_circle(c + p[0] * w, p[1] * w + 1.6, ink)
		draw_rect(Rect2(c + Vector2(-0.45, 0.05) * w - Vector2(0, 1.6), Vector2(0.9 * w, 0.45 * w + 3.2)), ink)
		for p in parts:
			draw_circle(c + p[0] * w, p[1] * w, fill)
		draw_rect(Rect2(c + Vector2(-0.45, 0.05) * w, Vector2(0.9 * w, 0.45 * w)), fill)


func _build_pill() -> void:
	wx_icon = WeatherIcon.new()
	wx_icon.name = "WeatherIcon"
	wx_icon.custom_minimum_size = Vector2(38, 38)
	wx_icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	wx_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wx_label = ui._label("", 16, ui.BROWN, true)
	price_label = ui._label("", 15, ui.BROWN_SOFT, true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 0)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	col.add_child(wx_label)
	col.add_child(price_label)
	pill = ui._pill(ui._hrow([wx_icon, col], 8), ui.CREAM, 4, 16)
	pill.name = "WeatherPill"
	# beside the energy meter in the top-left cluster
	var n: Node = ui.energy_bar
	while n and n.get_parent() and str(n.get_parent().name) != "TopLeft":
		n = n.get_parent()
	if n and n.get_parent():
		n.add_child(pill)
	else:
		ui.hud.add_child(pill)


func _refresh() -> void:
	if pill == null:
		return
	var W = GS.sys.weather
	var M = GS.sys.market
	var ch: int = M.change()
	var night: bool = GS.hour >= 18.5 or GS.hour < 5.5
	var sig := "%s|%d|%d|%d|%d|%s" % [W.today, GS.day, GS.tbs_price, ch, W.fires.size(), night]
	if sig == _sig:
		return
	_sig = sig
	wx_icon.kind = W.today
	wx_icon.smoke = W.haze() > 0.05
	wx_icon.night = night
	wx_icon.queue_redraw()
	var hint := ""
	if not W.fires.is_empty():
		hint = " • %d titik api!" % W.fires.size()
	wx_label.text = "%s • %s %d/%d%s" % [W.weather_name(), W.season_name(), W.season_day(), W.SEASON_DAYS, hint]
	wx_label.add_theme_color_override("font_color", ui.RED if not W.fires.is_empty() else ui.BROWN)
	var arrow := ""
	if ch > 0:
		arrow = "  naik +" + GS.fmt_short(ch).trim_prefix("Rp ")
	elif ch < 0:
		arrow = "  turun -" + GS.fmt_short(-ch).trim_prefix("Rp ")
	price_label.text = "Harga TBS %s%s" % [GS.fmt_short(GS.tbs_price), arrow]
	price_label.add_theme_color_override("font_color", Color("3f7f2a") if ch > 0 else (ui.RED if ch < 0 else ui.BROWN_SOFT))


# ------------------------------------------------------------------ price chart
class PriceChart extends Control:
	## the last 14 days of the mill price; wet-season days have a blue band, dry ones tan
	var values: Array = []
	var days: Array = []      # the day number of each value
	var avg := 0
	var font: Font

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		var bg := StyleBoxFlat.new()
		bg.bg_color = Color("fffaf0")
		bg.border_color = Color("d8c29a")
		bg.set_border_width_all(2)
		bg.set_corner_radius_all(16)
		draw_style_box(bg, r)
		if values.is_empty():
			return
		var left := 74.0
		var right := 16.0
		var top := 30.0
		var bottom := 26.0
		var plot := Rect2(left, top, size.x - left - right, size.y - top - bottom)
		var lo := INF
		var hi := -INF
		for v in values:
			lo = minf(lo, float(v))
			hi = maxf(hi, float(v))
		lo = minf(lo, avg)
		hi = maxf(hi, avg)
		var pad := maxf(6000.0, (hi - lo) * 0.15)
		lo -= pad
		hi += pad
		var n := values.size()
		var step := plot.size.x / maxf(1.0, float(HISTORY_N - 1))
		var x0 := plot.end.x - step * (n - 1)
		# season bands
		for i in n:
			var d: int = days[i]
			var wet := ((d - 1) / WeatherSys.SEASON_DAYS) % 2 == 0
			var bx0 := maxf(x0 + step * (i - 0.5), plot.position.x)
			var bx1 := minf(x0 + step * (i + 0.5), plot.end.x)
			if bx1 <= bx0:
				continue
			var band := Rect2(bx0, plot.position.y, bx1 - bx0, plot.size.y)
			draw_rect(band, Color(0.62, 0.76, 0.92, 0.22) if wet else Color(0.93, 0.78, 0.5, 0.22))
		# grid + labels
		var fs := 14
		for k in 3:
			var v := lerpf(lo, hi, k / 2.0)
			var y := plot.end.y - plot.size.y * k / 2.0
			draw_line(Vector2(plot.position.x, y), Vector2(plot.end.x, y), Color(0.85, 0.77, 0.6, 0.7), 1.0)
			if font:
				draw_string(font, Vector2(8, y + 5), GS.fmt_short(int(v)), HORIZONTAL_ALIGNMENT_LEFT, left - 12, fs, Color("8a6a4a"))
		var ya := plot.end.y - (avg - lo) / (hi - lo) * plot.size.y
		draw_dashed_line(Vector2(plot.position.x, ya), Vector2(plot.end.x, ya), Color("e8953a"), 2.0, 8.0)
		if font:
			draw_string(font, Vector2(plot.position.x + 4, ya - 5), "rata-rata", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("c07a2a"))
		# the line
		var pts := PackedVector2Array()
		for i in n:
			pts.append(Vector2(x0 + step * i, plot.end.y - (float(values[i]) - lo) / (hi - lo) * plot.size.y))
		if pts.size() >= 2:
			draw_polyline(pts, Color("4a2f1d"), 4.0, true)
			draw_polyline(pts, Color("5c8a3a"), 2.4, true)
		for i in pts.size():
			draw_circle(pts[i], 3.5 if i < pts.size() - 1 else 6.5, Color("4a2f1d"))
			draw_circle(pts[i], 2.0 if i < pts.size() - 1 else 4.5, Color("f2b43e") if i == pts.size() - 1 else Color("fffaf0"))
		if font and not pts.is_empty():
			var last := pts[pts.size() - 1]
			var txt := GS.fmt_short(int(values[n - 1]))
			var tw := font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
			draw_string(font, Vector2(clampf(last.x - tw * 0.5, left, size.x - tw - 6), maxf(last.y - 12, 17)), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("4a2f1d"))
			draw_string(font, Vector2(plot.position.x, size.y - 7), "%d hari lalu" % (n - 1) if n > 1 else "", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("8a6a4a"))
			draw_string(font, Vector2(plot.end.x - 58, size.y - 7), "hari ini", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("8a6a4a"))
		if font:
			draw_string(font, Vector2(left, 20), "Harga TBS 14 hari", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("4a2f1d"))
			draw_string(font, Vector2(size.x - 236, 20), "biru: musim hujan • cokelat: kemarau", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("8a6a4a"))

	const HISTORY_N := 14


func price_chart(w := 600.0, h := 170.0) -> Control:
	var M = GS.sys.market
	M.sync_today()
	var c := PriceChart.new()
	c.name = "PriceChart"
	c.values = M.history.duplicate()
	for i in c.values.size():
		c.days.append(GS.day - (c.values.size() - 1 - i))
	c.avg = M.average()
	c.font = ui._font_semi
	c.custom_minimum_size = Vector2(w, h)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


# ------------------------------------------------------------------ shared row builder
func _row(icon_name: String, title: String, lines: Array, buttons: Array, extra: Control = null) -> Control:
	var row := PanelContainer.new()
	var rs: StyleBoxFlat = ui._box(ui.CREAM_LIGHT, 18, ui.LINE, 2)
	ui._margins(rs, 10, 8, 12, 8)
	row.add_theme_stylebox_override("panel", rs)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	row.add_child(h)
	var ib := PanelContainer.new()
	var ibs: StyleBoxFlat = ui._box(Color("f3e4c4"), 28)
	ui._margins(ibs, 4, 4, 4, 4)
	ib.add_theme_stylebox_override("panel", ibs)
	ib.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	ib.add_child(ui._icon_rect(icon_name, 44))
	h.add_child(ib)
	var tc := VBoxContainer.new()
	tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	tc.add_theme_constant_override("separation", 1)
	tc.add_child(ui._label(title, 20, ui.BROWN, true))
	for l in lines:
		var s := str(l)
		var col: Color = ui.BROWN_SOFT
		if s.begins_with("!"):
			s = s.substr(1)
			col = ui.RED
		elif s.begins_with("+"):
			s = s.substr(1)
			col = Color("3f7f2a")
		var dl: Label = ui._label(s, 15, col)
		dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		tc.add_child(dl)
	if extra:
		tc.add_child(extra)
	h.add_child(tc)
	if not buttons.is_empty():
		var bc := VBoxContainer.new()
		bc.add_theme_constant_override("separation", 6)
		bc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		for b in buttons:
			(b as Button).add_theme_font_size_override("font_size", 17)
			bc.add_child(b)
		h.add_child(bc)
	return row


func _btn(text: String, cb: Callable, enabled := true, primary := true) -> Button:
	var b: Button = ui.button(text, cb, enabled, 150, primary)
	b.custom_minimum_size.y = 42
	return b


# ------------------------------------------------------------------ pabrik additions
func pabrik_items(items: Array) -> void:
	## deals.open_pabrik: chart first, then gudang sale and the bribe
	var M = GS.sys.market
	items.push_front({"node": price_chart(minf(680.0, ui.root.get_viewport_rect().size.x - 90.0), 170.0)})
	var stock: int = M.stock()
	if stock > 0:
		items.append({"icon": "icon_truk", "text": "Jual stok gudang (%d tandan)" % stock,
			"desc": "Diangkut pikap pabrik, ongkos 5%%. Mutu turun tiap hari (sortasi): tertua %d hari." % M.oldest_age(),
			"price": GS.fmt_short(int(M.value() * 0.95)), "button": "Jual", "cb": func(): sell_gudang(0.95, Callable(world.deals, "open_pabrik"))})
	var bribed: bool = M.bribed()
	items.append({"icon": "icon_uang", "text": "Main mata dengan Pak Gondrong" if not bribed else "Timbangan sudah 'disetel' hari ini",
		"desc": "Mandor timbangan pabrik. Selipkan amplop: hari ini TBS-mu 'lebih berat' 15%%. Kecurigaan +%d, kalau ketahuan lebih." % int(M.BRIBE_HEAT) if not bribed
			else "Semua TBS yang kamu jual hari ini dihargai %s/tandan." % GS.fmt_rp(M.sale_price()),
		"price": GS.fmt_short(M.BRIBE_COST) if not bribed else "",
		"button": "Selipkan", "enabled": not bribed and GS.money >= M.BRIBE_COST, "cb": func(): bribe_foreman()})


func bribe_foreman() -> void:
	var res: String = GS.sys.market.bribe()
	if res == "":
		return
	Sfx.play("cash")
	if res == "caught":
		GS.toast.emit("Pak Gondrong menerima amplop... dan Rian merekamnya dari balik truk. Kecurigaan naik!", "bad")
	else:
		GS.toast.emit("Pak Gondrong mengedip. 'Timbangannya lagi rusak, Bos. Rusak ke arah yang baik.'", "good")
	ui.refresh_menu(Callable(world.deals, "open_pabrik"))


func sell_gudang(mult: float, reopen: Callable) -> int:
	var got: int = GS.sys.market.sell_gudang(mult)
	if got > 0:
		Sfx.play("cash")
		world.float_text(world.player.global_position, "+" + GS.fmt_short(got), Color("2f6d2a"))
		if reopen.is_valid():
			ui.refresh_menu(reopen)
	return got


# ------------------------------------------------------------------ gudang
func _add_gudang_spot() -> void:
	if not world.door_points.has("gudang"):
		return
	var d: Vector3 = world.door_points["gudang"]
	world.interactables.append({"pos": d, "r": 2.4,
		"prompt": func(): return "Buka gudang TBS (%d/%d)" % [GS.sys.market.stock(), GS.sys.market.capacity()],
		"act": func(): open_gudang()})


func open_gudang() -> void:
	Sfx.play("door", 1.0, -6.0)
	var M = GS.sys.market
	var T = GS.sys.tech
	var tbs := int(GS.inv.get("tbs", 0))
	var items: Array = []
	var lines: Array = []
	if M.gudang.is_empty():
		lines.append("Gudang kosong. Buruhmu menaruh hasil panen di sini tiap pagi.")
	else:
		for b in M.gudang:
			var age := int(b[1])
			var q: float = M.quality(age)
			var warn := ""
			if age >= M.max_age():
				warn = "!"
			lines.append("%s%d tandan • umur %d hari • mutu %d%%%s" % [warn, int(b[0]), age, int(round(q * 100.0)),
				" • BESOK BUSUK" if age >= M.max_age() else ""])
	if M.formalin():
		lines.append("Disemprot formalin: tidak akan busuk. Jangan tanya baunya.")
	items.append({"node": _row("icon_tbs", "Stok %d/%d tandan • nilai hari ini %s" % [M.stock(), M.capacity(), GS.fmt_short(M.value())], lines, [])})
	items.append({"icon": "icon_tbs", "text": "Simpan TBS bawaan (%d)" % tbs, "desc": "Tunggu harga bagus... asal tidak keburu busuk.",
		"button": "Simpan", "enabled": tbs > 0 and M.room() > 0, "cb": func():
			var k: int = M.store(int(GS.inv["tbs"]))
			GS.take_item("tbs", k)
			Sfx.play("pop")
			ui.refresh_menu(open_gudang)})
	var space: int = GS.capacity() - tbs
	items.append({"icon": "icon_gerobak", "text": "Ambil TBS ke bawaan", "desc": "Yang paling segar dulu. Muat %d lagi." % maxi(space, 0),
		"button": "Ambil", "enabled": M.stock() > 0 and space > 0, "cb": func():
			var k: int = M.take(GS.capacity() - int(GS.inv["tbs"]))
			GS.add_item("tbs", k)
			Sfx.play("pop")
			ui.refresh_menu(open_gudang)})
	if M.stock() > 0:
		items.append({"icon": "icon_truk", "text": "Panggil pikap pabrik", "desc": "Jual semua stok gudang di tempat, ongkos angkut 5%. Harga hari ini " + GS.fmt_short(M.sale_price()) + "/tandan.",
			"price": GS.fmt_short(int(M.value() * 0.95)), "button": "Jual", "cb": func(): sell_gudang(0.95, open_gudang)})
	if T.oil_ready():
		var avail: int = tbs + M.stock()
		var n := mini(avail, 10)
		var cost: int = T.OIL_COST[T.level("pabrik")]
		items.append({"icon": "icon_minyak", "text": "Pabrik mini: olah %d TBS jadi minyak" % n,
			"desc": "1 TBS → %d jerigen (bawaan dulu, lalu stok tertua). Biaya olah %s/TBS%s." % [T.OIL_PER_TBS, GS.fmt_short(cost),
				", limbah langsung ke sungai" if T.level("pabrik") == "kotor" else ", limbah diolah IPAL"],
			"price": GS.fmt_short(cost * n), "button": "Olah", "enabled": n > 0, "cb": func():
				var done: int = T.mill(10)
				if done > 0:
					Sfx.play("pop")
					GS.toast.emit("Pabrik mini menggiling %d TBS: +%d jerigen minyak goreng." % [done, done * T.OIL_PER_TBS], "good")
				ui.refresh_menu(open_gudang)})
		var oil := int(GS.inv.get("minyak", 0))
		items.append({"icon": "icon_minyak", "text": "Jual minyak ke agen kota (%d jerigen)" % oil,
			"desc": "Rp 40rb/jerigen, diangkut agen. Atau jual mahal ke warga... mereka tidak punya pilihan.",
			"price": GS.fmt_short(oil * T.OIL_AGENT_PRICE), "button": "Jual", "enabled": oil > 0, "cb": func():
				var got: int = T.sell_oil_agent()
				if got > 0:
					Sfx.play("cash")
				ui.refresh_menu(open_gudang)})
	else:
		items.append({"icon": "icon_minyak", "text": "Pabrik Minyak Mini (belum ada)", "desc": "Upgrade di Kantor: olah TBS jadi minyak goreng sendiri, 1 TBS → 4 jerigen."})
	ui.menu("Gudang TBS", "Bawaan: %d/%d TBS • Minyak: %d jerigen" % [tbs, GS.capacity(), int(GS.inv.get("minyak", 0))], items, Callable(), "portrait_buruh")


# ------------------------------------------------------------------ kantor additions
func kantor_items(items: Array) -> void:
	var C = GS.sys.crew
	C.normalize()
	var n: int = GS.workers.size()
	var mood := ""
	if n > 0:
		mood = " Kepuasan rata-rata %d%%%s." % [int(C.avg_sat()), " (MOGOK!)" if C.strike else ""]
	items.push_front({"icon": "icon_kunci", "text": "Upgrade kebun & pabrik mini",
		"desc": "Bibit unggul, pupuk premium, jalan kebun, truk angkut, gudang besar, pabrik minyak mini. Versi bersih atau... kotor.",
		"button": "Buka", "cb": func(): open_upgrades()})
	items.push_front({"icon": "icon_helm", "text": "Kelola pekerja (%d/%d)" % [n, GS.MAX_WORKERS],
		"desc": "Buruh panen, mandor, sopir truk. Upah harian %s.%s" % [GS.fmt_short(C.daily_wages()), mood],
		"button": "Buka", "cb": func(): open_workers()})


# ------------------------------------------------------------------ workers panel
func open_workers() -> void:
	var C = GS.sys.crew
	C.normalize()
	var items: Array = []
	var pay_names := []
	for p in C.PAY:
		pay_names.append(p["name"])
	items.append({"icon": "icon_uang", "text": "Gaji: %s (%d%% UMR kebun)" % [C.PAY[C.pay_level]["name"], int(C.PAY[C.pay_level]["mult"] * 100)],
		"desc": "Hemat 60%: kerja lambat & bisa mogok • Standar • Layak 135%: semangat penuh. Buruh warga tergusur dibayar lebih murah lagi.",
		"button": "Ubah", "cb": func():
			C.set_pay((C.pay_level + 1) % C.PAY.size())
			ui.refresh_menu(open_workers)})
	for role in C.ROLES:
		var r: Dictionary = C.ROLES[role]
		var desc: String = r["desc"]
		if role == "sopir" and not GS.sys.tech.owned("truk"):
			desc += " (Truk Angkut belum dibeli.)"
		items.append({"icon": r["icon"], "text": "Rekrut %s (%d/%d)" % [r["name"].to_lower(), C.count(role), int(r["max"])],
			"desc": desc, "price": GS.fmt_short(int(round(int(r["wage"]) * float(C.PAY[C.pay_level]["mult"]) / 1000.0)) * 1000) + "/hari",
			"button": "Rekrut", "enabled": C.can_hire(role), "cb": func():
				var w: Dictionary = C.hire(role)
				if not w.is_empty():
					Sfx.play("coin")
					GS.toast.emit("%s mulai kerja besok pagi." % w["name"], "good")
					world.refresh_workers()
				ui.refresh_menu(open_workers)})
	if not C.last_work.is_empty():
		var lw: Dictionary = C.last_work
		items.append({"node": _row("icon_tbs", "Hasil kerja pagi ini",
			["Panen %d TBS (%d ke gudang) • tanam %d bibit • tebas %d semak" % [lw.get("harvest", 0), lw.get("stored", 0), lw.get("planted", 0), lw.get("cleared", 0)]], [])})
	for i in GS.workers.size():
		var w: Dictionary = GS.workers[i]
		var sat := float(w["sat"])
		var bar: ProgressBar = ui._bar(ui.BAR_GREEN if sat >= 60 else (ui.BAR_GOLD if sat >= 35 else ui.BAR_RED), 220, 12)
		bar.value = sat
		var idx := i
		var role: Dictionary = C.ROLES[w["role"]]
		var lines: Array = ["%s • upah %s/hari%s" % [role["name"], GS.fmt_short(int(w["wage"])), " • warga tergusur" if str(w.get("vid", "")) != "" else ""],
			("!" if sat < 35 else ("+" if sat >= 75 else "")) + "Kepuasan %d%%: %s" % [int(sat), C.mood(sat)]]
		items.append({"node": _row(role["icon"], str(w["name"]), lines, [_btn("Pecat", func():
			var gone: Dictionary = C.fire(idx)
			if not gone.is_empty():
				Sfx.play("bad", 1.0, -6.0)
				GS.toast.emit("%s dipecat. Buruh lain saling pandang." % gone["name"], "info")
				world.refresh_workers()
			ui.refresh_menu(open_workers), true, false)], bar)})
	var sub := "Pekerja %d/%d • Upah harian %s" % [GS.workers.size(), GS.MAX_WORKERS, GS.fmt_short(C.daily_wages())]
	if C.strike:
		sub += " • SEDANG MOGOK"
	ui.menu("Pekerja Kebun", sub, items, Callable(), "portrait_buruh")


# ------------------------------------------------------------------ upgrade tree
func open_upgrades() -> void:
	var T = GS.sys.tech
	var items: Array = []
	for id in T.ORDER:
		var u: Dictionary = T.TREE[id]
		var lv: String = T.level(id)
		var lines: Array = [u["desc"]]
		var buttons: Array = []
		var title: String = u["name"]
		if lv == "bersih":
			title += " (bersih, terpasang)"
			lines.append("+" + u["bersih"]["label"] + ": " + u["bersih"]["desc"])
		elif not T.unlocked(id):
			lines.append("!Butuh dulu: " + T.TREE[u["needs"]]["name"])
		else:
			if lv == "kotor":
				title += " (kotor, terpasang)"
				lines.append("!" + u["kotor"]["label"] + ": " + u["kotor"]["desc"])
			else:
				lines.append("Bersih (%s): %s" % [u["bersih"]["label"], u["bersih"]["desc"]])
				lines.append("Kotor (%s): %s" % [u["kotor"]["label"], u["kotor"]["desc"]])
			var bid: String = id
			var pb: int = u["bersih"]["price"]
			buttons.append(_btn(("Legalkan " if lv == "kotor" else "Bersih ") + GS.fmt_short(pb), func(): _buy(bid, "bersih"), GS.money >= pb))
			if lv == "":
				var pk: int = u["kotor"]["price"]
				buttons.append(_btn("Kotor " + GS.fmt_short(pk), func(): _buy(bid, "kotor"), GS.money >= pk, false))
		items.append({"node": _row(u["icon"], title, lines, buttons)})
	ui.menu("Upgrade Kebun", "Bersih = mahal tapi aman. Kotor = murah, tapi ada 'harga' lain.", items, Callable(), "portrait_player")


func _buy(id: String, variant: String) -> void:
	if GS.sys.tech.buy(id, variant):
		Sfx.play("cash")
		var u: Dictionary = GS.sys.tech.TREE[id]
		GS.toast.emit("%s (%s) terpasang!" % [u["name"], u[variant]["label"]], "good" if variant == "bersih" else "info")
		GS.check_quests()
	ui.refresh_menu(open_upgrades)


# ------------------------------------------------------------------ morning events
func run_event(ev: String) -> bool:
	## the systems' morning events; false if `ev` is not one of them
	var d: Node = world.deals
	var next := func(msg: String, kind: String):
		if msg != "":
			GS.toast.emit(msg, kind)
		GS.stats_changed.emit()
		d.run_morning_events()
	match ev:
		"mogok":
			var C = GS.sys.crew
			var wage := 0
			for w in GS.workers:
				if w["role"] == "buruh":
					wage = int(w["wage"])
					break
			var higher: int = mini(C.pay_level + 1, C.PAY.size() - 1)
			ui.dialog("portrait_buruh", "Perwakilan Buruh", "Juragan, hari ini kami mogok! Upah %s sehari, beli minyak goreng sejerigen saja tidak cukup. Padahal minyaknya dari sawit yang kami panen sendiri!" % GS.fmt_short(wage),
				[{"text": "Naikkan gaji", "hint": "jadi " + C.PAY[higher]["name"] if higher != C.pay_level else "bonus semangat", "cb": func(): next.call(C.end_strike("naik"), "good")},
				 {"text": "Ancam pakai preman", "hint": "kecurigaan +6", "cb": func(): next.call(C.end_strike("ancam"), "bad")},
				 {"text": "Pecat semua buruh", "hint": "reputasi -6", "cb": func():
					next.call(C.end_strike("pecat"), "bad")
					world.refresh_workers()}])
			return true
		"kabut_asap":
			ui.dialog("portrait_ibu", "Bu Bidan Rina", "Kabut asap menyelimuti desa, Juragan. Posyandu penuh anak batuk-batuk. Orang-orang bilang apinya dari kebunmu.",
				[{"text": "Bagikan masker & obat", "hint": "Rp 750rb", "enabled": GS.money >= 750000, "cb": func():
					GS.spend(750000)
					GS.add_rep(5.0)
					GS.add_heat(-4.0)
					next.call("Masker dibagikan. Fotonya kamu unggah dengan tagar #PeduliAsap.", "good")},
				 {"text": "Salahkan peladang tradisional", "hint": "reputasi -5", "cb": func():
					GS.add_rep(-5.0)
					GS.add_heat(-2.0)
					if GS.villagers.has("dullah"):
						GS.villagers["dullah"]["trust"] = maxf(0.0, float(GS.villagers["dullah"]["trust"]) - 20.0)
					next.call("Pak Kades mengangguk. Kakek Dullah geleng-geleng: 'Kami membakar seperlunya sejak dulu, tidak pernah begini.'", "bad")},
				 {"text": "Bilang itu cuma kabut pagi", "hint": "kecurigaan +5", "cb": func():
					GS.add_heat(5.0)
					GS.add_rep(-3.0)
					next.call("'Kabut pagi yang baunya seperti sate gosong,' kata Rian di live-nya.", "bad")}])
			return true
		"banjir":
			var W = GS.sys.weather
			var place: String = W.village_name(W.flood) if W.flood != "" else "Dusun Muara"
			ui.dialog("portrait_petani", "Bang Rahmat (Nelayan)", "%s kebanjiran, Juragan! Air cokelat setinggi lutut. Dulu hutan di hulu menahan air hujan. Sekarang yang ada... kebun sawitmu." % place,
				[{"text": "Kirim perahu & sembako", "hint": "Rp 1 jt", "enabled": GS.money >= 1000000, "cb": func():
					GS.spend(1000000)
					GS.add_rep(8.0)
					GS.add_heat(-3.0)
					next.call("Bantuanmu datang duluan, sebelum bantuan pemerintah. Warga sedikit luluh.", "good")},
				 {"text": "Foto-foto bagi mi instan", "hint": "Rp 150rb", "enabled": GS.money >= 150000, "cb": func():
					GS.spend(150000)
					GS.add_rep(2.0)
					GS.add_heat(1.0)
					next.call("Fotonya bagus. Mi-nya kurang. Warga menghitung: satu bungkus untuk tiga keluarga.", "info")},
				 {"text": "Salahkan curah hujan", "hint": "reputasi -5", "cb": func():
					GS.add_rep(-5.0)
					GS.add_heat(3.0)
					next.call("'Ini fenomena La Nina,' katamu. Warga yang rumahnya terendam tidak tertawa.", "bad")}])
			return true
		"ikan_mati":
			ui.dialog("portrait_petani", "Bang Rahmat (Nelayan)", "Ikan-ikan di muara mati mengapung, Juragan. Airnya bau pestisida. Katanya dari kebunmu.",
				[{"text": "Ganti rugi nelayan", "hint": "Rp 500rb", "enabled": GS.money >= 500000, "cb": func():
					GS.spend(500000)
					GS.add_rep(4.0)
					next.call("Nelayan menerima ganti rugi. Ikannya tetap mati.", "info")},
				 {"text": "'Ikannya bunuh diri'", "hint": "kecurigaan +3", "cb": func():
					GS.add_rep(-4.0)
					GS.add_heat(3.0)
					next.call("Pernyataanmu jadi meme se-kabupaten.", "bad")}])
			return true
	return false


# ------------------------------------------------------------------ status lines
func status_lines() -> Array:
	var W = GS.sys.weather
	var M = GS.sys.market
	var C = GS.sys.crew
	var T = GS.sys.tech
	var out: Array = ["— Cuaca, pasar & kebun —"]
	out.append("%s hari ke-%d • %s • titik api: %d (dipadamkan %d, hangus %d)" % [W.season_name(), W.season_day(), W.weather_name(), W.fires.size(), W.fires_out, W.fires_burned])
	out.append("Gudang %d/%d TBS • harga TBS %s (rata-rata 14 hari %s)" % [M.stock(), M.capacity(), GS.fmt_short(GS.tbs_price), GS.fmt_short(M.average())])
	out.append("Pekerja %d • gaji %s • kepuasan %d%% • mogok %d kali" % [GS.workers.size(), C.PAY[C.pay_level]["name"], int(C.avg_sat()), C.strikes])
	var ups: Array = []
	for id in T.ORDER:
		if T.owned(id):
			ups.append("%s (%s)" % [T.TREE[id]["name"], T.level(id)])
	out.append("Upgrade: " + (", ".join(ups) if not ups.is_empty() else "belum ada"))
	return out
