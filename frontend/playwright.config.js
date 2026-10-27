import { defineConfig, devices } from '@playwright/test'

// E2E UI per role. Jalankan terhadap stack yang sudah menyala (Vite + backend):
//   E2E_BASE_URL=http://localhost:5173 npx playwright test
// Sebaiknya backend memakai SALINAN database (SISIP_DB_FILE) agar data asli aman.
export default defineConfig({
  testDir: './e2e',
  outputDir: './e2e/test-results',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [['list'], ['html', { outputFolder: 'e2e/report', open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
})
