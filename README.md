# SISIP Program - Early Warning System & Prediksi Mahasiswa Berpotensi Sisip

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-green?style=for-the-badge&logo=flask)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-orange?style=for-the-badge&logo=tensorflow)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)
![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-v4-38BDF8?style=for-the-badge&logo=tailwindcss)

**SISIP Program** adalah aplikasi berbasis Web dan Artificial Intelligence (Deep Learning) yang dirancang sebagai *Early Warning System* untuk memprediksi mahasiswa yang berpotensi membutuhkan program sisip.

---

## Fitur Utama

- **Interactive Analytics Dashboard**: Visualisasi ringkasan statistik mahasiswa berpotensi sisip vs aman secara *real-time* dengan grafik Chart.js.
- **Filter Spesifik**: Filter data berdasarkan Program Studi (Prodi), Angkatan, dan Semester.
- **2D CNN Tabular Engine**: Menggunakan arsitektur Convolutional Neural Network 2D yang diadaptasi khusus untuk pengenalan pola data tabular akademis.
- **Batch Prediction via Excel**: Unggah berkas Excel rekap nilai mahasiswa untuk prediksi massal otomatis beserta unduh template format Excel.
- **Detail Mahasiswa & Transkrip Akademik**: Modal/halaman khusus rincian mahasiswa (NIM, Nama, Prodi, IPK per semester, dan riwayat nilai mata kuliah).
- **Cetak Laporan PDF**: Fitur ekspor laporan hasil prediksi dan detail mahasiswa ke format PDF (`jsPDF` & `jspdf-autotable`).
- **Multi-Role User Control**:
  - **End-User / DPA / Kaprodi**: Akses instan prediksi batch, filter bimbingan DPA/Prodi, dan pemantauan mahasiswa berisiko.
  - **Admin System**: Kebebasan eksperimen training model, pengaturan hyperparameter, manajemen riwayat batch, dan pengelolaan akun (termasuk menambah admin lain).
  - **BAPSI**: Mengunggah dan mengelola berkas data mahasiswa terbaru (PMB & akademik) di halaman **Berkas Mahasiswa** bergaya Google Drive (folder bertingkat). Berkas ini bisa diunduh semua peran dan langsung dipilih di halaman Preprocessing Data.

---

## Arsitektur & Teknologi

### Backend Stack
- **Bahasa & Framework**: Python 3.10+, Flask, Gunicorn
- **Machine Learning / Deep Learning**: TensorFlow / Keras (2D CNN Tabular Model), Scikit-Learn, Pandas, NumPy
- **Database**: SQLite (`sisip_database.db`)
- **Excel Processor**: OpenPyXL

### Frontend Stack
- **Framework & Build Tool**: React 18, Vite
- **Styling**: Tailwind CSS v4, Lucide React Icons
- **Visualisasi & Ekspor**: Chart.js, jsPDF, jsPDF-AutoTable
- **Routing & HTTP Client**: React Router v7, Axios

---

## Struktur Direktori Proyek

```text
sisip-program/
├── backend/                 # Backend API (Flask, TensorFlow, SQLite)
│   ├── app.py               # Titik masuk server (gunicorn app:app), hanya create_app()
│   ├── sisip/               # Seluruh kode backend
│   │   ├── config.py        # Pengaturan dari environment & daftar peran
│   │   ├── constants.py     # Skema kolom internal (kontrak dengan model terlatih)
│   │   ├── data_format.py   # Format berkas mentah yang bisa diatur admin (menu Format Data)
│   │   ├── db.py            # Koneksi SQLite, skema, migrasi
│   │   ├── auth.py          # Token login & dekorator hak akses
│   │   ├── ml.py            # Arsitektur 2D CNN & registri berkas model
│   │   ├── preprocessing.py # Penggabungan berkas PMB + akademik jadi data latih
│   │   └── routes/          # Endpoint API, satu Flask Blueprint per fitur
│   ├── e2e_test.py          # Uji end-to-end seluruh API
│   ├── requirements.txt     # Library Python & Dependensi Machine Learning
│   └── sisip_database.db    # Database SQLite (diabaikan dari Git)
├── frontend/                # Frontend Web Application (React + Vite)
│   ├── src/                 # Komponen UI React, Halaman, & Service API
│   ├── package.json         # Dependensi Node.js
│   ├── vite.config.js       # Konfigurasi Vite & Proxy Backend
│   └── index.html           # Root HTML Template
├── html-files/              # Mockup HTML Static (Referensi UI)
├── cnn_tabular_2d_v2.py     # Script eksperimen training model 2D CNN Tabular
├── .gitignore               # Aturan pengabaian file Git
└── README.md                # Dokumentasi proyek
```

