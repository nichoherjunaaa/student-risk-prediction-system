# Pertanyaan untuk Pembimbing + Letak Masalah di Kode Model

**Tanggal:** 3 September 2026
**Konteks:** Fitur utama (prediksi mahasiswa berpotensi sisip) sudah terintegrasi dan
berjalan — training → simpan artefak → aktivasi → prediksi terbukti konsisten
(uji: 604/604 hasil identik antara jalur HTTP dan pipeline model langsung).
Yang tersisa adalah pertanyaan **desain/domain** yang tidak bisa dijawab dari kode
saja, plus beberapa **penyimpangan kode** dari skrip riset `cnn_tabular_2d_v2.py`.

**Arsitektur model:** `backend/app.py` `build_cnn_model()` sudah = `model_f` dari
`cnn_tabular_2d_v2.py` (identik, 11.969 parameter). Yang belum sepenuhnya sama
adalah pipeline data & loop training (lihat Bagian 2).

---

## Ringkasan temuan utama

**Penentu SISIP / TIDAK SISIP saat ini = jumlah nilai mata kuliah buruk (D/D+/D-/E/F/T).**
Uji permutasi pada model Informatika aktif:

| Kelompok fitur | Jumlah kolom | Akurasi jika diacak | Kerusakan |
|---|---:|---:|---:|
| Nilai mata kuliah | 83 | 0.835 | **-0.135** |
| Nilai tes masuk | 6 | 0.962 | -0.008 |
| Biodata / asal sekolah | 8 | 0.967 | -0.003 |
| 56 mata kuliah konstan (isi `E` semua) | 56 | 0.970 | 0.000 |

*(akurasi awal 0.970)*

**IPK & Total SKS dibuang sebelum training**, padahal:

- Di "zona abu-abu" (304 dari 604 mhs dengan 57–72 nilai buruk, di mana jumlah nilai
  buruk tidak bisa memutuskan): mahasiswa SISIP rata-rata **IPK 3 = 1.63**, yang
  TIDAK SISIP rata-rata **IPK 3 = 2.96**.
- Aturan satu baris `IPK 3 < 2.00` menghasilkan **akurasi 94.2% / recall 90%** —
  **setara CNN 153 fitur**.
- Label sendiri tumpang tindih pada jumlah nilai buruk (SISIP min 57, TIDAK SISIP
  maks 72) → ada faktor penentu yang **tidak ada di fitur**.

Kesimpulan sementara: membuang IPK/SKS memasukkan *label noise* — model dipaksa
menebak di wilayah borderline yang justru paling penting untuk Early Warning System.

**Selain itu**, cara model menangani nilai huruf mutu bermasalah:

- Huruf mutu yang tidak muncul di data latih (mis. `D`, `F` pada kolom `PPKMB002`
  model Teknik Mesin yang hanya kenal `A`/`E`) diganti **diam-diam ke `A`** — nilai
  terbaik — sehingga mahasiswa gagal bisa terbaca aman (§2.9).
- `LabelEncoder` mengurutkan huruf mutu secara abjad: `B+` bernilai lebih tinggi
  dari `B` (urutan terbalik) (§2.10).
- Keempat model prodi dilatih dari data yang tidak konsisten — model Teknik Mesin
  jelas dari sampel yang jauh lebih kecil (§2.11).

---

## BAGIAN 1 — Pertanyaan untuk pembimbing

### A. Definisi label "sisip" (paling krusial)

1. **Apa kriteria resmi seorang mahasiswa dinyatakan "sisip"?** Ada SK / rumus baku?
   (mis. IPK < 2.00, atau SKS lulus < ambang tertentu, atau kombinasi, atau
   keputusan panitia akademik)
2. **Kolom `Label` di dataset diisi berdasarkan apa** — hasil rumus otomatis, atau
   keputusan manual manusia?
3. **Kapan `Label` dan `IPK 1/2/3` di berkas diambil** — sebelum atau sesudah
   keputusan/pelaksanaan program sisip? *(Menentukan apakah IPK boleh jadi fitur
   atau justru kebocoran label.)*
