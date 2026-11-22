import { Component, lazy, Suspense, useMemo, type ContextType, type ReactNode } from 'react'
import type { VaultGraph } from '../../api/contract.gen'
import { I18nContext, useI18n } from '../../i18n/context'
import { PROPOSED_COLOR, TIER_COLORS } from './colors'
import { buildGraphData, type ProposedNode } from './graphData'
import type { VaultState } from './useVaultGraph'

// Carga diferida: three.js solo se descarga cuando hay un grafo que pintar.
const VaultGraph3D = lazy(() => import('./VaultGraph3D'))

// Si WebGL falla (navegador antiguo, GPU desactivada), mostramos un aviso en lugar
// de dejar la pantalla en blanco. Los error boundaries solo existen como clase.
class GraphErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  // Una clase no puede usar hooks: lee el idioma del contexto así.
  static contextType = I18nContext
  declare context: ContextType<typeof I18nContext>
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="graph-message graph-message--error" role="alert">
          {this.context.t('graph.webgl')}
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
  const { t } = useI18n()
  if (state.status === 'loading') {
    return (
      <p className="graph-message" role="status">
        {t('graph.loading')}
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="graph-message graph-message--error" role="alert">
        <p>{t('graph.error', { message: state.message })}</p>
        {onRetry && (
          <button type="button" className="button" onClick={onRetry}>
            {t('review.retry')}
          </button>
        )}
      </div>
    )
  }
  if (state.vault.nodes.length === 0) {
    return (
      <p className="graph-message" role="status">
        {t('graph.empty')}
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
  const { t, tn } = useI18n()

  return (
    <div className="graph">
      <p className="graph__summary">
        {t('graph.summary', { notes: vault.nodes.length, links: vault.links.length })}
        {pending > 0 && ` · ${tn('graph.proposals', pending)}`}
      </p>
      <GraphErrorBoundary>
        <Suspense fallback={<p className="graph-message">{t('graph.preparing')}</p>}>
          <VaultGraph3D data={data} focusId={focusId} fitAll={fitAll} />
        </Suspense>
      </GraphErrorBoundary>
      <Legend />
    </div>
  )
}

function Legend() {
  const { t } = useI18n()
  return (
    <aside className="legend" aria-label={t('graph.legend')}>
      <span className="legend__item">
        <span className="legend__dot legend__dot--note" />
        {t('graph.legend.note')}
      </span>
      <span className="legend__item">
        <span className="legend__dot" style={{ background: PROPOSED_COLOR }} />
        {t('graph.legend.proposed')}
      </span>
      <span className="legend__title">{t('graph.legend.ring')}</span>
      {(['slm', 'large'] as const).map((tier) => (
        <span key={tier} className="legend__item">
          <span className="legend__ring" style={{ borderColor: TIER_COLORS[tier] }} />
          {t(`tier.${tier}`)}
        </span>
      ))}
    </aside>
  )
}
