import { vi } from 'vitest'

type Handler = (init?: RequestInit) => Response | Promise<Response>

/**
 * Sustituye fetch por un router en memoria: cada clave es «MÉTODO /ruta?query».
 * Una petición sin ruta definida falla el test con un mensaje claro.
 */
export function stubRoutes(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const key = `${(init?.method ?? 'GET').toUpperCase()} ${url}`
    const handler = routes[key]
    if (!handler) throw new Error(`Petición no prevista en el test: ${key}`)
    return handler(init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
