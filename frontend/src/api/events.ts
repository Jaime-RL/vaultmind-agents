import { researchEventsUrl } from './client'
import type { AgentEvent } from './contract.gen'

// Todos los tipos de evento del contrato (events.schema.json). El backend envía
// cada mensaje SSE con `event: <type>`, y EventSource SOLO entrega a `onmessage`
// los mensajes sin tipo: hay que escuchar cada tipo con addEventListener.
// `satisfies` hace que TypeScript avise si el contrato añade un tipo y falta aquí.
export const EVENT_TYPES = [
  'agent_thought',
  'tool_call',
  'tool_result',
  'route_decision',
  'node_proposed',
  'run_finished',
  'error',
] as const satisfies readonly AgentEvent['type'][]

type MissingTypes = Exclude<AgentEvent['type'], (typeof EVENT_TYPES)[number]>
// Si esta línea da error de tipos, falta un tipo de evento del contrato en EVENT_TYPES.
const exhaustive: MissingTypes extends never ? true : never = true
void exhaustive

export interface RunSubscription {
  close: () => void
}

interface Handlers {
  onEvent: (event: AgentEvent) => void
  /** La conexión se perdió antes de run_finished / error. */
  onDisconnect: () => void
}

/**
 * Se suscribe al flujo SSE de una investigación.
 *
 * Decisión: si la conexión se corta, NO dejamos que EventSource reconecte solo.
 * El backend reenvía todos los eventos desde el principio a cada conexión nueva,
 * así que una reconexión automática duplicaría líneas y nodos. En su lugar
 * avisamos (onDisconnect) y la interfaz reconecta de forma explícita, vaciando
 * antes lo recibido (acción 'reset-events' del reductor).
 */
export function subscribeToRun(runId: string, handlers: Handlers): RunSubscription {
  const source = new EventSource(researchEventsUrl(runId))
  let done = false

  const close = () => {
    done = true
    source.close()
  }

  const listener = (message: MessageEvent<string>) => {
    let event: AgentEvent
    try {
      event = JSON.parse(message.data) as AgentEvent
    } catch {
      return // Un mensaje mal formado no debe tumbar toda la interfaz.
    }
    handlers.onEvent(event)
    // El flujo siempre termina con run_finished o error (contracts/README.md).
    if (event.type === 'run_finished' || event.type === 'error') close()
  }

  for (const type of EVENT_TYPES) source.addEventListener(type, listener as EventListener)

  source.onerror = () => {
    if (done) return
    close()
    handlers.onDisconnect()
  }

  return { close }
}
