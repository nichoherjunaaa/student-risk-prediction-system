# Audit Pipeline Prediksi SISIP

**Tanggal:** 2 September 2026
**Basis kode:** commit `f62ffe8` (branch `main`)
**Lingkup:** verifikasi apakah hasil prediksi sudah sesuai tujuan proyek — *Early Warning System* mahasiswa berpotensi sisip.

---

## Kesimpulan

**Hasil prediksi belum sesuai tujuan proyek.**

Sistem berjalan tanpa error dan menghasilkan angka, tetapi angka tersebut **tidak dapat diatribusikan ke program studi manapun**. Perbedaan jumlah mahasiswa berisiko antar prodi murni berasal dari inisialisasi acak bobot model, bukan dari perbedaan data.

Pipeline machine-learning-nya sendiri sehat — penyelarasan fitur, penanganan kelas tidak seimbang, dan persistensi encoder/scaler semuanya benar. Masalahnya ada di **lapisan penyaringan data sebelum model dipanggil**.

| Indikator | Nilai | Status |
|---|---|---|
| Irisan NIM antar prodi | 395 / 395 identik | ❌ |
| Baris data latih per model | 604 untuk keempat prodi | ❌ |
| Penyelarasan fitur latih ↔ uji | 153 = 153, urutan cocok | ✅ |
| Total temuan | 3 (1 kritis, 1 tinggi, 1 sedang) | — |

---

## Temuan 1 — KRITIS

### Filter program studi tidak pernah aktif

**Lokasi:** `backend/app.py` — `/api/predict`, `/api/train`, `/api/preview`

Penyaringan prodi dibungkus penjagaan `if 'Prodi' in df.columns`. Ketika kolom itu tidak ada, blok dilewati tanpa peringatan dan seluruh isi sheet diteruskan ke model.

```python
# app.py — dijalankan pada predict, train, dan preview
if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
    df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
#      ^ bernilai False → penyaringan dilewati diam-diam, df tetap utuh
```

Pemeriksaan **seluruh 16 sheet** pada `DATA MAHASISWA 20-24.xlsx`: tidak ada satu pun kolom bernama *Prodi*, *Program Studi*, atau *Fakultas*. Sheet `TRAIN_SEM3` (604 baris) dan `TEST_SEM3` (395 baris) hanya memiliki `NIM`, `Nomor PMB`, data asal sekolah, nilai mata kuliah, `Angkatan`, `IPK 1–3`, dan `Total SKS 3`.

#### Bukti — 4 model dilatih, 4 prediksi dijalankan

| Prodi dipilih | Total baris | Berisiko | Aman | Daftar NIM vs Informatika |
|---|---:|---:|---:|---|
| Informatika | 395 | 106 | 289 | — acuan — |
| Teknik Elektro | 395 | 251 | 144 | identik (395/395) |
| Teknik Mesin | 395 | 222 | 173 | identik (395/395) |
| Matematika | 395 | 249 | 146 | identik (395/395) |

Karena `/api/train` memakai penjagaan yang sama, dampaknya merambat ke pelatihan: keempat model "khusus prodi" sesungguhnya dilatih pada 604 baris yang sama. Terverifikasi lewat `scaler.n_samples_seen_` pada tiap berkas `*_scaler.pkl` yang tersimpan.

#### Bukti — isi berkas scaler yang tersimpan

| Berkas model | `n_samples_seen_` | `n_features_in_` |
|---|---:|---:|
| `Model_2DCNN_informatika_…_scaler.pkl` | 604 | 153 |
| `Model_2DCNN_matematika_…_scaler.pkl` | 604 | 153 |
| `Model_2DCNN_teknik_elektro_…_scaler.pkl` | 604 | 153 |
| `Model_2DCNN_teknik_mesin_…_scaler.pkl` | 604 | 153 |

