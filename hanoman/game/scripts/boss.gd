class_name Boss
extends Enemy
## Mini-boss Kijang Kencana (the golden deer — Kala Marica in disguise) and the
## river-mouth guardians Sura (shark) and Baya (crocodile). Sura and Baya are old
## enemies: their attacks also hurt each other, so luring one into the other's
## strike is the intended trick.

signal phase_changed

var boss_name := ""
var boss_title := ""
var phase := 1
var clone := false
var rival: Boss
var submerged := false
var combo_left := 0
var _fin: Node3D
var _next_attack := ""
var _tele_pos := Vector3.ZERO
var _spawn_t := 0.0


func setup_boss(p_kind: String) -> void:
	kind = p_kind
	heavy = true
	knock_resist = 0.85
	match kind:
		"kijang":
			boss_name = "Kijang Kencana"
			boss_title = "Kala Marica in disguise"
			max_hp = 460.0 if not clone else 1.0
			move_speed = 6.5
			dmg = 12
			setup_body(0.8, 1.6, L_ENEMY, L_WORLD | L_ENEMY | L_PLAYER)
			set_model("kijang", "quad")
			if clone:
				Art.set_param(model, "glow", 0.4)
		"sura":
			boss_name = "Sura"
			boss_title = "Shark King of the Southern Sea"
			max_hp = 820.0
			move_speed = 5.0
			dmg = 16
			setup_body(1.4, 2.0, L_ENEMY, L_WORLD | L_PLAYER)
			set_model("sura", "fish")
		"baya":
			boss_name = "Baya"
			boss_title = "Crocodile King of Kali Mas"
			max_hp = 900.0
			move_speed = 3.2
			dmg = 15
			setup_body(1.5, 2.0, L_ENEMY, L_WORLD | L_PLAYER)
			set_model("baya", "quad")
	if G.run.get("heat", {}).has("kings") and not clone:
		max_hp *= 1.5
		dmg *= 1.25
	hp = max_hp
	cooldown = 1.2


func _make_bar() -> void:
	if clone:
		super._make_bar()


func _ready() -> void:
	add_to_group("enemy")
	if clone:
		super._ready()
		return
	add_to_group("boss")
	G.unlock_codex(kind)
	if kind == "sura" or kind == "baya":
		G.unlock_codex("surabaya")
	invuln = 1.0
	state = "intro"
	state_t = 0.0
	if rig:
		rig.play("roar", 1.2)


func think(delta: float) -> Vector3:
	if state == "intro":
		if state_t > 1.3:
			set_state("chase")
		return Vector3.ZERO
	match kind:
		"kijang":
			return _kijang(delta)
		"sura":
			return _sura(delta)
		"baya":
			return _baya(delta)
	return Vector3.ZERO


## Hits from a boss also land on its rival (Sura <-> Baya).
func _boss_melee(center: Vector3, r: float, amount: float, kb := 6.0) -> void:
	_melee(center, r, amount, kb)
	if rival and is_instance_valid(rival) and not rival.dead and not rival.submerged:
		var d := Vector2(rival.global_position.x - center.x, rival.global_position.z - center.z).length()
		if d < r + rival.radius and not rival.has_meta("hit_by_%d" % get_instance_id()):
			rival.set_meta("hit_by_%d" % get_instance_id(), true)
			rival.take_hit(amount * 3.0, global_position, 2.0, {"color": Color(1, 0.6, 0.2)})
			Fx.text(rival.global_position, "%s attacks %s!" % [boss_name, rival.boss_name], Color(1, 0.7, 0.3))
			get_tree().create_timer(0.6).timeout.connect(func():
				if is_instance_valid(rival): rival.remove_meta("hit_by_%d" % get_instance_id()))


# --- Kijang Kencana ---------------------------------------------------------------

