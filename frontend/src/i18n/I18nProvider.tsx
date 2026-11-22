import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Language } from '../api/contract.gen'
import { I18nContext, makeI18n } from './context'
import { MESSAGES } from './messages'

const STORAGE_KEY = 'vaultmind.language'

function initialLanguage(): Language {
  // El almacenamiento del navegador puede no existir o fallar (modo privado, iframes).
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved && saved in MESSAGES) return saved as Language
  } catch {
    /* sin almacenamiento: se usa el idioma del navegador */
  }
  const browser = (navigator.language || 'es').slice(0, 2)
  return browser in MESSAGES ? (browser as Language) : 'es'
}

/** Idioma de la interfaz: el guardado, o el del navegador la primera vez. */
export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Language }) {
  const [lang, setLangState] = useState<Language>(() => initial ?? initialLanguage())
  const value = useMemo(
    () =>
      makeI18n(lang, (next) => {
        setLangState(next)
        try {
          window.localStorage.setItem(STORAGE_KEY, next)
        } catch {
          /* no se recuerda entre visitas, pero funciona */
        }
      }),
    [lang],
  )
  // <html lang>: los lectores de pantalla y el navegador saben en qué idioma leer la página.
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
