class_name CrewSys
extends RefCounted
## Workers (logic; the panel is scripts/ui/systems_ui.gd). Extends the GS.workers
## entries {"id", "name", "wage", "vid"} with "role", "base" (the wage at standard pay)
## and "sat" (satisfaction 0..100); old saves' workers become buruh panen.
##
## Every morning: satisfaction drifts toward what the pay is worth (the pay level is
## Hemat / Standar / Layak for the whole crew; villagers you took the land of work for
## a pittance but are desperate), then wages are paid and the crew works your parcels:
## buruh panen harvest ripe palms into the gudang, plant your bibit and clear thickets;
## a mandor makes them 30% faster (and a little more miserable); a sopir with the Truk
## Angkut upgrade drives the gudang's stock to the mill (systems/tech_sys.gd). Unhappy
## workers slow down, and very unhappy buruh go on strike (mogok): no work, no pay, and
## a morning event (naikkan gaji / ancam / pecat).

const ROLES := {
	"buruh": {"name": "Buruh panen", "wage": 150000, "max": 6, "icon": "icon_egrek",
		"desc": "Memanen 8 pohon, menanam 3 bibit & menebas 2 semak tiap pagi. Hasil panen masuk gudang."},
	"mandor": {"name": "Mandor", "wage": 250000, "max": 1, "icon": "icon_helm",
		"desc": "Buruh kerja 30% lebih cepat, sambil diteriaki. Mengurangi mogok, tapi buruh makin kesal."},
	"sopir": {"name": "Sopir truk", "wage": 120000, "max": 1, "icon": "icon_truk",
		"desc": "Mengantar stok gudang ke pabrik tiap pagi (butuh Truk Angkut). Tanpa truk dia main HP."},
}
const PAY := [{"name": "Hemat", "mult": 0.6}, {"name": "Standar", "mult": 1.0}, {"name": "Layak", "mult": 1.35}]
const NAMES := {
	"buruh": ["Pak Udin", "Mas Agus", "Bang Togar", "Mbak Yuni", "Kang Dedi", "Bu Erna", "Mas Bayu", "Pak Juned"],
	"mandor": ["Pak Mandor Tigor", "Pak Mandor Bonar"],
	"sopir": ["Bang Ucup", "Mas Gareng"],
}
const HARVEST_PER := 8.0
const PLANT_PER := 3.0
const CLEAR_PER := 2.0
const MANDOR_BOOST := 1.3

var gs
var pay_level := 1
var strike := false        # on strike today
var strikes := 0           # all time
var last_work := {}        # this morning's output for the panel


func reset() -> void:
	pay_level = 1
	strike = false
	strikes = 0
	last_work = {}


# ------------------------------------------------------------------ queries
func normalize() -> void:
	## fills the new keys of old / generic worker entries (deals.gd hires, old saves)
	for w in gs.workers:
		if not w.has("role") or not ROLES.has(str(w["role"])):
			w["role"] = "buruh"
		if not w.has("base"):
			w["base"] = int(w.get("wage", ROLES[w["role"]]["wage"]))
		if not w.has("sat"):
			w["sat"] = 70.0
		w["base"] = int(w["base"])
		w["sat"] = clampf(float(w["sat"]), 0.0, 100.0)
		w["wage"] = wage_of(w)


func wage_of(w: Dictionary) -> int:
	return int(round(int(w.get("base", w.get("wage", 0))) * float(PAY[pay_level]["mult"]) / 1000.0)) * 1000


func daily_wages() -> int:
	normalize()
	var s := 0
	for w in gs.workers:
		s += int(w["wage"])
	return s


func count(role: String) -> int:
	var n := 0
	for w in gs.workers:
		if str(w.get("role", "buruh")) == role:
			n += 1
	return n


func can_hire(role: String) -> bool:
	return count(role) < int(ROLES[role]["max"]) and gs.workers.size() < gs.MAX_WORKERS


func target_sat(w: Dictionary) -> float:
	var std: float = float(ROLES[str(w.get("role", "buruh"))]["wage"])
	var ratio := float(wage_of(w)) / std
	var t := -20.0 + 100.0 * ratio
	if str(w.get("vid", "")) != "":
		t += 25.0   # lost their land to you; no other work around
	return clampf(t, 0.0, 100.0)


