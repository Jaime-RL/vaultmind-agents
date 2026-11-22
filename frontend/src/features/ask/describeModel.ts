import type { AskResponse } from '../../api/contract.gen'
import { makeI18n, type I18n } from '../../i18n/context'
import { formatUsd, shortModel } from '../agents-panel/describeEvent'

/** Quién respondió, cuánto costó y si el SLM tuvo que escalar. */
export function describeModel(response: AskResponse, t: I18n['t'] = makeI18n('es').t): string {
  if (!response.model || !response.tier) return t('ask.noModel')
  const who = response.tier === 'slm' ? t('ask.modelSlm') : t('ask.modelLarge')
  const escalated = response.escalated ? ` · ${t('ask.escalated')}` : ''
  return `${who} · ${shortModel(response.model)} · ${formatUsd(response.cost_usd)}${escalated}`
}
