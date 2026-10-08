extends Node
## The village calendar (day 1 = 10 Agustus): Tujuhbelasan on 17 Agustus (lomba panjat
## pinang = a tapping minigame, balap karung = three quick choices, red-white bunting),
## a pasar malam every 5 days (stalls, string lights, a bianglala), a kondangan every
## 6 days (tenda biru + janur kuning at a villager's house) and a pengajian every 7 days
## at Pak Ustad Karim's. Villagers gather at the spot during the event's hours; you can
## sponsor (reputation and friendship up) and join in.

var hub: Node
var _built := {}        # event id -> Node3D decoration
var _spots := {}        # event id -> Vector3
var _its := {}          # event id -> interactable
var _gathered := {}     # event id -> [vid]
var _tick := 0.0
var _wheel: Node3D
var _lights: Array = []
var _lamp_mat: StandardMaterial3D

const MONTHS := [["Agustus", 31], ["September", 30], ["Oktober", 31], ["November", 30], ["Desember", 31],
	["Januari", 31], ["Februari", 28], ["Maret", 31], ["April", 30], ["Mei", 31], ["Juni", 30], ["Juli", 31]]
const EVENTS := {
	"tujuhbelas": {"name": "Lomba Tujuhbelasan", "from": 8.0, "to": 17.0, "icon": "icon_bendera",
		"desc": "Panjat pinang & balap karung di lapangan desa"},
	"pasar": {"name": "Pasar Malam", "from": 17.0, "to": 23.5, "icon": "ui_moon",
		"desc": "Lapak jajanan, lampu warna-warni, bianglala"},
	"kondangan": {"name": "Kondangan", "from": 9.0, "to": 16.0, "icon": "icon_hadiah",
		"desc": "Hajatan pernikahan di rumah warga"},
	"pengajian": {"name": "Pengajian", "from": 18.5, "to": 22.0, "icon": "ui_star",
		"desc": "Pengajian di musala Pak Ustad Karim"},
}
const SPONSOR := {"tujuhbelas": 1500000, "pasar": 1000000, "kondangan": 0, "pengajian": 2000000}


func fs() -> Dictionary:
	return hub.st("fest", {"spons": 0, "pinang": 0, "karung": 0, "kondangan": 0, "pengajian": 0, "lempar": 0, "did": {}, "seen": 0})


# ------------------------------------------------------------------ calendar
func date_of(day: int) -> Array:
	## [date, month name] with day 1 = 10 Agustus
	var d := day - 1 + 10
	var m := 0
	while d > int(MONTHS[m][1]):
		d -= int(MONTHS[m][1])
		m = (m + 1) % MONTHS.size()
	return [d, MONTHS[m][0]]


func date_text(day: int) -> String:
	var dm := date_of(day)
	return "%d %s" % [dm[0], dm[1]]


func events_on(day: int) -> Array:
	var out: Array = []
	var dm := date_of(day)
	if int(dm[0]) == 17 and str(dm[1]) == "Agustus":
		out.append("tujuhbelas")
	if day % 6 == 3:
		out.append("kondangan")
	if day % 5 == 0:
		out.append("pasar")
	if day % 7 == 4:
		out.append("pengajian")
	return out


func host(day: int) -> String:
	## whose child gets married this kondangan (a villager still living at home)
	var ids: Array = []
	for vid in GS.VILLAGERS:
		if not GS.villagers[vid].get("evicted", false):
			ids.append(vid)
	if ids.is_empty():
		return ""
	return ids[(day * 7) % ids.size()]


func is_open(ev: String) -> bool:
	var e: Dictionary = EVENTS[ev]
	return ev in events_on(GS.day) and GS.hour >= float(e["from"]) and GS.hour < float(e["to"])


func hours(ev: String) -> String:
	var e: Dictionary = EVENTS[ev]
	return "%02d.%02d-%02d.%02d" % [int(e["from"]), int(fmod(float(e["from"]), 1.0) * 60), int(e["to"]), int(fmod(float(e["to"]), 1.0) * 60)]


func day_roll(report: Array) -> void:
	var evs := events_on(GS.day)
	var parts: Array = []
	for ev in evs:
		var txt := "%s (%s)" % [EVENTS[ev]["name"], hours(ev)]
		if ev == "kondangan" and host(GS.day) != "":
			txt = "Kondangan anak %s (%s)" % [GS.vname(host(GS.day)), hours(ev)]
		parts.append(txt)
	report.append("Kalender: %s.%s" % [date_text(GS.day), (" Hari ini: " + ", ".join(parts) + "!") if not parts.is_empty() else ""])
	var tomorrow := events_on(GS.day + 1)
	if "tujuhbelas" in tomorrow:
		report.append("Besok 17 Agustus! Warga sibuk memasang bendera dan umbul-umbul.")
	if "tujuhbelas" in evs or "kondangan" in evs:
		if not "festival" in GS.pending_events:
			GS.pending_events.append("festival")


