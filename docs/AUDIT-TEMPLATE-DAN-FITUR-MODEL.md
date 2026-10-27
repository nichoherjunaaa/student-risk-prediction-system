# Audit Lanjutan — Template Prediksi & Kualitas Fitur Model

**Tanggal:** 3 September 2026
**Basis kode:** commit `b8fa0a2` (branch `main`)
**Lingkup:** menelusuri keluhan "hasil prediksi selalu TIDAK SISIP", memverifikasi apakah mesin prediksi benar-benar bekerja, dan memeriksa kualitas fitur yang dipakai model.
**Pendahulu:** [`AUDIT-PIPELINE-PREDIKSI.md`](AUDIT-PIPELINE-PREDIKSI.md) (2 Sep 2026, commit `f62ffe8`) — dokumen ini melanjutkan penomoran temuannya.

---

## Kesimpulan

**Mesin prediksinya sehat. Yang rusak adalah data contoh di template dan penanganan nilai yang tidak dikenal model.**

Keluhan "selalu TIDAK SISIP" berasal dari template yang berisi angka di luar rentang data latih, bukan dari cacat model atau pipeline. Setelah nilai contoh diturunkan dari statistik model itu sendiri, hasil prediksi kembali bervariasi.

| Indikator | Nilai | Status |
|---|---|---|
| Akurasi model di data latih | 97,0% (SISIP 88/100, TIDAK SISIP 498/504) | ✅ |
| Prediksi pada data uji asli (395 mhs) | 84 SISIP / 311 TIDAK SISIP | ✅ |
| Template lama → prediksi | 8/8 TIDAK SISIP (prob ≈ 1,0000) | ❌ → diperbaiki |
| Template baru → prediksi | 4 SISIP / 4 TIDAK SISIP | ✅ |
| Sel bernilai tak dikenal pada dataset asli | 2.144 sel di 40 kolom | ⚠️ dimitigasi |
| Fitur konstan (tidak informatif) | 56 dari 153 (37%) | ⚠️ perlu keputusan |
| IPK & SKS dipakai model | Tidak | ⚠️ perlu keputusan |

---

## Verifikasi: modelnya sendiri bekerja

Sebelum menyalahkan model, perilakunya diuji langsung terhadap data berlabel.

**Model aktif Informatika** (`Model_2DCNN_informatika_20260804_224358`, 153 fitur, grid 9×17, biner).

| Uji | Hasil |
|---|---|
| Akurasi pada 604 baris `TRAIN_SEM3` | **0,970** |
| Matriks kebingungan | SISIP 88 benar / 12 salah · TIDAK SISIP 498 benar / 6 salah |
| Prediksi pada 395 baris `TEST_SEM3` | 84 SISIP, 311 TIDAK SISIP (21,3%) |
| 4 mahasiswa berlabel SISIP asli | prob 0,1438–0,3230 → **SISIP** ✅ |
| 4 mahasiswa berlabel TIDAK SISIP asli | prob 0,8978–0,9638 → **TIDAK SISIP** ✅ |

> Model membedakan kedua kelas dengan benar. Rentang probabilitas pada data uji 0,0864–0,9988 — bukan model yang macet di satu keluaran.

---

## Temuan 4 — KRITIS (sudah diperbaiki, commit `367601a`)

### Template hasil unduhan tidak bisa dipakai untuk prediksi

**Lokasi:** `backend/app.py` — `/api/template/predict`, `/api/predict`

Template menyertakan kolom identitas `Nama`, `Prodi`, dan `Semester`, tetapi `/api/predict` hanya membuang `NIM, Nomor PMB, Angkatan, IPK 1–3, Total SKS 3`. Ketiga kolom sisanya ikut masuk ke `StandardScaler`.

```
ValueError: The feature names should match those that were passed during fit.
Feature names unseen at fit time:
- Nama
- Prodi
- Semester
        backend/app.py:839  X_scaled = active_scaler.transform(df)
```

Karena baris ini berada di luar `try/except`, Flask mengembalikan **HTML 500** yang tidak bisa dibaca frontend, sehingga pengguna hanya melihat pesan generik "Gagal mengeksekusi prediksi".

Dataset asli tetap jalan karena `DATA MAHASISWA 20-24.xlsx` memang tidak punya kolom `Nama`/`Prodi`/`Semester` — hanya template buatan sendiri yang rusak.

