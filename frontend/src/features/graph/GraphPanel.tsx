import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import type { AgentEvent, VaultGraph } from '../../api/contract.gen'
import { getVault } from '../../api/endpoints'
import { buildGraphData } from './graphData'

// three.js es pesado: el lienzo se descarga solo cuando se muestra el grafo.
const ForceGraphView = lazy(() => import('./ForceGraphView'))

interface Props {
  /** Eventos de la investigación en curso: sus node_proposed aparecen en el grafo. */
  events?: AgentEvent[]
  /** Cambia cuando se aprueba una nota: recarga la bóveda para mostrarla ya como nota real. */
  refreshKey?: number
}

/** HU1 — La bóveda como grafo 3D, con las notas propuestas creciendo en directo. */
export default function GraphPanel({ events = [], refreshKey = 0 }: Props) {
  const [vault, setVault] = useState<VaultGraph | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getVault()
      .then((data) => {
        if (cancelled) return
        setVault(data)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'el backend no responde')
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  const data = useMemo(() => (vault ? buildGraphData(vault, events) : null), [vault, events])
  const counts = useMemo(() => {
    const c = { note: 0, copilot: 0, proposed: 0 }
    for (const n of data?.nodes ?? []) c[n.kind] += 1
    return c
  }, [data])

  return (
    <section className="panel graph" aria-labelledby="graph-title">
      <header className="panel__header">
        <h2 id="graph-title">Tu bóveda</h2>
        {data && (
          <ul className="legend" aria-label="Leyenda del grafo">
            <li className="legend__item legend__item--note">{counts.note} notas</li>
            <li className="legend__item legend__item--copilot">{counts.copilot} aprobadas</li>
            <li className="legend__item legend__item--proposed">{counts.proposed} propuestas</li>
          </ul>
        )}
      </header>

      {error && (
        <p className="notice notice--error" role="alert">
          No se pudo cargar la bóveda: {error}
        </p>
      )}
      {!data && !error && <p className="muted">Cargando la bóveda…</p>}
      {data && (
        <Suspense fallback={<p className="muted">Cargando el grafo 3D…</p>}>
          <ForceGraphView data={data} />
        </Suspense>
      )}
    </section>
  )
}