func morning_announce() -> void:
	var evs := events_on(GS.day)
	if "tujuhbelas" in evs:
		hub.ui.dialog("portrait_kades", "Pak Kades Harun", "Merdeka! Hari ini 17 Agustus! Lomba panjat pinang dan balap karung di lapangan desa, jam 08.00 sampai 17.00. Panitia masih butuh sponsor, Juragan... hadiahnya belum ada.",
			[{"text": "Jadi sponsor utama", "hint": GS.fmt_short(SPONSOR["tujuhbelas"]), "enabled": GS.money >= SPONSOR["tujuhbelas"],
				"cb": func():
					sponsor("tujuhbelas")
					hub.next_event()},
			 {"text": "Nanti saya mampir", "cb": func(): hub.next_event()}])
	elif "kondangan" in evs and host(GS.day) != "":
		var h := host(GS.day)
		hub.ui.dialog(hub.deals.vp(h), GS.vname(h), "Juragan, anak saya menikah hari ini. Mampir ke rumah, ya, jam 09.00 sampai 16.00. Ada tenda biru, ada dangdut, ada prasmanan. Amplopnya... seikhlasnya. Hehe.",
			[{"text": "Insya Allah datang", "cb": func(): hub.next_event()}])
	else:
		hub.next_event()


# ------------------------------------------------------------------ places & decorations
func spot(ev: String) -> Vector3:
	if _spots.has(ev):
		return _spots[ev]
	var w: Node = hub.world
	var p := Vector3.ZERO
	match ev:
		"tujuhbelas", "pasar":
			var c := Vector3(-14, 0, 14) if ev == "tujuhbelas" else Vector3(14, 0, 14)
			p = hub.free_spot_near(c, 4.5, 40.0)
		"pengajian":
			var k: Node3D = w.extras.get("karim")
			var at: Vector3 = k.home if k else Vector3(30, 0, 88)
			p = hub.free_spot_near(at + Vector3(0, 0, 3.0), 3.0, 24.0)
		"kondangan":
			var h := host(GS.day)
			var door: Vector3 = w.door_points.get(GS.VILLAGERS[h]["home"], Vector3.ZERO) if h != "" else Vector3.ZERO
			p = hub.free_spot_near(door + Vector3(0, 0, 3.5), 2.6, 18.0)
	_spots[ev] = p
	return p


func refresh() -> void:
	for ev in _built:
		if is_instance_valid(_built[ev]):
			_built[ev].queue_free()
	_built.clear()
	for ev in _its:
		hub.remove_spot(_its[ev])
	_its.clear()
	for ev in _gathered.keys():
		_release(ev)
	_spots.clear()
	_wheel = null
	_lights.clear()
	for ev in events_on(GS.day):
		var p := spot(ev)
		var n := Node3D.new()
		n.name = "Fest_" + ev
		n.position = p
		hub.world.add_child(n)
		_built[ev] = n
		match ev:
			"tujuhbelas": _build_17(n)
			"pasar": _build_pasar(n)
			"kondangan": _build_kondangan(n)
			"pengajian": _build_pengajian(n)
		var e: String = ev
		_its[ev] = hub.add_spot(p + Vector3(0, 0, 1.0), 3.2, func(): return prompt(e), func(): open(e))


func prompt(ev: String) -> String:
	var nm: String = EVENTS[ev]["name"]
	if is_open(ev):
		return "Ikut %s" % nm
	if GS.hour < float(EVENTS[ev]["from"]):
		return "%s mulai jam %02d.%02d" % [nm, int(EVENTS[ev]["from"]), int(fmod(float(EVENTS[ev]["from"]), 1.0) * 60)]
	return "%s sudah bubar" % nm


func _bunting(parent: Node3D, pts: Array, sag := 0.35) -> void:
	## red-white triangle flags strung between the points (one mesh, one draw call)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var k := 0
	for s in pts.size() - 1:
		var a: Vector3 = pts[s]
		var b: Vector3 = pts[s + 1]
		var n := maxi(2, int(a.distance_to(b) / 0.42))
		for j in n:
			var t0 := float(j) / n
			var t1 := float(j + 0.7) / n
			var p0 := a.lerp(b, t0) - Vector3(0, sin(t0 * PI) * sag, 0)
			var p1 := a.lerp(b, t1) - Vector3(0, sin(t1 * PI) * sag, 0)
			var tip := (p0 + p1) * 0.5 - Vector3(0, 0.32, 0)
			var col := Color("d93a2c") if k % 2 == 0 else Color("f6f2ea")
			k += 1
			for v in [p0, p1, tip]:
				st.set_color(col)
				st.add_vertex(v)
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 1.0
	st.set_material(m)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)


