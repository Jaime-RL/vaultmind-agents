import { useCallback, useEffect, useState } from 'react'
import { ApiError, getProposals, resolveProposal } from '../../api/client'
import type { Proposal } from '../../api/contract.gen'

export type ProposalsState =
  | { status: 'loading' }
  | { status: 'ready'; proposals: Proposal[] }
  | { status: 'error'; message: string }

type Resolution = 'approved' | 'rejected'

interface Options {
  /**
   * Cambia cada vez que puede haber propuestas nuevas (llega un node_proposed o
   * termina la investigación). Volvemos a pedir la lista entonces: en modo real el
   * backend guarda las propuestas al terminar de redactar, así que el evento puede
   * llegar un poco antes que la fila en SQLite. Pedirla otra vez al final lo cubre.
   */
  refreshKey: string
  onResolved: (id: string, status: Resolution) => void
}

/** Notas pendientes de revisión (GET /api/proposals?status=pending) y su aprobación o rechazo. */
export function useProposals({ refreshKey, onResolved }: Options) {
  const [state, setState] = useState<ProposalsState>({ status: 'loading' })
  // Id de la propuesta con una petición en curso (para desactivar sus botones).
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const fetchPending = useCallback(
    () =>
      getProposals('pending').then(
        (proposals): ProposalsState => ({ status: 'ready', proposals }),
        (error: unknown): ProposalsState => ({
          status: 'error',
          message: error instanceof Error ? error.message : 'Error desconocido',
        }),
      ),
    [],
  )

  // El estado solo se actualiza en el .then (cuando responde el backend), nunca de
  // forma síncrona dentro del efecto; `cancelled` descarta respuestas ya obsoletas.
  useEffect(() => {
    let cancelled = false
    void fetchPending().then((next) => !cancelled && setState(next))
    return () => {
      cancelled = true
    }
  }, [fetchPending, refreshKey])

  const load = useCallback(async () => setState(await fetchPending()), [fetchPending])

  const resolve = useCallback(
    async (id: string, action: 'approve' | 'reject', markdown?: string) => {
      setBusyId(id)
      setActionError(null)
      try {
        const updated = await resolveProposal(id, action, markdown)
        setState((current) =>
          current.status === 'ready'
            ? { status: 'ready', proposals: current.proposals.filter((p) => p.id !== id) }
            : current,
        )
        onResolved(id, updated.status === 'approved' ? 'approved' : 'rejected')
      } catch (error) {
        // 409 = otra pestaña (u otra persona) ya la resolvió: recargamos la lista.
        if (error instanceof ApiError && error.status === 409) {
          setActionError('Esta nota ya se había revisado. Lista actualizada.')
          await load()
        } else {
          setActionError(error instanceof Error ? error.message : 'No se pudo guardar la decisión.')
        }
      } finally {
        setBusyId(null)
      }
    },
    [load, onResolved],
  )

  return { state, busyId, actionError, resolve, reload: load }
}
