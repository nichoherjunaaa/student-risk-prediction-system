# Panduan Deployment Server Desktop Windows Menggunakan WSL2 (SISIP Program)

Dokumen ini berisi panduan lengkap untuk mengubah Komputer Desktop ber-OS **Windows 10 / Windows 11** menjadi server lokal (*On-Premise Server*) yang andal menggunakan **WSL2 (Windows Subsystem for Linux)**.

---

## 1. Lisensi & Biaya

**100% GRATIS (0 Rupiah)**
Seluruh perangkat lunak yang digunakan bersifat *Open Source* dan bebas lisensi:
- **OS**: Windows 10/11 (Menggunakan WSL2 Ubuntu) — *Gratis*
- **Backend & ML**: Python, Flask, Gunicorn, TensorFlow, Scikit-learn, SQLite — *Gratis*
- **Frontend**: Node.js, React, Vite, Nginx — *Gratis*
- **Sertifikat SSL / HTTPS**: Let's Encrypt / Certbot — *Gratis*
- **Akses Remote (Internet)**: Direct Public IP / Cloudflare Tunnel — *Gratis*

---

## 2. Kebutuhan Perangkat & Sistem

### Perangkat Keras (Hardware)
- **CPU**: Minimal Intel Core i3 / AMD Ryzen 3 (Quad-Core).
- **RAM**: Minimal **4 GB** (Disarankan **8 GB+** untuk proses training/prediksi TensorFlow).
- **Storage**: SSD dengan ruang kosong minimal 15–20 GB.

### Perangkat Lunak (Software)
- OS Windows 10 (versi 2004 ke atas) atau Windows 11.
- **WSL2 (Ubuntu 22.04 / 24.04 LTS)**.
- **Jaringan**: IP Publik (sudah disiapkan oleh Tim IT / Kampus).

---

## 3. Langkah-Langkah Instalasi Lengkap (WSL2 di Windows)

### LANGKAH 1: Install dan Aktifkan WSL2 di Windows

1. Buka **Windows PowerShell** sebagai **Administrator** (Klik kanan pada Start Menu -> *Windows PowerShell (Admin)*).
2. Ketik perintah berikut lalu tekan Enter:
   ```powershell
   wsl --install
   ```
3. Tunggu hingga proses pengunduhan selesai, lalu **Restart Komputer Desktop Anda**.
4. Setelah restart, jendela **Ubuntu** akan terbuka secara otomatis. Masukkan *Username* dan *Password* baru sesuai keinginan Anda (simpan password ini baik-baik).

---

### LANGKAH 2: Mengakses Folder Proyek dari WSL2

Proyek Anda yang ada di Windows (misal di `C:\sisip-program` atau drive lain) dapat diakses dari dalam terminal Ubuntu WSL2 pada path `/mnt/c/` atau `/mnt/d/`.

*Contoh jika file ada di Drive C:*
```bash
cd /mnt/c/path/ke/proyek/sisip-program
```

> **Tips Performa**: Untuk kecepatan optimal TensorFlow dan Node.js, Anda disarankan menyalin folder proyek ke dalam direktori home Linux WSL2:
> ```bash
> cp -r /mnt/c/path/ke/proyek/sisip-program ~/sisip-program
> cd ~/sisip-program
> ```

---

### LANGKAH 3: Install Dependensi Sistem di Ubuntu WSL2

Buka Terminal Ubuntu WSL2 dan jalankan perintah update serta install paket utama:

```bash
# Update paket Linux
sudo apt update && sudo apt upgrade -y

# Install Python, pip, venv, Nginx, Git, Curl, Certbot
sudo apt install -y python3 python3-pip python3-venv nginx git curl certbot python3-certbot-nginx

# Install Node.js v18 LTS & npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

---

### LANGKAH 4: Setup Backend (Python Flask + Gunicorn)

1. Masuk ke folder backend:
   ```bash
   cd ~/sisip-program/backend
   ```
2. Buat virtual environment & aktifkan:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install seluruh library Python:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Uji coba jalankan backend:
   ```bash
   gunicorn --bind 127.0.0.1:5000 app:app
   ```
   *(Jika tidak ada error, tekan `Ctrl + C` untuk berhenti)*.

---

### LANGKAH 5: Setup & Build Frontend (React + Vite)

1. Masuk ke folder frontend:
   ```bash
   cd ~/sisip-program/frontend
   ```
2. Install paket Node.js:
   ```bash
   npm install
   ```
3. Build file statis untuk produksi:
   ```bash
   npm run build
   ```
   *(Hasil build tersimpan otomatis di `frontend/dist`)*.

---

### LANGKAH 6: Konfigurasi Service Auto-Start Backend (Systemd)

Agar backend Flask otomatis berjalan sendiri di latar belakang saat Windows menyala:

1. Buat file service systemd:
   ```bash
   sudo nano /etc/systemd/system/sisip-backend.service
   ```
2. Isikan konfigurasinya (*sesuaikan username dan path*):
   ```ini
   [Unit]
   Description=SISIP Backend Flask Service
   After=network.target

   [Service]
   User=username_ubuntu_anda
   WorkingDirectory=/home/username_ubuntu_anda/sisip-program/backend
   Environment="PATH=/home/username_ubuntu_anda/sisip-program/backend/venv/bin"
   ExecStart=/home/username_ubuntu_anda/sisip-program/backend/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
