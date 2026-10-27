# Status Proyek SISIP — Kondisi Sekarang

**Tanggal:** 3 September 2026
**Basis:** `main` @ `b8fa0a2` + perubahan sesi ini (belum di-commit)

Ringkasan: **fitur utama (training + prediksi) terintegrasi dan berjalan benar
secara teknis.** Yang tersisa adalah (1) beberapa perbaikan teknis kecil yang
belum dikerjakan, dan (2) keputusan desain/data yang menunggu pembimbing —
lihat [`PERTANYAAN-PEMBIMBING.md`](PERTANYAAN-PEMBIMBING.md).

Verifikasi otomatis saat ini:

| Uji | Hasil |
|---|---|
| `backend/e2e_test.py` | **25 / 25 pass** |
| `backend/verify_model_integration.py` | train→aktivasi→prediksi lolos, held-out acc 0.967 |
| `npm run build` (frontend) | ✅ sukses |

---

## 1. SUDAH BERJALAN DENGAN BENAR (terverifikasi)

### Machine Learning

| Hal | Bukti verifikasi |
|---|---|
| **Integrasi penuh** train → simpan artefak → registri → aktivasi → prediksi | 604/604 hasil identik antara jalur HTTP dan pipeline model langsung |
| **Arsitektur CNN** = `model_f` dari `cnn_tabular_2d_v2.py` | layer & 11.969 parameter identik |
| **Pipeline latih == pipeline prediksi** (encoding, unknown→kelas-0, scaling, padding, reshape) | urutan kolom Excel diacak → hasil tetap sama (reindex bekerja) |
| **Model membedakan kelas dengan benar** | held-out (20% data berlabel): akurasi 0.967, presisi 1.00, recall 0.80, mengungguli baseline 0.835 |
| Model per-prodi disimpan lengkap (`.keras` + scaler + encoders + ley + config) | dicek di E2E |
| Prediksi menyimpan hasil + detail per mahasiswa ke DB | E2E |
| Peringatan nilai tak dikenal model ditampilkan ke pengguna | `Results.jsx` banner + sheet `NILAI_VALID` |

### Aplikasi Web

| Hal | Catatan |
|---|---|
| **Autentikasi token** (login → Bearer token, `require_auth` / `require_role`) | baru; endpoint tanpa token → 401, DPA ke endpoint admin → 403 |
| Password hash lama (SHA-256) & baru (PBKDF2) sama-sama bisa login | fallback verifikasi |
| Proteksi route frontend (`ProtectedRoute`, admin-only untuk `/admin/*` & `/history`) | baru |
| Unduh Template Excel (server-side, terisi contoh in-distribution) | E2E |
| Diagnosa berkas tidak cocok (Prodi/Angkatan/Semester) dengan pesan spesifik | E2E |
| Prediksi batch + tampil hasil + grafik per angkatan + unduh PDF | manual |
| Dedup batch per (prodi + angkatan + **semester**) | baru; E2E membuktikan batch semester berbeda tidak saling menimpa |
| Filter angkatan tahan sel kosong (`'2023'` vs `'2023.0'`) di predict, preview, **dan train** | konsisten sekarang |
| Metrik model yang dicatat = epoch `val_loss` terbaik (bukan epoch terakhir) | baru |
| Migrasi skema DB idempoten saat start | baru; kolom baru otomatis di-`ALTER` |
| Aktivasi model menolak jika berkas `.keras`/`.pkl` tidak lengkap | baru |
| Session timeout (idle 10 menit) | ada dari sebelumnya |

---

## 2. DIPERBAIKI DI SESI INI — belum di-commit

