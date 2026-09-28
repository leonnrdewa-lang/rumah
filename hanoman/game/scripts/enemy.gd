class_name Enemy
extends Actor
## Raksasa of Hutan Dandaka and Muara. One script, behaviour picked by `kind`:
##   wil        small fast imp, quick lunge bite
##   cakil      Buto Cakil, keeps distance, telegraphed keris charge
##   buto_ijo   big green ogre, slow, telegraphed area slam
##   banaspati  floating fire skull, keeps away, shoots fireballs
##   yuyu       Yuyu Kangkang giant crab, shell blocks hits from the front, claw snap
## Bosses extend this class (kijang.gd, sura.gd, baya.gd).

const STATS := {
	"wil": {"hp": 24, "speed": 4.6, "r": 0.45, "h": 1.1, "style": "biped", "range": 1.4, "dmg": 6},
	"cakil": {"hp": 50, "speed": 3.4, "r": 0.5, "h": 1.8, "style": "biped", "range": 6.0, "dmg": 10},
	"buto_ijo": {"hp": 130, "speed": 2.3, "r": 1.0, "h": 3.0, "style": "biped", "range": 2.8, "dmg": 14},
	"banaspati": {"hp": 30, "speed": 3.0, "r": 0.5, "h": 1.6, "style": "float", "range": 9.0, "dmg": 8},
	"yuyu": {"hp": 90, "speed": 2.6, "r": 1.1, "h": 1.2, "style": "crab", "range": 2.4, "dmg": 12},
}
const HPBAR := preload("res://shaders/hpbar.gdshader")

var kind := "wil"
var state := "spawn"
var state_t := 0.0
var dmg := 6.0
var atk_range := 1.4
var cooldown := 0.0
var target_dir := Vector3.FORWARD
var tele: Node3D
var _bar: MeshInstance3D
var _bar_mat: ShaderMaterial
var _lag := 1.0
var _wander := Vector3.ZERO
var _strafe := 1.0
var _hit_this_attack := false
var elite := false


func setup(p_kind: String, depth := 0) -> void:
	kind = p_kind
	var s: Dictionary = STATS.get(kind, STATS.wil)
	max_hp = float(s.hp) * (1.0 + depth * 0.06)
	hp = max_hp
	move_speed = s.speed
	dmg = s.dmg
	atk_range = s.range
	setup_body(s.r, s.h, L_ENEMY, L_WORLD | L_ENEMY | L_PLAYER)
	set_model(kind, s.style)
	if kind == "buto_ijo":
		knock_resist = 0.7
	if kind == "yuyu":
		knock_resist = 0.5
	_strafe = 1.0 if randf() < 0.5 else -1.0
	cooldown = randf_range(0.4, 1.4)


func _ready() -> void:
	add_to_group("enemy")
	_make_bar()
	invuln = 0.7
	state = "spawn"
	state_t = 0.0
	if model:
		model.position.y = -1.5
		create_tween().tween_property(model, "position:y", 0.0, 0.55).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	Fx.burst(global_position + Vector3(0, 0.3, 0), Color(0.5, 0.15, 0.6), 20, 4.0, 0.3, 0.6)


func _make_bar() -> void:
	_bar = MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(1.1 if radius < 0.8 else 1.8, 0.14)
	_bar.mesh = q
	_bar_mat = ShaderMaterial.new()
	_bar_mat.shader = HPBAR
	_bar.material_override = _bar_mat
	_bar.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_bar.position.y = float(STATS.get(kind, STATS.wil).h) + 0.5
	_bar.visible = false
	add_child(_bar)


func _update_bar(delta: float) -> void:
	if _bar == null:
		return
	var r := hp / max_hp
	_lag = move_toward(_lag, r, delta * 0.8)
	_bar.visible = r < 0.999 and not dead
	_bar_mat.set_shader_parameter("ratio", r)
	_bar_mat.set_shader_parameter("lag", _lag)


func player() -> Player:
	return G.main.player


func to_player() -> Vector3:
	var v: Vector3 = player().global_position - global_position
	v.y = 0
	return v


func set_state(s: String) -> void:
	state = s
	state_t = 0.0
	_hit_this_attack = false


