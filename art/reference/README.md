# Referensi visual (Higgsfield)

Semua gambar referensi dibuat di **Higgsfield** dengan model **GPT Image 2.5**
(`gpt_image_2_5`, varian *flare*), resolusi **1K** (1344×752, kualitas *high*,
1,5 kredit per gambar) untuk menghemat kredit. Gambar gaya dari user
(`00_user_style_reference.png`) dipakai sebagai *image reference* di setiap prompt.

Proyek Higgsfield: **"Sawit The Franchise - Game Refs"** (folder default proyek).

> Catatan: CDN hasil Higgsfield (`d8j0ntlcm91z4.cloudfront.net`) diblokir oleh
> kebijakan jaringan container build ini, jadi file PNG hasil generate tidak
> ikut tersimpan di repo. Buka proyek di atas di akun Higgsfield untuk melihat
> gambarnya. Palet warna di bawah diekstrak dari gambar-gambar tersebut (lewat
> sandbox Higgsfield) dan dipakai di `blender/common.py` dan shader game.

| # | Job ID | Isi | Prompt (ringkas) |
|---|--------|-----|------------------|
| 1 | `86b3caf3-3885-4f03-9339-635140f9c88d` | Suasana dunia | Screenshot game cozy, kamera top-down seperti referensi: pulau desa Indonesia, baris kebun sawit, rumah panggung genteng merah, pabrik sawit mungil, warung, pantai & laut toska |
| 2 | `f9b9fa45-7ae8-4dbc-bf2d-cb42d0ba5186` | Tahap tumbuh sawit | Bibit polybag → sawit muda → remaja → dewasa dengan pangkal pelepah & TBS merah-oranye; satu TBS; gerobak TBS |
| 3 | `78ece3d6-6211-4823-86bf-0c9fabb2f54a` | Karakter | Chibi ala Animal Crossing: juragan (topi safari, batik), kakek bercaping, ibu berhijab, anak bertopi, Pak Kades berpeci, preman |
| 4 | `505fdb4d-0467-4fe8-b8ca-65568ceea40f` | Bangunan & props | Rumah panggung, warung tenda belang, pabrik kelapa sawit dengan cerobong, kantor dengan papan nama hijau, pickup kuning, karung pupuk, jerigen minyak |
| 5 | `25e95104-116a-4f00-aaab-44b9b20d6077` | UI/HUD | Pil krem membulat dengan ikon cokelat bulat (mengikuti referensi), uang Rupiah, hari & jam, bar Reputasi/Kecurigaan, kotak dialog pilihan "Beli harga wajar / Tawar murah / Tipu pakai surat palsu / Gusur paksa" |
| 6 | `050819d4-0bb9-4f7f-ab33-6bf7ba1142ba` | Key art judul | Logo "SAWIT" + pita "THE FRANCHISE", juragan chibi membawa karung uang, warga mengintip |

## Palet (hasil ekstraksi)

| Peran | Hex |
|-------|-----|
| Rumput tengah / terang / gelap | `#6d9148` `#a9bd5d` `#4c733c` |
| Pasir / pasir basah | `#efdfb0` `#dad29b` |
| Air dangkal / laut | `#73c7aa` `#5ac3b1` |
| Jalan tanah | `#b8966b` |
| Genteng terakota | `#c2714a` `#9c4c2b` |
| Batang & kayu | `#5b5438` `#97623f` |
| Kulit karakter | `#f0b57d` `#e2a67b` |
| Krem UI / teks cokelat | `#fdf3dc` `#5a3b22` |

Keputusan gaya yang diambil dari referensi: kamera tinggi hampir top-down,
cahaya lembut dari kiri atas dengan bayangan transparan, tekstur rumput
"dilukis" (bercak terang-gelap), pantai berbusa putih dan garis ombak, serta
UI berupa pil krem kecil dengan ikon bulat di kiri.