> **Penting untuk penulisan laporan/skripsi:** selisih 106 vs 251 mahasiswa berisiko **bukan temuan tentang prodi**. Empat model itu melihat data yang sama persis; yang berbeda hanya bobot awal acak. Angka tersebut **tidak boleh** ditafsirkan sebagai "Teknik Elektro lebih berisiko daripada Informatika".

### Perbaikan

Struktur dataset sebenarnya **satu berkas = satu prodi**:
- `DATA MAHASISWA 20-24.xlsx` berisi kode mata kuliah Informatika (`INFO*`, `ALGO*`, `RPLN*`)
- `hasil_merge_final_tm.xlsx` punya kolom `Prodi` berisi satu nilai saja: "Teknik Mesin"

Pilih salah satu arah:

1. **Tambahkan kolom `Prodi`** ke sheet `TRAIN_SEM3`/`TEST_SEM3`, lalu biarkan filter bekerja seperti yang sudah ditulis.
2. **Atau hapus dropdown prodi dari alur prediksi** dan perlakukan berkas yang diunggah sebagai satu prodi — prodi ditetapkan saat admin melatih model, dan dipakai hanya sebagai label batch.

Apa pun pilihannya, ubah penjagaan diam-diam menjadi **gagal terang-terangan**: bila pengguna memilih prodi tetapi kolomnya tidak ada, kembalikan `400` dengan pesan jelas, jangan diam-diam memproses seluruh baris.

---

## Temuan 2 — TINGGI

### Semester tidak tersimpan, dan batch lama terhapus diam-diam

**Lokasi:** `backend/app.py` — `/api/predict`, tabel `batches`

Dropdown semester dikirim ke backend, tetapi berakhir di penjagaan yang sama dengan prodi — kolom `Semester` juga tidak ada di sheet. Lebih jauh, semester **tidak pernah disimpan ke basis data sama sekali**.

```python
# kunci penghapusan batch lama — semester tidak ikut
c.execute('SELECT id FROM batches WHERE prodi = ? AND angkatan = ?',
          (prodi, angkatan))
if existing:
    c.execute('DELETE FROM predictions WHERE batch_id = ?', (old_batch_id,))
    c.execute('DELETE FROM batches WHERE id = ?', (old_batch_id,))
```

#### Bukti — prediksi semester 5 menghapus batch semester 3

| Langkah | Parameter | `batch_id` | Status akhir |
|---|---|---:|---|
| 1. Prediksi | Informatika · 2023 · sem 3 | 10 | terhapus |
| 2. Prediksi | Informatika · 2023 · sem 5 | 11 | tersisa |

Skema tabel `batches` berisi `id, batch_name, date_uploaded, total_records, at_risk, safe, status, prodi, angkatan, uploaded_by` — **tidak ada `semester`**. Karena `uploaded_by` juga tidak masuk kunci, batch milik seorang DPA dapat terhapus oleh DPA lain yang memprediksi prodi dan angkatan yang sama.

### Perbaikan

- Tambahkan kolom `semester` pada tabel `batches` dan simpan nilainya.
- Perluas kunci penghapusan menjadi `(prodi, angkatan, semester, uploaded_by)`.
- Pertimbangkan mengganti hapus-otomatis dengan menyimpan riwayat dan menandai batch terbaru — Log Riwayat jadi kehilangan gunanya kalau data lama dihapus.

---

## Temuan 3 — SEDANG

### Metrik yang dilaporkan bukan metrik model yang disimpan

**Lokasi:** `backend/app.py` — `/api/train`

Pelatihan memakai `EarlyStopping(restore_best_weights=True)`, sehingga bobot yang disimpan berasal dari epoch dengan `val_loss` terbaik. Namun akurasi yang dicatat ke `model_registry` diambil dari epoch **terakhir**.

```python
early_stopping = keras.callbacks.EarlyStopping(
    monitor="val_loss", patience=5, restore_best_weights=True)
...
accuracy_score = float(history.history['val_accuracy'][-1])
# [-1] = epoch terakhir, bukan epoch terbaik yang bobotnya dipakai
```

