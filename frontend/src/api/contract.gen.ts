// FICHERO GENERADO por scripts/gen-contract-types.mjs desde contracts/*.schema.json.
// No lo edites a mano: cambia el esquema (en una PR acordada) y ejecuta `npm run gen:types`.
/* eslint-disable */

export interface AskRequest {
  question: string
  /**
   * Idioma de la respuesta. auto (por defecto) = el idioma de la pregunta.
   */
  language?: 'auto' | 'es' | 'en' | 'fr' | 'de' | 'pt'
}
/**
 * This interface was referenced by `AskRoot`'s JSON-Schema
 * via the `definition` "AskCitation".
 */

export interface AskCitation {
  /**
   * id del nodo en el grafo (ruta sin .md).
   */
  id: string
  title: string
}
/**
 * This interface was referenced by `AskRoot`'s JSON-Schema
 * via the `definition` "AskResponse".
 */

export interface AskResponse {
  /**
   * Respuesta en Markdown con [[wikilinks]] a las notas citadas.
   */
  answer: string
  /**
   * Notas de la bóveda que respaldan la respuesta, en orden de aparición.
   */
  citations: AskCitation[]
  /**
   * Modelo que respondió; null si no se llamó a ninguno (sin notas relevantes o sin LLM configurado).
   */
  model: string | null
  tier: ('slm' | 'large') | null
  /**
   * true si el SLM falló y respondió el modelo grande.
   */
  escalated: boolean
  cost_usd: number
  /**
   * Idioma en que se respondió (el elegido o el detectado).
   */
  language?: 'es' | 'en' | 'fr' | 'de' | 'pt'
}

/**
 * GET /api/research/{run_id}/events (SSE). Cada mensaje SSE lleva en 'data' un objeto de este esquema; el campo 'type' dice cuál.
 */

export type AgentEvent =
  AgentThought | ToolCall | ToolResult | RouteDecision | NodeProposed | RunFinished | RunError
/**
 * 'system' se usa para eventos del orquestador (fin de la investigación, errores).
 */

export type Agent = 'explorer' | 'researcher' | 'writer' | 'reviewer' | 'system'

export type Tier = 'slm' | 'large'

export interface AgentThought {
  type: 'agent_thought'
  run_id: string
  ts: string
  agent: Agent
  text: string
}

export interface ToolCall {
  type: 'tool_call'
  run_id: string
  ts: string
  agent: Agent
  /**
   * Ej.: 'search_arxiv', 'read_note', 'find_gaps'.
   */
  tool: string
  args: {}
}

export interface ToolResult {
  type: 'tool_result'
  run_id: string
  ts: string
  agent: Agent
  tool: string
  /**
   * Resumen corto y legible del resultado.
   */
  summary: string
}

export interface RouteDecision {
  type: 'route_decision'
  run_id: string
  ts: string
  agent: Agent
  /**
   * Tipo de tarea. Ej.: 'find_gaps', 'summarize_paper', 'write_note', 'verify_claims'.
   */
  task: string
  /**
   * Identificador del modelo usado.
   */
  model: string
  tier: Tier
  /**
   * Por qué se eligió este modelo.
   */
  reason: string
  /**
   * true si el SLM falló y se repitió con el modelo grande.
   */
  escalated: boolean
}

export interface NodeProposed {
  type: 'node_proposed'
  run_id: string
  ts: string
  agent: Agent
  proposal_id: string
  title: string
  /**
   * ids de los nodos existentes a los que enlaza la nota propuesta.
   */
  links: string[]
}

export interface RunFinished {
  type: 'run_finished'
  run_id: string
  ts: string
  agent: Agent
  stats: RunStats
}

export interface RunStats {
  notes_proposed: number
  cost_usd: number
  /**
   * Coste estimado si todo lo hubiera hecho el modelo grande.
   */
  baseline_cost_usd: number
  savings_usd: number
  escalations: number
  duration_s: number
}

export interface RunError {
  type: 'error'
  run_id: string
  ts: string
  agent: Agent
  message: string
}

/**
 * GET /api/metrics (opcional ?run_id=...) — qué modelo hizo cada tarea, cuánto costó y el ahorro total. Costes en USD, que es como facturan los proveedores.
 */

