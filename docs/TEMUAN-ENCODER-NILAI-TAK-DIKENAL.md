# Temuan: Nilai Huruf yang Tidak Dikenal Encoder

**Tanggal:** 27 Oktober 2026
**Lanjutan dari:** [TEMUAN-E2E-DAN-MODEL.md](TEMUAN-E2E-DAN-MODEL.md), bagian *Faktor pendukung — nilai yang tidak dikenal dibaca sebagai kelas pertama*
**Model yang diperiksa:** `Model_2DCNN_teknik_mesin_20260908_104752` (model aktif Teknik Mesin, dilatih dari 107 mahasiswa angkatan 2021)
**Sumber data:** `Data_akademik_te_tm_mat.xlsx`, sheet `TM`

---

## Kesimpulan

1. Setiap mata kuliah punya `LabelEncoder` sendiri. Encoder itu **hanya mengenal nilai yang muncul di data latih** untuk mata kuliah tersebut, sehingga daftar nilai yang dikenal berbeda-beda per mata kuliah.
2. Saat prediksi, nilai yang tidak dikenal diganti dengan `classes_[0]`, yaitu kelas pertama menurut urutan abjad. Penggantinya tidak memperhatikan arti nilai aslinya. Nilai buruk bisa dibaca "tidak mengambil", dan mata kuliah yang tidak diambil bisa dibaca "A".
3. **Mekanisme ini berasal dari skrip acuan** `cnn_tabular_2d_v2.py:83`, dan backend menyalinnya dengan setia (`backend/sisip/predictor.py:114-119`). Backend tidak salah implementasi di bagian ini.
4. **Dampaknya membesar karena kondisi di luar skrip:** model aktif dilatih dari satu angkatan saja, kurikulum Teknik Mesin berubah antar angkatan, dan skala nilai plus/minus tidak ada di data latih 2021.
5. Ini **faktor pendukung**, bukan penyebab utama. Penyebab utama prediksi keliru tetap epochs/patience yang terlalu kecil dan data latih satu angkatan (lihat bagian [Status perbaikan](#status-perbaikan)).

---

## 1. Letak di kode

### Skrip acuan — `cnn_tabular_2d_v2.py:75-85`

```python
# Encode kolom kategorikal menggunakan LabelEncoder
encoders = {}
for col in X_train.columns:                                   # 77: satu kali per mata kuliah
    if X_train[col].dtype == "object":
        le = LabelEncoder()                                   # 79: encoder baru per kolom
        X_train[col] = le.fit_transform(X_train[col].astype(str))   # 80: hanya mengenal nilai di data latih

        # Pastikan kolom di test mengikuti mapping yang sama
        X_test[col] = X_test[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])  # 83
        X_test[col] = le.transform(X_test[col])               # 84
        encoders[col] = le
```

- **Baris 79–80:** `le.classes_` berisi nilai unik kolom itu di data latih, diurutkan menurut kode karakter.
- **Baris 83:** nilai di data uji yang tidak ada di `classes_` diganti dengan `classes_[0]` tanpa peringatan.

### Backend

| Tahap | Lokasi | Keterangan |
|---|---|---|
| Training | `backend/sisip/routes/training.py:93-96` | `LabelEncoder` per kolom, disimpan ke `_encoders.pkl` |
| Prediksi | `backend/sisip/predictor.py:114-119` | Logika `classes_[0]` sama dengan skrip baris 83 |

```python
    # Kategori yang tidak dikenal model diganti ke kelas pertama (le.classes_[0]).
    for col, le in am.encoders.items():
        if col in df.columns:
            known = set(str(x) for x in le.classes_)
            as_str = df[col].astype(str)
            df[col] = le.transform(as_str.map(lambda s: s if s in known else str(le.classes_[0])))
```

---

## 2. Kenapa nilai yang dikenal encoder berbeda-beda

Isi encoder model aktif (`saved_models/Model_2DCNN_teknik_mesin_20260908_104752_encoders.pkl`):

| Mata kuliah | Nilai yang dikenal encoder | Penjelasan |
|---|---|---|
| Fisika Dasar | A, B, C, D, E | Semua mahasiswa 2021 mengambilnya |
| Fisika 1 | -, A, B, E | Hanya 4 mahasiswa 2021 yang mengambil |
| Fisika 2 | **-** saja | Tidak ada mahasiswa 2021 berlabel yang mengambilnya sampai semester 3 |
| Fisika 3 | -, A, B, C, E | Kebetulan tidak ada yang mendapat D |
| Fisika 4 | **-** saja | Sama dengan Fisika 2 |
| Statistika | A, B, C, E | Semua mengambil, jadi tidak ada `-` |
| Pendidikan Agama | A, B, C, E | Semua mengambil, jadi tidak ada `-` |
| Mekanika Teknik 2 | -, A, B, C, D, E | |

Ringkasan seluruh encoder model aktif:

- 113 kolom memiliki encoder.
- **23 kolom hanya mengenal satu nilai.** Bagi model, kolom seperti ini tidak membawa informasi, dan nilai lain apa pun saat prediksi pasti tidak dikenal.
- **Tidak ada nilai plus/minus** (A-, B+, B-, dst.) di encoder kolom nilai. Yang ada hanya A–E dan `-`. Padahal data angkatan 2023 memuat nilai seperti B-. Belum diverifikasi apakah angkatan 2021 memang belum memakai skala plus/minus.
- Beberapa kolom punya 23–76 kelas. Kemungkinan besar ini kolom non-nilai dari data PMB, dan kolom seperti ini juga rawan berisi nilai tak dikenal.

Penyebab perbedaannya:

1. **Siapa yang mengambil.** Mata kuliah yang tidak diambil siapa pun di data latih hanya berisi `-`.
2. **Nilai yang kebetulan keluar.** Dari 107 mahasiswa, kadang tidak ada yang mendapat D di satu mata kuliah.
3. **Kurikulum angkatan.** Lihat bagian 4.

---

## 3. Kenapa hasil salah bacanya kadang `-`, kadang `A`

`LabelEncoder` mengurutkan kelas menurut kode karakter. Tanda `-` (kode 45) lebih kecil daripada `A` (kode 65), jadi:

- **Kalau encoder mengenal `-`**, `classes_[0] = '-'`. Nilai tak dikenal dibaca **"tidak mengambil"**.
- **Kalau encoder tidak mengenal `-`**, `classes_[0] = 'A'`. Nilai tak dikenal dibaca **"A"**.

Kasus mahasiswa Teknik Mesin angkatan 2023 (NIM `07818674325d3846cddaaa578e566544`, IPK 1.10, label asli SISIP) mengalami 18 salah baca. Contohnya:

| Mata kuliah | Nilai asli | Dikenal encoder | Ada `-`? | Dibaca model sebagai |
|---|---|---|---|---|
| Fisika 2 | **E** | `-` | ya | `-` (tidak mengambil) |
| Fisika 3 | **D** | `-`, A, B, C, E | ya | `-` |
| Mekanika Teknik 2 | B- | `-`, A, B, C, D, E | ya | `-` |
| Statistika | `-` | A, B, C, E | **tidak** | **A** |
| Pendidikan Agama | B- | A, B, C, E | **tidak** | **A** |

Simulasi dengan `LabelEncoder`:

```
Fisika 3    classes_=['-','A','B','C','E']  classes_[0]='-'  nilai 'D' -> '-'
Statistika  classes_=['A','B','C','E']      classes_[0]='A'  nilai '-' -> 'A'
```

Arah salah bacanya ditentukan oleh kebetulan isi data latih, bukan oleh arti nilainya. Di seluruh angkatan 2023, **2.420 dari 11.752 sel (21%)** diganti dengan cara ini.

---

## 4. Perubahan kurikulum Teknik Mesin

### Mata kuliah Fisika (jumlah mahasiswa yang mengambil)

| Mata kuliah | Kode | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|
| Fisika Dasar | STMA105 | 88 | 118 | 3 | 0 |
| Fisika 1 | STMB105 | 0 | **4** | 118 | 104 |
| Fisika 2 | STMB205 | 0 | 88 | 117 | 96 |
| Fisika 3 | STMB305 | 0 | 97 | 106 | 96 |
| Fisika 4 | STMB405 | 0 | 98 | 112 | 92 |

Angkatan 2021, satu-satunya data latih model aktif, masih memakai Fisika Dasar. Angkatan 2022 dan 2023 sudah memakai Fisika 1–4.

Fisika 2 dan 3 diambil sekitar 90 mahasiswa 2021, tetapi encodernya hanya mengenal `-`. Dugaan: mereka mengambilnya di luar batas semester 3 yang dipakai model. Dugaan ini belum diperiksa per semester.

Sebagai pembanding, mata kuliah bernama Fisika di prodi lain: Teknik Elektro punya Fisika (FISK111), Fisika Mekanika, Fisika Optik & Bahan, Fisika Modern, dan Termofisika. Matematika hanya punya mata kuliah pilihan semester 4 yang diambil satu mahasiswa. Setiap prodi punya model dan encoder sendiri, jadi data antarprodi tidak tercampur.

### Statistika (kode lama STMA209, kode baru STMB501)

| Angkatan | Total mahasiswa | Mengambil sampai semester 3 | Semester terbanyak |
|---|---|---|---|
| 2020 | 88 | 82 | 2 |
| **2021** | **118** | **110** | **2** (109 mhs) |
| 2022 | 121 | 46 | 2 dan 4 |
| **2023** | **104** | **19** | 3 |

Kenapa encoder Statistika tidak mengenal `-`:

1. Kurikulum 2021 menempatkan Statistika di semester 2.
2. Dari 118 mahasiswa 2021, ada 8 yang tidak mengambil Statistika sampai semester 3. **Kedelapannya tidak berlabel Sisip Program**, sehingga dibuang saat training. Ke-107 mahasiswa berlabel semuanya punya nilai Statistika (A, B, C, atau E).
3. Di angkatan 2023, hanya 19 dari 104 mahasiswa yang sudah mengambil Statistika sampai semester 3. Akibatnya sekitar 85 mahasiswa 2023 yang belum mengambilnya dibaca model seolah-olah mendapat **A**.

Label angkatan 2021: 81 Tidak Sisip, 11 Sisip (SKS Lulus < 50), 11 Sisip (IPK < 2.00), 4 Sisip (SKS Tidak Lulus > 10), 11 kosong.

### Pendidikan Agama (TEOL 101)

Diambil 100% mahasiswa di semester 1 pada semua angkatan, jadi encodernya tidak pernah mengenal `-`. Pada mahasiswa kasus, salah bacanya terjadi karena nilai **B-**, yang tidak ada di encoder, sehingga dibaca **A**.

---

## 5. Apakah ini kesalahan skrip acuan?

| Aspek | Asal | Keterangan |
|---|---|---|
| Nilai tak dikenal diganti `classes_[0]` tanpa peringatan | **Skrip acuan** (`:83`) | Kelemahan desain yang diwarisi backend |
| Nilai huruf di-encode sebagai kategori (`LabelEncoder`), bukan skala mutu | **Skrip acuan** (`:77-80`) | Daftar nilai yang dikenal bergantung pada isi data latih. B- tidak dianggap dekat dengan B. Urutannya abjad, bukan mutu |
| Data latih hanya angkatan 2021 | Cara model dilatih lewat aplikasi | Skrip membaca sheet `TRAIN_SEM3` utuh tanpa filter angkatan |
| Kurikulum berubah antar angkatan | Data | |
| Skala plus/minus tidak ada di data 2021 | Data (belum diverifikasi) | |

Belum bisa dipastikan apakah masalah yang sama muncul di eksperimen asli skrip di Colab, karena isi angkatan pada sheet `TRAIN_SEM3` dan `TEST_SEM3` tidak diketahui. Kalau isinya juga lintas kurikulum, kemungkinan besar masalahnya sama.

---

## Status perbaikan

Sudah dilakukan (27 Oktober 2026, belum di-commit). Pengaturan training disamakan dengan skrip acuan:

| | Sebelum | Sesudah | Lokasi |
|---|---|---|---|
| Default epochs | 10 | 100 | `backend/sisip/routes/training.py:53`, `frontend/src/pages/AdminModel.jsx:44` |
| Patience early stopping | 5 | 10 | `backend/sisip/routes/training.py:157` |
| Shuffle | `False` | default (`True`) | `model.fit` di `training.py` |

Penanganan nilai tak dikenal **tidak diubah**, karena logikanya sudah sama dengan skrip acuan.

## Rekomendasi

1. **Latih ulang model Teknik Mesin dengan angkatan 2020–2022**, atau kosongkan isian angkatan. Angkatan 2022 sudah memakai kurikulum Fisika 1–4, sehingga jumlah nilai tak dikenal akan turun banyak tanpa mengubah kode.
2. **Catat jumlah sel yang diganti `classes_[0]`** pada setiap prediksi, dan tampilkan peringatan bila proporsinya besar. Langkah ini tidak mengubah hasil prediksi, jadi tetap setia pada skrip acuan.
3. **Usulan ke pembimbing:** petakan nilai huruf ke skala mutu tetap (A=4, A-=3.7, B+=3.3, B=3.0, …, E=0) dan beri penanda khusus untuk "tidak mengambil", alih-alih `LabelEncoder`. Dengan cara ini tidak ada lagi nilai tak dikenal, dan urutan nilai mengikuti mutunya. Usulan ini menyimpang dari skrip acuan, jadi perlu persetujuan dan model harus dilatih ulang.
4. **Pertanyaan ke pembimbing:** angkatan mana saja yang ada di sheet `TRAIN_SEM3` dan `TEST_SEM3` pada eksperimen Colab? Apakah masalah ini juga terjadi di sana?
