class_name WeatherSys
extends RefCounted
## Seasons and daily weather (logic only; the rain, smoke and fires are drawn by
## scripts/world/weather_fx.gd).
##
## The year alternates SEASON_DAYS of musim hujan (wet) and musim kemarau (dry),
## starting wet on day 1. Each morning rolls the day's weather from the season's odds:
## - hujan / badai make palms grow faster (a chance of an extra growth step each) and
##   put out burning land; badai halves the workers' output and lifts the TBS price
##   (trucks cannot get through, the mill is short of fruit).
## - kemarau: the longer it has not rained and the more land you have cleared, the
##   likelier land fires (kebakaran lahan) start on and around your parcels. A fire
##   left burning overnight scorches its tile (young palms die, ripe bunches burn,
##   thickets turn to ash: "lahan siap tanam, gratis") and may spread to the next
##   spot; if it was on your land, Kecurigaan rises and the village chokes in a
##   kabut asap (event). Put fires out on the spot: "Padamkan api".
## - heavy rain after a lot of clearing floods a village (banjir event).

const SEASON_DAYS := 10
const KINDS := ["cerah", "berawan", "hujan", "badai"]
const NAMES := {"cerah": "Cerah", "berawan": "Berawan", "hujan": "Hujan", "badai": "Badai"}
## weather odds per season, in KINDS order
const ODDS := {"hujan": [22, 30, 36, 12], "kemarau": [58, 32, 10, 0]}
## chance of an extra growth step per palm on a rainy day
const RAIN_GROWTH := {"hujan": 0.35, "badai": 0.5}
const FIRE_ENERGY := 6.0
const MAX_FIRES := 6
## cleared tiles (player + franchise land) above which heavy rain can flood a village
const FLOOD_CLEARED := 45

var gs   # the GS autoload (untyped: no cyclic script dependency)
var today := "cerah"
var dry_days := 0                 # days since it last rained
var fires: Array = []             # [{"pid": int, "idx": int, "age": int}]
var smoke := 0.0                  # kabut asap from last night's fires on your land (today only)
var flood := ""                   # village id flooded today ("" = none)
var smoke_cooldown := 0           # days until the next kabut asap event can happen
var fires_out := 0                # fires the player put out (all time)
var fires_burned := 0             # tiles scorched (all time)


func reset() -> void:
	today = "cerah"
	dry_days = 0
	fires = []
	smoke = 0.0
	flood = ""
	smoke_cooldown = 0
	fires_out = 0
	fires_burned = 0


# ------------------------------------------------------------------ queries
func season(day := -1) -> String:
	var d: int = gs.day if day < 0 else day
	return "hujan" if ((d - 1) / SEASON_DAYS) % 2 == 0 else "kemarau"


func season_name(day := -1) -> String:
	return "Musim Hujan" if season(day) == "hujan" else "Musim Kemarau"


func season_day(day := -1) -> int:
	var d: int = gs.day if day < 0 else day
	return (d - 1) % SEASON_DAYS + 1


func is_rainy() -> bool:
	return today == "hujan" or today == "badai"


func weather_name() -> String:
	return NAMES.get(today, "Cerah")


func fire_index(pid: int, idx: int) -> int:
	for i in fires.size():
		if int(fires[i]["pid"]) == pid and int(fires[i]["idx"]) == idx:
			return i
	return -1


func cleared_tiles() -> int:
	## tiles of player and franchise land that are no longer forest / garden
	var n := 0
	for p in gs.parcels:
		if p["owner"] == "player" or p["plasma"]:
			for t in p["tiles"]:
				if t["s"] != "bush":
					n += 1
	return n


func fire_on_player_land() -> int:
	var n := 0
	for f in fires:
		var p: Dictionary = gs.parcels[int(f["pid"])]
		if p["owner"] == "player" or p["plasma"]:
			n += 1
	return n


# ------------------------------------------------------------------ actions
func fire_action(pid: int, idx: int) -> Dictionary:
	## the context action on a burning tile (GS.tile_action_info), {} if not burning
	if fire_index(pid, idx) < 0:
		return {}
	return {"verb": "Padamkan api!", "ok": true, "kind": "padam"}


