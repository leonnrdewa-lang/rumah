extends Node
## All conversations and "business decisions": shops, the office, the mill,
## the broker, villagers and their land (buy fair, lowball, con, evict,
## franchise partnership, debt seizure), cooking-oil sales and morning events.

var world: Node
var ui: Node
var rng := RandomNumberGenerator.new()

const HQ_PORTRAIT := "icon_uang"

const CHAT := {
	"kakek": ["Dulu di sini hutan, Nak. Ada harimau, ada rangkong. Sekarang ada kamu.",
		"Pisang di kebun itu ditanam almarhumah istri Kakek. Manis sekali buahnya.",
		"Kakek tidak mengerti internet. Tapi Kakek mengerti tanah."],
	"ibu": ["Kalau mau beli, bawa surat yang jelas ya. Saya bacanya teliti, lho.",
		"Anak saya mau kuliah. Tapi kebun ini sumber penghasilan kami.",
		"Harga minyak goreng di warung naik terus. Siapa sih yang main harga?"],
	"kades": ["Desa kita terbuka untuk investasi! Asal... prosedurnya lancar, hehe.",
		"Surat tanah? Bisa diatur. Semua bisa diatur di desa ini.",
		"Saya ini pelayan masyarakat. Masyarakat yang punya amplop, terutama."],
	"nenek": ["Nenek tidak bisa baca, Cu. Tapi Nenek hafal batas kebun Nenek.",
		"Mau pisang goreng? Nenek goreng pakai minyak... yang mahal itu.",
		"Cucu Nenek kerja di kota. Katanya di sana sawit semua."],
	"pemuda": ["Aku pantau terus lho, Bang. Satu pohon ditebang, aku live-kan.",
		"Hutan kita tinggal sedikit. Kalau kebun ini jadi sawit, burung mau tinggal di mana?",
		"Followers-ku banyak. Jangan macam-macam sama kebunku."],
	"petani": ["Singkong dan cabai di kebun ini cukup buat makan sekeluarga.",
		"Katanya sawit bikin kaya. Kaya siapa dulu?",
		"Saya kerja dari subuh. Tanah ini keringat saya."],
	# ---- map v3: the hamlets
	"somad": ["Kopra saya dijual sampai Surabaya. Kamu jual apa? Oh, sawit. Hmm.",
		"Kalau mau beli kebun saya, siapkan uang tunai. Saya tidak terima 'bagi hasil'.",
		"Sepulang haji saya jadi lebih sabar. Tapi harga tanah saya tidak ikut sabar."],
	"ucok": ["Naik perahu saya? Lima ribu sekali seberang. Jembatan? Ah, itu buat orang yang tak suka seni.",
		"Sungai ini dulu jernih, Bang. Sekarang airnya warna teh susu.",
		"Kalau malam saya nyanyi di perahu. Ikan-ikan suka. Katanya."],
	"rian": ["Halo gaes, ini aku lagi sama Juragan Sawit! Coba Bang, senyum ke kamera.",
		"Videoku soal sungai keruh ditonton 200 ribu kali. Mau jadi video berikutnya?",
		"Aku cuma mau desa ini tetap hijau. Dan tetap ada sinyal."],
	"wati": ["Jamu kunyit asam, Juragan? Biar kuat kerja. Atau biar kuat menghadapi warga?",
		"Katanya Pak RT Bejo stempelnya bisa disewa. Eh, saya nggak bilang apa-apa ya.",
		"Gosip terbaru: katanya ada juragan sawit yang suka nyuruh preman. Siapa ya?"],
	"slamet": ["Getah karet saya harganya jatuh terus. Mungkin memang harus ganti sawit...",
		"Pohon karet itu ditanam bapak saya. Tiap goresan pisau ada ceritanya.",
		"Sabar itu kunci, Juragan. Tapi kunci rumah saya jangan diminta ya."],
	"dullah": ["Tanah ini tanah ulayat, Nak. Bukan milik saya sendiri, milik anak cucu kami.",
		"Batas kebun kami ditandai pohon durian tua. Nenek moyang yang menanamnya.",
		"Orang kota datang bawa peta. Kami sudah di sini sebelum peta itu dibuat."],
	"lastri": ["Anak-anak saya belajar bahwa hutan itu paru-paru dunia. Kamu dulu belajar apa?",
		"Kalau ada surat, saya baca dulu sampai titik terakhir. Kebiasaan guru.",
		"Gaji guru honorer itu kecil, Juragan. Tapi kebun ini membuat kami cukup."],
	"romlah": ["Rempeyek, Cu? Masih hangat. Minyaknya... ya, minyak yang mahal itu.",
		"Mata Nenek sudah rabun. Tulisan kecil-kecil itu Nenek tidak bisa baca.",
		"Cucu Nenek bilang, jangan tanda tangan apa-apa. Tapi cucu Nenek jauh di kota."],
	"darsih": ["Sejak sawit masuk dusun sebelah, sumur-sumur di sana kering. Mbok tidak bohong.",
		"Mbok sudah bantu lahirkan separuh warga dusun ini. Termasuk yang sekarang kerja buatmu.",
		"Jamu Mbok bisa sembuhkan masuk angin. Tapi bukan serakah."],
	"yanto": ["Saya dulu kerja di pabrik sawit. Di-PHK gara-gara 'efisiensi'. Lucu ya.",
		"Butuh uang buat biaya sekolah anak. Kalau harganya cocok, kita bicara.",
		"Kerja apa saja saya mau, Juragan. Asal dibayar, jangan cuma dijanjikan."],
	"karta": ["Kambing saya makan apa saja. Kemarin makan sandal Pak RT.",
		"Kebun rumput buat kambing ini jangan diganggu. Kambing juga butuh makan.",
		"Harga kambing naik pas Idul Adha. Harga kebun? Naik kalau kamu yang nanya."],
	"bidan": ["Semua orang di desa ini saya yang bantu lahirkan. Saya tahu siapa yang jujur.",
		"Posyandu butuh timbangan baru. Kalau mau CSR, itu lebih berguna dari foto-foto.",
		"Surat tanah saya lengkap dan asli. Saya simpan di lemari obat."],
	"rt": ["Surat keterangan domisili? Bisa. Surat keterangan tanah? Bisa juga... asal ada 'uang lelah'.",
		"Warga Dusun Selatan ini penurut kok, Juragan. Asal RT-nya diperhatikan.",
		"Saya ini RT teladan. Piagamnya saya beli... eh, saya dapat dari kecamatan."],
}
## map v3: named villagers without land (world.gd places them in their hamlet)
const EXTRAS := {
	"karim": {"name": "Pak Ustad Karim", "model": "char_kakek", "village": "selatan",
		"lines": ["Assalamualaikum, Juragan. Jangan lupa, rezeki itu titipan. Tanah juga.",
			"Musala kami bocor atapnya. Kalau mau sedekah, pintunya selalu terbuka.",
			"Orang yang mengambil hak orang lain, hisabnya berat, Juragan. Saya cuma mengingatkan."]},
	"tini": {"name": "Bu Tini", "model": "char_ibu", "village": "muara",
		"lines": ["Sayur, sayur! Kangkung dari pinggir sungai, masih segar!",
			"Dulu kangkung tumbuh di mana-mana. Sekarang sungainya keruh, kangkungnya kurus.",
			"Juragan mau pesan sayur buat buruh-buruhmu? Harga teman."]},
	"sari": {"name": "Dik Sari", "model": "char_anak", "village": "seberang", "radius": 6.0,
		"lines": ["Kakak lihat burung rangkong nggak? Kata Kakek dulu banyak di hutan sana.",
			"Aku mau jadi dokter kayak Bu Bidan! Atau jadi youtuber kayak Bang Rian.",
			"Jembatan kayu itu goyang-goyang kalau dilewati. Seru!"]},
	"budi": {"name": "Dik Budi", "model": "char_anak", "village": "barat", "radius": 6.0,
		"lines": ["Om, main layangan yuk! Di lapangan dekat sungai anginnya kencang.",
			"Kata Kakek Dullah, tanah ini punya kita semua. Om juga?",
			"Aku berani lompat dari jembatan ke sungai. Tapi Ibu marah."]},
	"eko": {"name": "Mas Eko (Ojek)", "model": "char_pemuda", "village": "sukamakmur",
		"lines": ["Ojek, Bang? Ke dusun mana saja goceng. Nyeberang jembatan tambah goceng.",
			"Jalan ke Dusun Utara becek kalau hujan. Kapan diaspal, ya?",
			"Truk sawit lewat terus, jalan jadi rusak. Siapa yang tanggung jawab, Bang?"]},
	"tigor": {"name": "Pak Mandor Tigor", "model": "char_buruh", "village": "utara",
		"lines": ["Saya mandor kebun. Mau cari buruh? Bayar di muka ya, Bos.",
			"Buruh sekarang susah dicari. Semua mau kerja di kota.",
			"Kebun sawit itu kejam, Bos. Tapi gajinya pasti. Kadang."]},
	"ipah": {"name": "Mak Ipah", "model": "char_nenek", "village": "bukit",
		"lines": ["Mak dulu menganyam tikar dari pandan hutan. Sekarang pandannya habis.",
			"Anak muda sekarang tidak mau ke hutan. Hutannya juga sudah tidak ada.",
			"Mau tikar, Nak? Ini yang terakhir, dari pandan yang terakhir."]},
	"rahmat": {"name": "Bang Rahmat (Nelayan)", "model": "char_petani", "village": "muara",
		"lines": ["Ikan di muara makin sedikit, Bang. Airnya bau pupuk.",
			"Perahu saya parkir di dermaga. Jangan disewa buat angkut TBS, ya.",
			"Kalau musim hujan sungai meluap. Jembatan beton itu satu-satunya yang kuat."]},
	"asep": {"name": "Kang Asep", "model": "char_buruh", "village": "barat",
		"lines": ["Saya tukang kayu. Jembatan kayu di Kali Kecil itu saya yang bikin.",
			"Kayu bagus sekarang mahal. Hutannya jadi kebun, kayunya jadi pagar.",
			"Mau bikin rumah panggung? Saya bisa, asal kayunya ada."]},
	"neneng": {"name": "Teh Neneng", "model": "char_ibu", "village": "utara",
		"lines": ["Warung kopi saya buka dari subuh. Mampir, Juragan, kopinya pahit tapi jujur.",
			"Pak Karta itu kambingnya sering masuk kebun orang. Pusing saya.",
			"Katanya ada lisensi franchise sawit. Franchise itu apa sih, Juragan? Semacam arisan?"]},
}
## passers-by walking between the hamlets (world.gd), and what they say
const WALKER_MODELS := ["char_petani", "char_ibu", "char_buruh", "char_pemuda", "char_nenek", "char_kakek",
	"char_anak", "char_ibu", "char_petani", "char_buruh", "char_pemuda", "char_ibu"]
