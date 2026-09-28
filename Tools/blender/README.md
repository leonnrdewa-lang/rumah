# Bangunan Ojol Rush (Blender)

Semua bangunan kota di game dibuat di **Blender 4.2** (gratis) lewat skrip Python, bukan AI image-to-3D,
supaya bentuknya bersih, rapi, dan tidak ada yang "abstrak". Hasilnya file GLB kecil di `Web/models/bld/`
plus `manifest.json` yang dipakai game untuk memilih bangunan per kavling.

## Menjalankan

```bash
pip install bpy==4.2.0                                   # Blender sebagai modul Python (gratis)
python3 Tools/blender/build.py                           # semua tipe -> Web/models/bld/
python3 Tools/blender/build.py --types ruko --out /tmp/x # satu tipe ke folder lain

# pratinjau seperti di game (toon + garis tinta). Sekali saja: npm pack three@0.128.0, lalu salin
# build/three.min.js dan examples/js/loaders/GLTFLoader.js ke Tools/blender/.vendor/
NODE_PATH=$(npm root -g) node Tools/blender/preview.js /tmp/ruko.png /tmp/x/ruko_*.glb --street
```

`preview.js` menulis lembar kontak: per model 3 tampilan (kamera game dari depan, kamera game dari
belakang, tampak jalan 3/4) + dengan `--street` deretan model berjajar seperti di blok game
(`*_street.png` dari depan, `*_street_back.png` dari belakang). Kotak hijau = ojol (1,9 m) sebagai skala.

## Konvensi (lihat `common.py`)

- Satuan meter, Blender Z-up. Di dalam builder: `x ∈ [-W/2, W/2]`, `y ∈ [0, D]` dengan **y = 0 fasad
  depan (menghadap jalan)**, `z ∈ [0, H]`.
- **Semua geometri (termasuk teritisan atap, kanopi, pagar) wajib di dalam kavling W×D**: bangunan
  tetangga menempel langsung. `build.py` mencetak `!! OVERFLOW` kalau ada yang keluar.
- Primitif: `box`, `cyl`, `face`, `panel` (lempeng tipis di fasad), `decal` (satu quad, paling murah),
  `window`, `door`, `shutter` (rolling door), `sign` (papan nama polos tanpa tulisan), `railing`,
  `awning` (kanopi/tenda, bisa belang), `roof_gable`, `roof_hip` (limasan), `roof_shed`, `parapet`,
  `water_tank` (toren), `ac_unit`, `plant_pot`. Detail di fasad selalu pakai `off`/`panel` (≥ 2 cm di
  depan dinding) supaya tidak z-fighting.
- Warna: kunci `PALETTE` atau hex `#rrggbb` (sRGB). Game mengubahnya jadi cel-shading 3 tingkat.
- Satu modul per tipe di `types/<tipe>.py` dengan `TYPE`, `ROLES`, `variants()`, `build(b, v, rng)`.
  Pakai `rng` (sudah di-seed) untuk variasi acak supaya hasil build selalu sama persis.

## Peran (roles) di game

Kamera game menunduk **58° dari selatan**. Karena itu:

| role | dipakai di | aturan |
|---|---|---|
| `front` | baris kavling yang fasadnya menghadap kamera (di seberang jalan) | fasad depan terlihat; tinggi 3–12 m |
| `low` | baris yang **membelakangi** kamera (kamera melihat atap + sisi belakang) | tinggi total **≤ 4,8 m** supaya jalan di belakangnya tidak tertutup; sisi belakang harus tetap menarik (jendela, pintu dapur, toren, jemuran) |
| `fill` | isian halaman belakang di tengah blok | kebanyakan terlihat atapnya |
| `tall` | cincin luar kota (latar belakang) | 20–60 m, gedung perkantoran/apartemen |

## Arah seni

- Jalanan Jakarta yang dikenali: ruko berderet dengan rolling door dan papan nama, rumah kampung
  bergenteng dengan pagar, warung bertenda, kos-kosan, rumah minimalis, kantor/klinik/bank kecil,
  minimarket generik, gedung tinggi.
- **Tidak boleh ada**: masjid/rumah ibadah/simbol agama, merek atau logo asli, tulisan yang bisa dibaca
  (papan nama pakai balok warna saja).
- Bentuk jelas dan kokoh: setiap bagian menempel/berdiri di sesuatu, tidak melayang, tidak tembus.
- Dari kamera game **atap adalah bagian yang paling banyak terlihat**: variasikan bentuk dan warna atap,
  isi atap datar dengan toren, AC, parabola, jemuran berwarna, tanaman pot, pagar atap, rumah tangga.
- Tidak monoton: dalam satu tipe variasikan lebar, jumlah lantai, bentuk atap, warna dinding/aksen,
  susunan jendela, kanopi, dan properti.
- Anggaran segitiga: ≤ 1200 per bangunan biasa, ≤ 2000 untuk `tall`.