func _poles(parent: Node3D, pts: Array, h: float, col := "f6f2ea") -> Array:
	var tops: Array = []
	for p in pts:
		var q: Vector3 = p
		q.y = hub.world.height_at(parent.position.x + q.x, parent.position.z + q.z) - parent.position.y
		hub.cyl(parent, 0.05, h, q + Vector3(0, h * 0.5, 0), col, 6)
		tops.append(q + Vector3(0, h - 0.1, 0))
	return tops


func _build_17(n: Node3D) -> void:
	# a square of bunting round the field, a flagpole with the merah putih
	var c := [Vector3(-4.5, 0, -3.5), Vector3(4.5, 0, -3.5), Vector3(4.5, 0, 3.5), Vector3(-4.5, 0, 3.5)]
	var tops := _poles(n, c, 3.0)
	tops.append(tops[0])
	_bunting(n, tops)
	hub.cyl(n, 0.05, 5.0, Vector3(-3.6, 2.5, -2.6), "dcdcd4", 6)
	hub.box(n, Vector3(1.1, 0.36, 0.02), Vector3(-3.05, 4.7, -2.6), "d93a2c", Vector3.ZERO, false)
	hub.box(n, Vector3(1.1, 0.36, 0.02), Vector3(-3.05, 4.34, -2.6), "f6f2ea", Vector3.ZERO, false)
	# panjat pinang: a greased pole with the prize ring
	var pp := Vector3(1.8, 0, -1.6)
	hub.cyl(n, 0.12, 6.0, pp + Vector3(0, 3.0, 0), "8a6040", 8)
	var ring := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.75
	tm.outer_radius = 0.86
	ring.mesh = tm
	ring.material_override = hub.mat("d93a2c")
	ring.position = pp + Vector3(0, 5.8, 0)
	n.add_child(ring)
	var prize_cols := ["e8b030", "3a74c0", "2f9a5a", "d9402a", "f6f2ea", "e8b030"]
	for k in 6:
		var a := k * TAU / 6.0
		var at := pp + Vector3(cos(a) * 0.8, 5.35, sin(a) * 0.8)
		hub.cyl(n, 0.008, 0.4, at + Vector3(0, 0.25, 0), "6a6a6a", 4)
		hub.box(n, Vector3(0.26, 0.26, 0.2), at, prize_cols[k])
	hub.label3d(n, "PANJAT PINANG", pp + Vector3(0, 6.5, 0), 44, Color("d93a2c"), true)
	# balap karung lane: start & finish lines, sacks waiting
	for z in [-0.4, 2.6]:
		hub.box(n, Vector3(4.0, 0.03, 0.12), Vector3(-1.6, 0.02, z), "f6f2ea", Vector3.ZERO, false)
	for k in 3:
		hub.cyl(n, 0.22, 0.6, Vector3(-3.0 + k * 1.1, 0.3, 2.9), "c0ac80", 8, Vector3.ZERO, 0.18)
	hub.label3d(n, "BALAP KARUNG", Vector3(-1.6, 1.6, 2.6), 36, Color("2f5a8a"), true)


func _build_pasar(n: Node3D) -> void:
	# three stalls, string lights, a bianglala
	for k in 3:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh("kios", true)
		mi.position = Vector3(-4.0 + k * 2.6, 0, -3.2)
		n.add_child(mi)
	for k in 3:
		var names := ["KERAK TELOR", "ES DAWET", "LEMPAR GELANG"]
		hub.label3d(n, names[k], Vector3(-4.0 + k * 2.6, 2.6, -2.4), 30, Color("7a3a12"), true)
	var tops := _poles(n, [Vector3(-5.5, 0, 1.5), Vector3(-1.8, 0, 3.2), Vector3(1.8, 0, 3.2), Vector3(5.5, 0, 1.5)], 3.2, "6a5a4a")
	_string_lights(n, tops)
	_wheel = Node3D.new()
	_wheel.position = Vector3(4.6, 3.6, -2.4)
	n.add_child(_wheel)
	var rim := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 2.6
	tm.outer_radius = 2.75
	tm.rings = 32
	rim.mesh = tm
	rim.rotation.x = PI * 0.5
	rim.material_override = hub.mat("e8b030")
	_wheel.add_child(rim)
	var cols := ["d9402a", "3a74c0", "2f9a5a", "e8b030", "8e5a7a", "f08a3a", "3fa38f", "d46aa0"]
	for k in 8:
		var a := k * TAU / 8.0
		var sp: MeshInstance3D = hub.box(_wheel, Vector3(0.08, 2.7, 0.08), Vector3(cos(a), sin(a), 0) * 1.35, "f6f2ea", Vector3(0, 0, a - PI * 0.5))
		sp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		hub.box(_wheel, Vector3(0.5, 0.45, 0.5), Vector3(cos(a), sin(a), 0) * 2.7 + Vector3(0, -0.2, 0), cols[k])
	for s in [-1.0, 1.0]:
		hub.box(n, Vector3(0.14, 4.0, 0.14), Vector3(4.6 + s * 1.2, 1.9, -2.4), "6a5a4a", Vector3(0, 0, s * 0.3))


