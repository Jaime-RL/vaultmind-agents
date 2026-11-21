import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getProposals, resolveProposal, type Proposal } from '../../api/endpoints'
import { AGENT_LABEL, shortModel } from '../../lib/format'
import NoteMarkdown from './NoteMarkdown'

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready' }

interface Props {
  /** Cambia cuando llega una nota nueva (evento node_proposed): fuerza a recargar la lista. */
  refreshKey?: number
  /** Avisa al resto de la app (p. ej. el grafo) de que una nota entró en la bóveda. */
  onApproved?: (proposal: Proposal) => void
}

/**
 * HU3 — Revisar y aprobar las notas propuestas antes de que entren en la bóveda.
 * Lista de pendientes a la izquierda; la nota seleccionada, renderizada, a la derecha.
 */
export default function ReviewPanel({ refreshKey = 0, onApproved }: Props) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  // Recargar = incrementar este contador (botón «Actualizar» o tras aprobar/rechazar).
  const [reloads, setReloads] = useState(0)
  const reload = () => setReloads((n) => n + 1)

  useEffect(() => {
    // El estado solo se actualiza cuando llega la respuesta; `cancelled` descarta
    // respuestas que lleguen tarde (desmontaje o una recarga más reciente).
    let cancelled = false
    getProposals('pending')
      .then((pending) => {
        if (cancelled) return
        setProposals(pending)
        // Mantiene la selección si sigue pendiente; si no, selecciona la primera.
        setSelectedId((current) =>
          current && pending.some((p) => p.id === current) ? current : (pending[0]?.id ?? null),
        )
        setLoad({ state: 'ready' })
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoad({ state: 'error', message: errorText(error) })
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey, reloads])

  async function decide(proposal: Proposal, action: 'approve' | 'reject') {
    setBusy(true)
    setNotice(null)
    try {
      await resolveProposal(proposal.id, action)
      setNotice({
        kind: 'ok',
        text:
          action === 'approve'
            ? `«${proposal.title}» guardada en tu bóveda (_copilot/).`
            : `«${proposal.title}» descartada.`,
      })
      if (action === 'approve') onApproved?.(proposal)
    } catch (error) {
      setNotice({ kind: 'error', text: errorText(error) })
    } finally {
      reload() // también tras un error, p. ej. 409: otra pestaña ya la resolvió
      setBusy(false)
    }
  }

  const selected = proposals.find((p) => p.id === selectedId) ?? null

  return (
    <section className="panel review" aria-labelledby="review-title">
      <header className="panel__header">
        <h2 id="review-title">Notas por revisar</h2>
        <button type="button" className="button button--ghost" onClick={reload}>
          Actualizar
        </button>
      </header>

      {notice && (
        <p className={`notice notice--${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.text}
        </p>
      )}

      {load.state === 'loading' && <p className="muted">Cargando propuestas…</p>}
      {load.state === 'error' && (
        <p className="notice notice--error" role="alert">
          No se pudieron cargar las propuestas: {load.message}
        </p>
      )}
      {load.state === 'ready' && proposals.length === 0 && (
        <p className="muted">
          No hay notas pendientes. Lanza una investigación y aparecerán aquí para que las revises.
        </p>
      )}

      {proposals.length > 0 && (
        <div className="review__layout">
          <ul className="review__list" aria-label="Propuestas pendientes">
            {proposals.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={`review__item ${p.id === selectedId ? 'review__item--active' : ''}`}
                  aria-pressed={p.id === selectedId}
                  onClick={() => setSelectedId(p.id)}
                >
                  <span className="review__item-title">{p.title}</span>
                  <span className="review__item-meta">
                    {p.sources.length} {p.sources.length === 1 ? 'fuente' : 'fuentes'} ·{' '}
                    {p.links.length} enlaces
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {selected && (
            <article className="review__detail" aria-label={`Nota ${selected.title}`}>
              <p className="review__meta">
                Redactada por {AGENT_LABEL[selected.agent] ?? selected.agent} con{' '}
                <code>{shortModel(selected.model)}</code>
              </p>
              {selected.sources.length === 0 && (
                <p className="notice notice--warn">Esta nota no tiene fuentes verificadas: revísala con cuidado.</p>
              )}
              <NoteMarkdown markdown={selected.markdown} />
              <div className="review__actions">
                <button
                  type="button"
                  className="button button--primary"
                  disabled={busy}
                  onClick={() => void decide(selected, 'approve')}
                >
                  Aprobar y guardar
                </button>
                <button
                  type="button"
                  className="button button--danger"
                  disabled={busy}
                  onClick={() => void decide(selected, 'reject')}
                >
                  Rechazar
                </button>
              </div>
            </article>
          )}
        </div>
      )}
    </section>
  )
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'el backend no responde'
}
