import { useState, type FormEvent } from 'react'
import type { ContentLanguage } from '../../api/contract.gen'
import { ContentLanguageSelect } from '../../components/LanguageSelect'
import { useI18n } from '../../i18n/context'

// Límites de ResearchRequest en contracts/research.schema.json.
const MIN = 3
const MAX = 200

interface Props {
  busy: boolean
  /** `language`: idioma de las notas; «auto» = el idioma en que está escrito el tema. */
  onSubmit: (topic: string, language: ContentLanguage) => void
}

export function ResearchForm({ busy, onSubmit }: Props) {
  const [topic, setTopic] = useState('')
  const [language, setLanguage] = useState<ContentLanguage>('auto')
  const { t } = useI18n()
  const trimmed = topic.trim()
  const valid = trimmed.length >= MIN && trimmed.length <= MAX

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (valid && !busy) onSubmit(trimmed, language)
  }

  return (
    <form className="research-form" onSubmit={handleSubmit}>
      <label htmlFor="topic" className="visually-hidden">
        {t('research.label')}
      </label>
      <input
        id="topic"
        className="research-form__input"
        type="text"
        placeholder={t('research.placeholder')}
        value={topic}
        maxLength={MAX}
        onChange={(event) => setTopic(event.target.value)}
        disabled={busy}
      />
      <ContentLanguageSelect value={language} onChange={setLanguage} disabled={busy} />
      <button type="submit" className="button button--primary" disabled={!valid || busy}>
        {busy ? t('research.busy') : t('research.submit')}
      </button>
    </form>
  )
}