### Perbaikan yang diterapkan

Kolom disusun lewat `df.reindex(columns=active_scaler.feature_names_in_)`, sehingga semua kolom identitas terbuang dan urutannya persis seperti saat pelatihan. Kolom fitur yang hilang menghasilkan `400` dengan daftar kolomnya, dan seluruh blok encoding→scaling→inference dibungkus `try/except` yang mengembalikan JSON.

---

## Temuan 5 — KRITIS (sudah diperbaiki, commit `b8fa0a2`)

### Nilai contoh di template berada jauh di luar rentang data latih

**Lokasi:** `backend/app.py` — `_build_sample_rows`

Generator contoh mengisi kolom nilai dengan rentang karangan 35–90. Kenyataannya kolom nilai tes masuk berskala **0–10**.

| Kolom | Rentang asli (data latih) | Isi template lama | z-score |
|---|---|---|---|
| Nilai Penalaran Verbal | 0–10 (mean 2,70 · σ 3,68) | 45,38–86,60 | **+16,60** |
| Nilai Kemampuan Numerik | 0–10 (mean 2,40 · σ 3,29) | 36,59–86,99 | **+19,73** |
| Nilai Penalaran Mekanik | 0–10 (mean 1,08 · σ 2,34) | 45,46–87,17 | **+27,84** |
| Nilai Hubungan Ruang | 0–10 (mean 2,65 · σ 3,66) | 38,93–89,85 | **+17,23** |
| Nilai Bahasa Inggris | 0–10 (mean 2,43 · σ 3,39) | 44,83–89,72 | **+18,81** |
| Nilai Final Rata-Rata | 0–10 (mean 2,52 · σ 3,36) | 49,95–87,61 | **+19,03** |
| Matematika_1 (rapor) | 0–98 (mean 51,37 · σ 40,07) | 42,38–87,23 | +0,36 |

Rata-rata |z| kolom numerik template = **10,10**, padahal data normal berada di sekitar 1. Model menerima input yang belum pernah dilihatnya dan mengembalikan prob 1,0000 untuk seluruh baris.

Sebagai pembanding, yang sebenarnya membedakan kedua kelas adalah **jumlah nilai buruk**, bukan angka-angka ini:

| Label | Rata-rata nilai D/E/F | Rata-rata nilai A–C |
|---|---:|---:|
| SISIP | 128,84 dari 133 (min 113) | 4,16 |
| TIDAK SISIP | 112,63 (maks 128) | 20,38 |

### Perbaikan yang diterapkan

Nilai contoh kini diturunkan dari statistik model sendiri — `scaler.mean_` dan `scaler.scale_` — dan digeser `k·σ` per baris dengan gradasi `k = [-1,2 … +1,8]`. Pendekatan ini berlaku untuk model apa pun tanpa perlu menebak rentang tiap kolom.

Hasil verifikasi template baru, tanpa diubah sama sekali:

```
Ahmad Fauzi Ramadhan   -> TIDAK SISIP      Muhammad Rizky Pratama -> SISIP
Siti Nur Aisyah        -> TIDAK SISIP      Putri Ayu Wulandari    -> SISIP
Budi Santoso           -> TIDAK SISIP      Andi Setiawan          -> SISIP
Dewi Lestari           -> TIDAK SISIP      Rina Marlina           -> SISIP
```

---

## Temuan 6 — TINGGI (dimitigasi, commit `b8fa0a2`)

### Nilai yang tidak dikenal model diganti diam-diam ke nilai terbaik

**Lokasi:** `backend/app.py` — `/api/predict`, blok encoding

```python
df[col] = df[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
```

Nilai di luar daftar kelas diganti ke `le.classes_[0]`. Untuk kolom mata kuliah berkelas `A–F`, kelas pertama adalah **`A`** — nilai terbaik. Salah ketik huruf mutu tidak menimbulkan error apa pun, hanya menggeser hasil ke arah TIDAK SISIP.

Nilai yang diterima **berbeda-beda tiap kolom**:

| Jumlah kolom | Nilai yang dikenal |
|---:|---|
| 56 | `E` saja |
| 22 | `A, B, C, D, E, F` |
| 12 | `A, E` |
| 5 | `A, B, C, D, E` |
| 5 | `B, E` |
| 4 | `A, A-, B, B+, B-, C, C+, D, E, F` |
| 3 | `C, E` |

