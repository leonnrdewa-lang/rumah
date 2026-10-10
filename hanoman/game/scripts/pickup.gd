class_name Pickup
extends Node3D
## Room rewards collected by walking over them: Kepeng (coins), Tirta Amerta
## (healing) and Kembang Wijayakusuma (permanent currency for Jembawan).

var type := "kepeng"
var _taken := false


static func make(t: String) -> Pickup:
	var p := Pickup.new()
	p.type = t
	var ids := {"kepeng": "kepeng", "tirta": "tirta", "bunga": "wijayakusuma"}
	var model_id: String = ids.get(t, "kepeng")
	if Art.has_model(model_id):
		var m := Art.model(model_id)
		m.scale = Vector3.ONE * 1.6
		m.position.y = 0.3
		p.add_child(m)
	else:
		var s := Sprite3D.new()
		s.texture = load(Arena.REWARD_ICON.get(t, Arena.REWARD_ICON.kepeng))
		s.pixel_size = 0.01
		s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		s.position.y = 0.8
		p.add_child(s)
	var l := OmniLight3D.new()
	l.light_color = {"kepeng": Color(1, 0.8, 0.3), "tirta": Color(1, 0.4, 0.5), "bunga": Color(0.9, 0.95, 1.0)}.get(t, Color.WHITE)
	l.light_energy = 1.5
	l.omni_range = 3.5
	l.position.y = 1.0
	p.add_child(l)
	return p


func _physics_process(_delta: float) -> void:
	if _taken or G.main.player == null:
		return
	rotation.y += 0.02
	var d := Vector2(G.main.player.global_position.x - global_position.x, G.main.player.global_position.z - global_position.z).length()
	if d < 1.3:
		_taken = true
		match type:
			"kepeng":
				var n := randi_range(45, 75)
				G.add_kepeng(n)
				G.say("+%d Kepeng" % n, Color(1, 0.85, 0.4))
				Au.sfx("sfx_pickup_coin")
			"tirta":
				G.heal(25)
				G.say("Tirta Amerta: +25 health", Color(1, 0.55, 0.6))
				Au.sfx("sfx_pickup_heal")
			"bunga":
				G.add_bunga(3)
				G.run.bunga_gained = int(G.run.get("bunga_gained", 0)) + 3
				G.say("+3 Wijayakusuma Blossoms", Color(0.95, 0.95, 1.0))
				Au.sfx("sfx_boon_pick", -4.0)
		Fx.burst(global_position + Vector3(0, 0.8, 0), Color(1, 0.9, 0.6), 18, 4.0, 0.2, 0.5)
		queue_free()
