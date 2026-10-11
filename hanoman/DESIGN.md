# Hanoman Duta — design & asset contract

Demo game action-roguelike isometrik ala *Hades II*, bertema mitologi Nusantara:
**Ramayana versi wayang Jawa** (Hanoman diutus Rama ke Alengka) dan
**legenda Sura & Baya** (hiu dan buaya yang bertarung di muara — asal nama Surabaya).

## Cerita demo

Sinta diculik Rahwana. Di **Pertapaan Pancawati** (hub, malam hari), Rama mengutus
Hanoman sebagai duta ke Alengka. Jalan ke sana: menembus **Hutan Dandaka** yang
dikuasai raksasa bawahan Rahwana, lalu menyeberangi **Muara Kalimas** yang dijaga dua
penguasa air yang selalu bertarung: **Sura** (hiu) dan **Baya** (buaya). Rahwana
memihak mereka supaya tidak ada yang bisa menyeberang. Para dewa (Bayu, Surya,
Baruna, Indra) memberi anugerah (*boon*). Mati = kembali ke Pancawati; Jembawan
menukar **Kembang Wijayakusuma** dengan kesaktian permanen.

## Alur run (demo)

| # | Ruang | Isi |
|---|---|---|
| 0 | Pancawati (hub) | Rama, Jembawan (toko kesaktian), Sugriwa; sumur/gapura = mulai run |
| 1–4 | Hutan Dandaka | arena gelombang musuh; hadiah ruang; pilih 1 dari 2 gapura |
| 5 | Dandaka — mini-bos | **Kijang Kencana** (Kala Marica menyamar) |
| 6 | Dandaka — Pasar Sang Hyang (toko) / mata air (pulih) |
| 7–8 | Muara Kalimas | arena di atas dermaga/batu, air di sekeliling |
| 9 | Muara — bos | **Sura & Baya** (dua bos sekaligus, saling serang juga) |
| — | Menang | "Bersambung ke Alengka…" → kembali ke hub |

Hadiah ruang: anugerah dewa (orb berwarna dewa), Kepeng (uang run), Tirta Amerta
(pulih nyawa), Kembang Wijayakusuma (mata uang permanen), Pusaka Palu (naik tingkat boon).
Pintu keluar (gapura candi bentar) menampilkan ikon hadiah ruang berikutnya.

## Kontrol

| | PC | HP |
|---|---|---|
| Gerak | WASD | joystick kiri |
| Serang (gada, kombo 3) | J / klik kiri | tombol |
| Jurus (Kuku Pancanaka: proyektil angin) | K / klik kanan | tombol |
| Ajian (lingkaran pengikat Bayu) | Q / L | tombol |
| Lesat (dash) | Spasi / Shift | tombol |
| Interaksi | E | tombol |

## Tempur

* Hanoman: 50 nyawa; lesat 1 muatan (0,35 s i-frame).
* Serang: gada 3 pukulan (10/10/20), jangkauan 1,8 m, busur 120°.
* Jurus: bilah angin lurus 12 m, 15 dmg, cooldown 0,6 s; 3 muatan "Prana" pulih sendiri.
* Ajian: lingkaran r=3 m di depan; musuh di dalam terikat (lambat 70%) 4 s; 1 muatan, pulih 8 s.
* Anugerah dewa mengubah salah satu aksi (Serang/Jurus/Ajian/Lesat) atau pasif.
  - **Bayu** (angin, toska): dorongan balik, lesat melukai.
  - **Surya** (api, emas-oranye): membakar (DoT), ledakan.
  - **Baruna** (air, biru): membasahi → lambat, gelombang.
  - **Indra** (petir, ungu): petir berantai.
* Kelangkaan: Biasa / Langka / Agung / Wahyu.

## Musuh

| id | nama | perilaku |
|---|---|---|
| `wil` | Wil (raksasa kecil) | kawanan, jalan cepat, cakar |
| `cakil` | Buto Cakil | ancang-ancang lalu menerjang dengan keris |
| `buto_ijo` | Buto Ijo | besar, lambat, hantaman area (telegraf lingkaran) |
| `banaspati` | Banaspati | tengkorak api melayang, menembak bola api |
| `yuyu` | Yuyu Kangkang | kepiting raksasa (Muara), capit + tahan depan |
| `kijang` | Kijang Kencana | mini-bos: lompat-terjang, bayangan kembar, berubah wujud raksasa di 50% |
| `sura` | Sura | bos hiu: menyelam lalu menerkam, gelombang |
| `baya` | Baya | bos buaya: gigit, sabet ekor berputar, lindas |

## Gaya visual

"Lukisan" ala Hades: garis tinta hitam tebal (outline), warna rata 2–3 tingkat
(toon), cahaya pinggir (rim light), latar gelap dengan aksen bercahaya (toska,
magenta, emas). Motif lokal: lantai batu berukir **kawung / parang / mega mendung**,
candi bata merah, gapura candi bentar, beringin, oncor (obor), arca, kain poleng.

Palet:

| peran | hex |
|---|---|
| malam dasar | `#10141c` `#1b2330` |
| lumut/daun Dandaka | `#1f3b33` `#2e5a45` `#4f7a4a` |
| bata candi | `#8a4a36` `#b0643f` |
| batu andesit | `#4b4f57` `#6c707a` |
| aksen toska (Bayu) | `#5fe0c8` |
| aksen emas (Surya) | `#f2b845` |
| aksen biru (Baruna) | `#4aa3ff` |
| aksen ungu (Indra) | `#b784ff` |
| aksen magenta bunga | `#e0508f` |
| bulu Hanoman | `#f4f1ea` |
| emas perhiasan | `#d9a93a` |

## Kontrak aset (Blender → Godot)

Semua aset dibuat skrip Python `bpy` di `hanoman/blender/*.py`, diekspor ke
`hanoman/game/assets/models/<id>.glb`.

* 1 unit = 1 m, Z atas, depan menghadap **-Y** (jadi +Z di Godot), origin di tanah.
* Satu Empty akar bernama `<id>`.
* Warna material rata (Principled, roughness 0.8). Game menggantinya dengan shader
  toon + outline dan membaca `albedo_color` material. Material bernama `M_Glow*`
  diberi emisi (mata, api, bunga bercahaya).
* **Karakter dipotong per bagian** (tanpa armature) agar dianimasikan dari kode.
  Anak langsung dari akar, masing-masing Empty-pivot di sendi, mesh di bawahnya:
  `body` (pivot pinggul), `head` (pivot leher, anak dari `body`), `arm_l`, `arm_r`
  (pivot bahu, anak `body`), `leg_l`, `leg_r` (pivot pinggul, anak akar),
  opsional `tail`, `weapon` (anak `arm_r`), `jaw`. Bagian yang tidak ada boleh dilewati.
* Tinggi: Hanoman ≈ 1,7 m; wil 1,1 m; cakil 1,8 m; buto ijo 3,0 m; banaspati melayang
  (kepala 0,8 m di z≈1,2); yuyu 1,2 m tinggi, 2,4 m lebar; kijang 1,6 m;
  Sura ≈ 5 m panjang; Baya ≈ 6 m panjang. Rama 1,8 m, Jembawan 1,5 m, Sugriwa 1,7 m.
* Anggaran: karakter ≤ 6000 tri, prop ≤ 1500, bos ≤ 12000.

Daftar model: lihat `hanoman/blender/README.md`.