Petunjuk pada template versi sebelumnya justru menyesatkan — menyuruh mengisi `A, A-, B+, …, T` padahal mayoritas kolom tidak mengenal nilai tersebut.

**Ini juga terjadi pada data produksi asli**, bukan hanya template buatan:

```
2144 sel pada 40 kolom berisi nilai yang tidak dikenal model dan diganti otomatis.
Contoh: Propinsi Asal Lahir (Kalimantan Selatan, Papua Tengah, Sulawesi Barat -> Bali),
        Kabupaten Asal Lahir (Anambas, Asahan, BANJAR -> Alor),
        Propinsi Asal Sekolah (Maluku Utara, Papua Tengah -> Bali)
```

Penyebabnya kardinalitas tinggi: nama kabupaten dan sekolah di data uji banyak yang tidak muncul di data latih.

### Perbaikan yang diterapkan

Penggantian tetap dilakukan (agar prediksi tidak gagal total), tetapi kini dicatat dan dilaporkan: jumlah sel, kolom, contoh nilai, dan nilai penggantinya dikembalikan sebagai `warnings` di respons `/api/predict`, lalu ditampilkan sebagai banner di halaman Hasil Prediksi (`frontend/src/pages/Results.jsx`). Template juga mendapat sheet baru **`NILAI_VALID`** berisi daftar nilai sah per kolom.

### Belum selesai

Penggantian ke kelas pertama tetap pilihan yang buruk secara statistik. Opsi yang lebih benar: latih encoder dengan kategori `__UNKNOWN__` eksplisit, atau kurangi kardinalitas (mis. pakai provinsi saja, bukan kabupaten dan nama sekolah).

---

## Temuan 7 — SEDANG (sudah diperbaiki, commit `88cc645`)

### Filter angkatan/semester meleset karena tipe data berubah jadi desimal

**Lokasi:** `backend/app.py` — `/api/predict`, `/api/preview`

Perbandingan dilakukan sebagai string mentah:

```python
df = df[df['Angkatan'].astype(str) == str(angkatan)]
```

Bila **satu sel saja** pada kolom `Angkatan` kosong, pandas mengubah seluruh kolom menjadi `float64`, sehingga `2024` terbaca `"2024.0"` dan tidak pernah sama dengan `"2024"`. Seluruh baris terbuang, lalu muncul pesan generik "Tidak ada data uji (TEST) untuk kriteria yang dipilih".

```
rows 3  dtype float64
['2024.0', '2024.0', nan]   ['3.0', '3.0', nan]
cocok 2024: 0      cocok semester 3: 0
```

### Perbaikan yang diterapkan

Helper `_norm_str` / `_match_series` menormalkan nilai sebelum dibandingkan (`2024`, `2024.0`, `" 2024 "` dianggap sama), diterapkan di `/api/predict` dan `/api/preview`. Pesan "tidak ada data uji" juga diganti dengan diagnosa konkret yang menyebutkan nilai apa yang ada di berkas versus yang dipilih di dropdown.

---

## Temuan 8 — TINGGI (belum ditindaklanjuti, perlu keputusan)

### IPK dan Total SKS tidak dipakai model sama sekali

**Lokasi:** `backend/app.py:481` (`/api/train`), `backend/app.py:978` (`/api/predict`)

```python
drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
```

`IPK 1`, `IPK 2`, `IPK 3`, dan `Total SKS 3` dibuang dari fitur pada pelatihan maupun prediksi. Model memutuskan status sisip **tanpa pernah melihat IPK mahasiswa**.

Dokumen audit sebelumnya mencatat pembuangan ini pada tabel "Yang sudah benar" dengan alasan mencegah kebocoran label. Penilaian itu perlu ditinjau: `Label` memang wajib dibuang, tetapi IPK dan SKS lulus **bukan label** — keduanya indikator akademik sah yang justru paling relevan untuk memprediksi potensi sisip, dan tersedia pada saat prediksi dijalankan.

Konsekuensi praktis: pada halaman detail, IPK ditampilkan sebagai informasi pendukung, padahal tidak berkontribusi apa pun terhadap angka yang ditampilkan di sampingnya.

### Yang perlu diputuskan