func _physics_process(delta: float) -> void:
	tick_status(delta)
	_update_bar(delta)
	if dead:
		return
	state_t += delta
	cooldown = max(0.0, cooldown - delta)
	var want := Vector3.ZERO
	if state == "spawn":
		if state_t > 0.6:
			set_state("chase")
	elif stagger > 0.0 and state != "attack":
		want = Vector3.ZERO
	else:
		want = think(delta)
	var sf := slow_factor()
	velocity = want * sf + knock + _separation() * 2.0
	velocity.y = 0
	move_and_slide()
	global_position.y = 0.0
	if rig:
		rig.update(delta * (0.4 + 0.6 * sf), Vector2(want.x, want.z).length() * sf)


func _separation() -> Vector3:
	var push := Vector3.ZERO
	for e in G.main.enemies():
		if e == self or e.dead:
			continue
		var d: Vector3 = global_position - e.global_position
		d.y = 0
		var l := d.length()
		var m: float = radius + e.radius
		if l < m and l > 0.001:
			push += d / l * (m - l)
	return push


## Returns the desired velocity for this frame.
func think(delta: float) -> Vector3:
	match kind:
		"cakil":
			return _think_cakil(delta)
		"buto_ijo":
			return _think_buto(delta)
		"banaspati":
			return _think_banaspati(delta)
		"yuyu":
			return _think_yuyu(delta)
	return _think_wil(delta)


func _chase_speed() -> float:
	return move_speed


func _telegraph(pos: Vector3, r: float, time: float, arc := TAU, yaw := 0.0) -> void:
	if tele and is_instance_valid(tele):
		tele.queue_free()
	tele = Fx.ring(pos, r, Color(1.0, 0.18, 0.15), time, true, arc, yaw)
	Au.sfx("sfx_telegraph", -14.0, 0.05)


func _clear_tele() -> void:
	if tele and is_instance_valid(tele):
		tele.queue_free()
	tele = null


func _melee(center: Vector3, r: float, amount: float, kb := 4.0) -> bool:
	if _hit_this_attack:
		return false
	var p := player()
	var d := Vector2(p.global_position.x - center.x, p.global_position.z - center.z).length()
	if d < r + p.radius * 0.6:
		_hit_this_attack = true
		p.take_hit(amount, global_position, kb)
		return true
	return false


# --- Wil -------------------------------------------------------------------

