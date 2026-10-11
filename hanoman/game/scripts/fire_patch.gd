class_name FirePatch
extends Node3D
## Burning ground left by Lesat Bara: sets enemies that touch it alight.

var dps := 6.0
var life := 1.6


static func spawn(pos: Vector3, p_dps: float) -> void:
	var f := FirePatch.new()
	f.dps = p_dps
	var tr := Fx.trail(Color(1.0, 0.55, 0.15), 0.35)
	tr.position.y = 0.2
	f.add_child(tr)
	Fx.layer.add_child(f)
	f.global_position = Vector3(pos.x, 0, pos.z)


func _physics_process(delta: float) -> void:
	life -= delta
	if life <= 0.0:
		queue_free()
		return
	for e in G.main.enemies():
		if not e.dead and Vector2(e.global_position.x - global_position.x, e.global_position.z - global_position.z).length() < 0.9 + e.radius:
			e.apply_burn(dps, 3.0)
