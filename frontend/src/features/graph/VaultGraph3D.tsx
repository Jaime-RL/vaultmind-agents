// Componente que pinta el grafo con WebGL. Va en su propio fichero porque se carga
// con React.lazy: three.js pesa ~600 kB y así no retrasa la primera pantalla.
// En los tests se sustituye por un doble (jsdom no tiene WebGL).
import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D, { type ForceGraphMethods } from 'react-force-graph-3d'
import * as THREE from 'three'
import { PROPOSED_COLOR, TIER_COLORS } from './colors'
import type { GraphData, GraphLink, GraphNode } from './graphData'

interface Props {
  data: GraphData
  /** Nodo que se acaba de proponer: la cámara se acerca a él. */
  focusId?: string
  /** true al terminar una investigación: la cámara vuelve a encuadrar todo el grafo. */
  fitAll?: boolean
}

// Objeto 3D de una nota propuesta: esfera de color de acento y un anillo del color
// del modelo (verde SLM, azul grande), separado de la esfera para que se distingan. Las notas normales usan la esfera por
// defecto de la librería, más barata de dibujar.
function proposedObject(node: GraphNode): THREE.Object3D {
  const group = new THREE.Group()
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(5, 24, 24),
    new THREE.MeshLambertMaterial({ color: node.color, emissive: node.color, emissiveIntensity: 0.35 }),
  )
  group.add(sphere)
  if (node.tier) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(7.5, 0.9, 12, 48),
      new THREE.MeshBasicMaterial({ color: TIER_COLORS[node.tier] }),
    )
    group.add(ring)
  }
  return group
}

export default function VaultGraph3D({ data, focusId, fitAll = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | undefined>(undefined)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const fitted = useRef(false)

  // El lienzo WebGL necesita medidas en píxeles: las tomamos del contenedor y las
  // actualizamos si cambia (ventana redimensionada, panel lateral abierto...).
  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // react-force-graph MODIFICA los nodos que recibe (les añade x, y, z, vx...).
  // Reutilizamos el mismo objeto para cada id entre actualizaciones: así, cuando
  // llega una nota propuesta, las demás conservan su posición y solo la nueva
  // entra animada, en lugar de recolocarse todo el grafo.
  // La caché es un objeto estable creado una sola vez (useState con inicializador),
  // no un ref: React no permite leer refs durante el render.
  const [nodeCache] = useState(() => new Map<string, GraphNode>())
  const graphData = useMemo(() => {
    const cache = nodeCache
    const nodes = data.nodes.map((node) => {
      const previous = cache.get(node.id)
      const merged = previous ? Object.assign(previous, node) : { ...node }
      cache.set(node.id, merged)
      return merged
    })
    // Los enlaces se copian: la librería sustituye source/target por los objetos nodo.
    return { nodes, links: data.links.map((link) => ({ ...link })) }
  }, [data, nodeCache])

  useEffect(() => {
    if (!fitAll) return
    const timer = setTimeout(() => graphRef.current?.zoomToFit(1200, 60), 1500)
    return () => clearTimeout(timer)
  }, [fitAll])

  useEffect(() => {
    if (!focusId || fitAll) return
    // Damos tiempo al motor de fuerzas a colocar el nodo nuevo antes de mover la cámara.
    const timer = setTimeout(() => {
      const node = nodeCache.get(focusId) as
        | (GraphNode & { x?: number; y?: number; z?: number })
        | undefined
      if (!node || node.x === undefined || !graphRef.current) return
      const distance = 120
      const ratio = 1 + distance / Math.hypot(node.x, node.y ?? 0, node.z ?? 0)
      graphRef.current.cameraPosition(
        { x: node.x * ratio, y: (node.y ?? 0) * ratio, z: (node.z ?? 0) * ratio },
        { x: node.x, y: node.y ?? 0, z: node.z ?? 0 },
        1500,
      )
    }, 900)
    return () => clearTimeout(timer)
  }, [focusId, fitAll, nodeCache])

  return (
    <div ref={containerRef} className="graph-canvas">
      {size.width > 0 && (
        <ForceGraph3D<GraphNode, GraphLink>
          ref={graphRef}
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor="#0f1117"
          nodeLabel={(node) => node.title}
          nodeColor={(node) => node.color}
          nodeVal={(node) => node.val}
          nodeOpacity={0.9}
          // Sin objeto propio (null), la librería dibuja su esfera por defecto.
          nodeThreeObject={(node) =>
            node.kind === 'proposed' ? proposedObject(node) : (null as unknown as THREE.Object3D)
          }
          linkColor={(link) => (link.proposed ? PROPOSED_COLOR : '#3a4152')}
          linkWidth={(link) => (link.proposed ? 1.2 : 0.4)}
          linkOpacity={0.6}
          // Partículas que viajan por los enlaces nuevos: se ve qué conecta la nota propuesta.
          linkDirectionalParticles={(link) => (link.proposed ? 3 : 0)}
          linkDirectionalParticleWidth={1.6}
          cooldownTicks={120}
          // Al terminar de colocarse por primera vez, encuadra toda la bóveda.
          onEngineStop={() => {
            if (fitted.current) return
            fitted.current = true
            graphRef.current?.zoomToFit(600, 40)
          }}
        />
      )}
    </div>
  )
}
