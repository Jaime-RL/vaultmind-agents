// Formato de cifras para los paneles. Los costes de una investigación son de
// fracciones de céntimo, así que se muestran con más decimales que un precio normal.

export function formatUsd(value: number): string {
  if (value === 0) return '0 $'
  const digits = Math.abs(value) < 0.01 ? 5 : 3
  return `${value.toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits })} $`
}

export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)} %`
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1).replace('.', ',')} s` : `${Math.round(ms)} ms`
}

/** «qwen/qwen-2.5-72b-instruct» → «qwen-2.5-72b-instruct»: el prefijo del proveedor sobra en pantalla. */
export function shortModel(model: string): string {
  return model.includes('/') ? model.slice(model.lastIndexOf('/') + 1) : model
}

export const AGENT_LABEL: Record<string, string> = {
  explorer: 'Explorador',
  researcher: 'Investigador',
  writer: 'Redactor',
  reviewer: 'Revisor',
  system: 'Sistema',
}
