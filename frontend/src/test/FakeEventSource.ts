/**
 * EventSource falso para tests: guarda las instancias y permite emitir eventos
 * con nombre («event: <tipo>») como hace el backend por SSE.
 */
export class FakeEventSource {
  static instances: FakeEventSource[] = []

  readonly url: string
  closed = false
  onopen: (() => void) | null = null
  private listeners = new Map<string, ((message: MessageEvent<string>) => void)[]>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (message: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  close() {
    this.closed = true
  }

  open() {
    this.onopen?.()
  }

  emit(event: { type: string } & Record<string, unknown>) {
    const message = new MessageEvent('message', { data: JSON.stringify(event) })
    for (const listener of this.listeners.get(event.type) ?? []) listener(message)
  }

  static last(): FakeEventSource {
    const source = FakeEventSource.instances.at(-1)
    if (!source) throw new Error('No se ha abierto ningún EventSource')
    return source
  }
}
