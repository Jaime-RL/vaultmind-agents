// Se ejecuta antes de cada fichero de test (ver `test.setupFiles` en vite.config.ts).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  // Ningún test llama a la red: los que necesitan fetch lo sustituyen con vi.stubGlobal.
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
