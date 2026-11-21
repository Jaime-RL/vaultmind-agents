import type { Agent, AgentEvent, RouteDecision, RunStats, Tier } from '../../api/contract.gen'
import type { ProposedNode } from '../graph/graphData'

/**
 * Estado de una investigación en la interfaz, construido SOLO a partir de los
 * eventos SSE del contrato. Toda la lógica vive en este reductor puro: dado el
 * mismo flujo de eventos produce siempre el mismo estado, lo que permite probar la
 * interfaz en directo reproduciendo fixtures/run_example.jsonl sin red ni temporizadores.
 */
export interface RunState {
  status: 'idle' | 'starting' | 'running' | 'finished' | 'error'
  topic?: string
  runId?: string
  /** Todos los eventos recibidos, en orden: es lo que pinta el panel de agentes. */
  events: AgentEvent[]
  proposed: ProposedNode[]
  routeDecisions: RouteDecision[]
  stats?: RunStats
  error?: string
  /** true si el error es solo que se cortó la conexión SSE: se puede reconectar. */
  disconnected?: boolean
  /** Último modelo usado por cada agente, para deducir el de cada nota propuesta. */
  lastTierByAgent: Partial<Record<Agent, Tier>>
}

export type RunAction =
  | { type: 'start'; topic: string }
  | { type: 'started'; runId: string }
  | { type: 'event'; event: AgentEvent }
  | { type: 'failed'; message: string }
  | { type: 'disconnected' }
  /** Antes de reconectar: el servidor vuelve a enviar todos los eventos desde el principio. */
  | { type: 'reset-events' }
  | { type: 'proposal-resolved'; id: string; status: 'approved' | 'rejected' }

export const initialRunState: RunState = {
  status: 'idle',
  events: [],
  proposed: [],
  routeDecisions: [],
  lastTierByAgent: {},
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'start':
      // Una investigación nueva empieza de cero, pero conserva las propuestas
      // anteriores aún pendientes: siguen en el grafo hasta que se revisen.
      return {
        ...initialRunState,
        status: 'starting',
        topic: action.topic,
        proposed: state.proposed.filter((p) => p.status === 'pending'),
      }
    case 'started':
      return { ...state, status: 'running', runId: action.runId }
    case 'failed':
      return { ...state, status: 'error', error: action.message, disconnected: false }
    case 'disconnected':
      return {
        ...state,
        status: 'error',
        error: 'Se perdió la conexión con la investigación.',
        disconnected: true,
      }
    case 'reset-events': {
      const fromThisRun = new Set(
        state.events.flatMap((e) => (e.type === 'node_proposed' ? [e.proposal_id] : [])),
      )
      return {
        ...state,
        status: 'running',
        error: undefined,
        disconnected: false,
        events: [],
        routeDecisions: [],
        lastTierByAgent: {},
        // Las propuestas de esta investigación volverán a llegar con la reproducción.
        proposed: state.proposed.filter((p) => !fromThisRun.has(p.id)),
      }
    }
    case 'proposal-resolved':
      return {
        ...state,
        proposed: state.proposed.map((p) => (p.id === action.id ? { ...p, status: action.status } : p)),
      }
    case 'event':
      return applyEvent(state, action.event)
  }
}

function applyEvent(state: RunState, event: AgentEvent): RunState {
  // Los eventos de otra investigación (una conexión antigua que aún emite) se ignoran.
  if (state.runId && event.run_id !== state.runId) return state

  const next: RunState = { ...state, events: [...state.events, event] }

  switch (event.type) {
    case 'route_decision':
      return {
        ...next,
        routeDecisions: [...state.routeDecisions, event],
        lastTierByAgent: { ...state.lastTierByAgent, [event.agent]: event.tier },
      }
    case 'node_proposed':
      if (state.proposed.some((p) => p.id === event.proposal_id)) return next
      return {
        ...next,
        proposed: [
          ...state.proposed,
          {
            id: event.proposal_id,
            title: event.title,
            links: event.links,
            agent: event.agent,
            // Supuesto: la nota la escribió el último modelo que usó ese agente. En el
            // backend el route_decision del Redactor llega justo antes de cada node_proposed.
            tier: state.lastTierByAgent[event.agent],
            status: 'pending',
          },
        ],
      }
    case 'run_finished':
      return { ...next, status: 'finished', stats: event.stats }
    case 'error':
      return { ...next, status: 'error', error: event.message }
    default:
      return next
  }
}
