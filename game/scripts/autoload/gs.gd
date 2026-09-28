extends Node
## Global game state for Sawit The Franchise: money, time, inventory, land,
## villagers, reputation/suspicion, quests and save/load.

signal stats_changed
signal toast(text: String, kind: String)
signal quest_changed
signal parcel_changed(pid: int)
signal villager_changed(vid: String)
signal day_started(report: Array)
signal game_over(reason: String)
signal game_won

const SAVE_PATH := "user://sawit_save.json"
## 2 = map v3 (20 parcels of 20 staggered tiles, 19 villagers); older saves start over
const SAVE_VERSION := 2
const DAY_START := 6.0
const DAY_END := 24.0
const HOURS_PER_SECOND := 1.0 / 12.0  # one in-game hour lasts 12 real seconds

const PRICE := {
	"bibit": 60000, "pupuk": 35000, "nasi": 15000, "kopi": 5000,
	"surat": 400000, "preman": 1500000, "amplop": 2000000,
	"gerobak": 750000, "truk": 4000000, "mesin": 4000000, "csr": 1500000,
	"buruh_upah": 150000, "buruh_murah": 60000, "lisensi": 20000000,
	"olah": 10000, "minyak_grosir": 30000, "franchise_fee": 2500000, "pancing": 50000,
}
## Fish (mancing): where they bite ("sea" = the coast, the lagoon and the jetty;
## "river" = the rivers and under the bridges), how often (weight), when (hours, empty =
## all day), sell price (warung / koperasi), how hard the timing bar is (0..1) and the
## rarity tier (N / R / SR / SSR, see RARITY). 20 species: 8 N, 6 R, 4 SR, 2 SSR.
const FISH := {
	# species and tiers follow the Higgsfield fish sheet (assets/ui/fish_sheet.png)
	# --- N (normal)
	"ikan_nila": {"name": "Ikan Nila", "rar": "N", "water": ["river"], "w": 30, "price": 25000, "hard": 0.15,
		"desc": "Ikan sungai sejuta umat. Enak dibakar."},
	"ikan_lele": {"name": "Ikan Lele", "rar": "N", "water": ["river"], "w": 24, "price": 20000, "hard": 0.2,
		"hours": [17.0, 24.0], "desc": "Suka keluar sore dan malam. Kumisnya lebih rapi dari Pak RT."},
	"ikan_mujair": {"name": "Ikan Mujair", "rar": "N", "water": ["river"], "w": 26, "price": 22000, "hard": 0.15,
		"desc": "Sepupu nila yang kurang terkenal. Tetap enak digoreng kering."},
	"ikan_gabus": {"name": "Ikan Gabus", "rar": "N", "water": ["river"], "w": 20, "price": 30000, "hard": 0.25,
		"desc": "Ikan buas penunggu rawa. Katanya bagus untuk luka operasi."},
	"ikan_patin": {"name": "Ikan Patin", "rar": "N", "water": ["river"], "w": 20, "price": 32000, "hard": 0.25,
		"desc": "Patin sungai, dagingnya lembut. Laku di warung."},
	"ikan_bandeng": {"name": "Ikan Bandeng", "rar": "N", "water": ["sea"], "w": 28, "price": 28000, "hard": 0.15,
		"desc": "Bandeng presto, tulangnya lunak. Oleh-oleh wajib."},
	"ikan_tongkol": {"name": "Ikan Tongkol", "rar": "N", "water": ["sea"], "w": 26, "price": 30000, "hard": 0.2,
		"hours": [5.0, 16.0], "desc": "Enak dibalado. Jangan lupa cabai rawitnya."},
	"ikan_baronang": {"name": "Ikan Baronang", "rar": "N", "water": ["sea"], "w": 22, "price": 35000, "hard": 0.25,
		"desc": "Suka ngemil lumut karang. Durinya beracun, hati-hati."},
	# --- R
	"ikan_bawal": {"name": "Ikan Bawal", "rar": "R", "water": ["sea"], "w": 10, "price": 60000, "hard": 0.4,
		"desc": "Bawal putih laut, pipih dan gurih. Restoran suka."},
	"ikan_kakap": {"name": "Ikan Kakap Merah", "rar": "R", "water": ["sea"], "w": 9, "price": 90000, "hard": 0.5,
		"desc": "Kakap merah dari dermaga. Harganya bikin juragan senyum."},
	"udang_galah": {"name": "Udang Galah", "rar": "R", "water": ["river", "sea"], "w": 8, "price": 80000, "hard": 0.45,
		"hours": [6.0, 11.0], "desc": "Capit birunya panjang. Muncul pagi-pagi di muara."},
	"ikan_belida": {"name": "Ikan Belida", "rar": "R", "water": ["river"], "w": 7, "price": 110000, "hard": 0.5,
		"hours": [16.0, 21.0], "desc": "Ikan pisau bahan pempek asli. Dilindungi... katanya."},
	"ikan_kerapu": {"name": "Ikan Kerapu", "rar": "R", "water": ["sea"], "w": 8, "price": 100000, "hard": 0.5,
		"desc": "Kerapu belang dari balik karang dermaga. Restoran kota antre."},
	"ikan_tenggiri": {"name": "Ikan Tenggiri", "rar": "R", "water": ["sea"], "w": 9, "price": 85000, "hard": 0.45,
		"desc": "Perenang cepat, bahan otak-otak dan pempek. Tarikannya kencang."},
	# --- SR
	"ikan_napoleon": {"name": "Ikan Napoleon", "rar": "SR", "water": ["sea"], "w": 2.2, "price": 450000, "hard": 0.7,
		"desc": "Ikan karang biru berjidat nonong. Katanya makan malam para jenderal."},
	"ikan_pari": {"name": "Pari Manta", "rar": "SR", "water": ["sea"], "w": 2.0, "price": 400000, "hard": 0.72,
		"hours": [16.0, 21.0], "desc": "Terbang di bawah air seperti layangan raksasa. Lepaskan? Atau jual?"},
	"ikan_todak": {"name": "Ikan Todak", "rar": "SR", "water": ["sea"], "w": 2.2, "price": 380000, "hard": 0.68,
		"desc": "Moncongnya pedang. Legenda bilang pernah menyerang Singapura."},
	"ikan_hiu": {"name": "Hiu Kecil", "rar": "SR", "water": ["sea"], "w": 2.4, "price": 350000, "hard": 0.66,
		"hours": [19.0, 24.0, 0.0, 4.0], "desc": "Masih kecil tapi giginya sudah tajam. Senyumnya mencurigakan."},
	# --- SSR
	"ikan_arwana": {"name": "Arwana Emas", "rar": "SSR", "water": ["river", "sea"], "w": 0.7, "price": 1500000, "hard": 0.86,
		"hours": [5.0, 8.0, 17.5, 20.0], "desc": "SANGAT LANGKA! Ikan hias pembawa hoki. Kolektor kota rela bayar mahal."},
	"ikan_raja_sawit": {"name": "Ikan Raja Sawit Legendaris", "rar": "SSR", "water": ["river", "sea"], "w": 0.5, "price": 2500000, "hard": 0.92,
		"hours": [22.0, 24.0, 0.0, 3.0], "desc": "LEGENDA! Ikan bermahkota dengan sirip daun sawit. Konon jelmaan juragan serakah dari zaman dulu. Muncul tengah malam."},
}
## rarity tiers: display name, badge colour, sort order
const RARITY := {
	"N": {"name": "N", "long": "Normal", "col": "8a8a8a", "order": 0},
	"R": {"name": "R", "long": "Rare", "col": "3a74c0", "order": 1},
	"SR": {"name": "SR", "long": "Super Rare", "col": "8a4ac0", "order": 2},
	"SSR": {"name": "SSR", "long": "Super Super Rare", "col": "e0a820", "order": 3},
}
## Everything that can sit in the bag (Tas): name, icon, description. Fish come from FISH.
const ITEMS := {
	"tbs": {"name": "TBS (Tandan Buah Segar)", "icon": "icon_tbs", "desc": "Hasil panen sawit. Jual ke Pabrik di timur desa."},
	"bibit": {"name": "Bibit sawit", "icon": "icon_bibit", "desc": "Tanam di petak kosong lahanmu. Beli di Koperasi."},
	"pupuk": {"name": "Pupuk", "icon": "icon_pupuk", "desc": "Sawit tumbuh 1 hari lebih cepat, atau buah dobel saat panen."},
	"minyak": {"name": "Minyak goreng", "icon": "icon_minyak", "desc": "Jerigen hasil olahan pabrik. Jual ke warga atau ke warung."},
	"surat": {"name": "Surat tanah palsu", "icon": "icon_surat", "desc": "Dipakai untuk 'membeli' kebun warga yang kurang teliti."},
	"pancing": {"name": "Pancing bambu", "icon": "icon_pancing", "desc": "Hadap ke air (pantai, sungai, dermaga, jembatan) lalu tekan aksi: Mancing."},
}
const TOOLS := [
	{"name": "Parang", "icon": "icon_parang", "desc": "Untuk menebas semak di lahanmu."},
	{"name": "Egrek", "icon": "icon_egrek", "desc": "Galah bersabit untuk memanen tandan sawit."},
]
const OIL_PRICES := [25000, 55000, 95000]
const OIL_PRICE_NAMES := ["Normal", "Mahal", "Gila-gilaan"]
const CAPACITY := {"base": 10, "gerobak": 25, "truk": 80}
const STAGE_DAYS := [2, 2, 2]
const FRUIT_DAYS := 2
const ENERGY_COST := {"clear": 10.0, "plant": 5.0, "fert": 3.0, "harvest": 6.0, "fish": 4.0}
const MAX_WORKERS := 4
## lands to control before the franchise licence can be bought (map v3 has 20 parcels:
## the player chooses whose gardens to take)
const LICENSE_NEED := 7

