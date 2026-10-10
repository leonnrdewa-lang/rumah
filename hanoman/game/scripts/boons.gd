class_name Boons
extends RefCounted
## The gods' blessings (anugerah). Each boon belongs to one god and one slot
## (serang / jurus / ajian / lesat / pasif); a slot holds one boon at a time.
## Values scale with rarity and with level (Pusaka Palu).

const RARITY := ["Common", "Rare", "Epic", "Heroic"]
const RARITY_COLOR := [Color("e8e0d0"), Color("5aa0ff"), Color("c07cff"), Color("ffb040")]
const RARITY_MULT := [1.0, 1.5, 2.0, 2.6]
const SLOT_NAME := {"serang": "Attack", "jurus": "Special", "ajian": "Spell", "lesat": "Dash", "pasif": "Passive"}

const ALL := {
	# --- Batara Bayu: wind — knockback, pull, gusts
	"bayu_serang": {"god": "bayu", "slot": "serang", "name": "Tempest Strike",
		"desc": "Staff swings deal +{v}% damage and knock foes far back.", "base": 40},
	"bayu_jurus": {"god": "bayu", "slot": "jurus", "name": "Whirlwind Special",
		"desc": "Extending Staff deals +{v}% damage and hurls foes away.", "base": 40},
	"bayu_ajian": {"god": "bayu", "slot": "ajian", "name": "Vortex Spell",
		"desc": "Spell circle pulls foes to its center and deals {v}/sec.", "base": 8},
	"bayu_lesat": {"god": "bayu", "slot": "lesat", "name": "Gale Dash",
		"desc": "Dash unleashes a gust that deals {v} and flings foes.", "base": 18},
	"bayu_pasif": {"god": "bayu", "slot": "pasif", "name": "Breath of Bayu",
		"desc": "Move {v}% faster.", "base": 12},
	# --- Batara Surya: fire — burn and blasts
	"surya_serang": {"god": "surya", "slot": "serang", "name": "Solar Strike",
		"desc": "Attacks burn foes: {v} damage/sec for 4 seconds.", "base": 5},
	"surya_jurus": {"god": "surya", "slot": "jurus", "name": "Blazing Special",
		"desc": "Each foe pierced by the Extending Staff explodes: {v} damage nearby.", "base": 22},
	"surya_ajian": {"god": "surya", "slot": "ajian", "name": "Sacred Fire Spell",
		"desc": "Foes in the Spell circle burn for {v}/sec.", "base": 10},
	"surya_lesat": {"god": "surya", "slot": "lesat", "name": "Ember Dash",
		"desc": "Dash leaves a trail of fire that burns for {v}/sec.", "base": 6},
	"surya_pasif": {"god": "surya", "slot": "pasif", "name": "Dawnlight",
		"desc": "Burning foes take +{v}% damage.", "base": 20},
	# --- Batara Baruna: sea — wet (slow), waves
	"baruna_serang": {"god": "baruna", "slot": "serang", "name": "Ocean Strike",
		"desc": "Attacks deal +{v}% damage and make foes Soaked (30% slow).", "base": 25},
	"baruna_jurus": {"god": "baruna", "slot": "jurus", "name": "Breaker Special",
		"desc": "Extending Staff becomes a wide torrent: {v} damage and Soaked.", "base": 22},
	"baruna_ajian": {"god": "baruna", "slot": "ajian", "name": "Flash Flood Spell",
		"desc": "When the Spell circle forms, a tidal surge deals {v}.", "base": 30},
	"baruna_lesat": {"god": "baruna", "slot": "lesat", "name": "Ripple Dash",
		"desc": "Dash splashes water: {v} damage and Soaked nearby.", "base": 12},
	"baruna_pasif": {"god": "baruna", "slot": "pasif", "name": "Tirta Kamandanu",
		"desc": "+{v} max health, restored at once.", "base": 15},
	# --- Batara Indra: thunder — chains and strikes
	"indra_serang": {"god": "indra", "slot": "serang", "name": "Thunderbolt Strike",
		"desc": "Attacks arc chain lightning to 2 more foes: {v} damage.", "base": 7},
	"indra_jurus": {"god": "indra", "slot": "jurus", "name": "Thunder Special",
		"desc": "Extending Staff calls a lightning bolt on each target: {v} damage.", "base": 26},
	"indra_ajian": {"god": "indra", "slot": "ajian", "name": "Rolling Thunder Spell",
		"desc": "Lightning strikes foes in the Spell circle every 0.5 sec: {v}.", "base": 9},
	"indra_lesat": {"god": "indra", "slot": "lesat", "name": "Flash Dash",
		"desc": "Dash strikes the nearest foe with lightning: {v} damage.", "base": 20},
	"indra_pasif": {"god": "indra", "slot": "pasif", "name": "Eye of Wajra",
		"desc": "{v}% critical hit chance (3x damage).", "base": 8},
	# --- Duo: two gods together, offered once you carry both
	"duo_badai": {"god": "bayu", "gods": ["bayu", "indra"], "slot": "pasif", "name": "Duo: Rolling Storm",
		"desc": "Your third blow calls lightning on the 3 nearest foes: {v} damage.", "base": 16},
	"duo_uap": {"god": "surya", "gods": ["surya", "baruna"], "slot": "pasif", "name": "Duo: Crater Steam",
		"desc": "Foes both Soaked and Burning take +{v}% damage.", "base": 45},
	"duo_topan": {"god": "bayu", "gods": ["bayu", "surya"], "slot": "pasif", "name": "Duo: Fire Typhoon",
		"desc": "Extending Staff leaves a path of fire that burns for {v}/sec.", "base": 7},
	"duo_gelombang": {"god": "baruna", "gods": ["baruna", "indra"], "slot": "pasif", "name": "Duo: Thunder Tide",
		"desc": "Hitting Soaked foes arcs lightning to others: {v} damage.", "base": 10},
	"duo_fajar": {"god": "surya", "gods": ["surya", "indra"], "slot": "pasif", "name": "Duo: Thunder Dawn",
		"desc": "Critical hits set off a {v} fire blast around the target.", "base": 20},
	"duo_samudra": {"god": "baruna", "gods": ["baruna", "bayu"], "slot": "pasif", "name": "Duo: Ocean Tempest",
		"desc": "Dash sweeps nearby foes: Soaked and {v} damage.", "base": 14},
}