const WALKER_LINES := ["Mau ke pasar dusun sebelah, Juragan. Jalan kaki, bensin mahal.",
	"Permisi, Juragan. Lewat, lewat...", "Panas sekali hari ini. Pohon peneduhnya sudah ditebang semua.",
	"Juragan dari kantor sawit itu, ya? Wah, orang penting.", "Saya mau jenguk saudara di seberang sungai.",
	"Katanya harga minyak goreng naik lagi. Benar, Juragan?", "Jalan-jalan sore, Juragan. Mumpung belum jadi kebun sawit semua."]
const CHAT_LANDLESS := ["Dulu saya punya kebun... sekarang punya tenda.", "Minyak goreng mahal, kebun tidak ada. Hidup makin berat.",
	"Kalau ada kerjaan, saya mau kok. Apa saja.", "Anak-anak tanya kenapa kebun kita jadi sawit. Saya bingung jawabnya."]
const KID := ["Om, kenapa pohonnya sama semua? Aku kangen pohon mangga.", "Om orang kaya ya? Bajunya batik mahal.",
	"Kata Ibu, jangan mau dikasih permen sama orang sawit.", "Om, kalau semua jadi sawit, kita main di mana?",
	"Aku mau jadi Juragan Sawit kayak Om! Atau jadi aktivis kayak Mas Joko."]


func _ready() -> void:
	rng.randomize()


func _portrait(model: String) -> String:
	return "portrait_" + model.replace("char_", "")


func vp(vid: String) -> String:
	return _portrait(GS.VILLAGERS[vid]["model"])


func say(portrait: String, speaker: String, text: String, next := Callable()) -> void:
	ui.dialog(portrait, speaker, text, [{"text": "Lanjut", "cb": next}] if next.is_valid() else [])


# ------------------------------------------------------------------ intro
func intro() -> void:
	say(HQ_PORTRAIT, "Telepon dari Pusat", "Halo, Juragan! Selamat, kamu resmi jadi pewaralaba Sawit The Franchise™ di Desa Sukamakmur!",
		func(): say(HQ_PORTRAIT, "Telepon dari Pusat", "Modal dari pusat: Rp 2 juta, 6 bibit, 3 karung pupuk, sebatang pancing, rumah mungil di timur kantor, dan sepetak lahan di samping kantor. Tiga pohon sudah berbuah, tinggal panen!",
			func(): ui.dialog(HQ_PORTRAIT, "Telepon dari Pusat", "Target pusat: kuasai SEMUA lahan desa ini. Caranya? Terserah kamu. Kami tidak mau tahu... asal jangan ketahuan. Klik-klik!",
				[{"text": "Siap, Pak Bos!", "cb": func(): ui.toast("Dekati pohon sawit berbuah di sebelah kiri kantor, lalu tekan E / tombol aksi.", "info")},
				 {"text": "Lihat cara main", "cb": func(): ui.show_help()}])))


