class_name Projectile
extends Node3D
## Straight-flying shot (Hanoman's wind blade, Banaspati fireballs, water jets).
## Hits are distance checks against the opposing team; it dies on leaving the arena.

var vel := Vector3.ZERO
var team := "player"
var damage := 10.0
var radius := 0.5
var life := 1.5
var pierce := false
var knockback := 3.0
var color := Color.WHITE
var on_hit: Callable
var hit_set := {}
var height := 1.0
var visual: Node3D
var look := ""          # painted sprite: fire | splash | "" (energy)


static func spawn(pos: Vector3, dir: Vector3, speed: float, p_team: String, dmg: float, col: Color, size := 0.3, p_look := "") -> Projectile:
	var p := Projectile.new()
	p.vel = dir.normalized() * speed
	p.team = p_team
	p.damage = dmg
	p.color = col
	p.radius = size + 0.35
	p.look = p_look
	var o := Fx.orb(col, size, p_look)
	p.add_child(o)
	p.visual = o
	var tr := Fx.trail(col, size * 0.9)
	p.add_child(tr)
	Fx.layer.add_child(p)
	p.global_position = Vector3(pos.x, p.height, pos.z)
	return p


func _physics_process(delta: float) -> void:
	life -= delta
	global_position += vel * delta
	if life <= 0.0 or not G.main.room_contains(global_position, 1.0):
		_pop()
		return
	if team == "player":
		for e in G.main.enemies():
			if e.dead or hit_set.has(e):
				continue
			var d := Vector2(e.global_position.x - global_position.x, e.global_position.z - global_position.z).length()
			if d < radius + e.radius:
				hit_set[e] = true
				if on_hit.is_valid():
					on_hit.call(e, self)
				else:
					e.take_hit(damage, global_position - vel.normalized(), knockback)
				if not pierce:
					_pop()
					return
	else:
		var pl: Actor = G.main.player
		if pl and not pl.dead:
			var d := Vector2(pl.global_position.x - global_position.x, pl.global_position.z - global_position.z).length()
			if d < radius + pl.radius * 0.7 and pl.invuln <= 0.0:
				pl.take_hit(damage, global_position - vel.normalized(), knockback)
				if on_hit.is_valid():
					on_hit.call(pl, self)
				_pop()


func _pop() -> void:
	match look:
		"fire":
			Fx.fire(global_position, 1.8, color)
			Au.sfx("sfx_explosion", -12.0, 0.1, 1.3)
		"splash":
			Fx.splash(Vector3(global_position.x, 0.0, global_position.z), 1.8, color)
		_:
			Fx.impact(global_position, color)
	queue_free()
