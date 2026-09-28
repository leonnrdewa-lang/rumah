class_name Boons
extends RefCounted
## The gods' blessings (anugerah). Each boon belongs to one god and one slot
## (serang / jurus / ajian / lesat / pasif); a slot holds one boon at a time.
## Values scale with rarity and with level (Pusaka Palu).

const RARITY := ["Biasa", "Langka", "Agung", "Wahyu"]
const RARITY_COLOR := [Color("e8e0d0"), Color("5aa0ff"), Color("c07cff"), Color("ffb040")]
const RARITY_MULT := [1.0, 1.5, 2.0, 2.6]
const SLOT_NAME := {"serang": "Serang", "jurus": "Jurus", "ajian": "Ajian", "lesat": "Lesat", "pasif": "Pasif"}

const ALL := {
	# --- Batara Bayu: wind — knockback, pull, gusts
	"bayu_serang": {"god": "bayu", "slot": "serang", "name": "Serang Prahara",
		"desc": "Serangan gada +{v}% kerusakan dan mendorong musuh jauh.", "base": 40},
	"bayu_jurus": {"god": "bayu", "slot": "jurus", "name": "Jurus Lesus",
		"desc": "Bilah angin menembus semua musuh, +{v}% kerusakan.", "base": 40},
	"bayu_ajian": {"god": "bayu", "slot": "ajian", "name": "Ajian Pusaran",
		"desc": "Lingkaran Ajian menyedot musuh ke tengah dan melukai {v}/detik.", "base": 8},
	"bayu_lesat": {"god": "bayu", "slot": "lesat", "name": "Lesat Angin Ribut",
		"desc": "Lesat melepas hembusan yang melukai {v} dan melempar musuh.", "base": 18},
	"bayu_pasif": {"god": "bayu", "slot": "pasif", "name": "Napas Bayu",
		"desc": "Gerak +{v}% lebih cepat.", "base": 12},
	# --- Batara Surya: fire — burn and blasts
	"surya_serang": {"god": "surya", "slot": "serang", "name": "Serang Surya",
		"desc": "Serangan membakar musuh: {v} kerusakan/detik selama 4 detik.", "base": 5},
	"surya_jurus": {"god": "surya", "slot": "jurus", "name": "Jurus Baskara",
		"desc": "Bilah angin meledak saat kena: {v} kerusakan di sekitarnya.", "base": 22},
	"surya_ajian": {"god": "surya", "slot": "ajian", "name": "Ajian Geni Suci",
		"desc": "Musuh di lingkaran Ajian terbakar {v}/detik.", "base": 10},
	"surya_lesat": {"god": "surya", "slot": "lesat", "name": "Lesat Bara",
		"desc": "Lesat meninggalkan jejak api yang membakar {v}/detik.", "base": 6},
	"surya_pasif": {"god": "surya", "slot": "pasif", "name": "Sinar Fajar",
		"desc": "Musuh yang terbakar menerima +{v}% kerusakan.", "base": 20},
	# --- Batara Baruna: sea — wet (slow), waves
	"baruna_serang": {"god": "baruna", "slot": "serang", "name": "Serang Samudra",
		"desc": "Serangan +{v}% kerusakan dan membuat musuh Basah (lambat 30%).", "base": 25},
	"baruna_jurus": {"god": "baruna", "slot": "jurus", "name": "Jurus Ombak",
		"desc": "Jurus menjadi ombak lebar {v} kerusakan yang membuat Basah.", "base": 22},
	"baruna_ajian": {"god": "baruna", "slot": "ajian", "name": "Ajian Banjir Bandang",
		"desc": "Saat lingkaran Ajian terbentuk, gelombang pasang melukai {v}.", "base": 30},
	"baruna_lesat": {"god": "baruna", "slot": "lesat", "name": "Lesat Riak",
		"desc": "Lesat memercikkan air: {v} kerusakan dan Basah di sekitar.", "base": 12},
	"baruna_pasif": {"god": "baruna", "slot": "pasif", "name": "Tirta Kamandanu",
		"desc": "+{v} nyawa maksimum, langsung dipulihkan.", "base": 15},
	# --- Batara Indra: thunder — chains and strikes
	"indra_serang": {"god": "indra", "slot": "serang", "name": "Serang Bajra",
		"desc": "Serangan memercikkan petir berantai ke 2 musuh lain: {v} kerusakan.", "base": 7},
	"indra_jurus": {"god": "indra", "slot": "jurus", "name": "Jurus Guntur",
		"desc": "Bilah angin memanggil sambaran petir di sasaran: {v} kerusakan.", "base": 26},
	"indra_ajian": {"god": "indra", "slot": "ajian", "name": "Ajian Gelap Ngampar",
		"desc": "Petir menyambar musuh di lingkaran Ajian tiap 0,5 detik: {v}.", "base": 9},
	"indra_lesat": {"god": "indra", "slot": "lesat", "name": "Lesat Kilat",
		"desc": "Lesat menyambar musuh terdekat dengan petir: {v} kerusakan.", "base": 20},
	"indra_pasif": {"god": "indra", "slot": "pasif", "name": "Mata Wajra",
		"desc": "{v}% peluang serangan kritis (3x kerusakan).", "base": 8},
}

