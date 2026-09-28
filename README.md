# Ojol Rush

> *"Kamu bukan yang tercepat. Kamu jagonya nyelip."*

Prototipe game arcade top-down 3D (Unity, portrait, satu jempol). Kamu adalah driver ojol aplikasi fiktif
**NgoJek-in** yang harus mengantar order menembus lalu lintas kota ala Jakarta: angkot yang ngerem mendadak,
bajaj yang zig-zag, bus yang belok lebar, gerobak, kucing nyebrang, dan ratusan motor.

Semua konten dibuat **secara prosedural lewat kode**: kota, kendaraan, UI, sampai suara (disintesis saat runtime).
Tidak ada scene, prefab, model, tekstur, atau file audio yang perlu disiapkan.

## Cara menjalankan

1. Install **Unity 2022.3 LTS** (Unity 6 juga seharusnya bisa; Unity akan meng-upgrade proyek saat dibuka).
2. Buka folder repo ini lewat Unity Hub → *Add project from disk*.
3. Buka scene apa saja (mis. `SampleScene` bawaan, atau scene kosong) lalu tekan **Play**.
   `Bootstrap` otomatis membuat `GameManager`; kamera/lampu bawaan scene dinonaktifkan.
4. Di Game view pilih resolusi portrait (mis. 1080×1920) supaya tampilannya sesuai target.

**Build ke HP:** File → Build Settings → Android / iOS → *Switch Platform*, tambahkan scene yang sedang dibuka,
lalu Build. Orientasi otomatis dikunci portrait saat runtime (sebaiknya set juga *Player Settings → Default
Orientation → Portrait*).

Saat proyek pertama kali dibuka, skrip editor `OjolRushProjectSetup` otomatis mengatur orientasi portrait,
menyimpan varian shader (instancing, fog linear), dan membuat material dasar di `Assets/OjolRush/Resources` supaya
build di HP tampil sama seperti di Editor. Bisa dijalankan ulang lewat menu **Ojol Rush → Apply Project Settings**.

Built-in render pipeline dan URP sama-sama didukung (material di-clone dari material default pipeline aktif).

## Kontrol

| Input | Aksi |
|---|---|
| Seret jempol ke suatu arah | Motor mengarah ke sana (motor ngegas sendiri) |
| Tahan jempol diam | Melambat — untuk menunggu celah |
| Lepas | Lanjut lurus dengan kecepatan penuh |
| Keyboard (desktop) | WASD / panah = arah, Spasi = pelan, Esc / P = pause |

Mode kontrol bisa diganti di menu: **SERET** (titik awal mengikuti jempol) atau **JOYSTICK** (stik tetap di bawah
layar). Pilihan disimpan.

## Loop permainan

Mulai shift → order masuk (ping!) → ambil di titik jemput (penanda oranye) → antar ke penanda hijau sebelum waktu
habis → rating ★ + tip → level Rush naik → lalu lintas makin padat → helm hancur (3 tabrakan berat) atau rating
anjlok di bawah 3.0 → **SHIFT SELESAI** → **LAGI** (restart instan).

- **SALIP!** — lewat mepet kendaraan (< 1,1 m) dengan kecepatan tinggi = +50. Salip beruntun dalam 2 detik jadi
  combo `SALIP x5!` (pengali sampai x10). Senggolan apa pun memutus combo.
- **Tabrakan ringan** cuma bikin oleng dan pelan. **Tabrakan berat** (kecepatan tabrak > 7 m/s) memecahkan 1 helm,
  hit-stop 60 ms, layar bergetar. Order makanan yang dibawa jadi **TUMPAH!** (−2 bintang), paket **PENYOK** (−1).
- **Gang** — dua jalan tikus sempit menembus blok: lebih pendek, tapi penuh ayam, jemuran, dan anak-anak main
  (menabrak anak = berhenti total + komplain warga −1 bintang).
- **Bahaya jalan** — genangan (motor meluncur), lubang (*JEGLONG!*), polisi tidur (lompat kecil), gerobak kaki lima
  dengan uap, kucing menyeberang.
- **Angkot** berhenti mendadak — tapi selalu di dekat penumpang yang melambai di pinggir jalan (bisa dipelajari).
  Mobil memberi lampu sein sebelum pindah lajur/belok; lampu rem terang terlihat dari atas.
- Lalu lintas **lajur kiri** seperti di Indonesia, lampu merah dua fase, belok kiri jalan terus, motor
  berkerumun di depan garis saat lampu merah, klakson bersahutan saat macet.

### Level Rush