func _string_lights(n: Node3D, tops: Array) -> void:
	var pts: Array = []
	for s in tops.size() - 1:
		var a: Vector3 = tops[s]
		var b: Vector3 = tops[s + 1]
		var k := int(a.distance_to(b) / 0.5)
		for j in k:
			var t := float(j) / k
			pts.append(a.lerp(b, t) - Vector3(0, sin(t * PI) * 0.4, 0))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	var sm := SphereMesh.new()
	sm.radius = 0.1
	sm.height = 0.2
	sm.radial_segments = 6
	sm.rings = 3
	_lamp_mat = StandardMaterial3D.new()
	_lamp_mat.vertex_color_use_as_albedo = true
	_lamp_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	sm.material = _lamp_mat
	mm.mesh = sm
	mm.instance_count = pts.size()
	var cols := [Color("ffd25a"), Color("ff6a5a"), Color("7ad0ff"), Color("8aff8a"), Color("ff9ae0")]
	for k in pts.size():
		mm.set_instance_transform(k, Transform3D(Basis(), pts[k]))
		mm.set_instance_color(k, cols[k % cols.size()])
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	n.add_child(mmi)
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.75, 0.5)
	l.omni_range = 13.0
	l.light_energy = 0.0
	l.position = Vector3(0, 2.6, 0.5)
	n.add_child(l)
	_lights.append(l)


func _build_kondangan(n: Node3D) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLib.merged_mesh("tenda", true)
	mi.position = Vector3(0, 0, -0.6)
	mi.scale = Vector3(1.5, 1.2, 1.4)
	n.add_child(mi)
	# janur kuning: two bent yellow palm-leaf arches at the entrance
	for s in [-1.0, 1.0]:
		var base := Vector3(s * 1.6, 0, 2.2)
		hub.cyl(n, 0.05, 2.6, base + Vector3(0, 1.3, 0), "d8b040", 6)
		for k in 6:
			var t := k / 5.0
			var p := base + Vector3(-s * (sin(t * PI * 0.5) * 0.9), 2.6 + sin(t * PI) * 0.5 - t * 0.7, 0)
			hub.box(n, Vector3(0.1, 0.42, 0.03), p, "f2d050", Vector3(0, 0, s * (0.6 + t)))
	# rows of plastic chairs
	for r in 2:
		for k in 4:
			hub.box(n, Vector3(0.42, 0.45, 0.42), Vector3(-1.2 + k * 0.8, 0.22, 0.4 + r * 0.8), ["d9402a", "3a74c0"][r])
	hub.label3d(n, "SELAMAT MENEMPUH\nHIDUP BARU", Vector3(0, 3.0, 2.2), 34, Color("7a3a12"), true)


func _build_pengajian(n: Node3D) -> void:
	hub.box(n, Vector3(4.2, 0.03, 3.0), Vector3(0, 0.02, 0), "3f8a5a", Vector3.ZERO, false)
	hub.box(n, Vector3(3.8, 0.035, 2.6), Vector3(0, 0.025, 0), "e8d8a8", Vector3.ZERO, false)
	hub.box(n, Vector3(0.6, 0.3, 0.4), Vector3(0, 0.15, -1.0), "7a5a3a")   # rehal table
	hub.cyl(n, 0.04, 3.2, Vector3(2.4, 1.6, -1.4), "8a8a8a", 6)            # TOA loudspeaker pole
	hub.cyl(n, 0.12, 0.35, Vector3(2.4, 3.1, -1.25), "e8e0d0", 8, Vector3(PI * 0.4, 0, 0), 0.22)
	hub.label3d(n, "PENGAJIAN MALAM", Vector3(0, 2.4, -1.4), 36, Color("2f6d4a"), true)
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.85, 0.6)
	l.omni_range = 7.0
	l.light_energy = 0.0
	l.position = Vector3(0, 2.6, 0)
	n.add_child(l)
	_lights.append(l)


# ------------------------------------------------------------------ per frame: wheel, lights, crowd
func _process(delta: float) -> void:
	if _wheel and is_instance_valid(_wheel):
		_wheel.rotation.z += delta * 0.25
	var night: float = hub.world.night_k
	for l in _lights:
		if is_instance_valid(l):
			l.light_energy = night * 2.2
	if _lamp_mat:
		_lamp_mat.albedo_color = Color(1, 1, 1).lerp(Color(1.6, 1.6, 1.6), night)
	_tick -= delta
	if _tick > 0.0 or not hub.playing():
		return
	_tick = 1.0
	for ev in _built:
		if is_open(ev):
			if not _gathered.has(ev):
				_gather(ev)
		elif _gathered.has(ev):
			_release(ev)


