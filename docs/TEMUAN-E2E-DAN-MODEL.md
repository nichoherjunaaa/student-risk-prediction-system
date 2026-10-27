# Temuan Uji E2E dan Analisis Model Teknik Mesin

**Tanggal:** 26 Oktober 2026
**Basis kode:** commit `f60c2a8` (branch `main`) + perubahan yang belum di-commit
**Lingkup:** hasil uji end-to-end Playwright terhadap database yang sedang dipakai, dan pembuktian penyebab prediksi keliru pada satu mahasiswa Teknik Mesin.

---

## Kesimpulan

1. **Seluruh alur aplikasi berjalan.** 16/16 uji E2E lulus untuk kelima peran (admin, DPA, Kaprodi, Dekan, BAPSI): kelola pengguna, kelola berkas, cek format, preprocessing, latih & aktifkan model, prediksi (dari berkas dan dari template), telusur hasil, unduh PDF, hak akses.
2. **Prediksi "TIDAK SISIP" untuk mahasiswa ber-IPK 1.10 berasal dari model yang terlatih buruk, bukan dari kesalahan alur prediksi.** Input yang dikirim sistem identik dengan data mentah, dan hasil sistem identik dengan inferensi independen. Model hanya menangkap 23% mahasiswa sisip. Eksperimen latih ulang menunjukkan **penyebab utamanya ada di kode training**: `epochs=10` dan `patience=5` (skrip acuan memakai 100 dan 10), ditambah data latih yang hanya berisi satu angkatan. Lokasi kode dan cuplikannya ada di bagian [Lokasi kode penyebab](#lokasi-kode-penyebab).
3. Ada **lima temuan aplikasi** di luar model (T2–T6) yang perlu ditindaklanjuti.

| # | Temuan | Jenis | Tingkat |
|---|---|---|---|
| T1 | Model Teknik Mesin gagal mengenali mahasiswa sisip (recall 23%) | Model | **Tinggi** |
| T2 | Model aktif Matematika tidak cocok dengan berkas BAPSI (13% fitur) | Model / data | Tinggi |
| T3 | Pemeriksaan berkas untuk prodi yang tidak ada di berkas ±28 detik, pesan tidak jelas | Aplikasi | Sedang |
| T4 | Prediksi template menimpa batch prediksi berkas (prodi + angkatan + semester sama) | Aplikasi | Sedang |
| T5 | ID Batch (`#BATCH-YYMMDDHHMM`) tidak unik | Aplikasi | Rendah |
| T6 | Log Riwayat admin hanya menampilkan batch milik akun sendiri | Perilaku / UX | Info |

---

## T1 — Model Teknik Mesin gagal mengenali mahasiswa sisip

### Kasus

| | |
|---|---|
| NIM | `07818674325d3846cddaaa578e566544` (Teknik Mesin, angkatan 2023) |
| IPK 1 / 2 / 3 | 0.60 / 0.89 / 1.10 |
| Total SKS lulus s.d. semester 3 | 37 |
| Label asli di berkas akademik | **Sisip Program SKS Lulus < 50 SKS** |
| Hasil prediksi sistem | **TIDAK SISIP** (konsisten di semua batch) |
| Model aktif | `Model_2DCNN_teknik_mesin_20260908_104752` (id 15, akurasi validasi 77.3%) |

### Bukti bahwa alur prediksi benar dan kesalahan ada di model

Skrip: [`lampiran/verifikasi_model_tm.py`](lampiran/verifikasi_model_tm.py). Inferensi pada skrip ini memuat artefak model langsung (`.keras`, `_scaler.pkl`, `_encoders.pkl`, `_ley.pkl`, `_config.pkl`) dan mengikuti langkah `cnn_tabular_2d_v2.py`. Skrip ini **tidak** memanggil kode prediksi sistem.

| # | Pemeriksaan | Hasil | Arti |
|---|---|---|---|
| 1 | Label asli di berkas akademik | `Sisip Program SKS Lulus < 50 SKS` | Jawaban benarnya memang SISIP |
| 2 | Nilai mata kuliah yang dikirim sistem ke model vs. nilai terbaik di berkas mentah (s.d. semester 3) | **105/105 cocok** | Preprocessing sistem benar |
| 3 | Daftar fitur model (`scaler.feature_names_in_`) | 145 fitur, **tidak ada satu pun IPK/SKS** | IPK 1.10 tidak pernah dilihat model |
| 4 | Inferensi independen vs. hasil tersimpan sistem | Output sigmoid **0.5894** → TIDAK SISIP; **104/104** prediksi batch 124 identik | Kode prediksi sistem benar |
| 5 | Kontrafaktual: semua nilai mata kuliah diganti E / A | E → 0.4694 (SISIP), A → 0.5553 (TIDAK SISIP) | Model nyaris tidak membedakan mahasiswa terburuk dan terbaik |
| 6 | Kinerja model terhadap label asli, angkatan 2020–2023 | Recall SISIP **26/111 (23%)**, akurasi 76% | Model lemah secara umum, bukan kasus tunggal |

Catatan pemeriksaan 2: dua selisih yang sempat muncul berasal dari skrip pemeriksa, bukan dari sistem. Di berkas mentah tertulis `'Pendidikan Agama '` (berspasi di akhir) dan sistem merapikannya dengan benar. Nilai kosong *Formasi Cerdas dan Humanis 1* (0 SKS) ditulis sistem sebagai `-`, dan artinya sama.

#### Pemeriksaan 3 — IPK/SKS memang dibuang

Ini mengikuti skrip acuan `cnn_tabular_2d_v2.py` baris 42 dan 61:

```python
train_df = train_df.drop(['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3'], axis=1)
```

Backend menerapkan aturan yang sama (`backend/sisip/constants.py:43`, *"IPK/SKS hanya untuk laporan, bukan fitur"*). Angka IPK di halaman detail mahasiswa hanya ditampilkan untuk laporan. Eksperimen di bawah (varian D) menunjukkan bahwa membuang IPK/SKS **bukan** penyebab kesalahan ini.

#### Pemeriksaan 6 — Kinerja per angkatan

| Angkatan | Mahasiswa berlabel | Sisip asli | Tertangkap model |
|---|---|---|---|
| 2020 | 75 | 15 | 5 |
| 2021 | 107 | 26 | 12 |
| 2022 | 116 | 51 | 8 |
| 2023 | 92 | 19 | **1** |
| **Total** | 390 | 111 | **26 (23%)** |

| Label asli ↓ / Prediksi → | SISIP | TIDAK SISIP |
|---|---|---|
| **SISIP** | 26 | **85** |
| **TIDAK SISIP** | 9 | 270 |

Akurasi 76% terlihat baik karena sekitar 72% mahasiswa memang tidak sisip. Model yang selalu menjawab "TIDAK SISIP" pun akan mendapat akurasi sekitar 72%. Untuk *early warning system*, angka yang menentukan adalah recall kelas SISIP, dan nilainya hanya 23%.

### Eksperimen sebab-akibat

Skrip: [`lampiran/eksperimen_penyebab_model_tm.py`](lampiran/eksperimen_penyebab_model_tm.py). Model dilatih ulang dengan langkah yang sama persis seperti `backend/sisip/routes/training.py` baris 82–167. Setiap varian hanya mengubah satu faktor dan dijalankan dengan 3 seed. Semua varian diuji pada **angkatan 2023** (92 mahasiswa, 19 sisip), yang tidak pernah dipakai untuk latih. Eksperimen ini tidak menyimpan model dan tidak menyentuh database.

| Varian | Perubahan | Recall SISIP | Akurasi | NIM kasus (output per seed) |
|---|---|---|---|---|
| **A** | Meniru model aktif: angkatan 2021, epochs 10, patience 5, shuffle False, tanpa IPK | 39% | 81% | SISIP 0.40 · SISIP 0.43 · **TIDAK SISIP 0.55** |
| B | A + data latih 2020–2022 | 35% | 78% | TIDAK SISIP 0.51 · SISIP 0.49 · SISIP 0.50 |
| **B1** | B + **epochs 100, patience 10** | **49%** | **88%** | **SISIP 0.01 · SISIP 0.07 · SISIP 0.01** |
| B2 | B + shuffle True saja | 37% | 76% | TIDAK SISIP 0.51 · SISIP 0.48 · SISIP 0.48 |
| A1 | A + epochs 100, patience 10, shuffle True, **data tetap 2021 saja** | 11% | 82% | SISIP 0.47 · TIDAK SISIP 0.73 · TIDAK SISIP 0.59 |
| C | B + epochs 100, patience 10, shuffle True (= skrip acuan) | 49% | 89% | SISIP 0.03 · SISIP 0.03 · SISIP 0.01 |
| D | C + IPK 1–3 & Total SKS 3 sebagai fitur | 47% | 88% | SISIP 0.05 · SISIP 0.00 · SISIP 0.02 |

Output adalah peluang kelas TIDAK SISIP. Di bawah 0.5 berarti SISIP.

Cara membaca:

- **A → B1:** dengan epochs 100 dan patience 10, model berhenti menebak di sekitar 0.5. Mahasiswa kasus terdeteksi SISIP dengan sangat yakin (0.01–0.07) di semua seed, dan recall naik 35% → 49%. **Ini penyebab utama.**
- **A → A1:** epochs yang cukup tidak menolong bila data latihnya hanya satu angkatan (recall 11%). **Data latih satu angkatan adalah penyebab kedua.** Perbaikan baru muncul bila kedua faktor dibenahi bersama.
- **B → B2:** `shuffle=False` tidak berpengaruh berarti.
- **C → D:** menambahkan IPK/SKS **tidak** memperbaiki model. Dugaan awal bahwa IPK yang dibuang menjadi penyebab utama **tidak terbukti**.
- Varian A sangat bergantung pada seed: mahasiswa yang sama bisa SISIP atau TIDAK SISIP. Model aktif (recall 1/19 pada 2023) kemungkinan besar adalah hasil dari pelatihan yang belum konvergen ini, dengan seed yang kebetulan buruk.

### Lokasi kode penyebab

#### Penyebab utama — model berhenti dilatih terlalu cepat

**`backend/sisip/routes/training.py:53`.** Default backend hanya 10 epoch.

```python
    epochs_val = int(request.form.get('epochs', 10))
```

**`frontend/src/pages/AdminModel.jsx:25` dan `:44`.** Isian hyperparameter disembunyikan dari admin, sehingga nilai `10` ini selalu yang dikirim ke `/api/train` (`AdminModel.jsx:105`).

```jsx
const SHOW_HYPERPARAMS = false;
...
  const [epochs, setEpochs] = useState(10);
```

**`backend/sisip/routes/training.py:157`.** Batas kesabaran early stopping hanya 5 epoch.

```python
    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
```

Bandingkan dengan skrip acuan **`cnn_tabular_2d_v2.py:405` dan `:418`**:

```python
early_stopping = keras.callbacks.EarlyStopping(
    monitor="val_loss", patience=10, restore_best_weights=True
)
...
    epochs=100,
```

Dengan 10 epoch, bobot model belum terbentuk. Keluarannya menumpuk di sekitar 0.5: mahasiswa kasus mendapat 0.589, dan kontrafaktual "semua nilai E" pun hanya 0.469. Akibatnya keputusan sisip/tidak hampir acak.

#### Penyebab kedua — data latih hanya satu angkatan

**`backend/sisip/routes/training.py:69-74`.** Baris latih disaring sesuai isian *Tahun Angkatan Latih* di Master Model (`AdminModel.jsx:212`, placeholder `Contoh: 2020, 2021`).

```python
        if 'Angkatan' in df.columns and angkatan != '':
            # Normalisasi ('2023' vs '2023.0') supaya satu sel kosong di kolom lain
            # yang mengubah kolom Angkatan jadi float tidak diam-diam membuang baris.
            angkatan_list = [norm_str(a) for a in str(angkatan).split(',') if a.strip()]
            if angkatan_list:
                df = df[df['Angkatan'].map(norm_str).isin(angkatan_list)]
```

Artefak model aktif mencatat `scaler.n_samples_seen_ = 107`. Angka ini persis sama dengan jumlah mahasiswa Teknik Mesin angkatan 2021 (26 sisip + 81 tidak), sementara data berlabel 2020–2022 berjumlah 298. Hampir pasti model aktif dilatih dengan isian angkatan `2021` saja. Kode ini sendiri benar. Masalahnya, tidak ada peringatan bila data latih terlalu sedikit.

#### Faktor pendukung — nilai yang tidak dikenal dibaca sebagai kelas pertama

**`backend/sisip/predictor.py:114-119`**, sama dengan skrip acuan **`cnn_tabular_2d_v2.py:83`**:

```python
    # Kategori yang tidak dikenal model diganti ke kelas pertama (le.classes_[0]).
    for col, le in am.encoders.items():
        if col in df.columns:
            known = set(str(x) for x in le.classes_)
            as_str = df[col].astype(str)
            df[col] = le.transform(as_str.map(lambda s: s if s in known else str(le.classes_[0])))
```

Encoder tiap mata kuliah hanya mengenal nilai huruf yang muncul di 107 mahasiswa data latih. Untuk mahasiswa kasus, **18 nilai dibaca keliru**, misalnya:

| Mata kuliah | Nilai asli | Dibaca model sebagai | Kelas yang dikenal encoder |
|---|---|---|---|
| Fisika 2 | **E** | `-` (tidak mengambil) | `-` |
| Ilmu Hayat | **E** | `-` | `-` |
| Fisika 3 | **D** | `-` | `-`, A, B, C, E |
| Mekanika Teknik 2 | B- | `-` | `-`, A, B, C, D, E |
| Statistika | `-` | **A** | A, B, C, E |
| Pendidikan Agama | B- | **A** | A, B, C, E |

Di seluruh angkatan 2023, **2.420 dari 11.752 sel (21%)** diganti dengan cara ini. Sebagian nilai gagal dibaca "tidak mengambil", dan sebagian mata kuliah yang tidak diambil dibaca "A". Perilaku ini mengikuti skrip acuan, jadi implementasinya setia. Namun dampaknya membesar karena data latih hanya satu angkatan. Faktor ini tidak diuji terpisah dalam eksperimen. Analisis lengkapnya ada di [TEMUAN-ENCODER-NILAI-TAK-DIKENAL.md](TEMUAN-ENCODER-NILAI-TAK-DIKENAL.md).

#### Bukan penyebab (sudah diuji)

| Kode | Isi | Hasil uji |
|---|---|---|
| `backend/sisip/constants.py:38-48` + `training.py:82` | IPK/SKS dibuang dari fitur | Varian D ≈ C, tidak berpengaruh |
| `backend/sisip/routes/training.py:164` | `shuffle=False` | Varian B2 ≈ B, tidak berpengaruh |
| `backend/sisip/predictor.py:136` | Ambang `> 0.5` | Dengan model yang konvergen, output kasus 0.01–0.07, jauh dari ambang |

### Rekomendasi (perlu diputuskan bersama pembimbing)

1. **Samakan default training dengan skrip acuan:** `epochs=100` di `training.py:53` dan `AdminModel.jsx:44`, serta `patience=10` di `training.py:157`.
2. **Latih ulang model Teknik Mesin** dengan seluruh angkatan berlabel, misalnya isian angkatan dikosongkan atau `2020, 2021, 2022`.
3. Tampilkan peringatan di Master Model bila data latih kecil, dan simpan jumlah sampel serta hyperparameter ke `model_registry` supaya setiap model bisa ditelusuri.
4. Jadikan **recall kelas SISIP** sebagai metrik di registri, di samping akurasi.
5. Tinjau penanganan nilai yang tidak dikenal (`predictor.py:119`). Petakan nilai huruf ke skala mutu (A=4 … E=0) alih-alih ke `classes_[0]`. Langkah ini menyimpang dari skrip acuan, jadi perlu persetujuan.

---

## T2 — Model aktif Matematika tidak cocok dengan berkas BAPSI

Prediksi dari berkas untuk prodi Matematika ditolak dengan pesan:

> Model aktif prodi Matematika tidak cocok dengan berkas ini: hanya 13% fitur model ditemukan (133 kolom tidak ada, mis. ALGO102, CARC103, KEBN 101, MATH103, …).

Model `Model_2DCNN_matematika_20260804_222804` (id 9) dilatih dari data berformat lama. Fiturnya berupa kode mata kuliah, bukan nama mata kuliah. **Tindak lanjut:** latih ulang model Matematika dari hasil menu Preprocessing Data. Penolakannya sendiri sudah benar dan ditampilkan dengan jelas (screenshot: `e2e-screenshots/07-dekan-prediksi/00-matematika-model-tidak-cocok.png`).

## T3 — Pemeriksaan berkas lambat untuk prodi yang tidak ada di berkas

Untuk akun prodi Informatika, berkas BAPSI hanya berisi TE/TM/MAT. Pada kondisi itu, `GET /api/predict/sumber?prodi=Informatika` butuh **±28 detik setiap kali dipanggil**. Hasilnya pun berupa pesan yang tidak menjelaskan penyebabnya:

> Batas semester model tidak dapat ditentukan dari berkas yang ada.

Hasil gagal ini tidak di-cache, sehingga halaman Unggah Data terasa menggantung setiap kali dibuka. **Tindak lanjut:** periksa dulu apakah prodi tersebut ada di berkas PMB sebelum preprocessing berat dijalankan, lalu kembalikan pesan yang jelas, misalnya "Berkas PMB terbaru tidak memuat mahasiswa prodi Informatika".

## T4 — Prediksi template menimpa batch prediksi berkas

Sistem hanya menyimpan satu batch aktif per akun untuk kombinasi prodi + angkatan + semester yang sama. Pada uji E2E, akun DPA menjalankan prediksi dari berkas (104 mahasiswa, batch 120) lalu prediksi template (8 baris contoh, batch 121). Batch 120 otomatis terhapus (soft delete) dan tergantikan batch 121. **Tindak lanjut:** putuskan apakah penimpaan ini diinginkan. Kalau ya, beri tahu pengguna sebelum batch lama ditimpa.

## T5 — ID Batch tidak unik

`batch_name` dibentuk dari tanggal dan jam sampai menit (`#BATCH-2610260015`). Lima prediksi pada run terakhir hanya menghasilkan dua ID: batch 122, 123, dan 124 semuanya bernama `#BATCH-2610260015`. Di laporan dan Log Riwayat, ID ini tidak bisa dipakai untuk membedakan batch. **Tindak lanjut:** tambahkan detik atau id database ke nama batch.

## T6 — Log Riwayat admin hanya batch milik sendiri

`GET /api/history` menyaring `user_id = akun login` untuk semua peran, termasuk admin (`backend/sisip/routes/history.py:29`). Batch yang dijalankan akun lain, termasuk akun admin lain, tidak muncul di Log Riwayat. Ini sesuai komentar di kode, tetapi sempat membingungkan saat meninjau hasil uji. **Tindak lanjut:** konfirmasi apakah admin seharusnya bisa melihat semua batch.

---

## Lampiran — Uji E2E

### Menjalankan

```bash
# backend (:5000) dan Vite (:5173) menyala, memakai database yang sedang dipakai
cd frontend && npm run test:e2e
```

| Berkas | Isi |
|---|---|
| `frontend/playwright.config.js` | Konfigurasi (Chromium, 1 worker, base URL dari `E2E_BASE_URL`) |
| `frontend/e2e/helpers.js` | Login, screenshot, unduhan |
| `frontend/e2e/roles.spec.js` | Navigasi & hak akses per peran (7 uji) |
| `frontend/e2e/full-flow.spec.js` | Alur lengkap lintas peran (9 uji) |
| `e2e-screenshots/` | Screenshot hasil uji (102 PNG) |
| `e2e-screenshots/akun-uji.txt` | Daftar akun uji setiap run |

### Data yang sengaja disisakan

Uji alur lengkap **tidak menghapus** data yang dibuatnya, supaya hasilnya bisa diperiksa di aplikasi. Setiap run memakai NIP dan nama folder baru, jadi data akan **bertambah** di setiap run:

- 4 akun uji (DPA Teknik Mesin, Kaprodi Teknik Elektro, Dekan, BAPSI), dengan password `E2eTest#2026`. NIP-nya tercatat di `akun-uji.txt`.
- Folder `E2E-<waktu> Berkas` berisi `20260605_Data_PMB.xlsx` dan `Data_akademik_te_tm_mat.xlsx`.
- Batch prediksi milik akun uji dan milik akun demo `Admin Tester`.
- Model Teknik Mesin hasil latih uji (nonaktif). Model aktif tiap prodi dikembalikan seperti semula.

Cadangan database sebelum uji pertama dibuat di direktori sementara sesi (tidak permanen).

### Run terakhir (26 Okt 2026)

| Batch | ID Batch | Akun | Cara | Prodi | Hasil |
|---|---|---|---|---|---|
| 120 | `#BATCH-2610260014` | DPA uji | Dari berkas | Teknik Mesin 2023 | 104 mhs (2 sisip). Ditimpa batch 121, lihat T4 |
| 121 | `#BATCH-2610260014` | DPA uji | Template | Teknik Mesin 2023 | 8 mhs (1 sisip) |
| 122 | `#BATCH-2610260015` | Kaprodi uji | Dari berkas | Teknik Elektro 2023 | 81 mhs (13 sisip) |
| 123 | `#BATCH-2610260015` | Dekan uji | Dari berkas | Teknik Elektro 2023 | 81 mhs (13 sisip) |
| 124 | `#BATCH-2610260015` | Admin Tester | Dari berkas | Teknik Mesin 2023 | 104 mhs (2 sisip) |
| – | – | Dekan uji | Dari berkas | Matematika 2023 | Ditolak, lihat T2 |
