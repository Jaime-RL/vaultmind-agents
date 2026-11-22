import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../../api/contract.gen'
import { TierDot } from '../../components/TierDot'
import { useI18n } from '../../i18n/context'
import type { MessageKey } from '../../i18n/messages'
import { describeToolCall, eventKey, formatUsd, shortModel } from './describeEvent'
import type { RunState } from './runReducer'

interface Props {
  state: RunState
  onReconnect: () => void
  /** Temas de ejemplo de la pantalla de bienvenida: lanzan una investigación en un clic. */
  onExample?: (topic: string) => void
}

const EXAMPLE_TOPICS = [
  'multi-token prediction',
  'speculative decoding',
  'retrieval-augmented generation',
]

export function AgentsPanel({ state, onReconnect, onExample }: Props) {
  const logRef = useRef<HTMLOListElement>(null)
  const { t } = useI18n()

  // Desplaza al último evento, salvo que el usuario haya subido a leer algo anterior.
  useEffect(() => {
    const log = logRef.current
    if (!log) return
    const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 120
    if (nearBottom) log.scrollTop = log.scrollHeight
  }, [state.events.length])

  if (state.status === 'idle') {
    return (
      <div className="welcome">
        <p className="panel-empty">{t('welcome.intro')}</p>
        <ol className="welcome__steps">
          {(['explorer', 'researcher', 'writer', 'reviewer'] as const).map((agent) => (
            <li key={agent}>
              <strong>{t(`agent.${agent}`)}</strong> {t(`welcome.${agent}`)}
            </li>
          ))}
        </ol>
        <p className="welcome__hint">{t('welcome.smartroute')}</p>
        {onExample && (
          <p className="welcome__examples">
            {t('welcome.try')}{' '}
            {EXAMPLE_TOPICS.map((topic) => (
              <button key={topic} type="button" className="chip" onClick={() => onExample(topic)}>
                {topic}
              </button>
            ))}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="agents-panel">
      {state.topic && (
        <p className="agents-panel__topic">
          {t('agents.topic')} <strong>{state.topic}</strong>
        </p>
      )}

      {state.status === 'starting' && (
        <p className="panel-empty" role="status">
          {t('agents.starting')}
        </p>
      )}

      {/* role="log" + aria-live: los lectores de pantalla anuncian las líneas nuevas. */}
      <ol ref={logRef} className="event-log" role="log" aria-live="polite" aria-label={t('agents.log')}>
        {state.events.map((event, index) => (
          <EventLine key={eventKey(event, index)} event={event} />
        ))}
      </ol>

      {state.status === 'running' && (
        <p className="agents-panel__running" role="status">
          <span className="spinner" aria-hidden="true" /> {t('agents.running')}
        </p>
      )}

      {state.status === 'error' && (
        <div className="notice notice--error" role="alert">
          <p>{state.disconnected ? t('research.error.disconnected') : state.error}</p>
          {state.disconnected && (
            <button type="button" className="button" onClick={onReconnect}>
              {t('agents.reconnect')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function AgentChip({ event }: { event: AgentEvent }) {
  const { t } = useI18n()
  return (
    // El agente se identifica por su nombre, no por un color (ver colors.ts).
    <span className="agent-chip">{t(`agent.${event.agent}`)}</span>
  )
}

function EventLine({ event }: { event: AgentEvent }) {
  const { t, tn } = useI18n()
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
          <span>{describeToolCall(event.tool, event.args as Record<string, unknown>, t)}</span>
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
            <TierDot tier={event.tier} /> {t(`tier.${event.tier}`)}
          </span>
          <span>
            <code>{event.task}</code> {t('event.with')} {shortModel(event.model)}
            {event.escalated && <strong className="escalated"> · {t('event.escalated')}</strong>}
            {/* El motivo se describe aquí (en el idioma de la interfaz) a partir del nivel. */}
            <span className="event__reason" title={event.reason}>
              {' '}
              — {t(routeReasonKey(event.tier, event.escalated))}
            </span>
          </span>
        </li>
      )
    case 'node_proposed':
      return (
        <li className="event event--proposed">
          <AgentChip event={event} />
          <span>
            ✨ {t('event.proposed')} <strong>{event.title}</strong>
          </span>
        </li>
      )
    case 'run_finished':
      return (
        <li className="event event--finished">
          <strong>{t('event.finished')}</strong>
          <span>
            {t('event.summary', {
              notes: tn('event.notes', event.stats.notes_proposed),
              cost: formatUsd(event.stats.cost_usd),
              savings: formatUsd(event.stats.savings_usd),
              escalations: tn('event.escalations', event.stats.escalations),
              seconds: Math.round(event.stats.duration_s),
            })}
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

function routeReasonKey(tier: 'slm' | 'large', escalated: boolean): MessageKey {
  if (escalated) return 'event.reason.escalated'
  return tier === 'slm' ? 'event.reason.slm' : 'event.reason.large'
}
