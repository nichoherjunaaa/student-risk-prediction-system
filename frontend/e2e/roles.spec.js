import { test, expect } from '@playwright/test'
import { ADMIN, shot as saveShot, apiToken, auth } from './helpers'

// Akun demo dari backend/sisip/db.py (DEMO_USERS). Dekan tidak ikut di-seed,
// jadi test membuat akun dekan uji lewat API (sekali saja, tidak dihapus).
const DEKAN = { nip: '910000000000000009', password: 'E2eDekan#2026', name: 'E2E Dekan' }
const ROLES = [
  {
    role: 'admin',
    nip: '900000000000000001',
    password: 'Admin#2026',
    home: '/admin/model',
    pages: [
      ['/admin/format-data', 'format-data'],
      ['/admin/preprocessing', 'preprocessing'],
      ['/admin/model', 'master-model'],
      ['/prediksi', 'buat-prediksi'],
      ['/results', 'hasil-prediksi'],
      ['/berkas', 'berkas-mahasiswa'],
      ['/admin/users', 'master-pengguna'],
      ['/admin/users/new', 'tambah-pengguna'],
      ['/history', 'log-riwayat'],
    ],
    forbidden: [],
  },
  {
    role: 'dpa',
    nip: '900000000000000002',
    password: 'Dpa#2026',
    home: '/prediksi',
    pages: [
      ['/prediksi', 'buat-prediksi'],
      ['/results', 'hasil-prediksi'],
      ['/berkas', 'berkas-mahasiswa'],
    ],
    forbidden: ['/admin/users', '/admin/model', '/history'],
  },
  {
    role: 'kaprodi',
    nip: '900000000000000003',
    password: 'Kaprodi#2026',
    home: '/prediksi',
    pages: [
      ['/prediksi', 'buat-prediksi'],
      ['/results', 'hasil-prediksi'],
      ['/berkas', 'berkas-mahasiswa'],
    ],
    forbidden: ['/admin/users', '/admin/preprocessing', '/history'],
  },
  {
    role: 'dekan',
    nip: DEKAN.nip,
    password: DEKAN.password,
    home: '/prediksi',
    pages: [
      ['/prediksi', 'buat-prediksi'],
      ['/results', 'hasil-prediksi'],
      ['/berkas', 'berkas-mahasiswa'],
    ],
    forbidden: ['/admin/users', '/admin/format-data', '/history'],
  },
  {
    role: 'bapsi',
    nip: '900000000000000004',
    password: 'Bapsi#2026',
    home: '/berkas',
    pages: [['/berkas', 'berkas-mahasiswa']],
    forbidden: ['/prediksi', '/results', '/admin/users', '/admin/model'],
  },
]

const shot = (page, role, name) => saveShot(page, `00-peran/${role}`, name)

// Akun dekan uji dibuat sekali bila belum ada, lalu disisakan.
test.beforeAll(async ({ request }) => {
  const token = await apiToken(request, ADMIN)
  const users = await (await request.get('/api/users', auth(token))).json()
  if (users.some((u) => u.nip === DEKAN.nip)) return
  const res = await request.post('/api/users', {
    ...auth(token),
    data: { nip: DEKAN.nip, password: DEKAN.password, name: DEKAN.name, role: 'dekan', prodi: '' },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
})

async function login(page, { nip, password }) {
  await page.goto('/login')
  await page.locator('#nip').fill(nip)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: /masuk/i }).click()
}

test('login gagal dengan password salah', async ({ page }) => {
  await login(page, { nip: '900000000000000001', password: 'salah-total' })
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByText(/salah/i).first()).toBeVisible()
  await shot(page, 'umum', '01-login-gagal')
})

test('route terlindungi tanpa login dialihkan ke /login', async ({ page }) => {
  await page.goto('/admin/users')
  await expect(page).toHaveURL(/\/login$/)
  await shot(page, 'umum', '02-redirect-tanpa-login')
  await page.goto('/halaman-tidak-ada')
  await expect(page.getByText('404')).toBeVisible()
  await shot(page, 'umum', '03-not-found')
})

for (const acc of ROLES) {
  test.describe(`role ${acc.role}`, () => {
    test('login, buka semua halaman yang diizinkan, cek larangan, logout', async ({ page, request }) => {
      // Halaman Buat Prediksi memeriksa berkas BAPSI di server; untuk prodi yang tidak
      // ada di berkas, pemeriksaan itu bisa ~30 detik per kunjungan.
      test.setTimeout(4 * 60_000)
      const pageErrors = []
      page.on('pageerror', (err) => pageErrors.push(err.message))

      await page.goto('/login')
      await shot(page, acc.role, '00-login')

      await login(page, acc)
      await expect(page).toHaveURL(new RegExp(`${acc.home}$`))
      await expect(page.getByText('Keluar Sistem')).toBeVisible()
      await shot(page, acc.role, '01-beranda')

      let n = 2
      for (const [url, name] of acc.pages) {
        await page.goto(url)
        await expect(page).toHaveURL(new RegExp(`${url}$`))
        await shot(page, acc.role, `${String(n++).padStart(2, '0')}-${name}`)
      }

      // Halaman detail (batch -> mahasiswa -> mata kuliah) memakai batch milik akun ini.
      if (acc.role !== 'bapsi') {
        const res = await request.post('/api/login', { data: { nip: acc.nip, password: acc.password } })
        const { token } = await res.json()
        const hist = await request.get('/api/history', { headers: { Authorization: `Bearer ${token}` } })
        const batches = hist.ok() ? (await hist.json()).batches : []
        if (batches.length) {
          await page.goto(`/batch/${batches[0].id}`)
          await shot(page, acc.role, `${String(n++).padStart(2, '0')}-detail-batch`)
          const detail = page.locator('a[href^="/detail/"]').first()
          if (await detail.count()) {
            await detail.click()
            await expect(page).toHaveURL(/\/detail\//)
            await shot(page, acc.role, `${String(n++).padStart(2, '0')}-detail-mahasiswa`)
            const courses = page.locator('a[href^="/courses/"]').first()
            if (await courses.count()) {
              await courses.click()
              await expect(page).toHaveURL(/\/courses\//)
              await shot(page, acc.role, `${String(n++).padStart(2, '0')}-detail-mata-kuliah`)
            }
          }
        } else {
          test.info().annotations.push({ type: 'info', description: 'Akun belum punya batch prediksi; halaman detail dilewati.' })
        }
      }

      for (const url of acc.forbidden) {
        await page.goto(url)
        await expect(page).toHaveURL(new RegExp(`${acc.home}$`))
      }
      if (acc.forbidden.length) await shot(page, acc.role, `${String(n++).padStart(2, '0')}-akses-ditolak-dialihkan`)

      await page.getByText('Keluar Sistem').click()
      await expect(page).toHaveURL(/\/login$/)
      await shot(page, acc.role, `${String(n++).padStart(2, '0')}-logout`)

      expect(pageErrors, `JS error di halaman: ${pageErrors.join('\n')}`).toEqual([])
    })
  })
}
