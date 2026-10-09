class_name Breakable
extends StaticBody3D
## Clay gentong / wooden peti standing around the chambers. One staff hit (or
## the laser) smashes it into shards; some hide Kepeng or a sip of Tirta.

const CLAY := Color("9a5a34")
const CLAY_DARK := Color("6b3a22")
const WOOD := Color("7a5634")

var style := "gentong"
var broken := false
var radius := 0.45


static func make(p_style: String) -> Breakable:
	var b := Breakable.new()
	b.style = p_style
	b.collision_layer = Actor.L_WORLD
	b.collision_mask = 0
	b.add_to_group("breakable")
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = 0.42
	cyl.height = 1.2
	cs.shape = cyl
	cs.position.y = 0.6
	b.add_child(cs)
	if p_style == "peti":
		var box := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.8, 0.7, 0.8)
		box.mesh = bm
		box.material_override = Art.toon(WOOD, 0.0, 1.6, true)
		box.position.y = 0.35
		b.add_child(box)
		for y in [0.12, 0.58]:
			var band := MeshInstance3D.new()
			var bb := BoxMesh.new()
			bb.size = Vector3(0.84, 0.08, 0.84)
			band.mesh = bb
			band.material_override = Art.toon(Color("3b2a1c"), 0.0, 1.6, true)
			band.position.y = y
			b.add_child(band)
	else:
		# gentong: bulging clay jar with a darker rim
		var body := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.4
		sm.height = 0.9
		sm.radial_segments = 14
		sm.rings = 8
		body.mesh = sm
		body.material_override = Art.toon(CLAY, 0.0, 1.6, true)
		body.position.y = 0.45
		b.add_child(body)
		var neck := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.22
		cm.bottom_radius = 0.18
		cm.height = 0.22
		cm.radial_segments = 12
		neck.mesh = cm
		neck.material_override = Art.toon(CLAY_DARK, 0.0, 1.6, true)
		neck.position.y = 0.95
		b.add_child(neck)
	b.rotation.y = randf() * TAU
	b.scale = Vector3.ONE * randf_range(0.9, 1.15)
	return b


## Smash every breakable whose centre lies in the swing arc / circle.
static func hit_area(tree: SceneTree, center: Vector3, reach: float, dir := Vector3.ZERO, arc := TAU) -> void:
	for n in tree.get_nodes_in_group("breakable"):
		var b := n as Breakable
		if b == null or b.broken:
			continue
		var to := b.global_position - center
		to.y = 0
		if to.length() > reach + b.radius:
			continue
		if arc < 6.0 and dir.length() > 0.01 and to.length() > 0.3 and dir.angle_to(to) > arc * 0.5:
			continue
		b.smash(center)


## Smash breakables along a beam.
static func hit_line(tree: SceneTree, from: Vector3, dir: Vector3, length: float, width: float) -> void:
	for n in tree.get_nodes_in_group("breakable"):
		var b := n as Breakable
		if b == null or b.broken:
			continue
		var to := b.global_position - from
		to.y = 0
		var along := to.dot(dir)
		if along < 0.0 or along > length:
			continue
		if (to - dir * along).length() <= width * 0.5 + b.radius:
			b.smash(from)


func smash(from: Vector3) -> void:
	if broken:
		return
	broken = true
	remove_from_group("breakable")
	collision_layer = 0
	var p := global_position
	var col := WOOD if style == "peti" else CLAY
	Fx.debris(p + Vector3(0, 0.5, 0), col, 16, 7.0)
	Fx.dust(p, 1.2, Color(0.7, 0.55, 0.4))
	Fx.sprite("k_dirt", p + Vector3(0, 0.6, 0), 2.0, Color(0.8, 0.6, 0.4), 0.45, {"from": 0.4, "grow": 1.3, "tint": 0.5, "intensity": 0.9})
	Au.sfx("sfx_crate_break" if style == "peti" else "sfx_pot_break", -3.0, 0.12)
	G.vibrate(25)
	var r := randf()
	if G.in_run and r < 0.45:
		var n := randi_range(6, 16)
		G.add_kepeng(n)
		Fx.text(p, "+%d Kepeng" % n, Color(1, 0.85, 0.4))
		Fx.burst(p + Vector3(0, 0.8, 0), Color(1, 0.8, 0.3), 12, 4.0, 0.12, 0.5)
		Au.sfx("sfx_coin_drop", -4.0)
	elif G.in_run and r < 0.55:
		G.heal(5)
		Fx.text(p, "+5 nyawa", Color(1, 0.55, 0.6))
		Fx.burst(p + Vector3(0, 0.8, 0), Color(1, 0.45, 0.55), 10, 3.0, 0.12, 0.5)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector3(scale.x * 1.25, scale.y * 0.2, scale.z * 1.25), 0.08)
	tw.tween_callback(queue_free)
