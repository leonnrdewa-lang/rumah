class_name AlengkaBoss
extends Boss
## The guardians of Alengka.
##   kumbakarna  Rahwana's giant brother: earth-shaking club slams and stomp
##               waves; he dozes off between flurries (snoring, takes double
##               damage) and wakes up furious.
##   indrajit    Rahwana's sorcerer son: Nagapasa serpent arrows that bind,
##               teleports, arrow volleys; below half health he splits into
##               illusions and calls down a rain of arrows.

var _sleep_t := 0.0
var _awake_t := 0.0
var _zzz: Label3D
var _illusions_done := false


func setup_alengka(p_kind: String) -> void:
	kind = p_kind
	heavy = true
	knock_resist = 0.9
	match kind:
		"kumbakarna":
			boss_name = "Kumbakarna"
			boss_title = "The Sleeping Giant of Alengka"
			max_hp = 1300.0
			move_speed = 2.4
			dmg = 20
			setup_body(1.6, 5.0, L_ENEMY, L_WORLD | L_PLAYER)
			set_model("buto_ijo", "biped", 1.9)
			Art.set_param(model, "rim", 1.4)
			_awake_t = 9.0
		"indrajit":
			boss_name = "Indrajit"
			boss_title = "Meghanada, Conqueror of Indra"
			max_hp = 1100.0
			move_speed = 5.2
			dmg = 14
			setup_body(0.55, 1.9, L_ENEMY, L_WORLD | L_PLAYER)
			if Art.has_model("indrajit"):
				set_model("indrajit", "biped")
			else:
				set_model("cakil", "biped", 1.1)
				Art.set_param(model, "glow", 0.25)
	if G.run.get("heat", {}).has("kings"):
		max_hp *= 1.5
		dmg *= 1.25
	hp = max_hp
	cooldown = 1.5


func think(delta: float) -> Vector3:
	if state == "intro":
		if state_t > 1.3:
			set_state("chase")
		return Vector3.ZERO
	if kind == "kumbakarna":
		return _kumbakarna(delta)
	return _indrajit(delta)


func take_hit(amount: float, from: Vector3, knockback := 3.0, info := {}) -> float:
	if kind == "kumbakarna" and state == "sleep":
		amount *= 2.0
		if randf() < 0.3:
			Fx.text(global_position + Vector3(0, 3.0, 0), "Sleeping! x2", Color(0.7, 0.9, 1.0))
	return super.take_hit(amount, from, knockback, info)


# --- Kumbakarna ----------------------------------------------------------------------

func _kumbakarna(delta: float) -> Vector3:
	var to := to_player()
	var dist := to.length()
	match state:
		"chase":
			_awake_t -= delta
			if _awake_t <= 0.0:
				_fall_asleep()
				return Vector3.ZERO
			face_toward(to, delta, 3.0)
			if cooldown <= 0.0:
				if dist < 5.0:
					_next_attack = "slam"
				elif randf() < 0.5:
					_next_attack = "stomp"
				else:
					_next_attack = "leap"
				set_state("windup")
				target_dir = to.normalized()
				match _next_attack:
					"slam":
						_tele_pos = global_position + target_dir * 3.2
						_telegraph(_tele_pos, 3.2, 0.9)
						rig.play("windup", 0.9)
					"stomp":
						_tele_pos = global_position
						_telegraph(global_position, 7.5, 1.1)
						rig.play("roar", 1.1)
						Au.sfx("sfx_roar", -2.0, 0.0, 0.6)
					"leap":
						_tele_pos = G.main.clamp_to_room(player().global_position, 2.0)
						_telegraph(_tele_pos, 3.6, 1.2)
						rig.play("windup", 1.2)
				return Vector3.ZERO
			return to.normalized() * move_speed * (1.4 if phase == 2 else 1.0) if dist > 3.0 else Vector3.ZERO
		"windup":
			var wt: float = {"slam": 0.9, "stomp": 1.1, "leap": 1.2}[_next_attack]
			if _next_attack == "leap" and state_t > 0.5:
				global_position = global_position.lerp(_tele_pos, clampf((state_t - 0.5) / 0.7, 0.0, 1.0) * delta * 6.0)
				if model:
					model.position.y = sin(clampf((state_t - 0.5) / 0.7, 0.0, 1.0) * PI) * 4.0
			if state_t > wt:
				if model:
					model.position.y = 0.0
				_land(_next_attack)
				set_state("recover")
		"recover":
			if state_t > (0.6 if phase == 2 else 1.0):
				set_state("chase")
				cooldown = randf_range(1.2, 2.0)
		"sleep":
			_sleep_t -= delta
			if _zzz and Engine.get_physics_frames() % 50 == 0:
				Fx.text(global_position + Vector3(randf_range(-0.5, 0.5), 3.5, 0), "Z z z", Color(0.7, 0.85, 1.0))
			if _sleep_t <= 0.0:
				_wake_up()
	if phase == 1 and hp < max_hp * 0.5:
		phase = 2
		G.main.ui.phase_banner("Kumbakarna is fully awake!")
		G.main.flash(Color(1.0, 0.5, 0.3), 0.3, 0.5)
		Au.sfx("sfx_boss_roar", 0.0, 0.0, 0.7)
		move_speed *= 1.3
		phase_changed.emit()
	return Vector3.ZERO


