import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { stubRoutes } from './test/fetchRoutes'

// jsdom no tiene WebGL: el lienzo del grafo se sustituye por un marcador.
vi.mock('./features/graph/ForceGraphView', () => ({ default: () => <div>grafo</div> }))

const EMPTY_PANELS = {
  'GET /api/vault': () => Response.json({ nodes: [], links: [] }),
  'GET /api/proposals?status=pending': () => Response.json([]),
  'GET /api/metrics': () =>
    Response.json({
      tasks: [],
      totals: { tasks: 0, cost_usd: 0, baseline_cost_usd: 0, savings_usd: 0, escalations: 0, slm_share: 0 },
    }),
}

// Los tests nunca tocan la red: cada ruta tiene una respuesta controlada.
function stubHealth(health: () => Response | Promise<Response>) {
  return stubRoutes({ ...EMPTY_PANELS, 'GET /api/health': health })
}

describe('App', () => {
  it('pide /api/health con una ruta relativa y muestra el backend conectado', async () => {
    const fetchMock = stubHealth(() => Response.json({ status: 'ok' }))

    render(<App />)

    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Comprobando backend')
    expect(await screen.findByText('Backend conectado')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('muestra el backend no disponible si la petición falla', async () => {
    stubHealth(() => Promise.reject(new TypeError('Failed to fetch')))

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })

  it('trata una respuesta HTTP de error como backend no disponible', async () => {
    stubHealth(() => Response.json({ detail: 'boom' }, { status: 500 }))

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })

  it('muestra las cuatro secciones', async () => {
    stubHealth(() => Response.json({ status: 'ok' }))

    render(<App />)

    for (const name of ['Investigación', 'Tu bóveda', 'Notas por revisar', 'SmartRoute']) {
      expect(await screen.findByRole('heading', { name })).toBeInTheDocument()
    }
  })
})
