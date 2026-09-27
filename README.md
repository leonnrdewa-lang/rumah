# Sawit The Franchise

Game *farming sim* satir bergaya cozy (ala Animal Crossing / Coral Island) tentang
seorang juragan kebun sawit di Desa Sukamakmur. Tanam, pupuk, panen, dan jual
Tandan Buah Segar (TBS) ke pabrik. Kuasai lahan warga dengan cara halal...
atau tidak: tawar murah, tipu pakai surat palsu, gusur pakai preman, jerat
dengan "kemitraan franchise" dan utang, lalu jual minyak goreng kembali ke
mereka dengan harga yang kamu atur sendiri.

> Ini karya satir. Di dunia nyata, hormati hak tanah masyarakat adat dan warga,
> serta hutan tropis kita.

- **Engine:** Godot 4.5.1 (renderer *Compatibility* / WebGL 2 agar jalan di browser PC & Android)
- **Aset 3D:** dimodelkan lewat skrip Python di Blender 4.5 (`blender/*.py`), diekspor ke GLB
- **Referensi visual:** Higgsfield, model GPT Image 2.5 resolusi 1K (lihat `art/reference/README.md`)
- **Audio:** disintesis dengan numpy (`tools/make_audio.py`)

## Main

Demo web: buka `docs/index.html` lewat server statis apa pun (misalnya GitHub Pages
dari folder `/docs`), atau jalankan lokal:

```bash
cd docs && python3 -m http.server 8060
# buka http://localhost:8060 di browser PC atau HP (satu jaringan)
```

### Kontrol

| | PC | Android (browser) |
|---|---|---|
| Jalan | WASD / panah (Shift = lari) | geser jempol di sisi kiri layar |
| Aksi (tebas, tanam, pupuk, panen, ngobrol, masuk) | E / Spasi | tombol bulat kanan bawah |
| Pilihan dialog | klik atau tombol angka 1–6 | ketuk |
| Menu / Status / Peta | Esc atau P / Tab atau I / klik peta mini | tombol Menu, Status, ketuk peta mini |

### Alur permainan

1. Panen 3 pohon sawit yang sudah berbuah di samping Kantor, jual TBS ke Pabrik (timur desa).
2. Tanam bibit, beri pupuk, tidur di Kantor untuk ganti hari (sawit ±6 hari sampai berbuah).
3. Kuasai kebun 6 warga. Tiap warga punya sifat berbeda (lugu, teliti, korup, aktivis...):
   - **Beli harga wajar** — mahal, reputasi naik.
   - **Tawar murah** — peluang tergantung kepercayaan & sifat warga.
   - **Tipu pakai surat palsu** — beli suratnya dari Bang Jeki (calo) di dermaga.
   - **Rampas paksa (gusur)** — sewa preman Bang Codet; warga pindah ke tenda biru.
   - **Palak/rampok** — preman yang sama bisa merampas tabungan warga.
   - **Kemitraan franchise** — warga tetap "pemilik", kamu ambil 60% hasil, sisanya jadi cicilan utang berbunga 5%/hari... lalu **sita kebun** kalau utang menumpuk.
   - Pak Kades bisa disogok amplop.
4. Beli Mesin Olah Minyak, olah TBS jadi minyak goreng, jual ke warga (harga Normal / Mahal / Gila-gilaan). Warga tanpa lahan terpaksa beli, kalau perlu ngutang.
5. Awasi **Kecurigaan**: kalau penuh, Satgas menyidak dan mendenda. Sidak ke-3 = tamat.
6. Kuasai ke-7 lahan dan beli **Lisensi Sawit The Franchise™** (Rp 20 juta) → ending Raja Sawit.

## Struktur repo

```
art/reference/     gambar gaya dari user + catatan referensi Higgsfield (prompt, job ID, palet)
blender/           skrip modeling Blender (bpy): terrain, vegetasi, bangunan, props, karakter
  previews/        render pratinjau Cycles tiap aset
game/              proyek Godot 4.5
  assets/          models (.glb), icons, textures, audio, font Fredoka (OFL)
  data/            layout pulau (layout.json) + tinggi terrain (height.bin)
  scripts/         autoload (state, audio), world, actors, ui, debug/autotest
  shaders/         terrain, air, material dunia, dedaunan
tools/             build web, uji Playwright, generator audio & ikon UI
web/shell.html     halaman loader web (wasm/pck di-gzip, di-inflate di browser)
docs/              hasil build web siap host (GitHub Pages → /docs)
```

## Build ulang dari nol

Butuh Python 3.11 dengan `pip install bpy==4.5.* numpy scipy pillow`, dan Godot 4.5.1 + export template Web.

```bash
python3 blender/terrain.py        # pulau, masker tanah, layout, peta mini
python3 blender/vegetation.py     # sawit (4 tahap), semak, pohon, batu
python3 blender/buildings.py      # rumah, kantor, warung, koperasi, pabrik, dermaga, truk
python3 blender/props.py          # props + ikon item
python3 blender/characters.py     # 12 karakter chibi + potret dialog
python3 tools/make_ui_icons.py
python3 tools/make_audio.py
python3 tools/build_web.py        # ekspor Godot → docs/ dan dist/artifact/
```

Uji otomatis (butuh Xvfb untuk screenshot):

```bash
godot --headless --path game -- --autotest=logic          # semua jalur gameplay
xvfb-run godot --path game --rendering-driver opengl3 -- --autotest=basic --shots=/tmp/shots
NODE_PATH=$(npm root -g) node tools/web_test.js http://127.0.0.1:8060/ /tmp/shots
```

## Lisensi aset pihak ketiga

- Font **Fredoka** — SIL Open Font License (`game/assets/fonts/OFL.txt`).
- Semua model, tekstur, ikon, dan audio lainnya dibuat secara prosedural di repo ini.
