import { describe, expect, it } from 'vitest'
import type { VaultGraph } from '../../api/contract.gen'
import { PROPOSED_COLOR } from './colors'
import { loadDemoProposals } from '../../test/fixtures'
import { buildGraphData, mergeProposed, type ProposedNode } from './graphData'

const vault: VaultGraph = {
  nodes: [
    { id: 'rag/Chunking', title: 'Chunking', path: 'rag/Chunking.md', tags: [] },
    { id: 'rag/Embeddings', title: 'Embeddings', path: 'rag/Embeddings.md', tags: ['ml'] },
    { id: 'Ideas sueltas', title: 'Ideas sueltas', path: 'Ideas sueltas.md', tags: [] },
  ],
  links: [{ source: 'rag/Chunking', target: 'rag/Embeddings' }],
}

const proposal = (overrides: Partial<ProposedNode> = {}): ProposedNode => ({
  id: 'p-001',
  title: 'LoRA',
  links: ['rag/Embeddings'],
  agent: 'writer',
  tier: 'large',
  status: 'pending',
  ...overrides,
})

describe('buildGraphData', () => {
  it('convierte todas las notas y enlaces de la bóveda', () => {
    const data = buildGraphData(vault)

    expect(data.nodes.map((n) => n.id)).toEqual(['rag/Chunking', 'rag/Embeddings', 'Ideas sueltas'])
    expect(data.links).toEqual([{ source: 'rag/Chunking', target: 'rag/Embeddings', proposed: false }])
    expect(data.nodes.every((n) => n.kind === 'note')).toBe(true)
  })

  it('agrupa por carpeta y da el mismo color a las notas de la misma carpeta', () => {
    const [chunking, embeddings, ideas] = buildGraphData(vault).nodes

    expect(chunking?.folder).toBe('rag')
    expect(ideas?.folder).toBe('(raíz)')
    expect(chunking?.color).toBe(embeddings?.color)
  })

  it('hace más grandes las notas con más enlaces', () => {
    const [chunking, , ideas] = buildGraphData(vault).nodes

    expect(chunking!.val).toBeGreaterThan(ideas!.val)
  })

  it('añade las propuestas con el color de acento y enlazadas a notas existentes', () => {
    const data = buildGraphData(vault, [proposal()])
    const node = data.nodes.find((n) => n.id === 'p-001')

    expect(node).toMatchObject({ kind: 'proposed', agent: 'writer', tier: 'large' })
    expect(node?.color).toBe(PROPOSED_COLOR)
    expect(data.links).toContainEqual({ source: 'p-001', target: 'rag/Embeddings', proposed: true })
  })

  it('descarta enlaces a notas que no existen', () => {
    const data = buildGraphData(vault, [proposal({ links: ['no/existe', 'rag/Chunking'] })])

    expect(data.links.filter((l) => l.proposed)).toEqual([
      { source: 'p-001', target: 'rag/Chunking', proposed: true },
    ])
  })

  it('quita las propuestas rechazadas', () => {
    const data = buildGraphData(vault, [proposal({ status: 'rejected' })])

    expect(data.nodes.some((n) => n.id === 'p-001')).toBe(false)
    expect(data.links.some((l) => l.proposed)).toBe(false)
  })
})

describe('buildGraphData: notas aprobadas', () => {
  it('no duplica una nota aprobada cuando la bóveda recargada ya la contiene', () => {
    const reloaded: VaultGraph = {
      ...vault,
      nodes: [...vault.nodes, { id: '_copilot/LoRA', title: 'LoRA', path: '_copilot/LoRA.md', tags: [] }],
    }

    const data = buildGraphData(reloaded, [proposal({ status: 'approved' })])

    expect(data.nodes.filter((n) => n.title === 'LoRA')).toHaveLength(1)
    expect(data.nodes.find((n) => n.title === 'LoRA')?.kind).toBe('note')
  })

  it('mantiene la nota aprobada mientras la bóveda aún no se ha recargado', () => {
    const data = buildGraphData(vault, [proposal({ status: 'approved' })])

    expect(data.nodes.some((n) => n.id === 'p-001')).toBe(true)
  })
})

describe('mergeProposed', () => {
  const saved = loadDemoProposals()

  it('al recargar la página recupera las notas pendientes guardadas', () => {
    const merged = mergeProposed([], saved)

    expect(merged.map((p) => p.id)).toEqual(saved.map((p) => p.id))
    expect(merged.every((p) => p.status === 'pending' && p.tier === undefined)).toBe(true)
  })

  it('no duplica las de la investigación en curso ni recupera las ya resueltas', () => {
    const live: ProposedNode[] = [
      { id: saved[0]!.id, title: 'x', links: [], agent: 'writer', tier: 'large', status: 'pending' },
    ]
    const resolved = { ...saved[1]!, status: 'approved' as const }

    const merged = mergeProposed(live, [saved[0]!, resolved, saved[2]!])

    expect(merged.map((p) => p.id)).toEqual([saved[0]!.id, saved[2]!.id])
    expect(merged[0]!.tier).toBe('large') // se conserva el dato en directo
  })
})
