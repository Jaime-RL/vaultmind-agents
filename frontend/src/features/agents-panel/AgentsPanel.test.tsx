import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FakeEventSource } from '../../test/FakeEventSource'
import { stubRoutes } from '../../test/fetchRoutes'
import AgentsPanel from './AgentsPanel'
import { useResearch } from './useResearch'

const base = { run_id: 'run-1', ts: '2026-11-21T10:00:00Z' }

function Harness() {
  return <AgentsPanel research={useResearch()} />
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

async function launch(topic = 'SLMs para clima') {
  const input = screen.getByLabelText('Tema a investigar')
  await userEvent.clear(input)
  await userEvent.type(input, topic)
  await userEvent.click(screen.getByRole('button', { name: 'Investigar' }))
}

describe('AgentsPanel (HU2)', () => {
  it('lanza la investigación y muestra los eventos en directo', async () => {
    const fetchMock = stubRoutes({ 'POST /api/research': () => Response.json({ run_id: 'run-1' }) })
    render(<Harness />)

    await launch()

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ topic: 'SLMs para clima' })
    const source = FakeEventSource.last()
    expect(source.url).toBe('/api/research/run-1/events')
    expect(screen.getByRole('button', { name: 'Investigando…' })).toBeDisabled()

    act(() => {
      source.open()
      source.emit({ ...base, type: 'agent_thought', agent: 'explorer', text: 'Busco lagunas' })
      source.emit({ ...base, type: 'tool_call', agent: 'researcher', tool: 'search_arxiv', args: { query: 'LoRA' } })
      source.emit({
        ...base,
        type: 'route_decision',
        agent: 'researcher',
        task: 'summarize_paper',
        model: 'qwen/qwen-2.5-72b-instruct',
        tier: 'large',
        reason: 'el modelo pequeño falló',
        escalated: true,
      })
      source.emit({ ...base, type: 'node_proposed', agent: 'writer', proposal_id: 'p-1', title: 'LoRA', links: [] })
    })

    const items = within(screen.getByRole('list', { name: 'Eventos de la investigación' })).getAllByRole('listitem')
    expect(items).toHaveLength(4)
    expect(items[0]).toHaveTextContent('Explorador')
    expect(items[0]).toHaveTextContent('Busco lagunas')
    expect(items[1]).toHaveTextContent('search_arxiv({"query":"LoRA"})')
    expect(items[2]).toHaveTextContent('Grande')
    expect(items[2]).toHaveTextContent('qwen-2.5-72b-instruct (escalada)')
    expect(items[3]).toHaveTextContent('Nota propuesta: «LoRA»')
  })

  it('al terminar muestra el resumen y cierra la conexión', async () => {
    stubRoutes({ 'POST /api/research': () => Response.json({ run_id: 'run-1' }) })
    render(<Harness />)
    await launch()
    const source = FakeEventSource.last()

    act(() =>
      source.emit({
        ...base,
        type: 'run_finished',
        agent: 'system',
        stats: { notes_proposed: 3, cost_usd: 0.007, baseline_cost_usd: 0.01, savings_usd: 0.003, escalations: 1, duration_s: 60 },
      }),
    )

    expect(screen.getByRole('status')).toHaveTextContent('3 notas propuestas')
    expect(screen.getByRole('status')).toHaveTextContent('ahorro 30 %')
    expect(source.closed).toBe(true)
    expect(screen.getByRole('button', { name: 'Investigar' })).toBeEnabled()
  })

  it('muestra los errores del backend (sin clave → 503, límite → 429)', async () => {
    stubRoutes({
      'POST /api/research': () =>
        Response.json({ detail: 'Ya hay 3 investigaciones en curso' }, { status: 429 }),
    })
    render(<Harness />)

    await launch()

    expect(await screen.findByRole('alert')).toHaveTextContent('Ya hay 3 investigaciones en curso')
    expect(FakeEventSource.instances).toHaveLength(0)
  })

  it('muestra el evento de error y cierra la conexión', async () => {
    stubRoutes({ 'POST /api/research': () => Response.json({ run_id: 'run-1' }) })
    render(<Harness />)
    await launch()
    const source = FakeEventSource.last()

    act(() => source.emit({ ...base, type: 'error', agent: 'system', message: 'La investigación se detuvo' }))

    expect(screen.getByRole('alert')).toHaveTextContent('La investigación se detuvo')
    expect(source.closed).toBe(true)
  })

  it('al reconectar no duplica los eventos (el backend los repite desde el principio)', async () => {
    stubRoutes({ 'POST /api/research': () => Response.json({ run_id: 'run-1' }) })
    render(<Harness />)
    await launch()
    const source = FakeEventSource.last()
    const thought = { ...base, type: 'agent_thought', agent: 'explorer', text: 'Busco lagunas' }

    act(() => {
      source.open()
      source.emit(thought)
      source.open() // reconexión automática
      source.emit(thought)
    })

    expect(within(screen.getByRole('list', { name: 'Eventos de la investigación' })).getAllByRole('listitem')).toHaveLength(1)
  })
})
