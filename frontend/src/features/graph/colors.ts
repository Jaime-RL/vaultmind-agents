import type { Agent, Tier } from '../../api/contract.gen'

// Un color por agente para los nodos que proponen (y para sus líneas en el panel).
// Elegidos para distinguirse entre sí y leerse bien sobre fondo oscuro.
export const AGENT_COLORS: Record<Agent, string> = {
  explorer: '#f2cc60', // amarillo
  researcher: '#a371f7', // violeta
  writer: '#ff7b72', // coral
  reviewer: '#39c5cf', // turquesa
  system: '#8b949e', // gris
}

export const AGENT_LABELS: Record<Agent, string> = {
  explorer: 'Explorador',
  researcher: 'Investigador',
  writer: 'Redactor',
  reviewer: 'Revisor',
  system: 'Sistema',
}

// El modelo que hizo la tarea: verde = SLM (barato), azul = modelo grande.
export const TIER_COLORS: Record<Tier, string> = {
  slm: '#3fb950',
  large: '#58a6ff',
}

export const TIER_LABELS: Record<Tier, string> = {
  slm: 'SLM',
  large: 'Modelo grande',
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