const VILLAGERS := {
	"kakek": {"name": "Kakek Darman", "model": "char_kakek", "parcel": 1, "home": "rumah_kakek",
		"value": 4000000, "savings": 300000, "tawar": 0.7, "tipu": 0.85,
		"bio": "Petani tua yang lugu. Kebun pisangnya warisan almarhumah istri."},
	"ibu": {"name": "Bu Sari", "model": "char_ibu", "parcel": 2, "home": "rumah_ibu",
		"value": 5000000, "savings": 800000, "tawar": 0.35, "tipu": 0.4,
		"bio": "Ibu dua anak, jualan kue dan teliti soal surat-surat."},
	"kades": {"name": "Pak Kades Harun", "model": "char_kades", "parcel": 3, "home": "rumah_kades",
		"value": 8000000, "savings": 2500000, "tawar": 0.2, "tipu": 0.1, "sogok": true,
		"bio": "Kepala desa. Katanya anti korupsi, tapi amplopnya selalu tebal."},
	"nenek": {"name": "Nenek Ijah", "model": "char_nenek", "parcel": 4, "home": "rumah_nenek",
		"value": 3500000, "savings": 150000, "tawar": 0.45, "tipu": 0.9,
		"bio": "Nenek baik hati, tidak bisa membaca, suka memberi pisang goreng."},
	"pemuda": {"name": "Mas Joko", "model": "char_pemuda", "parcel": 5, "home": "rumah_pemuda",
		"value": 4500000, "savings": 400000, "tawar": 0.1, "tipu": 0.3, "aktivis": true,
		"bio": "Pemuda desa, aktivis lingkungan, rajin live di media sosial."},
	"petani": {"name": "Pak Tarno", "model": "char_petani", "parcel": 6, "home": "rumah_petani",
		"value": 5000000, "savings": 600000, "tawar": 0.45, "tipu": 0.55,
		"bio": "Petani ulet. Kebunnya penuh singkong dan cabai."},
	# ---- map v3: the hamlets (dusun) around Sukamakmur
	"somad": {"name": "Pak Haji Somad", "model": "char_kakek", "parcel": 7, "home": "rumah_somad",
		"value": 7500000, "savings": 3000000, "tawar": 0.15, "tipu": 0.25,
		"bio": "Juragan kopra di Dusun Seberang. Sudah naik haji dua kali, pelitnya tetap."},
	"ucok": {"name": "Bang Ucok", "model": "char_petani", "parcel": 8, "home": "rumah_ucok",
		"value": 4500000, "savings": 350000, "tawar": 0.55, "tipu": 0.5,
		"bio": "Sopir perahu tambang di sungai. Suka nyanyi keras-keras."},
	"rian": {"name": "Rian", "model": "char_pemuda", "parcel": 9, "home": "rumah_rian",
		"value": 4000000, "savings": 250000, "tawar": 0.2, "tipu": 0.35, "aktivis": true,
		"bio": "Konten kreator dusun. Semua hal jadi video, termasuk kamu."},
	"wati": {"name": "Mbak Wati", "model": "char_ibu", "parcel": 10, "home": "rumah_wati",
		"value": 4200000, "savings": 500000, "tawar": 0.4, "tipu": 0.45,
		"bio": "Penjual jamu gendong di Dusun Muara. Tahu semua gosip."},
	"slamet": {"name": "Pak Slamet", "model": "char_petani", "parcel": 11, "home": "rumah_slamet",
		"value": 5200000, "savings": 450000, "tawar": 0.5, "tipu": 0.6,
		"bio": "Petani karet yang sabar. Getah karetnya harga murah terus."},
	"dullah": {"name": "Kakek Dullah", "model": "char_kakek", "parcel": 12, "home": "rumah_dullah",
		"value": 6000000, "savings": 200000, "tawar": 0.1, "tipu": 0.2,
		"bio": "Tetua adat Dusun Barat. Hafal batas tanah ulayat sampai ke pohon-pohonnya."},
	"lastri": {"name": "Bu Lastri", "model": "char_ibu", "parcel": 13, "home": "rumah_lastri",
		"value": 4800000, "savings": 700000, "tawar": 0.3, "tipu": 0.2,
		"bio": "Guru SD. Membaca setiap surat sampai catatan kakinya."},
	"romlah": {"name": "Nenek Romlah", "model": "char_nenek", "parcel": 14, "home": "rumah_romlah",
		"value": 3200000, "savings": 120000, "tawar": 0.6, "tipu": 0.85,
		"bio": "Nenek penjual rempeyek. Matanya sudah rabun."},
	"darsih": {"name": "Mbok Darsih", "model": "char_nenek", "parcel": 15, "home": "rumah_darsih",
		"value": 3600000, "savings": 180000, "tawar": 0.5, "tipu": 0.75,
		"bio": "Dukun beranak Dusun Bukit. Percaya sawit bikin sumur kering."},
	"yanto": {"name": "Mas Yanto", "model": "char_buruh", "parcel": 16, "home": "rumah_yanto",
		"value": 3800000, "savings": 150000, "tawar": 0.65, "tipu": 0.5,
		"bio": "Mantan buruh pabrik yang di-PHK. Butuh uang cepat."},
	"karta": {"name": "Pak Karta", "model": "char_petani", "parcel": 19, "home": "rumah_karta",
		"value": 5000000, "savings": 600000, "tawar": 0.35, "tipu": 0.45,
		"bio": "Peternak kambing di Dusun Utara. Kambingnya suka makan bibit sawit."},
	"bidan": {"name": "Bu Bidan Rina", "model": "char_ibu", "parcel": 17, "home": "rumah_bidan",
		"value": 5500000, "savings": 1500000, "tawar": 0.2, "tipu": 0.15,
		"bio": "Bidan desa. Teliti, tegas, dan kenal semua orang sejak lahir."},
	"rt": {"name": "Pak RT Bejo", "model": "char_kades", "parcel": 18, "home": "rumah_rt",
		"value": 6500000, "savings": 1800000, "tawar": 0.3, "tipu": 0.2, "sogok": true,
		"bio": "Ketua RT Dusun Selatan. Stempelnya bisa disewa."},
}