func put_out(pid: int, idx: int) -> bool:
	var i := fire_index(pid, idx)
	if i < 0:
		return false
	if not gs.use_energy(FIRE_ENERGY):
		return false
	fires.remove_at(i)
	fires_out += 1
	var p: Dictionary = gs.parcels[pid]
	if p["owner"] != "player" and not p["plasma"]:
		# a neighbour's garden: the villagers notice
		gs.add_rep(1.5)
		var v: Dictionary = gs.villagers.get(p["owner"], {})
		if not v.is_empty():
			v["trust"] = minf(100.0, float(v["trust"]) + 4.0)
	gs.stats_changed.emit()
	return true


# ------------------------------------------------------------------ day cycle
func roll(report: Array) -> void:
	## the new day's weather (GS.start_new_day, after day += 1, before the palms grow)
	var odds: Array = ODDS[season()]
	var total := 0
	for o in odds:
		total += int(o)
	var r: int = gs.rng.randi_range(1, total)
	today = KINDS[KINDS.size() - 1]
	for i in KINDS.size():
		r -= int(odds[i])
		if r <= 0:
			today = KINDS[i]
			break
	if is_rainy():
		dry_days = 0
	else:
		dry_days += 1
	flood = ""
	smoke = 0.0
	smoke_cooldown = maxi(0, smoke_cooldown - 1)
	if season_day() == 1 and gs.day > 1:
		if season() == "kemarau":
			report.append("Musim kemarau tiba! Lahan kering mudah terbakar. Awasi titik api di kebunmu.")
		else:
			report.append("Musim hujan tiba! Sawit tumbuh lebih cepat... dan sungai bisa meluap.")
	var line := "Cuaca: %s hari ke-%d, %s." % [season_name(), season_day(), weather_name().to_lower()]
	match today:
		"hujan":
			line += " Hujan menyiram kebun, sawit tumbuh lebih cepat."
		"badai":
			line += " Badai! Buruh kerja setengah hari, truk sulit lewat."
		"cerah":
			if season() == "kemarau" and dry_days >= 4:
				line += " Sudah %d hari tidak hujan. Rawan kebakaran." % dry_days
	report.append(line)


func after_growth(report: Array) -> void:
	## rain bonus growth, fires burning / spreading / starting, floods
	if is_rainy():
		var k: float = RAIN_GROWTH[today]
		var n := 0
		for p in gs.parcels:
			if p["owner"] != "player" and not p["plasma"]:
				continue
			for t in p["tiles"]:
				if t["s"] == "palm" and not t["fr"] and gs.rng.randf() < k:
					gs.grow_tile(t)
					n += 1
		if n > 0:
			report.append("Hujan membuat %d pohon sawit tumbuh lebih cepat." % n)
	_burn(report)
	_ignite(report)
	_flood(report)


func _burn(report: Array) -> void:
	## fires left burning overnight scorch their tile and may spread
	if fires.is_empty():
		return
	if is_rainy():
		report.append("Hujan memadamkan %d titik api. Alhamdulillah, gratis." % fires.size())
		fires.clear()
		return
	var spread: Array = []
	var on_mine := 0
	var scorched := 0
	for f in fires:
		var pid := int(f["pid"])
		var idx := int(f["idx"])
		var p: Dictionary = gs.parcels[pid]
		var t: Dictionary = p["tiles"][idx]
		var mine: bool = p["owner"] == "player" or p["plasma"]
		if mine:
			on_mine += 1
		match t["s"]:
			"bush":
				t["s"] = "empty"   # "lahan siap tanam" — burned for free
			"palm":
				if int(t["st"]) <= 1:
					p["tiles"][idx] = gs._tile("empty")
				else:
					t["fr"] = false
					t["fd"] = 0
					t["f"] = false
		scorched += 1
		f["age"] = int(f["age"]) + 1
		if gs.rng.randf() < 0.45:
			var nidx: int = idx + (1 if gs.rng.randf() < 0.5 else -1)
			if nidx >= 0 and nidx < p["tiles"].size():
				spread.append({"pid": pid, "idx": nidx, "age": 0})
	fires_burned += scorched
	fires = fires.filter(func(f): return int(f["age"]) < 2)
	for s in spread:
		if fires.size() < MAX_FIRES and fire_index(int(s["pid"]), int(s["idx"])) < 0:
			fires.append(s)
	report.append("Api semalam menghanguskan %d petak%s." % [scorched, " dan merambat" if not spread.is_empty() else ""])
	if on_mine > 0:
		gs.heat = clampf(gs.heat + minf(6.0 * on_mine, 20.0), 0.0, 100.0)
		report.append("Kebakaran di lahanmu terpantau satelit. Kecurigaan +%d." % int(minf(6.0 * on_mine, 20.0)))
		smoke = 0.7
		if smoke_cooldown <= 0:
			gs.sys.events.append("kabut_asap")
			smoke_cooldown = 3


