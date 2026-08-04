# Todo List Features & Requirements: DPA & Admin System

## 1. Scope Role DPA (Dosen Pembimbing Akademik)

### Menu Upload
- [ ] **Dropdown Semester**
  - Tambahkan pilihan semester pada modal / form saat dosen akan melakukan unggah file data dan menjalankan prediksi.
- [ ] **Button Download Template**
  - Tambahkan tombol khusus untuk mengunduh template file Excel standard penulisan data mahasiswa/nilai.
- [ ] **Pratinjau (Preview) Upload**
  - Menampilkan ringkasan data sebelum disimpan/diproses yang berisi:
    - NIM
    - Nama Mahasiswa
    - IPK pada semester tersebut

---

## 2. Scope Role Admin

### Sisi Admin (Pengelolaan Model & Eksperimen)
- [ ] **Eksperimen Model**
  - Fleksibilitas / kebebasan bagi admin untuk melakukan eksperimen konfigurasi model machine learning.
- [ ] **Pengaturan Parameter**
  - Opsi pemilihan dan konfigurasi parameter yang digunakan dalam model/pelatihan.
- [ ] **Filter Tahun Akademik**
  - Pengaturan rentang tahun akademik/angkatan yang akan diakses dan diolah.
- [ ] **Proses Training Model**
  - Antarmuka khusus bagi admin untuk menjalankan re-training / training model machine learning dari sisi admin.

---

## 3. Fitur Bersama (Role Admin & DPA)

### Opsi Download & Interaktivitas PDF / Laporan
- [x] **Informasi Mahasiswa pada PDF**
  - Menampilkan header data utama:
    - Nama Mahasiswa
    - NIM
    - Program Studi (Prodi)
- [x] **Interaktivitas Bar Chart**
  - Saat batang pada Bar Chart diklik, tampilkan daftar mahasiswa terkait.
  - Hapus tampilan tabel/daftar mahasiswa statis yang sebelumnya berada di bawah chart.
- [x] **Modal / Tampilan "Lihat Detail"**
  - Jika tombol **Lihat Detil** diklik, tampilkan daftar nilai mata kuliah (Matkul) yang **belum lulus** pada semester tersebut.
- [x] **Metrik Persentase**
  - Ubah indikator persentase agar menampilkan **persentase mahasiswa yang berpotensi mengikuti sisip program** (bukan persentase mahasiswa yang lulus).