| # | Masalah | Jenis | File |
|---|---|---|---|
| 1 | Tidak ada autentikasi sama sekali (semua endpoint & route terbuka) | keamanan | `backend/app.py`, `frontend/src/App.jsx`, `frontend/src/lib/http.js` |
| 2 | Batch prediksi semester berbeda saling menimpa (kolom `semester` tak ada) | bug | `backend/app.py:1237-1255` + migrasi |
| 3 | Metrik akurasi/loss diambil dari epoch terakhir, bukan epoch terbaik | bug | `backend/app.py:830-847` |
| 4 | Filter angkatan `/api/train` meleset saat ada sel kosong (kolom jadi float) | bug | `backend/app.py:697-706` |
| 5 | `find_grid_dimensions` menghasilkan grid `1×n` untuk jumlah fitur bilangan prima → training gagal `ValueError` 500 | bug (dorman) | `backend/app.py:244-261` |
| 6 | Tidak ada migrasi skema DB (kolom baru tak ter-`ALTER` di DB lama) | bug | `backend/app.py:139-147` |
| 7 | Filter Prodi pakai `str.contains` regex → error jika label mengandung `()`/`+` | bug (potensial) | `backend/app.py:670, 710, 929` |
| 8 | Aktivasi model tidak cek kelengkapan berkas | issue | `backend/app.py:1343-1367` |
| 9 | Halaman Hasil Prediksi tidak menampilkan daftar mahasiswa beresiko | issue UX | `frontend/src/pages/Results.jsx` |
| 10 | Determinisme TF diset setelah `import tensorflow` (diabaikan) | bug | `backend/app.py:1-7` |
| 11 | ~135 baris kode `predict()` mati (dikomentari) + import ganda/sampah | kebersihan | `backend/app.py` |
| 12 | Catatan "IPK/SKS tidak dipakai model" di halaman detail mahasiswa | transparansi | `frontend/src/pages/DetailStudent.jsx` |
| 13 | IPK `0.00` tampil `-`; `colSpan` tabel salah | kosmetik | `frontend/src/pages/DetailBatch.jsx` |

Ditambah: `backend/e2e_test.py`, `backend/verify_model_integration.py`,
`docs/AUDIT-TEMPLATE-DAN-FITUR-MODEL.md`, `docs/PERTANYAAN-PEMBIMBING.md`,
`docs/STATUS-PROYEK.md` (dokumen ini).

---

## 3. ISSUE / BUG / ERROR YANG MASIH ADA

### 3A. Perlu keputusan pembimbing (desain & data) — paling berdampak

| # | Masalah | Tingkat | Detail |
|---|---|---|---|
| A1 | **IPK & Total SKS dibuang dari fitur model** | KRITIS | `backend/app.py:725`. Label `SISIP` ~98–99% bisa direproduksi dari IPK+SKS (decision tree depth-2 = 98.7%), yaitu 4 kolom yang dibuang. Model menebak aturan 2-variabel ini secara tidak langsung dari 153 kolom nilai. Lihat `PERTANYAAN-PEMBIMBING.md` §2.1. |
| A2 | **Definisi label `SISIP` tidak diketahui** — rumus otomatis atau keputusan manual? | KRITIS | Kalau rumus → mungkin tak butuh ML. Kalau manual → IPK/SKS tetap wajib jadi fitur. |
| A3 | **Kemungkinan label ambigu di sumbernya** — "sisip" remedial vs "mahasiswa sisipan/afirmasi" | KRITIS | Contoh: `TRAIN_SEM3` baris 343 — IPK 4.00→3.62 konsisten, nilai A semua, asal NTT → **dilabeli SISIP**. Kalau dua makna tercampur dalam satu kolom `Label`, model tak akan pernah belajar benar. |
| A4 | **Model prodi Matematika / Teknik Mesin / Teknik Elektro dilatih dari data yang tidak konsisten** | TINGGI | `backend/app.py:709-710` (filter prodi dilewati diam-diam), `:702-703` (tak ada validasi keragaman data). Bukti dari encoder tersimpan: kolom `PPKMB002` — model **Informatika** kenal `[A,B,C,D,E,F]`, model **Teknik Mesin** hanya `[A,E]` → dilatih dari sampel jauh lebih kecil. Prediksi model TM tidak bisa dipercaya (lihat A8). `PERTANYAAN-PEMBIMBING.md` §2.11. |
| A5 | **37% fitur konstan** (56 dari 153 kolom mata kuliah isinya `E` semua) | SEDANG | Uji permutasi: diacak → akurasi tidak bergeser sama sekali. Grid CNN 9×17 sepertiganya nol. Perlu kepastian: `E` seragam itu valid ("belum ditempuh") atau artefak merge. |
| A6 | **Pemetaan 153 fitur → grid 9×17 hanya berdasarkan urutan kolom** | SEDANG | Kode IGTD (pemetaan berbasis korelasi) ada di `cnn_tabular_2d_v2.py:141-214` tapi dikomentari. Konvolusi 3×3 mencampur fitur tak berhubungan → premis CNN lemah. Pertanyaan metode. |
| A7 | **Kenapa 2D-CNN untuk data tabular** (bukan MLP / XGBoost) | SEDANG | Aturan `IPK 3 < 2.0` (1 baris) = akurasi 94%, setara CNN 153 fitur. Perlu klarifikasi apakah CNN ini requirement metode. |
| A8 | **Nilai huruf mutu tak dikenal diganti diam-diam ke nilai TERBAIK (`A`)** | TINGGI | `backend/app.py:998` `else str(le.classes_[0])`; encoder di-fit di `:735-740`; pesan dirakit `:1152-1163`; asal `cnn_tabular_2d_v2.py:79-84`. 66 dari 141 kolom kategorikal → nilai tak dikenal jadi `A`. Contoh nyata: `PPKMB002 (D, F → A)`. Karena model prediksi SISIP dari jumlah nilai buruk → **hasil terdorong ke "TIDAK SISIP"**, mahasiswa berisiko lolos deteksi. Perlu keputusan: konservatif (→ nilai terburuk), kategori `__UNKNOWN__`, atau tolak berkas. Semua opsi butuh retrain. `PERTANYAAN-PEMBIMBING.md` §2.9 + pertanyaan C.12. |

