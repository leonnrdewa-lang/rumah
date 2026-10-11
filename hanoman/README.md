# Hanoman Duta

Demo **action roguelike isometrik ala *Hades II*** dengan kearifan lokal: lakon **Ramayana
versi wayang Jawa** (Hanoman diutus Prabu Rama ke Alengka) dan **legenda Sura & Baya**
(hiu dan buaya yang bertarung di muara, asal nama Surabaya). Desain lengkap: `DESIGN.md`.

- **Engine:** Godot 4.5.1, renderer Compatibility (WebGL 2), jalan di browser PC & HP
- **Gaya "lukisan":** shader toon 3 pita + garis tinta (inverted hull) + tekstur sapuan kuas,
  cahaya bulan kebiruan, obor hangat, aksen bercahaya, grade layar (vignette, grain)
- **Aset 3D:** 40 model dibuat skrip Blender (`blender/*.py`, bpy 4.5); karakter dipotong
  per bagian dan dianimasikan prosedural di game (`scripts/rig.gd`)
- **Higgsfield:** diorama Hutan Dandaka dibangun di **Higgsfield 3D Jutsu** (Blender 5.2 di
  cloud) dan dipakai sebagai latar 3D layar judul (`art/higgsfield_3d/`); 12 lukisan
  (key art, potret Hanoman, Rama, Jembawan, 4 dewa, Sura, Baya, Kijang Kencana) dibuat dengan
  GPT Image 2.5 di proyek Higgsfield "Hanoman Duta - Game Art" (`art/README.md`)
- **Audio:** gamelan disintesis (saron, bonang, gender, kenong, gong ageng, kendang) + FluidSynth,
  laras slendro/pelog; 7 musik, 30 SFX, 2 suasana (`tools/make_music.py`, `tools/make_sfx.py`)

## Versi Higgsfield (utama)

**https://hanoman-duta.higgsfield.app**, terbit di komunitas Higgsfield. Versi ini memuat paket
aset Higgsfield saat berjalan (`game/scripts/hf.gd` membaca `hf/manifest.json`):

- **Karakter 3D beranimasi** (image-to-3D + auto-rig): Hanoman (idle, lari, sabetan, hantaman,
  guling, ajian, kena pukul, gugur), Wil, Buto Cakil, Buto Ijo (jalan, serang, kena pukul),
  Rama, Jembawan, Sugriwa (idle); Sura, Baya, Yuyu Kangkang, Kijang Kencana (model bertekstur,
  gerak prosedural)
- **Lantai arena dilukis** (GPT Image 2.5, tampak atas) untuk Dandaka, pelataran bata, Muara,
  arena bos, dan Pancawati
- **Potret lukis** tanpa latar untuk dialog dan pilihan anugerah dewa
- **Suara (voice acting)**: 45 baris dialog berbahasa Indonesia, tiap tokoh suaranya berbeda
- **Efek jurus dilukis** (GPT Image 2.5 di latar hitam, blend aditif): sabetan tongkat, sinar
  Tongkat Mulur, lingkaran sakti, ledakan, api, cipratan, petir, angin, tanda bahaya musuh
- **SFX & musik epik**: 35 efek suara (Mirelo) + musik hutan, muara, kijang, dan bos (Sonilo)
- **Tongkat & Jurus Tongkat Mulur**: Hanoman menyerang dengan tongkat; Jurus memanjangkan
  tongkat seperti laser menembus semua raksasa di garisnya
- **Tahap 3 bilik**: tiap ruang pertempuran terdiri dari tiga bilik bersambung lorong
  (kolam, pilar, reruntuhan, bakau, candi, dermaga), gerbang terbuka setelah bilik bersih
- Alur pembuatannya: `tools/higgsfield/README.md`; daftar URL aset: `art/hf_assets.json`,
  `art/hf_assets_v3.json` (efek, suara, musik, lantai tambahan, klip Hanoman bertongkat)

## Main (versi aset Blender)

Web: `docs/hanoman/` (GitHub Pages → `<url-pages>/hanoman/`), atau lokal:

```bash
cd docs/hanoman && python3 -m http.server 8060   # buka http://localhost:8060
```

| | PC | HP |
|---|---|---|
| Gerak | WASD / panah | jempol kiri |
| Serang (tongkat, kombo 3) | J / klik kiri | tombol serang |
| Jurus (Tongkat Mulur, sinar tongkat memanjang) | K / klik kanan | tombol /// |
| Ajian (lingkaran pengikat Bayu) | Q | tombol lingkaran |
| Lesat (menghindar, kebal sesaat) | Spasi / Shift | tombol garis |
| Interaksi | E | ketuk label di bawah |

Mouse mengarahkan serangan; di HP serangan membidik raksasa terdekat. Gamepad juga didukung.

## Alur demo (v4, bahasa Inggris di dalam game)

1. **Pancawati Hermitage** (hub): Rama memberi misi, **Jembawan** mengajarkan kesaktian dan
   **senjata baru** (Rujakpolo Mace, Sacred Bow, Sudarsana Chakra), **Sugriwa** punya cerita yang
   terbuka sesuai progres, **rak senjata**, **Lontar of Tales** (kodeks + statistik), dan
   **Altar of Vows** (mode Heat) setelah menang sekali.
2. **Dandaka Forest** (ruang 1–4) → **Kijang Kencana** (5) → pasar & mata air (6).
3. **Kalimas Estuary** (7–8) → **Sura & Baya** (9): kalahkan mereka, epilog Surabaya, lalu lanjut.
4. **The Southern Ocean** (10–11, di atas punggung kura-kura raksasa) → istirahat (12).
5. **Alengka**: **Kumbakarna** (13, raksasa yang tertidur–bangun), **Asoka Garden** (14),
   **Indrajit** (15, panah Nagapasa, teleport, ilusi, hujan panah). Menang → Hanoman bertemu Sinta.
6. Musuh baru: pemanah, dukun pemanggil Wil, pembawa perisai; varian elite emas; tiap bos punya fase 2.
7. Simpan otomatis tiap ruang ("Resume Journey" di menu), cutscene bergambar tiap babak,
   suara Hanoman saat bertarung, 67 dialog bersuara bahasa Inggris, ekspresi potret.

**Anugerah dewa**: 20 boon + 6 boon Duo (dua dewa), 4 kelangkaan.

## Build ulang

```bash
pip install "bpy==4.5.*" numpy scipy pillow soundfile pyloudnorm mido
python3 hanoman/blender/characters.py && python3 hanoman/blender/enemies.py && python3 hanoman/blender/bosses.py
python3 hanoman/blender/props.py && python3 hanoman/blender/portraits.py && python3 hanoman/blender/title.py
python3 hanoman/tools/make_textures.py      # lantai lukis, noise, ikon, bingkai UI
python3 hanoman/tools/make_music.py && python3 hanoman/tools/make_sfx.py   # butuh fluidsynth + musescore-general-soundfont
python3 hanoman/tools/build_web.py          # Godot 4.5.1 + template Web → docs/hanoman/ dan hanoman/dist/artifact/
python3 hanoman/tools/fetch_art.py          # (opsional) unduh lukisan Higgsfield → potret hf_*.png diutamakan
```

Uji otomatis (tur judul → hub → ruang → bos → menang → gugur, dengan screenshot):

```bash
xvfb-run godot --path hanoman/game --rendering-driver opengl3 -- --autotest --shots=/tmp/shots
```

Font Cinzel, Cinzel Decorative, Alegreya: SIL Open Font License (`game/assets/fonts/OFL.txt`).
Musik dirender dengan MuseScore General SoundFont (MIT). Semua aset lain dibuat di repo ini.