func _kijang(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	if phase == 1 and hp < max_hp * 0.5 and not clone:
		_transform()
		return Vector3.ZERO
	match state:
		"chase":
			face_toward(to, delta, 8.0)
			if cooldown <= 0.0:
				var r := randf()
				if phase == 2 and r < 0.45:
					_next_attack = "slam"
					set_state("windup")
					target_dir = to.normalized()
					rig.play("rear", 0.9)
					_telegraph(global_position + target_dir * 2.5, 3.2, 0.9)
					Au.sfx("sfx_boss_roar", -6.0)
				elif r < 0.25 and not clone and phase == 1:
					_summon_clones()
					cooldown = 1.0
				else:
					_next_attack = "charge"
					combo_left = 2 if phase == 1 else 3
					_begin_charge()
				return Vector3.ZERO
			# prance in a circle around Hanoman
			var tangent := to.normalized().cross(Vector3.UP) * _strafe
			var radial: Vector3 = to.normalized() * clamp(d - 6.0, -1.0, 1.0)
			return (tangent + radial * 0.8).normalized() * move_speed * (0.7 if phase == 1 else 0.5)
		"windup":
			face_toward(target_dir, delta, 20.0)
			var wt := 0.6 if _next_attack == "charge" else 0.9
			if state_t > wt:
				set_state("attack")
				if _next_attack == "charge":
					rig.play("charge", 0.55)
					Au.sfx("sfx_enemy_dash", -1.0, 0.1, 0.8)
					Fx.dust(global_position, 1.2, Color(1.0, 0.85, 0.5))
				else:
					rig.play("slam", 0.5)
		"attack":
			if _next_attack == "charge":
				_boss_melee(global_position + target_dir * 0.8, 1.3, dmg, 7.0)
				if Engine.get_physics_frames() % 2 == 0:
					var gold := Color(1.0, 0.82, 0.3) if phase == 1 else Color(0.5, 1.0, 0.45)
					Fx.sparks(global_position + Vector3(0, 0.9, 0), gold, 5, 3.5, -target_dir + Vector3.UP * 0.5)
					Fx.sprite("shards", global_position + Vector3(0, 0.9, 0), 1.6, gold, 0.3, {"from": 0.6, "grow": 1.0, "tint": 0.5})
				if state_t > 0.55:
					_clear_tele()
					combo_left -= 1
					if combo_left > 0 and not dead:
						_begin_charge()
					else:
						set_state("recover")
						cooldown = randf_range(1.0, 1.8)
				return target_dir * 17.0
			else:
				if state_t > 0.2 and not _hit_this_attack:
					var c := global_position + target_dir * 2.5
					Fx.shock(c, 3.6, Color(0.6, 1.0, 0.5), 0.45, true)
					Fx.impact(c + Vector3(0, 0.5, 0), Color(0.6, 1.0, 0.5), true)
					Au.sfx("sfx_enemy_slam", 0.0, 0.05, 0.9)
					G.main.shake(0.45)
					G.main.flash(Color(0.6, 1.0, 0.5), 0.12, 0.15)
					_clear_tele()
					_boss_melee(c, 3.2, dmg + 4, 8.0)
					_hit_this_attack = true
					for k in 5:
						var a := atan2(target_dir.x, target_dir.z) + (k - 2) * 0.35
						var dir := Vector3(sin(a), 0, cos(a))
						var p := Projectile.spawn(c, dir, 8.0, "enemy", 8.0, Color(0.5, 1.0, 0.4), 0.3)
						p.life = 2.0
				if state_t > 0.6:
					set_state("recover")
					cooldown = randf_range(1.2, 2.0)
		"recover":
			if state_t > (0.6 if phase == 2 else 0.8):
				set_state("chase")
				if randf() < 0.5:
					_strafe = -_strafe
	return Vector3.ZERO


func _begin_charge() -> void:
	set_state("windup")
	var to := to_player()
	target_dir = to.normalized()
	rig.play("rear", 0.6)
	_telegraph(global_position, 9.5, 0.6, 0.3, atan2(target_dir.x, target_dir.z))


func _summon_clones() -> void:
	G.say("Kijang Kencana splits apart!", Color(1, 0.85, 0.4))
	Au.sfx("sfx_boon", -3.0, 0.0, 0.8)
	Fx.magic_circle(global_position, 3.0, Color(1.0, 0.82, 0.3), 1.0, 3.0)
	Fx.sprite("shards", global_position + Vector3(0, 1.2, 0), 4.0, Color(1.0, 0.85, 0.4), 0.5, {"from": 0.3, "grow": 1.3})
	for k in 2:
		var c := Boss.new()
		c.clone = true
		c.setup_boss("kijang")
		c.max_hp = 1.0
		c.hp = 1.0
		var off := Vector3(randf_range(-4, 4), 0, randf_range(-4, 4))
		G.main.spawn_actor(c, G.main.clamp_to_room(global_position + off, 2.0))
		Fx.smoke(c.global_position + Vector3(0, 1.0, 0), 2.4, Color(1.0, 0.8, 0.4))
		c.set_meta("no_count", false)
		get_tree().create_timer(9.0).timeout.connect(func():
			if is_instance_valid(c) and not c.dead: c.die())


func _transform() -> void:
	phase = 2
	set_state("recover")
	state_t = -1.2
	invuln = 1.4
	boss_name = "Kala Marica"
	boss_title = "The demon behind Kijang Kencana"
	G.say("Kijang Kencana reveals its true form: Kala Marica!", Color(0.6, 1.0, 0.5))
	Au.sfx("sfx_roar", 0.0, 0.0, 0.8)
	Au.sfx("sfx_lightning", -2.0)
	G.main.shake(0.7)
	G.main.flash(Color(0.6, 1.0, 0.5), 0.35, 0.4)
	Fx.lightning(global_position, 10.0, Color(0.6, 1.0, 0.5))
	Fx.magic_circle(global_position, 4.0, Color(0.5, 1.0, 0.45), 1.6, 2.5)
	Fx.smoke(global_position + Vector3(0, 1.5, 0), 5.0, Color(0.3, 0.7, 0.3))
	Fx.burst(global_position + Vector3(0, 1.5, 0), Color(0.4, 1.0, 0.4), 30, 7.0, 0.3, 0.8)
	var old := model
	var new_id := "kijang_raksasa" if Art.has_model("kijang_raksasa") else "kijang"
	model = Art.model(new_id, true)
	add_child(model)
	model.rotation.y = old.rotation.y
	if new_id == "kijang":
		model.scale = Vector3.ONE * 1.35
	old.queue_free()
	rig = Art.make_rig(model, "biped" if new_id == "kijang_raksasa" else "quad")
	rig.play("roar", 1.2)
	move_speed = 5.5
	phase_changed.emit()


# --- Sura --------------------------------------------------------------------------

func _set_submerged(on: bool) -> void:
	submerged = on
	if on:
		collision_layer = 0
		collision_mask = 0
		invuln = 999.0
		var tw := create_tween()
		tw.tween_property(model, "position:y", -2.6, 0.35)
		if _fin == null:
			_fin = Fx.trail(Color(0.7, 0.95, 1.0), 0.45)
			_fin.position.y = 0.1
			add_child(_fin)
		_fin.emitting = true
		Au.sfx("sfx_shark_splash", -2.0)
		Fx.splash(global_position, 3.5)
	else:
		collision_layer = L_ENEMY
		collision_mask = L_WORLD | L_PLAYER
		invuln = 0.0
		if _fin:
			_fin.emitting = false
		create_tween().tween_property(model, "position:y", 0.0, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		Au.sfx("sfx_geyser", 0.0, 0.05)
		Fx.splash(global_position, 5.0)
		Fx.sprite("splash", global_position + Vector3(0, 2.2, 0), 4.5, Color(0.6, 0.9, 1.0), 0.6, {"billboard": 2.0, "stretch": Vector2(0.8, 1.6), "from": 0.3, "grow": 1.1, "tint": 0.2})


func _sura(delta: float) -> Vector3:
	var to := to_player()
	var enraged := rival == null or not is_instance_valid(rival) or rival.dead
	match state:
		"chase":
			if cooldown <= 0.0:
				if randf() < 0.65:
					set_state("dive")
					_set_submerged(true)
				else:
					set_state("windup")
					_next_attack = "wave"
					target_dir = to.normalized()
					rig.play("rear", 0.8)
				return Vector3.ZERO
			face_toward(to, delta, 5.0)
			if to.length() < 3.8 and randf() < delta * 1.5:
				_next_attack = "bite"
				target_dir = to.normalized()
				set_state("windup")
				rig.play("rear", 0.55)
				_telegraph(global_position + target_dir * 2.2, 2.2, 0.55)
				return Vector3.ZERO
			return to.normalized() * move_speed * 0.6
		"dive":
			# glide under the deck toward Hanoman, then mark the spot
			var spd := move_speed * (2.2 if enraged else 1.7)
			face_toward(to, delta, 8.0)
			if state_t > 1.4 or to.length() < 1.0:
				set_state("marked")
				_tele_pos = G.main.clamp_to_room(player().global_position, 1.5)
				_telegraph(_tele_pos, 2.6, 0.85)
				return Vector3.ZERO
			global_position += to.normalized() * spd * delta
			return Vector3.ZERO
		"marked":
			if state_t > 0.85:
				global_position = Vector3(_tele_pos.x, 0, _tele_pos.z)
				_set_submerged(false)
				rig.play("bite", 0.5)
				_clear_tele()
				Fx.shock(_tele_pos, 3.2, Color(0.6, 0.9, 1.0), 0.5, true)
				Au.sfx("sfx_bite", 0.0, 0.05, 0.8)
				G.main.shake(0.5)
				G.main.flash(Color(0.6, 0.9, 1.0), 0.15, 0.2)
				_hit_this_attack = false
				_boss_melee(_tele_pos, 2.6, dmg, 9.0)
				set_state("surfaced")
				combo_left = 2
		"surfaced":
			face_toward(to, delta, 6.0)
			if state_t > (1.6 if enraged else 2.4):
				set_state("chase")
				cooldown = randf_range(0.5, 1.2)
			return to.normalized() * move_speed * 0.35
		"windup":
			if state_t > (0.55 if _next_attack == "bite" else 0.8):
				set_state("attack")
				if _next_attack == "bite":
					rig.play("bite", 0.4)
					Au.sfx("sfx_bite", 0.0, 0.1, 0.8)
					Fx.impact(global_position + target_dir * 2.2 + Vector3(0, 0.8, 0), Color(0.6, 0.9, 1.0), true)
				else:
					Au.sfx("sfx_geyser", -2.0, 0.1, 1.1)
					Fx.splash(global_position + target_dir * 1.5, 3.0)
					for k in 5:
						var a := atan2(target_dir.x, target_dir.z) + (k - 2) * 0.28
						var dir := Vector3(sin(a), 0, cos(a))
						var p := Projectile.spawn(global_position + dir * 1.5, dir, 10.0, "enemy", 9.0, Color(0.4, 0.8, 1.0), 0.45, "splash")
						p.life = 2.0
						p.on_hit = func(t: Actor, _pr): t.knock += dir * 6.0
		"attack":
			if _next_attack == "bite":
				_boss_melee(global_position + target_dir * 2.2, 2.2, dmg, 8.0)
			if state_t > 0.45:
				_clear_tele()
				set_state("recover")
				cooldown = randf_range(1.0, 2.0) * (0.7 if enraged else 1.0)
		"recover":
			if state_t > 0.6:
				set_state("chase")
	return Vector3.ZERO


# --- Baya --------------------------------------------------------------------------

func _baya(delta: float) -> Vector3:
	var to := to_player()
	var d := to.length()
	var enraged := rival == null or not is_instance_valid(rival) or rival.dead
	match state:
		"chase":
			face_toward(to, delta, 3.5)
			if cooldown <= 0.0:
				var r := randf()
				target_dir = to.normalized()
				set_state("windup")
				if d < 4.0 and r < 0.45:
					_next_attack = "spin"
					rig.play("rear", 0.85)
					_telegraph(global_position, 4.2, 0.85)
				elif d < 4.5:
					_next_attack = "bite"
					rig.play("rear", 0.5)
					_telegraph(global_position + target_dir * 2.6, 2.4, 0.5)
				else:
					_next_attack = "roll"
					rig.play("rear", 0.8)
					_telegraph(global_position, 11.0, 0.8, 0.35, atan2(target_dir.x, target_dir.z))
					Au.sfx("sfx_boss_roar", -4.0, 0.05, 0.7)
				return Vector3.ZERO
			return to.normalized() * move_speed * (1.3 if enraged else 1.0)
		"windup":
			var wt: float = {"spin": 0.85, "bite": 0.5, "roll": 0.8}[_next_attack]
			if _next_attack != "roll":
				face_toward(to, delta, 2.0)
			if state_t > wt:
				set_state("attack")
				match _next_attack:
					"spin":
						rig.play("spin", 0.6)
						Au.sfx("sfx_tail", 0.0, 0.05)
						Fx.shock(global_position, 4.4, Color(0.55, 0.85, 1.0), 0.5)
						Fx.splash(global_position, 5.0)
						Fx.sprite("wind", global_position + Vector3(0, 0.3, 0), 8.8, Color(0.6, 0.9, 1.0), 0.55, {"flat": true, "from": 0.5, "grow": 1.05, "spin": -7.0, "tint": 0.4})
					"bite":
						rig.play("bite", 0.4)
						Au.sfx("sfx_bite", 0.0)
						Fx.impact(global_position + target_dir * 2.6 + Vector3(0, 0.6, 0), Color(1.0, 0.6, 0.4), true)
					"roll":
						rig.play("charge", 0.9)
						Au.sfx("sfx_enemy_dash", 0.0, 0.05, 0.6)
		"attack":
			match _next_attack:
				"spin":
					if state_t > 0.2:
						_boss_melee(global_position, 4.2, dmg, 10.0)
						if model:
							model.rotation.y += delta * 16.0
				"bite":
					_boss_melee(global_position + target_dir * 2.6, 2.4, dmg + 3, 7.0)
				"roll":
					_boss_melee(global_position + target_dir * 1.2, 1.9, dmg, 9.0)
					if Engine.get_physics_frames() % 4 == 0:
						Fx.splash(global_position, 2.2)
					if state_t < 0.8:
						return target_dir * 14.0
			var len: float = {"spin": 0.65, "bite": 0.4, "roll": 0.85}[_next_attack]
			if state_t > len:
				_clear_tele()
				set_state("recover")
				cooldown = randf_range(1.0, 1.8) * (0.7 if enraged else 1.0)
		"recover":
			if state_t > 0.7:
				set_state("chase")
	return Vector3.ZERO


func on_death() -> void:
	if clone:
		Fx.burst(global_position + Vector3(0, 1, 0), Color(1, 0.85, 0.3), 20, 5.0, 0.2, 0.5)
		queue_free()
		return
	_clear_tele()
	Au.sfx("sfx_roar", 0.0, 0.0, 0.6)
	Au.sfx("sfx_explosion", 0.0)
	G.main.shake(0.8)
	G.main.hitstop(0.25)
	G.main.flash(Color(1, 0.9, 0.7), 0.45, 0.5)
	Fx.shock(global_position, 7.0, Color(1, 0.8, 0.4), 0.7, true)
	Fx.impact(global_position + Vector3(0, 1.5, 0), Color(1, 0.85, 0.5), true)
	Fx.smoke(global_position + Vector3(0, 1.5, 0), 6.0, Color(0.7, 0.5, 0.9))
	Fx.burst(global_position + Vector3(0, 1.5, 0), Color(1, 0.8, 0.4), 40, 9.0, 0.35, 1.0)
	if rival and is_instance_valid(rival) and not rival.dead:
		G.say("%s has fallen! %s goes berserk!" % [boss_name, rival.boss_name], Color(1, 0.6, 0.3))
	var tw := create_tween()
	tw.tween_interval(0.6)
	tw.tween_method(func(v): Art.set_param(model, "fade", v), 1.0, 0.0, 1.0)
	tw.tween_callback(queue_free)
