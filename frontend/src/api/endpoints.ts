// Funciones tipadas para cada endpoint del contrato (contracts/README.md).
// Los tipos salen de contract.gen.ts, generado desde contracts/: nunca se escriben a mano.
import { apiFetch } from './client'
import type {
  Metrics,
  Proposal1,
  ProposalAction,
  ResearchRequest,
  ResearchResponse,
  VaultGraph,
} from './contract.gen'

// json-schema-to-typescript llama «Proposal1» a la definición de una propuesta
// (el nombre «Proposal» lo usa para el fichero de esquema). Le damos un alias legible.
export type Proposal = Proposal1
export type ProposalStatus = Proposal['status']
export type TaskMetric = Metrics['tasks'][number]

const query = (params: Record<string, string | null | undefined>): string => {
  const entries = Object.entries(params).filter((entry): entry is [string, string] => !!entry[1])
  return entries.length ? `?${new URLSearchParams(entries).toString()}` : ''
}

export const getProposals = (status?: ProposalStatus): Promise<Proposal[]> =>
  apiFetch<Proposal[]>(`/api/proposals${query({ status })}`)

export const resolveProposal = (
  id: string,
  action: ProposalAction['action'],
): Promise<Proposal> =>
  apiFetch<Proposal>(`/api/proposals/${encodeURIComponent(id)}`, {
    method: 'POST',
    body: JSON.stringify({ action } satisfies ProposalAction),
  })

export const getMetrics = (runId?: string | null): Promise<Metrics> =>
  apiFetch<Metrics>(`/api/metrics${query({ run_id: runId })}`)

export const startResearch = (topic: string): Promise<ResearchResponse> =>
  apiFetch<ResearchResponse>('/api/research', {
    method: 'POST',
    body: JSON.stringify({ topic } satisfies ResearchRequest),
  })

export const getVault = (): Promise<VaultGraph> => apiFetch<VaultGraph>('/api/vault')
