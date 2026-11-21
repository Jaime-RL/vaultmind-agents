import { describe, expect, it } from 'vitest'
import type { AgentEvent } from '../../api/contract.gen'
import { loadRunExample } from '../../test/fixtures'
import { initialRunState, runReducer, type RunState } from './runReducer'

const events = loadRunExample()
const RUN_ID = events[0]!.run_id

/** Reproduce el fixture completo como lo haría el SSE, sin red ni esperas. */
function replay(list: AgentEvent[] = events): RunState {
  let state = runReducer(initialRunState, { type: 'start', topic: 'SLMs' })
  state = runReducer(state, { type: 'started', runId: RUN_ID })
  for (const event of list) state = runReducer(state, { type: 'event', event })
  return state
}

describe('runReducer con fixtures/run_example.jsonl', () => {
  it('termina la investigación con las estadísticas del run_finished', () => {
    const state = replay()

    expect(state.status).toBe('finished')
    expect(state.stats?.notes_proposed).toBe(3)
    expect(state.events).toHaveLength(events.length)
  })

  it('crea un nodo propuesto por cada node_proposed (criterio de HU2: al menos 3 notas)', () => {
    const state = replay()

    expect(state.proposed.map((p) => p.id)).toEqual(['p-001', 'p-002', 'p-003'])
    expect(state.proposed.every((p) => p.status === 'pending' && p.agent === 'writer')).toBe(true)
  })

  it('deduce el modelo de cada nota del último route_decision de su agente', () => {
    const state = replay()

    expect(state.proposed.map((p) => p.tier)).toEqual(['large', 'large', 'large'])
  })

  it('registra todas las decisiones del router, incluida la escalada', () => {
    const state = replay()
    const decisions = events.filter((e) => e.type === 'route_decision')

    expect(state.routeDecisions).toHaveLength(decisions.length)
    expect(state.routeDecisions.some((d) => d.escalated)).toBe(true)
  })

  it('ignora eventos de otra investigación', () => {
    const foreign = { ...events[0]!, run_id: 'otra' } as AgentEvent
    const state = replay([foreign])

    expect(state.events).toHaveLength(0)
  })

  it('pasa a error con el mensaje de un evento error', () => {
    const error: AgentEvent = {
      type: 'error',
      run_id: RUN_ID,
      ts: '2026-11-23T10:00:00Z',
      agent: 'system',
      message: 'El modelo no responde',
    }
    const state = replay([error])

    expect(state.status).toBe('error')
    expect(state.error).toBe('El modelo no responde')
  })
})

describe('runReducer: ciclo de vida', () => {
  it('una investigación nueva conserva las propuestas pendientes de la anterior', () => {
    let state = replay()
    state = runReducer(state, { type: 'proposal-resolved', id: 'p-001', status: 'approved' })
    state = runReducer(state, { type: 'proposal-resolved', id: 'p-002', status: 'rejected' })

    state = runReducer(state, { type: 'start', topic: 'Otro tema' })

    expect(state.status).toBe('starting')
    expect(state.events).toEqual([])
    expect(state.proposed.map((p) => p.id)).toEqual(['p-003'])
  })

  it('al reconectar descarta lo recibido para no duplicarlo cuando el servidor lo reenvíe', () => {
    let state = replay(events.slice(0, 20))
    state = runReducer(state, { type: 'reset-events' })
    for (const event of events) state = runReducer(state, { type: 'event', event })

    expect(state.events).toHaveLength(events.length)
    expect(state.proposed).toHaveLength(3)
  })
})

describe('runReducer: desconexión', () => {
  it('marca la desconexión como reconectable, a diferencia de un fallo', () => {
    let state = replay(events.slice(0, 5))
    state = runReducer(state, { type: 'disconnected' })
    expect(state).toMatchObject({ status: 'error', disconnected: true })

    state = runReducer(state, { type: 'reset-events' })
    expect(state).toMatchObject({ status: 'running', disconnected: false, events: [] })

    state = runReducer(state, { type: 'failed', message: 'x' })
    expect(state.disconnected).toBe(false)
  })
})
