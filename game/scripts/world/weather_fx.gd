extends Node
## What the weather looks and sounds like (the logic is scripts/systems/weather_sys.gd):
## - clouds and rain dim the sun, grey the sky light and the background; a cheap
##   screen-space overlay (one full-screen quad, no particles) draws slanted rain
##   streaks, a wet blue-grey tint and, in a storm, lightning flashes;
## - land fires: a flame + smoke column (two small CPUParticles3D) on each burning tile;
##   smoke haze (kabut asap) tints the screen and the light a dirty yellow-grey;
## - a flooded village gets a muddy water disc over its low ground for the day;
## - rain / thunder sounds are synthesised once (brown noise) and play quietly on the
##   Ambience bus (the existing ambience beds are untouched);
## - the Jalan Kebun upgrade (and mud in the rain) set the player's walking speed.
## Cost: 1 draw for the overlay (only while needed) + 2 per visible fire.

const OVERLAY_SHADER := """shader_type canvas_item;
uniform float rain = 0.0;
uniform float wet = 0.0;
uniform float haze = 0.0;
uniform float flash = 0.0;
uniform float aspect = 1.777;

float h1(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float streaks(vec2 uv, float cells, float speed, float len, float seed) {
	vec2 p = vec2(uv.x * aspect + uv.y * 0.22, uv.y) * vec2(cells, cells / len);
	p.y -= TIME * speed;
	vec2 c = floor(p);
	vec2 f = fract(p);
	float h = h1(c + seed);
	float on = step(1.0 - rain * 0.85, h);
	float x = abs(f.x - (0.15 + 0.7 * h1(c + seed + 7.0)));
	float w = 0.045 + 0.02 * h;
	return on * smoothstep(w, 0.0, x) * smoothstep(0.0, 0.35, f.y) * smoothstep(1.0, 0.65, f.y);
}

void fragment() {
	vec2 uv = UV;
	float r = 0.0;
	if (rain > 0.01) {
		r = streaks(uv, 34.0, 2.6, 3.0, 1.0) * 0.55 + streaks(uv, 20.0, 1.9, 2.4, 9.0) * 0.4;
	}
	vec3 col = vec3(0.0);
	float a = 0.0;
	// smoke haze: denser toward the top of the frame (the distance)
	float hz = haze * mix(0.9, 0.5, uv.y);
	col = mix(col, vec3(0.72, 0.6, 0.42), hz);
	a = hz;
	// wet tint: cool and dull
	float wt = wet * 0.24;
	col = mix(col, vec3(0.33, 0.4, 0.5), wt / max(a + wt, 0.001));
	a = a + wt * (1.0 - a);
	// rain streaks
	col = mix(col, vec3(0.86, 0.9, 0.96), r / max(a + r, 0.001));
	a = a + r * 0.6 * (1.0 - a);
	// lightning
	col = mix(col, vec3(0.95, 0.97, 1.0), flash);
	a = max(a, flash * 0.55);
	COLOR = vec4(col, a);
}
"""

const CLOUD := {"cerah": 0.0, "berawan": 0.38, "hujan": 0.78, "badai": 1.0}
const RAIN := {"cerah": 0.0, "berawan": 0.0, "hujan": 0.6, "badai": 1.0}

var world: Node
var cloud := 0.0
var rain := 0.0
var haze := 0.0
var _flash := 0.0
var _thunder_t := 6.0
var _layer: CanvasLayer
var _rect: ColorRect
var _mat: ShaderMaterial
var _fires := {}            # "pid:idx" -> Node3D
var _fire_sig := "-"
var _flood: MeshInstance3D
var _flood_id := ""
var _sync_t := 0.0
var _rain_player: AudioStreamPlayer
var _thunder_player: AudioStreamPlayer
var _flame_mesh: QuadMesh
var _smoke_mesh: QuadMesh
var _owned_centres: Array = []
var _owned_sig := -1


