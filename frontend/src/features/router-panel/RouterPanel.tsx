import { useId } from 'react'
import type { Metrics } from '../../api/contract.gen'
import { formatUsd, shortModel } from '../agents-panel/describeEvent'
import { AGENT_LABELS, TIER_SHORT } from '../graph/colors'
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
  return (
    <div className="router-panel">
      <div className="segmented" role="group" aria-label="Qué investigaciones mostrar">
        <button
          type="button"
          aria-pressed={scope === 'run'}
          disabled={!hasRun}
          title={hasRun ? undefined : 'Lanza una investigación para ver solo la suya'}
          onClick={() => onScopeChange('run')}
        >
          Esta investigación
        </button>
        <button type="button" aria-pressed={scope === 'all'} onClick={() => onScopeChange('all')}>
          Todas
        </button>
      </div>

      {state.status === 'loading' && (
        <p className="panel-empty" role="status">
          Cargando métricas…
        </p>
      )}
      {state.status === 'error' && (
        <p className="notice notice--error" role="alert">
          No se pudieron cargar las métricas: {state.message}
        </p>
      )}
      {state.status === 'ready' &&
        (state.metrics.tasks.length === 0 ? (
          <p className="panel-empty">
            Aún no hay tareas registradas. Cada llamada a un modelo aparecerá aquí con su coste.
          </p>
        ) : (
          <MetricsView metrics={state.metrics} />
        ))}
    </div>
  )
}

function MetricsView({ metrics }: { metrics: Metrics }) {
  const { totals, tasks } = metrics
  const savingsShare = totals.baseline_cost_usd > 0 ? totals.savings_usd / totals.baseline_cost_usd : 0

  return (
    <>
      {/* Cifra principal: lo que responde la HU4 («cuánto ahorra el router»). */}
      <section className="kpis" aria-label="Resumen">
        <div className="kpi kpi--hero">
          <span className="kpi__label">Ahorro frente a usar solo el modelo grande</span>
          <span className="kpi__value">{formatUsd(totals.savings_usd)}</span>
          <span className="kpi__hint">{percent(savingsShare)} menos</span>
        </div>
        <div className="kpi">
          <span className="kpi__label">Tareas resueltas por el SLM</span>
          <span className="kpi__value">{percent(totals.slm_share)}</span>
          <span className="kpi__hint">de {totals.tasks}</span>
        </div>
        <div className="kpi">
          <span className="kpi__label">Escaladas al modelo grande</span>
          <span className="kpi__value">{totals.escalations}</span>
          <span className="kpi__hint">el SLM falló y se repitió</span>
        </div>
      </section>

      <CostComparison cost={totals.cost_usd} baseline={totals.baseline_cost_usd} />

      <div className="table-scroll">
        <table className="metrics-table">
          <caption>Qué modelo hizo cada tarea y cuánto costó</caption>
          <thead>
            <tr>
              <th scope="col">Agente</th>
              <th scope="col">Tarea</th>
              <th scope="col">Modelo</th>
              <th scope="col" className="num">
                Tokens
              </th>
              <th scope="col" className="num">
                Coste
              </th>
              <th scope="col" className="num">
                Latencia
              </th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task, index) => (
              <tr key={`${task.run_id}-${index}`} className={task.escalated ? 'is-escalated' : undefined}>
                <td>{AGENT_LABELS[task.agent]}</td>
                <td>
                  <code>{task.task}</code>
                </td>
                <td title={task.model}>
                  {task.tier === 'slm' ? '🟢' : '🔵'} {TIER_SHORT[task.tier]}
                  <span className="metrics-table__model">{shortModel(task.model)}</span>
                  {task.escalated && <span className="escalated"> · escalada</span>}
                </td>
                <td className="num">{(task.prompt_tokens + task.completion_tokens).toLocaleString('es-ES')}</td>
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
  const max = Math.max(cost, baseline) || 1
  const rows = [
    { label: 'Con SmartRoute', value: cost, emphasis: true },
    { label: 'Solo modelo grande', value: baseline, emphasis: false },
  ]
  return (
    <figure className="cost-bars" aria-labelledby={captionId}>
      <figcaption id={captionId}>Coste total</figcaption>
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