const QUESTS := [
	{"text": "Panen 3 tandan (TBS) dari pohon sawit yang berbuah", "reward": 0},
	{"text": "Jual TBS ke Pabrik Kelapa Sawit di timur desa", "reward": 100000},
	{"text": "Tanam 4 bibit sawit di petak kosong lahanmu", "reward": 150000},
	{"text": "Tidur di kasur rumahmu (timur Kantor) untuk lanjut hari", "reward": 0},
	{"text": "Kuasai lahan warga pertama (beli, tawar, tipu... atau gusur)", "reward": 300000},
	{"text": "Bersihkan semak dan punya total 20 pohon sawit", "reward": 500000},
	{"text": "Beli Mesin Olah Minyak di Pabrik", "reward": 500000},
	{"text": "Jual 5 jerigen minyak goreng ke warga", "reward": 750000},
	{"text": "Kuasai 5 lahan (milik sendiri atau mitra franchise)", "reward": 1000000},
	{"text": "Kuasai 7 lahan & beli Lisensi Sawit The Franchise di Kantor", "reward": 0},
]

var money: int = 0
var day: int = 1
var hour: float = DAY_START
var energy: float = 100.0
var max_energy: float = 100.0
var rep: float = 0.0     # reputasi -100..100
var heat: float = 0.0    # kecurigaan 0..100
var inv := {}
var upgrades := {}
var oil_price_level: int = 1
var tbs_price: int = 150000
var tbs_trend: int = 0
var parcels: Array = []
var villagers := {}
var workers: Array = []          # entries: {"id": String, "wage": int, "vid": String}
var quest_index: int = 0
var stats := {}
## Koleksi Ikan: species id -> how many ever caught (new in the fish update; old saves
## start from the fish in the bag)
var fish_log := {}
var pending_events: Array = []
var game_active := false
## true when the last new day started from a bed (not passing out at midnight)
var last_slept := false
var rng := RandomNumberGenerator.new()


