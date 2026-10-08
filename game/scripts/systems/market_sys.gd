class_name MarketSys
extends RefCounted
## The TBS market and the gudang (logic; the chart and menus are scripts/ui/systems_ui.gd).
##
## - The mill price moves every morning: a random walk, pulled back toward the season's
##   base (the wet season floods the mill with fruit: cheaper; the dry season: dearer),
##   plus the weather (a storm cuts the roads: the mill pays more). The last HISTORY
##   days are kept for the 14-day chart in the pabrik menu.
## - The gudang (the shed beside your first parcel) stores TBS in batches by age. Fresh
##   fruit spoils: the mill's sortasi cuts the price of old bunches and after a few days
##   they rot (they become compost: pupuk). So: sell high, but not too late. Workers'
##   harvests go to the gudang (what does not fit goes to a tengkulak at 80%).
## - "Main mata" with Pak Gondrong, the mill's weighbridge foreman: pay him and today's
##   TBS weighs 15% more. Kecurigaan rises (and he may get filmed).

const HISTORY := 14
const BASE := {"hujan": 140000, "kemarau": 168000}
const MIN_PRICE := 90000
const MAX_PRICE := 240000
const WEATHER_PUSH := {"cerah": 0, "berawan": 0, "hujan": 3000, "badai": 14000}
## sale value by age in days (index), the batch rots at the table's end
const QUALITY := [1.0, 0.95, 0.85, 0.7]
const QUALITY_GOOD := [1.0, 0.98, 0.94, 0.88, 0.8, 0.7]    # gudang besar (bersih): ventilated
const QUALITY_FORMALIN := 0.97                              # gudang besar (kotor): never rots
const CAP_BASE := 40
const CAP_BIG := 150
const BRIBE_COST := 300000
const BRIBE_BONUS := 0.15
const BRIBE_HEAT := 7.0
const TENGKULAK := 0.8

var gs
var history: Array = []     # daily prices, oldest first; the last one is today's
var gudang: Array = []      # batches [qty, age]
var bribe_day := 0          # the day Pak Gondrong was paid ("main mata")
var rotted := 0             # TBS rotted in the gudang (all time)


func reset() -> void:
	history = [150000]
	gudang = []
	bribe_day = 0
	rotted = 0


# ------------------------------------------------------------------ price
func new_day(report: Array) -> void:
	var old: int = gs.tbs_price
	var base: int = BASE[gs.sys.weather.season()]
	var walk: int = gs.rng.randi_range(-3, 3) * 8000 + int(gs.tbs_trend) * 5000
	var revert := int((base - old) * 0.18)
	var push: int = WEATHER_PUSH.get(gs.sys.weather.today, 0)
	gs.tbs_price = clampi(old + walk + revert + push, MIN_PRICE, MAX_PRICE)
	gs.tbs_trend = gs.rng.randi_range(-1, 1)
	history.append(gs.tbs_price)
	while history.size() > HISTORY:
		history.pop_front()
	var p: int = gs.tbs_price
	report.append("Harga TBS hari ini: %s/tandan (%s)" % [gs.fmt_rp(p), "naik" if p > old else ("turun" if p < old else "stabil")])
	_spoil(report)


func sync_today() -> void:
	## morning events (harga_naik) change the price after it was recorded
	if history.is_empty():
		history.append(gs.tbs_price)
	elif int(history[-1]) != gs.tbs_price:
		history[-1] = gs.tbs_price


func change() -> int:
	## today's price against yesterday's
	sync_today()
	if history.size() < 2:
		return 0
	return int(history[-1]) - int(history[-2])


func average() -> int:
	sync_today()
	var s := 0
	for v in history:
		s += int(v)
	return s / maxi(1, history.size())


func bribed() -> bool:
	return bribe_day == gs.day


func sale_price() -> int:
	## what the mill pays per tandan today (Pak Gondrong's weighbridge included)
	return int(round(gs.tbs_price * (1.0 + (BRIBE_BONUS if bribed() else 0.0))))


func bribe() -> String:
	## "main mata" with the weighbridge foreman: "" if refused, else "ok" / "caught"
	if bribed() or not gs.spend(BRIBE_COST):
		return ""
	bribe_day = gs.day
	gs.stats["bribes"] = int(gs.stats.get("bribes", 0)) + 1
	gs.add_rep(-1.0)
	if gs.rng.randf() < 0.12 + gs.heat / 500.0:
		gs.add_heat(BRIBE_HEAT + 12.0)
		return "caught"
	gs.add_heat(BRIBE_HEAT)
	return "ok"