Terkait ini, **tidak ada ambang mutu** sebelum model boleh diaktifkan. Distribusi label latih adalah 504 *TIDAK SISIP* berbanding 100 *SISIP*, jadi menebak kelas mayoritas saja sudah memberi akurasi **83,4%**. Pada uji coba, satu model selesai dengan `val_accuracy` 0,570 — jauh di bawah garis dasar itu — dan tetap dapat dikunci sebagai model aktif lalu dipakai memprediksi.

### Perbaikan

- Ambil metrik dari epoch terbaik: `min(history.history['val_loss'])` dan `val_accuracy` pada indeks yang sama.
- Simpan juga **recall kelas SISIP** — untuk sistem peringatan dini, melewatkan mahasiswa berisiko jauh lebih mahal daripada salah menandai.
- Tolak aktivasi model yang akurasinya di bawah garis dasar kelas mayoritas, atau setidaknya tampilkan peringatan di halaman Master Model.

---

## Yang sudah benar

Terverifikasi, tidak perlu diubah:

| Aspek | Bukti |
|---|---|
| **Filter angkatan** | Kolom `Angkatan` ada, filter bekerja: 395 baris → 224 (2023) → 171 (2024) |
| **Penyelarasan fitur** | Latih dan uji sama-sama menghasilkan 153 fitur dengan urutan kolom identik setelah `drop_cols` |
| **Tidak ada kebocoran label** | Kolom `Label` dibuang dari `X` sebelum pelatihan; identitas (NIM, Nomor PMB, IPK, SKS) juga dikeluarkan dari fitur |
| **Kelas tidak seimbang** | `compute_class_weight("balanced")` diterapkan pada 100 SISIP vs 504 TIDAK SISIP |
| **Persistensi artefak** | Scaler, encoder, label-encoder, dan config disimpan bersama tiap model dan dimuat ulang saat prediksi |
| **Klasifikasi berisiko** | Pencocokan `label == 'SISIP'` bersifat persis, sehingga "TIDAK SISIP" tidak salah terhitung sebagai berisiko |

---

## Urutan pengerjaan

| # | Tugas | Estimasi | Alasan |
|---|---|---|---|
| 1 | **Putuskan sumber kebenaran program studi** | ± 1 jam | Tambahkan kolom `Prodi` ke Excel, atau hapus dropdown prodi dari alur prediksi. Memblokir semua interpretasi hasil, jadi kerjakan lebih dulu. |
| 2 | **Ubah filter yang gagal diam menjadi error eksplisit** | ± 30 menit | Kembalikan `400` saat pengguna meminta filter yang kolomnya tidak ada. Ini yang membuat bug pertama tidak terdeteksi selama ini. |
| 3 | **Simpan semester dan perbaiki kunci batch** | ± 1 jam | Tambah kolom `semester`, perluas kunci ke `(prodi, angkatan, semester, uploaded_by)`, hentikan penghapusan lintas-pengguna. |
| 4 | **Latih ulang seluruh model** | ± 30 menit | Model yang ada sekarang dilatih pada data yang tidak tersaring. Semuanya harus dilatih ulang setelah langkah 1 selesai. |
| 5 | **Laporkan metrik epoch terbaik + recall SISIP** | ± 45 menit | Selaraskan angka yang ditampilkan dengan bobot yang benar-benar disimpan, dan tambahkan metrik yang relevan untuk sistem peringatan dini. |

---

## Metode verifikasi

Keempat model dilatih ulang lewat `POST /api/train` pada basis data bersih, diaktifkan lewat `POST /api/models/{id}/activate`, lalu `POST /api/predict` dijalankan untuk tiap prodi dengan berkas Excel yang sama. Daftar NIM dibandingkan sebagai himpunan dan sebagai urutan.

**Berkas rujukan:**
- `DATA MAHASISWA 20-24.xlsx` (16 sheet)
- `hasil_merge_final_tm.xlsx`
- `backend/app.py`
- `frontend/src/pages/Upload.jsx`