func _gather(ev: String, instant := false) -> void:
	var p := spot(ev)
	var w: Node = hub.world
	var busy: Array = hub.prot.ps()["who"] if hub.prot.active() else []
	var cand: Array = []
	for vid in w.npcs:
		var v: Dictionary = GS.villagers[vid]
		if v["worker"] or vid in busy or (v.get("evicted", false) and ev == "kondangan"):
			continue
		cand.append(vid)
	cand.sort_custom(func(a, b): return w.npcs[a].global_position.distance_to(p) < w.npcs[b].global_position.distance_to(p))
	var want: Array = cand.slice(0, 7)
	if ev == "kondangan":
		var h := host(GS.day)
		if h != "" and not h in want:
			want.push_front(h)
	var out: Array = []
	for k in want.size():
		var vid: String = want[k]
		var n: Npc = w.npcs[vid]
		var a := k * TAU / maxf(1.0, want.size()) + 0.4
		var at := p + Vector3(cos(a) * 2.6, 0, sin(a) * 2.0 + 0.6)
		n.sleeps_at_night = false   # pasar malam / pengajian: they stay up for it
		n.set_anchor(at, 1.2, instant or n.global_position.distance_to(at) > 70.0)
		out.append(vid)
	_gathered[ev] = out


func _release(ev: String) -> void:
	for vid in _gathered.get(ev, []):
		if hub.world.npcs.has(vid):
			hub.world.npcs[vid].sleeps_at_night = true
			hub.world.refresh_villager(vid)
	_gathered.erase(ev)


func gathered(ev: String) -> Array:
	return _gathered.get(ev, [])


# ------------------------------------------------------------------ joining in
func did(ev: String, what: String) -> bool:
	var d: Dictionary = fs()["did"]
	return int(d.get(ev + ":" + what, -1)) == GS.day


func mark(ev: String, what: String) -> void:
	fs()["did"][ev + ":" + what] = GS.day


func open(ev: String) -> void:
	if not is_open(ev):
		hub.ui.toast(prompt(ev), "info")
		return
	var ui: Node = hub.ui
	var items: Array = []
	var cost: int = SPONSOR[ev]
	if cost > 0:
		items.append({"icon": "icon_uang", "text": "Jadi sponsor acara", "desc": "Spanduk 'Didukung oleh Sawit The Franchise™'. Reputasi +10, semua warga lebih akrab.",
			"price": GS.fmt_short(cost), "enabled": not did(ev, "spons") and GS.money >= cost, "cb": func():
				sponsor(ev)
				ui.refresh_menu(func(): open(ev))})
	match ev:
		"tujuhbelas":
			items.append({"icon": "icon_panjat", "text": "Lomba panjat pinang", "desc": "Tekan PANJAT! secepatnya sebelum licinnya oli menarikmu turun. Hadiah di puncak!",
				"button": "Ikut", "enabled": not did(ev, "pinang") and GS.energy >= 15.0, "cb": func():
					ui.close()
					pinang_start()})
			items.append({"icon": "icon_bendera", "text": "Lomba balap karung", "desc": "Tiga lompatan, tiga keputusan. Curang boleh, asal tidak ketahuan.",
				"button": "Ikut", "enabled": not did(ev, "karung") and GS.energy >= 10.0, "cb": func():
					ui.close()
					karung_start()})
		"pasar":
			items.append({"icon": "icon_kue", "text": "Kerak telor & es dawet", "desc": "Energi +30.", "price": GS.fmt_short(25000), "cb": func():
				if GS.spend(25000):
					GS.energy = minf(GS.max_energy, GS.energy + 30.0)
					GS.stats_changed.emit()
					Sfx.play("pop")})
			items.append({"icon": "ui_star", "text": "Lempar gelang", "desc": "Tiga gelang, hadiah boneka (atau kue).", "price": GS.fmt_short(10000),
				"enabled": not did(ev, "lempar"), "cb": func():
					ui.close()
					lempar()})
			items.append({"icon": "ui_moon", "text": "Naik bianglala", "desc": "Melihat seluruh kebun sawitmu dari atas. Indah... kalau kamu suka hijau yang seragam.",
				"price": GS.fmt_short(5000), "cb": func():
					if GS.spend(5000):
						ui.close()
						hub.deals.say("portrait_player", "Kamu", "Dari atas bianglala, desa terlihat kecil. Kebun warga, kebunmu, tenda biru... semuanya kelihatan. Hmm.")})
		"kondangan":
			var h := host(GS.day)
			for opt in [[100000, "Amplop Rp 100 ribu", "Standar kondangan desa."], [1000000, "Amplop Rp 1 juta (sambil difoto)", "Reputasi naik, yang punya hajat terharu."],
					[0, "Amplop kosong", "Hemat. Semoga tidak ketahuan..."]]:
				var amt: int = opt[0]
				items.append({"icon": "icon_hadiah", "text": opt[1], "desc": opt[2], "price": GS.fmt_short(amt) if amt > 0 else "",
					"button": "Kasih", "enabled": not did(ev, "amplop") and GS.money >= amt, "cb": func():
						ui.close()
						amplop(h, amt)})
			items.append({"icon": "icon_megafon", "text": "Nyanyi dangdut di panggung", "desc": "Energi -10, reputasi +3. Suaramu... berani.",
				"button": "Nyanyi", "enabled": not did(ev, "nyanyi") and GS.energy >= 10.0, "cb": func():
					ui.close()
					nyanyi()})
		"pengajian":
			items.append({"icon": "ui_star", "text": "Ikut mengaji", "desc": "Reputasi +4, Kecurigaan -3. Hati tenang.",
				"button": "Ikut", "enabled": not did(ev, "ngaji"), "cb": func():
					ui.close()
					ngaji()})
			items.append({"icon": "ui_star", "text": "Minta didoakan agar lolos sidak", "desc": "Pak Ustad menatapmu lama sekali.",
				"button": "Minta", "enabled": not did(ev, "doa"), "cb": func():
					ui.close()
					doa()})
	var who := gathered(ev).size()
	ui.menu(EVENTS[ev]["name"], "%s • %s • %d warga hadir" % [date_text(GS.day), hours(ev), who], items, Callable(),
		"portrait_kades" if ev == "tujuhbelas" else ("portrait_kakek" if ev == "pengajian" else "portrait_ibu"))


