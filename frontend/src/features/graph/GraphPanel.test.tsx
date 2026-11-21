import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AgentEvent, VaultGraph } from '../../api/contract.gen'
import { stubRoutes } from '../../test/fetchRoutes'
import GraphPanel from './GraphPanel'
import { buildGraphData, type GraphData } from './graphData'

// jsdom no tiene WebGL: sustituimos el lienzo por una lista con lo que recibiría.
vi.mock('./ForceGraphView', () => ({
  default: ({ data }: { data: GraphData }) => (
    <ul aria-label="nodos">
      {data.nodes.map((n) => (
        <li key={n.id}>{`${n.kind}:${n.title}`}</li>
      ))}
    </ul>
  ),
}))

const VAULT: VaultGraph = {
  nodes: [
    { id: 'modelos/SLM', title: 'SLM', path: 'modelos/SLM.md', tags: [] },
    { id: 'modelos/LLM', title: 'LLM', path: 'modelos/LLM.md', tags: [] },
    { id: '_copilot/LoRA', title: 'LoRA', path: '_copilot/LoRA.md', tags: [] },
  ],
  links: [
    { source: 'modelos/SLM', target: 'modelos/LLM' },
    { source: 'modelos/SLM', target: '_copilot/LoRA' },
  ],
}

const proposed = (id: string, title: string, links: string[]): AgentEvent => ({
  type: 'node_proposed',
  run_id: 'run-1',
  ts: '2026-11-21T10:00:00Z',
  agent: 'writer',
  proposal_id: id,
  title,
  links,
})

describe('buildGraphData', () => {
  it('marca las notas aprobadas y añade las propuestas enlazadas a notas existentes', () => {
    const data = buildGraphData(VAULT, [proposed('p-1', 'Routing de modelos', ['modelos/LLM', 'no-existe'])])

    const kinds = Object.fromEntries(data.nodes.map((n) => [n.id, n.kind]))
    expect(kinds).toEqual({
      'modelos/SLM': 'note',
      'modelos/LLM': 'note',
      '_copilot/LoRA': 'copilot',
      'proposed:p-1': 'proposed',
    })
    // El enlace a una nota inexistente se descarta.
    expect(data.links.filter((l) => l.proposed)).toEqual([
      { source: 'proposed:p-1', target: 'modelos/LLM', proposed: true },
    ])
    expect(data.nodes.find((n) => n.id === 'modelos/LLM')?.degree).toBe(2)
  })

  it('una propuesta ya aprobada no se duplica', () => {
    const data = buildGraphData(VAULT, [proposed('p-2', 'LoRA', ['modelos/SLM'])])

    expect(data.nodes.filter((n) => n.title === 'LoRA')).toHaveLength(1)
  })
})

describe('GraphPanel (HU1)', () => {
  it('pinta la bóveda con su leyenda y las notas propuestas', async () => {
    stubRoutes({ 'GET /api/vault': () => Response.json(VAULT) })

    render(<GraphPanel events={[proposed('p-1', 'Routing de modelos', ['modelos/LLM'])]} />)

    const nodes = await screen.findByRole('list', { name: 'nodos' })
    expect(nodes).toHaveTextContent('proposed:Routing de modelos')
    expect(screen.getByRole('list', { name: 'Leyenda del grafo' })).toHaveTextContent(
      '2 notas1 aprobadas1 propuestas',
    )
  })

  it('muestra el error si no se puede cargar la bóveda', async () => {
    stubRoutes({ 'GET /api/vault': () => Response.json({ detail: 'Bóveda no encontrada' }, { status: 404 }) })

    render(<GraphPanel />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Bóveda no encontrada')
  })
})