4. Jika `Label` ternyata = hasil rumus IPK/SKS: **apakah proyek ini memang butuh
   machine learning**, atau cukup mengimplementasikan rumusnya? *(ML bermakna kalau
   label = judgment manusia yang tidak bisa dirumuskan.)*

### B. Fitur & data

5. **56 dari 153 kolom mata kuliah isinya `E` semua** di data latih. Itu berarti
   "mata kuliah belum ditempuh", atau artefak penggabungan data? Kalau belum
   ditempuh — apakah `E` representasi yang benar, atau seharusnya dikosongkan /
   ditandai khusus (`BELUM_DITEMPUH`)?
6. **Dataset hanya berisi mahasiswa Informatika** (tidak ada kolom `Prodi`). Model
   "Matematika / Teknik Mesin / Teknik Elektro" di sistem saat ini dilatih dari data
   Informatika yang sama. Apakah data prodi lain memang tersedia, atau fitur
   multi-prodi ini belum bisa diisi?
7. **Nilai tes masuk & biodata** (provinsi asal, sekolah asal, jalur pendaftaran)
   kontribusinya ~0 terhadap prediksi. Tetap dipertahankan sebagai fitur, atau
   boleh dibuang supaya model lebih ramping dan mudah dijelaskan?

### C. Metode

8. `cnn_tabular_2d_v2.py` menyusun 153 fitur jadi grid 9×17 **berurutan apa adanya**
   (kode pemetaan fitur→pixel berbasis korelasi / IGTD ada di baris 141–214 tapi
   **dikomentari**). Apakah pembimbing mengharapkan pemetaan spasial yang bermakna,
   atau urutan kolom apa adanya sudah cukup? *(CNN mengandalkan korelasi antar
   pixel bertetangga; kalau urutannya acak, keunggulan CNN hilang.)*
9. **Kenapa 2D-CNN untuk data tabular** (bukan MLP / Random Forest / XGBoost)?
   Requirement metode dari pembimbing, atau pilihan bebas? *(Untuk 153 fitur
   tabular, model lebih sederhana biasanya setara/lebih baik dan lebih
   interpretable.)*
10. **Prioritas metrik** untuk Early Warning System: **recall** (jangan sampai
    mahasiswa berisiko lolos deteksi) atau **presisi** (jangan salah tuduh)?
    Saat ini ~4 dari 20 mahasiswa SISIP tidak terdeteksi (recall ~0.80).
11. **Ambang keputusan** default 0.5. Untuk sistem peringatan dini, apakah boleh
    diturunkan (mis. 0.35) supaya lebih sensitif menangkap mahasiswa berisiko?
12. **Nilai huruf mutu yang tidak dikenal model** (mis. `B-` di kolom yang saat
    latih hanya pernah lihat `A/B/C`) saat ini diganti diam-diam ke nilai
    **terbaik** (`A`). Apakah pembimbing setuju kebijakan yang benar untuk Early
    Warning System adalah **konservatif** — nilai tak dikenal dipetakan ke yang
    **terburuk**, atau berkas ditolak sampai datanya dibetulkan? Lihat §2.9.
13. **Pemetaan huruf mutu → angka**: apakah pembimbing punya skala baku
    (mis. `A=4.00, A-=3.67, B+=3.33, …, E=0`)? Saat ini `LabelEncoder` urut abjad
    membuat `B+` bernilai lebih besar dari `B` (urutan terbalik). Lihat §2.10.

### D. Operasional

14. **Data angkatan baru (2023/2024) belum punya `Label`** (`TEST_SEM3`).
    Bagaimana rencana memverifikasi apakah prediksi model benar di angkatan yang
    statusnya belum diketahui?
15. **Retrain model**: siapa yang menjalankan, seberapa sering, pakai data angkatan
    mana? Apakah tiap tahun ditambah angkatan baru?

---

## BAGIAN 2 — Letak masalah di kode model