func _land(what: String) -> void:
	_clear_tele()
	match what:
		"slam":
			_melee(_tele_pos, 3.2, dmg + 6, 9.0)
			Fx.shock(_tele_pos, 4.2, Color(1.0, 0.7, 0.4), 0.45, true)
			Fx.impact(_tele_pos + Vector3(0, 0.5, 0), Color(1.0, 0.7, 0.4), true)
		"stomp":
			_melee(global_position, 7.5, dmg, 12.0)
			Fx.shock(global_position, 8.0, Color(0.9, 0.6, 0.4), 0.6, true)
			Fx.dust(global_position, 6.0)
		"leap":
			_melee(_tele_pos, 3.6, dmg + 4, 10.0)
			Fx.shock(_tele_pos, 5.0, Color(1.0, 0.6, 0.3), 0.5, true)
	Au.sfx("sfx_enemy_slam", 0.0, 0.05, 0.6)
	G.main.shake(0.6)
	G.vibrate(60)


func _fall_asleep() -> void:
	set_state("sleep")
	_sleep_t = 4.0 if phase == 1 else 2.5
	_clear_tele()
	G.say("Kumbakarna dozes off... strike now!", Color(0.7, 0.9, 1.0))
	_zzz = Label3D.new()
	if model:
		create_tween().tween_property(model, "rotation:x", 0.25, 0.6)


func _wake_up() -> void:
	set_state("recover")
	state_t = -0.4
	_awake_t = randf_range(8.0, 11.0)
	if _zzz:
		_zzz.queue_free()
		_zzz = null
	if model:
		create_tween().tween_property(model, "rotation:x", 0.0, 0.3)
	rig.play("roar", 1.0)
	Au.sfx("sfx_boss_roar", -1.0, 0.0, 0.6)
	G.main.shake(0.5)
	Fx.shock(global_position, 6.0, Color(1.0, 0.5, 0.3), 0.5, true)
	_melee(global_position, 4.0, dmg * 0.6, 12.0)


# --- Indrajit ----------------------------------------------------------------------

func _indrajit(delta: float) -> Vector3:
	var to := to_player()
	var dist := to.length()
	if phase == 1 and hp < max_hp * 0.5:
		phase = 2
		G.main.ui.phase_banner("Indrajit summons his illusions!")
		G.main.flash(Color(0.6, 0.4, 1.0), 0.35, 0.5)
		Au.sfx("sfx_lightning", -1.0)
		_split()
		phase_changed.emit()
	match state:
		"chase":
			face_toward(to, delta, 8.0)
			if cooldown <= 0.0:
				var r := randf()
				if dist < 3.5 or r < 0.2:
					_next_attack = "blink"
				elif r < 0.6:
					_next_attack = "naga"
				else:
					_next_attack = "volley"
				set_state("windup")
				target_dir = to.normalized()
				match _next_attack:
					"naga":
						rig.play("windup", 0.7)
						_telegraph(global_position, 14.0, 0.7, 0.18, atan2(target_dir.x, target_dir.z))
					"volley":
						rig.play("windup", 0.8)
						_telegraph(global_position, 11.0, 0.8, 1.0, atan2(target_dir.x, target_dir.z))
					"blink":
						Fx.smoke(global_position + Vector3(0, 1, 0), 2.2, Color(0.5, 0.3, 0.9))
				return Vector3.ZERO
			# keep a sniper's distance
			var want := 8.0
			if dist < want - 1.0:
				return -to.normalized() * move_speed
			if dist > want + 2.0:
				return to.normalized() * move_speed * 0.8
			return to.normalized().cross(Vector3.UP) * move_speed * 0.6 * _strafe
		"windup":
			face_toward(to, delta, 4.0)
			var wt: float = {"naga": 0.7, "volley": 0.8, "blink": 0.25}[_next_attack]
			if state_t > wt:
				_clear_tele()
				match _next_attack:
					"naga":
						_naga_arrow(target_dir)
					"volley":
						for k in 5:
							_arrow(target_dir.rotated(Vector3.UP, (k - 2) * 0.16), 16.0, dmg * 0.7)
						Au.sfx("sfx_swing2", -3.0, 0.1, 1.4)
					"blink":
						_blink()
				set_state("recover")
		"recover":
			if state_t > (0.5 if phase == 2 else 0.8):
				set_state("chase")
				cooldown = randf_range(0.8, 1.6) * (0.7 if phase == 2 else 1.0)
	if phase == 2 and Engine.get_physics_frames() % 240 == 0:
		_arrow_rain()
	return Vector3.ZERO


