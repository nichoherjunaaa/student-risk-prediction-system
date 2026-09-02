# Deployment: VPS + Docker Compose + Jenkins CI/CD

Target: VPS `43.133.144.108` yang **sudah** menjalankan Docker + Jenkins (dipakai
project lain). SISIP ditambahkan sebagai stack Docker Compose terpisah dan
di-deploy otomatis oleh Jenkins setiap push ke branch `main`.

```
git push main --webhook--> Jenkins (:8080) --> docker compose build & up --> SISIP live (:8090)
```

Arsitektur runtime (isolasi penuh dari project lama — project name `sisip`,
network & volume sendiri):

| Container  | Isi                                   | Port         |
|------------|---------------------------------------|--------------|
| `sisip-frontend` | Nginx + build React (`dist`)    | host `${SISIP_HTTP_PORT:-8090}` -> 80 |
| `sisip-backend`  | Flask + Gunicorn + TensorFlow   | internal `5000` (tidak di-publish) |
| volume `sisip_sisip-data` | `sisip_database.db` + `saved_models/` | persisten |

Nginx (`sisip-frontend`) mem-proxy `/api/` ke `sisip-backend:5000`. DB SQLite &
file model disimpan di named volume, jadi **tidak hilang** saat redeploy.

---

## 1. Persiapan VPS

Docker & Jenkins sudah ada, jadi tinggal:

### 1.1 Firewall — buka port aplikasi

```bash
ufw allow 8090/tcp        # port SISIP (sesuaikan dgn SISIP_HTTP_PORT)
```

### 1.2 Cek resource

TensorFlow butuh RAM besar. Pastikan masih ada headroom di luar project lama:

```bash
free -h            # idealnya sisa >= 2 GB untuk container backend
df -h /            # butuh ~3 GB untuk image backend
```

Kalau RAM mepet, tambah swap:

```bash
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 2. Prasyarat Jenkins (sudah terpasang di VPS)

Jenkins sudah jalan di `http://43.133.144.108:8080`. Pastikan hal berikut:

1. **Agent bisa jalankan Docker.** Cek dari "Manage Jenkins -> Script Console":
   ```groovy
   println "docker compose version".execute().text
   ```
   Harus keluar versi Compose v2. Kalau Jenkins jalan dalam container, dia perlu
   `/var/run/docker.sock` ter-mount + CLI `docker` + plugin `docker-compose`.
   (Karena project lama kamu sudah CI/CD dengan Docker, ini biasanya sudah beres.)

2. **Plugin:** `Git`, `Pipeline`, dan **`GitHub`** (untuk trigger webhook).
   Manage Jenkins -> Plugins -> Available.

3. **Jenkins URL benar:** Manage Jenkins -> System -> **Jenkins URL** =
   `http://43.133.144.108:8080/` (dipakai untuk validasi webhook).

---

## 3. Kredensial

Manage Jenkins -> **Credentials** -> **System** -> **Global credentials (unrestricted)**
-> **+ Add Credentials**:

| Kind | ID | Isi |
|------|----|-----|
| **Secret file** | `sisip-env` | Upload file `.env` berisi variabel produksi (lihat di bawah) |

Untuk akses repo GitHub, **pakai ulang credential `id-nicho`** yang sudah ada
(dipakai project `sigap`). Tidak perlu bikin credential GitHub baru. Kalau repo
`student-risk-prediction-system` ternyata public, malah tidak butuh credential
sama sekali untuk checkout.

Isi file `.env` yang di-upload sebagai `sisip-env`
(pakai `.env.example` di repo sebagai acuan):

```env
SISIP_HTTP_PORT=8090
SISIP_ADMIN_EMAIL=admin@gmail.com
SISIP_ADMIN_PASSWORD=GANTI_PASSWORD_KUAT
```

> Port host `8090` dipilih supaya tidak bentrok dengan project lama di port 80.
> Ganti ke `80` kalau memang bebas, atau ke port lain sesuai kebutuhan.
> Buka port di firewall: `ufw allow 8090/tcp`.

`Jenkinsfile` meng-copy secret file ini jadi `./.env` saat build dan menghapusnya
lagi di akhir (stage `Prepare env` + `post { always }`).

---

## 4. Buat Pipeline Job

1. **New Item** -> nama `sisip-program` -> **Pipeline** -> OK.
2. **Pipeline** section:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://github.com/nichoherjunaaa/student-risk-prediction-system.git`
   - Credentials: pilih `github-sisip` (kalau repo private; kalau public kosongkan)
   - Branch Specifier: `*/main`
   - Script Path: `Jenkinsfile`
3. **Save**.

`Jenkinsfile` sudah berisi `triggers { pollSCM('H/5 * * * *') }` sebagai cadangan.
Untuk deploy **instan** setiap push ke `main`, pasang webhook di langkah 5.

---

## 5. Auto-deploy setiap ada perubahan di `main`

Ada dua lapis trigger; keduanya sudah/otomatis aktif:

### 5a. Webhook GitHub (utama, instan)

1. Di Jenkins job `sisip-program` -> **Configure** -> **Build Triggers** ->
   centang **GitHub hook trigger for GITScm polling** -> Save.
2. Di GitHub repo -> **Settings -> Webhooks -> Add webhook**:
   - **Payload URL:** `http://43.133.144.108:8080/github-webhook/`
   - **Content type:** `application/json`
   - **SSL verification:** Disable (Jenkins masih HTTP)
   - **Which events:** *Just the push event*
   - **Active:** ✓
3. Klik webhook yang baru dibuat -> tab **Recent Deliveries** -> pastikan ada
   centang hijau (respons `200`).

Alur: `git push origin main` -> GitHub kirim POST ke `/github-webhook/` ->
Jenkins cek perubahan -> pipeline jalan -> `docker compose up -d` ->
health check. Biasanya mulai < 5 detik setelah push.

