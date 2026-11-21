import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FakeEventSource, installFakeEventSource } from '../test/fakeEventSource'
import { loadRunExample } from '../test/fixtures'
import { EVENT_TYPES, subscribeToRun } from './events'

beforeEach(installFakeEventSource)

const events = loadRunExample()

describe('subscribeToRun', () => {
  it('abre la URL de eventos del run con ruta relativa', () => {
    subscribeToRun('run-1', { onEvent: vi.fn(), onDisconnect: vi.fn() })

    expect(FakeEventSource.last().url).toBe('/api/research/run-1/events')
  })

  it('escucha todos los tipos de evento del contrato (onmessage no los recibiría)', () => {
    subscribeToRun('run-1', { onEvent: vi.fn(), onDisconnect: vi.fn() })

    expect([...FakeEventSource.last().listeners.keys()].sort()).toEqual([...EVENT_TYPES].sort())
  })

  it('entrega cada evento del fixture en orden y cierra al llegar run_finished', () => {
    const onEvent = vi.fn()
    subscribeToRun('run-demo-001', { onEvent, onDisconnect: vi.fn() })
    const source = FakeEventSource.last()

    for (const event of events) source.emit(event)

    expect(onEvent).toHaveBeenCalledTimes(events.length)
    expect(onEvent.mock.calls.map(([e]) => e.type)).toEqual(events.map((e) => e.type))
    expect(source.closed).toBe(true)
  })

  it('avisa de la desconexión y no deja que EventSource reconecte solo', () => {
    const onDisconnect = vi.fn()
    subscribeToRun('run-1', { onEvent: vi.fn(), onDisconnect })
    const source = FakeEventSource.last()

    source.onerror?.()

    expect(onDisconnect).toHaveBeenCalledOnce()
    expect(source.closed).toBe(true)
  })

  it('no avisa de desconexión si el flujo ya había terminado', () => {
    const onDisconnect = vi.fn()
    subscribeToRun('run-1', { onEvent: vi.fn(), onDisconnect })
    const source = FakeEventSource.last()

    source.emit(events.at(-1)!)
    source.onerror?.()

    expect(onDisconnect).not.toHaveBeenCalled()
  })

  it('ignora mensajes que no son JSON', () => {
    const onEvent = vi.fn()
    subscribeToRun('run-1', { onEvent, onDisconnect: vi.fn() })

    const listener = FakeEventSource.last().listeners.get('agent_thought')![0]!
    listener(new MessageEvent('message', { data: '{roto' }) as MessageEvent<string>)

    expect(onEvent).not.toHaveBeenCalled()
  })
})
