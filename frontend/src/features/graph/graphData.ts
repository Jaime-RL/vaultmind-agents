import type { Agent, Proposal, Tier, VaultGraph } from '../../api/contract.gen'
import { folderColor, PROPOSED_COLOR } from './colors'

/** Nota propuesta por los agentes que todavía no está en la bóveda. */
export interface ProposedNode {
  id: string // proposal_id
  title: string
  links: string[] // ids de notas existentes
  agent: Agent
  // El contrato no dice qué modelo escribió cada nota en node_proposed: lo deducimos
  // del último route_decision de ese agente (ver runReducer). Puede faltar.
  tier?: Tier
  status: 'pending' | 'approved' | 'rejected'
}

export interface GraphNode {
  id: string
  title: string
  kind: 'note' | 'proposed'
  color: string
  /** Tamaño relativo (nodeVal): crece con el número de enlaces. */
  val: number
  folder?: string
  agent?: Agent
  tier?: Tier
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

/**
 * Une la bóveda y las notas propuestas en el formato de react-force-graph.
 *
 * Es una función pura (sin React ni WebGL) para poder probar con detalle lo que
 * se pinta: qué nodos aparecen, sus colores y qué enlaces se descartan.
 */
export function buildGraphData(vault: VaultGraph, proposed: ProposedNode[] = []): GraphData {
  const degree = new Map<string, number>()
  const bump = (id: string) => degree.set(id, (degree.get(id) ?? 0) + 1)
  for (const link of vault.links) {
    bump(link.source)
    bump(link.target)
  }

  const known = new Set(vault.nodes.map((node) => node.id))
  const knownTitles = new Set(vault.nodes.map((node) => node.title))

  const nodes: GraphNode[] = vault.nodes.map((node) => {
    // id = ruta sin extensión ("rag/Chunking"): la primera parte es la carpeta.
    const folder = node.id.includes('/') ? node.id.split('/')[0]! : '(raíz)'
    return {
      id: node.id,
      title: node.title,
      kind: 'note',
      folder,
      color: folderColor(folder),
      val: 1 + (degree.get(node.id) ?? 0) * 0.5,
    }
  })

  const links: GraphLink[] = vault.links.map((link) => ({ ...link, proposed: false }))

  for (const proposal of proposed) {
    // Rechazadas: desaparecen del grafo. Aprobadas: siguen, ya como parte de la bóveda.
    if (proposal.status === 'rejected') continue
    // Una nota aprobada se escribe en _copilot/<título>.md: cuando la bóveda se recarga
    // ya aparece como nota normal, así que no la duplicamos como propuesta.
    if (proposal.status === 'approved' && knownTitles.has(proposal.title)) continue
    nodes.push({
      id: proposal.id,
      title: proposal.title,
      kind: 'proposed',
      agent: proposal.agent,
      tier: proposal.tier,
      color: PROPOSED_COLOR,
      val: 4,
    })
    for (const target of proposal.links) {
      // Un enlace a un nodo que no existe haría fallar el layout: se descarta.
      if (known.has(target)) links.push({ source: proposal.id, target, proposed: true })
    }
  }

  return { nodes, links }
}

/**
 * Nodos propuestos del grafo: los de la investigación en curso y las propuestas pendientes
 * guardadas que aún no están (al recargar la página la investigación ya no está en memoria).
 * De una propuesta guardada no se sabe con qué nivel de modelo se escribió: sin anillo.
 */
export function mergeProposed(live: ProposedNode[], pending: Proposal[]): ProposedNode[] {
  const known = new Set(live.map((p) => p.id))
  const restored = pending
    .filter((p) => p.status === 'pending' && !known.has(p.id))
    .map<ProposedNode>((p) => ({
      id: p.id,
      title: p.title,
      links: p.links,
      agent: p.agent,
      tier: undefined,
      status: 'pending',
    }))
  return restored.length ? [...live, ...restored] : live
}
