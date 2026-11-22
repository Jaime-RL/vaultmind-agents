import type { AskResponse } from '../../api/contract.gen'
import { formatUsd, shortModel } from '../agents-panel/describeEvent'

/** Quién respondió, cuánto costó y si el SLM tuvo que escalar. */
export function describeModel(response: AskResponse): string {
  if (!response.model || !response.tier) return 'Sin modelo: búsqueda en tus notas'
  const who = response.tier === 'slm' ? 'SLM' : 'Modelo grande'
  const escalated = response.escalated ? ' · escalado: el SLM no citó tus notas' : ''
  return `${who} · ${shortModel(response.model)} · ${formatUsd(response.cost_usd)}${escalated}`
}
