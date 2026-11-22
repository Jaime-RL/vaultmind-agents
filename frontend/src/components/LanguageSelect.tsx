import type { ContentLanguage, Language } from '../api/contract.gen'
import { useI18n } from '../i18n/context'
import { LANGUAGE_LABELS } from '../i18n/messages'

const LANGS = Object.keys(LANGUAGE_LABELS) as Language[]

/** Idioma de la interfaz (cabecera). */
export function InterfaceLanguageSelect() {
  const { lang, setLang, t } = useI18n()
  return (
    <select
      className="lang-select"
      aria-label={t('app.language')}
      value={lang}
      onChange={(e) => setLang(e.target.value as Language)}
    >
      {LANGS.map((l) => (
        <option key={l} value={l}>
          {LANGUAGE_LABELS[l]}
        </option>
      ))}
    </select>
  )
}

/** Idioma del contenido (notas o respuestas). «Auto» = el idioma en que se escribe. */
export function ContentLanguageSelect({
  value,
  onChange,
  disabled,
}: {
  value: ContentLanguage
  onChange: (lang: ContentLanguage) => void
  disabled?: boolean
}) {
  const { t } = useI18n()
  return (
    <select
      className="lang-select lang-select--content"
      aria-label={t('content.label')}
      title={value === 'auto' ? t('content.autoHint') : t('content.label')}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as ContentLanguage)}
    >
      <option value="auto">🌐 {t('content.auto')}</option>
      {LANGS.map((l) => (
        <option key={l} value={l}>
          {l.toUpperCase()}
        </option>
      ))}
    </select>
  )
}
