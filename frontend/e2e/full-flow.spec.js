import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { ADMIN, ROOT, SHOT_DIR, shot, loginOk, logout, apiToken, auth, download } from './helpers'

// Alur lengkap terhadap database yang sedang dipakai backend:
//   admin membuat akun tiap role -> BAPSI mengelola & mengunggah berkas PMB/akademik
//   -> admin cek format, preprocessing, latih & aktifkan model -> DPA, Kaprodi,
//   Dekan, admin menjalankan prediksi -> ringkasan.
// Hasil test SENGAJA disisakan supaya bisa dilihat di aplikasi: akun uji, folder
// & berkas BAPSI, batch prediksi, dan model hasil latih (nonaktif). Aksi hapus
// diuji pada data sementara yang dibuat khusus untuk dihapus. Hanya model aktif
// Teknik Mesin yang dikembalikan seperti semula. Daftar akun uji tiap run ditulis
// ke e2e-screenshots/akun-uji.txt.

test.describe.configure({ mode: 'serial' })

const PMB_FILE = path.join(ROOT, '20260605_Data_PMB.xlsx')
const AKADEMIK_FILE = path.join(ROOT, 'Data_akademik_te_tm_mat.xlsx')
const STAMP = String(Date.now())
const RUN = `E2E-${STAMP}`
const FOLDER = `${RUN} Berkas`
const PASSWORD = 'E2eTest#2026'

// Berkas contoh hanya memuat Teknik Mesin, Teknik Elektro, dan Matematika.
// NIP unik per run supaya hasil run sebelumnya tidak perlu dihapus.
const nip = (i) => `9${STAMP}${i}`
const USERS = {
  dpa: { nip: nip(1), name: `${RUN} DPA`, role: 'dpa', prodi: 'Teknik Mesin' },
  kaprodi: { nip: nip(2), name: `${RUN} Kaprodi`, role: 'kaprodi', prodi: 'Teknik Elektro' },
  dekan: { nip: nip(3), name: `${RUN} Dekan`, role: 'dekan', prodi: '' },
  bapsi: { nip: nip(4), name: `${RUN} BAPSI`, role: 'bapsi', prodi: '' },
}
const cred = (u) => ({ nip: u.nip, password: PASSWORD })

let trainFile = null
let previousActive = null

test('01 admin membuat akun untuk setiap role', async ({ page }) => {
  const G = '01-admin-kelola-pengguna'
  await loginOk(page, ADMIN)
  await page.goto('/admin/users')
  await shot(page, G, '01-daftar-pengguna-awal')

  for (const u of Object.values(USERS)) {
    await page.getByRole('button', { name: 'Tambah Pengguna' }).click()
    await expect(page).toHaveURL(/\/admin\/users\/new$/)
    await page.getByPlaceholder('Masukkan nama lengkap pengguna').fill(u.name)
    await page.getByPlaceholder(/Contoh: 1987/).fill(u.nip)
    await page.locator('form select').first().selectOption(u.role)
    if (u.prodi) await page.locator('form select').nth(1).selectOption(u.prodi)
    await page.getByPlaceholder('Buat kata sandi aman').fill(PASSWORD)
    await shot(page, G, `02-form-${u.role}`)
    await page.getByRole('button', { name: 'Simpan Data' }).click()
    await expect(page).toHaveURL(/\/admin\/users$/)
    await expect(page.getByRole('row', { name: new RegExp(u.name) })).toBeVisible()
  }
  await shot(page, G, '03-daftar-setelah-tambah')

  // Ubah nama akun dekan, lalu kembalikan.
  const dekan = USERS.dekan
  await page.getByRole('button', { name: `Ubah pengguna ${dekan.name}` }).click()
  await expect(page).toHaveURL(/\/admin\/users\/edit\/\d+$/)
  await expect(page.getByPlaceholder('Masukkan nama lengkap pengguna')).toHaveValue(dekan.name)
  dekan.name = `${dekan.name} (diubah)`
  await page.getByPlaceholder('Masukkan nama lengkap pengguna').fill(dekan.name)
  await shot(page, G, '04-form-ubah-dekan')
  await page.getByRole('button', { name: 'Simpan Data' }).click()
  await expect(page.getByRole('row', { name: new RegExp(dekan.name.replace(/[()]/g, '\\$&')) })).toBeVisible()
  await shot(page, G, '05-daftar-setelah-ubah')

  // Aksi hapus diuji pada akun sementara, akun uji lainnya disisakan.
  const sementara = { nip: nip(9), name: `${RUN} Akun Sementara` }
  await page.getByRole('button', { name: 'Tambah Pengguna' }).click()
  await page.getByPlaceholder('Masukkan nama lengkap pengguna').fill(sementara.name)
  await page.getByPlaceholder(/Contoh: 1987/).fill(sementara.nip)
  await page.locator('form select').first().selectOption('bapsi')
  await page.getByPlaceholder('Buat kata sandi aman').fill(PASSWORD)
  await page.getByRole('button', { name: 'Simpan Data' }).click()
  await page.getByRole('button', { name: `Hapus pengguna ${sementara.name}` }).click()
  await shot(page, G, '06-konfirmasi-hapus-pengguna')
  await page.getByRole('button', { name: 'Ya, Hapus' }).click()
  await expect(page.getByRole('button', { name: `Hapus pengguna ${sementara.name}` })).toBeHidden()
  await shot(page, G, '07-daftar-setelah-hapus')

  fs.mkdirSync(SHOT_DIR, { recursive: true })
  fs.appendFileSync(path.join(SHOT_DIR, 'akun-uji.txt'), [
    `# Run ${RUN} (${new Date().toISOString()}) - password semua akun: ${PASSWORD}`,
    ...Object.values(USERS).map((u) => `${u.role.padEnd(8)} NIP ${u.nip}  ${u.name}${u.prodi ? ` (${u.prodi})` : ''}`),
    '',
  ].join('\n'))
  await logout(page)
})