const LINES := {
	"bayu": ["Anakku, angin selalu berpihak padamu. Terbanglah!", "Hembusanku menyertai langkahmu, Anjaniputra.",
		"Alengka jauh, tapi angin lebih cepat dari segala raksasa."],
	"surya": ["Terangku akan membakar kegelapan Rahwana.", "Jangan biarkan bara di dadamu padam, Hanoman.",
		"Setiap fajar adalah janji. Pakailah apiku."],
	"baruna": ["Laut yang memisahkanmu dari Alengka adalah wilayahku. Hati-hati dengan Sura dan Baya.",
		"Air itu sabar, tapi bisa meruntuhkan gunung.", "Samudra akan membuka jalan bagi utusan yang jujur."],
	"indra": ["Kahyangan menyaksikanmu, kera putih. Buat kami bangga.", "Petirku untuk mereka yang berani.",
		"Rahwana pernah mempermalukan kahyangan. Balaskan untuk kami."],
}


static func god_of(id: String) -> String:
	return ALL[id].god


static func owned(id: String) -> bool:
	return G.run.get("boons", {}).has(id)


static func val(id: String) -> float:
	var b = G.run.get("boons", {}).get(id)
	if b == null:
		return 0.0
	var lvl: int = b.lvl
	return ALL[id].base * RARITY_MULT[b.rar] * (1.0 + 0.5 * (lvl - 1))


static func val_for(id: String, rar: int, lvl := 1) -> float:
	return ALL[id].base * RARITY_MULT[rar] * (1.0 + 0.5 * (lvl - 1))


static func desc(id: String, rar: int, lvl := 1) -> String:
	var v := val_for(id, rar, lvl)
	return String(ALL[id].desc).replace("{v}", str(int(round(v))))


static func slot_holder(slot: String) -> String:
	return G.run.get("slots", {}).get(slot, "")


static func roll_rarity(bonus := 0.0) -> int:
	var r := randf()
	if r < 0.04 + bonus * 0.5:
		return 3
	if r < 0.14 + bonus:
		return 2
	if r < 0.42 + bonus:
		return 1
	return 0


## Three offers from one god, skipping boons already owned.
static func offers(god: String) -> Array:
	var pool := []
	for id in ALL:
		if ALL[id].god == god and not owned(id):
			pool.append(id)
	pool.shuffle()
	# prefer filling empty slots early
	pool.sort_custom(func(a, b): return int(slot_holder(ALL[a].slot) == "") > int(slot_holder(ALL[b].slot) == ""))
	var out := []
	for i in min(3, pool.size()):
		out.append({"id": pool[i], "rar": roll_rarity()})
	return out


static func take(id: String, rar: int) -> void:
	var slot: String = ALL[id].slot
	var old := slot_holder(slot)
	if slot != "pasif" and old != "":
		G.run.boons.erase(old)
	if slot != "pasif":
		G.run.slots[slot] = id
	else:
		# passives stack in their own list
		pass
	G.run.boons[id] = {"lvl": 1, "rar": rar}
	var god: String = ALL[id].god
	if not G.run.gods_met.has(god):
		G.run.gods_met.append(god)
	if id == "baruna_pasif":
		var v := val(id)
		G.run.max_hp = float(G.run.max_hp) + v
		G.heal(v)
	G.run_changed.emit()


static func level_up(id: String) -> void:
	if not owned(id):
		return
	var before := val(id)
	G.run.boons[id].lvl = int(G.run.boons[id].lvl) + 1
	if id == "baruna_pasif":
		var gain := val(id) - before
		G.run.max_hp = float(G.run.max_hp) + gain
		G.heal(gain)
	G.run_changed.emit()


static func random_god(exclude := "") -> String:
	var gods := ["bayu", "surya", "baruna", "indra"]
	gods.erase(exclude)
	return gods[randi() % gods.size()]