Referensi berdasarkan kondisi kode saat ini (`backend/app.py`) dan skrip riset
(`cnn_tabular_2d_v2.py`). Kolom "Di mana" menandai apakah masalahnya di sistem saja,
di skrip riset saja, atau di keduanya.

### 2.1 — KRITIS: IPK & Total SKS dibuang dari fitur

| | |
|---|---|
| **File / baris** | `backend/app.py:725` (fungsi `train_model`) |
| | `backend/app.py:975` (fallback di `predict`, jarang terpakai) |
| | `backend/app.py:402-405` (konstanta `TEMPLATE_IDENTITY_COLS`) |
| | `cnn_tabular_2d_v2.py:42` dan `:61` |
| **Kode** | `drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']` |
| **Masalah** | `NIM`, `Nomor PMB`, `Angkatan` benar dibuang (identitas). Tapi `IPK 1/2/3` dan `Total SKS 3` **ikut terbuang**, padahal itu indikator akademik paling relevan dan tersedia saat prediksi. |
| **Dampak** | Model kehilangan variabel pemisah utama; dipaksa menebak dari nilai mata kuliah saja di wilayah borderline. Batas atas akurasi ~95% tak bisa ditembus arsitektur apa pun. |
| **Di mana** | **Keduanya** — `app.py` menyalin persis dari `cnn_tabular_2d_v2.py`. Jadi kalau diubah, dua-duanya harus diubah. |
| **Butuh keputusan pembimbing** | Pertanyaan A.3 (apakah IPK diambil sebelum/sesudah keputusan sisip). |
| **Perbaikan** | Hapus `'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3'` dari `drop_cols` di `app.py:725`, keluarkan dari `TEMPLATE_IDENTITY_COLS` (`app.py:402`), sesuaikan `_build_sample_rows`, lalu **latih ulang keempat model** (jumlah fitur 153 → 157, model lama tidak kompatibel). |

### 2.2 — SEDANG: 37% fitur konstan tidak dibuang

| | |
|---|---|
| **File / baris** | `backend/app.py:736-749` (loop encoding + `StandardScaler`) |
| | `cnn_tabular_2d_v2.py:77-96` |
| **Masalah** | 56 dari 153 kolom mata kuliah hanya punya satu nilai (`E`) di data latih. Setelah `LabelEncoder` → 0, setelah `StandardScaler` → 0 (varians nol). Tidak ada langkah membuang kolom varians-nol sebelum membentuk grid. |
| **Dampak** | Grid "citra" 9×17 yang jadi input CNN, sepertiganya (56 sel) konstan nol. Kapasitas model & komputasi terbuang; struktur spasial makin tidak bermakna. |
| **Di mana** | **Keduanya.** |
| **Butuh keputusan pembimbing** | Pertanyaan B.5 (apakah `E` seragam itu valid atau artefak). |
| **Perbaikan** | Setelah encoding, buang kolom dengan `nunique() <= 1` sebelum `find_grid_dimensions`. Konsekuensi: `n_features` berubah (153 → ~97) dan geometri grid berubah → retrain. |

### 2.3 — SEDANG: Scaler di-fit termasuk data validasi (kebocoran ringan)

| | |
|---|---|
| **File / baris** | `backend/app.py:748-756` |
| **Kode** | `global_scaler.fit_transform(X)` (baris 749) dijalankan **sebelum** `train_test_split(...)` (baris 751). |
| **Masalah** | `mean_` dan `scale_` scaler dihitung dari seluruh data, termasuk 20% yang kemudian jadi set validasi. Metrik validasi jadi sedikit optimistis. |
| **Dampak** | Kecil untuk StandardScaler, tapi metodologi kurang bersih. Angka `val_accuracy` yang dilaporkan ke registri sedikit lebih tinggi dari yang seharusnya. |
| **Di mana** | `app.py` (dan efek serupa ada di `cnn_tabular_2d_v2.py:95` karena `validation_split` mengambil ekor data yang sudah di-scale). |
| **Perbaikan** | Split dulu → `scaler.fit(X_train)` → `scaler.transform(X_val)`. |

