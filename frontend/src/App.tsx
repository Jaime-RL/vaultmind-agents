import { useEffect, useState } from 'react'
import { getHealth } from './api/client'
import { Tabs } from './components/Tabs'
import { AgentsPanel } from './features/agents-panel/AgentsPanel'
import { ResearchForm } from './features/agents-panel/ResearchForm'
import { useResearchRun } from './features/agents-panel/useResearchRun'
import { GraphView } from './features/graph/GraphView'
import { useVaultGraph } from './features/graph/useVaultGraph'
import './App.css'

type BackendStatus = 'checking' | 'ok' | 'down'

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: 'Comprobando backend…',
  ok: 'Backend conectado',
  down: 'Backend no disponible',
}

function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>('checking')
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
  return status
}

export default function App() {
  const status = useBackendStatus()
  const { state: vaultState, reload: reloadVault } = useVaultGraph()
  const run = useResearchRun()
  const [tab, setTab] = useState('agents')
  const busy = run.state.status === 'starting' || run.state.status === 'running'
  // La cámara del grafo se acerca a la última nota propuesta.
  const focusId = run.state.proposed.at(-1)?.id

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <h1>VaultMind</h1>
          <p className="topbar__tagline">Agentes que investigan y hacen crecer tu bóveda de Obsidian</p>
        </div>
        <ResearchForm busy={busy} onSubmit={run.start} />
        <p className={`status status--${status}`} role="status" aria-label="Estado del backend">
          {STATUS_LABEL[status]}
        </p>
      </header>

      <main className="workspace">
        <section className="workspace__graph" aria-label="Grafo de la bóveda">
          <GraphView
            state={vaultState}
            proposed={run.state.proposed}
            focusId={focusId}
            fitAll={run.state.status === 'finished'}
            onRetry={reloadVault}
          />
        </section>
        <aside className="workspace__side">
          <Tabs
            label="Paneles"
            active={tab}
            onChange={setTab}
            tabs={[
              {
                id: 'agents',
                label: 'Agentes',
                content: <AgentsPanel state={run.state} onReconnect={run.reconnect} />,
              },
            ]}
          />
        </aside>
      </main>
    </div>
  )
}
