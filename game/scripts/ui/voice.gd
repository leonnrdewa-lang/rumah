class_name Voice
extends RefCounted
## Spoken dialog: pre-rendered voice acting in Bahasa Indonesia, a distinct voice per
## character (tools/make_voices.py: neural Indonesian TTS + WORLD vocoder character
## transforms, every clip checked with speech recognition).
##
## The audio lives OUTSIDE the game pack: one Ogg bank per character in voices/
## (next to index.html on the web, game/voices/ from source), fetched lazily and
## cached, so the download stays small. res://data/voice_index.json (inside the pack)
## says which bank holds which line: clips are keyed by the md5 of the line's display
## text (stage directions in parentheses dropped). Lines built from open-ended numbers
## match a template (regex) instead, and anything unknown falls back to one of the
## speaker's short barks picked from the line's mood, so a known speaker never stays
## silent. API used by ui.gd: speak(portrait_key, speaker, text), stop(), enabled.

static var enabled := true
## counters for the autotest: how lines resolved ("line", "template", "bark", "none")
static var stats := {"line": 0, "template": 0, "bark": 0, "none": 0, "played": 0}
static var _node: _VoiceNode
static var _index: Dictionary = {}
static var _templates: Array = []   # [{chars: {id: true}, re: RegEx, group, variants, default, by_capture}]

const INDEX_PATH := "res://data/voice_index.json"
const CACHE_BANKS := 18   # bank files kept in memory (~0.3-0.9 MB each)


static func _ensure() -> bool:
	if _index.is_empty():
		var f := FileAccess.open(INDEX_PATH, FileAccess.READ)
		if f == null:
			return false
		var d = JSON.parse_string(f.get_as_text())
		if not (d is Dictionary):
			return false
		_index = d
		_templates.clear()
		for t in _index.get("templates", []):
			var re := RegEx.new()
			if re.compile(str(t["re"])) != OK:
				continue
			var cs := {}
			for c in t.get("chars", []):
				cs[c] = true
			_templates.append({"chars": cs, "re": re, "group": int(t.get("group", 1)),
				"variants": t.get("variants", {}), "default": str(t.get("default", "")),
				"by_capture": t.get("by_capture", {})})
	if _node == null or not is_instance_valid(_node):
		var tree := Engine.get_main_loop() as SceneTree
		if tree == null or tree.root == null:
			return false
		_node = _VoiceNode.new()
		_node.name = "VoicePlayer"
		tree.root.add_child.call_deferred(_node)
	return true


## the lookup text: stage directions "(...)", BBCode and line breaks dropped
static func canon(text: String) -> String:
	var re := RegEx.new()
	re.compile("\\[[^\\]]*\\]|\\([^)]*\\)")
	var t := re.sub(text, "", true).replace("\n", " ")
	var sp := RegEx.new()
	sp.compile("\\s+")
	t = sp.sub(t, " ", true).strip_edges()
	if t.length() > 1 and t.begins_with("\"") and t.ends_with("\""):
		t = t.substr(1, t.length() - 2).strip_edges()
	return t


static func text_key(text: String) -> String:
	return canon(text).md5_text().substr(0, 12)


## Which character speaks: the display name first (every villager has a unique one),
## then the portrait (passers-by are all "Warga").
static func character_of(speaker: String, portrait_key: String) -> String:
	if not _ensure():
		return ""
	var sp: Dictionary = _index.get("speakers", {})
	if sp.has(speaker):
		return str(sp[speaker])
	var banks: Dictionary = _index.get("banks", {})
	var pk := portrait_key.trim_prefix("portrait_")
	var by_portrait: Dictionary = _index.get("portraits", {})
	if speaker == "Warga" and banks.has("warga_" + pk):
		return "warga_" + pk
	if by_portrait.has(pk):
		return str(by_portrait[pk])
	return "warga_" + pk if banks.has("warga_" + pk) else ""


## -> {"char": id, "clip": key, "kind": "line"|"template"|"bark"|"none"}
static func resolve(portrait_key: String, speaker: String, text: String) -> Dictionary:
	var cid := character_of(speaker, portrait_key)
	var out := {"char": cid, "clip": "", "kind": "none"}
	if cid == "":
		return out
	var bank: Dictionary = _index["banks"].get(cid, {})
	var clips: Dictionary = bank.get("clips", {})
	var ct := canon(text)
	var k := ct.md5_text().substr(0, 12)
	if clips.has(k):
		out["clip"] = k
		out["kind"] = "line"
		return out
	for t in _templates:
		if not t["chars"].has(cid):
			continue
		var m: RegExMatch = t["re"].search(ct)
		if m == null:
			continue
		var cap := m.get_string(t["group"]) if m.get_group_count() >= t["group"] else ""
		var pick := ""
		if t["variants"].has(cap):
			pick = str(t["variants"][cap])
		elif t["by_capture"].has(cap):
			pick = str(t["by_capture"][cap])
		else:
			pick = t["default"]
		if pick != "" and clips.has(pick):
			out["clip"] = pick
			out["kind"] = "template"
			return out
	var barks: Dictionary = bank.get("barks", {})
	var mood := mood_of(ct)
	var b := str(barks.get(mood, barks.get("neutral", "")))
	if b != "" and clips.has(b):
		out["clip"] = b
		out["kind"] = "bark"
	return out


