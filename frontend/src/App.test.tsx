import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import type { GraphData } from './features/graph/graphData'
import { FakeEventSource, installFakeEventSource } from './test/fakeEventSource'
import { loadDemoProposals, loadRunExample } from './test/fixtures'

// El grafo 3D se sustituye por una lista con los nodos que recibiría (jsdom no tiene WebGL).
vi.mock('./features/graph/VaultGraph3D', () => ({
  default: ({ data }: { data: GraphData }) => (
    <ul aria-label="grafo 3D">
      {data.nodes.map((node) => (
        <li key={node.id}>{node.title}</li>
      ))}
    </ul>
  ),
}))

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
    expect(await screen.findByRole('list', { name: 'grafo 3D' })).toBeInTheDocument()
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

describe('App: investigación en directo (HU2)', () => {
  it('lanza la investigación, muestra a los agentes y añade las notas propuestas al grafo', async () => {
    installFakeEventSource()
    const events = loadRunExample()
    const fetchMock = stubApi({
      '/api/health': Response.json({ status: 'ok' }),
      '/api/vault': Response.json(VAULT),
      '/api/research': Response.json({ run_id: events[0]!.run_id }),
    })
    render(<App />)
    await screen.findByRole('list', { name: 'grafo 3D' })

    await userEvent.type(screen.getByLabelText('Tema a investigar'), 'SLMs con tool calling')
    await userEvent.click(screen.getByRole('button', { name: 'Investigar' }))

    // POST con el tema del formulario y suscripción al SSE de ese run_id.
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research',
      expect.objectContaining({
        method: 'POST',
        // Sin proveedor de idioma, la interfaz va en español y las notas en «auto».
        body: JSON.stringify({ topic: 'SLMs con tool calling', language: 'auto', ui_language: 'es' }),
      }),
    )
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))
    expect(FakeEventSource.last().url).toBe(`/api/research/${events[0]!.run_id}/events`)
    expect(screen.getByRole('button', { name: 'Investigando…' })).toBeDisabled()

    act(() => {
      for (const event of events) FakeEventSource.last().emit(event)
    })

    const graph = screen.getByRole('list', { name: 'grafo 3D' })
    expect(within(graph).getByText('Function calling en SLMs')).toBeInTheDocument()
    expect(within(graph).getByText('Routing de modelos')).toBeInTheDocument()
    expect(within(graph).getByText('LoRA')).toBeInTheDocument()
    expect(within(screen.getByRole('log')).getAllByRole('listitem')).toHaveLength(events.length)
    expect(screen.getByRole('button', { name: 'Investigar' })).toBeEnabled()
  })

  it('explica el error si hay demasiadas investigaciones en marcha (429)', async () => {
    installFakeEventSource()
    stubApi({
      '/api/health': Response.json({ status: 'ok' }),
      '/api/vault': Response.json(VAULT),
      '/api/research': Response.json({ detail: 'demasiadas' }, { status: 429 }),
    })
    render(<App />)

    await userEvent.type(screen.getByLabelText('Tema a investigar'), 'Un tema')
    await userEvent.click(screen.getByRole('button', { name: 'Investigar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('demasiadas investigaciones en marcha')
    expect(FakeEventSource.instances).toHaveLength(0)
  })
})

describe('App: revisión de notas (HU3)', () => {
  it('aprueba una nota: la guarda vía API, la quita de pendientes y recarga la bóveda', async () => {
    installFakeEventSource()
    const [first, ...rest] = loadDemoProposals()
    const fetchMock = stubApi({
      '/api/health': Response.json({ status: 'ok' }),
      '/api/vault': Response.json(VAULT),
      '/api/proposals?status=pending': Response.json([first, ...rest]),
      [`/api/proposals/${first!.id}`]: Response.json({ ...first, status: 'approved' }),
    })
    render(<App />)

    const tab = await screen.findByRole('tab', { name: `Notas${rest.length + 1}` })
    await userEvent.click(tab)
    await userEvent.click(screen.getByRole('button', { name: 'Aprobar' }))

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/proposals/${first!.id}`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'approve' }) }),
    )
    await vi.waitFor(() =>
      expect(screen.getByRole('tab', { name: `Notas${rest.length}` })).toBeInTheDocument(),
    )
    // La bóveda se pide otra vez para que el grafo muestre la nota ya guardada en _copilot/.
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/vault')).toHaveLength(2)
  })
})
