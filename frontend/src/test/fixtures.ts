// Acceso a los fixtures compartidos del repo (fixtures/, de la Persona A) desde los tests.
// Se leen del disco en lugar de copiarlos: si A regenera el fixture, los tests usan
// siempre la versión actual y detectan cualquier desajuste con la interfaz.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { AgentEvent } from '../api/contract.gen'

// Vitest se ejecuta desde frontend/, así que la raíz del repo es el directorio padre.
// (En jsdom, import.meta.url no es una ruta de fichero y no sirve para esto.)
const repoRoot = resolve(process.cwd(), '..')

/** fixtures/run_example.jsonl: una investigación completa, un evento por línea. */
export function loadRunExample(): AgentEvent[] {
  const text = readFileSync(resolve(repoRoot, 'fixtures', 'run_example.jsonl'), 'utf8')
  return text
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => JSON.parse(line) as AgentEvent)
}
