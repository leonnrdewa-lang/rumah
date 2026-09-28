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

## Alur demo

1. **Pertapaan Pancawati** (hub malam): Prabu Rama memberi misi, **Resi Jembawan** menukar
   Kembang Wijayakusuma dengan kesaktian permanen, **Prabu Sugriwa** memberi tips. Masuk sumur tua.
2. **Hutan Dandaka**, ruang 1–4: gelombang Wil, Buto Cakil (terjang keris), Buto Ijo (hantaman
   area), Banaspati (bola api). Tiap ruang bersih → hadiah; pilih 1 dari 2 gapura candi bentar
   yang menunjukkan hadiah berikutnya.
3. **Kijang Kencana** (mini-bos): terjang beruntun, membelah diri, lalu berubah wujud jadi Kala Marica.
4. **Pasar Sang Hyang & Sendang Suci**: pulihkan nyawa, belanja anugerah/Tirta/Pusaka Palu.
5. **Muara Kalimas**, ruang 7–8: Yuyu Kangkang (kebal dari depan) dan kawan-kawan.
6. **Bos Sura & Baya** sekaligus: Sura menyelam lalu menerkam dari bawah, gelombang air; Baya
   menggigit, sabetan ekor berputar, terjangan guling. Serangan mereka saling melukai: adu mereka!
7. Menang → epilog asal nama Surabaya, "Bersambung ke Alengka…". Gugur → kembali ke Pancawati.

**Anugerah dewa** (20 boon, 4 kelangkaan): Batara **Bayu** (angin, dorongan/sedotan),
**Surya** (api, bakar/ledakan), **Baruna** (air, basah/lambat, ombak), **Indra** (petir berantai).
Tiap anugerah mengisi slot Serang / Jurus / Ajian / Lesat / Pasif.

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