func _ignite(report: Array) -> void:
	if season() != "kemarau" or is_rainy() or fires.size() >= MAX_FIRES:
		return
	var cleared := cleared_tiles()
	var chance := 0.1 + 0.035 * minf(dry_days, 8) + 0.2 * minf(cleared / 80.0, 1.0)
	if today == "berawan":
		chance *= 0.6
	if gs.rng.randf() >= chance:
		return
	var n: int = 1 + gs.rng.randi_range(0, 1 + dry_days / 4)
	var started: Array = []
	for i in n:
		var spot := _fire_spot()
		if spot.is_empty() or fires.size() >= MAX_FIRES:
			break
		fires.append(spot)
		var pname: String = gs.parcels[int(spot["pid"])]["name"]
		if not pname in started:
			started.append(pname)
	if not started.is_empty():
		report.append("AWAS API! Titik api terlihat di %s! Padamkan sebelum menjalar (hadap petak yang terbakar, tekan aksi)." % ", ".join(started))


func _fire_spot() -> Dictionary:
	## a tile that can catch fire: mostly your own land, else a garden next to it
	var mine: Array = []
	var near: Array = []
	for p in gs.parcels:
		var pid := int(p["id"])
		var own: bool = p["owner"] == "player" or p["plasma"]
		for i in p["tiles"].size():
			var t: Dictionary = p["tiles"][i]
			if fire_index(pid, i) >= 0:
				continue
			if own and (t["s"] != "palm" or int(t["st"]) <= 2):
				mine.append([pid, i])
			elif not own and t["s"] == "bush" and pid <= 6:
				near.append([pid, i])   # the gardens around Sukamakmur
	var pool: Array = mine if (gs.rng.randf() < 0.65 and not mine.is_empty()) or near.is_empty() else near
	if pool.is_empty():
		return {}
	var pick: Array = pool[gs.rng.randi() % pool.size()]
	return {"pid": int(pick[0]), "idx": int(pick[1]), "age": 0}


func _flood(report: Array) -> void:
	if not is_rainy() or season() != "hujan":
		return
	var cleared := cleared_tiles()
	if cleared < FLOOD_CLEARED:
		return
	var chance := (0.5 if today == "badai" else 0.12) + float(cleared - FLOOD_CLEARED) / 300.0
	if gs.rng.randf() >= chance:
		return
	var vs: Array = gs.load_layout().get("villages", [])
	if vs.is_empty():
		return
	flood = str(vs[gs.rng.randi() % vs.size()]["id"])
	gs.add_rep(-4.0)
	for vid in gs.villagers:
		gs.villagers[vid]["trust"] = maxf(0.0, float(gs.villagers[vid]["trust"]) - 3.0)
	report.append("BANJIR! Sungai meluap, %s kebanjiran. Warga bilang hutan di hulu sudah jadi kebun sawit." % village_name(flood))
	gs.sys.events.append("banjir")


func village_name(id: String) -> String:
	return "Desa Sukamakmur" if id == "sukamakmur" else "Dusun " + id.capitalize()


func haze() -> float:
	## smoke over the island today, 0..1 (weather_fx tints the screen with it)
	return clampf(maxf(smoke, fires.size() * 0.16), 0.0, 0.8)


# ------------------------------------------------------------------ save
func to_dict() -> Dictionary:
	return {"today": today, "dry": dry_days, "fires": fires, "smoke": smoke, "flood": flood,
		"smoke_cd": smoke_cooldown, "out": fires_out, "burned": fires_burned}


func from_dict(d: Dictionary) -> void:
	today = str(d.get("today", "cerah"))
	if not today in KINDS:
		today = "cerah"
	dry_days = int(d.get("dry", 0))
	fires = []
	for f in d.get("fires", []):
		if typeof(f) == TYPE_DICTIONARY and int(f.get("pid", -1)) >= 0 and int(f["pid"]) < gs.parcels.size():
			fires.append({"pid": int(f["pid"]), "idx": int(f.get("idx", 0)), "age": int(f.get("age", 0))})
	smoke = float(d.get("smoke", 0.0))
	flood = str(d.get("flood", ""))
	smoke_cooldown = int(d.get("smoke_cd", 0))
	fires_out = int(d.get("out", 0))
	fires_burned = int(d.get("burned", 0))
