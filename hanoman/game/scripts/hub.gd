class_name Hub
extends RefCounted
## Pertapaan Pancawati: Rama's night camp. Rama gives the mission, Jembawan
## trades Kembang Wijayakusuma for permanent Kesaktian, Sugriwa gives combat
## tips, and the old well leads into Hutan Dandaka.

const SUGRIWA_TIPS := [
	"Don't just swing, Hanoman! Press Dash to dodge. While dashing, nothing can touch you.",
	"The Spell circle binds ogres and slows them down. Pound them while they're bound!",
	"Yuyu Kangkang is armored in front. Bind it with a Spell or hit it from behind.",
	"Buto Ijo is slow, but his slams are marked by a red circle. Don't stand in it!",
	"Buto Cakil always winds up before he lunges. Watch the red line, then dash aside.",
	"Sura and Baya are sworn rivals. If one's attack hits the other... heh heh heh.",
	"Each gate shows the reward that waits beyond it. Choose your path wisely.",
	"You keep your Wijayakusuma Blossoms even if you fall. Trade them to Elder Jembawan.",
]


static func build(_main: Node) -> Arena:
	var a := Arena.new()
	a.kind = "hub"
	a.biome = "hub"
	a.half = Vector2(12, 8.5)
	a.corner = 4.0
	return a


static func populate(main: Node, a: Arena) -> void:
	# backdrop: pendopo pavilion behind the north edge
	a.add_prop("pendopo", Vector2(0, -a.half.y - 4.5), 0.0, 1.0)
	a.add_prop("gamelan", Vector2(7.0, -5.5), -0.4)
	a.add_prop("arca", Vector2(-9.5, -5.5), 0.5)
	a.add_prop("arca", Vector2(9.5, 4.5), -2.4)
	for p in [Vector2(-3.5, -6.5), Vector2(3.5, -6.5), Vector2(-10, 1), Vector2(10, -1)]:
		a.add_torch(p)
	# the old well: start of the journey
	var well := Interactable.make("Set out for Dandaka Forest", func(i: Interactable):
		i.active = false
		main.start_run())
	well.add_child(Art.model("sumur"))
	var glow := OmniLight3D.new()
	glow.light_color = Color("5fe0c8")
	glow.light_energy = 1.6
	glow.omni_range = 4.0
	glow.position.y = 1.2
	well.add_child(glow)
	a.add_child(well)
	well.position = Vector3(0, 0, -5.2)
	a.obstacles.append([Vector2(0, -5.2), 1.0])
	_body(a, Vector2(0, -5.2), 0.9)
	# NPCs
	_npc(main, a, "rama", "King Rama", Vector2(-4.5, -3.5), func(): _talk_rama(main))
	_npc(main, a, "jembawan", "Sage Jembawan", Vector2(5.0, -2.5), func(): _talk_jembawan(main))
	_npc(main, a, "sugriwa", "King Sugriwa", Vector2(-7.0, 2.5), func(): _talk_sugriwa(main))
	for id in ["hanoman", "rama", "jembawan", "sugriwa"]:
		if not G.seen("codex_" + id):
			G.mark_seen("codex_" + id)
	# weapon rack: switch between the pusaka Jembawan has taught
	var rack := Interactable.make("Choose your weapon", func(_i): _weapon_rack(main))
	rack.add_child(_rack_model())
	a.add_child(rack)
	rack.position = Vector3(8.5, 0, 2.5)
	_body(a, Vector2(8.5, 2.5), 0.7)
	# lontar stand: the Codex of tales and the journey records
	var lontar := Interactable.make("Read the Lontar of Tales", func(_i):
		main.busy = true
		main.ui.codex_menu(func(): main.busy = false))
	lontar.add_child(Art.model("altar_dewa"))
	a.add_child(lontar)
	lontar.position = Vector3(-9.0, 0, -2.0)
	_body(a, Vector2(-9.0, -2.0), 0.7)
	# altar of vows (Heat), after the first victory
	if int(G.meta.wins) > 0:
		var altar := Interactable.make("Swear vows at the altar (Heat)", func(_i): _vow_altar(main))
		altar.add_child(Art.model("arca"))
		var fire := OmniLight3D.new()
		fire.light_color = Color(1.0, 0.4, 0.2)
		fire.light_energy = 2.0
		fire.omni_range = 4.0
		fire.position.y = 1.5
		altar.add_child(fire)
		a.add_child(altar)
		altar.position = Vector3(0.0, 0, 5.0)
		_body(a, Vector2(0.0, 5.0), 0.8)