test('02 BAPSI mengelola folder dan mengunggah berkas', async ({ page }) => {
  const G = '02-bapsi-berkas-mahasiswa'
  await loginOk(page, cred(USERS.bapsi))
  await expect(page).toHaveURL(/\/berkas$/)
  await shot(page, G, '01-beranda')

  // Folder baru, lalu ganti nama.
  await page.getByRole('button', { name: 'Folder Baru' }).click()
  const draftName = `${RUN} draf`
  await page.getByRole('dialog').locator('input').fill(draftName)
  await shot(page, G, '02-dialog-folder-baru')
  await page.getByRole('button', { name: 'Buat Folder' }).click()
  await expect(page.getByRole('row', { name: new RegExp(draftName) })).toBeVisible()
  await page.getByRole('row', { name: new RegExp(draftName) }).getByRole('button', { name: 'Ganti nama' }).click()
  await page.getByRole('dialog').locator('input').fill(FOLDER)
  await page.getByRole('button', { name: 'Simpan' }).click()
  await expect(page.getByRole('row', { name: new RegExp(FOLDER) })).toBeVisible()
  await shot(page, G, '03-folder-dibuat')

  // Masuk folder dan unggah berkas PMB, akademik, dan satu berkas pendukung.
  await page.getByRole('row', { name: new RegExp(FOLDER) }).getByRole('button', { name: FOLDER }).click()
  await expect(page.getByText('Folder ini masih kosong.')).toBeVisible()
  for (const [label, file] of [['Berkas PMB', PMB_FILE], ['Berkas Akademik', AKADEMIK_FILE], ['Lainnya', AKADEMIK_FILE]]) {
    await page.getByRole('button', { name: 'Unggah Berkas' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: label, exact: true }).click()
    await dialog.locator('input[type="file"]').setInputFiles(file)
    await shot(page, G, `04-unggah-${label.toLowerCase().replace(/\s+/g, '-')}`)
    await dialog.getByRole('button', { name: /^Unggah 1 Berkas$/ }).click()
    await expect(dialog).toBeHidden({ timeout: 60_000 })
  }
  await expect(page.getByRole('row', { name: /20260605_Data_PMB\.xlsx/ })).toBeVisible()
  await shot(page, G, '05-berkas-terunggah')

  // Berkas pendukung: ganti nama, unduh, pindahkan ke Beranda, lalu hapus.
  const pendukung = page.getByRole('row').filter({ hasText: 'Lainnya' })
  await pendukung.getByRole('button', { name: 'Ganti nama' }).click()
  await page.getByRole('dialog').locator('input').fill(`${RUN} lampiran`)
  await page.getByRole('button', { name: 'Simpan' }).click()
  const lampiran = page.getByRole('row', { name: new RegExp(`${RUN} lampiran`) })
  await expect(lampiran).toBeVisible()
  await download(page, () => lampiran.getByRole('button', { name: 'Unduh' }).click())
  await lampiran.getByRole('button', { name: 'Pindahkan' }).click()
  await shot(page, G, '06-dialog-pindahkan')
  await page.getByRole('button', { name: 'Pindahkan ke Sini' }).click()
  await expect(lampiran).toBeHidden()

  await page.getByRole('navigation', { name: 'Lokasi folder' }).getByRole('button').first().click()
  await page.getByPlaceholder('Cari nama berkas di semua folder').fill(RUN)
  await expect(page.getByRole('row', { name: new RegExp(`${RUN} lampiran`) })).toBeVisible()
  await shot(page, G, '07-pencarian')
  await page.getByRole('row', { name: new RegExp(`${RUN} lampiran`) }).getByRole('button', { name: 'Hapus berkas' }).click()
  await shot(page, G, '08-konfirmasi-hapus-berkas')
  await page.getByRole('button', { name: 'Ya, Hapus' }).click()
  await expect(page.getByRole('row', { name: new RegExp(`${RUN} lampiran`) })).toBeHidden()

  await page.getByPlaceholder('Cari nama berkas di semua folder').fill('')
  await page.getByRole('button', { name: 'Tampilan kisi' }).click()
  await shot(page, G, '09-tampilan-kisi')
  await page.getByRole('button', { name: 'Tampilan daftar' }).click()

  // BAPSI tidak boleh membuka menu prediksi.
  await page.goto('/prediksi')
  await expect(page).toHaveURL(/\/berkas$/)
  await logout(page)
})

