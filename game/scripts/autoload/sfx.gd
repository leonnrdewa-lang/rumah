extends Node
## Tiny audio manager: one-shot sound effects, background music and ambience.
## Sounds are generated offline by tools/make_audio.py into assets/audio/.

const SOUNDS := ["click", "coin", "chop", "plant", "harvest", "bad", "quest", "pop", "whoosh", "step", "door", "cash"]

var _streams := {}
var _players: Array[AudioStreamPlayer] = []
var _music: AudioStreamPlayer
var _ambient: AudioStreamPlayer
var music_on := true
var sfx_on := true


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for s in SOUNDS:
		var path := "res://assets/audio/%s.wav" % s
		if ResourceLoader.exists(path):
			_streams[s] = load(path)
	for i in 8:
		var p := AudioStreamPlayer.new()
		p.bus = "Master"
		add_child(p)
		_players.append(p)
	_music = AudioStreamPlayer.new()
	_music.volume_db = -9.0
	add_child(_music)
	_ambient = AudioStreamPlayer.new()
	_ambient.volume_db = -14.0
	add_child(_ambient)
	if ResourceLoader.exists("res://assets/audio/music.wav"):
		_music.stream = load("res://assets/audio/music.wav")
	if ResourceLoader.exists("res://assets/audio/ambient.wav"):
		_ambient.stream = load("res://assets/audio/ambient.wav")


func play(name: String, pitch := 1.0, volume_db := 0.0) -> void:
	if not sfx_on or not _streams.has(name):
		return
	for p in _players:
		if not p.playing:
			p.stream = _streams[name]
			p.pitch_scale = pitch * randf_range(0.96, 1.04)
			p.volume_db = volume_db
			p.play()
			return


func start_music() -> void:
	if music_on and _music.stream and not _music.playing:
		_music.play()
	if _ambient.stream and not _ambient.playing:
		_ambient.play()


func set_music(on: bool) -> void:
	music_on = on
	if on:
		start_music()
	else:
		_music.stop()