# ------------------------------------------------------------------ gudang
func capacity() -> int:
	return CAP_BIG if gs.sys.tech.level("gudang") != "" else CAP_BASE


func stock() -> int:
	var n := 0
	for b in gudang:
		n += int(b[0])
	return n


func room() -> int:
	return maxi(0, capacity() - stock())


func _table() -> Array:
	return QUALITY_GOOD if gs.sys.tech.level("gudang") == "bersih" else QUALITY


func formalin() -> bool:
	return gs.sys.tech.level("gudang") == "kotor"


func quality(age: int) -> float:
	if formalin():
		return QUALITY_FORMALIN if age > 0 else 1.0
	var t := _table()
	return float(t[mini(age, t.size() - 1)])


func max_age() -> int:
	## a batch this old rots tomorrow morning
	return 9999 if formalin() else _table().size() - 1


func store(n: int) -> int:
	## puts n fresh TBS in the gudang; returns how many fit
	var k := mini(n, room())
	if k <= 0:
		return 0
	if not gudang.is_empty() and int(gudang[-1][1]) == 0:
		gudang[-1][0] = int(gudang[-1][0]) + k
	else:
		gudang.append([k, 0])
	return k


func take(n: int) -> int:
	## takes up to n TBS out (freshest first); returns how many
	var got := 0
	while got < n and not gudang.is_empty():
		var b: Array = gudang[-1]
		var k := mini(int(b[0]), n - got)
		b[0] = int(b[0]) - k
		got += k
		if int(b[0]) <= 0:
			gudang.pop_back()
	return got


func take_oldest(n: int) -> int:
	var got := 0
	while got < n and not gudang.is_empty():
		var b: Array = gudang[0]
		var k := mini(int(b[0]), n - got)
		b[0] = int(b[0]) - k
		got += k
		if int(b[0]) <= 0:
			gudang.pop_front()
	return got


func value(mult := 1.0) -> int:
	## what the gudang's stock fetches at the mill today (sortasi cuts for old fruit)
	var v := 0.0
	for b in gudang:
		v += int(b[0]) * sale_price() * quality(int(b[1])) * mult
	return int(v)


func oldest_age() -> int:
	return int(gudang[0][1]) if not gudang.is_empty() else -1


func sell_gudang(mult := 1.0) -> int:
	## sells the whole stock; returns the money
	var n := stock()
	if n <= 0:
		return 0
	var got := value(mult)
	gudang.clear()
	gs.add_money(got)
	gs.stats["tbs_sold"] = int(gs.stats.get("tbs_sold", 0)) + n
	gs.check_quests()
	return got


func sell_overflow(n: int) -> int:
	## harvest that does not fit in the gudang: a passing tengkulak takes it cheap
	if n <= 0:
		return 0
	var got := int(n * gs.tbs_price * TENGKULAK)
	gs.money += got
	gs.stats["earned"] = int(gs.stats.get("earned", 0)) + got
	gs.stats["tbs_sold"] = int(gs.stats.get("tbs_sold", 0)) + n
	return got


func _spoil(report: Array) -> void:
	if gudang.is_empty():
		return
	var rot := 0
	var keep: Array = []
	for b in gudang:
		b[1] = int(b[1]) + 1
		if int(b[1]) > max_age():
			rot += int(b[0])
		else:
			keep.append(b)
	gudang = keep
	if rot > 0:
		rotted += rot
		var compost := rot / 4
		if compost > 0:
			gs.inv["pupuk"] = int(gs.inv.get("pupuk", 0)) + compost
		report.append("%d TBS di gudang busuk dan dibuang%s. Harusnya dijual kemarin..." % [rot,
			(" (jadi kompos: +%d pupuk)" % compost) if compost > 0 else ""])
	elif oldest_age() >= max_age():
		report.append("TBS tertua di gudang sudah %d hari. Besok busuk!" % oldest_age())


# ------------------------------------------------------------------ save
func to_dict() -> Dictionary:
	return {"history": history, "gudang": gudang, "bribe_day": bribe_day, "rotted": rotted}


func from_dict(d: Dictionary) -> void:
	history = []
	for v in d.get("history", []):
		history.append(int(v))
	if history.is_empty():
		history = [gs.tbs_price]
	gudang = []
	for b in d.get("gudang", []):
		if typeof(b) == TYPE_ARRAY and b.size() >= 2 and int(b[0]) > 0:
			gudang.append([int(b[0]), int(b[1])])
	bribe_day = int(d.get("bribe_day", 0))
	rotted = int(d.get("rotted", 0))
