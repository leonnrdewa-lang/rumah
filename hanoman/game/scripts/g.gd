extends Node
## Global state: permanent progress (saved), the current run, input map setup
## and a few shared helpers. Autoloaded as `G`.

signal run_changed
signal meta_changed
signal settings_changed
signal toast(text: String, color: Color)

const SAVE_PATH := "user://hanoman_save.json"

const GOD_COLORS := {
	"bayu": Color("5fe0c8"), "surya": Color("f2b845"),
	"baruna": Color("4aa3ff"), "indra": Color("b784ff"),
}
const GOD_NAMES := {
	"bayu": "Batara Bayu", "surya": "Batara Surya",
	"baruna": "Batara Baruna", "indra": "Batara Indra",
}
const GOD_TITLES := {
	"bayu": "God of Wind", "surya": "God of the Sun",
	"baruna": "God of the Sea", "indra": "King of Heaven, God of Thunder",
}

## Jembawan's permanent upgrades ("Kesaktian"): id -> [name, desc, cost per rank, max rank]
const UPGRADES := {
	"otot": ["Wire Sinews", "+10 max health per rank.", [2, 4, 6], 3],
	"tulang": ["Iron Bones", "Survive one fatal blow per journey (revive at 50% health).", [6], 1],
	"lesat": ["Stride of Bayu", "+1 Dash charge.", [5], 1],
	"gada": ["Jeweled Staff", "+15% Attack damage per rank.", [3, 5], 2],
	"prana": ["True Prana", "+1 Special charge.", [4], 1],
	"rejeki": ["Kepeng Fortune", "Begin each journey with 60 Kepeng per rank.", [2, 3], 2],
}

var meta := {
	"bunga": 0, "runs": 0, "wins": 0, "deaths": 0, "best_room": 0,
	"upgrades": {}, "seen": {}, "boss_kills": 0,
	"settings": {},
}
const SETTING_DEFAULTS := {"music": 0.8, "sfx": 1.0, "vibrate": true, "quality": "high"}
var run := {}
var in_run := false
var touch_mode := false
var paused_by_menu := false
var main: Node = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_input()
	load_meta()
	if DisplayServer.is_touchscreen_available() and _is_mobile_web():
		enable_touch()


## Touch play: taps are emulated as mouse clicks for the menus, so the mouse
## buttons must stop triggering Serang / Jurus (the on-screen buttons do that).
func enable_touch() -> void:
	touch_mode = true
	for a in ["attack", "special"]:
		for e in InputMap.action_get_events(a):
			if e is InputEventMouseButton:
				InputMap.action_erase_event(a, e)


func _is_mobile_web() -> bool:
	if not OS.has_feature("web"):
		return false
	var ua = JavaScriptBridge.eval("navigator.userAgent || ''", true)
	var s := str(ua).to_lower()
	return s.contains("android") or s.contains("iphone") or s.contains("ipad") or s.contains("mobile")


# --- input ---------------------------------------------------------------

func _key(code: Key) -> InputEventKey:
	var e := InputEventKey.new()
	e.physical_keycode = code
	return e


func _mouse(b: MouseButton) -> InputEventMouseButton:
	var e := InputEventMouseButton.new()
	e.button_index = b
	return e


