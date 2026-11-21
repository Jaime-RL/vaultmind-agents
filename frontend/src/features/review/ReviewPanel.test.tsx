import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Proposal } from '../../api/endpoints'
import { stubRoutes } from '../../test/fetchRoutes'
import ReviewPanel from './ReviewPanel'
import { wikilinksToMarkdown } from './wikilinks'

const proposal = (id: string, title: string, extra: Partial<Proposal> = {}): Proposal => ({
  id,
  run_id: 'run-1',
  title,
  markdown: `# ${title}\n\nEntrena matrices de bajo rango. Ver [[SLM]] y [[modelos/Fine-tuning|ajuste fino]].\n\n## Fuentes\n\n- [Paper](https://arxiv.org/abs/2106.09685)\n`,
  sources: [{ title: 'Paper', url: 'https://arxiv.org/abs/2106.09685' }],
  links: ['modelos/SLM'],
  agent: 'writer',
  model: 'qwen/qwen-2.5-72b-instruct',
  status: 'pending',
  created_at: '2026-11-21T10:00:00Z',
  ...extra,
})

describe('ReviewPanel (HU3)', () => {
  it('lista las pendientes y muestra la primera renderizada', async () => {
    stubRoutes({
      'GET /api/proposals?status=pending': () =>
        Response.json([proposal('p-1', 'LoRA'), proposal('p-2', 'Routing de modelos')]),
    })

    render(<ReviewPanel />)

    const list = await screen.findByRole('list', { name: 'Propuestas pendientes' })
    expect(within(list).getAllByRole('button')).toHaveLength(2)
    const note = screen.getByRole('article', { name: 'Nota LoRA' })
    expect(within(note).getByRole('heading', { name: 'LoRA' })).toBeInTheDocument()
    expect(within(note).getByText('qwen-2.5-72b-instruct')).toBeInTheDocument()
    // Los wikilinks se pintan como notas de la bóveda, no como enlaces navegables.
    expect(within(note).getByText('ajuste fino')).toHaveClass('wikilink')
    // Las fuentes abren en otra pestaña.
    expect(within(note).getByRole('link', { name: 'Paper' })).toHaveAttribute('target', '_blank')
  })

  it('aprueba una nota, avisa y recarga la lista', async () => {
    let pending = [proposal('p-1', 'LoRA'), proposal('p-2', 'Routing de modelos')]
    const fetchMock = stubRoutes({
      'GET /api/proposals?status=pending': () => Response.json(pending),
      'POST /api/proposals/p-1': (init) => {
        expect(JSON.parse(String(init?.body))).toEqual({ action: 'approve' })
        pending = pending.slice(1)
        return Response.json({ ...proposal('p-1', 'LoRA'), status: 'approved' })
      },
    })
    const onApproved = vi.fn()

    render(<ReviewPanel onApproved={onApproved} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Aprobar y guardar' }))

    expect(await screen.findByRole('status')).toHaveTextContent('«LoRA» guardada en tu bóveda')
    expect(onApproved).toHaveBeenCalledWith(expect.objectContaining({ id: 'p-1' }))
    expect(await screen.findByRole('article', { name: 'Nota Routing de modelos' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/proposals/p-1', expect.objectContaining({ method: 'POST' }))
  })

  it('rechaza una nota', async () => {
    let pending = [proposal('p-1', 'LoRA')]
    stubRoutes({
      'GET /api/proposals?status=pending': () => Response.json(pending),
      'POST /api/proposals/p-1': () => {
        pending = []
        return Response.json({ ...proposal('p-1', 'LoRA'), status: 'rejected' })
      },
    })

    render(<ReviewPanel />)
    await userEvent.click(await screen.findByRole('button', { name: 'Rechazar' }))

    expect(await screen.findByText('«LoRA» descartada.')).toBeInTheDocument()
    expect(await screen.findByText(/No hay notas pendientes/)).toBeInTheDocument()
  })

  it('muestra el error del backend (p. ej. 409 si ya estaba resuelta)', async () => {
    stubRoutes({
      'GET /api/proposals?status=pending': () => Response.json([proposal('p-1', 'LoRA')]),
      'POST /api/proposals/p-1': () => Response.json({ detail: 'La propuesta ya está approved' }, { status: 409 }),
    })

    render(<ReviewPanel />)
    await userEvent.click(await screen.findByRole('button', { name: 'Aprobar y guardar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('La propuesta ya está approved')
  })

  it('avisa si una nota no tiene fuentes', async () => {
    stubRoutes({
      'GET /api/proposals?status=pending': () => Response.json([proposal('p-1', 'LoRA', { sources: [] })]),
    })

    render(<ReviewPanel />)

    expect(await screen.findByText(/no tiene fuentes verificadas/)).toBeInTheDocument()
  })

  it('indica cuando no hay pendientes o el backend falla', async () => {
    stubRoutes({ 'GET /api/proposals?status=pending': () => Response.json([]) })
    const { unmount } = render(<ReviewPanel />)
    expect(await screen.findByText(/No hay notas pendientes/)).toBeInTheDocument()
    unmount()

    stubRoutes({ 'GET /api/proposals?status=pending': () => Promise.reject(new TypeError('offline')) })
    render(<ReviewPanel />)
    expect(await screen.findByRole('alert')).toHaveTextContent('el backend no responde')
  })
})

describe('wikilinksToMarkdown', () => {
  it('convierte destino, alias y sección', () => {
    expect(wikilinksToMarkdown('[[SLM]]')).toBe('[SLM](wikilink:SLM)')
    expect(wikilinksToMarkdown('[[a/b|alias]]')).toBe('[alias](wikilink:a%2Fb)')
    expect(wikilinksToMarkdown('[[Nota#Sección]]')).toBe('[Nota](wikilink:Nota)')
  })
})
