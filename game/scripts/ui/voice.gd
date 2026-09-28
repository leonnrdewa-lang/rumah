class_name Voice
extends RefCounted
## Spoken dialog lines in Bahasa Indonesia through the platform's text-to-speech
## (the browser's speechSynthesis on the web build: Android Chrome and desktop
## Chrome/Edge ship natural Indonesian voices, so there is nothing to download).
## Every villager gets a stable voice: pitch and rate from their key, plus a
## female/male/old/child character. Without an Indonesian voice nothing speaks
## (an English voice reading Indonesian sounds wrong).

static var enabled := true
static var _voices: Array = []
static var _checked := false

## characters by key word -> [pitch, rate]
const FEMALE := ["ibu", "nenek", "mak", "bu_", "sari", "siti", "wati", "ani", "rina", "dewi", "nyai", "mbak"]
const OLD := ["kakek", "nenek", "mbah", "pak_tua", "haji"]
const CHILD := ["anak", "dik", "bocah"]


static func _ensure() -> void:
	if _checked:
		return
	_checked = true
	if not ProjectSettings.get_setting("audio/general/text_to_speech", false):
		return
	for code in ["id", "id_ID", "id-ID", "in"]:
		_voices.append_array(DisplayServer.tts_get_voices_for_language(code))
	if _voices.is_empty():
		# some browsers only list voices after a moment: look again on the next line
		_checked = false


static func _has(s: String, words: Array) -> bool:
	for w in words:
		if s.contains(w):
			return true
	return false


static func speak(who_key: String, speaker: String, text: String) -> void:
	if not enabled or text.strip_edges() == "":
		return
	_ensure()
	stop()
	if _voices.is_empty():
		return
	var k := (who_key + " " + speaker).to_lower()
	var h := absi(hash(k))
	var pitch := 0.9 + float(h % 21) / 100.0          # 0.90 .. 1.10 per person
	var rate := 1.0 + float((h / 21) % 13) / 100.0    # 1.00 .. 1.12
	if _has(k, FEMALE):
		pitch += 0.28
	if _has(k, OLD):
		pitch -= 0.12
		rate -= 0.12
	if _has(k, CHILD):
		pitch += 0.5
		rate += 0.08
	var clean := _clean(text)
	var v: String = _voices[h % _voices.size()]
	DisplayServer.tts_speak(clean, v, 80, clampf(pitch, 0.5, 2.0), clampf(rate, 0.7, 1.4))


static func stop() -> void:
	if _checked and not _voices.is_empty():
		DisplayServer.tts_stop()


static func _clean(t: String) -> String:
	var re := RegEx.new()
	re.compile("\\[[^\\]]*\\]")        # BBCode
	var s := re.sub(t, "", true)
	s = s.replace("Rp ", "rupiah ").replace("TBS", "te be es").replace("PKS", "pe ka es")
	s = s.replace("...", ", ").replace("…", ", ").replace("*", "")
	return s
