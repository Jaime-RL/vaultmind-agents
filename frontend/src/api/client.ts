// Cliente REST mínimo. Los tipos de las respuestas vienen de contract.gen.ts.
//
// API_BASE vacío (el valor por defecto) = rutas relativas (/api/...):
// - en desarrollo, Vite las reenvía al backend (ver vite.config.ts);
// - en producción, FastAPI sirve el frontend desde el mismo origen.
// Solo hace falta VITE_API_URL para apuntar a un backend en otro origen
// (por ejemplo, el frontend en local contra la URL pública).
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

export interface Health {
  status: 'ok'
}

export const getHealth = (): Promise<Health> => apiFetch<Health>('/api/health')