func _ready() -> void:
	rng.randomize()
	new_game()
	game_active = false
	if OS.has_feature("web"):
		# lets tools/web_test.js find buttons on the canvas by label
		add_child(preload("res://scripts/debug/web_probe.gd").new())


# ------------------------------------------------------------------ setup
func new_game() -> void:
	money = 2000000
	day = 1
	hour = DAY_START
	energy = 100.0
	max_energy = 100.0
	rep = 0.0
	heat = 0.0
	inv = {"bibit": 6, "pupuk": 3, "tbs": 0, "minyak": 0, "surat": 0, "pancing": 1}
	upgrades = {"gerobak": false, "truk": false, "mesin": false, "preman": 0, "lisensi": false}
	oil_price_level = 1
	tbs_price = 150000
	tbs_trend = 0
	workers = []
	quest_index = 0
	pending_events = []
	stats = {"harvested": 0, "tbs_sold": 0, "planted": 0, "cleared": 0, "earned": 0,
		"land_fair": 0, "land_cheap": 0, "land_fraud": 0, "land_seized": 0, "land_debt": 0,
		"oil_sold": 0, "oil_villager": 0, "sidak": 0, "franchise": 0, "bribes": 0,
		"fish_caught": 0, "fish_sold": 0}
	parcels = []
	fish_log = {}
	var layout: Dictionary = load_layout()
	var n := tile_count()
	for p in layout.get("parcels", []):
		var tiles: Array = []
		for i in n:
			tiles.append(_tile("bush"))
		parcels.append({"id": int(p["id"]), "name": p["name"], "owner": p["owner"], "plasma": false,
			"center": p["center"], "tiles": tiles})
	# starting plot: a few trees already bearing fruit so the first harvest happens on day one
	# (the north row: 3 ripe, then a palm that fruits tomorrow and two young ones; a few
	# thickets are left in the south row to clear)
	var start: Array = parcels[0]["tiles"]
	for i in n:
		start[i] = _tile("empty")
	for i in [0, 1, 2]:
		start[i] = _tile("palm", 3)
		start[i]["fr"] = true
	start[3] = _tile("palm", 3)
	start[3]["fd"] = 1
	start[4] = _tile("palm", 2)
	start[5] = _tile("palm", 1)
	for i in range(n - 3, n):
		start[i] = _tile("bush")
	villagers = {}
	for vid in VILLAGERS:
		var d: Dictionary = VILLAGERS[vid]
		villagers[vid] = {"trust": 50.0, "money": int(d["savings"]), "debt": 0, "status": "owner",
			"worker": false, "talk_day": 0, "oil_day": 0, "tent": -1, "evicted": false}
	game_active = true
	stats_changed.emit()
	quest_changed.emit()


