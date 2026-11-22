import { useId } from 'react'
import type { Metrics } from '../../api/contract.gen'
import { formatUsd, shortModel } from '../agents-panel/describeEvent'
import { TierDot } from '../../components/TierDot'
import { LOCALES, useI18n } from '../../i18n/context'
import type { MetricsState } from './useMetrics'

export type MetricsScope = 'run' | 'all'

interface Props {
  state: MetricsState
  scope: MetricsScope
  hasRun: boolean
  onScopeChange: (scope: MetricsScope) => void
}

const percent = (value: number) => `${Math.round(value * 100)} %`

export function RouterPanel({ state, scope, hasRun, onScopeChange }: Props) {
  const { t } = useI18n()
  return (
    <div className="router-panel">
      <div className="segmented" role="group" aria-label={t('router.scope')}>
        <button
          type="button"
          aria-pressed={scope === 'run'}
          disabled={!hasRun}
          title={hasRun ? undefined : t('router.scope.runHint')}
          onClick={() => onScopeChange('run')}
        >
          {t('router.scope.run')}
        </button>
        <button type="button" aria-pressed={scope === 'all'} onClick={() => onScopeChange('all')}>
          {t('router.scope.all')}
        </button>
      </div>

      {state.status === 'loading' && (
        <p className="panel-empty" role="status">
          {t('router.loading')}
        </p>
      )}
      {state.status === 'error' && (
        <p className="notice notice--error" role="alert">
          {t('router.error', { message: state.message })}
        </p>
      )}
      {state.status === 'ready' &&
        (state.metrics.tasks.length === 0 ? (
          <p className="panel-empty">
            {t('router.empty')}
          </p>
        ) : (
          <MetricsView metrics={state.metrics} />
        ))}
    </div>
  )
}

function MetricsView({ metrics }: { metrics: Metrics }) {
  const { totals, tasks } = metrics
  const { t, lang } = useI18n()
  const savingsShare = totals.baseline_cost_usd > 0 ? totals.savings_usd / totals.baseline_cost_usd : 0

  return (
    <>
      {/* Cifra principal: lo que responde la HU4 («cuánto ahorra el router»). */}
      <section className="kpis" aria-label={t('router.summary')}>
        <div className="kpi kpi--hero">
          <span className="kpi__label">{t('router.savings')}</span>
          <span className="kpi__value">{formatUsd(totals.savings_usd)}</span>
          <span className="kpi__hint">{t('router.savingsHint', { percent: percent(savingsShare) })}</span>
        </div>
        <div className="kpi">
          <span className="kpi__label">{t('router.slmShare')}</span>
          <span className="kpi__value">{percent(totals.slm_share)}</span>
          <span className="kpi__hint">{t('router.slmShareHint', { n: totals.tasks })}</span>
        </div>
        <div className="kpi">
          <span className="kpi__label">{t('router.escalations')}</span>
          <span className="kpi__value">{totals.escalations}</span>
          <span className="kpi__hint">{t('router.escalationsHint')}</span>
        </div>
      </section>

      <CostComparison cost={totals.cost_usd} baseline={totals.baseline_cost_usd} />

      <div className="table-scroll">
        <table className="metrics-table">
          <caption>{t('router.table')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('router.col.agent')}</th>
              <th scope="col">{t('router.col.task')}</th>
              <th scope="col">{t('router.col.model')}</th>
              <th scope="col" className="num">
                {t('router.col.tokens')}
              </th>
              <th scope="col" className="num">
                {t('router.col.cost')}
              </th>
              <th scope="col" className="num">
                {t('router.col.latency')}
              </th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task, index) => (
              <tr key={`${task.run_id}-${index}`} className={task.escalated ? 'is-escalated' : undefined}>
                <td>{t(`agent.${task.agent}`)}</td>
                <td>
                  <code>{task.task}</code>
                </td>
                <td title={task.model}>
                  <TierDot tier={task.tier} /> {t(`tier.short.${task.tier}`)}
                  <span className="metrics-table__model">{shortModel(task.model)}</span>
                  {task.escalated && <span className="escalated"> · {t('router.escalated')}</span>}
                </td>
                <td className="num">{(task.prompt_tokens + task.completion_tokens).toLocaleString(LOCALES[lang])}</td>
                <td className="num">{formatUsd(task.cost_usd)}</td>
                <td className="num">{(task.latency_ms / 1000).toFixed(1)} s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/**
 * Dos barras sobre el mismo eje: coste real frente a «todo con el modelo grande».
 * Una sola magnitud (USD) y una sola escala; el valor va escrito junto a cada barra,
 * así que no depende del color.
 */
function CostComparison({ cost, baseline }: { cost: number; baseline: number }) {
  const captionId = useId()
  const { t } = useI18n()
  const max = Math.max(cost, baseline) || 1
  const rows = [
    { label: t('router.withSmartRoute'), value: cost, emphasis: true },
    { label: t('router.largeOnly'), value: baseline, emphasis: false },
  ]
  return (
    <figure className="cost-bars" aria-labelledby={captionId}>
      <figcaption id={captionId}>{t('router.totalCost')}</figcaption>
      {rows.map((row) => (
        <div key={row.label} className="cost-bars__row" title={`${row.label}: ${formatUsd(row.value)}`}>
          <span className="cost-bars__label">{row.label}</span>
          <span className="cost-bars__track">
            <span
              className={`cost-bars__bar ${row.emphasis ? 'cost-bars__bar--emphasis' : ''}`}
              style={{ width: `${(row.value / max) * 100}%` }}
            />
          </span>
          <span className="cost-bars__value">{formatUsd(row.value)}</span>
        </div>
      ))}
    </figure>
  )
}
