import { useCallback, useEffect, useMemo, useState } from 'react'
import { getHealth } from './api/client'
import { Tabs } from './components/Tabs'
import { AgentsPanel } from './features/agents-panel/AgentsPanel'
import { AskPanel } from './features/ask/AskPanel'
import { LiveSavings } from './features/live-savings/LiveSavings'
import { ResearchForm } from './features/agents-panel/ResearchForm'
import { useResearchRun } from './features/agents-panel/useResearchRun'
import { GraphView } from './features/graph/GraphView'
import { useVaultGraph } from './features/graph/useVaultGraph'
import { ReviewPanel } from './features/review/ReviewPanel'
import { RouterPanel, type MetricsScope } from './features/router-panel/RouterPanel'
import { useMetrics } from './features/router-panel/useMetrics'
import { useProposals } from './features/review/useProposals'
import './App.css'
import { mergeProposed } from './features/graph/graphData'
import { InterfaceLanguageSelect } from './components/LanguageSelect'
import type { ContentLanguage } from './api/contract.gen'
import { useI18n } from './i18n/context'
import type { MessageKey } from './i18n/messages'

type BackendStatus = 'checking' | 'ok' | 'down'

const STATUS_KEY = {
  checking: 'app.backend.checking',
  ok: 'app.backend.ok',
  down: 'app.backend.down',
} as const satisfies Record<BackendStatus, MessageKey>

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
  const { t } = useI18n()
  const { state: vaultState, reload: reloadVault } = useVaultGraph()
  const run = useResearchRun()
  const [tab, setTab] = useState('agents')
  const busy = run.state.status === 'starting' || run.state.status === 'running'
  // Nota citada en «Preguntar» a la que vuela la cámara; se olvida al lanzar otra investigación.
  const [askFocus, setAskFocus] = useState<string>()
  // La cámara del grafo se acerca a la nota citada o, si no, a la última nota propuesta.
  const focusId = askFocus ?? run.state.proposed.at(-1)?.id
  const { start } = run
  const startResearch = useCallback(
    (topic: string, language?: ContentLanguage) => {
      setAskFocus(undefined)
      start(topic, language)
    },
    [start],
  )

  const { markResolved } = run
  const onResolved = useCallback(
    (id: string, resolution: 'approved' | 'rejected') => {
      markResolved(id, resolution)
      // Una nota aprobada ya existe en la bóveda (en _copilot/): recargamos el grafo.
      if (resolution === 'approved') reloadVault()
    },
    [markResolved, reloadVault],
  )
  const proposals = useProposals({
    // Se vuelve a pedir la lista cuando llega una propuesta o termina la investigación.
    refreshKey: `${run.state.runId ?? ''}:${run.state.proposed.length}:${run.state.status}`,
    onResolved,
  })
  const pendingCount = proposals.state.status === 'ready' ? proposals.state.proposals.length : 0

  // Métricas del router: por defecto las de la investigación en curso, si la hay.
  const [scope, setScope] = useState<MetricsScope>('run')
  const metricsRunId = scope === 'run' ? run.state.runId : undefined
  const metrics = useMetrics(
    metricsRunId,
    `${run.state.routeDecisions.length}:${run.state.status}`,
  )

  // Notas del grafo: las de la investigación en curso y, además, las pendientes que ya
  // estaban guardadas (p. ej., tras recargar la página), para que no desaparezcan del grafo.
  const graphProposed = useMemo(
    () => mergeProposed(run.state.proposed, proposals.state.status === 'ready' ? proposals.state.proposals : []),
    [run.state.proposed, proposals.state],
  )

  // Métricas SOLO de la investigación en curso, para el marcador de SmartRoute sobre el grafo.
  const runMetrics = useMetrics(run.state.runId, `${run.state.routeDecisions.length}:${run.state.status}`)

  // Notas de la bóveda (por id y por título) para marcar los [[enlaces]] que ya existen.
  const existingNotes = useMemo(
    () =>
      new Set(
        vaultState.status === 'ready' ? vaultState.vault.nodes.flatMap((n) => [n.id, n.title]) : [],
      ),
    [vaultState],
  )

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <h1>VaultMind</h1>
          <p className="topbar__tagline">{t('app.tagline')}</p>
        </div>
        <ResearchForm busy={busy} onSubmit={startResearch} />
        <div className="topbar__end">
          <InterfaceLanguageSelect />
          <p className={`status status--${status}`} role="status" aria-label={t('app.backend.label')}>
            {t(STATUS_KEY[status])}
          </p>
        </div>
      </header>

      <main className="workspace">
        <section className="workspace__graph" aria-label={t('app.graph')}>
          <GraphView
            state={vaultState}
            proposed={graphProposed}
            focusId={focusId}
            fitAll={run.state.status === 'finished' && !askFocus}
            onRetry={reloadVault}
          />
          {run.state.runId && (
            <LiveSavings decisions={run.state.routeDecisions} metrics={runMetrics} running={busy} />
          )}
        </section>
        <aside className="workspace__side">
          <Tabs
            label={t('app.panels')}
            active={tab}
            onChange={setTab}
            tabs={[
              {
                id: 'agents',
                label: t('tab.agents'),
                content: <AgentsPanel state={run.state} onReconnect={run.reconnect} onExample={startResearch} />,
              },
              {
                id: 'review',
                label: t('tab.review'),
                badge: pendingCount,
                content: (
                  <ReviewPanel
                    state={proposals.state}
                    busyId={proposals.busyId}
                    actionError={proposals.actionError}
                    existing={existingNotes}
                    onResolve={proposals.resolve}
                    onRetry={() => void proposals.reload()}
                    onDeepen={(title) => {
                      setTab('agents')
                      startResearch(title)
                    }}
                  />
                ),
              },
              {
                id: 'ask',
                label: t('tab.ask'),
                content: <AskPanel existing={existingNotes} onFocusNote={setAskFocus} />,
              },
              {
                id: 'router',
                label: t('tab.router'),
                content: (
                  <RouterPanel
                    state={metrics}
                    scope={run.state.runId ? scope : 'all'}
                    hasRun={Boolean(run.state.runId)}
                    onScopeChange={setScope}
                  />
                ),
              },
            ]}
          />
        </aside>
      </main>
    </div>
  )
}
