import { useEffect, useMemo, useState } from 'react'
import { getHealth } from './api/client'
import AgentsPanel from './features/agents-panel/AgentsPanel'
import { useResearch } from './features/agents-panel/useResearch'
import GraphPanel from './features/graph/GraphPanel'
import ReviewPanel from './features/review/ReviewPanel'
import RouterPanel from './features/router-panel/RouterPanel'
import './App.css'

type BackendStatus = 'checking' | 'ok' | 'down'

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: 'Comprobando backend…',
  ok: 'Backend conectado',
  down: 'Backend no disponible',
}

/**
 * Pantalla principal: investigación (HU2) y grafo (HU1) arriba; revisión de notas
 * (HU3) y panel del router (HU4) debajo. Los paneles se recargan solos según
 * llegan eventos de la investigación.
 */
export default function App() {
  const [status, setStatus] = useState<BackendStatus>('checking')
  const research = useResearch()
  const [approvals, setApprovals] = useState(0)

  useEffect(() => {
    // `cancelled` evita actualizar el estado si el componente se desmonta antes
    // de que llegue la respuesta (y el doble montaje de StrictMode en desarrollo).
    let cancelled = false
    getHealth()
      .then(() => !cancelled && setStatus('ok'))
      .catch(() => !cancelled && setStatus('down'))
    return () => {
      cancelled = true
    }
  }, [])

  // Contadores derivados de los eventos: cada nota propuesta recarga la revisión y
  // cada decisión del router recarga sus métricas.
  const { proposals, routes } = useMemo(() => {
    let p = 0
    let r = 0
    for (const e of research.events) {
      if (e.type === 'node_proposed') p += 1
      if (e.type === 'route_decision' || e.type === 'run_finished') r += 1
    }
    return { proposals: p, routes: r }
  }, [research.events])

  return (
    <main className="app">
      <header className="app__header">
        <div>
          <h1>VaultMind</h1>
          <p className="app__tagline">Agentes que investigan y hacen crecer tu bóveda de Obsidian</p>
        </div>
        <p className={`status status--${status}`} role="status">
          {STATUS_LABEL[status]}
        </p>
      </header>

      <div className="grid-top">
        <AgentsPanel research={research} />
        <GraphPanel events={research.events} refreshKey={approvals} />
      </div>
      <ReviewPanel refreshKey={proposals} onApproved={() => setApprovals((n) => n + 1)} />
      <RouterPanel runId={research.runId} refreshKey={routes} />
    </main>
  )
}