# ------------------------------------------------------------------ services
func open_service(id: String) -> void:
	Sfx.play("door", 1.0, -6.0)
	match id:
		"kantor": open_kantor()
		"toko": open_toko()
		"warung": open_warung()
		"pabrik": open_pabrik()
		"calo": open_calo()


func open_kantor() -> void:
	var items: Array = []
	var workers_n := GS.workers.size()
	items.append({"icon": "icon_helm", "text": "Rekrut buruh (%d/%d)" % [workers_n, GS.MAX_WORKERS],
		"desc": "Tiap pagi memanen & menjual 8 pohon siap panen dan menebas 2 semak. Upah dibayar tiap pagi.",
		"price": GS.fmt_short(GS.PRICE["buruh_upah"]) + "/hari", "button": "Rekrut",
		"enabled": workers_n < GS.MAX_WORKERS, "cb": func(): _hire_generic()})
	if workers_n > 0:
		items.append({"icon": "icon_helm", "text": "Pecat satu buruh", "desc": "Hemat upah. Buruh pulang tanpa pesangon, tentu saja.",
			"button": "Pecat", "cb": func(): _fire_worker()})
	if not GS.upgrades["gerobak"]:
		items.append({"icon": "icon_gerobak", "text": "Gerobak dorong", "desc": "Kapasitas angkut TBS jadi 25.",
			"price": GS.fmt_short(GS.PRICE["gerobak"]), "cb": func(): _buy_upgrade("gerobak")})
	elif not GS.upgrades["truk"]:
		items.append({"icon": "icon_truk", "text": "Truk pickup bekas", "desc": "Kapasitas angkut TBS jadi 80.",
			"price": GS.fmt_short(GS.PRICE["truk"]), "cb": func(): _buy_upgrade("truk")})
	items.append({"icon": "icon_uang", "text": "Program CSR: bagi-bagi sembako", "desc": "Foto-foto sambil bagi beras. Reputasi +20, kecurigaan -5.",
		"price": GS.fmt_short(GS.PRICE["csr"]), "cb": func(): _csr()})
	if GS.upgrades["mesin"]:
		items.append({"icon": "icon_minyak", "text": "Harga minyak goreng: " + GS.OIL_PRICE_NAMES[GS.oil_price_level],
			"desc": "Normal Rp 25rb • Mahal Rp 55rb • Gila-gilaan Rp 95rb per jerigen. Makin mahal, makin dibenci.",
			"button": "Ubah", "cb": func():
				GS.oil_price_level = (GS.oil_price_level + 1) % 3
				ui.refresh_menu(open_kantor)})
	var need := GS.LICENSE_NEED - GS.controlled_parcels()
	items.append({"icon": "icon_kunci", "text": "Lisensi Sawit The Franchise™",
		"desc": ("Syarat: kuasai %d lahan (kurang %d)." % [GS.LICENSE_NEED, need]) if need > 0 else "Lahanmu sudah cukup luas. Saatnya jadi Raja Sawit!",
		"price": GS.fmt_short(GS.PRICE["lisensi"]), "enabled": need <= 0 and GS.money >= GS.PRICE["lisensi"],
		"cb": func(): _buy_license()})
	ui.menu("Kantor Sawit", "Uang: %s • Harga TBS hari ini: %s" % [GS.fmt_rp(GS.money), GS.fmt_rp(GS.tbs_price)], items, Callable(), "portrait_player")


func sleep_in_bed() -> void:
	## the kasur in the player's house (world.use_bed): the only way to end the day
	_sleep()


func _sleep() -> void:
	if GS.hour < 16.0:
		ui.dialog("portrait_player", "Kamu", "Masih jam %s. Yakin mau tidur sekarang?" % GS.clock_text(),
			[{"text": "Tidur saja, capek", "cb": func(): _do_sleep()}, {"text": "Nanti dulu", "cb": Callable()}])
	else:
		_do_sleep()


func _do_sleep() -> void:
	ui.close()
	Sfx.play("whoosh")
	GS.sleep()


func _hire_generic() -> void:
	if GS.workers.size() >= GS.MAX_WORKERS:
		return
	GS.workers.append({"id": "buruh%d" % rng.randi(), "name": "Buruh harian", "wage": GS.PRICE["buruh_upah"], "vid": ""})
	GS.toast.emit("Buruh baru siap kerja mulai besok pagi.", "good")
	GS.stats_changed.emit()
	world.refresh_workers()
	ui.refresh_menu(open_kantor)


func _fire_worker() -> void:
	if GS.workers.is_empty():
		return
	var w: Dictionary = GS.workers.pop_back()
	if w["vid"] != "":
		GS.villagers[w["vid"]]["worker"] = false
	GS.toast.emit(w["name"] + " dipecat.", "info")
	GS.stats_changed.emit()
	world.refresh_workers()
	ui.refresh_menu(open_kantor)


func _buy_upgrade(key: String) -> void:
	if GS.spend(GS.PRICE[key]):
		GS.upgrades[key] = true
		Sfx.play("cash")
		GS.toast.emit("Kapasitas angkut sekarang %d TBS!" % GS.capacity(), "good")
		GS.stats_changed.emit()
		ui.refresh_menu(open_kantor)


func _csr() -> void:
	if GS.spend(GS.PRICE["csr"]):
		GS.add_rep(20)
		GS.add_heat(-5)
		Sfx.play("cash")
		GS.toast.emit("Foto bagi-bagi sembako viral. Reputasi naik!", "good")
		ui.refresh_menu(open_kantor)


func _buy_license() -> void:
	if GS.controlled_parcels() < GS.LICENSE_NEED or not GS.spend(GS.PRICE["lisensi"]):
		return
	GS.upgrades["lisensi"] = true
	GS.check_quests()
	ui.close()
	world.state = "over"
	world.player.anim.play_action("cheer", 1.2)
	ui.show_ending()


