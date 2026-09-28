# Seni Higgsfield — Hanoman Duta

Lukisan gaya *Hades II* (tinta tebal, warna rata, rim light) dibuat di **Higgsfield**,
model **GPT Image 2.5**, 1K. Proyek Higgsfield: **"Hanoman Duta - Game Art"**.
Daftar job + URL: `higgsfield.json` (key art, 11 potret: Hanoman, Rama, Jembawan,
4 dewa, Sura, Baya, Kijang Kencana, dan mockup gameplay).

CDN Higgsfield diblokir dari container build, jadi gambar belum masuk ke game.
Game memakai potret render Blender (`game/assets/portraits/*.png`) sebagai cadangan.
Untuk memakai lukisan Higgsfield, di komputer yang bisa mengakses CDN jalankan:

```bash
python3 hanoman/tools/fetch_art.py      # unduh ke hanoman/game/assets/portraits/hf_<nama>.png
```

Game otomatis memakai `hf_<nama>.png` bila ada (lebih diutamakan dari render Blender).