### 3B. Bisa diperbaiki tanpa menunggu pembimbing (teknis murni)

| # | Masalah | Tingkat | Lokasi | Dampak |
|---|---|---|---|---|
| B1 | **`StandardScaler` di-fit termasuk data validasi** (fit sebelum `train_test_split`) | SEDANG | `backend/app.py:748-756` | Metrik `val_accuracy` yang dicatat sedikit optimistis (kebocoran ringan). Perbaikan: split dulu → `fit` pada train saja. |
| B2 | **Loop training menyimpang dari `cnn_tabular_2d_v2.py`** | SEDANG | `backend/app.py:697` (`epochs` default 10 vs 100), `:800` (`patience` 5 vs 10), `:807` (`shuffle=False`) | Model di sistem berpotensi under-training dibanding versi Colab. **Sudah disamakan (27 Okt 2026):** epochs 100, patience 10, shuffle default. |
| B3 | `LabelEncoder` di-fit pada seluruh X sebelum split (val ikut) | RENDAH | `backend/app.py:735-740` | Kebocoran kategori kecil. |
| B3b | **Encoding huruf mutu urut abjad, bukan urut baik-buruk** | SEDANG | `backend/app.py:735-740` (`LabelEncoder` untuk semua kolom nilai) · `cnn_tabular_2d_v2.py:77-85` | `A=0, A-=1, B=2, B+=3, …` → `B+` bernilai lebih tinggi dari `B` (urutan `+` terbalik). Perbaikan: pemetaan tetap `{A:4.0, A-:3.7, B+:3.3, B:3.0, …, E:0, F:0}`. Butuh retrain. `PERTANYAAN-PEMBIMBING.md` §2.10 + pertanyaan C.13. |
| B4 | `df.reindex(columns=expected_cols)` di `predict()` **tidak dibungkus try/except** | RENDAH | `backend/app.py:973` | Jika berkas Excel punya kelainan struktur kolom langka → 500 HTML, bukan JSON. Edge case (pandas biasanya auto-mangle kolom duplikat). |
| B5 | `cnn_tabular_2d_v2.py:252` masih punya bug `find_grid_dimensions` bilangan prima | RENDAH | skrip riset, tidak dipakai runtime | Konsistensi saja. |
| B6 | Tidak ada evaluasi test-set berlabel yang **tersimpan** di registri | RENDAH | `backend/app.py:830-847` | Hanya `val_accuracy`/`val_loss` internal. Sulit menilai model dari luar tanpa skrip terpisah. `verify_model_integration.py` menutupi ini secara manual. |
| B7 | Tidak ada rate-limit / lockout pada `/api/login` | RENDAH | `backend/app.py` | Brute-force password mungkin. |
| B8 | CORS default `*` (bisa dibatasi lewat `SISIP_CORS_ORIGINS`) | RENDAH | `backend/app.py:38-42` | Di belakang Nginx same-origin, tapi kalau port 5000 terbuka publik → akses lintas-origin. |
| B9 | `SISIP_SEED_DEMO_USERS` default `1` di `docker-compose.yml` | RENDAH | `docker-compose.yml` | Akun demo (`admin.test@sisip.test` / `Admin#2026`) aktif di produksi kecuali di-set `0`. Sudah didokumentasikan di `.env.example`. |