func open_toko() -> void:
	var items: Array = [
		{"icon": "icon_bibit", "text": "Bibit sawit (1)", "desc": "Bibit unggul bersertifikat (katanya).", "price": GS.fmt_short(GS.PRICE["bibit"]),
			"cb": func(): _buy("bibit", 1, GS.PRICE["bibit"], open_toko)},
		{"icon": "icon_bibit", "text": "Bibit sawit (5)", "desc": "Paket hemat lima polybag.", "price": GS.fmt_short(GS.PRICE["bibit"] * 5),
			"cb": func(): _buy("bibit", 5, GS.PRICE["bibit"] * 5, open_toko)},
		{"icon": "icon_pupuk", "text": "Pupuk (1 karung)", "desc": "Mempercepat tumbuh 1 hari, atau buah dobel saat panen.", "price": GS.fmt_short(GS.PRICE["pupuk"]),
			"cb": func(): _buy("pupuk", 1, GS.PRICE["pupuk"], open_toko)},
		{"icon": "icon_pupuk", "text": "Pupuk (5 karung)", "desc": "Stok untuk sepetak lahan.", "price": GS.fmt_short(GS.PRICE["pupuk"] * 5),
			"cb": func(): _buy("pupuk", 5, GS.PRICE["pupuk"] * 5, open_toko)},
		{"icon": "icon_koin", "text": "Kopi sachet", "desc": "Energi +12. Pahit seperti kenyataan.", "price": GS.fmt_short(GS.PRICE["kopi"]),
			"cb": func(): _eat(12, GS.PRICE["kopi"], open_toko)},
	]
	if int(GS.inv.get("pancing", 0)) <= 0:
		items.append({"icon": "icon_pancing", "text": "Pancing bambu", "desc": "Untuk mancing di pantai, sungai, dermaga & jembatan.",
			"price": GS.fmt_short(GS.PRICE["pancing"]), "cb": func(): _buy("pancing", 1, GS.PRICE["pancing"], open_toko)})
	items.append({"icon": "icon_umpan", "text": "Umpan cacing (10)", "desc": "Satu umpan untuk sekali lempar kail. Punya: %d." % int(GS.inv.get("umpan", 0)),
		"price": GS.fmt_short(GS.PRICE["umpan"]), "cb": func(): _buy("umpan", 10, GS.PRICE["umpan"], open_toko)})
	_add_fish_sale(items, open_toko, "Koperasi menampung ikan untuk dijual ke kota.")
	ui.menu("Koperasi Desa Sukamakmur", "Bibit: %d • Pupuk: %d • Uang: %s" % [GS.inv["bibit"], GS.inv["pupuk"], GS.fmt_rp(GS.money)], items, Callable(), "portrait_petani")


func _buy(item: String, n: int, cost: int, reopen: Callable) -> void:
	if GS.spend(cost):
		GS.add_item(item, n)
		Sfx.play("coin")
		ui.refresh_menu(reopen)


func _eat(energy: float, cost: int, reopen: Callable) -> void:
	if GS.energy >= GS.max_energy - 1.0:
		GS.toast.emit("Kamu sudah kenyang dan segar.", "info")
		return
	if GS.spend(cost):
		GS.energy = minf(GS.max_energy, GS.energy + energy)
		GS.stats_changed.emit()
		Sfx.play("pop")
		ui.refresh_menu(reopen)


func open_warung() -> void:
	var gossip := _gossip()
	var items: Array = [
		{"icon": "icon_koin", "text": "Nasi bungkus + teh manis", "desc": "Energi +40.", "price": GS.fmt_short(GS.PRICE["nasi"]),
			"cb": func(): _eat(40, GS.PRICE["nasi"], open_warung)},
	]
	var oil := int(GS.inv["minyak"])
	if oil > 0:
		items.append({"icon": "icon_minyak", "text": "Jual semua minyak goreng ke warung (%d)" % oil,
			"desc": "Harga grosir Rp 30rb/jerigen. Mak Inah menjualnya lagi ke warga.",
			"price": GS.fmt_short(oil * GS.PRICE["minyak_grosir"]), "button": "Jual", "cb": func(): _sell_oil_wholesale()})
	_add_fish_sale(items, open_warung, "Mak Inah memasaknya jadi lauk warung.")
	ui.menu("Warung Mak Inah", "\"" + gossip + "\"", items, Callable(), "portrait_ibu")


func _add_fish_sale(items: Array, reopen: Callable, desc: String) -> void:
	var n := GS.fish_count()
	if n <= 0:
		return
	var icon := "ikan_nila"
	for id in GS.FISH:
		if int(GS.inv.get(id, 0)) > 0:
			icon = id
			break
	items.append({"icon": icon, "text": "Jual semua ikan (%d ekor)" % n, "desc": desc,
		"price": GS.fmt_short(GS.fish_value()), "button": "Jual", "cb": func(): sell_fish(reopen)})


func sell_fish(reopen := Callable()) -> int:
	var got := GS.sell_all_fish()
	if got > 0:
		Sfx.play("cash")
		world.float_text(world.player.global_position, "+" + GS.fmt_short(got), Color("2f6d2a"))
		if reopen.is_valid():
			ui.refresh_menu(reopen)
	return got


func _gossip() -> String:
	if GS.heat >= 70:
		return "Hati-hati, Juragan. Katanya ada Satgas mau turun ke desa minggu ini."
	if GS.rep <= -40:
		return "Warga lagi kumpul-kumpul. Katanya mau demo ke kantormu."
	for vid in GS.villagers:
		var v: Dictionary = GS.villagers[vid]
		if v["status"] == "owner" and not GS.parcel_of(vid)["plasma"] and GS.VILLAGERS[vid]["tipu"] >= 0.8:
			return "%s itu polos sekali. Surat apa saja pasti ditandatangani." % GS.vname(vid)
	return "Harga TBS hari ini %s. Pabrik di timur buka sampai malam." % GS.fmt_rp(GS.tbs_price)


func _sell_oil_wholesale() -> void:
	var oil := int(GS.inv["minyak"])
	if oil <= 0:
		return
	GS.take_item("minyak", oil)
	GS.add_money(oil * GS.PRICE["minyak_grosir"])
	GS.stats["oil_sold"] += oil
	Sfx.play("cash")
	ui.refresh_menu(open_warung)


