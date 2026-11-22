import type { Proposal } from '../../api/contract.gen'
import { useI18n } from '../../i18n/context'
import { CONFIDENCE_ICON, confidenceLabel, confidenceLevel } from './confidence'

/** Insignia compacta para la cabecera de la tarjeta: «✓ 5/5 respaldadas». */
export function ConfidenceBadge({ proposal }: { proposal: Proposal }) {
  const level = confidenceLevel(proposal.review)
  const { t } = useI18n()
  return (
    <span
      className={`confidence confidence--${level}`}
      title={t('confidence.hint')}
    >
      <span aria-hidden="true">{CONFIDENCE_ICON[level]}</span> {confidenceLabel(proposal.review, t)}
      {proposal.review?.revised && (
        <span className="confidence__revised"> · {t('confidence.revised')}</span>
      )}
    </span>
  )
}

/** Detalle de la revisión dentro de la nota abierta. */
export function ReviewDetails({ proposal }: { proposal: Proposal }) {
  const review = proposal.review
  const { t, tn } = useI18n()
  if (!review) {
    return (
      <p className="review-details review-details--unknown">{t('confidence.noReview')}</p>
    )
  }
  return (
    <section className="review-details" aria-label={t('confidence.reviewLabel')}>
      {review.revised && (
        <p className="review-details__revised">
          ✎ <strong>{t('confidence.revisedLong')}</strong> {t('confidence.revisedDetail')}
        </p>
      )}
      {review.issues.length > 0 && (
        <details>
          <summary>
            {tn('confidence.issues', review.issues.length)}
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
