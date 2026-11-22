import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AskResponse } from '../../api/contract.gen'
import { AskPanel } from './AskPanel'
import { describeModel } from './describeModel'

const answer: AskResponse = {
  answer: 'LoRA congela los pesos y entrena matrices pequeñas [[LoRA]].',
  citations: [{ id: 'modelos/LoRA', title: 'LoRA' }],
  model: 'openai/gpt-oss-20b',
  tier: 'slm',
  escalated: false,
  cost_usd: 0.0001,
}

function renderPanel(ask = vi.fn().mockResolvedValue(answer)) {
  const onFocusNote = vi.fn()
  render(
    <AskPanel existing={new Set(['modelos/LoRA', 'LoRA'])} onFocusNote={onFocusNote} ask={ask} />,
  )
  return { ask, onFocusNote }
}

describe('AskPanel', () => {
  it('responde con las notas citadas y lleva la cámara a la primera', async () => {
    const { ask, onFocusNote } = renderPanel()

    await userEvent.type(screen.getByLabelText(/Pregunta a tu bóveda/), '¿Qué es LoRA?')
    await userEvent.click(screen.getByRole('button', { name: 'Preguntar' }))

    expect(ask).toHaveBeenCalledWith('¿Qué es LoRA?', 'auto')
    expect(await screen.findByText(/congela los pesos/)).toBeInTheDocument()
    expect(onFocusNote).toHaveBeenCalledWith('modelos/LoRA')
    expect(screen.getByText(/SLM · gpt-oss-20b/)).toBeInTheDocument()
  })

  it('cada cita es un botón que enseña la nota en el grafo', async () => {
    const { onFocusNote } = renderPanel()

    await userEvent.click(screen.getByRole('button', { name: '¿Qué es LoRA?' })) // ejemplo
    await userEvent.click(await screen.findByRole('button', { name: 'LoRA' }))

    expect(onFocusNote).toHaveBeenLastCalledWith('modelos/LoRA')
  })

  it('muestra el error del backend sin perder lo escrito', async () => {
    renderPanel(vi.fn().mockRejectedValue(new Error('El modelo no pudo responder')))

    await userEvent.type(screen.getByLabelText(/Pregunta a tu bóveda/), '¿Qué es LoRA?')
    await userEvent.click(screen.getByRole('button', { name: 'Preguntar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('El modelo no pudo responder')
    expect(screen.getByLabelText(/Pregunta a tu bóveda/)).toHaveValue('¿Qué es LoRA?')
  })

  it('no envía preguntas de menos de 3 caracteres', async () => {
    const { ask } = renderPanel()

    await userEvent.type(screen.getByLabelText(/Pregunta a tu bóveda/), 'a')

    expect(screen.getByRole('button', { name: 'Preguntar' })).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })
})

describe('describeModel', () => {
  it('explica quién respondió, el coste y si hubo escalada', () => {
    expect(
      describeModel({ ...answer, tier: 'large', model: 'openai/gpt-oss-120b', escalated: true }),
    ).toBe('Modelo grande · gpt-oss-120b · $0.0001 · escalado: el SLM no citó tus notas')
    expect(describeModel({ ...answer, model: null, tier: null })).toBe(
      'Sin modelo: búsqueda en tus notas',
    )
  })
})
