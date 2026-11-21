import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import type { Metrics } from '../../api/contract.gen'
import { getMetrics } from '../../api/endpoints'
import { AGENT_LABEL, formatMs, formatPercent, formatUsd, shortModel } from '../../lib/format'

interface Props {
  /** Investigación en curso o la última; null = todas. */
  runId?: string | null
  /** Cambia con cada decisión del router (evento route_decision) para recargar. */
  refreshKey?: number
}

type Scope = 'run' | 'all'

/**
 * HU4 — Qué modelo hizo cada tarea, cuánto costó y cuánto ahorra el router
 * frente a usar siempre el modelo grande.
 */
export default function RouterPanel({ runId = null, refreshKey = 0 }: Props) {
  const [scope, setScope] = useState<Scope>(runId ? 'run' : 'all')
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Al empezar una investigación nueva, el panel pasa a mostrar esa investigación.
  const [lastRunId, setLastRunId] = useState(runId)
  if (runId !== lastRunId) {
    setLastRunId(runId)
    if (runId) setScope('run')
  }

  const effectiveRun = scope === 'run' ? runId : null

  useEffect(() => {
    let cancelled = false
    getMetrics(effectiveRun)
      .then((data) => {
        if (cancelled) return
        setMetrics(data)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'el backend no responde')
      })
    return () => {
      cancelled = true
    }
  }, [effectiveRun, refreshKey])

  const totals = metrics?.totals
  const savingsShare = totals && totals.baseline_cost_usd > 0 ? totals.savings_usd / totals.baseline_cost_usd : 0
  const costWidth = totals && totals.baseline_cost_usd > 0 ? totals.cost_usd / totals.baseline_cost_usd : 0

  return (
    <section className="panel router" aria-labelledby="router-title">
      <header className="panel__header">
        <h2 id="router-title">SmartRoute</h2>
        <div className="segmented" role="group" aria-label="Ámbito de las métricas">
          <button
            type="button"
            aria-pressed={scope === 'run'}
            disabled={!runId}
            onClick={() => setScope('run')}
          >
            Esta investigación
          </button>
          <button type="button" aria-pressed={scope === 'all'} onClick={() => setScope('all')}>
            Todas
          </button>
        </div>
      </header>

      {error && (
        <p className="notice notice--error" role="alert">
          No se pudieron cargar las métricas: {error}
        </p>
      )}

      {totals && totals.tasks === 0 && (
        <p className="muted">Aún no hay tareas. Lanza una investigación para ver qué modelo hace cada una.</p>
      )}

      {totals && totals.tasks > 0 && metrics && (
        <>
          <dl className="kpis">
            <div className="kpi kpi--accent">
              <dt>Ahorro</dt>
              <dd>
                {formatPercent(savingsShare)}
                <small>{formatUsd(totals.savings_usd)}</small>
              </dd>
            </div>
            <div className="kpi">
              <dt>Coste real</dt>
              <dd>{formatUsd(totals.cost_usd)}</dd>
            </div>
            <div className="kpi">
              <dt>Solo modelo grande</dt>
              <dd>{formatUsd(totals.baseline_cost_usd)}</dd>
            </div>
            <div className="kpi">
              <dt>Tareas con SLM</dt>
              <dd>
                {formatPercent(totals.slm_share)}
                <small>
                  {totals.tasks} tareas · {totals.escalations}{' '}
                  {totals.escalations === 1 ? 'escalada' : 'escaladas'}
                </small>
              </dd>
            </div>
          </dl>

          <div className="cost-bars" aria-label="Coste con router frente a usar siempre el modelo grande">
            <div className="cost-bars__row">
              <span>Con SmartRoute</span>
              <div className="cost-bars__track">
                <div className="cost-bars__fill cost-bars__fill--router" style={{ width: `${costWidth * 100}%` }} />
              </div>
            </div>
            <div className="cost-bars__row">
              <span>Solo grande</span>
              <div className="cost-bars__track">
                <div className="cost-bars__fill cost-bars__fill--baseline" style={{ width: '100%' }} />
              </div>
            </div>
          </div>

          <table className="tasks">
            <thead>
              <tr>
                <th scope="col">Agente</th>
                <th scope="col">Tarea</th>
                <th scope="col">Modelo</th>
                <th scope="col" className="num">Tokens</th>
                <th scope="col" className="num">Coste</th>
                <th scope="col" className="num">Latencia</th>
              </tr>
            </thead>
            <tbody>
              {metrics.tasks.map((t, index) => (
                <tr key={`${t.run_id}-${index}`}>
                  <td>{AGENT_LABEL[t.agent] ?? t.agent}</td>
                  <td>
                    <code>{t.task}</code>
                  </td>
                  <td>
                    <span className={`tier tier--${t.tier}`}>{t.tier === 'slm' ? 'SLM' : 'Grande'}</span>{' '}
                    <span className="muted">{shortModel(t.model)}</span>
                    {t.escalated && (
                      <span className="escalated" title="El modelo pequeño falló y se repitió con el grande">
                        ↑ escalada
                      </span>
                    )}
                  </td>
                  <td className="num">{(t.prompt_tokens + t.completion_tokens).toLocaleString('es-ES')}</td>
                  <td className="num">{formatUsd(t.cost_usd)}</td>
                  <td className="num">{formatMs(t.latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
