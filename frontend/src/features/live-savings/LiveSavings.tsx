import type { RouteDecision } from '../../api/contract.gen'
import { formatUsd } from '../agents-panel/describeEvent'
import type { MetricsState } from '../router-panel/useMetrics'
import { routeCounts, savingsShare } from './routeCounts'

interface Props {
  decisions: RouteDecision[]
  /** Métricas de ESTA investigación (se recargan con cada decisión del router). */
  metrics: MetricsState
  running: boolean
}

/**
 * Marcador de SmartRoute sobre el grafo: qué modelo ha resuelto cada llamada y cuánto se
 * ahorra frente a usar siempre el grande. Es la idea central del proyecto hecha visible
 * mientras los agentes trabajan.
 */
export function LiveSavings({ decisions, metrics, running }: Props) {
  if (decisions.length === 0) return null
  const counts = routeCounts(decisions)
  const totals = metrics.status === 'ready' ? metrics.metrics.totals : null
  const share = totals ? savingsShare(totals.cost_usd, totals.baseline_cost_usd) : null
  const last = decisions.at(-1)

  return (
    <aside className="live-savings" aria-label="SmartRoute en directo" aria-live="polite">
      <p className="live-savings__title">
        SmartRoute {running && <span className="live-savings__dot" aria-hidden="true" />}
      </p>
      <p className="live-savings__split">
        <span className="tier-chip tier-chip--slm">{counts.slm} SLM</span>
        <span className="tier-chip tier-chip--large">{counts.large} grande</span>
        {counts.escalations > 0 && (
          // key: la animación se repite cada vez que hay una escalada nueva.
          <span key={counts.escalations} className="tier-chip tier-chip--escalated">
            ⤴ {counts.escalations} {counts.escalations === 1 ? 'escalada' : 'escaladas'}
          </span>
        )}
      </p>
      {share !== null && totals && (
        <p className="live-savings__money">
          <strong>{Math.round(share * 100)} % ahorro</strong>
          <span>
            {formatUsd(totals.cost_usd)} frente a {formatUsd(totals.baseline_cost_usd)}
          </span>
        </p>
      )}
      {running && last && (
        <p className="live-savings__last" key={decisions.length}>
          {last.task} → {last.tier === 'slm' ? 'SLM' : 'grande'}
          {last.escalated ? ' (escalada)' : ''}
        </p>
      )}
    </aside>
  )
}
