# Integrasi SIA → Sisip Program (masuk tanpa login)

**Tanggal:** 24 September 2026
**Status:** tahap koordinasi dengan tim SIA — belum diimplementasikan di Sisip.

Halaman login Sisip tetap ada. Jalur SIA ini adalah jalur masuk tambahan.

## Alur

1. User mengklik menu **"Sisip Program"** di SIA.
2. **Backend SIA** membuat link bertanda tangan (rumus di bawah), lalu mengarahkan
   browser ke link tersebut.
3. Sisip memeriksa link itu. Kalau valid, user langsung masuk ke dashboard. Kalau
   tidak valid, akses ditolak.

## Format link

```
https://<base-url-sisip>/sso/sia?id=<id>&ts=<ts>&nonce=<nonce>&sig=<sig>
```

| Parameter | Isi |
|---|---|
| `id` | Identitas dosen: **email** (huruf kecil) **atau** **nomor dosen** (angka saja, tanpa spasi, titik, atau strip) |
| `ts` | Waktu saat link dibuat, dalam Unix timestamp (detik, UTC) |
| `nonce` | 32 karakter hex acak, dibuat baru setiap kali link dibuat |
| `sig` | Tanda tangan digital, dihitung dengan rumus di bawah |

Sisip menentukan jenis `id` dari nilainya: kalau mengandung `@`, dicari sebagai
email; kalau tidak, dicari sebagai nomor dosen.

## Rumus tanda tangan

```
pesan = "v1|" + id + "|" + ts + "|" + nonce
sig   = hex_lowercase( HMAC_SHA256( key = SECRET, data = pesan ) )
```

`sig` membuktikan dua hal: link benar-benar dibuat oleh SIA (hanya SIA dan Sisip
yang tahu `SECRET`), dan isi link tidak diubah di tengah jalan. Tanpa `sig`,
siapa pun bisa mengetik link dengan nomor dosen orang lain dan masuk sebagai
dosen tersebut.

## Contoh implementasi (PHP)

```php
$id    = preg_replace('/\D/', '', $nomor_dosen);   // atau: strtolower(trim($email))
$ts    = time();
$nonce = bin2hex(random_bytes(16));
$sig   = hash_hmac('sha256', "v1|$id|$ts|$nonce", SECRET);

$url = SISIP_BASE_URL . '/sso/sia?' . http_build_query([
    'id' => $id, 'ts' => $ts, 'nonce' => $nonce, 'sig' => $sig,
]);
header('Location: ' . $url);
```

## Contoh uji

Gunakan secret contoh ini untuk mencocokkan implementasi. Kalau `sig` yang
dihasilkan sama, rumusnya sudah benar. (Nilai di bawah sudah diverifikasi di
Python dan PHP.)

```
SECRET contoh : contoh-rahasia-JANGAN-dipakai-di-produksi

pesan : v1|dpa@gmail.com|1790000000|3f9c2a7e1b4d8c60a5e2f1d9b7c3a4e8
sig   : baea804e9842000a88dd0da85267d3d3814b14c988302ee1dd4bddfc91cfe73e

pesan : v1|0012345678|1790000000|3f9c2a7e1b4d8c60a5e2f1d9b7c3a4e8
sig   : 59f52c52a12c5077afb55f8037de09c49e58a225899d82bc95734e5dba628b9c
```

## Ketentuan

1. `sig` **wajib dibuat di backend SIA**. `SECRET` tidak boleh ada di JavaScript,
   HTML, atau repository publik.
2. Link hanya berlaku **120 detik** dan hanya bisa dipakai **sekali**. Link harus
   dibuat saat menu diklik, tidak boleh disimpan atau dibuat lebih awal.
3. **Jam server SIA harus sinkron** (NTP). Selisih waktu lebih dari 120 detik akan
   membuat link ditolak.
4. Kedua sisi wajib memakai **HTTPS**.
5. User **harus sudah terdaftar di Sisip**. Hak akses (role) ditentukan oleh Sisip,
   bukan oleh SIA.
6. **`SECRET` asli** diberikan oleh pihak Sisip saat implementasi, lewat jalur aman
   (bukan grup chat atau email biasa). `SECRET` dipegang oleh dua pihak: SIA untuk
   membuat `sig`, Sisip untuk memeriksanya.

## Yang perlu dikoordinasikan

### Pertanyaan untuk tim SIA

1. Identitas dosen apa yang tersedia di SIA: **email**, **nomor dosen**, atau keduanya?
2. Kalau nomor dosen, jenisnya apa: **NIDN, NIP, atau NUPTK**?
3. Kalau email, apakah email tersebut sama dengan email yang dipakai dosen di Sisip
   (email kampus atau email pribadi)?
4. Bahasa atau framework apa yang dipakai backend SIA? Ini untuk contoh kode kalau
   bukan PHP.
5. Apakah server SIA sudah memakai HTTPS dan jamnya sudah tersinkron NTP?
6. Siapa yang boleh melihat menu "Sisip Program" di SIA? Apakah hanya dosen DPA
   dan Kaprodi?

### Informasi dari pihak Sisip ke tim SIA

1. **Base URL** Sisip di server produksi.
2. **`SECRET`** asli, diserahkan lewat jalur aman saat implementasi.
3. Jadwal **uji coba bersama** sebelum menu dibuka untuk semua user.

---

## Catatan internal Sisip (tidak perlu dikirim ke tim SIA)

### Persiapan sebelum implementasi

- Tentukan **base URL produksi** Sisip.
- Setelah tim SIA menjawab pertanyaan 1–3, isi akun DPA dan Kaprodi di Sisip sesuai
  jawabannya: email yang sama dengan di SIA, atau nomor dosen.
- Buat `SECRET` dengan `openssl rand -hex 32`, terpisah dari `SISIP_SECRET_KEY`.

### Rencana implementasi

- **Backend:**
  - Endpoint `POST /api/sso/sia`. Urutan pemeriksaan: `sig` cocok (dibandingkan
    dengan `hmac.compare_digest`), `|sekarang − ts| ≤ 120` detik, `nonce` belum
    pernah dipakai, lalu user terdaftar dan belum dihapus (`deleted_at IS NULL`).
  - Kalau lolos, buat token sesi dengan `_make_token()`, sama seperti login biasa.
  - Tabel `sso_nonce (nonce PRIMARY KEY, expires_at)` yang dibersihkan otomatis.
  - Kolom `users.nomor_dosen` (unik, boleh kosong) lewat `_migrate_columns`.
  - Env `SISIP_SIA_SSO_SECRET`. Kalau kosong, jalur SSO mati.
  - Log audit setiap percobaan SSO beserta hasilnya.
- **Frontend:**
  - Route `/sso/sia`: kirim parameter ke backend, hapus query dari URL
    (`history.replaceState`), `clearSession()`, simpan token, lalu masuk ke
    dashboard sesuai role.
  - Halaman error "Akses dari SIA tidak valid atau sudah kedaluwarsa" dengan
    tautan ke halaman login.
  - Kolom "Nomor Dosen (NIDN/NIP)" di form tambah/edit user milik admin.
- **Nginx produksi:** route `/sso/sia` diarahkan ke `index.html`, dan header
  `Referrer-Policy: no-referrer` supaya token tidak bocor lewat Referer.

### Keputusan yang masih terbuka

- Akun **admin** boleh masuk lewat SIA atau khusus lewat halaman login? Saran: khusus
  lewat halaman login.
- Setelah logout, user yang masuk lewat SIA kembali ke halaman login Sisip atau ke SIA?
