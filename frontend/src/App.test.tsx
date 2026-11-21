import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

// Sustituye fetch por una respuesta controlada: los tests nunca tocan la red.
function stubFetch(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('App', () => {
  it('pide /api/health con una ruta relativa y muestra el backend conectado', async () => {
    const fetchMock = stubFetch(Response.json({ status: 'ok' }))

    render(<App />)

    expect(screen.getByRole('status')).toHaveTextContent('Comprobando backend')
    expect(await screen.findByText('Backend conectado')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('muestra el backend no disponible si la petición falla', async () => {
    stubFetch(new TypeError('Failed to fetch'))

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })

  it('trata una respuesta HTTP de error como backend no disponible', async () => {
    stubFetch(Response.json({ detail: 'boom' }, { status: 500 }))

    render(<App />)

    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })
})