> Pipeline hanya membangun branch `main` (Branch Specifier `*/main`), jadi push
> ke branch lain / PR tidak ikut men-deploy.

### 5b. Poll SCM (cadangan, tiap 5 menit)

Sudah tertulis di `Jenkinsfile` (`pollSCM('H/5 * * * *')`). Kalau webhook gagal
terkirim (mis. GitHub tidak bisa menjangkau IP:8080), Jenkins tetap menarik
perubahan `main` maksimal 5 menit kemudian. Tidak perlu setup tambahan.

### Verifikasi auto-deploy

```bash
# di lokal
git commit --allow-empty -m "test: trigger auto-deploy" && git push origin main
```
Buka Jenkins -> job `sisip-program` -> harus muncul build baru "Started by GitHub push".

---

## 6. Deploy Pertama

Trigger sekali manual: Jenkins -> job `sisip-program` -> **Build Now**.
Pipeline akan checkout -> build image -> `docker compose up -d` -> health check.
Build pertama ~5–10 menit (download image TensorFlow).

Verifikasi:

```bash
docker ps --filter name=sisip
curl http://43.133.144.108:8090/api/health     # {"status":"ok"}
```

Buka `http://43.133.144.108:8090` -> login `admin@gmail.com` / password dari `.env`.

### Akun demo untuk testing E2E

`SISIP_SEED_DEMO_USERS=1` (default) membuat 1 akun per role, otomatis setiap
startup backend (idempotent — tidak menimpa kalau sudah ada):

| Role      | Email                      | Password      | Akses di UI                          |
|-----------|----------------------------|---------------|-------------------------------------|
| `admin`   | `admin.test@sisip.test`    | `Admin#2026`   | Master Model, Master Pengguna, Log Riwayat, Unggah, Hasil |
| `dpa`     | `dpa.test@sisip.test`      | `Dpa#2026`     | Unggah Data, Hasil Prediksi          |
| `kaprodi` | `kaprodi.test@sisip.test`  | `Kaprodi#2026` | sama dengan DPA (kode UI belum bedakan kaprodi) |

Untuk produksi sungguhan, set `SISIP_SEED_DEMO_USERS=0` di credential `sisip-env`
lalu hapus akun `*.test@sisip.test` lewat menu **Master Pengguna**.

---

## 7. (Opsional) Migrasi data lama

Volume mulai kosong; `backend` otomatis membuat DB baru dan seed akun admin.
Kalau mau membawa `sisip_database.db` dan `saved_models/` yang sudah ada dari
mesin lokal (jalankan setelah deploy pertama, container `sisip-backend` sudah ada):

```bash
# dari mesin lokal
scp backend/sisip_database.db root@43.133.144.108:/root/
scp -r backend/saved_models root@43.133.144.108:/root/

# di VPS — pakai nama container langsung, tanpa perlu file compose
docker stop sisip-backend
docker cp /root/sisip_database.db sisip-backend:/data/sisip_database.db
docker cp /root/saved_models/. sisip-backend:/data/saved_models/
docker start sisip-backend
```

Row `model_registry` lama yang menyimpan path relatif (`saved_models/xxx.keras`)
tetap dikenali — `resolve_model_path()` di `app.py` mencari ulang berdasarkan
nama file di `SISIP_MODEL_DIR`.

---

## 8. Operasional

Container punya nama tetap (`sisip-backend`, `sisip-frontend`), jadi tidak perlu
tahu lokasi file compose:

```bash
docker logs -f sisip-backend           # log backend
docker logs -f sisip-frontend          # log nginx
docker restart sisip-backend
docker stats sisip-backend             # cek RAM (TensorFlow rakus)

# Backup DB
docker cp sisip-backend:/data/sisip_database.db ~/backup-$(date +%F).db

# Isi volume
docker run --rm -v sisip_sisip-data:/data alpine ls -la /data
```

**Rollback:** di Jenkins buka build lama yang hijau -> **Replay**, atau
`git revert <commit> && git push origin main` (auto-deploy akan jalan lagi).

**Stop sementara:** `docker stop sisip-frontend sisip-backend` (volume aman).

---

## 9. Pengembangan lokal (tetap jalan seperti biasa)

```bash
# backend
cd backend && python app.py            # http://localhost:5000

# frontend
cd frontend && npm run dev             # http://localhost:5173
```

`vite.config.js` sudah punya proxy: `/api` -> `http://localhost:5000` saat dev.
Frontend memakai path relatif `/api/...`, jadi kode yang sama jalan di dev
maupun produksi.

---

## Catatan

- **Trigger di `Jenkinsfile` (`pollSCM`) baru aktif setelah build pertama.**
  Jalankan **Build Now** sekali (langkah 6) supaya Jenkins membaca blok `triggers`.
- **Isolasi dari project lama:** compose pakai `name: sisip`, network `sisip_default`,
  volume `sisip_sisip-data`, container `sisip-*`, dan port host `8090`. Tidak
  menyentuh resource project lain. Kalau `8090` juga terpakai, ganti `SISIP_HTTP_PORT`
  di credential `sisip-env`.
- Image backend besar (~2 GB) karena TensorFlow. Untuk menghemat disk, bisa ganti
  `tensorflow` -> `tensorflow-cpu` di `backend/requirements.txt` (VPS tidak punya GPU).
- Belum ada HTTPS (akses via IP:port). Kalau nanti mau domain/HTTPS, arahkan
  reverse proxy yang ada ke `http://127.0.0.1:8090`.
- Autentikasi backend masih sederhana (cek email+password hash, tanpa token
  session di server). Pertimbangkan hardening sebelum expose ke publik luas.