func sponsor(ev: String) -> bool:
	var cost: int = SPONSOR.get(ev, 0)
	if cost <= 0 or did(ev, "spons") or not GS.spend(cost):
		return false
	mark(ev, "spons")
	var f := fs()
	f["spons"] = int(f["spons"]) + 1
	GS.add_rep(10)
	GS.add_heat(-3)
	hub.add_stat("donated", cost)
	for vid in GS.VILLAGERS:
		hub.rel.add(vid, 4.0, false)
	Sfx.play("cash")
	hub.ui.toast("Spanduk 'Didukung oleh Sawit The Franchise™' terpasang. Warga bertepuk tangan (sebagian).", "good")
	return true


# ------------------------------------------------------------------ panjat pinang (tapping minigame)
var pinang: Control


func pinang_start() -> void:
	if not GS.use_energy(15.0):
		return
	mark("tujuhbelas", "pinang")
	var ui: Node = hub.ui
	var panel := Pinang.new()
	panel.name = "PanjatPinang"
	panel.fest = self
	panel.build(ui)
	pinang = panel
	ui._open_modal(panel, true)


func pinang_result(win: bool) -> void:
	pinang = null
	var f := fs()
	if win:
		f["pinang"] = int(f["pinang"]) + 1
		var prizes := [["sepeda ontel", 400000], ["rice cooker", 300000], ["ember dan gayung", 50000], ["kaos 'Merdeka!'", 30000]]
		var pr: Array = prizes[hub.rng.randi() % prizes.size()]
		GS.add_money(int(pr[1]))
		GS.add_rep(5)
		GS.add_item("kue", 2)
		Sfx.play("quest")
		hub.deals.say("portrait_kades", "Pak Kades Harun", "MERDEKA! Juragan sampai di puncak pinang dan menyambar hadiah %s (dijual lagi %s) plus 2 kue! Warga bersorak... sebagian karena Juragan penuh oli." % [pr[0], GS.fmt_short(int(pr[1]))])
	else:
		GS.add_rep(1)
		hub.deals.say("portrait_kades", "Pak Kades Harun", "Juragan merosot lagi! Olinya terlalu licin... atau perut Juragan terlalu buncit. Tetap semangat, merdeka!")