func _ready() -> void:
	_layer = CanvasLayer.new()
	_layer.layer = 4   # over the 3D world, under the colour grade (5) and the HUD (10)
	_layer.name = "WeatherOverlay"
	add_child(_layer)
	_rect = ColorRect.new()
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mat = ShaderMaterial.new()
	_mat.shader = Shader.new()
	_mat.shader.code = OVERLAY_SHADER
	_rect.material = _mat
	_rect.visible = false
	_layer.add_child(_rect)


# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	if world == null or world.sun == null:
		return
	var W = GS.sys.weather
	var playing: bool = world.state == "play" or world.state == "over"
	var outdoors: bool = world.inside == ""
	var want_cloud: float = CLOUD.get(W.today, 0.0) if playing else 0.0
	var want_rain: float = RAIN.get(W.today, 0.0) if playing else 0.0
	var want_haze: float = W.haze() if playing else 0.0
	var k := 1.0 - exp(-delta * 1.2)
	cloud = lerpf(cloud, want_cloud, k)
	rain = lerpf(rain, want_rain, k)
	haze = lerpf(haze, want_haze, k)
	if absf(cloud - want_cloud) < 0.002:
		cloud = want_cloud
	if absf(rain - want_rain) < 0.002:
		rain = want_rain
	if absf(haze - want_haze) < 0.002:
		haze = want_haze
	_light()
	_storm(delta, W.today == "badai" and playing)
	var r := rain if outdoors else 0.0
	var show := r > 0.01 or haze > 0.01 or _flash > 0.01
	_rect.visible = show
	if show:
		var vp: Vector2 = _rect.get_viewport_rect().size
		_mat.set_shader_parameter("aspect", vp.x / maxf(vp.y, 1.0))
		_mat.set_shader_parameter("rain", r)
		_mat.set_shader_parameter("wet", r)
		_mat.set_shader_parameter("haze", haze * (1.0 if outdoors else 0.4))
		_mat.set_shader_parameter("flash", _flash if outdoors else _flash * 0.3)
	_sound(delta, outdoors)
	_sync_t -= delta
	if _sync_t <= 0.0:
		_sync_t = 0.25
		_sync_fires()
		_sync_flood()
		_set_speed()


func _light() -> void:
	## runs after world._update_daylight (children process after their parent)
	var env: Environment = world.env
	# a grey day is darker and duller; smoke drains the colour (world.gd sets the base values)
	var sat: float = world.POST_SATURATION * (1.0 if world.quality_high else world.LQ_SATURATION)
	var bri: float = world.POST_BRIGHTNESS
	env.adjustment_saturation = sat * (1.0 - 0.28 * cloud - 0.4 * haze)
	env.adjustment_brightness = bri * (1.0 - 0.13 * cloud - 0.05 * haze)
	if cloud <= 0.001 and haze <= 0.001 and _flash <= 0.001:
		return
	world.sun.light_energy *= 1.0 - 0.62 * cloud - 0.25 * haze
	env.ambient_light_color = env.ambient_light_color.lerp(Color("8f9cb0"), cloud * 0.55).lerp(Color("c8a77a"), haze * 0.6)
	env.ambient_light_energy *= 1.0 - 0.12 * cloud
	env.background_color = env.background_color.lerp(Color("66737a"), cloud * 0.65).lerp(Color("a89470"), haze * 0.7)
	world.sun.light_color = world.sun.light_color.lerp(Color("d8dde6"), cloud * 0.5).lerp(Color("f0c890"), haze * 0.5)
	if world.inside == "":
		world.sun.light_energy += _flash * 1.4


func _storm(delta: float, storm: bool) -> void:
	_flash = maxf(0.0, _flash - minf(delta, 0.05) * 3.2)
	if not storm:
		return
	_thunder_t -= delta
	if _thunder_t <= 0.0:
		_thunder_t = randf_range(7.0, 16.0)
		_flash = 1.0
		_thunder()


