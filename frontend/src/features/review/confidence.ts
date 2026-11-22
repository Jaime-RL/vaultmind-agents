import type { ProposalReview } from '../../api/contract.gen'

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'unknown'

/**
 * Nivel de confianza de una nota según su revisión.
 * - high: todas las afirmaciones tienen respaldo.
 * - medium: al menos el 60 %.
 * - low: menos del 60 %, o ninguna afirmación contada (no hay nada que verificar).
 * - unknown: el Revisor no pudo revisarla.
 */
export function confidenceLevel(review: ProposalReview | null | undefined): ConfidenceLevel {
  if (!review) return 'unknown'
  if (review.claims === 0) return 'low'
  if (review.supported >= review.claims) return 'high'
  return review.supported / review.claims >= 0.6 ? 'medium' : 'low'
}

// El color nunca va solo: cada nivel tiene también su icono y su texto (daltonismo).
export const CONFIDENCE_ICON: Record<ConfidenceLevel, string> = {
  high: '✓',
  medium: '!',
  low: '✕',
  unknown: '?',
}

export function confidenceLabel(review: ProposalReview | null | undefined): string {
  if (!review) return 'Sin revisar'
  return `${review.supported}/${review.claims} respaldadas`
}
