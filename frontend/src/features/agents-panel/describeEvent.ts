import type { AgentEvent } from '../../api/contract.gen'
import { makeI18n, type I18n } from '../../i18n/context'

/**
 * Texto legible de una herramienta, para que el panel diga «Buscando en arXiv…»
 * en lugar de «search_arxiv». Las herramientas desconocidas se muestran tal cual:
 * si A añade una nueva, el panel sigue funcionando.
 */
/** Qué está haciendo una herramienta, en el idioma de la interfaz. */
export function describeToolCall(
  tool: string,
  args: Record<string, unknown>,
  t: I18n['t'] = makeI18n('es').t,
): string {
  const query = typeof args.query === 'string' ? args.query : undefined
  switch (tool) {
    case 'search_arxiv':
      return query ? t('tool.arxiv', { query }) : t('tool.arxiv.noQuery')
    case 'search_semantic_scholar':
      return query ? t('tool.s2', { query }) : t('tool.s2.noQuery')
    case 'find_gaps':
      return t('tool.findGaps')
    case 'verify_claims':
      return t('tool.verify')
    case 'read_note':
      return typeof args.note === 'string' ? t('tool.readNote', { note: args.note }) : t('tool.readNote.noNote')
    default:
      return t('tool.other', { tool })
  }
}

export function shortModel(model: string): string {
  return (model.split('/').at(-1) ?? model).replace(/-instruct$/, '')
}

export function formatUsd(value: number): string {
  // Los costes de una investigación son de milésimas de dólar: 4 decimales.
  return `$${value.toFixed(value < 1 ? 4 : 2)}`
}

/** Clave estable de un evento para las listas de React (el contrato no trae id). */
export function eventKey(event: AgentEvent, index: number): string {
  return `${index}-${event.type}-${event.ts}`
}

/** «1 nota», «3 notas»: concordancia de número para los recuentos del panel. */
export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}
