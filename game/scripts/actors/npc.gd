class_name Npc
extends Node3D
## A villager (or any other character) that idles and wanders around an anchor
## point, goes home at night and turns to face the player while talking.

var vid := ""            # villager id in GS.villagers, or "" for extras
var display_name := ""
var model_name := ""
var world: Node
var model: Node3D
var anim: CharAnim
var anchor := Vector3.ZERO
var radius := 6.0
var home := Vector3.ZERO
var sleeps_at_night := true
var speed := 1.5
var talking := false
var talk_target: Node3D
var _target := Vector3.ZERO
var _wait := 0.0
var _t := 0.0
var _moving := false
var _emote: Label3D
var _emote_t := 0.0
var _name_label: Label3D


func setup(p_world: Node, p_model: String, p_name: String, p_anchor: Vector3, p_radius: float) -> void:
	world = p_world
	model_name = p_model
	display_name = p_name
	anchor = p_anchor
	home = p_anchor
	radius = p_radius


func _ready() -> void:
	model = ModelLib.instance(model_name, false)
	add_child(model)
	anim = CharAnim.new(model)
	position = anchor
	_target = anchor
	_wait = randf_range(0.5, 3.0)
	_emote = Label3D.new()
	_emote.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_emote.font = ModelLib.label_font()
	_emote.font_size = 72
	_emote.outline_size = 14
	_emote.modulate = Color("5a3b22")
	_emote.outline_modulate = Color("fdf3dc")
	_emote.position.y = 1.75
	_emote.no_depth_test = true
	_emote.visible = false
	add_child(_emote)
	_name_label = Label3D.new()
	_name_label.text = display_name
	_name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_label.font = ModelLib.label_font()
	_name_label.font_size = 36
	_name_label.outline_size = 9
	_name_label.pixel_size = 0.01
	_name_label.modulate = Color("5a3b22")
	_name_label.outline_modulate = Color("fdf3dc")
	_name_label.position.y = 1.45
	_name_label.no_depth_test = true
	_name_label.visible = false
	add_child(_name_label)


func set_anchor(p: Vector3, r: float, teleport := false) -> void:
	anchor = p
	radius = r
	_target = p
	if teleport:
		position = p


func emote(text: String, seconds := 2.5) -> void:
	_emote.text = text
	_emote.visible = true
	_emote_t = seconds


func is_awake() -> bool:
	if not sleeps_at_night:
		return true
	return GS.hour >= 6.5 and GS.hour < 19.5


func _process(delta: float) -> void:
	_t += delta
	if _emote_t > 0.0:
		_emote_t -= delta
		_emote.position.y = 1.75 + sin(_t * 4.0) * 0.05
		if _emote_t <= 0.0:
			_emote.visible = false
	if talking and world and world.ui and world.ui.modal == null:
		talking = false
	if world and world.player and _name_label:
		var near: bool = world.state == "play" and world.player.global_position.distance_to(global_position) < 5.5
		_name_label.visible = near and not talking and not _emote.visible
	var awake := is_awake()
	visible = awake or talking or position.distance_to(home) > 1.0
	if talking and talk_target:
		var d := talk_target.global_position - global_position
		model.rotation.y = lerp_angle(model.rotation.y, atan2(d.x, d.z), clampf(delta * 8.0, 0.0, 1.0))
		anim.talk_t = 0.2
		anim.update(delta, 0.0, _t)
		return
	var goal := _target if awake else home
	var to := goal - position
	to.y = 0.0
	if to.length() > 0.25 and (_wait <= 0.0 or not awake):
		var step := to.normalized() * speed * (1.6 if not awake else 1.0) * delta
		if step.length() > to.length():
			step = to
		position += step
		model.rotation.y = lerp_angle(model.rotation.y, atan2(to.x, to.z), clampf(delta * 8.0, 0.0, 1.0))
		_moving = true
	else:
		_moving = false
		if awake:
			_wait -= delta
			if _wait <= 0.0 and to.length() <= 0.25:
				_pick_target()
	if world:
		position.y = world.height_at(position.x, position.z)
	anim.update(delta, speed if _moving else 0.0, _t)


func _pick_target() -> void:
	_wait = randf_range(2.0, 7.0)
	for i in 12:
		var a := randf() * TAU
		var r := sqrt(randf()) * radius
		var p := anchor + Vector3(cos(a) * r, 0, sin(a) * r)
		if world == null or (world.is_walkable(p.x, p.z) and world.is_free(p.x, p.z, 0.6)
				and world.is_free((p.x + position.x) * 0.5, (p.z + position.z) * 0.5, 0.4)):
			_target = p
			return
	_target = anchor
