/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo el navegador habla SOLO con Vite (puerto 5173) y Vite reenvía
// /api al backend. Así el frontend siempre usa rutas relativas (/api/...), igual
// que en producción, donde FastAPI sirve el frontend compilado desde el mismo
// origen: sin CORS y sin una URL distinta por entorno.
//
// VITE_PROXY_TARGET es una variable del servidor de Vite (no llega al navegador):
// - en local sin Docker: http://localhost:8000 (valor por defecto)
// - en docker compose: http://backend:8000 (nombre del servicio en la red de compose)
const proxyTarget = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  build: {
    // El trozo del grafo 3D (three.js) pesa ~1,5 MB, pero se carga aparte y solo
    // cuando hay grafo que pintar (React.lazy). La pantalla inicial no lo espera.
    chunkSizeWarningLimit: 1600,
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
    },
    // Con la carpeta montada como volumen desde Windows o macOS, los eventos de
    // fichero no siempre llegan al contenedor: VITE_USE_POLLING=true los sondea.
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : {},
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
