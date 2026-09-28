class_name Npc
extends Node3D
## Hub character: idles with the part rig and turns toward Hanoman when near.

var id := "rama"
var model: Node3D
var rig: Rig
var _talk_t := 0.0


func _ready() -> void:
	model = Art.model(id, true)
	add_child(model)
	rig = Rig.new(model, "biped")
	model.rotation.y = randf_range(-0.4, 0.4)


func _process(delta: float) -> void:
	rig.update(delta, 0.0)
	var pl: Node3D = G.main.player
	if pl and pl.is_inside_tree():
		var to := pl.global_position - global_position
		to.y = 0
		if to.length() < 5.0:
			model.rotation.y = lerp_angle(model.rotation.y, atan2(to.x, to.z), clamp(delta * 4.0, 0.0, 1.0))
			_talk_t -= delta
			if _talk_t <= 0.0 and to.length() < 2.5:
				_talk_t = 4.0
				rig.play("talk", 1.0)