| Rush | Nama | Isi |
|---|---|---|
| 1 | Santai | Lalu lintas ringan, timer longgar |
| 2 | Mulai Padat | Lebih padat, jauh lebih banyak penumpang angkot |
| 3 | Hujan Lokal | Hujan (grip turun, genangan baru), razia polisi, timer lebih ketat |
| 4 | Jam Pulang Kantor | Banyak bus, jalan banjir (zona lambat), 2 razia |
| 5 | MACET TOTAL | Hujan terus, banjir di mana-mana — memang hampir mustahil |

Level naik berdasarkan jumlah antaran (0 / 2 / 4 / 6 / 9).

## Tuning

Semua angka (kecepatan motor, grip, jarak salip, poin, tip, rating game over, timer order, isi tiap level Rush,
dll.) ada di `GameConfig`. Untuk mengubah tanpa menyentuh kode:
**Assets → Create → Ojol Rush → Game Config**, beri nama `OjolRushConfig`, simpan di folder `Resources`, lalu edit
di Inspector.

## Arsitektur

Semua di `Assets/OjolRush/Scripts`, namespace `OjolRush`. `GameManager` memanggil setiap sistem secara eksplisit
tiap frame (input → motor → lalu lintas → bahaya → tabrakan/salip → order → level → kamera/efek/audio/HUD).

| Sistem (PRD) | File |
|---|---|
| GameManager | `Core/GameManager.cs`, `Core/Bootstrap.cs` |
| PlayerBikeController | `Player/PlayerBikeController.cs`, `Player/PlayerInput.cs` |
| TrafficManager + TrafficAI | `Traffic/TrafficManager.cs`, `Traffic/TrafficVehicle.cs`, `Traffic/TrafficSensing.cs`, `Traffic/TrafficLights.cs`, `Traffic/VehicleSpec.cs`, `Traffic/VehicleFactory.cs` |
| OrderManager | `Gameplay/OrderManager.cs` |
| RushLevelManager (+ hujan) | `Gameplay/RushLevelManager.cs` |
| ScoreManager, rating | `Gameplay/ScoreManager.cs` |
| ComboSystem | `Gameplay/ComboSystem.cs` |
| CameraManager | `Presentation/CameraManager.cs` |
| PoolManager | `Core/PoolManager.cs` |
| AudioManager | `Presentation/AudioManager.cs` |
| HUD | `Presentation/HUD.cs` |
| Kota, bahaya, banjir, razia | `World/CityMap.cs`, `World/CityBuilder.cs`, `World/HazardManager.cs` |
| Efek partikel & hujan | `Presentation/FxManager.cs` |
| Mesh/material/teks prosedural | `Core/MeshKit.cs`, `Core/Geo.cs` |
| Semua angka tuning | `Core/GameConfig.cs` |

## Test

- **Di Unity:** Window → General → Test Runner → EditMode → Run All (`Assets/OjolRush/Tests/EditMode`).
- **Tanpa Unity** (Mono + NUnitLite, juga dijalankan GitHub Actions):
  ```bash
  sudo apt-get install -y mono-mcs mono-runtime
  Tools/HeadlessTests/compile-check.sh   # compile semua script terhadap DLL UnityEngine 2021.3
  Tools/HeadlessTests/run.sh             # 26 test: skor, combo, rating, order, level, peta, simulasi lalu lintas
  ```
  Simulasi lalu lintas menjalankan AI asli selama 2 menit waktu game dengan 60 kendaraan dan memastikan tidak ada
  NaN, kendaraan tidak keluar jalan, tidak ada macet permanen, dan kendaraan jarang saling tembus.

## Status & batasan

Milestone 1–5 dari PRD sudah diimplementasikan dalam kode (riding, lalu lintas + salip, order + timer, level Rush +
event, juice). Yang **belum**:

- Belum pernah dimainkan di Unity Editor maupun di HP — kode ini ditulis dan diverifikasi di lingkungan tanpa
  Unity (compile check + unit test + simulasi headless). Harap cek rasa kontrol & angka tuning saat playtest
  pertama (milestone 6–7).
- Grafis & suara masih placeholder prosedural (low-poly dari kotak, suara sintetis). Aset asli bisa menggantikan
  `VehicleFactory`/`CityBuilder` dan `AudioManager.clips`.
- HUD memakai IMGUI supaya tanpa dependensi; untuk produksi sebaiknya pindah ke uGUI/UI Toolkit.
- Model bisnis belum ditentukan (sesuai PRD).

Tidak ada merek asli yang dipakai — aplikasinya fiktif (NgoJek-in).
