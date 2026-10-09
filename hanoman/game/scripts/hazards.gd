class_name Hazards
extends Node
## Second phase of the boss arenas. Once a boss falls below half health the
## arena itself turns on Hanoman: geysers burst from the estuary (Sura & Baya)
## or golden lightning rains down (Kijang Kencana), always telegraphed.

var arena: Arena
var bosses: Array = []
var active := false
var _t := 2.0


func _physics_process(delta: float) -> void:
	if arena == null or not is_instance_valid(arena) or arena.is_clear:
		return
	var alive := bosses.filter(func(b): return is_instance_valid(b) and not b.dead)
	if alive.is_empty():
		return
	if not active:
		for b in alive:
			if b.hp < b.max_hp * 0.5 or b.phase >= 2:
				_begin()
				break
		return
	if G.main.busy:
		return
	_t -= delta
	if _t <= 0.0:
		_t = randf_range(2.6, 3.6)
		_wave()


func _begin() -> void:
	active = true
	_t = 1.5
	var muara := arena.biome == "muara"
	G.main.ui.phase_banner("Air Pasang!" if muara else "Hujan Petir Emas!")
	G.main.flash(Color(0.5, 0.8, 1.0) if muara else Color(1.0, 0.85, 0.4), 0.3, 0.6)
	G.main.shake(0.5)
	Au.sfx("sfx_bell", -1.0)
	Au.sfx("sfx_wave" if muara else "sfx_lightning", -2.0)


func _wave() -> void:
	var pl: Vector3 = G.main.player.global_position
	var muara := arena.biome == "muara"
	var col := Color(0.4, 0.8, 1.0) if muara else Color(1.0, 0.8, 0.3)
	var n := 3
	for i in n:
		var off := Vector3.ZERO if i == 0 else Vector3(randf_range(-4.5, 4.5), 0, randf_range(-3.5, 3.5))
		var p: Vector3 = G.main.clamp_to_room(pl + off, 1.2)
		var r := 1.7
		Fx.ring(p, r, col, 1.1, true, TAU, 0.0, true)
		var tw := create_tween()
		tw.tween_interval(1.1 + i * 0.08)
		tw.tween_callback(_strike.bind(p, r, col, muara))


func _strike(p: Vector3, r: float, col: Color, muara: bool) -> void:
	if arena == null or not is_instance_valid(arena) or arena.is_clear:
		return
	if muara:
		Fx.splash(p, 3.2, col)
		Fx.sprite("splash", p + Vector3(0, 1.6, 0), 3.6, col, 0.6, {"billboard": 2.0, "stretch": Vector2(0.7, 1.6), "from": 0.4, "grow": 1.2, "tint": 0.3, "intensity": 2.0})
		Au.sfx("sfx_geyser", -5.0, 0.1)
	else:
		Fx.lightning(p, 9.0, col)
		Fx.shock(p, r + 0.6, col, 0.3)
		Au.sfx("sfx_lightning", -5.0, 0.1)
	G.main.shake(0.15)
	var pl: Player = G.main.player
	if pl and not pl.dead and Vector2(pl.global_position.x - p.x, pl.global_position.z - p.z).length() < r + pl.radius * 0.5:
		pl.take_hit(9.0, p, 6.0)
	# the arena hurts the bosses too: lure them in
	for b in bosses:
		if is_instance_valid(b) and not b.dead and not b.submerged and Vector2(b.global_position.x - p.x, b.global_position.z - p.z).length() < r + b.radius:
			b.take_hit(18.0, p, 0.0, {"color": col})