## a line's mood from its punctuation and a few words (for the fallback barks)
static func mood_of(t: String) -> String:
	var l := t.to_lower()
	if l.begins_with("haha") or l.contains("hehe"):
		return "laugh"
	if l.contains("?!") or l.contains("tidak!") or l.contains("palsu"):
		return "annoyed"
	if l.contains("...") or l.contains("aduh") or l.contains("ampun"):
		return "sad"
	if t.ends_with("!") or l.begins_with("wah"):
		return "surprise"
	if t.ends_with("?"):
		return "neutral"
	return "yes" if l.contains("juragan") else "neutral"


static func speak(who_key: String, speaker: String, text: String) -> void:
	if not enabled or text.strip_edges() == "" or not _ensure():
		return
	var r := resolve(who_key, speaker, text)
	stats[r["kind"]] = int(stats.get(r["kind"], 0)) + 1
	if r["kind"] == "none":
		stop()
		return
	var bank: Dictionary = _index["banks"][r["char"]]
	var seg: Array = bank["clips"][r["clip"]]   # [file index, start, duration]
	var files: Array = bank["files"]
	_node.request(str(files[int(seg[0])]), float(seg[1]), float(seg[2]))
	# a conversation has started: the rest of this person's lines (the business talk) too
	for f in files:
		_node.fetch(str(f))


static func stop() -> void:
	if _node and is_instance_valid(_node):
		_node.halt()


static func is_speaking() -> bool:
	return _node != null and is_instance_valid(_node) and _node.speaking()


## a line is waiting for its bank to download
static func is_pending() -> bool:
	return _node != null and is_instance_valid(_node) and not _node.want.is_empty()


## load a character's first bank (greetings, chat, barks) ahead of time: voice.gd does
## this for the people near the player; the rest comes when a conversation starts
static func prefetch(char_id: String) -> void:
	if not enabled or char_id == "" or not _ensure():
		return
	var bank: Dictionary = _index["banks"].get(char_id, {})
	if not bank.is_empty():
		_node.fetch(str(bank["files"][0]))


static func bank_ready(char_id: String) -> bool:
	if _node == null or not is_instance_valid(_node) or not _ensure():
		return false
	var bank: Dictionary = _index["banks"].get(char_id, {})
	return not bank.is_empty() and _node.has_bank(str(bank["files"][0]))


## every line of the manifest (res://data/voice_manifest.json, source tree only) that
## would not play a clip in its own speaker's voice
static func check_manifest() -> Array:
	var bad: Array = []
	if not _ensure():
		return ["no voice index"]
	var f := FileAccess.open("res://data/voice_manifest.json", FileAccess.READ)
	if f == null:
		return ["no manifest"]
	var man: Dictionary = JSON.parse_string(f.get_as_text())
	var chars: Dictionary = man.get("characters", {})
	for l in man.get("lines", []):
		var cid: String = l["char"]
		var c: Dictionary = chars.get(cid, {})
		var name: String = c.get("name", "")
		var r := resolve(str(c.get("portrait", "")), name, str(l["text"]))
		if r["char"] != cid or r["kind"] == "none":
			bad.append("%s: %s -> %s" % [cid, str(l["text"]).left(50), r])
		elif not str(l["src"]).begins_with("generic") and not str(l["src"]).begins_with("bark") and r["kind"] != "line":
			bad.append("%s: %s -> %s (no exact clip)" % [cid, str(l["text"]).left(50), r["kind"]])
	return bad


