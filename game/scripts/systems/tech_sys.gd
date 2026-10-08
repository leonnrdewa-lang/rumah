class_name TechSys
extends RefCounted
## The Kantor's upgrade tree (logic; the menu is scripts/ui/systems_ui.gd). Each upgrade
## comes "bersih" (clean: expensive, safe) or "kotor" (dirty: cheap, with Kecurigaan /
## harm to the villagers), stored in GS.upgrades["t_<id>"] = "bersih" | "kotor" (old
## saves simply have none). A dirty upgrade can later be made clean ("legalkan") by
## paying the clean price.
##
##   bibit  ──► pupuk          jalan ──► truk          gudang ──► pabrik
##
## - bibit:  seedlings skip a day of the bibit stage (kotor: 15% are fakes that die)
## - pupuk:  fertilised palms bear 3 bunches instead of 2 (kotor: runoff, fish die)
## - jalan:  walk 35% faster around your parcels, no mud in the rain (kotor: cut
##           through the protected forest)
## - truk:   with a sopir, the gudang is sold every morning when the price beats the
##           14-day average or the fruit is about to rot (kotor: ODOL truck wrecks the
##           village road)
## - gudang: 150 TBS of storage, slower spoiling (kotor: formalin, never rots)
## - pabrik: a mini oil mill at the gudang: 1 TBS -> 4 jerigen of minyak goreng without
##           going to the PKS; sell the oil to the city agent (kotor: the waste goes
##           in the river)

const TREE := {
	"bibit": {"name": "Bibit Unggul", "icon": "icon_bibit", "needs": "",
		"desc": "Bibit melewati tahap kecambah 1 hari lebih cepat.",
		"bersih": {"label": "Bersertifikat", "price": 1500000, "desc": "Dari balai benih resmi. Mahal, tapi pasti tumbuh."},
		"kotor": {"label": "Selundupan", "price": 500000, "heat": 10.0, "rep": -2.0,
			"desc": "Kecambah 'unggul' dari truk tanpa nomor. Kecurigaan +10, 15% bibit ternyata palsu dan mati."}},
	"pupuk": {"name": "Pupuk Premium", "icon": "icon_pupuk", "needs": "bibit",
		"desc": "Pohon yang dipupuk berbuah 3 tandan, bukan 2.",
		"bersih": {"label": "Organik + kompos tankos", "price": 2500000, "desc": "Tanah sehat, sungai tetap jernih."},
		"kotor": {"label": "Oplosan + pestisida keras", "price": 800000, "heat": 4.0,
			"desc": "Limbahnya mengalir ke sungai: reputasi -1/hari, kadang ikan warga mati."}},
	"jalan": {"name": "Jalan Kebun", "icon": "icon_parang", "needs": "",
		"desc": "Jalan 35% lebih cepat di sekitar kebunmu, tidak becek saat hujan.",
		"bersih": {"label": "Diperkeras sirtu", "price": 1500000, "desc": "Izin lengkap. Warga ikut lewat."},
		"kotor": {"label": "Jalan pintas hutan lindung", "price": 500000, "heat": 12.0, "rep": -6.0,
			"desc": "Membelah hutan lindung pakai ekskavator sewaan. Kecurigaan +12, reputasi -6."}},
	"truk": {"name": "Truk Angkut", "icon": "icon_truk", "needs": "jalan",
		"desc": "Dengan sopir truk, stok gudang otomatis dijual saat harga di atas rata-rata 14 hari atau TBS hampir busuk.",
		"bersih": {"label": "Truk resmi, KIR lengkap", "price": 5000000, "desc": "Muat sesuai aturan. Jalan desa aman."},
		"kotor": {"label": "Truk ODOL tanpa KIR", "price": 2000000,
			"desc": "Over dimension over load. Jalan desa hancur: reputasi -2 & kecurigaan +1 tiap hari."}},
	"gudang": {"name": "Gudang Besar", "icon": "icon_rumah", "needs": "",
		"desc": "Kapasitas gudang 40 → 150 tandan.",
		"bersih": {"label": "Berventilasi", "price": 3000000, "desc": "TBS lebih lambat busuk (tahan 5 hari)."},
		"kotor": {"label": "Semprot formalin", "price": 1000000,
			"desc": "TBS tidak pernah busuk! Selama ada stok: kecurigaan +1 & reputasi -1 tiap hari."}},
	"pabrik": {"name": "Pabrik Minyak Mini", "icon": "icon_minyak", "needs": "gudang",
		"desc": "Olah TBS jadi minyak goreng di gudangmu sendiri: 1 TBS → 4 jerigen, jual ke agen kota.",
		"bersih": {"label": "Dengan IPAL", "price": 8000000, "desc": "Limbah diolah dulu. Biaya olah Rp 8rb/TBS."},
		"kotor": {"label": "Limbah ke sungai", "price": 3500000,
			"desc": "Biaya olah Rp 2rb/TBS. Tiap hari mengolah: kecurigaan +2, reputasi -2, warga hilir gatal-gatal."}},
}
const ORDER := ["bibit", "pupuk", "jalan", "truk", "gudang", "pabrik"]
const OIL_PER_TBS := 4
const OIL_COST := {"bersih": 8000, "kotor": 2000}
const OIL_AGENT_PRICE := 40000
const FAKE_SEED := 0.15
const WALK_BOOST := 1.35

var gs
var oil_today := 0     # TBS milled at home today (the dirty mill's waste)
var truck_sold := 0    # TBS the truck sold (all time)


func reset() -> void:
	oil_today = 0
	truck_sold = 0


