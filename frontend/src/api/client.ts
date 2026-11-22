// Cliente de la API. Una función por endpoint de contracts/README.md; los tipos de
// petición y respuesta vienen de contract.gen.ts (generado desde los esquemas).
//
// API_BASE vacío (el valor por defecto) = rutas relativas (/api/...):
// - en desarrollo, Vite las reenvía al backend (ver vite.config.ts);
// - en producción, FastAPI sirve el frontend desde el mismo origen.
// Solo hace falta VITE_API_URL para apuntar a un backend en otro origen
// (por ejemplo, el frontend en local contra la URL pública).
import type {
  AskRequest,
  AskResponse,
  Metrics,
  Proposal,
  ProposalAction,
  ProposalList,
  ResearchRequest,
  ResearchResponse,
  VaultGraph,
} from './contract.gen'

export const API_BASE: string = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

/** Error HTTP con el `detail` que devuelve FastAPI ({"detail": "..."}). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    // El contrato fija los errores como {"detail": "..."}; si no viene, usamos el texto de estado.
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

const post = <T>(path: string, body: unknown) =>
  apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) })

export interface Health {
  status: 'ok'
}

export const getHealth = (): Promise<Health> => apiFetch<Health>('/api/health')

export const getVault = (): Promise<VaultGraph> => apiFetch<VaultGraph>('/api/vault')

export const startResearch = (topic: string): Promise<ResearchResponse> =>
  post<ResearchResponse>('/api/research', { topic } satisfies ResearchRequest)

/** URL del flujo SSE de una investigación (la abre EventSource en src/api/events.ts). */
export const researchEventsUrl = (runId: string): string =>
  `${API_BASE}/api/research/${encodeURIComponent(runId)}/events`

export const getProposals = (status?: Proposal['status']): Promise<ProposalList> =>
  apiFetch<ProposalList>(`/api/proposals${status ? `?status=${status}` : ''}`)

export const resolveProposal = (id: string, action: ProposalAction['action']): Promise<Proposal> =>
  post<Proposal>(`/api/proposals/${encodeURIComponent(id)}`, { action } satisfies ProposalAction)

export const getMetrics = (runId?: string): Promise<Metrics> =>
  apiFetch<Metrics>(`/api/metrics${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`)

export const askVault = (question: string): Promise<AskResponse> =>
  post<AskResponse>('/api/ask', { question } satisfies AskRequest)