# ------------------------------------------------------------------ fires
func _sync_fires() -> void:
	var W = GS.sys.weather
	var sig := ""
	for f in W.fires:
		sig += "%d:%d," % [int(f["pid"]), int(f["idx"])]
	if sig == _fire_sig:
		return
	_fire_sig = sig
	var want := {}
	for f in W.fires:
		want["%d:%d" % [int(f["pid"]), int(f["idx"])]] = true
	for key in _fires.keys():
		if not want.has(key):
			var n: Node3D = _fires[key]
			_fires.erase(key)
			if is_instance_valid(n):
				_douse(n)
	for key in want:
		if _fires.has(key) or not world.tile_views.has(key):
			continue
		var tv: Node3D = world.tile_views[key]
		var n := _make_fire()
		n.position = tv.position
		world.add_child(n)
		_fires[key] = n


func _douse(n: Node3D) -> void:
	## the flames go out at once, the last smoke drifts off
	for c in n.get_children():
		if c is CPUParticles3D:
			(c as CPUParticles3D).emitting = false
	get_tree().create_timer(3.2).timeout.connect(n.queue_free)


func _make_fire() -> Node3D:
	var root := Node3D.new()
	root.name = "LandFire"
	if _flame_mesh == null:
		_flame_mesh = QuadMesh.new()
		_flame_mesh.size = Vector2(0.6, 0.95)
		var fm := StandardMaterial3D.new()
		fm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		fm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		fm.vertex_color_use_as_albedo = true
		fm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		fm.albedo_texture = _soft_dot(true)
		_flame_mesh.material = fm
		_smoke_mesh = QuadMesh.new()
		_smoke_mesh.size = Vector2(1.7, 1.7)
		var sm := StandardMaterial3D.new()
		sm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		sm.vertex_color_use_as_albedo = true
		sm.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		sm.albedo_texture = _soft_dot(false)
		_smoke_mesh.material = sm
	var flame := CPUParticles3D.new()
	flame.amount = 22
	flame.lifetime = 0.8
	flame.mesh = _flame_mesh
	flame.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	flame.emission_sphere_radius = 0.55
	flame.direction = Vector3.UP
	flame.spread = 12.0
	flame.gravity = Vector3(0, 2.6, 0)
	flame.initial_velocity_min = 0.8
	flame.initial_velocity_max = 1.6
	flame.scale_amount_min = 1.0
	flame.scale_amount_max = 1.8
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.5))
	sc.add_point(Vector2(0.25, 1.0))
	sc.add_point(Vector2(1, 0.15))
	flame.scale_amount_curve = sc
	var fg := Gradient.new()
	fg.set_color(0, Color(1.0, 0.86, 0.32, 1.0))
	fg.add_point(0.35, Color(1.0, 0.46, 0.08, 0.95))
	fg.set_color(fg.get_point_count() - 1, Color(0.6, 0.1, 0.03, 0.0))
	flame.color_ramp = fg
	flame.position = Vector3(0, 0.25, 0)
	flame.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	flame.visibility_range_end = 80.0
	root.add_child(flame)
	var smoke := CPUParticles3D.new()
	smoke.amount = 16
	smoke.lifetime = 4.0
	smoke.mesh = _smoke_mesh
	smoke.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	smoke.emission_sphere_radius = 0.4
	smoke.direction = Vector3(0.25, 1, 0.1)
	smoke.spread = 15.0
	smoke.gravity = Vector3(0.4, 0.5, 0)
	smoke.initial_velocity_min = 1.1
	smoke.initial_velocity_max = 1.7
	smoke.scale_amount_min = 0.9
	smoke.scale_amount_max = 1.5
	var ss := Curve.new()
	ss.add_point(Vector2(0, 0.5))
	ss.add_point(Vector2(1, 3.0))
	smoke.scale_amount_curve = ss
	var sg := Gradient.new()
	sg.set_color(0, Color(0.2, 0.18, 0.16, 0.0))
	sg.add_point(0.12, Color(0.24, 0.22, 0.2, 0.88))
	sg.add_point(0.6, Color(0.42, 0.4, 0.37, 0.55))
	sg.set_color(sg.get_point_count() - 1, Color(0.6, 0.58, 0.55, 0.0))
	smoke.color_ramp = sg
	smoke.position = Vector3(0, 1.7, 0)   # above the flames, so they stay visible from the camera
	smoke.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	smoke.visibility_range_end = 120.0
	root.add_child(smoke)
	# scorched ground under the fire
	var scorch := GroundFx.blob(1.15, 0.55)
	scorch.position = Vector3(0, 0.03, 0)
	root.add_child(scorch)
	return root


