import { useEffect, useState } from 'react'
import { getMetrics } from '../../api/client'
import type { Metrics } from '../../api/contract.gen'

export type MetricsState =
  | { status: 'loading' }
  | { status: 'ready'; metrics: Metrics }
  | { status: 'error'; message: string }

/**
 * GET /api/metrics, de una investigación (runId) o de todas.
 *
 * `refreshKey` cambia con cada decisión del router y al terminar la investigación:
 * el backend guarda una métrica por cada llamada al LLM, así que el panel se
 * actualiza casi en directo sin necesidad de sondear.
 */
export function useMetrics(runId: string | undefined, refreshKey: string): MetricsState {
  const [state, setState] = useState<MetricsState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    getMetrics(runId).then(
      (metrics) => !cancelled && setState({ status: 'ready', metrics }),
      (error: unknown) =>
        !cancelled &&
        setState({ status: 'error', message: error instanceof Error ? error.message : 'Error desconocido' }),
    )
    return () => {
      cancelled = true
    }
  }, [runId, refreshKey])

  return state
}
