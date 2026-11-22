import type { AgentEvent } from '../../api/contract.gen'

/**
 * Texto legible de una herramienta, para que el panel diga «Buscando en arXiv…»
 * en lugar de «search_arxiv». Las herramientas desconocidas se muestran tal cual:
 * si A añade una nueva, el panel sigue funcionando.
 */
export function describeToolCall(tool: string, args: Record<string, unknown>): string {
  const query = typeof args.query === 'string' ? args.query : undefined
  switch (tool) {
    case 'search_arxiv':
      return query ? `Buscando en arXiv: «${query}»` : 'Buscando en arXiv…'
    case 'search_semantic_scholar':
      return query ? `Buscando en Semantic Scholar: «${query}»` : 'Buscando en Semantic Scholar…'
    case 'find_gaps':
      return 'Buscando conceptos de la bóveda que aún no tienen nota…'
    case 'verify_claims':
      return 'Verificando las afirmaciones de la nota frente a sus fuentes…'
    case 'read_note':
      return typeof args.note === 'string' ? `Leyendo la nota «${args.note}»` : 'Leyendo una nota…'
    default:
      return `Usando la herramienta ${tool}…`
  }
}

/** Nombre corto del modelo: «qwen/qwen-2.5-7b-instruct» → «qwen-2.5-7b» (el completo va en el title). */
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