3. Simpan (`Ctrl + O`, Enter, lalu `Ctrl + X`).
4. Aktifkan service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start sisip-backend
   sudo systemctl enable sisip-backend
   ```

---

### LANGKAH 7: Konfigurasi Nginx Web Server

1. Buat file konfigurasi situs:
   ```bash
   sudo nano /etc/nginx/sites-available/sisip
   ```
2. Masukkan konfigurasi Nginx (*Ganti `sisip.kampus.ac.id` dengan nama domain/subdomain Anda jika ada, atau biarkan `_`*):
   ```nginx
   server {
       listen 80;
       server_name sisip.kampus.ac.id; # Atau biarkan _ jika belum ada domain

       # Serve Frontend React
       location / {
           root /home/username_ubuntu_anda/sisip-program/frontend/dist;
           index index.html;
           try_files $uri $uri/ /index.html;
       }

       # Forward Request API ke Backend Flask
       location /api/ {
           proxy_pass http://127.0.0.1:5000/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
3. Aktifkan dan restart Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/sisip /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

### LANGKAH 8: Mengakses Aplikasi dari Laptop Lain di LAN Windows

1. Cek IP Windows Komputer Server:
   - Buka **Command Prompt (CMD)** di Windows, ketik: `ipconfig`
   - Catat **IPv4 Address** (misal: `192.168.1.50`).
2. Buka Firewall Windows untuk Port 80 & 443:
   - Buka PowerShell (Admin) di Windows, jalankan:
     ```powershell
     New-NetFirewallRule -DisplayName "SISIP Server Port 80" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
     New-NetFirewallRule -DisplayName "SISIP Server Port 443" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow
     ```
3. **Akses dari Perangkat Lain di LAN**: `http://192.168.1.50`

---

## 4. Langkah Pengaturan IP Publik (Akses dari Luar Kampus / Internet)

Karena **IP Publik sudah disiapkan**, konfigurasi dilakukan setelah **LANGKAH 8** selesai (setelah server lokal dipastikan berjalan).

Berikut adalah 4 sub-langkah penerapan IP Publik:

### Sub-Langkah 4.1: Pengaturan Port Forwarding di Router / Firewall Utama Kampus
Minta Tim IT / Admin Jaringan Kampus untuk mengarahkan Port Forwarding (NAT) dari Router ke PC Server:
* **Public IP (Contoh)**: `202.x.y.z`
* **Port Forwarding**:
  * Forward **Port 80 (HTTP)** Public IP (`202.x.y.z:80`) $\rightarrow$ ke IP Lokal Windows Server (`192.168.1.50:80`).
  * Forward **Port 443 (HTTPS)** Public IP (`202.x.y.z:443`) $\rightarrow$ ke IP Lokal Windows Server (`192.168.1.50:443`).

---

### Sub-Langkah 4.2: Mapping Domain / Subdomain ke IP Publik (A Record DNS)
Jika Anda memiliki nama domain kampus (misal: `sisip.kampus.ac.id`):
1. Buka DNS Management domain Anda.
2. Tambahkan **A Record**:
   * **Host / Name**: `sisip` (atau subdomain yang diinginkan)
   * **Points to / Value**: `202.x.y.z` (IP Publik Anda)
   * **TTL**: Auto / 3600

---

### Sub-Langkah 4.3: Update Server Name di Nginx
Di dalam terminal Ubuntu WSL2:
```bash
sudo nano /etc/nginx/sites-available/sisip
```
Ubah bagian `server_name`:
```nginx
server_name sisip.kampus.ac.id 202.x.y.z;
```
Lalu simpan dan reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

### Sub-Langkah 4.4: Memasang Sertifikat SSL Gratis (HTTPS) dengan Certbot
Agar akses dari luar kampus aman (menggunakan HTTPS), pasang sertifikat SSL Let's Encrypt gratis melalui terminal Ubuntu WSL2:

```bash
sudo certbot --nginx -d sisip.kampus.ac.id
```
* Certbot akan secara otomatis mengonfigurasi sertifikat SSL di Nginx dan mengarahkan lalu lintas HTTP secara otomatis ke **HTTPS**.
* Sertifikat ini gratis dan akan diperbarui (*auto-renew*) secara otomatis oleh Certbot.

---

### 🚀 Pengujian Akses dari Luar Kampus:
Setelah Sub-Langkah 4.1 - 4.4 selesai, siapa pun di luar jaringan kampus (menggunakan paket data HP / Wi-Fi rumah) dapat mengakses sistem via browser melalui URL:

```text
https://sisip.kampus.ac.id
atau
http://202.x.y.z  (jika diakses langsung via IP Publik)
```
