import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./features/graph/VaultGraph3D', () => ({ default: () => <div>grafo 3D</div> }))

const VAULT = { nodes: [{ id: 'a', title: 'A', path: 'a.md', tags: [] }], links: [] }

// fetch falso que responde según la ruta: los tests nunca tocan la red.
function stubApi(routes: Record<string, Response | Error>) {
  const fetchMock = vi.fn((url: string) => {
    const response = routes[url]
    if (response instanceof Error) return Promise.reject(response)
    return Promise.resolve(response?.clone() ?? Response.json({ detail: 'no' }, { status: 404 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('App', () => {
  it('comprueba el backend con rutas relativas y carga la bóveda', async () => {
    const fetchMock = stubApi({
      '/api/health': Response.json({ status: 'ok' }),
      '/api/vault': Response.json(VAULT),
    })

    render(<App />)

    expect(await screen.findByText('Backend conectado')).toBeInTheDocument()
    expect(await screen.findByText('grafo 3D')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
    expect(fetchMock).toHaveBeenCalledWith('/api/vault', expect.anything())
  })

  it('muestra el backend no disponible si la petición falla', async () => {
    stubApi({ '/api/health': new TypeError('Failed to fetch'), '/api/vault': new TypeError('x') })

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })

  it('trata una respuesta HTTP de error como backend no disponible', async () => {
    stubApi({
      '/api/health': Response.json({ detail: 'boom' }, { status: 500 }),
      '/api/vault': Response.json(VAULT),
    })

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })
})
