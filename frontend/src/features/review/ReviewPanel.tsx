import { useState } from 'react'
import type { Proposal } from '../../api/contract.gen'
import { shortModel } from '../agents-panel/describeEvent'
import { useI18n } from '../../i18n/context'
import { LANGUAGE_LABELS } from '../../i18n/messages'
import { ConfidenceBadge, ReviewDetails } from './ConfidenceBadge'
import { NoteMarkdown } from './NoteMarkdown'
import type { ProposalsState } from './useProposals'

interface Props {
  state: ProposalsState
  busyId: string | null
  actionError: string | null
  existing: Set<string>
  onResolve: (id: string, action: 'approve' | 'reject', markdown?: string) => void
  onRetry: () => void
  /** «Profundizar»: lanza una investigación nueva sobre esta nota. */
  onDeepen?: (title: string) => void
}

export function ReviewPanel({ state, busyId, actionError, existing, onResolve, onRetry, onDeepen }: Props) {
  // null = «la primera por defecto» (el usuario llega a revisar, no a hacer clic);
  // '' = todas cerradas a propósito; un id = esa nota abierta.
  const [openId, setOpenId] = useState<string | null>(null)
  const { t } = useI18n()

  if (state.status === 'loading') {
    return (
      <p className="panel-empty" role="status">
        {t('review.loading')}
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="notice notice--error" role="alert">
        <p>{t('review.error', { message: state.message })}</p>
        <button type="button" className="button" onClick={onRetry}>
          {t('review.retry')}
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
      <p className="review-panel__intro">{t('review.intro')}</p>
      {actionError && (
        <p className="notice notice--error" role="alert">
          {actionError}
        </p>
      )}
      {proposals.length === 0 ? (
        <p className="panel-empty">{t('review.empty')}</p>
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
              onDeepen={onDeepen}
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
  onResolve: (id: string, action: 'approve' | 'reject', markdown?: string) => void
  onDeepen?: (title: string) => void
}

function ProposalCard({ proposal, open, busy, existing, onToggle, onResolve, onDeepen }: CardProps) {
  const bodyId = `proposal-${proposal.id}`
  // null = sin editar; un texto = el usuario está editando la nota antes de aprobarla.
  const [draft, setDraft] = useState<string | null>(null)
  const edited = draft !== null && draft.trim() !== '' && draft !== proposal.markdown
  const { t, tn } = useI18n()
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
          {t(`agent.${proposal.agent}`)} · {shortModel(proposal.model)} ·{' '}
          {tn('review.sources', proposal.sources.length)}
          {proposal.language && <> · {LANGUAGE_LABELS[proposal.language]}</>}
        </span>
        <ConfidenceBadge proposal={proposal} />
      </button>

      {open && (
        <div id={bodyId} className="proposal__body">
          <ReviewDetails proposal={proposal} />
          {draft === null ? (
            <NoteMarkdown markdown={proposal.markdown} existing={existing} />
          ) : (
            <textarea
              className="proposal__editor"
              aria-label={t('review.editLabel', { title: proposal.title })}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={14}
            />
          )}

          {extraSources.length > 0 && (
            <section className="proposal__sources" aria-label={t('review.sourcesTitle')}>
              <h3>{t('review.sourcesTitle')}</h3>
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
              onClick={() => onResolve(proposal.id, 'approve', edited ? draft : undefined)}
            >
              {busy ? t('review.saving') : edited ? t('review.approveEdited') : t('review.approve')}
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => setDraft(draft === null ? proposal.markdown : null)}
            >
              {draft === null ? t('review.edit') : t('review.discard')}
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => onResolve(proposal.id, 'reject')}
            >
              {t('review.reject')}
            </button>
            {onDeepen && (
              <button
                type="button"
                className="button button--ghost"
                disabled={busy}
                title={t('review.deepenHint')}
                onClick={() => onDeepen(proposal.title)}
              >
                {t('review.deepen')}
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
