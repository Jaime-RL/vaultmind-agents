import type { RouteDecision } from '../../api/contract.gen'
import { useI18n } from '../../i18n/context'
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
  const { t, tn } = useI18n()
  if (decisions.length === 0) return null
  const counts = routeCounts(decisions)
  const totals = metrics.status === 'ready' ? metrics.metrics.totals : null
  const share = totals ? savingsShare(totals.cost_usd, totals.baseline_cost_usd) : null
  const last = decisions.at(-1)

  return (
    <aside className="live-savings" aria-label={t('live.label')} aria-live="polite">
      <p className="live-savings__title">
        SmartRoute {running && <span className="live-savings__dot" aria-hidden="true" />}
      </p>
      <p className="live-savings__split">
        <span className="tier-chip tier-chip--slm">{counts.slm} SLM</span>
        <span className="tier-chip tier-chip--large">{t('live.large', { n: counts.large })}</span>
        {counts.escalations > 0 && (
          // key: la animación se repite cada vez que hay una escalada nueva.
          <span key={counts.escalations} className="tier-chip tier-chip--escalated">
            {tn('live.escalations', counts.escalations)}
          </span>
        )}
      </p>
      {share !== null && totals && (
        <p className="live-savings__money">
          <strong>{t('live.savings', { percent: Math.round(share * 100) })}</strong>
          <span>
            {t('live.versus', {
              cost: formatUsd(totals.cost_usd),
              baseline: formatUsd(totals.baseline_cost_usd),
            })}
          </span>
        </p>
      )}
      {running && last && (
        <p className="live-savings__last" key={decisions.length}>
          {last.task} → {t(`tier.short.${last.tier}`)}
          {last.escalated ? ` ${t('live.escalatedShort')}` : ''}
        </p>
      )}
    </aside>
  )
}
