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


static func _talk_sugriwa(main: Node) -> void:
	main.busy = true
	main.ui.dialog([["sugriwa", SUGRIWA_TIPS[randi() % SUGRIWA_TIPS.size()]]], func(): main.busy = false)


static func _talk_jembawan(main: Node) -> void:
	main.busy = true
	main.ui.dialog([["jembawan", "Kembang Wijayakusuma... bunga kehidupan. Bawakan padaku, dan akan kuajarkan kesaktian lama."]], func():
		_open_shop(main))


static func _open_shop(main: Node) -> void:
	var opts := []
	for id in G.UPGRADES:
		var u: Array = G.UPGRADES[id]
		var rank := G.up_rank(id)
		var maxed := rank >= int(u[3])
		var cost: int = 0 if maxed else int(u[2][rank])
		opts.append({"title": "%s  %s" % [u[0], "★".repeat(rank) + "☆".repeat(int(u[3]) - rank)],
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