# ------------------------------------------------------------------ player node
class _VoiceNode:
	extends Node
	var player: AudioStreamPlayer
	var banks := {}          # bank file -> AudioStreamOggVorbis
	var order: Array = []    # LRU of loaded banks
	var loading := {}        # bank file -> true
	var want := {}           # the line waiting for its bank: {file, start, dur, t}
	var stop_at := -1.0
	var _poll := 0.0
	var _ducked := false

	func _ready() -> void:
		process_mode = Node.PROCESS_MODE_ALWAYS
		player = AudioStreamPlayer.new()
		player.bus = "Voice" if AudioServer.get_bus_index("Voice") >= 0 else "Master"
		add_child(player)
		# the phone boss calls first thing, and the player talks back
		for c in ["hq", "player"]:
			Voice.prefetch(c)
		_play_want.call_deferred()  # a line asked for before this node joined the tree

	func speaking() -> bool:
		return player != null and player.playing and stop_at > 0.0

	func has_bank(file: String) -> bool:
		return banks.has(file)

	func request(file: String, start: float, dur: float) -> void:
		halt()
		want = {"file": file, "start": start, "dur": dur, "t": Time.get_ticks_msec()}
		if banks.has(file):
			_play_want()
		else:
			fetch(file)

	func halt() -> void:
		want = {}
		stop_at = -1.0
		if player and player.playing:
			player.stop()
		_duck(false)

	func _duck(on: bool) -> void:
		if on == _ducked:
			return
		_ducked = on
		if Sfx.has_method("duck_voice"):
			Sfx.duck_voice(on)

	func _play_want() -> void:
		if want.is_empty() or not banks.has(want["file"]) or player == null or not is_inside_tree():
			return
		# a line whose bank arrived too late is dropped rather than talking over the next one
		# (closing the dialog calls halt() and clears it; 10 s covers a slow phone network)
		if Time.get_ticks_msec() - int(want["t"]) > 10000:
			want = {}
			return
		var file: String = want["file"]
		order.erase(file)
		order.append(file)
		player.stream = banks[file]
		player.play(float(want["start"]))
		stop_at = float(want["start"]) + float(want["dur"])
		Voice.stats["played"] = int(Voice.stats.get("played", 0)) + 1
		want = {}
		_duck(true)

	func fetch(file: String) -> void:
		if banks.has(file) or loading.has(file):
			return
		if not is_inside_tree():
			# the node joins the tree deferred: the very first line (the intro call) comes
			# earlier, so retry once it is in
			fetch.call_deferred(file)
			return
		loading[file] = true
		if OS.has_feature("web"):
			var url := str(JavaScriptBridge.eval("new URL('voices/%s', document.baseURI).href" % file, true))
			var http := HTTPRequest.new()
			add_child(http)
			http.request_completed.connect(func(result: int, code: int, _h: PackedStringArray, body: PackedByteArray):
				http.queue_free()
				_loaded(file, body if result == HTTPRequest.RESULT_SUCCESS and code == 200 else PackedByteArray()))
			if http.request(url) != OK:
				http.queue_free()
				_loaded(file, PackedByteArray())
			return
		var bytes := PackedByteArray()
		for p in ["res://voices/" + file, OS.get_executable_path().get_base_dir().path_join("voices/" + file)]:
			if FileAccess.file_exists(p):
				bytes = FileAccess.get_file_as_bytes(p)
				break
		_loaded.call_deferred(file, bytes)

	func _loaded(file: String, bytes: PackedByteArray) -> void:
		loading.erase(file)
		var s: AudioStreamOggVorbis = null
		if not bytes.is_empty():
			s = AudioStreamOggVorbis.load_from_buffer(bytes)
		if s == null:
			push_warning("voice bank %s could not be loaded" % file)
			if not want.is_empty() and want["file"] == file:
				want = {}
			return
		s.loop = false
		banks[file] = s
		order.append(file)
		while order.size() > Voice.CACHE_BANKS:
			var old: String = order.pop_front()
			if player.stream == banks.get(old) and player.playing:
				order.append(old)
				break
			banks.erase(old)
		if not want.is_empty() and want["file"] == file:
			_play_want()

	func _process(delta: float) -> void:
		if stop_at > 0.0:
			if not player.playing or player.get_playback_position() >= stop_at:
				player.stop()
				stop_at = -1.0
				_duck(false)
		if not want.is_empty() and Time.get_ticks_msec() - int(want["t"]) > 4000:
			want = {}
		_poll -= delta
		if _poll <= 0.0:
			_poll = 0.5
			_prefetch_nearby()

	func _prefetch_nearby() -> void:
		## banks of the people around the player, twice a second
		if not Voice.enabled:
			return
		var w := get_tree().current_scene
		if w == null or not ("npcs" in w) or w.get("player") == null or str(w.get("state")) != "play":
			return
		var at: Vector3 = w.player.global_position
		var sp: Dictionary = Voice._index.get("speakers", {})
		var ivid = w.get("_inside_vid")
		if ivid is String and ivid != "":
			Voice.prefetch(ivid)
		var people: Array = w.npcs.values() + w.extras.values() + w.walkers
		for n in people:
			if not is_instance_valid(n) or not (n is Node3D):
				continue
			if (n.global_position - at).length_squared() > 16.0 * 16.0:
				continue
			var cid := ""
			if n.vid != "":
				cid = n.vid
			elif sp.has(n.display_name):
				cid = str(sp[n.display_name])
			elif n.display_name == "Warga":
				cid = "warga_" + str(n.model_name).trim_prefix("char_")
			if cid != "":
				Voice.prefetch(cid)

	func _exit_tree() -> void:
		if player:
			player.stop()
			player.stream = null
		banks.clear()