func tile_count() -> int:
	## planting spots per parcel (layout: cols x rows)
	var l := load_layout()
	return int(l.get("parcel_cols", 4)) * int(l.get("parcel_rows", 3))


func _tile(state: String, stage: int = 0) -> Dictionary:
	return {"s": state, "st": stage, "g": 0, "f": false, "fr": false, "fd": 0}


var _layout_cache: Dictionary = {}


func load_layout() -> Dictionary:
	if _layout_cache.is_empty():
		var f := FileAccess.open("res://data/layout.json", FileAccess.READ)
		if f:
			_layout_cache = JSON.parse_string(f.get_as_text())
	return _layout_cache


# ------------------------------------------------------------------ helpers
static func fmt_rp(amount: int) -> String:
	var neg := amount < 0
	var s := str(absi(amount))
	var out := ""
	var count := 0
	for i in range(s.length() - 1, -1, -1):
		out = s[i] + out
		count += 1
		if count % 3 == 0 and i > 0:
			out = "." + out
	return ("-Rp " if neg else "Rp ") + out


static func fmt_short(amount: int) -> String:
	if absi(amount) >= 1000000:
		var v := amount / 1000000.0
		var t := ("%.1f" % v).replace(".0", "").replace(".", ",")
		return "Rp " + t + " jt"
	if absi(amount) >= 1000:
		return "Rp " + str(amount / 1000) + " rb"
	return "Rp " + str(amount)


func clock_text() -> String:
	var hh := int(hour) % 24
	var mm := int((hour - floor(hour)) * 60.0) / 10 * 10
	return "%02d:%02d" % [hh, mm]


func capacity() -> int:
	if upgrades.get("truk", false):
		return CAPACITY["truk"]
	if upgrades.get("gerobak", false):
		return CAPACITY["gerobak"]
	return CAPACITY["base"]


func add_money(amount: int, earned := true) -> void:
	money += amount
	if earned and amount > 0:
		stats["earned"] += amount
	stats_changed.emit()


func spend(amount: int) -> bool:
	if money < amount:
		toast.emit("Uangmu kurang! Butuh " + fmt_rp(amount), "bad")
		return false
	money -= amount
	stats_changed.emit()
	return true


func use_energy(amount: float) -> bool:
	if energy < amount:
		toast.emit("Kamu kecapekan. Makan di warung atau tidur dulu.", "bad")
		return false
	energy -= amount
	stats_changed.emit()
	return true


func add_rep(v: float) -> void:
	rep = clampf(rep + v, -100.0, 100.0)
	stats_changed.emit()


func add_heat(v: float) -> void:
	heat = clampf(heat + v, 0.0, 100.0)
	stats_changed.emit()


func add_item(item: String, n: int = 1) -> void:
	inv[item] = int(inv.get(item, 0)) + n
	stats_changed.emit()


func take_item(item: String, n: int = 1) -> bool:
	if int(inv.get(item, 0)) < n:
		return false
	inv[item] = int(inv[item]) - n
	stats_changed.emit()
	return true


func stage_need(stage: int, fert: bool) -> int:
	return maxi(1, STAGE_DAYS[stage] - (1 if fert else 0))


func owned_parcels() -> int:
	var n := 0
	for p in parcels:
		if p["owner"] == "player":
			n += 1
	return n


func controlled_parcels() -> int:
	var n := 0
	for p in parcels:
		if p["owner"] == "player" or p["plasma"]:
			n += 1
	return n


func palm_count() -> int:
	var n := 0
	for p in parcels:
		if p["owner"] == "player":
			for t in p["tiles"]:
				if t["s"] == "palm":
					n += 1
	return n


func parcel_of(vid: String) -> Dictionary:
	var pid := int(VILLAGERS[vid]["parcel"])
	return parcels[pid]


func vname(vid: String) -> String:
	return VILLAGERS[vid]["name"]


