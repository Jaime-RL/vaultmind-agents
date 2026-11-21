/// <reference types="vite/client" />

// Variables de entorno que el frontend lee en tiempo de build (documentadas en .env.example).
interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_USE_MOCKS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