func _arrow(dir: Vector3, speed: float, amount: float) -> Projectile:
	var p := Projectile.spawn(global_position + dir * 0.8, dir, speed, "enemy", amount, Color(0.75, 0.45, 1.0), 0.18)
	p.life = 1.6
	return p


## Nagapasa: a serpent arrow that binds Hanoman in place for a moment.
func _naga_arrow(dir: Vector3) -> void:
	var p := _arrow(dir, 20.0, dmg)
	p.color = Color(0.4, 1.0, 0.5)
	p.on_hit = func(target, _proj):
		if target is Player:
			var pl: Player = target
			pl.apply_bound(1.1)
			Fx.text(pl.global_position, "Bound by Nagapasa!", Color(0.5, 1.0, 0.5))
			Fx.magic_circle(pl.global_position, 1.2, Color(0.4, 1.0, 0.5), 1.1, 4.0)
	Au.sfx("sfx_laser", -6.0, 0.05, 1.6)


func _blink() -> void:
	var pl := player().global_position
	var a := randf() * TAU
	var dest: Vector3 = G.main.clamp_to_room(pl + Vector3(cos(a), 0, sin(a)) * 8.0, 2.0)
	Fx.smoke(global_position + Vector3(0, 1, 0), 2.4, Color(0.5, 0.3, 0.9))
	global_position = dest
	Fx.smoke(global_position + Vector3(0, 1, 0), 2.4, Color(0.5, 0.3, 0.9))
	Fx.magic_circle(global_position, 1.6, Color(0.6, 0.4, 1.0), 0.6, 3.0)
	Au.sfx("sfx_dash", -3.0, 0.1, 0.8)


func _split() -> void:
	if _illusions_done:
		return
	_illusions_done = true
	for k in 2:
		var c := AlengkaBoss.new()
		c.clone = true
		c.setup_alengka("indrajit")
		c.max_hp = 40.0
		c.hp = 40.0
		c.dmg = dmg * 0.5
		var a := TAU * k / 2.0 + 0.8
		G.main.spawn_actor(c, G.main.clamp_to_room(global_position + Vector3(cos(a), 0, sin(a)) * 5.0, 2.0))
		if c.model:
			Art.set_param(c.model, "glow", 0.5)
		Fx.smoke(c.global_position + Vector3(0, 1.0, 0), 2.4, Color(0.6, 0.4, 1.0))


func _arrow_rain() -> void:
	var pl := player().global_position
	for k in 4:
		var p: Vector3 = G.main.clamp_to_room(pl + Vector3(randf_range(-4, 4), 0, randf_range(-3, 3)) * (0.0 if k == 0 else 1.0), 1.0)
		Fx.ring(p, 1.6, Color(0.7, 0.45, 1.0), 1.0, true, TAU, 0.0, true)
		var tw := create_tween()
		tw.tween_interval(1.0 + k * 0.1)
		tw.tween_callback(func():
			Fx.sprite("k_trace", p + Vector3(0, 2.0, 0), 3.0, Color(0.7, 0.45, 1.0), 0.25, {"billboard": 2.0, "stretch": Vector2(0.3, 1.6), "tint": 0.4, "intensity": 2.2})
			Fx.impact(p + Vector3(0, 0.3, 0), Color(0.7, 0.45, 1.0))
			var plr: Player = G.main.player
			if plr and not plr.dead and Vector2(plr.global_position.x - p.x, plr.global_position.z - p.z).length() < 1.6 + plr.radius * 0.5:
				plr.take_hit(9.0, p, 4.0))


func on_death() -> void:
	if clone:
		Fx.smoke(global_position + Vector3(0, 1, 0), 2.0, Color(0.6, 0.4, 1.0))
		queue_free()
		return
	# the illusions vanish with their master
	for e in G.main.enemies():
		if e is AlengkaBoss and e.clone and not e.dead:
			e.die()
	super.on_death()
