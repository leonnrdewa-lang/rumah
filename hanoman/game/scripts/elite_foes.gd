class_name AlengkaFoe
extends Enemy
## Rahwana's soldiers that join the fight from the estuary onward:
##   pemanah  archer: keeps its distance, aims a red line, then looses an arrow
##   dukun    sorcerer: summons Wil from purple circles and blinks away when cornered
##   tameng   shield-bearer: a great shield blocks every blow from the front

const FOES := {
	"pemanah": {"hp": 40, "speed": 3.6, "r": 0.5, "h": 1.8, "model": "cakil", "scale": 1.0, "tint": Color(1.0, 0.45, 0.35), "range": 11.0, "dmg": 9},
	"dukun": {"hp": 55, "speed": 3.0, "r": 0.5, "h": 1.5, "model": "wil", "scale": 1.35, "tint": Color(0.75, 0.4, 1.0), "range": 9.0, "dmg": 6},
	"tameng": {"hp": 110, "speed": 2.8, "r": 0.8, "h": 2.0, "model": "cakil", "scale": 1.2, "tint": Color(0.5, 0.75, 1.0), "range": 1.9, "dmg": 12},
}

var _shield: Node3D
var _summons := 0


static func is_foe(k: String) -> bool:
	return FOES.has(k)


func setup(p_kind: String, depth := 0) -> void:
	kind = p_kind
	var s: Dictionary = FOES[kind]
	max_hp = float(s.hp) * (1.0 + depth * 0.06)
	hp = max_hp
	move_speed = s.speed
	dmg = s.dmg
	atk_range = s.range
	setup_body(s.r, s.h, L_ENEMY, L_WORLD | L_ENEMY | L_PLAYER)
	set_model(s.model, "biped", s.scale)
	Art.set_param(model, "flash_color", s.tint)
	_strafe = 1.0 if randf() < 0.5 else -1.0
	cooldown = randf_range(0.6, 1.6)
	apply_vows()
	match kind:
		"pemanah":
			_add_bow()
		"tameng":
			knock_resist = 0.6
			_add_shield()
		"dukun":
			var orb := Fx.orb(Color(0.75, 0.4, 1.0), 0.22)
			orb.position = Vector3(0.5, 1.9, 0.2)
			model.add_child(orb)


func _ready() -> void:
	super._ready()
	# a faint permanent tint so the new soldiers read differently from the forest raksasa
	Art.set_param(model, "flash", 0.18)


func tick_status(delta: float) -> void:
	super.tick_status(delta)
	if _flash <= 0.0:
		Art.set_param(model, "flash", 0.18)


func _make_bar() -> void:
	super._make_bar()
	_bar.position.y = float(FOES[kind].h) + 0.6


func think(delta: float) -> Vector3:
	match kind:
		"pemanah":
			return _think_archer(delta)
		"dukun":
			return _think_dukun(delta)
		"tameng":
			return _think_shield(delta)
	return Vector3.ZERO


# --- archer --------------------------------------------------------------------------

func _think_archer(delta: float) -> Vector3:
	var to := to_player()
	var dist := to.length()
	match state:
		"chase":
			face_toward(to, delta, 8.0)
			if cooldown <= 0.0 and dist < atk_range:
				set_state("windup")
				target_dir = to.normalized()
				_telegraph(global_position, 13.0, 0.9, 0.12, atan2(target_dir.x, target_dir.z))
				Au.sfx("sfx_staff_draw", -8.0, 0.1, 1.3)
				return Vector3.ZERO
			if dist < 6.0:
				return -to.normalized() * move_speed
			if dist > atk_range - 1.0:
				return to.normalized() * move_speed
			return to.normalized().cross(Vector3.UP) * move_speed * 0.5 * _strafe
		"windup":
			if state_t > 0.9:
				_clear_tele()
				var p := Projectile.spawn(global_position + target_dir * 0.7, target_dir, 18.0, "enemy", dmg, Color(1.0, 0.5, 0.35), 0.16)
				p.life = 1.4
				Au.sfx("sfx_swing1", -6.0, 0.1, 1.5)
				set_state("recover")
		"recover":
			if state_t > 0.6:
				set_state("chase")
				cooldown = randf_range(1.6, 2.6)
	return Vector3.ZERO


# --- sorcerer -------------------------------------------------------------------------

