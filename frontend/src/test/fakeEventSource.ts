// EventSource falso para los tests: jsdom no lo implementa y los tests no deben abrir
// conexiones. Imita lo que usa src/api/events.ts: listeners por tipo, onerror y close().
import { vi } from 'vitest'
import type { AgentEvent } from '../api/contract.gen'

export class FakeEventSource {
  static instances: FakeEventSource[] = []
  readonly url: string
  closed = false
  onerror: (() => void) | null = null
  readonly listeners = new Map<string, Array<(m: MessageEvent<string>) => void>>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, fn: (m: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn])
  }

  close() {
    this.closed = true
  }

  /** Simula un mensaje SSE `event: <type>` con `data: <json>`, como el backend. */
  emit(event: AgentEvent) {
    const message = new MessageEvent('message', { data: JSON.stringify(event) })
    for (const fn of this.listeners.get(event.type) ?? []) fn(message as MessageEvent<string>)
  }

  static last(): FakeEventSource {
    const source = FakeEventSource.instances.at(-1)
    if (!source) throw new Error('No se ha abierto ningún EventSource')
    return source
  }
}

export function installFakeEventSource() {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
}