func _joy(b: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.button_index = b
	return e


func _axis(a: JoyAxis, v: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new()
	e.axis = a
	e.axis_value = v
	return e


func _setup_input() -> void:
	var map := {
		"left": [_key(KEY_A), _key(KEY_LEFT), _axis(JOY_AXIS_LEFT_X, -1.0)],
		"right": [_key(KEY_D), _key(KEY_RIGHT), _axis(JOY_AXIS_LEFT_X, 1.0)],
		"up": [_key(KEY_W), _key(KEY_UP), _axis(JOY_AXIS_LEFT_Y, -1.0)],
		"down": [_key(KEY_S), _key(KEY_DOWN), _axis(JOY_AXIS_LEFT_Y, 1.0)],
		"attack": [_key(KEY_J), _mouse(MOUSE_BUTTON_LEFT), _joy(JOY_BUTTON_X)],
		"special": [_key(KEY_K), _mouse(MOUSE_BUTTON_RIGHT), _joy(JOY_BUTTON_Y)],
		"cast": [_key(KEY_Q), _key(KEY_L), _joy(JOY_BUTTON_RIGHT_SHOULDER)],
		"dash": [_key(KEY_SPACE), _key(KEY_SHIFT), _joy(JOY_BUTTON_A)],
		"interact": [_key(KEY_E), _key(KEY_ENTER), _joy(JOY_BUTTON_B)],
		"pause": [_key(KEY_ESCAPE), _key(KEY_P), _joy(JOY_BUTTON_START)],
		"ui_1": [_key(KEY_1)], "ui_2": [_key(KEY_2)], "ui_3": [_key(KEY_3)],
	}
	for a in map:
		if not InputMap.has_action(a):
			InputMap.add_action(a, 0.3)
		for e in map[a]:
			InputMap.action_add_event(a, e)


# --- permanent progress ----------------------------------------------------

func load_meta() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return
	var d = JSON.parse_string(f.get_as_text())
	if d is Dictionary:
		for k in d:
			meta[k] = d[k]


func save_meta() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(meta))
	meta_changed.emit()


func setting(k: String):
	return meta.get("settings", {}).get(k, SETTING_DEFAULTS[k])


func set_setting(k: String, v) -> void:
	if not meta.has("settings") or not meta.settings is Dictionary:
		meta.settings = {}
	meta.settings[k] = v
	save_meta()
	settings_changed.emit()


func high_quality() -> bool:
	return setting("quality") == "high"


## Short rumble on phones (hits, slams, getting hurt).
func vibrate(ms: int) -> void:
	if touch_mode and setting("vibrate"):
		Input.vibrate_handheld(ms)


func up_rank(id: String) -> int:
	return int(meta.upgrades.get(id, 0))


func add_bunga(n: int) -> void:
	# vows (Heat) raise the reward
	if in_run and n > 0:
		n = int(round(n * (1.0 + 0.25 * run.get("heat", {}).size())))
	meta.bunga = int(meta.bunga) + n
	save_meta()


# --- vows (Heat): optional challenges unlocked after the first victory ----------

const VOWS := {
	"swift": ["Vow of Haste", "All foes move 25% faster."],
	"iron": ["Vow of Iron Hides", "All foes have 40% more health."],
	"fragile": ["Vow of Frailty", "Hanoman starts with 25% less health."],
	"horde": ["Vow of the Horde", "Empowered ogres appear far more often."],
	"kings": ["Vow of Wrathful Kings", "Bosses have 50% more health and hit harder."],
}


func vows() -> Array:
	return meta.get("vows", [])


func toggle_vow(id: String) -> void:
	var v: Array = vows().duplicate()
	if v.has(id):
		v.erase(id)
	else:
		v.append(id)
	meta.vows = v
	save_meta()


# --- records & codex -------------------------------------------------------------

func stat(k: String) -> float:
	return float(meta.get("stats", {}).get(k, 0))


func add_stat(k: String, v := 1.0) -> void:
	if not meta.has("stats") or not meta.stats is Dictionary:
		meta.stats = {}
	meta.stats[k] = float(meta.stats.get(k, 0)) + v


func unlock_codex(id: String) -> void:
	if Codex.ENTRIES.has(id) and not seen("codex_" + id):
		mark_seen("codex_" + id)
		say("Codex entry unlocked: " + Codex.ENTRIES[id][0], Color(0.75, 0.9, 1.0))


# --- mid-journey save -------------------------------------------------------------

const RUN_PATH := "user://hanoman_run.json"


func save_run(reward: Dictionary) -> void:
	var f := FileAccess.open(RUN_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify({"run": run, "reward": reward}))


func has_saved_run() -> bool:
	return FileAccess.file_exists(RUN_PATH)


func clear_saved_run() -> void:
	if FileAccess.file_exists(RUN_PATH):
		DirAccess.remove_absolute(RUN_PATH)


## Restore a saved journey; returns the reward of the room to re-enter.
func load_run() -> Dictionary:
	var f := FileAccess.open(RUN_PATH, FileAccess.READ)
	if f == null:
		return {}
	var d = JSON.parse_string(f.get_as_text())
	if not d is Dictionary or not d.has("run"):
		return {}
	run = d.run
	for id in run.get("boons", {}):
		run.boons[id].lvl = int(run.boons[id].lvl)
		run.boons[id].rar = int(run.boons[id].rar)
	for k in ["room", "kepeng", "death_defy", "dash_charges", "prana_max", "kills", "bunga_gained"]:
		run[k] = int(run.get(k, 0))
	run.room = int(run.room) - 1     # enter_room() steps back into the same room
	in_run = true
	run_changed.emit()
	return d.get("reward", {"type": "kepeng"})


func seen(key: String) -> bool:
	return meta.seen.has(key)


func mark_seen(key: String) -> void:
	meta.seen[key] = true
	save_meta()


# --- run -----------------------------------------------------------------

func new_run() -> void:
	var max_hp := 50 + 10 * up_rank("otot")
	run = {
		"hp": max_hp, "max_hp": max_hp,
		"kepeng": 60 * up_rank("rejeki"),
		"bunga_gained": 0,
		"boons": {},            # boon id -> level
		"slots": {},            # slot -> boon id (serang/jurus/ajian/lesat)
		"gods_met": [],
		"room": 0,
		"death_defy": up_rank("tulang"),
		"dash_charges": 1 + up_rank("lesat"),
		"prana_max": 3 + up_rank("prana"),
		"attack_mult": 1.0 + 0.15 * up_rank("gada"),
		"kills": 0,
		"heat": {},
		"started": Time.get_unix_time_from_system(),
	}
	for v in vows():
		run.heat[v] = true
	if run.heat.has("fragile"):
		run.max_hp = int(run.max_hp * 0.75)
		run.hp = run.max_hp
	in_run = true
	meta.runs = int(meta.runs) + 1
	save_meta()
	run_changed.emit()


func end_run(won: bool) -> void:
	in_run = false
	clear_saved_run()
	add_stat("kills", float(run.get("kills", 0)))
	var secs := Time.get_unix_time_from_system() - float(run.get("started", Time.get_unix_time_from_system()))
	add_stat("playtime", secs)
	if won:
		if stat("fastest") <= 0.0 or secs < stat("fastest"):
			meta.stats.fastest = secs
		meta.max_heat = max(int(meta.get("max_heat", 0)), run.get("heat", {}).size())
		meta.wins = int(meta.wins) + 1
	else:
		meta.deaths = int(meta.deaths) + 1
	meta.best_room = max(int(meta.best_room), int(run.get("room", 0)))
	save_meta()


func heal(n: float) -> void:
	run.hp = min(float(run.max_hp), float(run.hp) + n)
	run_changed.emit()


func add_kepeng(n: int) -> void:
	run.kepeng = int(run.kepeng) + n
	run_changed.emit()


func boon_level(id: String) -> int:
	return int(run.get("boons", {}).get(id, 0))


func say(text: String, color := Color(1, 0.92, 0.75)) -> void:
	toast.emit(text, color)
