import { useEffect, useState } from 'react'
import { getHealth } from './api/client'
import './App.css'

type BackendStatus = 'checking' | 'ok' | 'down'

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: 'Comprobando backend…',
  ok: 'Backend conectado',
  down: 'Backend no disponible',
}

// Esqueleto del día 1: solo demuestra que frontend y backend se hablan
// (a través del proxy de Vite en desarrollo). Las vistas de cada historia
// (grafo, panel de agentes, revisión, router) irán en src/features/.
export default function App() {
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

  return (
    <main className="app">
      <header className="app__header">
        <h1>VaultMind</h1>
        <p className="app__tagline">Agentes que investigan y hacen crecer tu bóveda de Obsidian</p>
      </header>
      <p className={`status status--${status}`} role="status">
        {STATUS_LABEL[status]}
      </p>
    </main>
  )
}
