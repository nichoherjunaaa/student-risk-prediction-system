# Integrasi Model CNN ke Sistem SISIP

**Tanggal:** 5 September 2026
**Basis:** `main` @ `10c7cb4` + perubahan sesi ini (belum di-commit)
**Lingkup:** memetakan bagian mana dari `cnn_tabular_2d_v2.py` yang sudah masuk
ke sistem, dan memutuskan sisanya perlu diintegrasikan atau tidak.

Catatan kerja — belum ada satu pun rekomendasi di dokumen ini yang dikerjakan.

---

## Ringkasan

Notebook `cnn_tabular_2d_v2.py` **tidak dipanggil** oleh sistem. Isinya
diterjemahkan ulang ke `backend/app.py` dan dipecah menjadi dua endpoint:
`/api/train` dan `/api/predict`. Bagian inti pemodelan sudah terintegrasi utuh;
yang tertinggal adalah bagian **evaluasi** — dan justru di situ ada masalah yang
nyata, bukan sekadar kurang lengkap.

| Bagian notebook | Status |
|---|---|
| Preprocessing (encoder, scaler, grid 2D, padding) | ✅ terintegrasi |
| Arsitektur CNN (`model_f`) | ✅ terintegrasi |
| Class weight + EarlyStopping | ✅ terintegrasi |
| Persistensi model & prediksi ulang | ✅ terintegrasi (tambahan sistem) |
| Confusion matrix & metrik per kelas | ❌ belum — **perlu, mendesak** |
| Kurva akurasi/loss per epoch | ❌ belum — perlu, murah |
| Permutation importance | ❌ belum — **sebaiknya tidak** masuk aplikasi |
| Varian `model_a`–`model_e` | ❌ belum — **sebaiknya tidak** |

---

## Peta integrasi

### Tahap latih — `POST /api/train` (`backend/app.py:818`)

| Notebook | Sistem |
|---|---|
| `pd.read_excel(sheet_name='TRAIN_SEM3')` | baca sheet dari berkas yang diunggah Admin |
| `drop(['NIM','Nomor PMB','Angkatan','IPK 1..3','Total SKS 3'])` | `non_feature_columns()` (`app.py:411`) — jadi aturan regex, bukan daftar tetap |
| `LabelEncoder()` tiap kolom object | `app.py:868` → `global_encoders` |
| `le_y = LabelEncoder()` untuk target | `app.py:874` |
| `StandardScaler()` | `app.py:878` |
| `find_grid_dimensions(n)` | `app.py:256` — **plus perbaikan**, lihat catatan di bawah |
| `np.pad` + `reshape(-1, h, w, 1)` | `app.py:892-900` |
| `cnn_model(...)` varian `model_f` (filter 8→16, dense 64→32, dropout 0.3) | `build_cnn_model()` (`app.py:274`), arsitektur sama; dropout jadi parameter |
| `compute_class_weight("balanced")` | `app.py:924` |
| `EarlyStopping(val_loss, restore_best_weights)` | `app.py:930` — patience 5 (notebook 10) |
| `model.fit(...)` | `app.py:931` |

**Perbaikan atas notebook:** `find_grid_dimensions` versi notebook hanya mencari
faktorisasi pas. Kalau jumlah fitur bilangan prima (mis. 157), satu-satunya
faktor adalah 1 × 157 sehingga tinggi grid = 1, lalu MaxPooling kedua
menghasilkan dimensi 0 dan pelatihan gagal. Sistem menambahkan
`MIN_GRID_SIDE = 4` (`app.py:253`) dan padding nol.

**Perbedaan lain yang disengaja:** notebook memakai `validation_split=0.2` di
dalam `fit`; sistem memakai `train_test_split(..., stratify=y)` supaya proporsi
kelas di data validasi terjaga.

### Tahap simpan — tidak ada di notebook

`model.save()` + empat berkas pendamping via joblib (`app.py:954-958`):
`_scaler.pkl`, `_encoders.pkl`, `_ley.pkl`, `_config.pkl` (height, width,
pad_size, n_classes, n_features). Semuanya ke `saved_models/`, lalu satu baris
di tabel `model_registry`.

Ini inti integrasinya: notebook hidup dalam satu sesi memori, sistem harus bisa
memuat model yang sama berhari-hari kemudian.

### Tahap aktivasi — tidak ada di notebook

`POST /api/models/<id>/activate` menentukan satu model aktif **per program
studi**. Prediksi selalu memakai model aktif prodi yang bersangkutan.

### Tahap prediksi — `POST /api/predict` (`app.py:999`)

| Notebook | Sistem |
|---|---|
| pakai objek dari memori | muat ulang `.keras` + 4 `.pkl` model aktif prodi (`app.py:1038`) |
| `map(lambda s: s if s in le.classes_ else le.classes_[0])` | logika identik (`app.py:1110`) |
| `scaler.transform` → pad → reshape | `app.py:1131-1137` |
| `argmax` / `> 0.5` → `le_y.inverse_transform` | `app.py:1148` |
| `print(test_results)` | disimpan ke tabel `batches` + `predictions`, tampil di UI |

### Tambahan sistem: `backend/preprocessing.py`

Notebook langsung membaca sheet `TRAIN_SEM3` yang **sudah jadi** — dirakit
manual di Excel. Menu Preprocessing Data menggantikan pekerjaan manual itu:
menggabungkan berkas PMB + akademik mentah menjadi sheet berformat sama.

---

## Rekomendasi

### 1. Confusion matrix + precision / recall / F1 — **perlu, dulukan**

Bukan soal kelengkapan, tapi karena **angka yang ditampilkan sekarang
menyesatkan pengambilan keputusan**. Bukti dari data yang ada:

