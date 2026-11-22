import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { loadRunExample } from '../../test/fixtures'
import { AgentsPanel } from './AgentsPanel'
import { initialRunState, runReducer, type RunState } from './runReducer'

const events = loadRunExample()

function replayed(count = events.length): RunState {
  let state = runReducer(initialRunState, { type: 'start', topic: 'SLMs con tool calling' })
  state = runReducer(state, { type: 'started', runId: events[0]!.run_id })
  for (const event of events.slice(0, count)) state = runReducer(state, { type: 'event', event })
  return state
}

describe('AgentsPanel', () => {
  it('invita a lanzar una investigación cuando no hay ninguna', () => {
    render(<AgentsPanel state={initialRunState} onReconnect={vi.fn()} />)

    expect(screen.getByText(/Escribe un tema arriba/)).toBeInTheDocument()
  })

  it('la bienvenida explica los agentes y lanza un tema de ejemplo en un clic', async () => {
    const onExample = vi.fn()
    render(<AgentsPanel state={initialRunState} onReconnect={vi.fn()} onExample={onExample} />)

    expect(screen.getByText('Revisor')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'multi-token prediction' }))

    expect(onExample).toHaveBeenCalledWith('multi-token prediction')
  })

  it('pinta una línea por evento del fixture (flujo SSE en la UI)', () => {
    render(<AgentsPanel state={replayed()} onReconnect={vi.fn()} />)

    const log = screen.getByRole('log', { name: 'Razonamiento de los agentes' })
    expect(within(log).getAllByRole('listitem')).toHaveLength(events.length)
  })

  it('traduce las herramientas, las decisiones del router y las notas propuestas', () => {
    render(<AgentsPanel state={replayed()} onReconnect={vi.fn()} />)
    const log = screen.getByRole('log')

    expect(within(log).getByText('Buscando en arXiv: «function calling small language models»')).toBeInTheDocument()
    expect(within(log).getAllByText(/SLM$/).length).toBeGreaterThan(0)
    expect(within(log).getAllByText(/Modelo grande$/).length).toBeGreaterThan(0)
    expect(within(log).getByText('· escalado')).toBeInTheDocument()
    expect(within(log).getByText('Function calling en SLMs')).toBeInTheDocument()
    expect(within(log).getByText('Investigación terminada')).toBeInTheDocument()
  })

  it('muestra que los agentes trabajan mientras la investigación sigue abierta', () => {
    render(<AgentsPanel state={replayed(10)} onReconnect={vi.fn()} />)

    expect(screen.getByText('Los agentes están trabajando…')).toBeInTheDocument()
  })

  it('ofrece reconectar solo si se perdió la conexión', async () => {
    const onReconnect = vi.fn()
    const disconnected = runReducer(replayed(10), { type: 'disconnected' })
    const { rerender } = render(<AgentsPanel state={disconnected} onReconnect={onReconnect} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Se perdió la conexión')
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }))
    expect(onReconnect).toHaveBeenCalledOnce()

    rerender(<AgentsPanel state={runReducer(replayed(10), { type: 'failed', message: 'Sin saldo' })} onReconnect={onReconnect} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Sin saldo')
    expect(screen.queryByRole('button', { name: 'Reconectar' })).not.toBeInTheDocument()
  })
})
