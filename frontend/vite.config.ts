import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '')
  const marketLens = mode === 'marketlens'
  const proxyTarget = marketLens
    ? env.MARKETLENS_API_PROXY_TARGET || 'http://127.0.0.1:8010'
    : env.API_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss(), marketLens && {
      name: 'marketlens-title',
      transformIndexHtml: html => html.replace('<title>SAQ QURYLYS</title>', '<title>MarketLens</title>'),
    }],
    envPrefix: marketLens ? 'VITE_MARKETLENS_' : 'VITE_',
    envDir: '..',
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
      },
    },
    test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], restoreMocks: true, testTimeout: 15000 },
  }
})
