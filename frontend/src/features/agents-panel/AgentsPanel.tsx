import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../../api/contract.gen'
import { TierDot } from '../../components/TierDot'
import { AGENT_LABELS, TIER_LABELS } from '../graph/colors'
import { describeToolCall, eventKey, formatUsd, plural, shortModel } from './describeEvent'
import type { RunState } from './runReducer'

interface Props {
  state: RunState
  onReconnect: () => void
}

export function AgentsPanel({ state, onReconnect }: Props) {
  const logRef = useRef<HTMLOListElement>(null)

  // Desplaza al último evento, salvo que el usuario haya subido a leer algo anterior.
  useEffect(() => {
    const log = logRef.current
    if (!log) return
    const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 120
    if (nearBottom) log.scrollTop = log.scrollHeight
  }, [state.events.length])

  if (state.status === 'idle') {
    return (
      <p className="panel-empty">
        Escribe un tema arriba y pulsa <strong>Investigar</strong>: aquí verás en directo qué
        piensa y qué hace cada agente.
      </p>
    )
  }

  return (
    <div className="agents-panel">
      {state.topic && (
        <p className="agents-panel__topic">
          Investigación: <strong>{state.topic}</strong>
        </p>
      )}

      {state.status === 'starting' && (
        <p className="panel-empty" role="status">
          Lanzando la investigación…
        </p>
      )}

      {/* role="log" + aria-live: los lectores de pantalla anuncian las líneas nuevas. */}
      <ol ref={logRef} className="event-log" role="log" aria-live="polite" aria-label="Razonamiento de los agentes">
        {state.events.map((event, index) => (
          <EventLine key={eventKey(event, index)} event={event} />
        ))}
      </ol>

      {state.status === 'running' && (
        <p className="agents-panel__running" role="status">
          <span className="spinner" aria-hidden="true" /> Los agentes están trabajando…
        </p>
      )}

      {state.status === 'error' && (
        <div className="notice notice--error" role="alert">
          <p>{state.error}</p>
          {state.disconnected && (
            <button type="button" className="button" onClick={onReconnect}>
              Reconectar
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function AgentChip({ event }: { event: AgentEvent }) {
  return (
    // El agente se identifica por su nombre, no por un color (ver colors.ts).
    <span className="agent-chip">{AGENT_LABELS[event.agent]}</span>
  )
}

function EventLine({ event }: { event: AgentEvent }) {
  switch (event.type) {
    case 'agent_thought':
      return (
        <li className="event event--thought">
          <AgentChip event={event} />
          <span>{event.text}</span>
        </li>
      )
    case 'tool_call':
      return (
        <li className="event event--tool">
          <AgentChip event={event} />
          <span>{describeToolCall(event.tool, event.args as Record<string, unknown>)}</span>
        </li>
      )
    case 'tool_result':
      return (
        <li className="event event--result">
          <span className="event__indent" aria-hidden="true">
            ↳
          </span>
          <span>{event.summary}</span>
        </li>
      )
    case 'route_decision':
      return (
        <li className="event event--route">
          <span className={`tier-badge tier-badge--${event.tier}`}>
            <TierDot tier={event.tier} /> {TIER_LABELS[event.tier]}
          </span>
          <span>
            <code>{event.task}</code> con {shortModel(event.model)}
            {event.escalated && <strong className="escalated"> · escalado</strong>}
            <span className="event__reason"> — {event.reason}</span>
          </span>
        </li>
      )
    case 'node_proposed':
      return (
        <li className="event event--proposed">
          <AgentChip event={event} />
          <span>
            ✨ Nota propuesta: <strong>{event.title}</strong>
          </span>
        </li>
      )
    case 'run_finished':
      return (
        <li className="event event--finished">
          <strong>Investigación terminada</strong>
          <span>
            {plural(event.stats.notes_proposed, 'nota propuesta', 'notas propuestas')} · coste{' '}
            {formatUsd(event.stats.cost_usd)} · ahorro {formatUsd(event.stats.savings_usd)} frente a
            usar solo el modelo grande · {plural(event.stats.escalations, 'escalada')} ·{' '}
            {Math.round(event.stats.duration_s)} s
          </span>
        </li>
      )
    case 'error':
      return (
        <li className="event event--error">
          <AgentChip event={event} />
          <span>{event.message}</span>
        </li>
      )
  }
}