### 2.4 — SEDANG: Loop training menyimpang dari skrip riset

| Parameter | `cnn_tabular_2d_v2.py` | `backend/app.py` | Baris di `app.py` |
|---|---|---|---|
| `epochs` | 100 | **default 10** (field disembunyikan di UI, `AdminModel.jsx:22` `SHOW_HYPERPARAMS = false`) | `697` |
| `EarlyStopping(patience=)` | 10 | **5** | `800` |
| `model.fit(shuffle=)` | default (`True`) | **`False`** | `807` |
| Strategi validasi | `validation_split=0.2` (20% ekor, tak diacak) | `train_test_split(stratify=y, random_state=42)` — **lebih baik** | `751-756` |

| | |
|---|---|
| **Masalah** | `epochs=10` + `patience=5` berpotensi **under-training** dibanding versi Colab (100 epoch). `shuffle=False` membuat urutan batch sama tiap epoch → bisa menurunkan generalisasi. |
| **Dampak** | Model di sistem bisa sedikit di bawah potensi yang ditunjukkan di eksperimen Colab. |
| **Di mana** | `app.py` menyimpang dari `cnn_tabular_2d_v2.py`. |
| **Perbaikan** | Naikkan default `epochs` ke 100 dan `patience` ke 10; hapus `shuffle=False`. Perubahan kecil dan aman (EarlyStopping tetap menahan overfitting). |

### 2.5 — SUDAH DIPERBAIKI: `find_grid_dimensions` gagal untuk jumlah fitur bilangan prima

| | |
|---|---|
| **File / baris** | `backend/app.py:244-261` (**sudah diperbaiki**) · `cnn_tabular_2d_v2.py:252-257` (**masih ada**) |
| **Masalah lama** | Bila `n_features` bilangan prima (mis. 157 = 153 + IPK/SKS), satu-satunya faktorisasi adalah `1 × n` → tinggi grid = 1 → `MaxPooling2D` kedua menghasilkan dimensi 0 → training gagal `ValueError` (HTTP 500). |
| **Status** | Di `app.py` sudah dijamin sisi grid minimal 4, sisanya di-padding. `n=153` tetap `9×17` sehingga model lama tidak terganggu. `cnn_tabular_2d_v2.py` **belum** diperbaiki. |
| **Catatan** | Bug ini akan langsung muncul begitu perbaikan 2.1 diterapkan (157 fitur = prima). Sudah diantisipasi. |

### 2.6 — RENDAH: Grid 2D dibentuk dari urutan kolom, bukan pemetaan bermakna

| | |
|---|---|
| **File / baris** | `backend/app.py:769-770` (training) & `:1018` (prediksi) — reshape `-1, height, width, 1` |
| | `cnn_tabular_2d_v2.py:141-214` (kode IGTD **dikomentari**), `:259-274` (yang aktif) |
| **Masalah** | Premis 2D-CNN adalah pixel bertetangga saling berkorelasi. Di sini 153 fitur hanya di-`reshape` berurutan ke 9×17, jadi kolom `Matematika_1` dan `Fisika_1` bisa "bertetangga" atau tidak secara acak. Konvolusi 3×3 mencampur fitur yang tak berhubungan. |
| **Dampak** | CNN tetap belajar (lewat lapisan Dense setelah Flatten), tapi bagian konvolusinya kehilangan justifikasi teoretis. Ini pertanyaan metode, bukan bug. |
| **Di mana** | **Keduanya.** |
| **Butuh keputusan pembimbing** | Pertanyaan C.8. |

### 2.7 — RENDAH: Tidak ada evaluasi pada test set berlabel yang tersimpan

