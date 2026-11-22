import type { RouteDecision } from '../../api/contract.gen'

export interface RouteCounts {
  slm: number
  large: number
  escalations: number
}

/** Cuántas llamadas ha resuelto cada modelo, contadas en directo con los route_decision. */
export function routeCounts(decisions: RouteDecision[]): RouteCounts {
  return decisions.reduce<RouteCounts>(
    (acc, d) => ({
      slm: acc.slm + (d.tier === 'slm' ? 1 : 0),
      large: acc.large + (d.tier === 'large' ? 1 : 0),
      escalations: acc.escalations + (d.escalated ? 1 : 0),
    }),
    { slm: 0, large: 0, escalations: 0 },
  )
}

/** Ahorro relativo frente a usar solo el modelo grande (0-1), o null si aún no hay coste. */
export function savingsShare(costUsd: number, baselineUsd: number): number | null {
  if (baselineUsd <= 0) return null
  return Math.max(0, 1 - costUsd / baselineUsd)
}