export interface Metrics {
  tasks: {
    run_id: string
    agent: 'explorer' | 'researcher' | 'writer' | 'reviewer' | 'system'
    task: string
    model: string
    tier: 'slm' | 'large'
    prompt_tokens: number
    completion_tokens: number
    cost_usd: number
    latency_ms: number
    escalated: boolean
  }[]
  totals: {
    tasks: number
    cost_usd: number
    /**
     * Coste estimado si todo lo hubiera hecho el modelo grande.
     */
    baseline_cost_usd: number
    savings_usd: number
    escalations: number
    /**
     * Fracción de tareas resueltas por el SLM.
     */
    slm_share: number
  }
}

/**
 * This interface was referenced by `ProposalRoot`'s JSON-Schema
 * via the `definition` "ProposalList".
 */

export type ProposalList = Proposal[]

export interface Source {
  title: string
  url: string
}
/**
 * This interface was referenced by `ProposalRoot`'s JSON-Schema
 * via the `definition` "Proposal".
 */

export interface Proposal {
  id: string
  run_id: string
  title: string
  /**
   * Contenido completo de la nota, con [[wikilinks]].
   */
  markdown: string
  sources: Source[]
  /**
   * ids de los nodos enlazados.
   */
  links: string[]
  agent: 'explorer' | 'researcher' | 'writer' | 'reviewer' | 'system'
  model: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  /**
   * Resultado del Revisor. Ausente o null si la nota no se pudo revisar.
   */
  review?: ProposalReview | null
  /**
   * Idioma en que está escrita la nota. Ausente o null en notas antiguas.
   */
  language?: ('es' | 'en' | 'fr' | 'de' | 'pt') | null
}
/**
 * This interface was referenced by `ProposalRoot`'s JSON-Schema
 * via the `definition` "ProposalReview".
 */

export interface ProposalReview {
  /**
   * Afirmaciones factuales de la nota.
   */
  claims: number
  /**
   * Cuántas respaldan el resumen y los abstracts.
   */
  supported: number
  /**
   * Afirmaciones sin respaldo que encontró el Revisor.
   */
  issues: string[]
  /**
   * true si el Redactor reescribió la nota tras la revisión.
   */
  revised: boolean
}
/**
 * This interface was referenced by `ProposalRoot`'s JSON-Schema
 * via the `definition` "ProposalAction".
 */

export interface ProposalAction {
  action: 'approve' | 'reject'
  /**
   * Solo con approve: versión editada por el usuario que sustituye a la propuesta.
   */
  markdown?: string | null
}

/**
 * This interface was referenced by `ResearchRoot`'s JSON-Schema
 * via the `definition` "Language".
 */

export type Language = 'es' | 'en' | 'fr' | 'de' | 'pt'
/**
 * This interface was referenced by `ResearchRoot`'s JSON-Schema
 * via the `definition` "ContentLanguage".
 */

export type ContentLanguage = 'auto' | 'es' | 'en' | 'fr' | 'de' | 'pt'

export interface ResearchRequest {
  topic: string
  /**
   * Idioma de las notas. auto (por defecto) = el idioma en que está escrito el tema.
   */
  language?: 'auto' | 'es' | 'en' | 'fr' | 'de' | 'pt'
  /**
   * Idioma de la interfaz: el de los mensajes de los agentes. Por defecto, es.
   */
  ui_language?: 'es' | 'en' | 'fr' | 'de' | 'pt'
}
/**
 * This interface was referenced by `ResearchRoot`'s JSON-Schema
 * via the `definition` "ResearchResponse".
 */

export interface ResearchResponse {
  /**
   * Identificador para seguir los eventos en /api/research/{run_id}/events.
   */
  run_id: string
}

/**
 * GET /api/vault — la bóveda como grafo. Solo incluye enlaces entre notas que existen.
 */

export interface VaultGraph {
  nodes: {
    /**
     * Ruta relativa sin extensión, con '/' como separador. Ej.: 'ml/transformers'.
     */
    id: string
    /**
     * Nombre del fichero sin .md (como lo muestra Obsidian).
     */
    title: string
    /**
     * Ruta relativa con extensión. Ej.: 'ml/transformers.md'.
     */
    path: string
    tags: string[]
  }[]
  links: {
    /**
     * id del nodo origen.
     */
    source: string
    /**
     * id del nodo destino.
     */
    target: string
  }[]
}
