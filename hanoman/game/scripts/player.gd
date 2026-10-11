class_name Player
extends Actor
## Hanoman: Serang (3-hit tongkat combo ending in a ground slam), Jurus (the
## staff shoots out like a laser, Prana charges), Ajian (Bayu binding circle),
## Lesat (dash with i-frames). The gods' boons hook into each action.

const DASH_SPEED := 21.0
const DASH_TIME := 0.17
const DASH_REGEN := 0.75
const PRANA_REGEN := 1.5
const CAST_COOLDOWN := 8.0
const COMBO := [
	{"anim": "swing_a", "len": 0.3, "hit": 0.11, "dmg": 12.0, "range": 2.6, "arc": 2.6, "lunge": 3.0},
	{"anim": "swing_b", "len": 0.3, "hit": 0.11, "dmg": 12.0, "range": 2.6, "arc": 2.6, "lunge": 3.0},
	{"anim": "slam", "len": 0.52, "hit": 0.25, "dmg": 28.0, "range": 3.0, "arc": 6.3, "lunge": 4.5},
]
const LASER_LEN := 15.0
const LASER_WIDTH := 1.4

var aim := Vector3(0, 0, 1)
var mouse_aim := false
var _mouse_t := -10.0
var combo_i := -1
var atk_t := 0.0
var atk_hit_done := false
var atk_queued := false
var atk_dir := Vector3.FORWARD
var dash_t := 0.0
var dash_dir := Vector3.ZERO
var dash_charges := 1
var dash_regen := 0.0
var prana := 3.0
var cast_cd := 0.0
var special_cd := 0.0
var cast_anim := 0.0
var input_locked := false
var touch_move := Vector2.ZERO
var touch_aim := Vector2.ZERO
var interact_target: Node = null
var _fire_trail_t := 0.0
var _step_t := 0.0
var staff: Staff


func _ready() -> void:
	team = "player"
	setup_body(0.45, 1.6, L_PLAYER, L_WORLD | L_ENEMY)
	set_model("hanoman", "biped")
	staff = Staff.attach(model)
	Weapons.dress(staff)
	move_speed = 7.2
	add_to_group("player")
	reset_for_run()


func reset_for_run() -> void:
	dead = false
	dash_charges = max_dash()
	prana = max_prana()
	cast_cd = 0.0
	collision_layer = L_PLAYER
	collision_mask = L_WORLD | L_ENEMY
	combo_i = -1
	dash_t = 0.0
	cast_anim = 0.0
	invuln = 0.0
	knock = Vector3.ZERO
	velocity = Vector3.ZERO
	if rig:
		rig.revive()
	Weapons.dress(staff)
	if staff:
		staff.visible = true
	if model:
		Art.set_param(model, "fade", 1.0)
		model.visible = true


func max_dash() -> int:
	return int(G.run.get("dash_charges", 1 + G.up_rank("lesat")))


func max_prana() -> int:
	return int(G.run.get("prana_max", 3 + G.up_rank("prana")))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_mouse_t = Time.get_ticks_msec() / 1000.0
		mouse_aim = true


func _physics_process(delta: float) -> void:
	tick_status(delta)
	if dead:
		rig.update(delta, 0.0)
		return
	_regen(delta)
	var mv := Vector3.ZERO
	if not input_locked:
		var v := Input.get_vector("left", "right", "up", "down")
		if touch_move.length() > 0.1:
			v = touch_move
		mv = Vector3(v.x, 0, v.y)
		if mv.length() > 1.0:
			mv = mv.normalized()
		if bound_t > 0.0:
			mv *= 0.15
	_update_aim(mv)
	if not input_locked and G.main.combat_enabled():
		if Input.is_action_just_pressed("dash"):
			try_dash(mv)
		if Input.is_action_just_pressed("attack"):
			try_attack()
		if Input.is_action_just_pressed("special"):
			try_special()
		if Input.is_action_just_pressed("cast"):
			try_cast()
	if not input_locked and Input.is_action_just_pressed("interact"):
		try_interact()
	var speed := move_speed * (1.0 + Boons.val("bayu_pasif") / 100.0)
	if dash_t > 0.0:
		dash_t -= delta
		velocity = dash_dir * DASH_SPEED
		_dash_tick(delta)
		if dash_t <= 0.0:
			_end_dash()
	elif combo_i >= 0:
		_attack_tick(delta)
		var c: Dictionary = _combo()[combo_i]
		var lunge: float = c.lunge if atk_t < c.hit + 0.05 else 0.0
		velocity = atk_dir * lunge + mv * speed * 0.25
	else:
		velocity = mv * speed
		if mv.length() > 0.1:
			face_toward(mv, delta, 18.0)
			_step_t += delta * mv.length()
			if _step_t > 0.3:
				_step_t = 0.0
				# wading: ripples and splashes on the wet estuary / ocean floors
				if G.main.room and G.main.room.biome in Arena.WATERY:
					Fx.sprite("shock", global_position + Vector3(0, 0.05, 0), 1.4, Color(0.6, 0.85, 1.0), 0.6, {"flat": true, "from": 0.2, "grow": 1.0, "tint": 0.5, "intensity": 0.9, "hold": 0.1})
					if randf() < 0.4:
						Fx.splash(global_position, 0.8)
				Au.sfx("sfx_step%d" % randi_range(1, 3), -14.0, 0.1)
	if cast_anim > 0.0:
		cast_anim -= delta
		velocity *= 0.3
	velocity += knock
	velocity.y = 0
	move_and_slide()
	global_position.y = 0.0
	if G.main.room:
		global_position = G.main.room.push_inside(global_position, radius * 0.8)
	rig.update(delta, Vector2(velocity.x, velocity.z).length() if dash_t <= 0.0 else 0.0)
	rig.lean = 0.55 if dash_t > 0.0 else 0.0
	_find_interact()