test('03 admin cek format data dan preprocessing', async ({ page }) => {
  const G = '03-admin-format-preprocessing'
  await loginOk(page, ADMIN)

  await page.goto('/admin/format-data')
  await page.locator('input[type="file"]').setInputFiles(PMB_FILE)
  await page.getByRole('button', { name: /^Cek$/ }).click()
  await expect(page.getByText(/Sheet1/).first()).toBeVisible({ timeout: 30_000 })
  await shot(page, G, '01-cek-format-berkas-pmb')

  await page.goto('/admin/preprocessing')
  await expect(page.getByLabel('Pilih Berkas PMB')).toContainText('20260605_Data_PMB.xlsx')
  await page.locator('main select').filter({ hasText: 'Deteksi dari berkas' }).selectOption('Teknik Mesin')
  await shot(page, G, '02-form-preprocessing')
  await page.getByRole('button', { name: 'Proses & Gabungkan' }).click()
  await expect(page.getByText('Jumlah Mahasiswa')).toBeVisible({ timeout: 120_000 })
  await shot(page, G, '03-hasil-preprocessing')
  trainFile = await download(page, () => page.getByRole('button', { name: /Unduh/ }).click())
  await logout(page)
})

test('04 admin melatih model lalu mengaktifkannya', async ({ page }) => {
  test.setTimeout(15 * 60_000)
  test.skip(!trainFile, 'butuh berkas hasil preprocessing dari test 03')
  const G = '04-admin-master-model'
  await loginOk(page, ADMIN)
  await page.goto('/admin/model')
  const aktifTM = page.getByRole('row').filter({ hasText: 'Teknik Mesin' }).filter({ hasText: 'Model Aktif' })
  previousActive = (await aktifTM.locator('td').first().innerText()).trim()

  // Prodi tidak dipilih: dideteksi dari kolom Prodi berkas hasil preprocessing.
  await page.locator('input[type="file"]').setInputFiles(trainFile)
  await shot(page, G, '01-form-latih')
  await page.getByRole('button', { name: 'Latih Model' }).click()
  await shot(page, G, '02-sedang-melatih')
  await expect(page.getByText('Model Berhasil Dilatih')).toBeVisible({ timeout: 14 * 60_000 })
  await shot(page, G, '03-latih-berhasil')
  await page.getByRole('button', { name: 'Tutup', exact: true }).click()

  // Model terbaru Teknik Mesin ada di atas; aktifkan, lalu kembalikan model sebelumnya.
  const baru = page.getByRole('row').filter({ hasText: 'Teknik Mesin' }).filter({ has: page.getByRole('button', { name: /^Aktifkan model/ }) }).first()
  const namaBaru = (await baru.locator('td').first().innerText()).trim()
  await baru.getByRole('button', { name: /^Aktifkan model/ }).click()
  await expect(page.getByRole('row').filter({ hasText: namaBaru })).toContainText('Model Aktif')
  await shot(page, G, '04-model-baru-aktif')

  await page.getByRole('button', { name: `Aktifkan model ${previousActive}` }).click()
  await expect(page.getByRole('row').filter({ hasText: previousActive })).toContainText('Model Aktif')
  await shot(page, G, '05-model-lama-dipulihkan')
  await logout(page)
})

