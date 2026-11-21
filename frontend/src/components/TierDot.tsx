import type { Tier } from '../api/contract.gen'
import { TIER_COLORS } from '../features/graph/colors'

/**
 * Punto de color del modelo (verde SLM, azul grande). Se dibuja con CSS y no con
 * los emojis 🟢/🔵: según el sistema, los emojis salen en gris o con otros tonos,
 * y estos colores están validados para daltonismo (ver colors.ts). Siempre va
 * acompañado del nombre del modelo, así que no depende solo del color.
 */
export function TierDot({ tier }: { tier: Tier }) {
  return <span className="tier-dot" style={{ background: TIER_COLORS[tier] }} aria-hidden="true" />
}
