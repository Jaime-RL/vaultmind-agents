import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Proposal, ProposalReview } from '../../api/contract.gen'
import { loadDemoProposals } from '../../test/fixtures'
import { ConfidenceBadge, ReviewDetails } from './ConfidenceBadge'
import { confidenceLevel } from './confidence'

const base = loadDemoProposals()[0]!
const withReview = (review: ProposalReview | null): Proposal => ({
  ...base,
  review,
})
const review = (claims: number, supported: number, extra: Partial<ProposalReview> = {}) => ({
  claims,
  supported,
  issues: [],
  revised: false,
  ...extra,
})

describe('confidenceLevel', () => {
  it.each([
    [review(5, 5), 'high'],
    [review(5, 3), 'medium'],
    [review(5, 2), 'low'],
    [review(0, 0), 'low'],
    [null, 'unknown'],
  ] as const)('%o → %s', (r, level) => {
    expect(confidenceLevel(r)).toBe(level)
  })
})

describe('ConfidenceBadge', () => {
  it('muestra cuántas afirmaciones tienen respaldo, con icono además del color', () => {
    render(<ConfidenceBadge proposal={withReview(review(5, 5))} />)

    const badge = screen.getByText(/5\/5 respaldadas/)
    expect(badge).toHaveClass('confidence--high')
    expect(badge).toHaveTextContent('✓')
  })

  it('indica si el Revisor hizo corregir la nota', () => {
    render(<ConfidenceBadge proposal={withReview(review(4, 4, { revised: true }))} />)

    expect(screen.getByText(/corregida/)).toBeInTheDocument()
  })

  it('avisa cuando la nota no se pudo revisar', () => {
    render(<ConfidenceBadge proposal={withReview(null)} />)

    expect(screen.getByText(/Sin revisar/)).toHaveClass('confidence--unknown')
  })
})

describe('ReviewDetails', () => {
  it('lista las afirmaciones sin respaldo en un desplegable', async () => {
    render(
      <ReviewDetails
        proposal={withReview(review(5, 3, { issues: ['la cifra del 40 %', 'Qwen-3D'] }))}
      />,
    )

    await userEvent.click(screen.getByText('2 afirmaciones sin respaldo'))
    expect(screen.getByText('Qwen-3D')).toBeVisible()
  })

  it('explica que la nota fue corregida', () => {
    render(<ReviewDetails proposal={withReview(review(4, 4, { revised: true }))} />)

    expect(screen.getByText(/Corregida por el Revisor/)).toBeInTheDocument()
  })

  it('la demo incluye una nota corregida para enseñarlo en el vídeo', () => {
    expect(loadDemoProposals().some((p) => p.review?.revised)).toBe(true)
  })
})