### 3C. Kecil / kosmetik

| # | Masalah | Lokasi |
|---|---|---|
| C1 | `AdminRoles` ("Manajemen Role") murni state lokal — tidak tersimpan ke mana pun (mockup) | `frontend/src/pages/AdminRoles.jsx` |
| C2 | Tombol User / Settings / Bell di header tidak berfungsi (dekoratif) | `frontend/src/components/Header.jsx` |
| C3 | `Upload.jsx` — pratinjau tidak refresh saat dropdown Semester diubah (`useEffect` deps) | `frontend/src/pages/Upload.jsx:46-50` |
| C4 | `History.jsx` — badge "2026" & grafik donat `strokeDasharray="75,100"` hardcoded | `frontend/src/pages/History.jsx` |
| C5 | `Results.jsx` — `setData` di-assign tapi tidak dipakai; `data` dari `localStorage` bisa basi | `frontend/src/pages/Results.jsx:14` |
| C6 | `backend/database.db` (0 byte) ter-track di git — file sampah | `backend/database.db` |
| C7 | `npm run lint` — 41 error pre-existing (`'React' is defined but never used`, dll.); tidak diblokir CI | seluruh `frontend/src` |
| C8 | Progress bar training/prediksi adalah animasi palsu (bukan progres nyata) | `AdminModel.jsx`, `Upload.jsx` — disengaja |

---

## 4. Status commit & deploy

- **3 commit perbaikan template** (`367601a`, `88cc645`, `b8fa0a2`) sudah di `origin/main` — akan ter-deploy ke VPS lewat Jenkins.
- **Semua perubahan sesi ini belum di-commit** (14 file modified + 5 file/dir baru).
- **Sebelum deploy perubahan sesi ini ke VPS**, tambahkan ke Jenkins secret file `sisip-env`:
  - `SISIP_SECRET_KEY=<acak panjang>` — tanpa ini token pakai default `dev-insecure-secret-change-me` (bisa dipalsukan).
  - `SISIP_SEED_DEMO_USERS=0` — matikan akun demo di produksi.
  - opsional `SISIP_CORS_ORIGINS=https://<domain>`.

---

## 5. Urutan tindak lanjut yang disarankan

1. **Bawa `PERTANYAAN-PEMBIMBING.md` ke pembimbing** — A1–A3 (butuh/tidaknya ML),
   A6 & A8 (konsistensi data + kebijakan nilai tak dikenal), C.12–C.13 (skala huruf mutu).
2. **Satu retrain untuk semua**: begitu pembimbing menjawab, kerjakan sekaligus
   A1 (IPK/SKS) + A4/A8 (retrain semua prodi dari data sama, tangani nilai tak dikenal)
   + B2 (epochs/patience/shuffle) + B3b (encoding huruf mutu ordinal). Semua butuh
   latih ulang model — jangan retrain berkali-kali.
3. B1, B3, B4, B6 → perbaikan teknis murni, bisa kapan saja.
4. Commit perubahan sesi ini + set `SISIP_SECRET_KEY` di Jenkins sebelum deploy.
5. Bersihkan C1–C8 saat ada waktu (tidak mendesak).

> **Peringatan "nilai tak dikenal" di UI** (`Results.jsx:195-207`): jangan dimatikan
> sampai A8 diperbaiki — itu satu-satunya indikasi bahwa data prediksi sedang
> dipalsukan diam-diam. Setelah A8 beres, peringatan hanya akan muncul untuk
> salah-ketik huruf mutu yang nyata, dan itu memang layak ditampilkan.
