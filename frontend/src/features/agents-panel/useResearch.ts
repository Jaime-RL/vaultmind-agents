import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE, ApiError } from '../../api/client'
import type { AgentEvent, RunStats } from '../../api/contract.gen'
import { startResearch } from '../../api/endpoints'

export type ResearchStatus = 'idle' | 'starting' | 'running' | 'finished' | 'error'

// El backend manda cada evento SSE con «event: <tipo>», así que EventSource solo
// los entrega a quien escucha ESE tipo (onmessage no los recibe).
const EVENT_TYPES = [
  'agent_thought',
  'tool_call',
  'tool_result',
  'route_decision',
  'node_proposed',
  'run_finished',
  'error',
] as const

export interface ResearchState {
  status: ResearchStatus
  runId: string | null
  events: AgentEvent[]
  stats: RunStats | null
  error: string | null
}

const INITIAL: ResearchState = { status: 'idle', runId: null, events: [], stats: null, error: null }

/**
 * HU2 — Lanza una investigación (POST /api/research) y sigue sus eventos por SSE
 * hasta run_finished o error.
 */
export function useResearch() {
  const [state, setState] = useState<ResearchState>(INITIAL)
  const sourceRef = useRef<EventSource | null>(null)

  const close = () => {
    sourceRef.current?.close()
    sourceRef.current = null
  }

  // Al desmontar, cerramos la conexión.
  useEffect(() => close, [])

  const start = useCallback(async (topic: string) => {
    close()
    setState({ ...INITIAL, status: 'starting' })
    let runId: string
    try {
      runId = (await startResearch(topic)).run_id
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'el backend no responde'
      setState({ ...INITIAL, status: 'error', error: message })
      return
    }

    setState({ ...INITIAL, status: 'running', runId })
    const source = new EventSource(`${API_BASE}/api/research/${encodeURIComponent(runId)}/events`)
    sourceRef.current = source
    let opened = false

    source.onopen = () => {
      // Si la conexión se corta, EventSource reconecta solo y el backend repite la
      // investigación desde el principio: vaciamos la lista para no duplicar eventos.
      if (opened) setState((s) => ({ ...s, events: [] }))
      opened = true
    }

    for (const type of EVENT_TYPES) {
      source.addEventListener(type, (message) => {
        const event = JSON.parse((message as MessageEvent<string>).data) as AgentEvent
        setState((s) => {
          const next = { ...s, events: [...s.events, event] }
          if (event.type === 'run_finished') return { ...next, status: 'finished', stats: event.stats }
          if (event.type === 'error') return { ...next, status: 'error', error: event.message }
          return next
        })
        if (event.type === 'run_finished' || event.type === 'error') close()
      })
    }
  }, [])

  return { ...state, start }
}