# ------------------------------------------------------------------ farming actions
func tile_action_info(pid: int, idx: int) -> Dictionary:
	## What the context action would do on this tile: {"verb": String, "ok": bool}
	var p: Dictionary = parcels[pid]
	var t: Dictionary = p["tiles"][idx]
	if p["owner"] != "player":
		if p["plasma"]:
			return {"verb": "Kebun mitra franchise " + vname(p["owner"]), "ok": false}
		return {"verb": p["name"] + " (bukan milikmu)", "ok": false}
	match t["s"]:
		"bush":
			return {"verb": "Tebas semak", "ok": true, "kind": "clear"}
		"empty":
			if int(inv["bibit"]) > 0:
				return {"verb": "Tanam bibit sawit", "ok": true, "kind": "plant"}
			return {"verb": "Butuh bibit (beli di Koperasi)", "ok": false}
		"palm":
			if t["fr"]:
				return {"verb": "Panen TBS", "ok": true, "kind": "harvest"}
			if not t["f"] and int(inv["pupuk"]) > 0:
				return {"verb": "Beri pupuk", "ok": true, "kind": "fert"}
			var stage_names := ["Bibit", "Sawit muda", "Sawit remaja", "Sawit dewasa"]
			var txt: String = stage_names[t["st"]]
			if t["st"] < 3:
				var left: int = stage_need(t["st"], t["f"]) - int(t["g"])
				txt += " (tumbuh %d hari lagi)" % left
			else:
				txt += " (berbuah %d hari lagi)" % maxi(1, FRUIT_DAYS - (1 if t["f"] else 0) - int(t["fd"]))
			if t["f"]:
				txt += " • sudah dipupuk"
			return {"verb": txt, "ok": false}
	return {"verb": "", "ok": false}


func do_tile_action(pid: int, idx: int) -> String:
	## Performs the action; returns the kind done ("" if nothing happened).
	var info := tile_action_info(pid, idx)
	if not info["ok"]:
		return ""
	var t: Dictionary = parcels[pid]["tiles"][idx]
	var kind: String = info["kind"]
	match kind:
		"clear":
			if not use_energy(ENERGY_COST["clear"]):
				return ""
			t["s"] = "empty"
			stats["cleared"] += 1
		"plant":
			if not use_energy(ENERGY_COST["plant"]):
				return ""
			take_item("bibit")
			parcels[pid]["tiles"][idx] = _tile("palm", 0)
			stats["planted"] += 1
		"fert":
			if not use_energy(ENERGY_COST["fert"]):
				return ""
			take_item("pupuk")
			t["f"] = true
		"harvest":
			var gain := 2 if t["f"] else 1
			if int(inv["tbs"]) + gain > capacity():
				toast.emit("Bawaan penuh (%d/%d TBS). Jual dulu ke Pabrik!" % [inv["tbs"], capacity()], "bad")
				return ""
			if not use_energy(ENERGY_COST["harvest"]):
				return ""
			t["fr"] = false
			t["fd"] = 0
			t["f"] = false
			add_item("tbs", gain)
			stats["harvested"] += gain
	parcel_changed.emit(pid)
	check_quests()
	stats_changed.emit()
	return kind


# ------------------------------------------------------------------ time
func advance(delta: float) -> void:
	if not game_active:
		return
	hour += delta * HOURS_PER_SECOND
	if hour >= DAY_END:
		toast.emit("Sudah tengah malam! Kamu pingsan dan diantar ojek pulang (-Rp 100.000).", "bad")
		money = maxi(0, money - 100000)
		start_new_day(false)
	stats_changed.emit()


func start_new_day(slept: bool) -> void:
	var report: Array = []
	# --- suspicion catches up with you overnight
	if heat >= 100.0:
		stats["sidak"] += 1
		var fine := maxi(2000000, int(money * 0.3))
		if stats["sidak"] >= 3 or money < fine:
			game_active = false
			var why := "Satgas Sawit menggerebek kantormu untuk ketiga kalinya." if stats["sidak"] >= 3 \
				else "Satgas Sawit menggerebek kantormu dan kamu tak sanggup bayar denda."
			game_over.emit(why)
			return
		money -= fine
		heat = 45.0
		report.append("[SIDAK] Satgas menyita " + fmt_rp(fine) + " sebagai denda. (Sidak ke-%d dari 3)" % stats["sidak"])
	last_slept = slept
	day += 1
	hour = DAY_START
	energy = max_energy if slept else max_energy * 0.6
	# --- palms grow
	for p in parcels:
		if p["owner"] != "player" and not p["plasma"]:
			continue
		for t in p["tiles"]:
			if t["s"] != "palm":
				continue
			if t["st"] < 3:
				t["g"] += 1
				if t["g"] >= stage_need(t["st"], t["f"]):
					t["st"] += 1
					t["g"] = 0
					t["f"] = false
			elif not t["fr"]:
				t["fd"] += 1
				if t["fd"] >= maxi(1, FRUIT_DAYS - (1 if t["f"] else 0)):
					t["fr"] = true
					t["fd"] = 0
	# --- TBS market price random walk
	var old := tbs_price
	tbs_price = clampi(tbs_price + rng.randi_range(-3, 3) * 10000 + tbs_trend * 5000, 90000, 230000)
	tbs_trend = rng.randi_range(-1, 1)
	report.append("Harga TBS hari ini: %s/tandan (%s)" % [fmt_rp(tbs_price), "naik" if tbs_price > old else ("turun" if tbs_price < old else "stabil")])
	# --- workers
	_pay_and_run_workers(report)
	# --- franchise (plasma) partners
	_run_plasma(report)
	# --- slow drift
	heat = clampf(heat - 6.0, 0.0, 100.0)
	rep = rep * 0.97
	for vid in villagers:
		var v: Dictionary = villagers[vid]
		v["trust"] = lerpf(v["trust"], 50.0 + rep * 0.3, 0.1)
		if v["debt"] > 0:
			v["debt"] = int(v["debt"] * 1.05)  # "bunga ringan"
		if v["status"] == "landless":
			v["money"] = maxi(0, v["money"] - 10000)
	# --- random morning events
	pending_events.clear()
	if rep <= -35.0 and rng.randf() < 0.5:
		pending_events.append("demo")
	elif heat >= 60.0 and rng.randf() < 0.45:
		pending_events.append("wartawan")
	elif rng.randf() < 0.18:
		pending_events.append("harga_naik" if rng.randf() < 0.5 else "hujan")
	for p in parcels:
		parcel_changed.emit(p["id"])
	check_quests()
	stats_changed.emit()
	save_game()
	day_started.emit(report)


