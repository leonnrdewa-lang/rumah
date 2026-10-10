class_name Chakram
extends Node3D
## Sudarsana chakra: thrown out along `dir`, then flies back to Hanoman (hitting
## on both passes), or with `orbit` circles him for a few seconds.

var owner_player: Player
var dmg := 12.0
var dir := Vector3.FORWARD
var col := Color(1.0, 0.85, 0.45)
var orbit := false
var orbit_phase := 0.0
var _t := 0.0
var _returning := false
var _hit := {}
var _disc: Node3D


func _ready() -> void:
	_disc = Node3D.new()
	add_child(_disc)
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = 0.38
	c.bottom_radius = 0.38
	c.height = 0.06
	c.radial_segments = 16
	mi.mesh = c
	mi.material_override = Art.toon(Color("e8b23a"), 0.6, 1.6, true)
	_disc.add_child(mi)
	for k in 6:
		var b := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.14, 0.04, 0.3)
		b.mesh = bm
		b.material_override = mi.material_override
		var a := TAU * k / 6.0
		b.position = Vector3(cos(a), 0, sin(a)) * 0.45
		b.rotation.y = -a + 0.6
		_disc.add_child(b)
	var glow := Fx.orb(col, 0.2, "k_twirl")
	add_child(glow)
	var tr := Fx.trail(col, 0.2)
	add_child(tr)


func _physics_process(delta: float) -> void:
	_t += delta
	_disc.rotation.y += delta * 22.0
	if owner_player == null or not is_instance_valid(owner_player):
		queue_free()
		return
	var home := owner_player.global_position + Vector3(0, 1.0, 0)
	if orbit:
		var a := orbit_phase + _t * 5.0
		global_position = home + Vector3(cos(a), 0, sin(a)) * 2.4
		if fmod(_t, 0.35) < delta:
			_hit.clear()
		if _t > 3.5:
			Fx.burst(global_position, col, 8, 3.0, 0.1, 0.3)
			queue_free()
			return
	else:
		if not _returning:
			global_position += dir * 17.0 * delta
			if _t > 0.42 or not G.main.room_contains(global_position, 0.5):
				_returning = true
				_hit.clear()
		else:
			var to := home - global_position
			if to.length() < 0.8:
				queue_free()
				return
			global_position += to.normalized() * 22.0 * delta
	for e in G.main.enemies():
		if e.dead or _hit.has(e):
			continue
		if Vector2(e.global_position.x - global_position.x, e.global_position.z - global_position.z).length() < 0.7 + e.radius:
			_hit[e] = true
			owner_player._deal(e, dmg, 2.5, col)
			Au.sfx("sfx_punch1", -8.0, 0.15, 1.4)