static var _dots := {}


static func _soft_dot(hot: bool) -> Texture2D:
	## a round soft sprite (white; tinted by the particle colour)
	if _dots.has(hot):
		return _dots[hot]
	var n := 32
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	for y in n:
		for x in n:
			var u := (x + 0.5 - n * 0.5) / (n * 0.5)
			var v := (y + 0.5 - n * 0.5) / (n * 0.5)   # -1 top .. 1 bottom
			if hot:
				u /= clampf(0.35 + 0.65 * (v + 1.0) * 0.5, 0.2, 1.0)   # narrow tip at the top
			var d := Vector2(u, v).length()
			var a := clampf(1.0 - d, 0.0, 1.0)
			a = a * a * (3.0 - 2.0 * a)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	var tex := ImageTexture.create_from_image(img)
	_dots[hot] = tex
	return tex


# ------------------------------------------------------------------ flood
func _sync_flood() -> void:
	var id: String = GS.sys.weather.flood
	if id == _flood_id:
		return
	_flood_id = id
	if _flood:
		_flood.queue_free()
		_flood = null
	if id == "":
		return
	var c := Vector3.ZERO
	for v in world.layout.get("villages", []):
		if str(v["id"]) == id:
			c = world.v3(v["center"])
	# the water stands knee-deep over the village's low ground (the water shader masks
	# it out wherever the terrain is higher, with foam along the edge)
	var level: float = world.terrain_height(c.x, c.z) + 0.4
	_flood = MeshInstance3D.new()
	_flood.name = "Flood"
	var cm := CylinderMesh.new()
	cm.top_radius = 22.0
	cm.bottom_radius = 22.0
	cm.height = 0.02
	cm.radial_segments = 48
	cm.rings = 1
	_flood.mesh = cm
	var m := ShaderMaterial.new()
	m.shader = world.WATER_SHADER
	m.set_shader_parameter("height_tex", world.height_tex)
	m.set_shader_parameter("noise_tex", world.NOISE_TEX)
	m.set_shader_parameter("world_size", world.world_size)
	m.set_shader_parameter("water_level", level)
	m.set_shader_parameter("shallow", Color(0.76, 0.62, 0.42))
	m.set_shader_parameter("mid_col", Color(0.66, 0.5, 0.3))
	m.set_shader_parameter("deep", Color(0.5, 0.37, 0.22))
	m.set_shader_parameter("sheen", Color(0.86, 0.82, 0.72))
	m.set_shader_parameter("foam", Color(0.9, 0.84, 0.7))
	_flood.material_override = m
	_flood.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_flood.position = Vector3(c.x, level - 0.01, c.z)
	world.add_child(_flood)


func flood_node() -> Node3D:
	return _flood


func fire_nodes() -> Dictionary:
	return _fires


# ------------------------------------------------------------------ walking speed
func _set_speed() -> void:
	var pl: Node = world.player
	if pl == null or not ("speed_mult" in pl):
		return
	var sig := GS.owned_parcels()
	if sig != _owned_sig:
		_owned_sig = sig
		_owned_centres.clear()
		for p in GS.parcels:
			if p["owner"] == "player" or p["plasma"]:
				_owned_centres.append(world.v3(p["center"]))
	var m := 1.0
	var pp: Vector3 = pl.global_position
	var on_farm := false
	if world.inside == "":
		for c in _owned_centres:
			if absf(pp.x - c.x) < 13.0 and absf(pp.z - c.z) < 10.0:
				on_farm = true
				break
	if on_farm:
		m = GS.sys.tech.walk_mult()
	if GS.sys.weather.is_rainy() and world.inside == "" and not (on_farm and GS.sys.tech.owned("jalan")):
		m *= 0.88   # becek
	pl.speed_mult = m


