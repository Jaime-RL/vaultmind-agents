import { useCallback, useEffect, useReducer, useRef } from 'react'
import { ApiError, startResearch } from '../../api/client'
import { subscribeToRun, type RunSubscription } from '../../api/events'
import { initialRunState, runReducer } from './runReducer'

/** Mensajes legibles para los errores HTTP que define el backend al lanzar una investigación. */
function startErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return 'Ya hay demasiadas investigaciones en marcha. Prueba en un minuto.'
    if (error.status === 503) return `El backend no puede investigar ahora: ${error.message}`
    return error.message
  }
  return 'No se pudo conectar con el backend.'
}

/**
 * Conecta la interfaz con una investigación: la lanza (POST /api/research), escucha
 * su flujo SSE y lo convierte en estado con runReducer.
 */
export function useResearchRun() {
  const [state, dispatch] = useReducer(runReducer, initialRunState)
  const subscription = useRef<RunSubscription | null>(null)

  const listen = useCallback((runId: string) => {
    subscription.current?.close()
    subscription.current = subscribeToRun(runId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onDisconnect: () => dispatch({ type: 'disconnected' }),
    })
  }, [])

  const start = useCallback(
    async (topic: string) => {
      subscription.current?.close()
      dispatch({ type: 'start', topic })
      try {
        const { run_id } = await startResearch(topic)
        dispatch({ type: 'started', runId: run_id })
        listen(run_id)
      } catch (error) {
        dispatch({ type: 'failed', message: startErrorMessage(error) })
      }
    },
    [listen],
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
