import { expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
// Screenshot disimpan di luar folder frontend: <repo>/e2e-screenshots/<grup>/<nama>.png
export const SHOT_DIR = process.env.E2E_SHOT_DIR || path.join(ROOT, 'e2e-screenshots')
export const DOWNLOAD_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), 'test-results', 'downloads')

export const ADMIN = { nip: '900000000000000001', password: 'Admin#2026' }

export async function shot(page, group, name) {
  await page.waitForLoadState('networkidle')
  // Tunggu animasi Chart.js selesai supaya batang grafik ikut tertangkap.
  if (await page.locator('canvas').count()) await page.waitForTimeout(1500)
  fs.mkdirSync(path.join(SHOT_DIR, group), { recursive: true })
  await page.screenshot({ path: path.join(SHOT_DIR, group, `${name}.png`), fullPage: true })
}

export async function login(page, { nip, password }) {
  await page.goto('/login')
  await page.locator('#nip').fill(nip)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: /^masuk$/i }).click()
}

// Login yang harus berhasil: tunggu token tersimpan dan halaman beranda terbuka
// sebelum navigasi berikutnya, supaya permintaan login tidak ikut dibatalkan.
export async function loginOk(page, account) {
  await login(page, account)
  await expect(page).not.toHaveURL(/\/login$/)
}

export async function logout(page) {
  await page.getByText('Keluar Sistem').click()
  await expect(page).toHaveURL(/\/login$/)
}

export async function apiToken(request, { nip, password }) {
  const res = await request.post('/api/login', { data: { nip, password } })
  expect(res.ok(), `login API ${nip}`).toBeTruthy()
  return (await res.json()).token
}

export const auth = (token) => ({ headers: { Authorization: `Bearer ${token}` } })

// Simpan unduhan yang dipicu `trigger` dan kembalikan path berkasnya.
export async function download(page, trigger) {
  const [dl] = await Promise.all([page.waitForEvent('download'), trigger()])
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true })
  const target = path.join(DOWNLOAD_DIR, dl.suggestedFilename())
  await dl.saveAs(target)
  expect(fs.statSync(target).size).toBeGreaterThan(0)
  return target
}