func open_pabrik() -> void:
	var tbs := int(GS.inv["tbs"])
	var items: Array = []
	items.append({"icon": "icon_tbs", "text": "Jual semua TBS (%d tandan)" % tbs,
		"desc": "Harga hari ini %s per tandan." % GS.fmt_rp(GS.tbs_price), "price": GS.fmt_short(tbs * GS.tbs_price),
		"button": "Jual", "enabled": tbs > 0, "cb": func(): _sell_tbs()})
	if not GS.upgrades["mesin"]:
		items.append({"icon": "icon_minyak", "text": "Beli Mesin Olah Minyak", "desc": "Olah TBS jadi minyak goreng (1 TBS → 3 jerigen). Lalu jual ke warga... dengan harga sesukamu.",
			"price": GS.fmt_short(GS.PRICE["mesin"]), "cb": func():
				if GS.spend(GS.PRICE["mesin"]):
					GS.upgrades["mesin"] = true
					Sfx.play("cash")
					GS.check_quests()
					GS.stats_changed.emit()
					ui.refresh_menu(open_pabrik)})
	else:
		items.append({"icon": "icon_minyak", "text": "Olah 1 TBS jadi 3 jerigen minyak", "desc": "Biaya olah Rp 10rb.",
			"price": GS.fmt_short(GS.PRICE["olah"]), "button": "Olah", "enabled": tbs > 0, "cb": func(): _process_oil(1)})
		if tbs > 1:
			items.append({"icon": "icon_minyak", "text": "Olah semua TBS (%d)" % tbs, "desc": "Jadi %d jerigen minyak goreng." % (tbs * 3),
				"price": GS.fmt_short(GS.PRICE["olah"] * tbs), "button": "Olah", "cb": func(): _process_oil(tbs)})
	ui.menu("Pabrik Kelapa Sawit", "TBS dibawa: %d/%d • Minyak: %d jerigen" % [tbs, GS.capacity(), GS.inv["minyak"]], items, Callable(), "portrait_buruh")


func _sell_tbs() -> void:
	var tbs := int(GS.inv["tbs"])
	if tbs <= 0:
		return
	GS.take_item("tbs", tbs)
	GS.add_money(tbs * GS.tbs_price)
	GS.stats["tbs_sold"] += tbs
	Sfx.play("cash")
	world.float_text(world.player.global_position, "+" + GS.fmt_short(tbs * GS.tbs_price), Color("2f6d2a"))
	GS.check_quests()
	ui.refresh_menu(open_pabrik)


func _process_oil(n: int) -> void:
	if int(GS.inv["tbs"]) < n or not GS.spend(GS.PRICE["olah"] * n):
		return
	GS.take_item("tbs", n)
	GS.add_item("minyak", n * 3)
	Sfx.play("pop")
	ui.refresh_menu(open_pabrik)


func open_calo() -> void:
	var items: Array = [
		{"icon": "icon_surat", "text": "Surat tanah palsu", "desc": "Cap basah, tanda tangan meyakinkan. Untuk warga yang kurang teliti.",
			"price": GS.fmt_short(GS.PRICE["surat"]), "cb": func(): _buy("surat", 1, GS.PRICE["surat"], open_calo)},
		{"icon": "icon_helm", "text": "Sewa preman Bang Codet (%d siap)" % GS.upgrades["preman"],
			"desc": "Untuk satu kali 'relokasi sukarela'. Dijamin cepat, tidak dijamin sopan.",
			"price": GS.fmt_short(GS.PRICE["preman"]), "cb": func():
				if GS.spend(GS.PRICE["preman"]):
					GS.upgrades["preman"] = int(GS.upgrades["preman"]) + 1
					Sfx.play("cash")
					ui.refresh_menu(open_calo)},
		{"icon": "icon_uang", "text": "Titip amplop ke oknum", "desc": "Kecurigaan -35. Tidak ada kuitansi.",
			"price": GS.fmt_short(GS.PRICE["amplop"]), "cb": func():
				if GS.spend(GS.PRICE["amplop"]):
					GS.add_heat(-35)
					GS.add_rep(-3)
					GS.stats["bribes"] += 1
					Sfx.play("cash")
					GS.toast.emit("Amplop diterima. 'Kasus' mendadak hilang.", "good")
					ui.refresh_menu(open_calo)},
	]
	ui.menu("Bang Jeki, Calo Serba Bisa", "\"Mau beres cepat? Abang bisa atur, asal ada 'uang rokok'.\"", items, Callable(), "portrait_calo")