static func _rack_model() -> Node3D:
	var n := Node3D.new()
	var bar := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1.8, 0.12, 0.12)
	bar.mesh = bm
	bar.material_override = Art.toon(Color("5a3a22"), 0.0, 1.6, true)
	bar.position.y = 1.4
	n.add_child(bar)
	for x in [-0.8, 0.8]:
		var post := MeshInstance3D.new()
		var pm := BoxMesh.new()
		pm.size = Vector3(0.14, 1.5, 0.14)
		post.mesh = pm
		post.material_override = bar.material_override
		post.position = Vector3(x, 0.75, 0)
		n.add_child(post)
	var k := 0
	for w in Weapons.ALL:
		if not Weapons.unlocked(w):
			continue
		var s := Staff.new()
		n.add_child(s)
		s.position = Vector3(-0.55 + k * 0.38, 0.75, 0.12)
		s.set_style(w)
		if w == "tongkat":
			s.set_length(1.4)
		k += 1
	return n


static func _weapon_rack(main: Node) -> void:
	main.busy = true
	var opts := []
	for w in Weapons.ALL:
		var d: Dictionary = Weapons.ALL[w]
		var got := Weapons.unlocked(w)
		opts.append({"title": d.name + ("  (equipped)" if Weapons.current() == w else ""),
			"desc": d.desc + ("" if got else "   (Jembawan can teach this)"), "id": w, "disabled": not got,
			"icon": "res://assets/icons/slot_serang.png"})
	main.ui.choice_menu("Weapon Rack", "Choose the pusaka Hanoman carries", opts, func(o: Dictionary):
		main.busy = false
		if o.is_empty():
			return
		G.meta.weapon = o.id
		G.save_meta()
		Weapons.dress(main.player.staff)
		Au.sfx("sfx_staff_draw", -2.0)
		G.say("Hanoman takes up the " + Weapons.ALL[o.id].name + ".", Color(1, 0.9, 0.6)), true)


static func _vow_altar(main: Node) -> void:
	main.busy = true
	var opts := []
	for id in G.VOWS:
		var on: bool = G.vows().has(id)
		opts.append({"title": ("[SWORN] " if on else "") + G.VOWS[id][0], "desc": G.VOWS[id][1], "id": id,
			"icon": "res://assets/icons/rw_bunga.png"})
	main.ui.choice_menu("Altar of Vows", "Heat %d  -  each vow adds +25%% Blossoms" % G.vows().size(), opts, func(o: Dictionary):
		if o.is_empty():
			main.busy = false
			return
		G.toggle_vow(o.id)
		Au.sfx("sfx_bell", -4.0)
		_vow_altar(main), true)

static func _body(a: Arena, pos: Vector2, r: float) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = Actor.L_WORLD
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = r
	cyl.height = 2.0
	cs.shape = cyl
	cs.position.y = 1.0
	body.add_child(cs)
	body.position = Vector3(pos.x, 0, pos.y)
	a.add_child(body)


static func _npc(main: Node, a: Arena, id: String, title: String, pos: Vector2, talk: Callable) -> void:
	var n := Npc.new()
	n.id = id
	a.add_child(n)
	n.position = Vector3(pos.x, 0, pos.y)
	var it := Interactable.make("Talk to " + title, func(_i): talk.call())
	n.add_child(it)
	_body(a, pos, 0.6)


static func intro(main: Node) -> void:
	G.mark_seen("intro")
	main.busy = true
	main.ui.dialog([
		["rama", "Hanoman, son of Batara Bayu. Rahwana has carried Dewi Sinta off to Alengka, across the sea."],
		["rama", "Take my ring. Show Sinta that Rama has never forgotten her."],
		["hanoman", "I am ready, my King. Neither Dandaka Forest nor the Kalimas Estuary will stop me."],
		["jembawan", "Be careful, child. At that estuary, Sura the shark and Baya the crocodile never stop fighting over territory. They say Rahwana has bought their loyalty."],
		["rama", "The gods go with you. Climb down the old well. It is the sages' secret path to the forest."],
	], func(): main.busy = false)


static func _talk_rama(main: Node) -> void:
	var lines := []
	if int(G.meta.wins) > 0:
		lines = [["rama", "You have conquered Sura and Baya, and the road to Alengka lies open. This land will remember your courage."],
			["rama", "(Thank you for playing the Hanoman Duta demo! Keep journeying to try other boons.)"]]
	elif int(G.meta.deaths) > 0:
		var pool := [
			[["rama", "You've returned, Hanoman. Those wounds are a mark of courage, not defeat."]],
			[["rama", "Each time you fall, you rise stronger. Such is the nature of wind: it never truly stops."]],
			[["rama", "Sinta is waiting. But I would rather you come back alive than arrive late and fall."], ["hanoman", "I will succeed this time, my Lord."]],
		]
		lines = pool[randi() % pool.size()]
	else:
		lines = [["rama", "The old well is your path, Hanoman. May the gods go with you."]]
	main.busy = true
	main.ui.dialog(lines, func(): main.busy = false)


