/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.VITE_BACKEND_URL || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      // Same-origin proxy: the httpOnly refresh cookie and WebSocket Origin check just work.
      proxy: {
        '/api': { target: backend, changeOrigin: false },
        '/ws': { target: backend.replace(/^http/, 'ws'), ws: true, changeOrigin: false },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