# ------------------------------------------------------------------ villagers
func talk(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var npc: Npc = world.npcs[vid]
	npc.talking = true
	npc.talk_target = world.player
	var p: Dictionary = GS.parcel_of(vid)
	var greet := _greeting(vid)
	var choices: Array = []
	var chatted: bool = int(v["talk_day"]) == GS.day
	choices.append({"text": "Ngobrol santai", "hint": "" if not chatted else "sudah hari ini", "cb": func(): _chat(vid)})
	if v["status"] == "owner" and not p["plasma"]:
		choices.append({"text": "Soal kebunmu...", "cb": func(): land_menu(vid)})
	if v["status"] == "owner" and p["plasma"]:
		choices.append({"text": "Soal kemitraan franchise...", "cb": func(): plasma_menu(vid)})
	if v["status"] == "owner" and not p["plasma"] and v["debt"] >= GS.VILLAGERS[vid]["value"] * 0.5:
		choices.append({"text": "Sita kebun untuk bayar utang", "hint": "utang " + GS.fmt_short(v["debt"]), "cb": func(): _seize_for_debt(vid)})
	if int(GS.inv["minyak"]) > 0:
		var price: int = GS.OIL_PRICES[GS.oil_price_level]
		choices.append({"text": "Tawarkan minyak goreng", "hint": GS.fmt_short(price), "enabled": int(v["oil_day"]) != GS.day,
			"cb": func(): _sell_oil(vid)})
	if int(GS.upgrades["preman"]) > 0 and int(v["money"]) >= 50000:
		choices.append({"text": "Suruh preman memalak uangnya", "hint": "rampok " + GS.fmt_short(v["money"]), "cb": func(): _extort(vid)})
	if v["status"] == "landless" and not v["worker"]:
		choices.append({"text": "Tawari kerja jadi buruh", "hint": GS.fmt_short(GS.PRICE["buruh_murah"]) + "/hari",
			"enabled": GS.workers.size() < GS.MAX_WORKERS, "cb": func(): _hire_villager(vid)})
	choices.append({"text": "Pamit", "cb": Callable()})
	ui.dialog(vp(vid), GS.vname(vid), greet, choices, func(): _end_talk(vid))


func _end_talk(vid: String) -> void:
	var npc: Npc = world.npcs[vid]
	npc.talking = false


func _greeting(vid: String) -> String:
	var v: Dictionary = GS.villagers[vid]
	var t: float = v["trust"]
	if v["status"] == "landless":
		if v.get("evicted", false):
			return "...Mau apa lagi kamu ke sini? Rumah kami sudah kalian 'rapikan'."
		return "Oh, Juragan. Kebun saya sekarang sudah jadi milikmu. Ada perlu apa?"
	if t >= 70:
		return "Eh, Juragan! Mampir, mampir. Mau kopi?"
	if t <= 25:
		return "Kamu lagi. Mau apa?"
	return "Selamat %s, Juragan. Ada yang bisa dibantu?" % _time_word()


func _time_word() -> String:
	if GS.hour < 11:
		return "pagi"
	if GS.hour < 15:
		return "siang"
	if GS.hour < 18.5:
		return "sore"
	return "malam"


func _chat(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var line: String
	if v["status"] == "landless":
		line = CHAT_LANDLESS[rng.randi() % CHAT_LANDLESS.size()]
	else:
		var lines: Array = CHAT[vid]
		line = lines[rng.randi() % lines.size()]
	if int(v["talk_day"]) != GS.day:
		v["talk_day"] = GS.day
		v["trust"] = minf(100.0, v["trust"] + 6.0)
		line += "\n(Kepercayaan +6)"
	say(vp(vid), GS.vname(vid), line)


func land_menu(vid: String) -> void:
	var d: Dictionary = GS.VILLAGERS[vid]
	var v: Dictionary = GS.villagers[vid]
	var value: int = d["value"]
	var choices: Array = []
	choices.append({"text": "Beli harga wajar", "hint": GS.fmt_short(value), "enabled": GS.money >= value, "cb": func(): _buy_fair(vid)})
	choices.append({"text": "Tawar murah", "hint": GS.fmt_short(int(value * 0.45)), "enabled": GS.money >= int(value * 0.45), "cb": func(): _lowball(vid)})
	choices.append({"text": "Tipu pakai surat palsu", "hint": "punya %d surat" % GS.inv["surat"], "enabled": int(GS.inv["surat"]) > 0,
		"cb": func(): _fraud(vid)})
	choices.append({"text": "Rampas paksa (gusur) pakai preman", "hint": "preman siap: %d" % GS.upgrades["preman"], "enabled": int(GS.upgrades["preman"]) > 0,
		"cb": func(): _evict(vid)})
	if d.get("sogok", false):
		var cost := int(value * 0.5) + 1500000
		choices.append({"text": "Selipkan amplop tebal", "hint": GS.fmt_short(cost), "enabled": GS.money >= cost, "cb": func(): _bribe_kades(vid, cost)})
	choices.append({"text": "Tawarkan kemitraan franchise", "hint": "biaya " + GS.fmt_short(GS.PRICE["franchise_fee"]), "cb": func(): _offer_franchise(vid)})
	choices.append({"text": "Batal", "cb": Callable()})
	var mood := "percaya padamu" if v["trust"] >= 60 else ("ragu-ragu" if v["trust"] >= 35 else "curiga padamu")
	ui.dialog(vp(vid), GS.vname(vid), "Kebun saya? Luasnya %d petak, harganya sekitar %s. (Dia terlihat %s.)" % [GS.tile_count(), GS.fmt_rp(value), mood],
		choices, func(): _end_talk(vid))


func _acquire(vid: String, how: String) -> void:
	var p: Dictionary = GS.parcel_of(vid)
	var v: Dictionary = GS.villagers[vid]
	p["owner"] = "player"
	p["plasma"] = false
	p["name"] = "Lahan Sawit #%d" % (GS.owned_parcels())
	v["status"] = "landless"
	GS.stats["land_" + how] += 1
	GS.parcel_changed.emit(int(p["id"]))
	GS.villager_changed.emit(vid)
	GS.check_quests()
	GS.stats_changed.emit()
	Sfx.play("quest")
	ui.toast("Kebun %s sekarang milikmu! Tebas semaknya lalu tanam sawit." % GS.vname(vid), "good")


func _buy_fair(vid: String) -> void:
	var value: int = GS.VILLAGERS[vid]["value"]
	if not GS.spend(value):
		return
	GS.villagers[vid]["money"] += value
	GS.add_rep(8)
	for other in GS.villagers:
		GS.villagers[other]["trust"] = minf(100.0, GS.villagers[other]["trust"] + 5.0)
	Sfx.play("cash")
	_acquire(vid, "fair")
	say(vp(vid), GS.vname(vid), "Terima kasih, Juragan. Harganya pantas. Semoga kebun ini membawa berkah... untuk kita semua.")


func _lowball(vid: String) -> void:
	var d: Dictionary = GS.VILLAGERS[vid]
	var v: Dictionary = GS.villagers[vid]
	var chance: float = clampf(d["tawar"] * (0.6 + v["trust"] / 125.0) + GS.rep / 300.0, 0.03, 0.95)
	var price := int(d["value"] * 0.45)
	if rng.randf() < chance:
		if not GS.spend(price):
			return
		v["money"] += price
		GS.add_rep(-3)
		Sfx.play("cash")
		_acquire(vid, "cheap")
		say(vp(vid), GS.vname(vid), "Hmm... ya sudah, saya butuh uangnya sekarang. Ambil saja kebunnya. (Dia menghela napas panjang.)")
	else:
		v["trust"] = maxf(0.0, v["trust"] - 20.0)
		GS.add_rep(-2)
		Sfx.play("bad")
		say(vp(vid), GS.vname(vid), "Segitu? Kamu kira kebun saya kebun kacang? Tidak! (Kepercayaan -20)")


func _fraud(vid: String) -> void:
	var d: Dictionary = GS.VILLAGERS[vid]
	var v: Dictionary = GS.villagers[vid]
	if not GS.take_item("surat"):
		return
	var chance: float = clampf(d["tipu"] + (v["trust"] - 50.0) / 250.0 - GS.heat / 400.0, 0.03, 0.97)
	var pay := int(d["value"] * 0.1)
	if rng.randf() < chance:
		GS.money -= mini(pay, GS.money)
		v["money"] += pay
		GS.add_heat(18.0 + (10.0 if d.get("aktivis", false) else 0.0))
		GS.add_rep(-6)
		Sfx.play("cash")
		_acquire(vid, "fraud")
		say(vp(vid), GS.vname(vid), "Surat apa ini, Juragan? ...Oh, 'surat bantuan pemerintah'? Ya sudah, saya cap jempol di sini. Uang %s ini buat saya?" % GS.fmt_short(pay))
	else:
		v["trust"] = maxf(0.0, v["trust"] - 40.0)
		GS.add_heat(30)
		GS.add_rep(-12)
		Sfx.play("bad")
		say(vp(vid), GS.vname(vid), "Ini surat palsu! Capnya saja masih basah! Saya laporkan ke Pak Kades! (Kecurigaan +30)")


func _evict(vid: String) -> void:
	var d: Dictionary = GS.VILLAGERS[vid]
	var v: Dictionary = GS.villagers[vid]
	GS.upgrades["preman"] = int(GS.upgrades["preman"]) - 1
	GS.add_heat(38.0 + (20.0 if d.get("aktivis", false) else 0.0))
	GS.add_rep(-30)
	for other in GS.villagers:
		GS.villagers[other]["trust"] = maxf(0.0, GS.villagers[other]["trust"] - 15.0)
	v["evicted"] = true
	_acquire(vid, "seized")
	world.npcs[vid].emote("!!", 4.0)
	var house: Vector3 = world.door_points.get(GS.VILLAGERS[vid]["home"], world.player.global_position)
	world.spawn_temp_actor("char_preman", "Bang Codet", house + Vector3(1.2, 0, 1.0), 2.5)
	world.spawn_temp_actor("char_preman", "Anak buah Codet", house + Vector3(-1.4, 0, 1.4), 2.5)
	var extra := (" %s sempat live di media sosial... (Kecurigaan ekstra!)" % GS.vname(vid)) if d.get("aktivis", false) else ""
	ui.info_panel("Relokasi 'Sukarela'", ["Bang Codet dan kawan-kawan datang membawa pentungan dan senyum ramah.",
		"%s dan keluarganya kini tinggal di tenda biru dekat warung." % GS.vname(vid),
		"Kecurigaan +%d • Reputasi -30 • Semua warga makin tidak percaya padamu.%s" % [38 + (20 if d.get("aktivis", false) else 0), extra]], "...Lanjut", Callable(), ui.RED)


func _extort(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var loot := int(v["money"])
	GS.upgrades["preman"] = int(GS.upgrades["preman"]) - 1
	v["money"] = 0
	v["trust"] = 0.0
	GS.add_money(loot)
	GS.add_heat(22)
	GS.add_rep(-15)
	Sfx.play("cash")
	world.npcs[vid].emote("!!", 4.0)
	world.spawn_temp_actor("char_preman", "Bang Codet", world.npcs[vid].global_position + Vector3(1.2, 0, 0.8), 2.0)
	say(vp(vid), GS.vname(vid), "Ampun, Bang! Ini uang tabungan buat sekolah anak... Ambil, ambil saja! (Kamu merampok %s. Kecurigaan +22, reputasi -15)" % GS.fmt_rp(loot))


func _bribe_kades(vid: String, cost: int) -> void:
	if not GS.spend(cost):
		return
	GS.villagers[vid]["money"] += cost
	GS.add_heat(-15)
	GS.add_rep(-5)
	GS.stats["bribes"] += 1
	Sfx.play("cash")
	_acquire(vid, "cheap")
	say(vp(vid), GS.vname(vid), "Wah, tebal sekali... 'dokumennya'. Baik, kebun saya serahkan demi pembangunan desa. Soal laporan warga, biar saya yang urus.")


func _offer_franchise(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var fee: int = GS.PRICE["franchise_fee"]
	if v["trust"] < 30:
		say(vp(vid), GS.vname(vid), "Kemitraan? Dari kamu? Tidak, terima kasih.")
		return
	ui.dialog(vp(vid), GS.vname(vid), "Jadi saya tetap pemilik, tapi kebunnya ditanami sawit, hasilnya dibagi 60 untuk Juragan, 40 untuk saya? Biaya waralabanya %s... saya cuma punya %s." % [GS.fmt_rp(fee), GS.fmt_rp(v["money"])],
		[{"text": "Sisanya ngutang saja ke saya (bunga ringan 5%/hari)", "cb": func(): _sign_franchise(vid)},
		 {"text": "Tidak jadi", "cb": Callable()}], func(): _end_talk(vid))


func _sign_franchise(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var p: Dictionary = GS.parcel_of(vid)
	var fee: int = GS.PRICE["franchise_fee"]
	var paid := mini(fee, int(v["money"]))
	v["money"] -= paid
	v["debt"] += fee - paid
	GS.add_money(paid)
	p["plasma"] = true
	for i in p["tiles"].size():
		p["tiles"][i] = {"s": "palm", "st": 0, "g": 0, "f": false, "fr": false, "fd": 0}
	GS.stats["franchise"] += 1
	GS.add_rep(2)
	GS.parcel_changed.emit(int(p["id"]))
	GS.check_quests()
	Sfx.play("quest")
	say(vp(vid), GS.vname(vid), "Baik, saya tanda tangan. Semoga sawit ini bikin kami sejahtera seperti di iklan. (Utang: %s)" % GS.fmt_rp(v["debt"]))


func plasma_menu(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var value: int = GS.VILLAGERS[vid]["value"]
	var choices: Array = []
	if v["debt"] >= value * 0.5:
		choices.append({"text": "Sita kebun untuk bayar utang", "hint": "utang " + GS.fmt_short(v["debt"]), "cb": func(): _seize_for_debt(vid)})
	choices.append({"text": "Kembali", "cb": Callable()})
	var ready := 0
	for t in GS.parcel_of(vid)["tiles"]:
		if t["s"] == "palm" and int(t["st"]) == 3:
			ready += 1
	ui.dialog(vp(vid), GS.vname(vid), "Pohon dewasa di kebun saya: %d. Utang saya ke Juragan: %s. %s" % [ready, GS.fmt_rp(v["debt"]),
		"Bunganya kok cepat sekali naiknya ya..." if v["debt"] > 0 else "Alhamdulillah sudah lunas."], choices, func(): _end_talk(vid))


func _seize_for_debt(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	v["debt"] = 0
	GS.add_heat(8)
	GS.add_rep(-10)
	_acquire(vid, "debt")
	say(vp(vid), GS.vname(vid), "Kebun saya disita? Tapi... ini kan cuma utang minyak goreng dan biaya waralaba... (Semuanya sah secara hukum. Hampir.)")


func _sell_oil(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	var level: int = GS.oil_price_level
	var price: int = GS.OIL_PRICES[level]
	var landless: bool = v["status"] == "landless"
	var chance: float = [0.92, 0.55, 0.28][level] + GS.rep / 250.0
	if landless:
		chance = 1.0  # tidak punya kebun, tidak punya pilihan
	if rng.randf() > chance:
		v["oil_day"] = GS.day
		say(vp(vid), GS.vname(vid), "%s sejerigen? Mahal sekali! Saya goreng pakai air saja." % GS.fmt_rp(price))
		return
	if not GS.take_item("minyak"):
		return
	v["oil_day"] = GS.day
	var on_credit := false
	if v["money"] >= price:
		v["money"] -= price
		GS.add_money(price)
	else:
		v["debt"] += price
		on_credit = true
	GS.stats["oil_sold"] += 1
	GS.stats["oil_villager"] += 1
	GS.add_rep([1.0, -2.0, -5.0][level])
	GS.add_heat([0.0, 1.0, 3.0][level])
	Sfx.play("coin")
	GS.check_quests()
	var line := "Terpaksa beli, Juragan. Dapur harus tetap ngebul." if level > 0 else "Terima kasih, harganya wajar."
	if on_credit:
		line = "Uang saya habis... catat sebagai utang dulu ya, Juragan. (Utang: %s)" % GS.fmt_rp(v["debt"])
	say(vp(vid), GS.vname(vid), line)


func _hire_villager(vid: String) -> void:
	var v: Dictionary = GS.villagers[vid]
	v["worker"] = true
	GS.workers.append({"id": vid, "name": GS.vname(vid), "wage": GS.PRICE["buruh_murah"], "vid": vid})
	GS.stats_changed.emit()
	world.refresh_workers()
	say(vp(vid), GS.vname(vid), "Kerja di kebun yang dulu milik saya sendiri... dengan upah %s sehari. Ya sudah, daripada tidak makan." % GS.fmt_short(GS.PRICE["buruh_murah"]))


func talk_extra(id: String) -> void:
	if id == "anak":
		say("portrait_anak", "Dik Udin", KID[rng.randi() % KID.size()])
	elif EXTRAS.has(id):
		var e: Dictionary = EXTRAS[id]
		var lines: Array = e["lines"]
		var n: Npc = world.extras.get(id)
		if n:
			n.talking = true
			n.talk_target = world.player
		say(_portrait(e["model"]), e["name"], lines[rng.randi() % lines.size()])


func talk_walker(i: int) -> void:
	var n: Npc = world.walkers[i]
	n.talking = true
	n.talk_target = world.player
	say(_portrait(WALKER_MODELS[i % WALKER_MODELS.size()]), "Warga", WALKER_LINES[rng.randi() % WALKER_LINES.size()])


func parcel_info(pid: int) -> void:
	var p: Dictionary = GS.parcels[pid]
	var counts := [0, 0, 0, 0]
	var ready := 0
	var bush := 0
	var empty := 0
	for t in p["tiles"]:
		match t["s"]:
			"palm":
				counts[int(t["st"])] += 1
				if t["fr"]:
					ready += 1
			"bush":
				bush += 1
			"empty":
				empty += 1
	var lines: Array = []
	if p["owner"] == "player":
		lines.append("Pemilik: kamu, Juragan.")
	else:
		lines.append("Pemilik: %s%s" % [GS.vname(p["owner"]), " (mitra franchise)" if p["plasma"] else ""])
		lines.append("Harga pasaran: %s" % GS.fmt_rp(GS.VILLAGERS[p["owner"]]["value"]))
		lines.append("Ajak ngobrol pemiliknya untuk urusan tanah.")
	lines.append("Semak/kebun lama: %d • Petak kosong: %d" % [bush, empty])
	lines.append("Sawit: bibit %d • muda %d • remaja %d • dewasa %d (siap panen %d)" % [counts[0], counts[1], counts[2], counts[3], ready])
	ui.info_panel(p["name"], lines, "Tutup")


# ------------------------------------------------------------------ morning events
func run_morning_events() -> void:
	if GS.pending_events.is_empty():
		return
	var ev: String = GS.pending_events.pop_front()
	match ev:
		"demo":
			var kd: Vector3 = world.door_points.get("kantor", Vector3.ZERO)
			world.spawn_banner(kd + Vector3(-2.5, 0, 2.2), "KEMBALIKAN\nTANAH KAMI!")
			for vid in GS.villagers:
				if GS.villagers[vid]["status"] == "landless":
					world.npcs[vid].set_anchor(kd + Vector3(randf_range(-3, 3), 0, randf_range(2.5, 4.5)), 1.5, true)
			ui.dialog("portrait_pemuda", "Mas Joko (Demo Warga)", "Warga berkumpul di depan kantormu membawa spanduk 'KEMBALIKAN TANAH KAMI!'. Mereka menunggu jawabanmu, Juragan.",
				[{"text": "Bayar uang damai", "hint": "Rp 1 jt", "enabled": GS.money >= 1000000, "cb": func():
					GS.spend(1000000)
					GS.add_rep(10)
					GS.toast.emit("Demo bubar. Warga pulang membawa nasi kotak.", "info")
					run_morning_events()},
				 {"text": "Panggil preman untuk membubarkan", "hint": "kecurigaan +20", "cb": func():
					GS.add_heat(20)
					GS.add_rep(-10)
					GS.toast.emit("Demo bubar paksa. Videonya tersebar di grup WhatsApp.", "bad")
					run_morning_events()},
				 {"text": "Cuekin saja", "cb": func():
					GS.add_rep(-8)
					GS.money = maxi(0, GS.money - 300000)
					GS.stats_changed.emit()
					GS.toast.emit("Warga kesal. Ada yang mengempiskan ban gerobakmu (-Rp 300rb).", "bad")
					run_morning_events()}])
		"wartawan":
			ui.dialog("portrait_petugas", "Wartawan Investigasi", "Selamat pagi. Saya dari majalah 'Tempo Doeloe'. Boleh tahu asal-usul lahan sawit Anda?",
				[{"text": "Selipkan amplop", "hint": "Rp 1 jt", "enabled": GS.money >= 1000000, "cb": func():
					GS.spend(1000000)
					GS.add_heat(-8)
					GS.add_rep(-3)
					GS.toast.emit("Beritanya berubah jadi advertorial.", "info")
					run_morning_events()},
				 {"text": "Jawab jujur", "cb": func():
					GS.add_heat(12)
					GS.add_rep(6)
					GS.toast.emit("Kejujuranmu dimuat di halaman depan. Hmm.", "info")
					run_morning_events()},
				 {"text": "Usir wartawannya", "cb": func():
					GS.add_heat(15)
					GS.toast.emit("'Juragan sawit usir wartawan' jadi trending.", "bad")
					run_morning_events()}])
		"harga_naik":
			GS.tbs_price = int(GS.tbs_price * 1.25)
			GS.stats_changed.emit()
			say("portrait_calo", "Kabar Pasar", "Tengkulak dari kota memborong! Harga TBS naik 25%% hari ini: %s per tandan." % GS.fmt_rp(GS.tbs_price),
				func(): run_morning_events())
		"hujan":
			GS.add_item("pupuk", 4)
			GS.add_heat(3)
			say("portrait_kades", "Pak Kades Harun", "Pupuk subsidi untuk petani sudah datang... dan entah kenapa 4 karung nyasar ke gudangmu. Jangan bilang-bilang ya.",
				func(): run_morning_events())