# ------------------------------------------------------------------ sound
func _bus() -> String:
	return "Ambience" if AudioServer.get_bus_index("Ambience") >= 0 else "Master"


func _sound(delta: float, outdoors: bool) -> void:
	var want := rain * (1.0 if outdoors else 0.35)
	if want < 0.01 and _rain_player == null:
		return
	if _rain_player == null:
		_rain_player = AudioStreamPlayer.new()
		_rain_player.stream = _noise_loop()
		_rain_player.bus = _bus()
		_rain_player.volume_db = -60.0
		add_child(_rain_player)
		_rain_player.play()
	var db := linear_to_db(maxf(want, 0.0005)) - 14.0
	_rain_player.volume_db = lerpf(_rain_player.volume_db, db, 1.0 - exp(-delta * 2.0))
	if want < 0.01 and _rain_player.volume_db < -55.0:
		_rain_player.queue_free()
		_rain_player = null


func _thunder() -> void:
	if _thunder_player == null:
		_thunder_player = AudioStreamPlayer.new()
		_thunder_player.stream = _thunder_clip()
		_thunder_player.bus = _bus()
		add_child(_thunder_player)
	_thunder_player.volume_db = -8.0 if world.inside == "" else -16.0
	_thunder_player.pitch_scale = randf_range(0.8, 1.1)
	_thunder_player.play()


static func _noise_loop() -> AudioStreamWAV:
	## 1.5 s of soft rain: pink-ish noise, a little crackle, seamless loop (made once, ~24k samples)
	var rate := 16000
	var n := int(rate * 1.5)
	var data := PackedByteArray()
	data.resize(n * 2)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var b0 := 0.0
	var b1 := 0.0
	var vals := PackedFloat32Array()
	vals.resize(n)
	for i in n:
		var w := rng.randf_range(-1.0, 1.0)
		b0 = 0.97 * b0 + 0.03 * w
		b1 = 0.6 * b1 + 0.4 * w
		var v := b0 * 2.2 + (b1 - b0) * 0.35
		if rng.randf() < 0.004:
			v += rng.randf_range(-0.5, 0.5)   # drops on leaves
		vals[i] = v
	var fade := 1500
	for i in fade:   # cross-fade the end into the start
		var t := float(i) / fade
		vals[i] = vals[i] * t + vals[n - fade + i] * (1.0 - t)
	for i in n:
		data.encode_s16(i * 2, int(clampf(vals[i] * 0.55, -1.0, 1.0) * 32000.0))
	var s := AudioStreamWAV.new()
	s.format = AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate = rate
	s.stereo = false
	s.data = data
	s.loop_mode = AudioStreamWAV.LOOP_FORWARD
	s.loop_begin = 0
	s.loop_end = n - fade
	return s


static func _thunder_clip() -> AudioStreamWAV:
	## a 2.6 s rumble: brown noise with a sharp crack and a long decay
	var rate := 16000
	var n := int(rate * 2.6)
	var data := PackedByteArray()
	data.resize(n * 2)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var b := 0.0
	var c := 0.0
	for i in n:
		var t := float(i) / rate
		var w := rng.randf_range(-1.0, 1.0)
		b = clampf(b + w * 0.06, -1.0, 1.0) * 0.995
		c = 0.5 * c + 0.5 * w
		var env := exp(-t * 1.4) * (1.0 + 0.5 * sin(t * 9.0)) * smoothstep(0.0, 0.03, t)
		var v := b * 1.6 * env + c * exp(-t * 9.0) * 0.5
		data.encode_s16(i * 2, int(clampf(v, -1.0, 1.0) * 30000.0))
	var s := AudioStreamWAV.new()
	s.format = AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate = rate
	s.stereo = false
	s.data = data
	return s
