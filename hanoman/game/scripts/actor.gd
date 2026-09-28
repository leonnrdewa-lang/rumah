class_name Actor
extends CharacterBody3D
## Shared body for Hanoman and every enemy: health, status effects from the
## gods' boons (Bakar = burn, Basah = wet/slow, Terikat = bound in Ajian circle,
## Setrum = lightning mark), knockback, hit flash and facing.

signal died(actor: Actor)

const L_WORLD := 1
const L_PLAYER := 2
const L_ENEMY := 4

var hp := 10.0
var max_hp := 10.0
var radius := 0.5
var team := "enemy"
var model: Node3D
var rig: Rig
var dead := false
var invuln := 0.0
var knock := Vector3.ZERO
var knock_resist := 0.0
var heavy := false           # bosses: no hitstun, reduced knockback
var move_speed := 4.0
var facing := Vector3(0, 0, 1)
var stagger := 0.0

var burn_t := 0.0
var burn_dps := 0.0
var wet_t := 0.0
var wet_slow := 0.0
var bound_t := 0.0
var _flash := 0.0
var _burn_tick := 0.0
var _fx_burn: CPUParticles3D


func setup_body(r: float, h: float, layer: int, mask: int) -> void:
	radius = r
	var cs := CollisionShape3D.new()
	var cap := CylinderShape3D.new()
	cap.radius = r
	cap.height = h
	cs.shape = cap
	cs.position.y = h * 0.5
	add_child(cs)
	collision_layer = layer
	collision_mask = mask
	motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	wall_min_slide_angle = 0.0


func set_model(id: String, style := "biped", scale_f := 1.0) -> void:
	model = Art.model(id, true)
	model.scale = Vector3.ONE * scale_f
	add_child(model)
	rig = Rig.new(model, style)


func slow_factor() -> float:
	var f := 1.0
	if wet_t > 0.0:
		f *= 1.0 - wet_slow
	if bound_t > 0.0:
		f *= 0.3
	return f


func face_toward(dir: Vector3, delta: float, rate := 14.0) -> void:
	dir.y = 0
	if dir.length_squared() < 0.0001:
		return
	facing = dir.normalized()
	if model:
		var target := atan2(facing.x, facing.z)
		model.rotation.y = lerp_angle(model.rotation.y, target, clamp(delta * rate, 0.0, 1.0))


func snap_face(dir: Vector3) -> void:
	dir.y = 0
	if dir.length_squared() < 0.0001:
		return
	facing = dir.normalized()
	if model:
		model.rotation.y = atan2(facing.x, facing.z)


## Returns the damage actually dealt.
func take_hit(dmg: float, from: Vector3, knockback := 3.0, info := {}) -> float:
	if dead or invuln > 0.0:
		return 0.0
	var mult := 1.0
	if team == "enemy":
		mult *= G.main.player.damage_taken_mult(self)
	var d := dmg * mult
	if info.get("crit", false):
		d *= 3.0
	hp -= d
	_flash = 1.0
	if rig:
		rig.hit()
	var away := global_position - from
	away.y = 0
	if away.length_squared() > 0.0001:
		knock += away.normalized() * knockback * (1.0 - knock_resist)
	if not heavy:
		stagger = max(stagger, 0.18)
	var col := Color(1, 0.95, 0.8)
	if info.has("color"):
		col = info.color
	if team == "enemy":
		Fx.number(global_position, d, col, info.get("crit", false))
	on_hurt(d, info)
	if hp <= 0.0:
		hp = 0.0
		die()
	return d


func on_hurt(_d: float, _info: Dictionary) -> void:
	pass


func apply_burn(dps: float, time := 4.0) -> void:
	burn_dps = max(burn_dps, dps)
	burn_t = max(burn_t, time)


func apply_wet(slow: float, time := 3.0) -> void:
	wet_slow = max(wet_slow, slow)
	wet_t = max(wet_t, time)


func apply_bound(time: float) -> void:
	bound_t = max(bound_t, time)


func die() -> void:
	if dead:
		return
	dead = true
	collision_layer = 0
	collision_mask = 0
	died.emit(self)
	on_death()


func on_death() -> void:
	Au.sfx("sfx_enemy_die", -2.0)
	Fx.burst(global_position + Vector3(0, 0.8, 0), Color(0.9, 0.3, 0.5), 22, 6.0, 0.2, 0.6)
	var tw := create_tween()
	tw.tween_method(func(v): Art.set_param(model, "fade", v), 1.0, 0.0, 0.5)
	tw.tween_callback(queue_free)


## Status effects, flash and knockback decay; call from _physics_process.
func tick_status(delta: float) -> void:
	invuln = max(0.0, invuln - delta)
	stagger = max(0.0, stagger - delta)
	if _flash > 0.0:
		_flash = max(0.0, _flash - delta * 6.0)
		Art.set_param(model, "flash", _flash * 0.8)
	knock = knock.move_toward(Vector3.ZERO, delta * 22.0)
	wet_t = max(0.0, wet_t - delta)
	bound_t = max(0.0, bound_t - delta)
	if burn_t > 0.0:
		burn_t -= delta
		_burn_tick += delta
		if _fx_burn == null:
			_fx_burn = Fx.trail(Color(1.0, 0.5, 0.15), 0.25)
			_fx_burn.position.y = 1.0
			add_child(_fx_burn)
		if _burn_tick >= 0.5:
			_burn_tick = 0.0
			if not dead:
				hp -= burn_dps * 0.5
				Fx.number(global_position, burn_dps * 0.5, Color(1, 0.6, 0.2))
				if hp <= 0.0:
					die()
		if burn_t <= 0.0:
			burn_dps = 0.0
			if _fx_burn:
				_fx_burn.queue_free()
				_fx_burn = null
