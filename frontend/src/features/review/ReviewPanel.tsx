import { useState } from 'react'
import type { Proposal } from '../../api/contract.gen'
import { plural, shortModel } from '../agents-panel/describeEvent'
import { AGENT_LABELS } from '../graph/colors'
import { ConfidenceBadge, ReviewDetails } from './ConfidenceBadge'
import { NoteMarkdown } from './NoteMarkdown'
import type { ProposalsState } from './useProposals'

interface Props {
  state: ProposalsState
  busyId: string | null
  actionError: string | null
  existing: Set<string>
  onResolve: (id: string, action: 'approve' | 'reject') => void
  onRetry: () => void
}

export function ReviewPanel({ state, busyId, actionError, existing, onResolve, onRetry }: Props) {
  // null = «la primera por defecto» (el usuario llega a revisar, no a hacer clic);
  // '' = todas cerradas a propósito; un id = esa nota abierta.
  const [openId, setOpenId] = useState<string | null>(null)

  if (state.status === 'loading') {
    return (
      <p className="panel-empty" role="status">
        Cargando notas propuestas…
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="notice notice--error" role="alert">
        <p>No se pudieron cargar las notas: {state.message}</p>
        <button type="button" className="button" onClick={onRetry}>
          Reintentar
        </button>
      </div>
    )
  }

  const { proposals } = state
  // Si la nota abierta se acaba de aprobar o rechazar, pasamos a la siguiente.
  const activeId =
    openId === ''
      ? null
      : proposals.some((p) => p.id === openId)
        ? openId
        : (proposals[0]?.id ?? null)

  return (
    <div className="review-panel">
      <p className="review-panel__intro">
        Nada entra en tu bóveda sin tu aprobación. Las notas aprobadas se guardan en{' '}
        <code>_copilot/</code>.
      </p>
      {actionError && (
        <p className="notice notice--error" role="alert">
          {actionError}
        </p>
      )}
      {proposals.length === 0 ? (
        <p className="panel-empty">No hay notas pendientes de revisar. Lanza una investigación para generar nuevas.</p>
      ) : (
        <ul className="proposal-list">
          {proposals.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              open={proposal.id === activeId}
              busy={busyId === proposal.id}
              existing={existing}
              onToggle={() => setOpenId(proposal.id === activeId ? '' : proposal.id)}
              onResolve={onResolve}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

interface CardProps {
  proposal: Proposal
  open: boolean
  busy: boolean
  existing: Set<string>
  onToggle: () => void
  onResolve: (id: string, action: 'approve' | 'reject') => void
}

function ProposalCard({ proposal, open, busy, existing, onToggle, onResolve }: CardProps) {
  const bodyId = `proposal-${proposal.id}`
  // El backend ya añade una sección de fuentes al final del Markdown; aquí solo
  // listamos las que no aparezcan en la nota, para no mostrarlas dos veces.
  const extraSources = proposal.sources.filter((source) => !proposal.markdown.includes(source.url))
  return (
    <li className={`proposal ${open ? 'proposal--open' : ''}`}>
      <button
        type="button"
        className="proposal__header"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={onToggle}
      >
        <span className="proposal__title">{proposal.title}</span>
        <span className="proposal__meta">
          {AGENT_LABELS[proposal.agent]} ·{' '}
          {shortModel(proposal.model)} · {plural(proposal.sources.length, 'fuente')}
        </span>
        <ConfidenceBadge proposal={proposal} />
      </button>

      {open && (
        <div id={bodyId} className="proposal__body">
          <ReviewDetails proposal={proposal} />
          <NoteMarkdown markdown={proposal.markdown} existing={existing} />

          {extraSources.length > 0 && (
            <section className="proposal__sources" aria-label="Fuentes">
              <h3>Fuentes</h3>
              <ol>
                {extraSources.map((source) => (
                  <li key={source.url}>
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      {source.title}
                    </a>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <div className="proposal__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={busy}
              onClick={() => onResolve(proposal.id, 'approve')}
            >
              {busy ? 'Guardando…' : 'Aprobar'}
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => onResolve(proposal.id, 'reject')}
            >
              Rechazar
            </button>
          </div>
        </div>
      )}
    </li>
  )
}
