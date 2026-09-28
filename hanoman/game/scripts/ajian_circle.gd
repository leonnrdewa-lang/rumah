class_name AjianCircle
extends Node3D
## Ajian Bayu: a rune circle on the ground. Enemies inside are Terikat (bound,
## 70% slower) and take the Ajian boon's extra effects (pull, burn, lightning).

const RADIUS := 3.0
const LIFE := 4.0

var player: Player
var t := 0.0
var _mat: ShaderMaterial
var _tick := 0.0
var _mi: MeshInstance3D


func _ready() -> void:
	var holder := Boons.slot_holder("ajian")
	var col := G.GOD_COLORS.bayu
	if holder != "":
		col = G.GOD_COLORS[Boons.god_of(holder)]
	_mi = MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(2, 2)
	q.orientation = PlaneMesh.FACE_Y
	_mi.mesh = q
	_mat = Art.ring_mat(col, true)
	_mat.set_shader_parameter("fill", 1.0)
	_mi.material_override = _mat
	_mi.position.y = 0.05
	_mi.scale = Vector3.ONE * 0.1
	_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_mi)
	create_tween().tween_property(_mi, "scale", Vector3(RADIUS, 1, RADIUS), 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	var light := OmniLight3D.new()
	light.light_color = col
	light.light_energy = 1.2
	light.omni_range = 5.0
	light.position.y = 1.0
	add_child(light)
	Fx.burst(global_position + Vector3(0, 0.3, 0), col, 24, 4.0, 0.18, 0.5)
	if Boons.owned("baruna_ajian"):
		Fx.shock(global_position, RADIUS + 1.0, G.GOD_COLORS.baruna, 0.45)
		Au.sfx("sfx_wave", -3.0)
		for e in _inside(1.0):
			player._deal(e, Boons.val("baruna_ajian"), 4.0, G.GOD_COLORS.baruna)
			e.apply_wet(0.3)


func _inside(extra := 0.0) -> Array:
	var out := []
	for e in G.main.enemies():
		if e.dead:
			continue
		var d := Vector2(e.global_position.x - global_position.x, e.global_position.z - global_position.z).length()
		if d < RADIUS + extra + e.radius * 0.5:
			out.append(e)
	return out


func _physics_process(delta: float) -> void:
	t += delta
	_tick += delta
	var ticking := _tick >= 0.5
	if ticking:
		_tick = 0.0
	for e in _inside():
		e.apply_bound(0.25)
		if Boons.owned("bayu_ajian"):
			var to: Vector3 = global_position - e.global_position
			to.y = 0
			if not e.heavy:
				e.knock += to.normalized() * delta * 14.0
			if ticking:
				e.take_hit(Boons.val("bayu_ajian") * 0.5, global_position, 0.0, {"color": Color("a8fff0")})
		if Boons.owned("surya_ajian"):
			e.apply_burn(Boons.val("surya_ajian"), 1.5)
		if ticking and Boons.owned("indra_ajian"):
			player.strike(e, Boons.val("indra_ajian"))
	if t > LIFE - 0.4:
		_mat.set_shader_parameter("alpha", max(0.0, (LIFE - t) / 0.4))
	if t >= LIFE:
		queue_free()