```
Model aktif Teknik Elektro                    → akurasi 81.8%
Baseline "tebak TIDAK SISIP untuk semua orang" → 222/248 = 89.5%
```

Model Teknik Elektro **lebih buruk daripada menebak asal**, tetapi di halaman
Master Model tampil sebagai angka hijau 81.8% tanpa apa pun yang membantahnya.
Admin yang memilih model berdasarkan kolom itu bisa mengunci model yang tidak
pernah menandai satu pun mahasiswa berisiko — padahal itu tujuan sistemnya.
Terbukti juga di template: model TE memprediksi **8 dari 8** baris contoh
sebagai TIDAK SISIP, termasuk baris dengan profil terlemah.

Metrik yang dibutuhkan adalah **recall kelas SISIP**. Untuk kasus ini, salah
menandai mahasiswa aman itu murah (dosen tinggal mengecek); melewatkan mahasiswa
yang benar-benar berisiko itu mahal. Akurasi tidak membedakan keduanya.

Penyebabnya ketimpangan kelas — laporan preprocessing Teknik Elektro:
SISIP 26 vs TIDAK SISIP 222 (10,5% kasus positif).

**Biaya:** kecil. `confusion_matrix` sudah dipakai di notebook, data validasi
sudah ada di memori saat training selesai.

**Rencana:** hitung di `/api/train` setelah `model.fit`, simpan TN/FP/FN/TP +
precision/recall/F1 sebagai kolom JSON `metrics` di `model_registry`, tampilkan
di tabel Registri Model dan modal keberhasilan.

### 2. Kurva akurasi & loss per epoch — **perlu, murah**

Objek `history` sudah ada di memori (`app.py:931`), sekarang dibuang setelah
diambil satu angka. Simpan sebagai JSON di `model_registry`, gambar grafik kecil
di UI. Gunanya: kelihatan kalau model overfitting atau berhenti terlalu cepat —
sekarang Admin tidak punya cara apa pun untuk tahu itu.

Bisa dikerjakan sekali jalan dengan poin 1 karena sama-sama dari hasil
`model.fit`.

### 3. Permutation importance — **sebaiknya tidak masuk aplikasi**

- Cara kerjanya mengacak satu kolom lalu memprediksi ulang seluruh data, diulang
  per fitur. Untuk model TE: 160 fitur × 248 baris = **161 kali `model.predict`**
  dalam satu HTTP request — Admin menunggu puluhan detik sampai menit dengan
  layar menggantung.
- Versi notebook memakai `roc_auc_score(...ravel())` yang hanya jalan untuk
  klasifikasi biner; perlu ditulis ulang kalau kelas bertambah.
- Manfaat untuk pengguna aplikasi (Admin/DPA) tipis. Ini bahan analisis untuk
  **naskah skripsi**, bukan sesuatu yang ditindaklanjuti dosen wali saat membuka
  dashboard.

**Saran:** jalankan sekali secara offline lewat skrip terpisah, hasilnya masuk
dokumen. Kalau nanti tetap ingin di aplikasi, syaratnya harus jadi tugas latar
belakang — dihitung setelah training selesai lalu disimpan, bukan ditunggu di
dalam request.

### 4. Varian `model_a`–`model_e` — **sebaiknya tidak**

Notebook mencoba enam arsitektur lalu memilih `model_f`; tahap eksperimen itu
sudah selesai. Menaruh keenamnya di UI mengubah alat operasional jadi meja lab
dan menambah cara baru untuk salah pilih.

### 5. *(Bukan dari notebook)* Catat hyperparameter per model — **perlu**

Hyperparameter yang dipakai tiap model **tidak dicatat**. Panelnya sudah ada
tapi disembunyikan (`SHOW_HYPERPARAMS = false` di `AdminModel.jsx`), dengan
komentar bahwa nilainya dikirim ke `/api/train` tetapi tidak disimpan ke
`model_registry` sehingga setelan tiap model tidak bisa ditelusuri.

Ini menyangkut **reproducibility** dan kemungkinan besar ditanyakan pembimbing
("model ini dilatih dengan parameter apa?"). Menyimpan epochs / batch size /
learning rate / dropout / val split per baris registri jauh lebih berharga
daripada menambah varian arsitektur.

---

## Rangkuman keputusan

| Item | Rekomendasi | Alasan utama |
|---|---|---|
| Confusion matrix + recall/precision/F1 | **Ya, dulukan** | Akurasi sekarang menyesatkan; model TE kalah dari baseline |
| Kurva akurasi/loss per epoch | **Ya** | Data sudah ada, tinggal disimpan |
| Permutation importance | **Tidak** di aplikasi | 161× predict per permintaan; nilainya untuk naskah |
| Varian `model_a`–`model_e` | **Tidak** | Tahap eksperimen sudah selesai |
| Catat hyperparameter per model | **Ya** | Reproducibility; panelnya sudah ada tapi mati |

**Usul pelaksanaan:** satu perubahan sekaligus — tambah kolom `metrics` (JSON)
dan `hyperparams` (JSON) di `model_registry`, isi saat training, tampilkan di
Master Model.

---

## Catatan terkait: ketimpangan kelas Teknik Elektro

Terpisah dari integrasi notebook, tapi ditemukan saat menelusurinya. Data latih
Teknik Elektro hanya 10,5% kasus SISIP, dan model hasilnya nyaris tidak pernah
memprediksi SISIP. Opsi penanganan yang belum dibahas:

- menaikkan bobot kelas SISIP melebihi `"balanced"`;
- menurunkan ambang keputusan dari 0,5;
- menggabungkan lebih banyak angkatan agar contoh SISIP bertambah.

Perlu diputuskan bersama pembimbing — lihat
[`PERTANYAAN-PEMBIMBING.md`](PERTANYAAN-PEMBIMBING.md).