# ------------------------------------------------------------------ queries
func level(id: String) -> String:
	return str(gs.upgrades.get("t_" + id, ""))


func owned(id: String) -> bool:
	return level(id) != ""


func unlocked(id: String) -> bool:
	var need: String = TREE[id]["needs"]
	return need == "" or owned(need)


func growth_bonus(stage: int) -> int:
	## days taken off a palm's growth stage (GS.stage_need)
	return 1 if stage == 0 and owned("bibit") else 0


func fert_yield() -> int:
	return 3 if owned("pupuk") else 2


func walk_mult() -> float:
	return WALK_BOOST if owned("jalan") else 1.0


func oil_ready() -> bool:
	return owned("pabrik")


# ------------------------------------------------------------------ actions
func buy(id: String, variant: String) -> bool:
	if not TREE.has(id) or not variant in ["bersih", "kotor"] or not unlocked(id):
		return false
	if level(id) == variant or level(id) == "bersih":
		return false
	var v: Dictionary = TREE[id][variant]
	if not gs.spend(int(v["price"])):
		return false
	gs.upgrades["t_" + id] = variant
	if v.has("heat"):
		gs.add_heat(float(v["heat"]))
	if v.has("rep"):
		gs.add_rep(float(v["rep"]))
	gs.stats_changed.emit()
	return true


func on_planted(t: Dictionary) -> void:
	## a seedling was just planted (by you or the crew): fake seeds are marked
	if level("bibit") == "kotor" and gs.rng.randf() < FAKE_SEED:
		t["dud"] = true


func mill(n: int) -> int:
	## the mini oil mill: up to n TBS (carried first, then the gudang's oldest) -> minyak;
	## returns how many TBS were milled
	if not oil_ready() or n <= 0:
		return 0
	var cost: int = OIL_COST[level("pabrik")]
	n = mini(n, gs.money / maxi(1, cost))
	var from_bag := mini(n, int(gs.inv.get("tbs", 0)))
	var from_shed: int = gs.sys.market.take_oldest(n - from_bag)
	var done := from_bag + from_shed
	if done <= 0:
		return 0
	gs.inv["tbs"] = int(gs.inv["tbs"]) - from_bag
	gs.money -= cost * done
	gs.add_item("minyak", done * OIL_PER_TBS)
	oil_today += done
	return done


func sell_oil_agent() -> int:
	var n := int(gs.inv.get("minyak", 0))
	if n <= 0:
		return 0
	gs.inv["minyak"] = 0
	gs.stats["oil_sold"] = int(gs.stats.get("oil_sold", 0)) + n
	gs.add_money(n * OIL_AGENT_PRICE)
	return n * OIL_AGENT_PRICE


# ------------------------------------------------------------------ day cycle
func new_day(report: Array) -> void:
	# fake seedlings die as they leave the bibit stage
	var duds := 0
	for p in gs.parcels:
		if p["owner"] != "player" and not p["plasma"]:
			continue
		for i in p["tiles"].size():
			var t: Dictionary = p["tiles"][i]
			if t.get("dud", false) and t["s"] == "palm" and int(t["st"]) >= 1:
				p["tiles"][i] = gs._tile("empty")
				duds += 1
	if duds > 0:
		report.append("%d bibit selundupan ternyata palsu dan mati. Sertifikatnya juga palsu." % duds)
	# the truck and its driver
	if owned("truk") and gs.sys.market.stock() > 0:
		if gs.sys.crew.count("sopir") == 0:
			report.append("Truk angkut nganggur di gudang. Rekrut sopir truk di Kantor.")
		elif gs.sys.crew.strike:
			report.append("Sopir ikut mogok. Truk tidak jalan.")
		else:
			var m = gs.sys.market
			var avg: int = m.average()
			if gs.tbs_price >= avg or m.oldest_age() >= m.max_age() - 1:
				var n: int = m.stock()
				var got: int = m.sell_gudang()
				truck_sold += n
				report.append("Sopir mengantar %d TBS gudang ke pabrik: +%s%s." % [n, gs.fmt_rp(got),
					"" if gs.tbs_price >= avg else " (dijual sebelum busuk)"])
			else:
				report.append("Sopir menahan stok gudang: harga %s di bawah rata-rata %s." % [gs.fmt_short(gs.tbs_price), gs.fmt_short(avg)])
	# the dirty upgrades' daily price
	var rep := 0.0
	var heat := 0.0
	if level("pupuk") == "kotor":
		rep -= 1.0
		if gs.rng.randf() < 0.2:
			gs.sys.events.append("ikan_mati")
	if level("truk") == "kotor":
		rep -= 2.0
		heat += 1.0
	if level("gudang") == "kotor" and gs.sys.market.stock() > 0:
		rep -= 1.0
		heat += 1.0
	if level("pabrik") == "kotor" and oil_today > 0:
		rep -= 2.0
		heat += 2.0
		report.append("Limbah pabrik minyak mini mengalir ke sungai. Warga hilir gatal-gatal.")
	oil_today = 0
	if rep != 0.0 or heat != 0.0:
		gs.rep = clampf(gs.rep + rep, -100.0, 100.0)
		gs.heat = clampf(gs.heat + heat, 0.0, 100.0)
		report.append("Ongkos 'jalan pintas' hari ini: reputasi %d, kecurigaan +%d." % [int(rep), int(heat)])


# ------------------------------------------------------------------ save
func to_dict() -> Dictionary:
	return {"oil_today": oil_today, "truck_sold": truck_sold}


func from_dict(d: Dictionary) -> void:
	oil_today = int(d.get("oil_today", 0))
	truck_sold = int(d.get("truck_sold", 0))