## One-off conversations that unlock as the story moves on (checked first).
const STORY := [
	["first_death", "deaths", 1, [["sugriwa", "Hahaha! Look at you, Hanoman. Beaten black and blue by forest ogres!"],
		["hanoman", "Laugh all you like, brother. Tomorrow I go back, and they'll be the bruised ones."],
		["sugriwa", "That's my little brother. Remember: Dash, then strike. Not the other way round."]]],
	["met_kijang", "best_room", 5, [["sugriwa", "You met that golden deer? Kala Marica... he's the one who once lured Rama away from Sinta."],
		["hanoman", "This time he won't fool anyone ever again."]]],
	["deaths_5", "deaths", 5, [["sugriwa", "Five times you've come home bruised, and five times you've set out again."],
		["sugriwa", "The wanara army has begun singing your name, Hanoman. Don't let them down."]]],
	["reached_muara", "best_room", 7, [["sugriwa", "The Kalimas Estuary! You got that far? Your fur still reeks of shark and crocodile."],
		["hanoman", "Sura and Baya bicker all the time. Maybe that's their weakness."],
		["sugriwa", "Heh... just pit them against each other. Let them bite each other."]]],
	["first_win", "wins", 1, [["sugriwa", "Sura and Baya are beaten! All of Kiskenda is feasting for you, little brother!"],
		["hanoman", "It's not time to feast yet, brother. Alengka still lies across the sea."]]],
]


static func _talk_sugriwa(main: Node) -> void:
	main.busy = true
	for s in STORY:
		if not G.seen("story_" + s[0]) and int(G.meta.get(s[1], 0)) >= int(s[2]):
			G.mark_seen("story_" + s[0])
			main.ui.dialog(s[3], func(): main.busy = false)
			return
	main.ui.dialog([["sugriwa", SUGRIWA_TIPS[randi() % SUGRIWA_TIPS.size()]]], func(): main.busy = false)


static func _talk_jembawan(main: Node) -> void:
	main.busy = true
	var line := "Wijayakusuma Blossoms... the flowers of life. Bring them to me, and I will teach you the old powers."
	var bought := 0
	for id in G.meta.upgrades:
		bought += int(G.meta.upgrades[id])
	if bought >= 4:
		line = "Your power grows, child. Your bones are now hard as iron. There is still more I can teach."
	elif int(G.meta.bunga) >= 6:
		line = "How fragrant... you've brought many Wijayakusuma Blossoms. Come, choose the power you wish."
	elif int(G.meta.deaths) >= 3 and bought == 0:
		line = "You keep falling without learning a thing from me? Gather Blossoms, then come back to me."
	main.ui.dialog([["jembawan", line]], func():
		_open_shop(main))


static func _open_shop(main: Node) -> void:
	var opts := []
	for w in Weapons.ALL:
		if w == "tongkat" or Weapons.unlocked(w):
			continue
		var wc: int = Weapons.ALL[w].cost
		opts.append({"title": "Teach me the " + Weapons.ALL[w].name, "desc": Weapons.ALL[w].desc + "   -  %d Blossoms" % wc,
			"id": "weapon:" + w, "cost": wc, "disabled": int(G.meta.bunga) < wc, "icon": "res://assets/icons/slot_serang.png"})
	for id in G.UPGRADES:
		var u: Array = G.UPGRADES[id]
		var rank := G.up_rank(id)
		var maxed := rank >= int(u[3])
		var cost: int = 0 if maxed else int(u[2][rank])
		opts.append({"title": "%s  (%d/%d)" % [u[0], rank, int(u[3])],
			"desc": u[1] + ("" if maxed else "   —  %d Blossoms" % cost), "id": id, "cost": cost,
			"disabled": maxed or int(G.meta.bunga) < cost, "icon": "res://assets/icons/rw_bunga.png"})
	main.ui.choice_menu("Jembawan's Teachings", "Wijayakusuma Blossoms: %d" % int(G.meta.bunga), opts, func(o: Dictionary):
		if o.is_empty():
			main.busy = false
			return
		G.meta.bunga = int(G.meta.bunga) - int(o.cost)
		if String(o.id).begins_with("weapon:"):
			var w := String(o.id).substr(7)
			var ws: Array = G.meta.get("weapons", [])
			ws.append(w)
			G.meta.weapons = ws
			G.meta.weapon = w
			Weapons.dress(main.player.staff)
			G.say("Jembawan teaches you the " + Weapons.ALL[w].name + "! (switch at the weapon rack)", Color(1, 0.9, 0.6))
		else:
			G.meta.upgrades[o.id] = G.up_rank(o.id) + 1
		G.save_meta()
		Au.sfx("sfx_boon_pick")
		_open_shop(main), true)
