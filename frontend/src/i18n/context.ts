import { createContext, useContext } from 'react'
import type { Language } from '../api/contract.gen'
import { MESSAGES, type MessageKey } from './messages'

export type TranslateParams = Record<string, string | number>

export interface I18n {
  lang: Language
  setLang: (lang: Language) => void
  /** Texto traducido; `{nombre}` se sustituye por `params.nombre`. */
  t: (key: MessageKey, params?: TranslateParams) => string
  /** Plural sencillo: usa `key.one` si n === 1 y `key.other` si no, con `{n}` ya puesto. */
  tn: (key: string, n: number, params?: TranslateParams) => string
}

export function translate(lang: Language, key: MessageKey, params: TranslateParams = {}): string {
  const text = MESSAGES[lang][key] ?? MESSAGES.es[key] ?? key
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  )
}

export function makeI18n(lang: Language, setLang: (lang: Language) => void = () => {}): I18n {
  const t = (key: MessageKey, params?: TranslateParams) => translate(lang, key, params)
  const tn = (key: string, n: number, params?: TranslateParams) =>
    t(`${key}.${n === 1 ? 'one' : 'other'}` as MessageKey, { n, ...params })
  return { lang, setLang, t, tn }
}

// Sin proveedor (p. ej. en los tests de un componente suelto), la interfaz va en español.
export const I18nContext = createContext<I18n>(makeI18n('es'))

export const useI18n = () => useContext(I18nContext)

/** Formato de números según el idioma (separador de miles). */
export const LOCALES: Record<Language, string> = {
  es: 'es-ES',
  en: 'en-GB',
  fr: 'fr-FR',
  de: 'de-DE',
  pt: 'pt-PT',
}
