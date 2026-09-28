class_name AnimRig
extends Rig
## Drives a skinned, keyframed model (Higgsfield image-to-3D + auto-rig, clips
## merged into one GLB) through the same API the combat code uses for the
## procedural Rig: play(action, length), update(delta, speed), hit().
## Game actions map to clips via the manifest's "clips" table; an action clip is
## time-scaled so its strike lands when the game's hit frame fires.

const BLEND := 0.12

var ap: AnimationPlayer
var clips := {}          # logical name -> animation name in the player
var loco := ""
var _locked_until := 0.0
var _dead := false
var _freeze_at := -1.0


func _init(model: Node3D, rig_style := "biped") -> void:
	super._init(model, rig_style)
	ap = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var info: Dictionary = model.get_meta("hf_info", {})
	var table: Dictionary = info.get("clips", {})
	var names := ap.get_animation_list() if ap else PackedStringArray()
	for logical in table:
		var want := String(table[logical]).to_lower()
		for n in names:
			if String(n).to_lower() == want or String(n).to_lower().ends_with("|" + want):
				clips[logical] = n
	for n in names:
		var low := String(n).to_lower()
		for key in ["idle", "run", "walk", "attack", "hit", "dead", "die", "cast", "dash", "slam"]:
			if not clips.has(key) and low.contains(key):
				clips[key] = n
	for key in ["idle", "run", "walk"]:
		if clips.has(key):
			var a := ap.get_animation(clips[key])
			if a:
				a.loop_mode = Animation.LOOP_LINEAR
	if ap:
		_play_clip(_first(["idle", "walk", "run"]), 1.0, 0.0)
	print("AnimRig %s: clips=%s" % [model.name, str(clips)])


func _first(keys: Array) -> String:
	for k in keys:
		if clips.has(k):
			return clips[k]
	return ""


func _play_clip(anim: String, spd := 1.0, blend := BLEND) -> void:
	if anim == "" or ap == null:
		return
	ap.play(anim, blend, spd)


const ACTION_MAP := {
	"swing_a": ["attack_1", "attack"], "swing_b": ["attack_2", "attack_1", "attack"],
	"slam": ["attack_3", "slam", "attack"], "thrust": ["special", "attack_1", "attack"],
	"cast": ["cast", "attack_3", "attack"], "lunge": ["attack", "attack_1"],
	"bite": ["attack", "bite"], "snap": ["attack"], "charge": ["run", "walk"],
	"windup": ["attack", "attack_1"], "rear": ["roar", "attack", "idle"], "roar": ["roar", "idle"],
	"spin": ["attack_3", "attack"], "dash": ["dash"], "talk": ["talk", "idle"],
	"guard": [], "die": ["die", "dead"], "hurt": ["hit", "hurt"],
}


func play(a: String, length := 0.3) -> void:
	super.play(a, length)
	if ap == null or _dead:
		return
	var cands: Array = ACTION_MAP.get(a, ["attack"])
	var anim := ""
	for c in cands:
		if clips.has(c):
			anim = clips[c]
			break
	if anim == "":
		return
	var clip_len := ap.get_animation(anim).length
	_freeze_at = -1.0
	if a == "die":
		_dead = true
		_play_clip(anim, 1.0, 0.08)
		return
	if a == "windup":
		# hold the strike clip on its anticipation pose as a telegraph
		_play_clip(anim, 1.0, 0.08)
		_freeze_at = clip_len * 0.28
		_locked_until = t + length
		return
	var spd: float = clamp(clip_len / max(length, 0.05), 0.6, 3.5)
	if a == "charge" or a == "talk":
		spd = 1.3 if a == "charge" else 1.0
	_play_clip(anim, spd, 0.06)
	_locked_until = t + length


func revive() -> void:
	super.revive()
	_dead = false
	_locked_until = 0.0
	_freeze_at = -1.0
	if ap:
		ap.speed_scale = 1.0
		_play_clip(_first(["idle", "walk", "run"]), 1.0, 0.0)


func hit() -> void:
	super.hit()
	if ap and not _dead and t >= _locked_until and clips.has("hit"):
		_play_clip(clips.hit, 1.6, 0.05)
		_locked_until = t + 0.22


func update(delta: float, spd: float) -> void:
	t += delta
	speed = lerp(speed, spd, clamp(delta * 10.0, 0.0, 1.0))
	if action != "":
		action_t += delta
		if action_t >= action_len:
			action = ""
	if ap == null or _dead:
		return
	if _freeze_at >= 0.0 and ap.current_animation_position >= _freeze_at:
		ap.speed_scale = 0.0
	else:
		ap.speed_scale = 1.0
	if t < _locked_until:
		return
	_freeze_at = -1.0
	var want := ""
	var sscale := 1.0
	if speed > 0.6:
		want = _first(["run", "walk"])
		sscale = clamp(speed / 5.5, 0.6, 1.6) if want == clips.get("run", "") else clamp(speed / 2.5, 0.6, 1.8)
	else:
		want = _first(["idle", "walk"])
		if not clips.has("idle"):
			sscale = 0.15
	if want != "" and (ap.current_animation != want or not ap.is_playing()):
		_play_clip(want, 1.0, 0.15)
	ap.speed_scale = sscale
