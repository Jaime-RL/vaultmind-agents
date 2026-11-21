import type { Agent, Tier } from '../../api/contract.gen'

// Colores validados con el validador de la guía de visualización (scripts/validate_palette.js,
// modo oscuro, todos los pares) para que se distingan también con daltonismo:
//
// - Nota propuesta: UN solo acento (magenta). Se descartó «un color por agente»:
//   ninguna combinación de 4 tonos supera la separación para daltonismo junto al
//   verde y el azul del modelo, y en la práctica todas las notas las propone el
//   Redactor, así que el color por agente no aportaba información.
// - Modelo: verde (SLM) y azul (grande), en el anillo que rodea a la nota.
//   Magenta frente a verde queda en la banda de aviso para deuteranopía: por eso
//   el anillo va separado de la esfera y la leyenda (y el panel) lo nombran.
export const PROPOSED_COLOR = '#d55181'

export const AGENT_LABELS: Record<Agent, string> = {
  explorer: 'Explorador',
  researcher: 'Investigador',
  writer: 'Redactor',
  reviewer: 'Revisor',
  system: 'Sistema',
}

// El modelo que hizo la tarea: verde = SLM (barato), azul = modelo grande.
export const TIER_COLORS: Record<Tier, string> = {
  slm: '#2ea043',
  large: '#388bfd',
}

export const TIER_LABELS: Record<Tier, string> = {
  slm: 'SLM',
  large: 'Modelo grande',
}

/** Versión corta para tablas estrechas. */
export const TIER_SHORT: Record<Tier, string> = {
  slm: 'SLM',
  large: 'Grande',
}

// Notas existentes: tonos neutros (gris azulado) que varían solo en luminosidad por
// carpeta. Nada de rosas ni violetas: se confundirían con los colores de los agentes,
// y la idea es que las notas nuevas destaquen sobre la bóveda de un vistazo.
const FOLDER_PALETTE = ['#4f5d75', '#5f6e88', '#6f7f99', '#8090a8', '#56677f', '#687a92', '#7a8ba3']

export function folderColor(folder: string): string {
  // Hash estable: la misma carpeta tiene siempre el mismo color entre recargas.
  let hash = 0
  for (const char of folder) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return FOLDER_PALETTE[hash % FOLDER_PALETTE.length] ?? FOLDER_PALETTE[0]!
}
