import { useCallback, useEffect, useState } from 'react'
import { getVault } from '../../api/client'
import type { VaultGraph } from '../../api/contract.gen'

export type VaultState =
  | { status: 'loading' }
  | { status: 'ready'; vault: VaultGraph }
  | { status: 'error'; message: string }

/**
 * Carga /api/vault. `reload()` la vuelve a pedir: se usa tras aprobar una nota,
 * que pasa a existir en la bóveda (dentro de _copilot/).
 */
export function useVaultGraph() {
  const [state, setState] = useState<VaultState>({ status: 'loading' })
  // Cambiar este número fuerza una nueva petición desde el efecto.
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    getVault()
      .then((vault) => !cancelled && setState({ status: 'ready', vault }))
      .catch((error: unknown) => {
        if (cancelled) return
        const message = error instanceof Error ? error.message : 'Error desconocido'
        setState({ status: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [version])

  // En una recarga no volvemos a 'loading': el grafo sigue visible mientras llega
  // la versión nueva, en lugar de parpadear.
  const reload = useCallback(() => setVersion((v) => v + 1), [])

  return { state, reload }
}