class Pinang extends PanelContainer:
	## A greased pole: every PANJAT! press climbs, the oil keeps pulling you down.
	## Reach 100% within the time to win. (fest.pinang_result applies the outcome)
	var fest: Node
	var ui: Node
	var height := 0.0
	var time_left := 12.0
	var oil := 1.0
	var running := true
	var bar: ProgressBar
	var info: Label
	var pole: Control

	func build(p_ui: Node) -> void:
		ui = p_ui
		set_meta("pinang", true)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 10)
		add_child(col)
		var t: Label = ui._title_label("Panjat Pinang!", ui.TITLE_BROWN, 32)
		t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		col.add_child(t)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 18)
		col.add_child(h)
		pole = PoleView.new()
		pole.custom_minimum_size = Vector2(120, 260)
		pole.set("view", self)
		h.add_child(pole)
		var rc := VBoxContainer.new()
		rc.add_theme_constant_override("separation", 10)
		rc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(rc)
		var d: Label = ui._label("Tekan PANJAT! (atau E / Spasi) secepatnya.\nOli di tiang menarikmu merosot!", 18, ui.BROWN)
		rc.add_child(d)
		bar = ui._bar(ui.BAR_GREEN, 300, 18)
		rc.add_child(bar)
		info = ui._label("", 18, ui.BROWN_SOFT, true)
		rc.add_child(info)
		var b: Button = ui.button("PANJAT!", func(): climb(), true, 260, true)
		b.name = "ClimbButton"
		b.add_theme_font_size_override("font_size", 28)
		b.custom_minimum_size.y = 70
		rc.add_child(b)

	func climb() -> void:
		if not running:
			return
		height = minf(100.0, height + 7.5 + randf() * 2.5)
		Sfx.play("pop", 1.0 + height / 200.0, -10.0)
		if height >= 100.0:
			_finish(true)

	func _process(delta: float) -> void:
		if not running:
			return
		time_left -= delta
		oil = maxf(0.35, oil - delta * 0.05)
		height = maxf(0.0, height - 13.0 * oil * delta)
		bar.value = height
		info.text = "Tinggi: %d%%   •   Waktu: %.1f s   •   Oli: %d%%" % [int(height), maxf(0.0, time_left), int(oil * 100.0)]
		pole.queue_redraw()
		if time_left <= 0.0:
			_finish(false)

	func _finish(win: bool) -> void:
		running = false
		info.text = "SAMPAI PUNCAK!" if win else "Waktu habis... merosot!"
		var tw := create_tween()
		tw.tween_interval(0.8)
		tw.tween_callback(func():
			ui.close()
			fest.pinang_result(win))


class PoleView extends Control:
	var view: Control

	func _draw() -> void:
		var h: float = view.height if view else 0.0
		var x := size.x * 0.5
		draw_rect(Rect2(0, size.y - 14, size.x, 14), Color("8fbf5a"))
		draw_rect(Rect2(x - 7, 26, 14, size.y - 40), Color("8a6040"))
		for k in 6:
			draw_rect(Rect2(x - 7, 40 + k * 36, 14, 4), Color(0.1, 0.08, 0.06, 0.4))
		draw_arc(Vector2(x, 22), 40, 0, TAU, 24, Color("d93a2c"), 5.0)
		var cols := [Color("e8b030"), Color("3a74c0"), Color("2f9a5a"), Color("d9402a")]
		for k in 4:
			draw_rect(Rect2(x - 44 + k * 24, 30, 16, 16), cols[k])
		var y := (size.y - 30) - (h / 100.0) * (size.y - 70)
		draw_circle(Vector2(x, y - 14), 9, Color("f2b98a"))
		draw_rect(Rect2(x - 9, y - 6, 18, 20), Color("3a74c0"))
		draw_line(Vector2(x - 9, y - 4), Vector2(x - 2, y - 18), Color("f2b98a"), 4.0)
		draw_line(Vector2(x + 9, y - 4), Vector2(x + 2, y - 18), Color("f2b98a"), 4.0)


# ------------------------------------------------------------------ balap karung (three choices)
var _karung := 0


func karung_start() -> void:
	if not GS.use_energy(10.0):
		return
	mark("tujuhbelas", "karung")
	_karung = 0
	karung_leg(1)


func karung_leg(leg: int) -> void:
	var texts := ["Peluit berbunyi! Kamu di dalam karung goni bersama empat lawan. Lompatan pertama?",
		"Setengah lintasan! Mas Joko di sebelahmu mulai menyusul. Lompatan kedua?",
		"Garis finis di depan mata! Lompatan terakhir?"]
	hub.ui.dialog("portrait_kades", "Wasit Balap Karung", texts[leg - 1], [
		{"text": "Lompat jauh (cepat, bisa jatuh)", "cb": func(): karung_jump(leg, "jauh")},
		{"text": "Lompat kecil-kecil (aman)", "cb": func(): karung_jump(leg, "aman")},
		{"text": "Senggol lawan (curang)", "cb": func(): karung_jump(leg, "senggol")},
	])


func karung_jump(leg: int, how: String) -> void:
	match how:
		"jauh":
			if hub.rng.randf() < 0.6:
				_karung += 2
				hub.ui.toast("Lompatan jauh! Kamu memimpin.", "good")
			else:
				_karung -= 1
				hub.ui.toast("Gedebuk! Kamu jatuh terguling. Penonton tertawa.", "bad")
		"aman":
			_karung += 1
		"senggol":
			if hub.rng.randf() < 0.4:
				GS.add_rep(-3)
				hub.ui.toast("Ketahuan wasit! Kamu didiskualifikasi (Reputasi -3).", "bad")
				karung_finish(-99)
				return
			_karung += 2
			hub.ui.toast("Lawan terjungkal. Wasit sedang melihat ke arah lain...", "info")
	if leg < 3:
		karung_leg(leg + 1)
	else:
		karung_finish(_karung)