Memasukkan IPK dan SKS ke fitur mengharuskan **seluruh model dilatih ulang** dan mengubah jumlah fitur dari 153. Perlu kepastian dulu bahwa nilai IPK pada berkas benar-benar mencerminkan kondisi *sebelum* status sisip ditetapkan — kalau IPK diambil setelah keputusan sisip, barulah itu kebocoran.

---

## Temuan 9 — SEDANG (belum ditindaklanjuti, perlu keputusan)

### 37% fitur bernilai konstan

**56 dari 133 kolom mata kuliah** hanya memiliki satu nilai di data latih, yaitu `E`. Setelah `LabelEncoder` semuanya menjadi 0, dan `StandardScaler` memberi mereka varians nol.

Artinya dari 153 fitur yang dipetakan ke grid 9×17 untuk CNN, **56 di antaranya tidak membawa informasi apa pun**. Grid citra semu yang jadi masukan CNN sebagian besar berisi konstanta.

### Yang perlu diputuskan

Membuang kolom berverians nol sebelum pelatihan akan mengubah `n_features` (153 → 97) dan geometri grid, sehingga seluruh model harus dilatih ulang. Sebelum itu perlu dipastikan apakah nilai `E` seragam tersebut memang benar (mata kuliah belum ditempuh) atau merupakan artefak penggabungan data.

---

## Status temuan dokumen sebelumnya

| Temuan (dok. sebelumnya) | Status per commit `b8fa0a2` |
|---|---|
| 1 — Filter prodi tidak pernah aktif | **Masih terbuka.** Dataset tetap tanpa kolom `Prodi`; keempat model masih dilatih pada 604 baris yang sama. Filter kini gagal terang-terangan bila kolomnya ada tapi nilainya beda, tetapi bila kolomnya memang tidak ada, blok masih dilewati diam-diam. |
| 2 — Semester tidak tersimpan, batch terhapus | **Masih terbuka.** Tabel `batches` belum punya kolom `semester`; kunci penghapusan masih `(prodi, angkatan)`. |
| 3 — Metrik epoch terakhir, bukan terbaik | **Masih terbuka.** |

---

## Metode verifikasi

Seluruh pengujian dijalankan lewat Flask test client terhadap basis data dan model aktif yang ada, tanpa perlu menyalakan server:

```bash
cd backend
venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
import app as A
c = A.app.test_client()
r = c.get('/api/template/predict?prodi=Informatika')
# lalu POST /api/predict dengan berkas hasil unduhan
PY
```

Skenario yang diverifikasi lolos:

| Skenario | Hasil |
|---|---|
| Unduh template tanpa memilih prodi | 200, 8 baris contoh, default Informatika/2023/Sem 3 |
| Template default langsung diprediksi | 200 — 4 SISIP, 4 TIDAK SISIP |
| Prodi dipilih tidak cocok dengan isi berkas | 400 + penjelasan nilai mana yang berbeda |
| Angkatan dipilih tidak cocok | 400 + penjelasan |
| Kolom fitur dihapus dari berkas | 400 + daftar kolom yang hilang |
| Nilai huruf mutu tak dikenal (`B+`, `Z9`) | 200 + peringatan "16 sel pada 2 kolom … `B+ -> A`" |
| IPK/SKS berisi teks rusak (`lupa diisi`, `-`) | 200, tidak lagi 500 |
| Sel angkatan kosong di satu baris | 200 (sebelumnya seluruh baris terbuang) |
| Regresi `DATA MAHASISWA 20-24.xlsx` | 200 — 395 baris, 84 SISIP |

**Berkas rujukan:**
- `DATA MAHASISWA 20-24.xlsx` — sheet `TRAIN_SEM3` (604 baris) dan `TEST_SEM3` (395 baris)
- `backend/saved_models/Model_2DCNN_informatika_20260804_224358.*`
- `backend/app.py`, `frontend/src/pages/Upload.jsx`, `frontend/src/pages/Results.jsx`

**Commit terkait:**

| Commit | Isi |
|---|---|
| `367601a` | Perbaikan kolom identitas menabrak scaler (Temuan 4) |
| `88cc645` | Template terisi contoh + normalisasi filter + pesan mismatch (Temuan 7) |
| `b8fa0a2` | Contoh in-distribution + sheet NILAI_VALID + peringatan nilai tak dikenal (Temuan 5, 6) |
