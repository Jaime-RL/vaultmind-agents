import type { AgentEvent } from '../../api/contract.gen'
import { shortModel } from '../../lib/format'

/** Texto de una línea del panel para cada tipo de evento. */
export function describeEvent(event: AgentEvent): string {
  switch (event.type) {
    case 'agent_thought':
      return event.text
    case 'tool_call':
      return `→ ${event.tool}(${Object.keys(event.args).length ? JSON.stringify(event.args) : ''})`
    case 'tool_result':
      return `← ${event.tool}: ${event.summary}`
    case 'route_decision':
      return `${event.task} → ${shortModel(event.model)}${event.escalated ? ' (escalada)' : ''} · ${event.reason}`
    case 'node_proposed':
      return `Nota propuesta: «${event.title}»`
    case 'run_finished':
      return `Investigación terminada: ${event.stats.notes_proposed} notas propuestas`
    case 'error':
      return event.message
  }
}