func _pay_and_run_workers(report: Array) -> void:
	if workers.is_empty():
		return
	var kept: Array = []
	for w in workers:
		if money >= int(w["wage"]):
			money -= int(w["wage"])
			kept.append(w)
		else:
			report.append("%s berhenti kerja karena upahnya tidak dibayar." % w["name"])
			if w["vid"] != "":
				villagers[w["vid"]]["worker"] = false
	workers = kept
	var harvested := 0
	var cleared := 0
	var budget := 0
	var clear_budget := 0
	for w in workers:
		budget += 8
		clear_budget += 2
	for p in parcels:
		if p["owner"] != "player":
			continue
		for t in p["tiles"]:
			if budget > 0 and t["s"] == "palm" and t["fr"]:
				t["fr"] = false
				t["fd"] = 0
				harvested += 2 if t["f"] else 1
				t["f"] = false
				budget -= 1
			elif clear_budget > 0 and t["s"] == "bush":
				t["s"] = "empty"
				cleared += 1
				clear_budget -= 1
	if harvested > 0:
		var income := harvested * tbs_price
		money += income
		stats["earned"] += income
		stats["harvested"] += harvested
		stats["tbs_sold"] += harvested
		report.append("Buruh memanen %d TBS dan menjualnya: +%s" % [harvested, fmt_rp(income)])
	if cleared > 0:
		report.append("Buruh menebas %d petak semak." % cleared)
	report.append("Upah %d buruh dibayar." % workers.size())


func _run_plasma(report: Array) -> void:
	for p in parcels:
		if not p["plasma"] or p["owner"] == "player":
			continue
		var vid: String = p["owner"]
		var v: Dictionary = villagers[vid]
		var n := 0
		for t in p["tiles"]:
			if t["s"] == "palm" and t["fr"]:
				t["fr"] = false
				t["fd"] = 0
				n += 1
		if n > 0:
			var total := n * tbs_price
			var cut := int(total * 0.6)
			var share := total - cut
			money += cut
			stats["earned"] += cut
			var pay := mini(share, int(v["debt"]))
			v["debt"] -= pay
			money += pay
			v["money"] += share - pay
			report.append("Setoran franchise %s: %d TBS, bagianmu %s%s" % [vname(vid), n, fmt_rp(cut),
				(" + cicilan utang " + fmt_rp(pay)) if pay > 0 else ""])
		if v["debt"] > 0:
			report.append("Utang %s sekarang %s (bunga 5%%/hari)." % [vname(vid), fmt_rp(v["debt"])])


func sleep() -> void:
	start_new_day(true)


# ------------------------------------------------------------------ fishing / bag
func item_info(key: String) -> Dictionary:
	## {"name", "icon", "desc", "price"} for a bag item ({} if unknown)
	if FISH.has(key):
		var f: Dictionary = FISH[key]
		return {"name": f["name"], "icon": key, "desc": f["desc"], "price": int(f["price"]), "fish": true, "rar": str(f.get("rar", "N"))}
	return ITEMS.get(key, {})


func fish_available(water: String, h: float) -> Array:
	## fish ids that can bite in this water at hour h
	var out: Array = []
	for id in FISH:
		var f: Dictionary = FISH[id]
		if not water in f["water"]:
			continue
		var hs: Array = f.get("hours", [])
		if not hs.is_empty():
			var ok := false
			for i in range(0, hs.size(), 2):
				if h >= float(hs[i]) and h < float(hs[i + 1]):
					ok = true
			if not ok:
				continue
		out.append(id)
	return out


func roll_fish(water: String, h: float) -> String:
	var pool := fish_available(water, h)
	if pool.is_empty():
		return "ikan_nila"
	var total := 0.0
	for id in pool:
		total += float(FISH[id]["w"])
	var r := rng.randf() * total
	for id in pool:
		r -= float(FISH[id]["w"])
		if r <= 0.0:
			return id
	return pool[-1]


func catch_fish(id: String) -> void:
	add_item(id, 1)
	fish_log[id] = int(fish_log.get(id, 0)) + 1
	stats["fish_caught"] = int(stats.get("fish_caught", 0)) + 1


func fish_rarity(id: String) -> String:
	return str(FISH.get(id, {}).get("rar", "N"))


func fish_caught_species() -> int:
	var n := 0
	for id in FISH:
		if int(fish_log.get(id, 0)) > 0:
			n += 1
	return n


