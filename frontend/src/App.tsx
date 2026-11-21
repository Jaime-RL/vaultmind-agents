import { useEffect, useState } from 'react'
import { getHealth } from './api/client'
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

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <h1>VaultMind</h1>
          <p className="topbar__tagline">Agentes que investigan y hacen crecer tu bóveda de Obsidian</p>
        </div>
        <p className={`status status--${status}`} role="status" aria-label="Estado del backend">
          {STATUS_LABEL[status]}
        </p>
      </header>

      <main className="workspace">
        <section className="workspace__graph" aria-label="Grafo de la bóveda">
          <GraphView state={vaultState} onRetry={reloadVault} />
        </section>
      </main>
    </div>
  )
}
