import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        // Dev only: forward API calls to the local Flask backend.
        // In production the frontend uses relative /api paths proxied by Nginx.
        '/api': {
          target: env.VITE_API_TARGET || 'http://localhost:5000',
          changeOrigin: true,
        },
      },
    },
  }
})
