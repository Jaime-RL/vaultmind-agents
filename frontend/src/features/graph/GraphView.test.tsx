import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { VaultGraph } from '../../api/contract.gen'
import type { GraphData } from './graphData'
import { GraphView } from './GraphView'

// jsdom no tiene WebGL: sustituimos el lienzo 3D por una lista con lo que recibiría.
// Así comprobamos QUÉ se pinta (nodos y enlaces) sin depender de la tarjeta gráfica.
vi.mock('./VaultGraph3D', () => ({
  default: ({ data }: { data: GraphData }) => (
    <ul aria-label="grafo">
      {data.nodes.map((node) => (
        <li key={node.id} data-kind={node.kind}>
          {node.title}
        </li>
      ))}
      <li>{data.links.length} enlaces dibujados</li>
    </ul>
  ),
}))

const vault: VaultGraph = {
  nodes: [
    { id: 'rag/Chunking', title: 'Chunking', path: 'rag/Chunking.md', tags: [] },
    { id: 'rag/Embeddings', title: 'Embeddings', path: 'rag/Embeddings.md', tags: [] },
  ],
  links: [{ source: 'rag/Chunking', target: 'rag/Embeddings' }],
}

describe('GraphView', () => {
  it('muestra un estado de carga', () => {
    render(<GraphView state={{ status: 'loading' }} />)

    expect(screen.getByRole('status')).toHaveTextContent('Cargando la bóveda')
  })

  it('muestra el error y permite reintentar', async () => {
    const onRetry = vi.fn()
    render(<GraphView state={{ status: 'error', message: 'Bóveda no encontrada' }} onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Bóveda no encontrada')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('avisa si la bóveda está vacía', () => {
    render(<GraphView state={{ status: 'ready', vault: { nodes: [], links: [] } }} />)

    expect(screen.getByRole('status')).toHaveTextContent('La bóveda está vacía')
  })

  it('dibuja todas las notas y enlaces de la bóveda (criterio de HU1)', async () => {
    render(<GraphView state={{ status: 'ready', vault }} />)

    const graph = await screen.findByRole('list', { name: 'grafo' })
    expect(graph).toHaveTextContent('Chunking')
    expect(graph).toHaveTextContent('Embeddings')
    expect(graph).toHaveTextContent('1 enlaces dibujados')
    expect(screen.getByText('2 notas · 1 enlaces')).toBeInTheDocument()
  })

  it('añade las notas propuestas al grafo', async () => {
    render(
      <GraphView
        state={{ status: 'ready', vault }}
        proposed={[
          { id: 'p-1', title: 'LoRA', links: ['rag/Embeddings'], agent: 'writer', tier: 'large', status: 'pending' },
        ]}
      />,
    )

    const graph = await screen.findByRole('list', { name: 'grafo' })
    expect(graph).toHaveTextContent('LoRA')
    expect(graph).toHaveTextContent('2 enlaces dibujados')
    expect(screen.getByText('2 notas · 1 enlaces · 1 propuesta')).toBeInTheDocument()
  })
})
