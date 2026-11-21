import { useEffect, useRef, useState } from 'react'
import ForceGraph3D, { type ForceGraphMethods } from 'react-force-graph-3d'
import type { GraphData, GraphNode } from './graphData'

// Colores por tipo de nodo (coinciden con la leyenda de GraphPanel).
const NODE_COLOR: Record<GraphNode['kind'], string> = {
  note: '#9aa1b2',
  copilot: '#3fb950',
  proposed: '#7c8cff',
}

/**
 * Lienzo WebGL del grafo. Va en su propio fichero porque three.js pesa: se carga
 * con React.lazy solo cuando hace falta, y en los tests se sustituye (jsdom no tiene WebGL).
 */
export default function ForceGraphView({ data, height = 420 }: { data: GraphData; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<ForceGraphMethods | undefined>(undefined)
  const [width, setWidth] = useState(600)

  // El canvas no se adapta solo: medimos el contenedor y escuchamos sus cambios de tamaño.
  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) setWidth(Math.floor(entry.contentRect.width))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={containerRef} className="graph__canvas">
      <ForceGraph3D
        ref={graphRef}
        graphData={data}
        width={width}
        height={height}
        backgroundColor="#0f1117"
        nodeId="id"
        nodeLabel={(node) => (node as GraphNode).title}
        nodeColor={(node) => NODE_COLOR[(node as GraphNode).kind]}
        nodeVal={(node) => 1 + (node as GraphNode).degree / 2}
        nodeOpacity={0.95}
        linkColor={(link) => ((link as { proposed: boolean }).proposed ? '#7c8cff' : '#3a4150')}
        linkWidth={(link) => ((link as { proposed: boolean }).proposed ? 1.5 : 0.5)}
        // Partículas en los enlaces nuevos: se ve «crecer» la bóveda mientras investigan.
        linkDirectionalParticles={(link) => ((link as { proposed: boolean }).proposed ? 3 : 0)}
        linkDirectionalParticleWidth={1.5}
        enableNodeDrag={false}
        // Cuando la simulación se estabiliza, encuadra toda la bóveda.
        cooldownTicks={120}
        onEngineStop={() => graphRef.current?.zoomToFit(600, 30)}
      />
    </div>
  )
}