func _think_wil(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	match state:
		"chase":
			face_toward(to, delta)
			if d < atk_range + 0.6 and cooldown <= 0.0:
				set_state("windup")
				target_dir = to.normalized()
				rig.play("windup", 0.35)
				_telegraph(global_position, 1.8, 0.35, 1.6, atan2(target_dir.x, target_dir.z))
				return Vector3.ZERO
			var side := to.normalized().cross(Vector3.UP) * _strafe * 0.3
			return (to.normalized() + side).normalized() * _chase_speed()
		"windup":
			if state_t > 0.35:
				set_state("attack")
				rig.play("lunge", 0.3)
				Au.sfx("sfx_swing1", -10.0, 0.2, 1.4)
			return Vector3.ZERO
		"attack":
			_melee(global_position + target_dir * 0.9, 1.0, dmg, 3.0)
			if state_t > 0.25:
				set_state("recover")
				cooldown = randf_range(0.9, 1.6)
				_clear_tele()
			return target_dir * 7.0
		"recover":
			if state_t > 0.5:
				set_state("chase")
	return Vector3.ZERO


# --- Buto Cakil ----------------------------------------------------------------

func _think_cakil(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	match state:
		"chase":
			face_toward(to, delta)
			if cooldown <= 0.0 and d < 8.0:
				set_state("windup")
				target_dir = to.normalized()
				rig.play("windup", 0.7)
				_telegraph(global_position, 6.5, 0.7, 0.35, atan2(target_dir.x, target_dir.z))
				return Vector3.ZERO
			var want := 4.5
			var radial: Vector3 = to.normalized() * clamp(d - want, -1.0, 1.0)
			var side := to.normalized().cross(Vector3.UP) * _strafe * 0.7
			if randf() < delta * 0.3:
				_strafe = -_strafe
			return (radial + side).normalized() * _chase_speed()
		"windup":
			face_toward(target_dir, delta, 30.0)
			if state_t > 0.7:
				set_state("attack")
				rig.play("lunge", 0.45)
				Au.sfx("sfx_dash", -6.0, 0.1, 0.8)
			return Vector3.ZERO
		"attack":
			_melee(global_position + target_dir * 0.5, 1.1, dmg, 5.0)
			if state_t > 0.45:
				set_state("recover")
				cooldown = randf_range(1.6, 2.4)
				_clear_tele()
			return target_dir * 13.0
		"recover":
			if state_t > 0.8:
				set_state("chase")
	return Vector3.ZERO


# --- Buto Ijo ------------------------------------------------------------------

func _think_buto(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	match state:
		"chase":
			face_toward(to, delta, 4.0)
			if d < atk_range + 1.5 and cooldown <= 0.0:
				set_state("windup")
				target_dir = to.normalized()
				rig.play("windup", 0.95)
				_telegraph(global_position + target_dir * 2.2, 2.8, 0.95)
				Au.sfx("sfx_boss_roar", -12.0, 0.1, 1.5)
				return Vector3.ZERO
			return to.normalized() * _chase_speed()
		"windup":
			if state_t > 0.95:
				set_state("attack")
				rig.play("slam", 0.5)
		"attack":
			if state_t > 0.14 and not _hit_this_attack:
				var c := global_position + target_dir * 2.2
				Fx.shock(c, 3.0, Color(0.9, 0.7, 0.4), 0.4)
				Au.sfx("sfx_slam", 0.0, 0.05, 0.8)
				G.main.shake(0.3)
				_clear_tele()
				if not _melee(c, 2.8, dmg, 7.0):
					_hit_this_attack = true
			if state_t > 0.5:
				set_state("recover")
				cooldown = randf_range(1.5, 2.5)
		"recover":
			if state_t > 0.9:
				set_state("chase")
	return Vector3.ZERO


# --- Banaspati -----------------------------------------------------------------

func _think_banaspati(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	face_toward(to, delta, 6.0)
	match state:
		"chase":
			if cooldown <= 0.0 and d < 12.0:
				set_state("windup")
				rig.play("bite", 0.5)
				Fx.burst(global_position + Vector3(0, 1.3, 0), Color(1, 0.5, 0.1), 12, 2.0, 0.2, 0.5)
				return Vector3.ZERO
			if _wander == Vector3.ZERO or randf() < delta * 0.8:
				_wander = Vector3(randf_range(-1, 1), 0, randf_range(-1, 1)).normalized()
			var radial: Vector3 = to.normalized() * clamp(d - 7.0, -1.0, 1.0)
			return (radial + _wander * 0.8).normalized() * _chase_speed()
		"windup":
			if state_t > 0.5:
				var dir := to.normalized()
				var p := Projectile.spawn(global_position + dir * 0.8, dir, 9.5, "enemy", dmg, Color(1.0, 0.45, 0.1), 0.3)
				p.height = 1.2
				p.life = 2.2
				Au.sfx("sfx_fireball", -6.0)
				set_state("recover")
				cooldown = randf_range(2.0, 3.0)
		"recover":
			if state_t > 0.6:
				set_state("chase")
	return Vector3.ZERO


# --- Yuyu Kangkang ---------------------------------------------------------------

func _think_yuyu(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	match state:
		"chase":
			face_toward(to, delta, 5.0)
			if rig.action == "":
				rig.play("guard", 0.2)
			if d < atk_range + 1.0 and cooldown <= 0.0:
				set_state("windup")
				target_dir = to.normalized()
				rig.play("windup", 0.6)
				_telegraph(global_position + target_dir * 1.4, 1.8, 0.6)
				return Vector3.ZERO
			var side := to.normalized().cross(Vector3.UP) * _strafe
			return (to.normalized() * 0.7 + side * 0.6).normalized() * _chase_speed()
		"windup":
			if state_t > 0.6:
				set_state("attack")
				rig.play("snap", 0.35)
				Au.sfx("sfx_croc_snap", -4.0, 0.1, 1.3)
		"attack":
			_melee(global_position + target_dir * 1.4, 1.8, dmg, 5.0)
			if state_t > 0.35:
				_clear_tele()
				set_state("recover")
				cooldown = randf_range(1.2, 2.0)
		"recover":
			if state_t > 0.7:
				set_state("chase")
	return Vector3.ZERO


func take_hit(amount: float, from: Vector3, knockback := 3.0, info := {}) -> float:
	if kind == "yuyu" and bound_t <= 0.0 and state != "recover":
		var dir := from - global_position
		dir.y = 0
		if dir.length() > 0.01 and facing.angle_to(dir) < 0.9:
			Fx.text(global_position, "Tangkis!", Color(0.8, 0.8, 0.9))
			Au.sfx("sfx_hit_heavy", -8.0, 0.1, 1.6)
			return super.take_hit(amount * 0.25, from, knockback * 0.3, info)
	return super.take_hit(amount, from, knockback, info)


func die() -> void:
	_clear_tele()
	super.die()