func _regen(delta: float) -> void:
	if dash_charges < max_dash():
		dash_regen += delta
		if dash_regen >= DASH_REGEN:
			dash_regen = 0.0
			dash_charges += 1
	if prana < max_prana():
		prana = min(float(max_prana()), prana + delta / PRANA_REGEN)
	cast_cd = max(0.0, cast_cd - delta)
	special_cd = max(0.0, special_cd - delta)


func _update_aim(mv: Vector3) -> void:
	var now := Time.get_ticks_msec() / 1000.0
	var cand := Vector3.ZERO
	if touch_aim.length() > 0.3:
		cand = Vector3(touch_aim.x, 0, touch_aim.y)
	elif mouse_aim and now - _mouse_t < 3.0 and not G.touch_mode:
		var gp: Vector3 = G.main.mouse_ground()
		cand = gp - global_position
		cand.y = 0
	if cand.length() < 0.2:
		cand = mv if mv.length() > 0.2 else facing
	aim = cand.normalized() if cand.length() > 0.001 else facing


## Soft auto-aim: nearest enemy inside a cone around `dir` (wider on touch).
func assisted(dir: Vector3, rng := 8.0) -> Vector3:
	var cone := 0.9 if G.touch_mode else 0.45
	var best: Actor = null
	var best_d := rng
	for e in G.main.enemies():
		if e.dead:
			continue
		var to: Vector3 = e.global_position - global_position
		to.y = 0
		var d := to.length()
		if d < best_d and d > 0.01 and dir.angle_to(to) < cone:
			best = e
			best_d = d
	if best:
		var to := best.global_position - global_position
		to.y = 0
		return to.normalized()
	return dir


# --- Serang --------------------------------------------------------------

func try_attack() -> void:
	if dash_t > 0.0:
		atk_queued = true
		return
	if combo_i >= 0:
		atk_queued = true
		return
	_start_swing(0)


func _start_swing(i: int) -> void:
	combo_i = i
	atk_t = 0.0
	atk_hit_done = false
	atk_queued = false
	atk_dir = assisted(aim, 6.0)
	snap_face(atk_dir)
	var c: Dictionary = _combo()[i]
	rig.play(c.anim, c.len)
	Au.sfx("sfx_swing%d" % (i + 1), -3.0 if i < 2 else -1.0, 0.08, 1.0 if i < 2 else 0.85)


func _attack_tick(delta: float) -> void:
	atk_t += delta
	var c: Dictionary = _combo()[combo_i]
	if not atk_hit_done and atk_t >= c.hit:
		atk_hit_done = true
		_swing_hit(combo_i)
	if atk_t >= c.len:
		var next := combo_i + 1
		if atk_queued and next < _combo().size():
			_start_swing(next)
		else:
			combo_i = -1
			if atk_queued:
				_start_swing(0)
	elif atk_queued and atk_t >= c.len * 0.7 and combo_i + 1 < _combo().size():
		_start_swing(combo_i + 1)


func _combo() -> Array:
	return Weapons.COMBOS.get(Weapons.current(), COMBO)


