# Serah-terima: Sawit The Franchise (lanjut di PC lokal)

Catatan ini untuk sesi Claude Code baru, supaya bisa langsung lanjut dari sesi cloud
`session_01M7a4rv5dfQbxrs4P7XJC4u` (https://claude.ai/code/session_01M7a4rv5dfQbxrs4P7XJC4u).

## Proyek singkat
- Game sim kebun sawit yang satir: beli tanah warga murah, menipu, lalu jual minyaknya
  balik ke warga. Gaya 3D anime cel-shading dengan garis tinta.
- Engine: **Godot 4.5.1** (renderer Compatibility). Build web untuk PC dan Android.
- Model dibuat lewat **Blender** (`pip install bpy` 4.5, lalu jalankan `python3 blender/<script>.py`).
- Repo: `https://github.com/leonnrdewa-lang/rumah`, branch **`claude/focused-bardeen-cmygsy`**.
  Repo lama `yusik2l31/Claude` sudah tidak dipakai, karena push ke sana ditolak.
- Demo online (Claude Artifact): https://claude.ai/artifact/QynyV7jFdfuyyKfqyinRyC (versi 15).
  Publish ke artifact hanya bisa lewat Claude. Di lokal, pakai `docs/` (GitHub Pages).

## Menjalankan
- **Main di editor:** buka folder `game/` di Godot 4.5.1, lalu tekan Play.
- **Tes logika:** `godot --headless --path game -- --autotest=logic`.
  Hasil yang benar: `features logic: OK` dan `save roundtrip ok=true`.
- **Screenshot:** `godot --path game -- --autotest=basic --shots=/tmp/shots`.
  - Skenario lain: `features`, `map3`, `ambience`, `voice`, `animals` (WIP).
  - Di Linux tanpa layar, tambahkan `xvfb-run -a` di depan perintah.
- **Tes kontrol sentuh:** `godot --path game -s res://scripts/debug/touch_check.gd`.
- **Build web:** `GODOT=/Applications/Godot.app/Contents/MacOS/Godot python3 tools/build_web.py`.
  - Keluarannya di `docs/` (GitHub Pages) dan `dist/artifact/` (pack base64 yang dipecah per 12 MB).
  - Bank suara warga di `game/voices/` disalin ke `voices/`.
- **Tes browser:** `NODE_PATH=$(npm root -g) node tools/web_test.js http://127.0.0.1:8060/ /tmp/out`.
  Butuh Playwright. Sajikan dulu `docs/` dengan `python3 -m http.server 8060`.

## Struktur penting
- `game/scripts/world/world.gd`: membangun dunia, kamera, target aksi, kualitas grafis, governor FPS.
  - `deals.gd`: semua dialog dan transaksi lahan.
  - `fishing.gd`: minigame mancing, umpan, 20 ikan N/R/SR/SSR.
  - `interior.gd`: interior rumah per tipe.
  - `ambience.gd`: suara sungai, laut, hutan, malam.
  - `animals.gd`: binatang (**WIP**).
- `game/scripts/autoload/gs.gd`: state game, save (`user://sawit_save.json`), `export_code()`/`import_code()`.
  `sfx.gd`: musik per waktu dan konteks, `duck_voice`, stinger.
- `game/scripts/ui/ui.gd`: HUD, dialog, menu, joystick, Kode Save.
  - `voice.gd`: suara warga (bank Ogg per karakter, diunduh saat perlu).
  - `ui_dialog.gd`, `ui_portrait.gd`: potret anime 2D di `game/assets/portraits/`.
- Shader: `game/shaders/toon_light.gdshaderinc` (cel shading), `outline.gdshader` (garis tinta),
  `post_grade.gdshader` (color grade).
- Tools:
  - `tools/make_voices.py`: suara TTS VITS Indonesia Wikidepia, lisensi NON-KOMERSIAL; butuh model di `/opt/idtts` dan Whisper di `/opt/asr`.
  - `tools/make_music.py`: musik, butuh FluidSynth + FluidR3_GM.
  - `tools/make_ambience.py`, `tools/make_animal_sounds.py`, `tools/make_item_icons.py`.
- Blender: `blender/layout.py`, `terrain.py`, `buildings.py`, `characters.py`, `animals.py` (baru).

## Status saat pindah
Sudah selesai dan sudah rilis di artifact v15:
- Map 5x lebih besar, 6 dusun, 5 jembatan, 20 petak kebun.
- Cel shading, joystick, mancing + umpan, tas, interior rumah yang beda-beda, tidur di kasur.
- Potret anime, voice acting 42 karakter, musik, ambience, Kode Save (versi awal).

**Belum selesai (lanjutkan ini dulu):**
1. **Perilaku binatang:** `game/scripts/world/animals.gd`, sekitar 2000 baris.
   - Sudah ada: spawn, keliling, makan, bersuara, lari menjauh, "Elus <hewan>".
   - Belum direview. Tes logika sudah lolos, tapi tampilan belum pernah dicek.
   - Yang harus dicek: binatang tidak melayang atau tenggelam, kaki tidak meluncur, arah hadap benar,
     bebek tetap di air, kodok cukup besar dan kelihatan, tidak menghalangi pintu/jembatan/kebun,
     dan performanya (tambahan kurang dari 40 draw call, kurang dari 1,5 ms).
   - Jalankan `--autotest=animals` lalu lihat screenshot-nya.
   - Model: `game/assets/models/animal_<sapi|kerbau|kambing|ayam|bebek|kodok|kucing|anjing>.glb`,
     dengan klip idle/walk/run/eat/call, plus hop/swim/sit/wag.
   - Suara: `game/assets/audio/animals/*.ogg`.
2. **Kode Save di web:** tombol "Masukkan Kode Save" sebelumnya memakai `window.prompt`, yang
   diblokir di iframe artifact. Sudah diganti overlay HTML lewat JavaScriptBridge di `ui.gd`, tapi
   **belum dites di browser**. Tes top-level dan di iframe sandbox tanpa `allow-modals`.
3. Setelah itu: build web, lalu tes desktop.

## Preferensi pengguna (penting)
- Bahasa Indonesia santai. Pengguna ingin **cepat**: rilis bertahap dan jangan menunggu lama.
- Grafik 3D anime cel-shading, hijau cerah (tidak pucat), UI kecil di HP, target 60 fps konsisten.
  Jangan kurangi jumlah NPC atau konten.
- **Audio (suara warga, musik, ambience) sudah dianggap bagus. Jangan diubah atau dicek ulang.**
- Kreator: **@leonrdewa** (Instagram). Namanya ada di menu "Dibuat oleh".
- Aset gambar pernah dibuat dengan Higgsfield GPT Image 2.5 (Sunburst, Low, 1296x768).
  Di cloud, CDN Higgsfield diblokir. Di PC seharusnya bisa langsung diunduh.
- Di PC, situs aset gratis (Quaternius/Kenney/Poly Pizza) bisa diakses. Model binatang
  boleh diganti dengan aset CC0 asal tetap cel-shading yang sama: `ModelLib.instance()` otomatis
  memasang toon shader + outline. Jangan beri nama material dengan kata Leaf/Grass/Plant/Bush.
