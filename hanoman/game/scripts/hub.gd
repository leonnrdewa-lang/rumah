class_name Hub
extends RefCounted
## Pertapaan Pancawati: Rama's night camp. Rama gives the mission, Jembawan
## trades Kembang Wijayakusuma for permanent Kesaktian, Sugriwa gives combat
## tips, and the old well leads into Hutan Dandaka.

const SUGRIWA_TIPS := [
	"Jangan cuma memukul, Hanoman! Tekan Lesat untuk menghindar. Selama melesat, tak ada yang bisa melukaimu.",
	"Lingkaran Ajian mengikat raksasa, membuat mereka lamban. Hajar mereka saat terikat!",
	"Yuyu Kangkang kebal dari depan. Ikat dia dengan Ajian atau pukul dari belakang.",
	"Buto Ijo lamban, tapi hantamannya ditandai lingkaran merah. Jangan berdiri di situ!",
	"Buto Cakil selalu ancang-ancang sebelum menerjang. Lihat garis merahnya, lalu melesat ke samping.",
	"Sura dan Baya itu musuh bebuyutan. Kalau serangan yang satu mengenai yang lain... hehehe.",
	"Tiap gapura menunjukkan hadiah di balik pintunya. Pilih jalanmu dengan bijak.",
	"Kembang Wijayakusuma tetap kau bawa pulang walau gugur. Tukarkan pada Kakang Jembawan.",
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
	var well := Interactable.make("Berangkat ke Hutan Dandaka", func(i: Interactable):
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
	_npc(main, a, "rama", "Prabu Rama", Vector2(-4.5, -3.5), func(): _talk_rama(main))
	_npc(main, a, "jembawan", "Resi Jembawan", Vector2(5.0, -2.5), func(): _talk_jembawan(main))
	_npc(main, a, "sugriwa", "Prabu Sugriwa", Vector2(-7.0, 2.5), func(): _talk_sugriwa(main))


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
	var it := Interactable.make("Bicara dengan " + title, func(_i): talk.call())
	n.add_child(it)
	_body(a, pos, 0.6)


static func intro(main: Node) -> void:
	G.mark_seen("intro")
	main.busy = true
	main.ui.dialog([
		["rama", "Hanoman, putra Batara Bayu. Rahwana telah membawa Dewi Sinta ke Alengka, di seberang samudra."],
		["rama", "Bawalah cincinku. Tunjukkan pada Sinta bahwa Rama tidak pernah melupakannya."],
		["hanoman", "Hamba siap, Gusti Prabu. Hutan Dandaka dan Muara Kalimas tak akan menghentikan hamba."],
		["jembawan", "Hati-hati, cucuku. Di muara itu Sura si hiu dan Baya si buaya tak pernah berhenti berebut wilayah. Kabarnya Rahwana telah membeli kesetiaan mereka."],
		["rama", "Para dewa menyertaimu. Masuklah ke sumur tua itu. Itu jalan rahasia para resi menuju hutan."],
	], func(): main.busy = false)


static func _talk_rama(main: Node) -> void:
	var lines := []
	if int(G.meta.wins) > 0:
		lines = [["rama", "Sura dan Baya telah kau taklukkan, dan jalan ke Alengka terbuka. Negeri ini akan mengingat keberanianmu."],
			["rama", "(Terima kasih sudah memainkan demo Hanoman Duta! Lanjutkan perjalanan untuk mencoba anugerah lain.)"]]
	elif int(G.meta.deaths) > 0:
		var pool := [
			[["rama", "Kau kembali, Hanoman. Luka itu tanda keberanian, bukan kekalahan."]],
			[["rama", "Setiap kali kau jatuh, kau bangkit lebih kuat. Itulah sifat angin: tak pernah benar-benar berhenti."]],
			[["rama", "Sinta menunggu. Tapi aku lebih suka kau kembali hidup daripada tiba terlambat dan gugur."], ["hanoman", "Hamba akan berhasil kali ini, Gusti."]],
		]
		lines = pool[randi() % pool.size()]
	else:
		lines = [["rama", "Sumur tua itu jalanmu, Hanoman. Semoga para dewa menyertaimu."]]
	main.busy = true
	main.ui.dialog(lines, func(): main.busy = false)


## One-off conversations that unlock as the story moves on (checked first).
const STORY := [
	["first_death", "deaths", 1, [["sugriwa", "Hahaha! Lihat dirimu, Hanoman. Babak belur dihajar raksasa hutan!"],
		["hanoman", "Tertawalah, Kakang. Besok aku kembali, dan mereka yang babak belur."],
		["sugriwa", "Itu baru adikku. Ingat: Lesat, lalu pukul. Jangan sebaliknya."]]],
	["met_kijang", "best_room", 5, [["sugriwa", "Kau bertemu kijang emas itu? Kala Marica... dialah yang dulu memancing Rama menjauh dari Sinta."],
		["hanoman", "Kali ini dia tidak akan menipu siapa pun lagi."]]],
	["deaths_5", "deaths", 5, [["sugriwa", "Lima kali kau pulang dengan tubuh lebam, tapi lima kali pula kau berangkat lagi."],
		["sugriwa", "Pasukan wanara mulai menyanyikan namamu, Hanoman. Jangan kecewakan mereka."]]],
	["reached_muara", "best_room", 7, [["sugriwa", "Muara Kalimas! Kau sudah sejauh itu? Bau amis hiu dan buaya masih menempel di bulumu."],
		["hanoman", "Sura dan Baya bertengkar sepanjang waktu. Mungkin itu kelemahan mereka."],
		["sugriwa", "Hehe... adu saja mereka. Biar mereka saling gigit."]]],
	["first_win", "wins", 1, [["sugriwa", "Sura dan Baya takluk! Seluruh Kiskenda berpesta untukmu, adikku!"],
		["hanoman", "Belum waktunya berpesta, Kakang. Alengka masih di seberang samudra."]]],
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
	var line := "Kembang Wijayakusuma... bunga kehidupan. Bawakan padaku, dan akan kuajarkan kesaktian lama."
	var bought := 0
	for id in G.meta.upgrades:
		bought += int(G.meta.upgrades[id])
	if bought >= 4:
		line = "Kesaktianmu tumbuh, cucuku. Tulang-tulangmu kini sekeras besi. Masih ada yang bisa kuajarkan."
	elif int(G.meta.bunga) >= 6:
		line = "Harum sekali... kau membawa banyak Kembang Wijayakusuma. Mari, pilih kesaktian yang kau mau."
	elif int(G.meta.deaths) >= 3 and bought == 0:
		line = "Kau terus gugur tanpa belajar apa pun dariku? Kumpulkan Kembang, lalu kembalilah padaku."
	main.ui.dialog([["jembawan", line]], func():
		_open_shop(main))


static func _open_shop(main: Node) -> void:
	var opts := []
	for id in G.UPGRADES:
		var u: Array = G.UPGRADES[id]
		var rank := G.up_rank(id)
		var maxed := rank >= int(u[3])
		var cost: int = 0 if maxed else int(u[2][rank])
		opts.append({"title": "%s  (%d/%d)" % [u[0], rank, int(u[3])],
			"desc": u[1] + ("" if maxed else "   —  %d Kembang" % cost), "id": id, "cost": cost,
			"disabled": maxed or int(G.meta.bunga) < cost, "icon": "res://assets/icons/rw_bunga.png"})
	main.ui.choice_menu("Kesaktian Jembawan", "Kembang Wijayakusuma: %d" % int(G.meta.bunga), opts, func(o: Dictionary):
		if o.is_empty():
			main.busy = false
			return
		G.meta.bunga = int(G.meta.bunga) - int(o.cost)
		G.meta.upgrades[o.id] = G.up_rank(o.id) + 1
		G.save_meta()
		Au.sfx("sfx_boon_pick")
		_open_shop(main), true)