func _swing_hit(i: int) -> void:
	var c: Dictionary = _combo()[i]
	var wpn := Weapons.current()
	if wpn == "panah" or wpn == "cakra":
		var rdmg: float = c.dmg * float(G.run.get("attack_mult", 1.0)) * (1.0 + (Boons.val("bayu_serang") + Boons.val("baruna_serang")) / 100.0)
		Weapons.shoot(self, i, atk_dir, rdmg)
		return
	var col := Color(1.0, 0.85, 0.45)
	var holder := Boons.slot_holder("serang")
	if holder != "":
		col = G.GOD_COLORS[Boons.god_of(holder)]
	var center := global_position
	if i == 2 and Boons.owned("duo_badai"):
		var targets: Array = G.main.enemies().filter(func(e): return not e.dead)
		targets.sort_custom(func(a, b): return a.global_position.distance_to(global_position) < b.global_position.distance_to(global_position))
		for e in targets.slice(0, 3):
			strike(e, Boons.val("duo_badai"))
	if i == 2:
		center += atk_dir * 1.2
		Fx.shock(center, c.range + 0.4, col, 0.38, true)
		Fx.impact(center + Vector3(0, 0.4, 0), col, true)
		Fx.sprite("circle", center + Vector3(0, 0.06, 0), c.range * 2.2, col, 0.6, {"flat": true, "from": 0.4, "grow": 1.1, "spin": 1.2, "tint": 0.5, "intensity": 1.6, "hold": 0.3})
		Au.sfx("sfx_staff_slam", -1.0, 0.05)
		G.main.shake(0.4)
		G.main.flash(Color(1.0, 0.85, 0.5), 0.18, 0.18)
	else:
		Fx.slash(global_position, atk_dir, c.range + 0.2, c.arc, col, 1.0 if i == 0 else -1.0)
		Fx.light(global_position + atk_dir * 1.2 + Vector3(0, 1, 0), col, 1.6, 4.0, 0.15)
	var dmg: float = c.dmg * float(G.run.get("attack_mult", 1.0))
	dmg *= 1.0 + (Boons.val("bayu_serang") + Boons.val("baruna_serang")) / 100.0
	var kb := 3.5 if i < 2 else 6.0
	if Boons.owned("bayu_serang"):
		kb *= 2.2
	Breakable.hit_area(get_tree(), center, c.range + 0.2, atk_dir, c.arc)
	var hits := 0
	for e in G.main.enemies():
		if e.dead:
			continue
		var to: Vector3 = e.global_position - center
		to.y = 0
		var reach: float = c.range + e.radius
		if to.length() > reach:
			continue
		if c.arc < 6.0 and to.length() > 0.3 and atk_dir.angle_to(to) > c.arc * 0.5:
			continue
		hits += 1
		_deal(e, dmg, kb, col)
		if Boons.owned("surya_serang"):
			e.apply_burn(Boons.val("surya_serang"))
		if Boons.owned("baruna_serang"):
			e.apply_wet(0.3)
		if Boons.owned("indra_serang"):
			chain_lightning(e, Boons.val("indra_serang"), 2)
	if hits > 0:
		Au.sfx("sfx_hit" if i < 2 else "sfx_hit_heavy", -2.0, 0.1, 1.0 if i < 2 else 0.8)
		# layered body blow under the painted whoosh
		Au.sfx("sfx_punch_heavy" if i == 2 else ("sfx_punch1" if i == 0 else "sfx_punch2"), -4.0, 0.1)
		if i == 2 or randf() < 0.15:
			bark("vo_atk%d" % randi_range(1, 3))
		G.main.hitstop(0.05 if i < 2 else 0.09)
		G.vibrate(18 if i < 2 else 45)


func _deal(e: Actor, dmg: float, kb: float, col: Color) -> float:
	var crit := randf() * 100.0 < Boons.val("indra_pasif")
	var d := e.take_hit(dmg, global_position, kb, {"crit": crit, "color": Color(1, 0.4, 0.3) if crit else Color(1, 0.95, 0.8)})
	if d > 0.0:
		Fx.impact(e.global_position + Vector3(0, 1.0, 0), col, crit or dmg >= 25.0)
		if Boons.owned("duo_gelombang") and e.wet_t > 0.0:
			chain_lightning(e, Boons.val("duo_gelombang"), 1)
		if crit and Boons.owned("duo_fajar"):
			var c: Vector3 = e.global_position
			Fx.fire(c + Vector3(0, 1, 0), 2.6, G.GOD_COLORS.surya)
			Fx.shock(c, 2.6, G.GOD_COLORS.surya, 0.3)
			for o in G.main.enemies():
				if not o.dead and o != e and o.global_position.distance_to(c) < 2.6 + o.radius:
					o.take_hit(Boons.val("duo_fajar"), c, 3.0, {"color": G.GOD_COLORS.surya})
		if crit:
			Au.sfx("sfx_crit", -3.0)
			G.main.flash(Color(1, 0.95, 0.8), 0.12, 0.1)
	return d


