import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Metrics } from '../../api/contract.gen'
import { stubRoutes } from '../../test/fetchRoutes'
import RouterPanel from './RouterPanel'

const task = (overrides: Partial<Metrics['tasks'][number]>): Metrics['tasks'][number] => ({
  run_id: 'run-1',
  agent: 'researcher',
  task: 'summarize_paper',
  model: 'qwen/qwen-2.5-7b-instruct',
  tier: 'slm',
  prompt_tokens: 1000,
  completion_tokens: 200,
  cost_usd: 0.00014,
  latency_ms: 850,
  escalated: false,
  ...overrides,
})

const METRICS: Metrics = {
  tasks: [
    task({}),
    task({ agent: 'writer', task: 'write_note', model: 'qwen/qwen-2.5-72b-instruct', tier: 'large', cost_usd: 0.0004, latency_ms: 4200 }),
    task({ agent: 'reviewer', task: 'verify_claims', model: 'qwen/qwen-2.5-72b-instruct', tier: 'large', escalated: true }),
  ],
  totals: { tasks: 3, cost_usd: 0.0007, baseline_cost_usd: 0.001, savings_usd: 0.0003, escalations: 1, slm_share: 1 / 3 },
}

const EMPTY: Metrics = {
  tasks: [],
  totals: { tasks: 0, cost_usd: 0, baseline_cost_usd: 0, savings_usd: 0, escalations: 0, slm_share: 0 },
}

describe('RouterPanel (HU4)', () => {
  it('muestra ahorro, costes y el modelo de cada tarea de la investigación', async () => {
    stubRoutes({ 'GET /api/metrics?run_id=run-1': () => Response.json(METRICS) })

    render(<RouterPanel runId="run-1" />)

    const saving = (await screen.findByText('Ahorro')).closest('div') as HTMLElement
    expect(within(saving).getByText(/30 %/)).toBeInTheDocument()
    expect(screen.getByText('Tareas con SLM').closest('div')).toHaveTextContent('33 %')
    expect(screen.getByText(/1 escalada/)).toBeInTheDocument()

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Investigador')
    expect(rows[0]).toHaveTextContent('SLM')
    expect(rows[1]).toHaveTextContent('Grande')
    expect(rows[1]).toHaveTextContent('qwen-2.5-72b-instruct')
    expect(rows[1]).toHaveTextContent('4,2 s')
    expect(rows[2]).toHaveTextContent('escalada')
  })

  it('cambia entre esta investigación y todas', async () => {
    const fetchMock = stubRoutes({
      'GET /api/metrics?run_id=run-1': () => Response.json(METRICS),
      'GET /api/metrics': () => Response.json(EMPTY),
    })

    render(<RouterPanel runId="run-1" />)
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: 'Todas' }))

    expect(await screen.findByText(/Aún no hay tareas/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/metrics', expect.anything())
  })

  it('sin investigación muestra todas y desactiva «Esta investigación»', async () => {
    stubRoutes({ 'GET /api/metrics': () => Response.json(EMPTY) })

    render(<RouterPanel />)

    expect(await screen.findByText(/Aún no hay tareas/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Esta investigación' })).toBeDisabled()
  })

  it('muestra el error si el backend falla', async () => {
    stubRoutes({ 'GET /api/metrics': () => Response.json({ detail: 'boom' }, { status: 500 }) })

    render(<RouterPanel />)

    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})