func avg_sat(role := "") -> float:
	var s := 0.0
	var n := 0
	for w in gs.workers:
		if role == "" or str(w.get("role", "buruh")) == role:
			s += float(w.get("sat", 70.0))
			n += 1
	return s / n if n > 0 else 100.0


static func productivity(sat: float) -> float:
	if sat >= 60.0:
		return 1.0
	if sat >= 35.0:
		return 0.6
	return 0.3


static func mood(sat: float) -> String:
	if sat >= 75.0:
		return "Senang"
	if sat >= 60.0:
		return "Biasa"
	if sat >= 35.0:
		return "Kesal (kerja lambat)"
	return "Marah (bisa mogok)"


# ------------------------------------------------------------------ actions
func hire(role: String) -> Dictionary:
	if not can_hire(role):
		return {}
	normalize()
	var used := []
	for w in gs.workers:
		used.append(w["name"])
	var pick: String = NAMES[role][0]
	for n in NAMES[role]:
		if not n in used:
			pick = n
			break
	var w := {"id": "%s%d" % [role, gs.rng.randi()], "name": pick, "vid": "", "role": role,
		"base": int(ROLES[role]["wage"]), "sat": 70.0}
	w["wage"] = wage_of(w)
	gs.workers.append(w)
	gs.stats_changed.emit()
	return w


func fire(i: int) -> Dictionary:
	if i < 0 or i >= gs.workers.size():
		return {}
	var w: Dictionary = gs.workers[i]
	gs.workers.remove_at(i)
	if str(w.get("vid", "")) != "" and gs.villagers.has(w["vid"]):
		gs.villagers[w["vid"]]["worker"] = false
	for o in gs.workers:
		o["sat"] = maxf(0.0, float(o.get("sat", 70.0)) - 5.0)   # who's next?
	gs.stats_changed.emit()
	return w


func set_pay(level: int) -> void:
	pay_level = clampi(level, 0, PAY.size() - 1)
	normalize()
	gs.stats_changed.emit()


# ------------------------------------------------------------------ day cycle
func new_day(report: Array) -> void:
	normalize()
	strike = false
	last_work = {}
	if gs.workers.is_empty():
		return
	var mandor := count("mandor") > 0
	var min_sat := 100.0
	for w in gs.workers:
		var s: float = float(w["sat"])
		s += (target_sat(w) - s) * 0.35
		if mandor and w["role"] == "buruh":
			s -= 3.0
		if gs.sys.weather.today == "badai":
			s -= 4.0
		w["sat"] = clampf(s, 0.0, 100.0)
		min_sat = minf(min_sat, w["sat"])
	# strike?
	if count("buruh") > 0:
		var bs := avg_sat("buruh")
		var chance := 0.0
		if bs < 35.0:
			chance = 0.55 - (0.25 if mandor else 0.0)
		elif min_sat < 20.0:
			chance = 0.25
		if gs.rng.randf() < chance:
			strike = true
			strikes += 1
			for w in gs.workers:
				w["sat"] = maxf(0.0, float(w["sat"]) - 3.0)
			report.append("MOGOK! Buruhmu mogok kerja! Mereka duduk-duduk di depan kantor membawa kardus bertuliskan 'UPAH LAYAK'.")
			gs.sys.events.append("mogok")
			return
	pay(report)
	work(report)


func pay(report: Array) -> void:
	var kept: Array = []
	var total := 0
	for w in gs.workers:
		var wage := int(w["wage"])
		if gs.money >= wage:
			gs.money -= wage
			total += wage
			kept.append(w)
		else:
			report.append("%s berhenti kerja karena upahnya tidak dibayar." % w["name"])
			if str(w.get("vid", "")) != "" and gs.villagers.has(w["vid"]):
				gs.villagers[w["vid"]]["worker"] = false
	gs.workers = kept
	if not kept.is_empty():
		report.append("Upah %d pekerja dibayar: %s (gaji %s)." % [kept.size(), gs.fmt_rp(total), PAY[pay_level]["name"]])