func damage_taken_mult(e: Actor) -> float:
	var m := 1.0
	if e.burn_t > 0.0 and Boons.owned("surya_pasif"):
		m += Boons.val("surya_pasif") / 100.0
	if e.burn_t > 0.0 and e.wet_t > 0.0 and Boons.owned("duo_uap"):
		m += Boons.val("duo_uap") / 100.0
	return m


func chain_lightning(from: Actor, dmg: float, count: int) -> void:
	var done := {from: true}
	var src := from
	for k in count:
		var best: Actor = null
		var bd := 6.0
		for e in G.main.enemies():
			if e.dead or done.has(e):
				continue
			var d: float = e.global_position.distance_to(src.global_position)
			if d < bd:
				bd = d
				best = e
		if best == null:
			return
		done[best] = true
		Fx.bolt(src.global_position + Vector3(0, 1, 0), best.global_position + Vector3(0, 1, 0))
		best.take_hit(dmg, src.global_position, 1.0, {"color": Color("d8b8ff")})
		Au.sfx("sfx_lightning", -8.0)
		src = best


func strike(e: Actor, dmg: float) -> void:
	Fx.bolt(e.global_position + Vector3(randf_range(-1, 1), 9, randf_range(-1, 1)), e.global_position + Vector3(0, 0.2, 0))
	Fx.shock(e.global_position, 1.5, G.GOD_COLORS.indra, 0.25)
	e.take_hit(dmg, e.global_position + Vector3(0, 0, -0.1), 0.5, {"color": Color("d8b8ff")})
	Au.sfx("sfx_lightning", -4.0)


# --- Jurus -----------------------------------------------------------------

## Tongkat Mulur: the staff shoots out along the aim like a laser, piercing every
## raksasa in the line.
func try_special() -> void:
	if prana < 1.0 or special_cd > 0.0 or dash_t > 0.0:
		return
	prana -= 1.0
	special_cd = 0.5
	combo_i = -1
	cast_anim = 0.32
	var dir := assisted(aim, LASER_LEN)
	snap_face(dir)
	if randf() < 0.5:
		bark("vo_special%d" % randi_range(1, 2))
	var holder := Boons.slot_holder("jurus")
	var col := Color(1.0, 0.78, 0.35)
	if holder != "":
		col = G.GOD_COLORS[Boons.god_of(holder)]
	if Weapons.current() != "tongkat":
		rig.play("spin" if Weapons.current() != "panah" else "cast", 0.55)
		Weapons.special(self, dir, col)
		return
	rig.play("thrust", 0.4)
	var wave := Boons.owned("baruna_jurus")
	# charge flare at the fist, then fire
	var hand := _hand_pos()
	Fx.sprite("impact", hand, 1.4, col, 0.14, {"from": 0.2, "grow": 1.0, "spin": 3.0, "tint": 0.4, "intensity": 2.6})
	Au.sfx("sfx_laser", -1.0, 0.03)
	get_tree().create_timer(0.07, true, false, true).timeout.connect(func():
		if not dead:
			_fire_laser(dir, col, wave))


func _hand_pos() -> Vector3:
	var p := global_position + facing * 0.45
	if staff and staff.is_inside_tree():
		p = staff.global_position
	return Vector3(p.x, 1.05, p.z)


