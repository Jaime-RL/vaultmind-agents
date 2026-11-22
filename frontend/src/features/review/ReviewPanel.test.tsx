import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { loadDemoProposals } from '../../test/fixtures'
import { ReviewPanel } from './ReviewPanel'

const proposals = loadDemoProposals()
const existing = new Set(['agentes/Tool calling', 'Tool calling', 'modelos/SLM', 'SLM'])

function renderPanel(overrides: Partial<Parameters<typeof ReviewPanel>[0]> = {}) {
  const props = {
    state: { status: 'ready' as const, proposals },
    busyId: null,
    actionError: null,
    existing,
    onResolve: vi.fn(),
    onRetry: vi.fn(),
    ...overrides,
  }
  render(<ReviewPanel {...props} />)
  return props
}

describe('ReviewPanel', () => {
  it('lista las notas pendientes y abre la primera con su nota renderizada y sus fuentes', () => {
    renderPanel()

    expect(screen.getAllByRole('button', { expanded: false })).toHaveLength(proposals.length - 1)
    const first = proposals[0]!
    expect(screen.getByRole('heading', { level: 1, name: first.title })).toBeInTheDocument()
    // Las fuentes vienen dentro de la propia nota (las añade el backend) y son enlaces.
    for (const source of first.sources) {
      expect(screen.getAllByRole('link', { name: source.title })[0]).toHaveAttribute('href', source.url)
    }
    // ...así que no se repiten en una lista aparte.
    expect(screen.queryByRole('region', { name: 'Fuentes' })).not.toBeInTheDocument()
  })

  it('lista aparte las fuentes que la nota no menciona', () => {
    const [first] = proposals
    const extra = { title: 'Paper extra', url: 'https://arxiv.org/abs/9999.00001' }
    renderPanel({
      state: { status: 'ready', proposals: [{ ...first!, sources: [...first!.sources, extra] }] },
    })

    const sources = screen.getByRole('region', { name: 'Fuentes' })
    expect(within(sources).getAllByRole('link')).toHaveLength(1)
    expect(within(sources).getByRole('link', { name: 'Paper extra' })).toHaveAttribute('href', extra.url)
  })

  it('aprueba o rechaza la nota abierta', async () => {
    const { onResolve } = renderPanel()

    await userEvent.click(screen.getByRole('button', { name: 'Aprobar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Rechazar' }))

    expect(onResolve).toHaveBeenNthCalledWith(1, proposals[0]!.id, 'approve', undefined)
    expect(onResolve).toHaveBeenNthCalledWith(2, proposals[0]!.id, 'reject')
  })

  it('desactiva los botones mientras se guarda la decisión', () => {
    renderPanel({ busyId: proposals[0]!.id })

    expect(screen.getByRole('button', { name: 'Guardando…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeDisabled()
  })

  it('permite cerrar la nota abierta y abrir otra', async () => {
    renderPanel()
    const firstHeader = screen.getByRole('button', { name: new RegExp(proposals[0]!.title) })

    await userEvent.click(firstHeader)
    expect(firstHeader).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(screen.getByRole('button', { name: new RegExp(proposals[1]!.title) }))
    expect(screen.getByRole('heading', { level: 1, name: proposals[1]!.title })).toBeInTheDocument()
  })

  it('muestra los estados vacío, de carga y de error', async () => {
    const { unmount } = render(
      <ReviewPanel state={{ status: 'ready', proposals: [] }} busyId={null} actionError={null} existing={existing} onResolve={vi.fn()} onRetry={vi.fn()} />,
    )
    expect(screen.getByText(/No hay notas pendientes/)).toBeInTheDocument()
    unmount()

    const onRetry = vi.fn()
    render(
      <ReviewPanel state={{ status: 'error', message: 'boom' }} busyId={null} actionError={null} existing={existing} onResolve={vi.fn()} onRetry={onRetry} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('boom')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('permite editar la nota y aprobar la versión editada', async () => {
    const { onResolve } = renderPanel()

    await userEvent.click(screen.getByRole('button', { name: 'Editar' }))
    const editor = screen.getByRole('textbox', { name: /Editar/ })
    await userEvent.clear(editor)
    await userEvent.type(editor, '# Mi versión')
    await userEvent.click(screen.getByRole('button', { name: 'Aprobar con cambios' }))

    expect(onResolve).toHaveBeenCalledWith(proposals[0]!.id, 'approve', '# Mi versión')
  })

  it('descartar los cambios vuelve a la nota original', async () => {
    renderPanel()

    await userEvent.click(screen.getByRole('button', { name: 'Editar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Descartar cambios' }))

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aprobar' })).toBeInTheDocument()
  })

  it('«Profundizar» lanza una investigación sobre la nota', async () => {
    const onDeepen = vi.fn()
    renderPanel({ onDeepen })

    await userEvent.click(screen.getByRole('button', { name: 'Profundizar' }))

    expect(onDeepen).toHaveBeenCalledWith(proposals[0]!.title)
  })
})