func fish_ids_sorted() -> Array:
	## collection order: by rarity, then by the FISH order
	var ids: Array = FISH.keys()
	var idx := {}
	for i in ids.size():
		idx[ids[i]] = i
	ids.sort_custom(func(a, b):
		var ra: int = RARITY[fish_rarity(a)]["order"]
		var rb: int = RARITY[fish_rarity(b)]["order"]
		return ra < rb if ra != rb else idx[a] < idx[b])
	return ids


func fish_count() -> int:
	var n := 0
	for id in FISH:
		n += int(inv.get(id, 0))
	return n


func fish_value() -> int:
	var v := 0
	for id in FISH:
		v += int(inv.get(id, 0)) * int(FISH[id]["price"])
	return v


func sell_all_fish() -> int:
	## sells every fish in the bag; returns the money earned
	var total := fish_value()
	var n := fish_count()
	if n <= 0:
		return 0
	for id in FISH:
		inv.erase(id)
	stats["fish_sold"] = int(stats.get("fish_sold", 0)) + n
	add_money(total)
	return total


# ------------------------------------------------------------------ quests
func check_quests() -> void:
	var changed := false
	while quest_index < QUESTS.size() and _quest_done(quest_index):
		var r: int = QUESTS[quest_index]["reward"]
		if r > 0:
			money += r
		toast.emit("Misi selesai: " + QUESTS[quest_index]["text"] + ((" (+" + fmt_rp(r) + ")") if r > 0 else ""), "quest")
		quest_index += 1
		changed = true
	if changed:
		quest_changed.emit()
		stats_changed.emit()


func _quest_done(i: int) -> bool:
	match i:
		0: return stats["harvested"] >= 3
		1: return stats["tbs_sold"] >= 1
		2: return stats["planted"] >= 4
		3: return day >= 2
		4: return controlled_parcels() >= 2
		5: return palm_count() >= 20
		6: return upgrades["mesin"]
		7: return stats["oil_villager"] >= 5
		8: return controlled_parcels() >= 5
		9: return upgrades["lisensi"]
	return false


func current_quest() -> String:
	if quest_index >= QUESTS.size():
		return "Kamu sudah jadi Raja Sawit!"
	return QUESTS[quest_index]["text"]


# ------------------------------------------------------------------ save / load
func has_save() -> bool:
	## only a save this version can load counts ("Lanjutkan" stays hidden for old ones)
	if not FileAccess.file_exists(SAVE_PATH):
		return false
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return false
	var data = JSON.parse_string(f.get_as_text())
	return typeof(data) == TYPE_DICTIONARY and int(data.get("v", 0)) == SAVE_VERSION


func save_game() -> void:
	var data := {
		"v": SAVE_VERSION, "money": money, "day": day, "hour": hour, "energy": energy, "rep": rep, "heat": heat,
		"inv": inv, "upgrades": upgrades, "oil": oil_price_level, "tbs_price": tbs_price, "parcels": parcels,
		"villagers": villagers, "workers": workers, "quest": quest_index, "stats": stats,
		"fish_log": fish_log,
	}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data))
		f.close()


func load_game() -> bool:
	if not has_save():
		return false
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return false
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY or int(data.get("v", 0)) != SAVE_VERSION:
		return false
	new_game()
	money = int(data["money"])
	day = int(data["day"])
	hour = float(data["hour"])
	energy = float(data["energy"])
	rep = float(data["rep"])
	heat = float(data["heat"])
	for k in data["inv"]:
		inv[k] = int(data["inv"][k])
	for k in data["upgrades"]:
		upgrades[k] = data["upgrades"][k]
	upgrades["preman"] = int(upgrades["preman"])
	oil_price_level = int(data["oil"])
	tbs_price = int(data["tbs_price"])
	parcels = data["parcels"]
	for p in parcels:
		p["id"] = int(p["id"])
		for t in p["tiles"]:
			t["st"] = int(t["st"])
			t["g"] = int(t["g"])
			t["fd"] = int(t["fd"])
	villagers = data["villagers"]
	for vid in villagers:
		var v: Dictionary = villagers[vid]
		v["money"] = int(v["money"])
		v["debt"] = int(v["debt"])
		v["talk_day"] = int(v["talk_day"])
		v["oil_day"] = int(v["oil_day"])
		v["tent"] = int(v["tent"])
	workers = data["workers"]
	for w in workers:
		w["wage"] = int(w["wage"])
	quest_index = int(data["quest"])
	for k in data["stats"]:
		stats[k] = int(data["stats"][k])
	var fl = data.get("fish_log", {})
	if typeof(fl) == TYPE_DICTIONARY:
		for k in fl:
			if FISH.has(k):
				fish_log[k] = int(fl[k])
	for k in FISH:   # saves from before the collection: count the fish in the bag
		if int(inv.get(k, 0)) > 0 and not fish_log.has(k):
			fish_log[k] = int(inv[k])
	game_active = true
	stats_changed.emit()
	quest_changed.emit()
	return true


func delete_save() -> void:
	if has_save():
		DirAccess.remove_absolute(SAVE_PATH)