func karung_finish(score: int) -> bool:
	if score <= -99:
		return false
	var win := score >= 4
	if win:
		var f := fs()
		f["karung"] = int(f["karung"]) + 1
		GS.add_money(200000)
		GS.add_rep(3)
		Sfx.play("quest")
		hub.deals.say("portrait_kades", "Wasit Balap Karung", "JUARA SATU! Juragan menang balap karung dan dapat piala plastik plus amplop Rp 200 ribu. (Dananya dari sponsor... Juragan sendiri?)")
	else:
		GS.add_item("kue", 1)
		hub.deals.say("portrait_kades", "Wasit Balap Karung", "Juara harapan tiga! Hadiahnya sebungkus kue klepon. Yang penting partisipasi, Juragan.")
	return win


# ------------------------------------------------------------------ pasar malam / kondangan / pengajian
func lempar() -> bool:
	if not GS.spend(10000):
		return false
	mark("pasar", "lempar")
	var hits := 0
	for k in 3:
		if hub.rng.randf() < 0.35:
			hits += 1
	if hits >= 2:
		var f := fs()
		f["lempar"] = int(f["lempar"]) + 1
		GS.add_item("kue", 2)
		hub.deals.say("portrait_ibu", "Penjaga Lapak", "%d dari 3 gelang masuk! Hadiahnya boneka beruang... eh, stoknya habis. Ganti 2 kue klepon, ya." % hits)
		return true
	hub.deals.say("portrait_ibu", "Penjaga Lapak", "Masuk %d dari 3. Belum beruntung, Juragan! Botolnya memang agak... lebar di bawah. Coba lagi lain kali." % hits)
	return false


func amplop(h: String, amt: int) -> void:
	mark("kondangan", "amplop")
	var f := fs()
	f["kondangan"] = int(f["kondangan"]) + 1
	if amt <= 0:
		GS.add_rep(-1)
		if hub.rng.randf() < 0.3 and h != "":
			hub.rel.add(h, -15.0)
			GS.add_rep(-5)
			hub.deals.say(hub.deals.vp(h), GS.vname(h), "Juragan... amplopnya kosong. Bendahara hajatan kami teliti sekali, lho. (Gosip menyebar. Reputasi -5)")
		else:
			hub.deals.say(hub.deals.vp(h) if h != "" else "portrait_ibu", GS.vname(h) if h != "" else "Tuan Rumah", "Terima kasih sudah datang, Juragan! Silakan ambil prasmanannya. (Amplop kosongmu belum dibuka. Belum.)")
		return
	if not GS.spend(amt):
		return
	hub.add_stat("donated", amt)
	if h != "":
		hub.rel.add(h, 10.0 if amt < 1000000 else 22.0)
	GS.add_rep(2.0 if amt < 1000000 else 6.0)
	GS.energy = minf(GS.max_energy, GS.energy + 20.0)
	GS.stats_changed.emit()
	hub.deals.say(hub.deals.vp(h) if h != "" else "portrait_ibu", GS.vname(h) if h != "" else "Tuan Rumah",
		"Wah, terima kasih, Juragan! Silakan makan prasmanan, ada rendang dan kerupuk. (Energi +20)" if amt < 1000000 else
		"Ya Allah, Juragan! Amplop setebal ini... Fotografer, foto, foto! Juragan duduk di pelaminan sebentar! (Reputasi +6)")


func nyanyi() -> void:
	mark("kondangan", "nyanyi")
	GS.use_energy(10.0)
	GS.add_rep(3)
	for vid in gathered("kondangan"):
		hub.rel.add(vid, 3.0, false)
	hub.add_stat("songs")
	hub.deals.say("portrait_player", "Kamu", "\"Terlalu... sadis caramu... menyingkirkan diriku dari kebunku...\" (Penonton bergoyang. Ada yang menangis, entah terharu atau tersindir.)")


func ngaji() -> void:
	mark("pengajian", "ngaji")
	var f := fs()
	f["pengajian"] = int(f["pengajian"]) + 1
	GS.add_rep(4)
	GS.add_heat(-3)
	if int(f["pengajian"]) % 3 == 0:
		hub.add_stat("tobat_pts")
	hub.deals.say("portrait_kakek", "Pak Ustad Karim", "Malam ini kita bahas soal amanah dan hak orang lain, Juragan. Kebetulan sekali Juragan datang. (Reputasi +4, Kecurigaan -3)")


func doa() -> void:
	mark("pengajian", "doa")
	GS.add_heat(-5)
	GS.add_rep(-2)
	hub.deals.say("portrait_kakek", "Pak Ustad Karim", "Saya doakan Juragan... dapat hidayah. Soal sidak, itu urusan Juragan dengan Satgas. Dan dengan Yang Di Atas. (Kecurigaan -5)")
