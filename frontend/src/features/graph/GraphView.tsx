import { Component, lazy, Suspense, useMemo, type ReactNode } from 'react'
import type { VaultGraph } from '../../api/contract.gen'
import { AGENT_COLORS, AGENT_LABELS, TIER_COLORS, TIER_LABELS } from './colors'
import { buildGraphData, type ProposedNode } from './graphData'
import type { VaultState } from './useVaultGraph'

// Carga diferida: three.js solo se descarga cuando hay un grafo que pintar.
const VaultGraph3D = lazy(() => import('./VaultGraph3D'))

// Si WebGL falla (navegador antiguo, GPU desactivada), mostramos un aviso en lugar
// de dejar la pantalla en blanco. Los error boundaries solo existen como clase.
class GraphErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="graph-message graph-message--error" role="alert">
          No se pudo dibujar el grafo 3D. Comprueba que tu navegador tiene WebGL activado.
        </p>
      )
    }
    return this.props.children
  }
}

interface Props {
  state: VaultState
  proposed?: ProposedNode[]
  focusId?: string
  fitAll?: boolean
  onRetry?: () => void
}

export function GraphView({ state, proposed = [], focusId, fitAll, onRetry }: Props) {
  if (state.status === 'loading') {
    return (
      <p className="graph-message" role="status">
        Cargando la bóveda…
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="graph-message graph-message--error" role="alert">
        <p>No se pudo cargar la bóveda: {state.message}</p>
        {onRetry && (
          <button type="button" className="button" onClick={onRetry}>
            Reintentar
          </button>
        )}
      </div>
    )
  }
  if (state.vault.nodes.length === 0) {
    return (
      <p className="graph-message" role="status">
        La bóveda está vacía: añade notas Markdown a la carpeta de la bóveda para verlas aquí.
      </p>
    )
  }
  return <ReadyGraph vault={state.vault} proposed={proposed} focusId={focusId} fitAll={fitAll} />
}

function ReadyGraph({
  vault,
  proposed,
  focusId,
  fitAll,
}: {
  vault: VaultGraph
  proposed: ProposedNode[]
  focusId?: string
  fitAll?: boolean
}) {
  const data = useMemo(() => buildGraphData(vault, proposed), [vault, proposed])
  const pending = proposed.filter((p) => p.status === 'pending').length

  return (
    <div className="graph">
      <p className="graph__summary">
        {vault.nodes.length} notas · {vault.links.length} enlaces
        {pending > 0 && ` · ${pending} ${pending === 1 ? 'propuesta' : 'propuestas'}`}
      </p>
      <GraphErrorBoundary>
        <Suspense fallback={<p className="graph-message">Preparando el grafo 3D…</p>}>
          <VaultGraph3D data={data} focusId={focusId} fitAll={fitAll} />
        </Suspense>
      </GraphErrorBoundary>
      <Legend />
    </div>
  )
}

function Legend() {
  const agents = ['explorer', 'researcher', 'writer', 'reviewer'] as const
  return (
    <aside className="legend" aria-label="Leyenda del grafo">
      <span className="legend__title">Notas nuevas</span>
      {agents.map((agent) => (
        <span key={agent} className="legend__item">
          <span className="legend__dot" style={{ background: AGENT_COLORS[agent] }} />
          {AGENT_LABELS[agent]}
        </span>
      ))}
      <span className="legend__title">Anillo = modelo</span>
      {(['slm', 'large'] as const).map((tier) => (
        <span key={tier} className="legend__item">
          <span className="legend__ring" style={{ borderColor: TIER_COLORS[tier] }} />
          {TIER_LABELS[tier]}
        </span>
      ))}
    </aside>
  )
}