| | |
|---|---|
| **File / baris** | `backend/app.py:830-847` (hanya menyimpan `val_accuracy` / `val_loss`) |
| | `cnn_tabular_2d_v2.py:448` (confusion matrix dihitung pada **data latih** — rawan menyesatkan) |
| **Masalah** | Metrik yang tercatat di registri hanya dari set validasi internal. Tidak ada matriks kebingungan / recall / presisi pada data uji berlabel yang disimpan untuk ditinjau. `TEST_SEM3` tidak punya `Label`. |
| **Dampak** | Sulit menilai kualitas model dari luar tanpa menjalankan skrip terpisah. |
| **Perbaikan** | Simpan hasil split hold-out (mis. 20% dari TRAIN dengan stratifikasi) + confusion matrix ke `model_registry` atau tabel baru. Skrip `backend/verify_model_integration.py` sudah melakukan pengukuran ini secara manual. |

### 2.8 — INFO: Arsitektur model sudah benar

| | |
|---|---|
| **File / baris** | `backend/app.py:262-286` `build_cnn_model()` |
| **Status** | ✅ Identik dengan `model_f` di `cnn_tabular_2d_v2.py:370-374`: Conv2D 8 → 16 (kernel 3×3), Dense 64 → 32, dropout 0.3 / 0.3 / 0.2, output sigmoid. Total 11.969 parameter, sama persis. |
| **Catatan minor** | `app.py:280` `Dropout(dropout_rate - 0.1 ...)` menghasilkan `0.19999999998` karena aritmetika float — tidak berpengaruh, kosmetik saja. |

### 2.9 — TINGGI: Nilai huruf mutu tak dikenal diganti diam-diam ke nilai terbaik

| | |
|---|---|
| **File / baris** | `backend/app.py:735-740` (`train_model` — encoder di-fit hanya dari huruf mutu yang kebetulan muncul di data latih untuk kolom itu) |
| | `backend/app.py:983-999` (`predict` — deteksi & penggantian), khususnya **`:998`** `df[col] = as_str.map(lambda s: s if s in known else str(le.classes_[0]))` |
| | `backend/app.py:996` — nilai pengganti = `le.classes_[0]` (kelas pertama urut abjad) |
| | `backend/app.py:1152-1163` — perakitan pesan peringatan |
| | `frontend/src/pages/Results.jsx:195-207` — banner peringatan di UI |
| | `cnn_tabular_2d_v2.py:79-84` — asal-usul, sama persis (`le.classes_[0]`) |
| **Masalah** | Setiap huruf mutu di berkas yang tidak muncul di data latih untuk kolom itu diganti ke `classes_[0]`. Untuk **66 dari 141** kolom kategorikal model Informatika, `classes_[0]` = **`A`** (nilai terbaik). Contoh nyata (model Teknik Mesin): kolom `PPKMB002` di data latih hanya pernah lihat `['A', 'E']`, sehingga nilai `D` dan `F` di berkas → diubah jadi `A`. |
| **Dampak** | Model memprediksi SISIP dari *jumlah nilai buruk*. Mengganti nilai tak dikenal jadi `A` secara sistematis **mendorong hasil ke "TIDAK SISIP"** — mahasiswa berisiko bisa lolos deteksi. Prosesnya diam-diam; tanpa banner peringatan tidak ada indikasi apa pun. |
| **Di mana** | **Keduanya** (`app.py` menyalin dari `cnn_tabular_2d_v2.py`). |
| **Butuh keputusan pembimbing** | Pertanyaan C.12 (konservatif vs optimistis vs tolak berkas). |
| **Perbaikan** | (a) Untuk kolom nilai: pakai pemetaan ordinal (§2.10) sehingga nilai tak dikenal tetap dipetakan ke angka yang benar. (b) Untuk kolom kategori lain: kategori `__UNKNOWN__` eksplisit, atau — untuk EWS — petakan ke nilai **terburuk**. (c) Alternatif paling aman: tolak berkas + sebut sel yang tidak valid. Semua opsi butuh retrain. |

### 2.10 — SEDANG: Encoding huruf mutu tidak mencerminkan urutan baik-buruk