const LINES := {
	"bayu": ["My son, the wind is always on your side. Fly!", "My breath goes with your every step, son of Anjani.",
		"Alengka is far, but the wind outruns every demon."],
	"surya": ["My light shall burn away Rahwana's darkness.", "Never let the ember in your chest go out, Hanoman.",
		"Every dawn is a promise. Take my fire."],
	"baruna": ["The sea between you and Alengka is my domain. Beware Sura and Baya.",
		"Water is patient, yet it can bring down mountains.", "The ocean will part for an honest envoy."],
	"indra": ["Heaven is watching you, white ape. Make us proud.", "My thunder is for the brave.",
		"Rahwana once shamed the heavens. Avenge us."],
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
		if ALL[id].god == god and not owned(id) and not ALL[id].has("gods"):
			pool.append(id)
	pool.shuffle()
	# prefer filling empty slots early
	pool.sort_custom(func(a, b): return int(slot_holder(ALL[a].slot) == "") > int(slot_holder(ALL[b].slot) == ""))
	var out := []
	for i in min(3, pool.size()):
		out.append({"id": pool[i], "rar": roll_rarity()})
	# a Duo blessing appears when you already carry the partner god's gift
	var duos := []
	for id in ALL:
		if ALL[id].has("gods") and not owned(id) and god in ALL[id].gods:
			for g in ALL[id].gods:
				if g != god and _has_god(g):
					duos.append(id)
	if not duos.is_empty() and randf() < 0.5:
		var d: String = duos[randi() % duos.size()]
		var entry := {"id": d, "rar": max(1, roll_rarity())}
		if out.size() >= 3:
			out[2] = entry
		else:
			out.append(entry)
	return out


static func _has_god(g: String) -> bool:
	for id in G.run.get("boons", {}):
		if ALL[id].god == g and not ALL[id].has("gods"):
			return true
	return false


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
