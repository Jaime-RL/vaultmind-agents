import type { AgentEvent, VaultGraph } from '../../api/contract.gen'

export type NodeKind = 'note' | 'copilot' | 'proposed'

export interface GraphNode {
  id: string
  title: string
  kind: NodeKind
  /** Número de enlaces: hace los nodos más conectados un poco más grandes. */
  degree: number
}

export interface GraphLink {
  source: string
  target: string
  proposed: boolean
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

type NodeProposedEvent = Extract<AgentEvent, { type: 'node_proposed' }>

/**
 * Une la bóveda real con las notas que van proponiendo los agentes.
 *
 * - Las notas de `_copilot/` (ya aprobadas) se marcan aparte.
 * - Cada `node_proposed` añade un nodo provisional enlazado a notas existentes;
 *   desaparece cuando la nota se aprueba y la bóveda se recarga con la nota real.
 */
export function buildGraphData(vault: VaultGraph, events: AgentEvent[]): GraphData {
  const nodes = new Map<string, GraphNode>()
  for (const n of vault.nodes) {
    nodes.set(n.id, { id: n.id, title: n.title, kind: n.id.startsWith('_copilot/') ? 'copilot' : 'note', degree: 0 })
  }
  const links: GraphLink[] = vault.links.map((l) => ({ ...l, proposed: false }))

  const approvedTitles = new Set([...nodes.values()].filter((n) => n.kind === 'copilot').map((n) => n.title))
  for (const event of events) {
    if (event.type !== 'node_proposed') continue
    const proposed = event as NodeProposedEvent
    // Si ya está aprobada, la nota real (en _copilot/) la sustituye.
    if (approvedTitles.has(proposed.title)) continue
    const id = `proposed:${proposed.proposal_id}`
    nodes.set(id, { id, title: proposed.title, kind: 'proposed', degree: 0 })
    for (const target of proposed.links) {
      if (nodes.has(target)) links.push({ source: id, target, proposed: true })
    }
  }

  for (const link of links) {
    const source = nodes.get(link.source)
    const target = nodes.get(link.target)
    if (source) source.degree += 1
    if (target) target.degree += 1
  }
  return { nodes: [...nodes.values()], links }
}
