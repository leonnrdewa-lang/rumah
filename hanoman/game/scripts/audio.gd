extends Node
## Music (crossfading between two players), ambience and pooled one-shot SFX.
## Files are looked up as res://assets/audio/<name>.ogg; missing files are skipped
## silently so the game runs before the audio pass is done. Autoloaded as `Au`.

const DIR := "res://assets/audio/"
const POOL := 20
## New effects that have no built-in recording fall back to the closest one.
const FALLBACK := {
	"sfx_laser": "sfx_special", "sfx_laser_hit": "sfx_hit_heavy", "sfx_geyser": "sfx_shark_splash",
	"sfx_tail": "sfx_swing3", "sfx_enemy_dash": "sfx_dash", "sfx_explosion": "sfx_explode",
	"sfx_enemy_slam": "sfx_slam", "sfx_staff_slam": "sfx_slam", "sfx_bite": "sfx_croc_snap",
	"sfx_gate": "sfx_door_open", "sfx_boon": "sfx_boon_appear",
	"mus_miniboss": "mus_dandaka",
	"sfx_punch1": "sfx_hit", "sfx_punch2": "sfx_hit", "sfx_punch_heavy": "sfx_hit_heavy",
	"sfx_pot_break": "sfx_explode", "sfx_coin_drop": "sfx_pickup_coin", "sfx_bell": "sfx_boon_appear",
	"sfx_rock_hit": "sfx_hit_heavy", "sfx_staff_draw": "sfx_swing1",
}

var _mus: Array[AudioStreamPlayer] = []
var _cur := 0
var _music_name := ""
var _amb: AudioStreamPlayer
var _amb_name := ""
var _pool: Array[AudioStreamPlayer] = []
var _next := 0
var _cache := {}
var _last_play := {}
var music_volume := 0.8
var sfx_volume := 1.0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_bus("Music", -4.0)
	_bus("SFX", 0.0)
	_bus("Amb", -8.0)
	for i in 2:
		var p := AudioStreamPlayer.new()
		p.bus = "Music"
		p.volume_db = -80.0
		add_child(p)
		_mus.append(p)
	_amb = AudioStreamPlayer.new()
	_amb.bus = "Amb"
	add_child(_amb)
	for i in POOL:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_pool.append(p)
	G.settings_changed.connect(_apply_volumes)
	_apply_volumes.call_deferred()


## Music level follows the action (combat louder, calm rooms softer), the
## player's volume settings and dialogue/menu ducking.
var _combat := false
var _ducked := false


func _music_db() -> float:
	var base := -3.0 if _combat else -9.0
	if _ducked:
		base -= 10.0
	return base + linear_to_db(maxf(float(G.setting("music")), 0.001))


func _apply_volumes(fade := 0.0) -> void:
	var mi := AudioServer.get_bus_index("Music")
	var si := AudioServer.get_bus_index("SFX")
	AudioServer.set_bus_volume_db(si, linear_to_db(maxf(float(G.setting("sfx")), 0.001)))
	AudioServer.set_bus_mute(si, float(G.setting("sfx")) < 0.01)
	AudioServer.set_bus_mute(mi, float(G.setting("music")) < 0.01)
	var target := _music_db()
	if fade <= 0.0:
		AudioServer.set_bus_volume_db(mi, target)
	else:
		create_tween().tween_method(func(v): AudioServer.set_bus_volume_db(mi, v),
			AudioServer.get_bus_volume_db(mi), target, fade)


func intensity(combat: bool) -> void:
	if combat == _combat:
		return
	_combat = combat
	_apply_volumes(1.5)


func _bus(name: String, db: float) -> void:
	if AudioServer.get_bus_index(name) != -1:
		return
	AudioServer.add_bus()
	var i := AudioServer.bus_count - 1
	AudioServer.set_bus_name(i, name)
	AudioServer.set_bus_send(i, "Master")
	AudioServer.set_bus_volume_db(i, db)


func _load(name: String) -> AudioStream:
	if _cache.has(name):
		return _cache[name]
	# Higgsfield pack first (epic generated sound effects), then the built-in file
	var s: AudioStream = Hf.sound(name)
	if s == null:
		var path := DIR + name + ".ogg"
		if ResourceLoader.exists(path):
			s = load(path)
		elif FALLBACK.has(name):
			s = _load(FALLBACK[name])
	if Hf.loaded:   # until the pack is in, keep asking so its sounds win
		_cache[name] = s
	return s


func music(name: String, fade := 1.2) -> void:
	if name == _music_name:
		return
	_music_name = name
	if name != "" and Hf.has_music(name):
		Hf.music_stream(name, func(st: AudioStream):
			if _music_name == name:
				_play_music(name, st if st else _load(name), fade))
		return
	_play_music(name, _load(name) if name != "" else null, fade)


func _play_music(name: String, s: AudioStream, fade: float) -> void:
	var old := _mus[_cur]
	_cur = 1 - _cur
	var nw := _mus[_cur]
	var tw := create_tween().set_parallel(true)
	tw.tween_property(old, "volume_db", -60.0, fade)
	tw.chain().tween_callback(old.stop)
	if s:
		if s is AudioStreamOggVorbis and not name.begins_with("stg_"):
			(s as AudioStreamOggVorbis).loop = true
		elif s is AudioStreamMP3:
			(s as AudioStreamMP3).loop = true
		nw.stream = s
		nw.volume_db = -40.0
		nw.play()
		create_tween().tween_property(nw, "volume_db", linear_to_db(music_volume), fade)


func ambience(name: String) -> void:
	if name == _amb_name:
		return
	_amb_name = name
	var s := _load(name) if name != "" else null
	if s == null:
		_amb.stop()
		return
	if s is AudioStreamOggVorbis:
		(s as AudioStreamOggVorbis).loop = true
	_amb.stream = s
	_amb.play()


func sting(name: String) -> void:
	var s := _load(name)
	if s == null:
		return
	var p := _pool[_next]
	_next = (_next + 1) % POOL
	p.stream = s
	p.bus = "Music"
	p.volume_db = 0.0
	p.pitch_scale = 1.0
	p.play()


## Play a one-shot. `vary` randomises pitch a little; a sound is throttled to at
## most one start per 35 ms so mass hits don't stack into noise.
func sfx(name: String, vol_db := 0.0, vary := 0.08, pitch := 1.0) -> void:
	var s := _load(name)
	if s == null:
		return
	var now := Time.get_ticks_msec()
	if now - int(_last_play.get(name, -1000)) < 35:
		return
	_last_play[name] = now
	var p := _pool[_next]
	_next = (_next + 1) % POOL
	p.stream = s
	p.bus = "SFX"
	p.volume_db = vol_db + linear_to_db(sfx_volume)
	p.pitch_scale = pitch * (1.0 + randf_range(-vary, vary))
	p.play()


func duck(on: bool) -> void:
	_ducked = on
	_apply_volumes(0.4)