func work(report: Array, factor := 1.0) -> Dictionary:
	## the crew works your parcels; returns {"harvest", "stored", "sold", "planted", "cleared"}
	var h := 0.0
	var pl := 0.0
	var cl := 0.0
	for w in gs.workers:
		if w["role"] != "buruh":
			continue
		var p := productivity(float(w["sat"]))
		h += HARVEST_PER * p
		pl += PLANT_PER * p
		cl += CLEAR_PER * p
	var k: float = factor * (MANDOR_BOOST if count("mandor") > 0 else 1.0) * (0.5 if gs.sys.weather.today == "badai" else 1.0)
	var hb := int(round(h * k))
	var pb := int(round(pl * k))
	var cb := int(round(cl * k))
	var harvested := 0
	var palms := 0
	var planted := 0
	var cleared := 0
	for p in gs.parcels:
		if p["owner"] != "player":
			continue
		var tiles: Array = p["tiles"]
		for i in tiles.size():
			var t: Dictionary = tiles[i]
			if gs.sys.weather.fire_index(int(p["id"]), i) >= 0:
				continue   # nobody works in the fire
			if hb > 0 and t["s"] == "palm" and t["fr"]:
				harvested += gs.sys.tech.fert_yield() if t["f"] else 1
				t["fr"] = false
				t["fd"] = 0
				t["f"] = false
				hb -= 1
				palms += 1
			elif pb > 0 and t["s"] == "empty" and int(gs.inv.get("bibit", 0)) > 0:
				gs.inv["bibit"] = int(gs.inv["bibit"]) - 1
				var nt: Dictionary = gs._tile("palm", 0)
				gs.sys.tech.on_planted(nt)
				tiles[i] = nt
				gs.stats["planted"] = int(gs.stats.get("planted", 0)) + 1
				pb -= 1
				planted += 1
			elif cb > 0 and t["s"] == "bush":
				t["s"] = "empty"
				gs.stats["cleared"] = int(gs.stats.get("cleared", 0)) + 1
				cb -= 1
				cleared += 1
	var stored: int = gs.sys.market.store(harvested)
	var sold: int = gs.sys.market.sell_overflow(harvested - stored)
	gs.stats["harvested"] = int(gs.stats.get("harvested", 0)) + harvested
	if harvested > 0:
		var line := "Buruh memanen %d TBS dari %d pohon; %d masuk gudang" % [harvested, palms, stored]
		if harvested > stored:
			line += ", %d sisanya dijual ke tengkulak (%s)" % [harvested - stored, gs.fmt_rp(sold)]
		report.append(line + ".")
	if planted > 0 or cleared > 0:
		report.append("Buruh menanam %d bibit dan menebas %d semak." % [planted, cleared])
	if count("buruh") > 0 and avg_sat("buruh") < 60.0:
		report.append("Buruh kerja lambat-lambat (kepuasan %d%%). Gajinya kurang, katanya." % int(avg_sat("buruh")))
	last_work = {"harvest": harvested, "stored": stored, "sold": sold, "planted": planted, "cleared": cleared}
	return last_work


func end_strike(how: String) -> String:
	## the mogok event's choice; returns the toast text
	var report: Array = []
	match how:
		"naik":
			set_pay(mini(pay_level + 1, PAY.size() - 1))
			for w in gs.workers:
				w["sat"] = minf(100.0, float(w["sat"]) + 22.0)
			gs.add_rep(3.0)
			pay(report)
			work(report)
			strike = false
			return "Gaji naik ke '%s'. Buruh bersorak dan kembali kerja." % PAY[pay_level]["name"]
		"ancam":
			for w in gs.workers:
				w["sat"] = maxf(0.0, float(w["sat"]) - 10.0)
			gs.add_heat(6.0)
			gs.add_rep(-5.0)
			pay(report)
			work(report, 0.7)
			strike = false
			return "Buruh kembali kerja sambil menggerutu. Ada yang merekam ancamanmu..."
		"pecat":
			var n := 0
			for i in range(gs.workers.size() - 1, -1, -1):
				if gs.workers[i]["role"] == "buruh":
					fire(i)
					n += 1
			gs.add_rep(-6.0)
			gs.add_heat(3.0)
			strike = false
			return "%d buruh dipecat tanpa pesangon. Cari buruh baru di Kantor." % n
	return ""


# ------------------------------------------------------------------ save
func to_dict() -> Dictionary:
	return {"pay": pay_level, "strike": strike, "strikes": strikes}


func from_dict(d: Dictionary) -> void:
	pay_level = clampi(int(d.get("pay", 1)), 0, PAY.size() - 1)
	strike = bool(d.get("strike", false))
	strikes = int(d.get("strikes", 0))
	normalize()
