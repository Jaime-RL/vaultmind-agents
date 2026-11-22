import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Metrics, RouteDecision } from '../../api/contract.gen'
import { loadRunExample } from '../../test/fixtures'
import { LiveSavings } from './LiveSavings'
import { routeCounts, savingsShare } from './routeCounts'

const decisions = loadRunExample().filter((e): e is RouteDecision => e.type === 'route_decision')

const metrics = (cost: number, baseline: number): { status: 'ready'; metrics: Metrics } => ({
  status: 'ready',
  metrics: {
    tasks: [],
    totals: {
      tasks: 1,
      cost_usd: cost,
      baseline_cost_usd: baseline,
      savings_usd: baseline - cost,
      escalations: 0,
      slm_share: 0.5,
    },
  },
})

describe('routeCounts', () => {
  it('cuenta las llamadas de cada modelo y las escaladas del fixture', () => {
    const counts = routeCounts(decisions)

    expect(counts.slm + counts.large).toBe(decisions.length)
    expect(counts.escalations).toBe(decisions.filter((d) => d.escalated).length)
    expect(counts.escalations).toBeGreaterThan(0) // la demo enseña al menos una escalada
  })

  it('calcula el ahorro relativo y nunca lo deja negativo', () => {
    expect(savingsShare(0.6, 1)).toBeCloseTo(0.4)
    expect(savingsShare(2, 1)).toBe(0)
    expect(savingsShare(0, 0)).toBeNull()
  })
})

describe('LiveSavings', () => {
  it('no se muestra antes de la primera decisión del router', () => {
    const { container } = render(
      <LiveSavings decisions={[]} metrics={{ status: 'loading' }} running />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra el reparto de modelos, el ahorro y la última decisión', () => {
    render(<LiveSavings decisions={decisions} metrics={metrics(0.0063, 0.01)} running />)

    const panel = screen.getByRole('complementary', {
      name: 'SmartRoute en directo',
    })
    const { slm, large } = routeCounts(decisions)
    expect(panel).toHaveTextContent(`${slm} SLM`)
    expect(panel).toHaveTextContent(`${large} grande`)
    expect(panel).toHaveTextContent('37 % ahorro')
    expect(panel).toHaveTextContent(`${decisions.at(-1)!.task} →`)
  })

  it('al terminar deja de mostrar la última decisión', () => {
    render(<LiveSavings decisions={decisions} metrics={metrics(0.5, 1)} running={false} />)

    expect(screen.queryByText(/→/)).not.toBeInTheDocument()
  })
})
