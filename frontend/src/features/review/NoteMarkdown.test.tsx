import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { NoteMarkdown } from './NoteMarkdown'

describe('NoteMarkdown', () => {
  it('renderiza Markdown y marca los [[enlaces]] según existan en la bóveda', () => {
    render(
      <NoteMarkdown
        markdown={'# Título\n\nUsa [[SLM]] y [[Nota inventada]].'}
        existing={new Set(['modelos/SLM', 'SLM'])}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Título' })).toBeInTheDocument()
    expect(screen.getByText('SLM')).toHaveClass('wikilink--known')
    expect(screen.getByText('Nota inventada')).toHaveClass('wikilink--new')
  })

  it('abre las fuentes externas en otra pestaña sin dar acceso a la ventana', () => {
    render(<NoteMarkdown markdown="[paper](https://arxiv.org/abs/1)" existing={new Set()} />)

    const link = screen.getByRole('link', { name: 'paper' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  // El Markdown lo escribe un LLM: es entrada no confiable.
  it('no ejecuta HTML incrustado ni enlaces javascript:', () => {
    const { container } = render(
      <NoteMarkdown
        markdown={'<img src=x onerror="alert(1)"> <script>alert(1)</script>\n\n[clic](javascript:alert(1))'}
        existing={new Set()}
      />,
    )

    expect(container.querySelector('img, script')).toBeNull()
    expect(screen.getByText('clic').getAttribute('href') ?? '').not.toContain('javascript')
  })

  it('muestra los avisos de Obsidian como un aviso, no como texto «[!warning]»', () => {
    render(
      <NoteMarkdown
        markdown={'Texto.\n\n> [!warning] Nota sin fuentes verificadas.'}
        existing={new Set()}
      />,
    )

    const callout = screen.getByRole('note')
    expect(callout).toHaveClass('callout--warning')
    expect(callout).toHaveTextContent('Atención: Nota sin fuentes verificadas.')
    expect(callout).not.toHaveTextContent('[!warning]')
  })

  it('deja las citas normales como citas', () => {
    const { container } = render(<NoteMarkdown markdown="> Una cita." existing={new Set()} />)

    expect(container.querySelector('blockquote')).toHaveTextContent('Una cita.')
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })
})
