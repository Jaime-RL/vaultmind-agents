import { useCallback, useEffect, useReducer, useRef } from 'react'
import { ApiError, startResearch } from '../../api/client'
import type { ContentLanguage } from '../../api/contract.gen'
import { useI18n, type I18n } from '../../i18n/context'
import { subscribeToRun, type RunSubscription } from '../../api/events'
import { initialRunState, runReducer } from './runReducer'

/** Mensajes legibles para los errores HTTP que define el backend al lanzar una investigación. */
function startErrorMessage(error: unknown, t: I18n['t']): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return t('research.error.busy')
    if (error.status === 503) return t('research.error.unavailable', { detail: error.message })
    return error.message
  }
  return t('research.error.network')
}

/**
 * Conecta la interfaz con una investigación: la lanza (POST /api/research), escucha
 * su flujo SSE y lo convierte en estado con runReducer.
 */
export function useResearchRun() {
  const [state, dispatch] = useReducer(runReducer, initialRunState)
  const subscription = useRef<RunSubscription | null>(null)
  const { lang, t } = useI18n()

  const listen = useCallback((runId: string) => {
    subscription.current?.close()
    subscription.current = subscribeToRun(runId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onDisconnect: () => dispatch({ type: 'disconnected' }),
    })
  }, [])

  const start = useCallback(
    async (topic: string, language: ContentLanguage = 'auto') => {
      subscription.current?.close()
      dispatch({ type: 'start', topic })
      try {
        // Los mensajes de los agentes llegan en el idioma de la interfaz.
        const { run_id } = await startResearch(topic, language, lang)
        dispatch({ type: 'started', runId: run_id })
        listen(run_id)
      } catch (error) {
        dispatch({ type: 'failed', message: startErrorMessage(error, t) })
      }
    },
    [listen, lang, t],
  )

  /** Reconecta al mismo run tras perder la conexión (el servidor reenvía todo). */
  const reconnect = useCallback(() => {
    if (!state.runId) return
    dispatch({ type: 'reset-events' })
    listen(state.runId)
  }, [listen, state.runId])

  const markResolved = useCallback(
    (id: string, status: 'approved' | 'rejected') => dispatch({ type: 'proposal-resolved', id, status }),
    [],
  )

  // Al desmontar, cerramos la conexión para no dejar el SSE abierto.
  useEffect(() => () => subscription.current?.close(), [])

  return { state, start, reconnect, markResolved }
}