func _fire_laser(dir: Vector3, col: Color, wave: bool) -> void:
	var from := _hand_pos()
	var width := LASER_WIDTH * (1.9 if wave else 1.0)
	var length := LASER_LEN
	Fx.laser(from, dir, length, width, col, 0.42)
	Breakable.hit_line(get_tree(), from, dir, length, width)
	if Boons.owned("duo_topan"):
		for k in int(length / 1.6):
			var fp := from + dir * (1.0 + k * 1.6)
			if G.main.room_contains(fp, -0.5):
				FirePatch.spawn(Vector3(fp.x, 0, fp.z), Boons.val("duo_topan"))
	G.vibrate(70)
	# the staff itself stretches out along the beam
	var beam_staff := Staff.new()
	Fx.layer.add_child(beam_staff)
	beam_staff.global_position = from
	beam_staff.basis = Basis(Quaternion(Vector3.UP, dir))
	beam_staff.grip = 0.3
	beam_staff.set_length(1.0)
	beam_staff.set_glow(col)
	beam_staff.extend_to(length, 0.09, 0.26, 0.14)
	beam_staff.get_tree().create_timer(0.55).timeout.connect(beam_staff.queue_free)
	if staff:
		staff.visible = false
		get_tree().create_timer(0.5).timeout.connect(func():
			if staff: staff.visible = true)
	G.main.shake(0.3)
	G.main.flash(col.lerp(Color.WHITE, 0.5), 0.22, 0.2)
	var dmg := 22.0 * (1.0 + Boons.val("bayu_jurus") / 100.0)
	if wave:
		dmg = Boons.val("baruna_jurus") * 1.4
	var kb := 9.0 if Boons.owned("bayu_jurus") else 4.0
	var hits := 0
	for e in G.main.enemies():
		if e.dead:
			continue
		var to: Vector3 = e.global_position - from
		to.y = 0
		var along := to.dot(dir)
		if along < -0.5 or along > length:
			continue
		var off := (to - dir * along).length()
		if off > width * 0.5 + e.radius:
			continue
		hits += 1
		var d := _deal(e, dmg, kb, col)
		if d > 0.0:
			e.knock += dir * kb * 0.5
		if wave:
			e.apply_wet(0.3)
		if Boons.owned("surya_jurus"):
			var c: Vector3 = e.global_position
			Fx.shock(c, 2.4, G.GOD_COLORS.surya, 0.3)
			Fx.fire(c + Vector3(0, 1, 0), 2.2, G.GOD_COLORS.surya)
			Au.sfx("sfx_explosion", -5.0)
			for o in G.main.enemies():
				if not o.dead and o != e and o.global_position.distance_to(c) < 2.4 + o.radius:
					_deal(o, Boons.val("surya_jurus"), 3.0, G.GOD_COLORS.surya)
		if Boons.owned("indra_jurus") and not e.dead:
			strike(e, Boons.val("indra_jurus"))
	if hits > 0:
		Au.sfx("sfx_laser_hit", -3.0)
		G.main.hitstop(0.06)


# --- Ajian -----------------------------------------------------------------

func try_cast() -> void:
	if cast_cd > 0.0 or dash_t > 0.0:
		return
	cast_cd = CAST_COOLDOWN
	combo_i = -1
	cast_anim = 0.3
	rig.play("cast", 0.45)
	var target := global_position + assisted(aim, 7.0) * 3.5
	if mouse_aim and not G.touch_mode:
		var gp: Vector3 = G.main.mouse_ground()
		var off := gp - global_position
		off.y = 0
		if off.length() > 6.0:
			off = off.normalized() * 6.0
		target = global_position + off
	target = G.main.clamp_to_room(target, 1.0)
	var c := AjianCircle.new()
	Fx.layer.add_child(c)
	c.global_position = Vector3(target.x, 0, target.z)
	c.player = self
	Au.sfx("sfx_cast", -2.0)
	G.main.flash(Color(0.7, 1.0, 0.95), 0.12, 0.15)


# --- Lesat -----------------------------------------------------------------

func try_dash(mv: Vector3) -> void:
	if dash_charges <= 0 or dash_t > 0.0:
		return
	dash_charges -= 1
	dash_regen = 0.0
	combo_i = -1
	dash_dir = (mv if mv.length() > 0.2 else facing).normalized()
	snap_face(dash_dir)
	dash_t = DASH_TIME
	rig.play("dash", DASH_TIME + 0.08)
	invuln = max(invuln, DASH_TIME + 0.08)
	collision_mask = L_WORLD
	Au.sfx("sfx_dash", -4.0)
	Fx.wind(global_position, 2.2)
	Fx.dust(global_position, 0.9, Color(0.8, 0.85, 0.9))
	Fx.sparks(global_position + Vector3(0, 0.8, 0), Color(0.8, 1.0, 0.95), 8, 5.0, -dash_dir + Vector3.UP * 0.3)
	if Boons.owned("bayu_lesat"):
		Fx.shock(global_position, 2.5, G.GOD_COLORS.bayu, 0.3)
		for e in G.main.enemies():
			if not e.dead and e.global_position.distance_to(global_position) < 2.5 + e.radius:
				_deal(e, Boons.val("bayu_lesat"), 9.0, G.GOD_COLORS.bayu)
	if Boons.owned("duo_samudra"):
		Fx.splash(global_position, 3.4, G.GOD_COLORS.baruna)
		Fx.wind(global_position, 3.4, G.GOD_COLORS.bayu)
		for e in G.main.enemies():
			if not e.dead and e.global_position.distance_to(global_position) < 3.2 + e.radius:
				_deal(e, Boons.val("duo_samudra"), 7.0, G.GOD_COLORS.baruna)
				e.apply_wet(0.3)
	if Boons.owned("indra_lesat"):
		var best: Actor = null
		var bd := 9.0
		for e in G.main.enemies():
			if not e.dead and e.global_position.distance_to(global_position) < bd:
				bd = e.global_position.distance_to(global_position)
				best = e
		if best:
			strike(best, Boons.val("indra_lesat"))


