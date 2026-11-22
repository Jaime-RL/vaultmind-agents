import type { Proposal } from '../../api/contract.gen'
import { CONFIDENCE_ICON, confidenceLabel, confidenceLevel } from './confidence'

/** Insignia compacta para la cabecera de la tarjeta: «✓ 5/5 respaldadas». */
export function ConfidenceBadge({ proposal }: { proposal: Proposal }) {
  const level = confidenceLevel(proposal.review)
  return (
    <span
      className={`confidence confidence--${level}`}
      title="Afirmaciones de la nota respaldadas por el resumen y los abstracts de las fuentes"
    >
      <span aria-hidden="true">{CONFIDENCE_ICON[level]}</span> {confidenceLabel(proposal.review)}
      {proposal.review?.revised && <span className="confidence__revised"> · corregida</span>}
    </span>
  )
}

/** Detalle de la revisión dentro de la nota abierta. */
export function ReviewDetails({ proposal }: { proposal: Proposal }) {
  const review = proposal.review
  if (!review) {
    return (
      <p className="review-details review-details--unknown">
        El Revisor no pudo comprobar esta nota: léela con más cuidado antes de aprobarla.
      </p>
    )
  }
  return (
    <section className="review-details" aria-label="Revisión">
      {review.revised && (
        <p className="review-details__revised">
          ✎ <strong>Corregida por el Revisor:</strong> la primera versión tenía afirmaciones sin
          respaldo y el Redactor la reescribió.
        </p>
      )}
      {review.issues.length > 0 && (
        <details>
          <summary>
            {review.issues.length === 1
              ? '1 afirmación sin respaldo'
              : `${review.issues.length} afirmaciones sin respaldo`}
          </summary>
          <ul>
            {review.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