// Klik Jalankan Prediksi; gagal cepat dengan pesan dari aplikasi bila prediksi ditolak.
async function runPrediction(page) {
  await page.getByRole('button', { name: 'Jalankan Prediksi' }).click()
  const pesanError = page.locator('main p.bg-red-50, main p.text-red-500').first()
  const berhasil = await Promise.race([
    page.waitForURL(/\/results$/, { timeout: 180_000 }).then(() => true),
    pesanError.waitFor({ timeout: 180_000 }).then(() => false),
  ])
  if (!berhasil) throw new Error(`Prediksi ditolak: ${await pesanError.innerText()}`)
  await expect(page.getByRole('button', { name: 'Unduh Laporan' })).toBeVisible()
}

// Prediksi dari berkas BAPSI, lalu telusuri hasil sampai detail mata kuliah.
// Dropdown prodi di kartu prediksi; berkas PMB & akademik dipilih server (selalu terbaru).
const prodiSelect = (page) => page.locator('main select').filter({ hasText: '-- Pilih Program Studi --' })

async function predictFlow(page, request, account, G, { pilihProdi } = {}) {
  await page.goto('/prediksi')
  if (pilihProdi) await prodiSelect(page).selectOption(pilihProdi)
  await expect(page.getByText('Berkas PMB', { exact: true })).toBeVisible({ timeout: 120_000 })
  await expect(page.getByRole('button', { name: 'Jalankan Prediksi' })).toBeEnabled()
  await shot(page, G, '01-prediksi-siap')
  await runPrediction(page)
  await shot(page, G, '02-hasil-prediksi')
  await download(page, () => page.getByRole('button', { name: 'Unduh Laporan' }).click())

  const token = await apiToken(request, account)
  const { batches } = await (await request.get('/api/history', auth(token))).json()
  expect(batches.length).toBeGreaterThan(0)
  // Alamat yang sama dengan klik batang chart di Hasil Prediksi (tanpa from).
  await page.goto(`/batch/${batches[0].id}`)
  await expect(page.locator('a[href^="/detail/"]').first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Kembali ke Hasil Prediksi' })).toBeVisible()
  await shot(page, G, '03-detail-batch')
  await download(page, () => page.getByRole('button', { name: 'Unduh Laporan' }).click())

  await page.locator('a[href^="/detail/"]').first().click()
  await expect(page).toHaveURL(/\/detail\//)
  // Kembali dari detail mahasiswa membawa filter daftar yang sama.
  await expect(page.getByRole('link', { name: 'Kembali ke Daftar Mahasiswa' }))
    .toHaveAttribute('href', new RegExp(`/batch/${batches[0].id}\\?filter=sisip$`))
  await expect(page.getByRole('button', { name: /Unduh Profil/ })).toBeVisible()
  await shot(page, G, '04-detail-mahasiswa')
  await download(page, () => page.getByRole('button', { name: /Unduh Profil/ }).click())

  await page.locator('a[href^="/courses/"]').first().click()
  await expect(page).toHaveURL(/\/courses\//)
  await shot(page, G, '05-detail-mata-kuliah')
}

test('05 DPA memprediksi dari berkas', async ({ page, request }) => {
  test.setTimeout(6 * 60_000)
  await loginOk(page, cred(USERS.dpa))
  await expect(page).toHaveURL(/\/prediksi$/)
  // Alamat lama (dulu "Unggah Data") dialihkan ke halaman prediksi.
  await page.goto('/upload')
  await expect(page).toHaveURL(/\/prediksi$/)
  await predictFlow(page, request, cred(USERS.dpa), '05-dpa-prediksi')
  await logout(page)
})

test('06 Kaprodi memprediksi dari berkas', async ({ page, request }) => {
  test.setTimeout(6 * 60_000)
  await loginOk(page, cred(USERS.kaprodi))
  await predictFlow(page, request, cred(USERS.kaprodi), '06-kaprodi-prediksi')
  await logout(page)
})

test('07 Dekan memprediksi prodi pilihan', async ({ page, request }) => {
  test.setTimeout(6 * 60_000)
  const G = '07-dekan-prediksi'
  await loginOk(page, cred(USERS.dekan))

  // Temuan: model aktif Matematika dilatih dari format data lama, sehingga
  // ditolak untuk berkas BAPSI. Pastikan penolakannya tampil jelas ke pengguna.
  await prodiSelect(page).selectOption('Matematika')
  await expect(page.getByRole('button', { name: 'Jalankan Prediksi' })).toBeEnabled({ timeout: 120_000 })
  await page.getByRole('button', { name: 'Jalankan Prediksi' }).click()
  await expect(page.getByText(/Model aktif prodi Matematika tidak cocok/)).toBeVisible({ timeout: 120_000 })
  await shot(page, G, '00-matematika-model-tidak-cocok')

  await predictFlow(page, request, cred(USERS.dekan), G, { pilihProdi: 'Teknik Elektro' })
  await logout(page)
})

test('08 admin memprediksi dan meninjau log riwayat', async ({ page, request }) => {
  test.setTimeout(6 * 60_000)
  const G = '08-admin-prediksi-riwayat'
  await loginOk(page, ADMIN)
  await predictFlow(page, request, ADMIN, G, { pilihProdi: 'Teknik Mesin' })
  await page.goto('/history')
  await shot(page, G, '06-log-riwayat')
  await page.getByRole('link', { name: /^Tinjau batch/ }).first().click()
  await expect(page).toHaveURL(/\/batch\/\d+/)
  await shot(page, G, '07-tinjau-batch')
  await logout(page)
})

test('09 ringkasan: hapus folder sementara, lihat hasil yang disisakan', async ({ page }) => {
  const G = '09-ringkasan'
  await loginOk(page, cred(USERS.bapsi))
  const sementara = `${RUN} sementara`
  await page.getByRole('button', { name: 'Folder Baru' }).click()
  await page.getByRole('dialog').locator('input').fill(sementara)
  await page.getByRole('button', { name: 'Buat Folder' }).click()
  const row = page.getByRole('row', { name: new RegExp(sementara) })
  await row.getByRole('button', { name: 'Hapus folder' }).click()
  await shot(page, G, '01-konfirmasi-hapus-folder')
  await page.getByRole('button', { name: 'Ya, Hapus' }).click()
  await expect(row).toBeHidden()
  await expect(page.getByRole('row', { name: new RegExp(FOLDER) })).toBeVisible()
  await shot(page, G, '02-berkas-bapsi-tersisa')
  await logout(page)

  await loginOk(page, ADMIN)
  await page.goto('/admin/users')
  for (const u of Object.values(USERS)) await expect(page.getByRole('row', { name: new RegExp(u.name.replace(/[()]/g, '\\$&')) })).toBeVisible()
  await shot(page, G, '03-akun-uji-tersisa')
  await page.goto('/admin/model')
  await shot(page, G, '04-registri-model')
  await logout(page)
})

test.afterAll(async ({ request }) => {
  // Bila test gagal di tengah test 04, pastikan model aktif Teknik Mesin kembali seperti semula.
  if (previousActive) {
    const token = await apiToken(request, ADMIN)
    const models = await (await request.get('/api/models', auth(token))).json()
    const prev = models.find((m) => m.version_name === previousActive)
    if (prev && !prev.is_active) await request.post(`/api/models/${prev.id}/activate`, auth(token))
  }
})