| | |
|---|---|
| **File / baris** | `backend/app.py:735-740` (`LabelEncoder().fit_transform` diterapkan ke SEMUA kolom kategorikal, termasuk semua kolom nilai) · `cnn_tabular_2d_v2.py:77-85` |
| **Masalah** | `LabelEncoder` mengurutkan nilai secara **abjad**, bukan berdasarkan makna akademik: `A=0, A-=1, B=2, B+=3, C=4, C+=5, D=6, E=7`. Akibatnya **`B+` (lebih baik dari B) dapat angka 3, lebih besar dari `B`=2** — modifier `+` membalik urutan. |
| **Dampak** | Representasi angka untuk sebagian nilai tidak monoton dengan baik-buruk. Efeknya kecil (hanya nilai ber-`+`), tapi menambah derau pada fitur yang paling menentukan. |
| **Di mana** | **Keduanya.** |
| **Butuh keputusan pembimbing** | Pertanyaan C.13 (skala baku huruf mutu). |
| **Perbaikan** | Ganti `LabelEncoder` untuk kolom nilai dengan pemetaan tetap `{'A':4.0, 'A-':3.7, 'B+':3.3, 'B':3.0, 'B-':2.7, 'C+':2.3, 'C':2.0, 'C-':1.7, 'D+':1.3, 'D':1.0, 'E':0.0, 'F':0.0, 'T':0.0}`. Butuh retrain. |

### 2.11 — TINGGI: Model per-prodi dilatih dari data yang tidak konsisten

| | |
|---|---|
| **File / baris** | `backend/app.py:709-710` (filter `Prodi` di `/api/train` — dilewati diam-diam bila kolom `Prodi` tidak ada di berkas) · `:702-703` (satu-satunya validasi: `len(df) == 0`) |
| **Masalah** | Tidak ada jaminan keempat model dilatih dari populasi & jumlah data yang sama. Bukti dari encoder tersimpan: kolom `PPKMB002` — model **Informatika** kenal `['A','B','C','D','E','F']`, model **Teknik Mesin** hanya `['A','E']`. Model Teknik Mesin jelas dilatih dari sampel yang jauh lebih sedikit / miskin variasi. |
| **Dampak** | Prediksi model Teknik Mesin (dan mungkin Matematika, Teknik Elektro) tidak bisa dipercaya untuk data nyata — mayoritas huruf mutu asli akan jatuh ke kasus "tidak dikenal" (§2.9). |
| **Di mana** | `app.py` + proses training oleh admin. |
| **Butuh keputusan pembimbing** | Pertanyaan A.6 (apakah data prodi lain memang ada). |
| **Perbaikan** | Latih ulang **semua prodi dari dataset yang sama dan lengkap**; tambah validasi minimal jumlah baris & keragaman kelas sebelum menyimpan model. |

---

## Urutan tindak lanjut yang disarankan

1. **Bawa Bagian 1 ke pembimbing** — terutama A.1–A.6, dan C.12–C.13. Jawaban A.2/A.3
   menentukan apakah 2.1 dikerjakan; jawaban A.6 & C.12/C.13 menentukan 2.9–2.11.
2. Jika pembimbing setuju IPK/SKS masuk fitur → kerjakan 2.1 + 2.4 + 2.10 + 2.11
   **sekaligus dalam satu retrain** (semua butuh latih ulang model).
3. 2.2 (buang fitur konstan) hanya jika pembimbing memastikan `E` seragam itu
   artefak, bukan data valid.
4. 2.3, 2.5, 2.7 bisa dikerjakan kapan saja (perbaikan teknis murni, tidak butuh
   keputusan domain).
5. 2.6 (pemetaan grid) dan pertanyaan C.9 (kenapa CNN) — diskusi metode dengan
   pembimbing, bukan perbaikan mendesak.

> Catatan: 2.9, 2.10, 2.11 semuanya menuntut **latih ulang model**. Paling efisien
> dikerjakan bersamaan dengan 2.1 (IPK/SKS) begitu pembimbing menjawab, supaya
> retrain cukup sekali.
