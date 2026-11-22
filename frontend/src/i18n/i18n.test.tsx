import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AskPanel } from '../features/ask/AskPanel'
import { ResearchForm } from '../features/agents-panel/ResearchForm'
import { InterfaceLanguageSelect } from '../components/LanguageSelect'
import { makeI18n, translate } from './context'
import { I18nProvider } from './I18nProvider'
import { MESSAGES, type MessageKey } from './messages'

describe('catálogo', () => {
  it('las cinco lenguas tienen exactamente las mismas claves y ninguna vacía', () => {
    const reference = Object.keys(MESSAGES.es).sort()
    for (const [lang, messages] of Object.entries(MESSAGES)) {
      expect(Object.keys(messages).sort(), lang).toEqual(reference)
      expect(
        Object.values(messages).filter((v) => !v.trim()),
        lang,
      ).toEqual([])
    }
  })

  it('cada traducción conserva los mismos {parámetros} que el español', () => {
    const params = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(',')
    for (const [lang, messages] of Object.entries(MESSAGES)) {
      for (const key of Object.keys(MESSAGES.es) as MessageKey[]) {
        expect(params(messages[key]), `${lang} ${key}`).toBe(params(MESSAGES.es[key]))
      }
    }
  })

  it('sustituye parámetros y elige singular o plural', () => {
    expect(translate('en', 'graph.summary', { notes: 28, links: 87 })).toBe('28 notes · 87 links')
    const { tn } = makeI18n('de')
    expect(tn('graph.proposals', 1)).toBe('1 Vorschlag')
    expect(tn('graph.proposals', 3)).toBe('3 Vorschläge')
  })
})

describe('idioma de la interfaz', () => {
  it('cambiar el selector traduce la interfaz y se recuerda', async () => {
    render(
      <I18nProvider initial="es">
        <InterfaceLanguageSelect />
        <ResearchForm busy={false} onSubmit={vi.fn()} />
      </I18nProvider>,
    )
    expect(screen.getByRole('button', { name: 'Investigar' })).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Idioma de la interfaz'), 'fr')

    expect(screen.getByRole('button', { name: 'Rechercher' })).toBeInTheDocument()
    expect(window.localStorage.getItem('vaultmind.language')).toBe('fr')
    expect(document.documentElement.lang).toBe('fr')
  })
})

describe('idioma del contenido', () => {
  it('la investigación envía el idioma elegido para las notas', async () => {
    const onSubmit = vi.fn()
    render(
      <I18nProvider initial="en">
        <ResearchForm busy={false} onSubmit={onSubmit} />
      </I18nProvider>,
    )

    await userEvent.type(screen.getByLabelText('Topic to research'), 'speculative decoding')
    await userEvent.selectOptions(screen.getByLabelText('Notes language'), 'pt')
    await userEvent.click(screen.getByRole('button', { name: 'Research' }))

    expect(onSubmit).toHaveBeenCalledWith('speculative decoding', 'pt')
  })

  it('por defecto pregunta en «auto»: responde en el idioma de la pregunta', async () => {
    const ask = vi.fn().mockResolvedValue({
      answer: 'LoRA freezes the weights [[LoRA]].',
      citations: [{ id: 'LoRA', title: 'LoRA' }],
      model: 'openai/gpt-oss-20b',
      tier: 'slm',
      escalated: false,
      cost_usd: 0.0001,
      language: 'en',
    })
    render(
      <I18nProvider initial="es">
        <AskPanel existing={new Set(['LoRA'])} onFocusNote={vi.fn()} ask={ask} />
      </I18nProvider>,
    )

    await userEvent.type(screen.getByLabelText(/Pregunta a tu bóveda/), 'What is LoRA?')
    await userEvent.click(screen.getByRole('button', { name: 'Preguntar' }))

    expect(ask).toHaveBeenCalledWith('What is LoRA?', 'auto')
    expect(await screen.findByText(/English/)).toBeInTheDocument()
  })
})