func _think_dukun(delta: float) -> Vector3:
	var to := to_player()
	var dist := to.length()
	match state:
		"chase":
			face_toward(to, delta, 6.0)
			if dist < 3.0 and cooldown <= 1.0:
				_blink_away()
				return Vector3.ZERO
			if cooldown <= 0.0 and _summons < 4:
				set_state("windup")
				rig.play("cast", 1.0)
				Fx.magic_circle(global_position, 1.6, Color(0.75, 0.4, 1.0), 1.0, 3.0)
				Au.sfx("sfx_cast", -6.0, 0.1, 0.8)
				return Vector3.ZERO
			if dist < 7.0:
				return -to.normalized() * move_speed
			return to.normalized().cross(Vector3.UP) * move_speed * 0.6 * _strafe
		"windup":
			if state_t > 1.0:
				for k in 2:
					var off := Vector3(randf_range(-2.5, 2.5), 0, randf_range(-2.5, 2.5))
					var pos: Vector3 = G.main.clamp_to_room(global_position + off, 1.5)
					Fx.magic_circle(pos, 1.2, Color(0.75, 0.4, 1.0), 0.8, 3.0)
					var w := Enemy.new()
					w.setup("wil", 0)
					w.max_hp *= 0.7
					w.hp = w.max_hp
					G.main.spawn_actor(w, pos)
					if G.main.room:
						G.main.room.alive.append(w)
					_summons += 1
				set_state("recover")
		"recover":
			if state_t > 0.8:
				set_state("chase")
				cooldown = randf_range(4.5, 6.5)
	return Vector3.ZERO


func _blink_away() -> void:
	cooldown = 2.5
	var pl: Vector3 = player().global_position
	var a := randf() * TAU
	Fx.smoke(global_position + Vector3(0, 1, 0), 2.0, Color(0.6, 0.3, 0.9))
	global_position = G.main.clamp_to_room(pl + Vector3(cos(a), 0, sin(a)) * 8.0, 1.5)
	Fx.smoke(global_position + Vector3(0, 1, 0), 2.0, Color(0.6, 0.3, 0.9))
	Au.sfx("sfx_dash", -6.0, 0.1, 0.7)


# --- shield-bearer ---------------------------------------------------------------------

func _think_shield(delta: float) -> Vector3:
	var to := to_player()
	var dist := to.length()
	match state:
		"chase":
			face_toward(to, delta, 2.2)
			if cooldown <= 0.0 and dist < atk_range + 0.8:
				set_state("windup")
				target_dir = to.normalized()
				_telegraph(global_position + target_dir * 1.4, 1.6, 0.6)
				rig.play("windup", 0.6)
				return Vector3.ZERO
			return to.normalized() * move_speed
		"windup":
			if state_t > 0.6:
				_clear_tele()
				_melee(global_position + target_dir * 1.4, 1.6, dmg, 8.0)
				Fx.impact(global_position + target_dir * 1.4 + Vector3(0, 0.8, 0), Color(0.6, 0.8, 1.0), true)
				Au.sfx("sfx_rock_hit", -3.0, 0.1)
				set_state("recover")
		"recover":
			if state_t > 1.0:
				set_state("chase")
				cooldown = randf_range(1.0, 1.8)
	return Vector3.ZERO


func take_hit(amount: float, from: Vector3, knockback := 3.0, info := {}) -> float:
	if kind == "tameng" and bound_t <= 0.0 and state != "recover":
		var dir := from - global_position
		dir.y = 0
		if dir.length() > 0.01 and facing.angle_to(dir) < 1.0:
			Fx.text(global_position, "Blocked!", Color(0.7, 0.85, 1.0))
			Fx.sparks(global_position + dir.normalized() * radius + Vector3(0, 1.0, 0), Color(0.7, 0.9, 1.0), 10, 6.0, dir)
			Au.sfx("sfx_rock_hit", -6.0, 0.1, 1.5)
			return super.take_hit(amount * 0.15, from, knockback * 0.3, info)
	return super.take_hit(amount, from, knockback, info)


# --- props ---------------------------------------------------------------------------

func _add_bow() -> void:
	var bow := MeshInstance3D.new()
	var t := TorusMesh.new()
	t.inner_radius = 0.48
	t.outer_radius = 0.54
	t.rings = 16
	t.ring_segments = 6
	bow.mesh = t
	bow.material_override = Art.toon(Color("6b3a1f"), 0.0, 1.6, true)
	bow.position = Vector3(-0.45, 1.1, 0.25)
	bow.rotation = Vector3(0, 0, PI / 2)
	bow.scale = Vector3(1.0, 1.0, 0.35)
	model.add_child(bow)


func _add_shield() -> void:
	_shield = MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = 0.75
	c.bottom_radius = 0.75
	c.height = 0.12
	c.radial_segments = 18
	(_shield as MeshInstance3D).mesh = c
	(_shield as MeshInstance3D).material_override = Art.toon(Color("8a6a2a"), 0.0, 1.6, true)
	_shield.position = Vector3(0, 1.0, 0.7)
	_shield.rotation = Vector3(PI / 2, 0, 0)
	model.add_child(_shield)
	var boss := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.18
	s.height = 0.2
	boss.mesh = s
	boss.material_override = Art.toon(Color("e8b23a"), 0.3, 1.6, true)
	boss.position = Vector3(0, 0.08, 0)
	_shield.add_child(boss)