---

## Panduan Instalasi & Penggunaan Lokal

### Prasyarat Sistem
- Python 3.10 atau versi lebih baru
- Node.js 18 LTS atau versi lebih baru & npm

---

### 1. Setup Backend (Flask API)

1. Masuk ke direktori backend:
   ```bash
   cd backend
   ```

2. Buat dan aktifkan *Virtual Environment*:
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

3. Install seluruh dependensi Python:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Jalankan Server Backend Flask:
   ```bash
   python app.py
   ```
   *Backend REST API akan berjalan pada `http://localhost:5000`.*

---

### 2. Setup Frontend (React + Vite)

1. Masuk ke direktori frontend:
   ```bash
   cd frontend
   ```

2. Install paket Node.js:
   ```bash
   npm install
   ```

3. Jalankan server pengembangan (Development Server):
   ```bash
   npm run dev
   ```
   *Frontend React akan berjalan pada `http://localhost:5173`.*

---

### 3. Panduan Penggunaan Aplikasi (Quick Start)

Setelah Backend dan Frontend berhasil dijalankan, ikuti langkah-langkah berikut untuk menggunakan sistem:

1. **Buka Aplikasi di Browser**:
   Akses `http://localhost:5173` melalui *browser* Anda.

2. **Login sebagai Super Admin**:
   Gunakan kredensial bawaan (*default*) untuk masuk sebagai administrator:
   - **NIP**: `235314122`
   - **Password**: nilai `SISIP_ADMIN_PASSWORD` di `.env` (lihat `.env.example`). Tanpa `.env`, password bawaannya `change-me-strong-password`; segera ganti.

   Semua akun login memakai **NIP**. Akun demo per peran (jika `SISIP_SEED_DEMO_USERS=1`):
   `900000000000000001` admin (`Admin#2026`), `...002` DPA (`Dpa#2026`),
   `...003` Kaprodi (`Kaprodi#2026`), `...004` BAPSI (`Bapsi#2026`).

3. **Melatih Model AI (Wajib Pertama Kali)**:
   - Sebelum bisa melakukan prediksi, Admin wajib melatih model AI terlebih dahulu.
   - Buka menu **Master Model** di panel samping sebelah kiri.
   - Masukkan *Target Program Studi* dan *Tahun Angkatan Latih*.
   - Sesuaikan parameter (*Max Epochs*, *Batch Size*, *Learning Rate*, dll) jika diperlukan.
   - Unggah dataset riwayat mahasiswa (berformat Excel) dan klik **Train Model Baru**.
   - Tunggu hingga proses selesai dan status sistem menampilkan bahwa model berhasil dibangun dan dikunci (*Active*).

4. **Menambahkan Akun Pengguna / DPA**:
   - Buka menu **Master Pengguna**.
   - Tambahkan akun Dosen Pembimbing Akademik (DPA) baru beserta kata sandi mereka. 
   - Anda juga dapat mengatur hak akses (Role) masing-masing jenis pengguna lewat tab **Manajemen Role** di bagian Header atas.

5. **Melakukan Prediksi Mahasiswa**:
   - *Logout* dari akun Admin, lalu *Login* menggunakan akun DPA/Dosen yang baru saja dibuat.
   - Buka menu **Unggah Data**.
   - Pilih Program Studi, Angkatan, dan Semester yang sesuai.
   - Unggah data Excel mahasiswa semester berjalan (pastikan *header* tabel sesuai dengan format yang dilatih) lalu klik **Jalankan Prediksi Sistem**.
   - Anda dapat meninjau hasil secara rinci pada menu **Hasil Prediksi** atau melihat ringkasan historis pada menu **Log Riwayat** (hanya tersedia untuk Admin).

---

## Kebijakan Keamanan & Kerahasiaan Data

Demi menjaga keamanan dan kerahasiaan data pribadi mahasiswa (*Data Privacy & Protection*):
- File **Excel** (`.xlsx`, `.xls`, `.csv`) yang berisi rekapitulasi data mahasiswa **TIDAK dimasukkan** ke dalam repositori GitHub.
- Database **SQLite** (`*.db`) dan berkas biner checkpoint model (`*.h5`, `.keras`, `.pkl`) diabaikan secara otomatis menggunakan file [`.gitignore`](.gitignore).

---

## Lisensi

Proyek ini dikembangkan untuk kebutuhan internal akademik dan evaluasi hasil belajar mahasiswa. 100% menggunakan teknologi berbasis *Open Source*.
