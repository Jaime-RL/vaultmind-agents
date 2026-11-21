import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Metrics } from '../../api/contract.gen'
import { RouterPanel } from './RouterPanel'

const metrics: Metrics = {
  tasks: [
    {
      run_id: 'r1', agent: 'explorer', task: 'find_gaps', model: 'qwen/qwen-2.5-7b-instruct', tier: 'slm',
      prompt_tokens: 900, completion_tokens: 300, cost_usd: 0.00015, latency_ms: 1800, escalated: false,
    },
    {
      run_id: 'r1', agent: 'researcher', task: 'summarize_paper', model: 'qwen/qwen-2.5-72b-instruct', tier: 'large',
      prompt_tokens: 2000, completion_tokens: 500, cost_usd: 0.00092, latency_ms: 4200, escalated: true,
    },
  ],
  totals: {
    tasks: 2, cost_usd: 0.00107, baseline_cost_usd: 0.002, savings_usd: 0.00093, escalations: 1, slm_share: 0.5,
  },
}

describe('RouterPanel', () => {
  it('muestra el ahorro total, el reparto SLM y las escaladas (criterio de HU4)', () => {
    render(<RouterPanel state={{ status: 'ready', metrics }} scope="run" hasRun onScopeChange={vi.fn()} />)

    const summary = screen.getByRole('region', { name: 'Resumen' })
    expect(within(summary).getByText('$0.0009')).toBeInTheDocument()
    expect(within(summary).getByText('47 % menos')).toBeInTheDocument()
    expect(within(summary).getByText('50 %')).toBeInTheDocument()
    expect(within(summary).getByText('1')).toBeInTheDocument()
  })

  it('compara el coste real con el de usar solo el modelo grande, con los valores escritos', () => {
    render(<RouterPanel state={{ status: 'ready', metrics }} scope="run" hasRun onScopeChange={vi.fn()} />)

    const figure = screen.getByRole('figure', { name: 'Coste total' })
    expect(within(figure).getByText('$0.0011')).toBeInTheDocument()
    expect(within(figure).getByText('$0.0020')).toBeInTheDocument()
  })

  it('lista modelo, coste y escalada de cada tarea en una tabla', () => {
    render(<RouterPanel state={{ status: 'ready', metrics }} scope="run" hasRun onScopeChange={vi.fn()} />)

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Explorador')
    expect(rows[0]).toHaveTextContent('SLM')
    expect(rows[1]).toHaveTextContent('Grande')
    expect(rows[1]).toHaveTextContent('qwen-2.5-72b')
    expect(rows[1]).toHaveTextContent('escalada')
    // Norma española: sin separador de miles en números de cuatro cifras.
    expect(rows[1]).toHaveTextContent('2500')
  })

  it('cambia entre esta investigación y todas', async () => {
    const onScopeChange = vi.fn()
    render(<RouterPanel state={{ status: 'ready', metrics }} scope="run" hasRun onScopeChange={onScopeChange} />)

    expect(screen.getByRole('button', { name: 'Esta investigación' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Todas' }))
    expect(onScopeChange).toHaveBeenCalledWith('all')
  })

  it('no deja elegir «esta investigación» si no hay ninguna', () => {
    render(<RouterPanel state={{ status: 'ready', metrics }} scope="all" hasRun={false} onScopeChange={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Esta investigación' })).toBeDisabled()
  })

  it('muestra los estados vacío, de carga y de error', () => {
    const empty = { tasks: [], totals: { ...metrics.totals, tasks: 0 } }
    const { rerender } = render(<RouterPanel state={{ status: 'ready', metrics: empty }} scope="all" hasRun={false} onScopeChange={vi.fn()} />)
    expect(screen.getByText(/Aún no hay tareas/)).toBeInTheDocument()

    rerender(<RouterPanel state={{ status: 'loading' }} scope="all" hasRun={false} onScopeChange={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Cargando métricas')

    rerender(<RouterPanel state={{ status: 'error', message: 'boom' }} scope="all" hasRun={false} onScopeChange={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('boom')
  })
})