func _dash_tick(delta: float) -> void:
	if Boons.owned("surya_lesat"):
		_fire_trail_t -= delta
		if _fire_trail_t <= 0.0:
			_fire_trail_t = 0.05
			FirePatch.spawn(global_position, Boons.val("surya_lesat"))


func _end_dash() -> void:
	collision_mask = L_WORLD | L_ENEMY
	if Boons.owned("baruna_lesat"):
		Fx.shock(global_position, 2.2, G.GOD_COLORS.baruna, 0.35)
		Au.sfx("sfx_wave", -6.0)
		for e in G.main.enemies():
			if not e.dead and e.global_position.distance_to(global_position) < 2.2 + e.radius:
				_deal(e, Boons.val("baruna_lesat"), 3.0, G.GOD_COLORS.baruna)
				e.apply_wet(0.3)
	if atk_queued:
		atk_queued = false
		_start_swing(0)


# --- damage ------------------------------------------------------------------

func take_hit(dmg: float, from: Vector3, knockback := 3.0, info := {}) -> float:
	if dead or invuln > 0.0 or not G.in_run:
		return 0.0
	G.run.hp = float(G.run.hp) - dmg
	invuln = 0.7
	_flash = 1.0
	rig.hit()
	var away := global_position - from
	away.y = 0
	if away.length_squared() > 0.001:
		knock += away.normalized() * knockback * 0.6
	Au.sfx("sfx_player_hurt", -1.0)
	bark("vo_low" if float(G.run.hp) - dmg < float(G.run.max_hp) * 0.25 else "vo_hurt%d" % randi_range(1, 2), true)
	Au.sfx("sfx_punch_heavy", -5.0, 0.1)
	G.vibrate(90)
	G.main.flash(Color(1.0, 0.2, 0.15), 0.15, 0.25)
	G.main.shake(0.35)
	G.main.hurt_flash()
	Fx.number(global_position, dmg, Color(1, 0.3, 0.3))
	if float(G.run.hp) <= 0.0:
		if int(G.run.death_defy) > 0:
			G.run.death_defy = int(G.run.death_defy) - 1
			G.run.hp = float(G.run.max_hp) * 0.5
			invuln = 2.0
			Fx.shock(global_position, 4.0, Color(1, 0.85, 0.4), 0.6)
			G.say("Iron Bones! Hanoman rises again.", Color(1, 0.85, 0.4))
		else:
			G.run.hp = 0.0
			die()
	G.run_changed.emit()
	return dmg


func on_death() -> void:
	combo_i = -1
	rig.play("die", 1.2)
	G.main.on_player_death()


# --- interaction --------------------------------------------------------------

func _find_interact() -> void:
	var best: Node = null
	var bd := 2.4
	for n in get_tree().get_nodes_in_group("interactable"):
		if not n.is_inside_tree() or not n.get_meta("active", true):
			continue
		var d: float = (n as Node3D).global_position.distance_to(global_position)
		if d < bd:
			bd = d
			best = n
	if best != interact_target:
		interact_target = best
		G.main.ui.show_prompt(best.get_meta("prompt", "") if best else "")


func try_interact() -> void:
	if G.main.busy or G.main.ui.dialog_blocking():
		return
	if interact_target and is_instance_valid(interact_target):
		interact_target.call("interact")


## Hanoman's voice (Higgsfield TTS barks): rate-limited so it never chatters.
var _bark_t := 0


func bark(key: String, force := false) -> void:
	var now := Time.get_ticks_msec()
	if not force and now - _bark_t < 2500:
		return
	if Hf.sound(key) == null:
		return
	_bark_t = now
	Au.sfx(key, -2.0, 0.03)
