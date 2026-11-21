import { useState, type FormEvent } from 'react'
import { AGENT_LABEL, formatPercent, formatUsd } from '../../lib/format'
import { describeEvent } from './describeEvent'
import type { useResearch } from './useResearch'

type Research = ReturnType<typeof useResearch>

const SUGGESTED_TOPIC = 'Function calling y routing de modelos para un chatbot de clima con SLMs'

/** HU2 — Lanzar una investigación y ver a los agentes trabajar en directo. */
export default function AgentsPanel({ research }: { research: Research }) {
  const [topic, setTopic] = useState(SUGGESTED_TOPIC)
  const busy = research.status === 'starting' || research.status === 'running'

  function submit(event: FormEvent) {
    event.preventDefault()
    if (topic.trim().length >= 3 && !busy) void research.start(topic.trim())
  }

  const { stats } = research

  return (
    <section className="panel agents" aria-labelledby="agents-title">
      <header className="panel__header">
        <h2 id="agents-title">Investigación</h2>
        {research.status === 'running' && <span className="pulse">Agentes trabajando…</span>}
      </header>

      <form className="research-form" onSubmit={submit}>
        <label htmlFor="topic" className="visually-hidden">
          Tema a investigar
        </label>
        <input
          id="topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="¿Qué quieres investigar para tu TFG?"
          maxLength={200}
          disabled={busy}
        />
        <button type="submit" className="button button--primary" disabled={busy || topic.trim().length < 3}>
          {busy ? 'Investigando…' : 'Investigar'}
        </button>
      </form>

      {research.status === 'error' && research.error && (
        <p className="notice notice--error" role="alert">
          {research.error}
        </p>
      )}

      {stats && (
        <p className="notice notice--ok" role="status">
          {stats.notes_proposed} notas propuestas · coste {formatUsd(stats.cost_usd)} · ahorro{' '}
          {formatPercent(stats.baseline_cost_usd > 0 ? stats.savings_usd / stats.baseline_cost_usd : 0)} ·{' '}
          {stats.escalations} {stats.escalations === 1 ? 'escalada' : 'escaladas'}
        </p>
      )}

      {research.events.length > 0 && (
        <ol className="timeline" aria-label="Eventos de la investigación" aria-live="polite">
          {research.events.map((event, index) => (
            <li key={index} className={`timeline__item timeline__item--${event.type}`}>
              <span className={`agent agent--${event.agent}`}>{AGENT_LABEL[event.agent] ?? event.agent}</span>
              {event.type === 'route_decision' && (
                <span className={`tier tier--${event.tier}`}>{event.tier === 'slm' ? 'SLM' : 'Grande'}</span>
              )}
              <span className="timeline__text">{describeEvent(event)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
